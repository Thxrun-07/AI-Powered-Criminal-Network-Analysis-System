"""
Step 1B regression tests for the batched relationship writers
(CALLED, TRANSFERRED_TO + Transaction, surveillance LOCATED_AT, PriorCase / HAS_PRIOR_CASE,
intelligence SourceRecord) and for the shared write definitions in backend.services.graph_writes.

Everything here runs against the repository's MockSession (tests/conftest.py) or a
small extension of it; live behaviour is covered by tests/test_live_neo4j_step1b.py.
"""
import json
import os
import re
import sys

import pytest

from tests.conftest import MockSession, MockResult, MockRecord  # noqa: E402

from backend.models.case_input import CaseData  # noqa: E402
from backend.services import graph_writes as gw  # noqa: E402
from backend.services.ingestion_service import IngestionService  # noqa: E402
from backend.services.insights_engine import InsightsEngine  # noqa: E402

EDGE_FIXTURE = os.path.join(os.path.dirname(__file__), "..", "fixtures", "case_edge_batching.json")


def _load(path: str) -> CaseData:
    with open(path, "r", encoding="utf-8") as f:
        return CaseData(**json.load(f))


def _sample(name: str) -> CaseData:
    return _load(os.path.join("dataset", name))


def _norm(q: str) -> str:
    return " ".join(q.split())


def _ingest(case_data: CaseData, monkeypatch, session=None):
    session = session or MockSession()
    monkeypatch.setattr(InsightsEngine, "run_all_detectors", staticmethod(lambda *a, **k: []))
    response = IngestionService.ingest_case(session, case_data)
    return session, response


def _find(session, statement: str):
    """Return [(query, params)] entries whose normalized text equals the normalized statement."""
    target = _norm(statement)
    return [(q, p) for q, p in session.queries if _norm(q) == target]


# ---------------------------------------------------------------------------
# 1. Structural: every batched relationship writer is issued exactly once, as UNWIND
# ---------------------------------------------------------------------------

def test_case_001_issues_one_batch_per_relationship_writer(monkeypatch):
    session, _ = _ingest(_sample("case_001_homicide.json"), monkeypatch)
    expected_writers = [
        "CALLED_MERGE", "TRANSACTIONS_MERGE", "SURVEILLANCE_LOCATIONS_MERGE",
        "SURVEILLANCE_PERSON_LOCATED_AT", "SURVEILLANCE_VEHICLE_LOCATED_AT",
        "PRIOR_CASES_MERGE", "INTEL_REPORTS_MERGE"
    ]
    for name in expected_writers:
        stmt = gw.BATCHED_RELATIONSHIP_STATEMENTS[name]
        hits = _find(session, stmt)
        assert len(hits) == 1, f"{name} expected exactly once, got {len(hits)}"
        assert _norm(stmt).startswith("UNWIND $rows AS row"), name
        assert "rows" in hits[0][1] and isinstance(hits[0][1]["rows"], list)


def test_no_per_record_relationship_queries_remain(monkeypatch):
    """No statement in the ingestion path may bind a per-record value as a top-level $param."""
    session, _ = _ingest(_load(EDGE_FIXTURE), monkeypatch)
    forbidden = {"$src_phone", "$dst_phone", "$call_id", "$src_acc", "$dst_acc", "$tx_id",
                 "$loc_id", "$p_id", "$vin", "$log_id", "$prior_id", "$person_id", "$report_id"}
    for q, _ in session.queries:
        assert not (forbidden & set(re.findall(r"\$\w+", q))), f"per-record parameter found in:\n{q}"


def test_empty_collections_issue_no_relationship_batches(monkeypatch):
    envelope = json.load(open(os.path.join("dataset", "envelope_sample.json")))
    case_data = CaseData(**envelope["case_data"])
    session, _ = _ingest(case_data, monkeypatch)
    for name, stmt in gw.BATCHED_RELATIONSHIP_STATEMENTS.items():
        assert _find(session, stmt) == [], f"{name} must not run for an empty collection"
    assert len(session.queries) == 4  # Case, People, Phones, OWNS (unchanged from before)


def test_ingestion_only_issues_statements_defined_in_graph_writes(monkeypatch):
    """Guard for the DeltaProcessor contract: every write the bulk path issues lives in graph_writes."""
    session, _ = _ingest(_load(EDGE_FIXTURE), monkeypatch)
    known = {_norm(s) for s in gw.ALL_WRITE_STATEMENTS.values()}
    for q, _ in session.queries:
        assert _norm(q) in known, f"statement not defined in graph_writes:\n{q}"


# ---------------------------------------------------------------------------
# 2. Write order is preserved
# ---------------------------------------------------------------------------

def test_relationship_batches_run_in_original_order(monkeypatch):
    session, _ = _ingest(_load(EDGE_FIXTURE), monkeypatch)
    order = [gw.CALLED_MERGE, gw.TRANSACTIONS_MERGE, gw.SURVEILLANCE_LOCATIONS_MERGE,
             gw.SURVEILLANCE_PERSON_LOCATED_AT, gw.SURVEILLANCE_VEHICLE_LOCATED_AT,
             gw.PRIOR_CASES_MERGE, gw.INTEL_REPORTS_MERGE]
    idx = [next(i for i, (q, _) in enumerate(session.queries) if _norm(q) == _norm(s)) for s in order]
    assert idx == sorted(idx), f"batch order changed: {idx}"
    # ... and all of them after the last entity batch (cell tower LOCATED_AT) exactly as before.
    tower_idx = next(i for i, (q, _) in enumerate(session.queries) if _norm(q) == _norm(gw.CELL_TOWER_LOCATED_AT)) \
        if _find(session, gw.CELL_TOWER_LOCATED_AT) else -1
    assert idx[0] > tower_idx


# ---------------------------------------------------------------------------
# 3. Parameter construction (row builders) — one assertion block per writer
# ---------------------------------------------------------------------------

def test_called_rows_and_call_id_fallbacks(monkeypatch):
    case_data = _load(EDGE_FIXTURE)
    session, _ = _ingest(case_data, monkeypatch)
    (q, params), = _find(session, gw.CALLED_MERGE)
    assert set(params) == {"rows", "case_id", "now"}
    assert params["case_id"] == "CASE-EDGE-001"
    rows = params["rows"]
    assert len(rows) == len(case_data.relationships.communications) == 4
    # explicit call_id
    assert rows[0] == {"src_phone": "+91E1", "dst_phone": "+91E2", "call_id": "CALL-E-1",
                       "timestamp": "2026-01-01T10:00:00Z", "duration_seconds": 60, "type": "VOICE_CALL",
                       "cell_tower": "T-E1", "source_record_id": "SR-E-1"}
    # duplicate key in the same batch is kept as its own row (MERGE semantics decide the outcome)
    assert rows[1]["call_id"] == "CALL-E-1" and rows[1]["cell_tower"] is None and rows[1]["duration_seconds"] == 90
    # communication_id fallback
    assert rows[2]["call_id"] == "COMM-E-2" and rows[2]["type"] == "SMS"
    # synthesized fallback + duration None -> 0
    assert rows[3]["call_id"] == "CALL_+91E3_+91E1_2026-01-01T12:00:00Z"
    assert rows[3]["duration_seconds"] == 0
    # every row has exactly the keys the Cypher references
    for r in rows:
        assert set(r) == {"src_phone", "dst_phone", "call_id", "timestamp", "duration_seconds", "type", "cell_tower", "source_record_id"}


def test_transaction_rows(monkeypatch):
    case_data = _load(EDGE_FIXTURE)
    session, _ = _ingest(case_data, monkeypatch)
    (q, params), = _find(session, gw.TRANSACTIONS_MERGE)
    assert set(params) == {"rows", "case_id", "now"}
    rows = params["rows"]
    assert len(rows) == 3
    assert rows[0] == {"src_acc": "ACC-E1", "dst_acc": "ACC-E2", "tx_id": "TX-E-1", "amount": 100.0, "currency": "INR",
                       "timestamp": "2026-01-02T10:00:00Z", "tx_type": "NEFT", "reference_no": "REF-1", "description": None, "source_record_id": "SR-E-1"}
    assert rows[2]["currency"] == "USD" and rows[2]["tx_type"] == "WIRE" and rows[2]["reference_no"] is None


def test_surveillance_rows_split_and_location_fallback(monkeypatch):
    case_data = _load(EDGE_FIXTURE)
    session, _ = _ingest(case_data, monkeypatch)
    (_, loc), = _find(session, gw.SURVEILLANCE_LOCATIONS_MERGE)
    (_, per), = _find(session, gw.SURVEILLANCE_PERSON_LOCATED_AT)
    (_, veh), = _find(session, gw.SURVEILLANCE_VEHICLE_LOCATED_AT)

    assert set(loc) == {"rows", "case_id", "now"}
    assert [r["loc_id"] for r in loc["rows"]] == ["LOC-E1", "LOC_SURV-E-2", "LOC-E1"]  # one row per log, as before
    assert loc["rows"][1] == {"loc_id": "LOC_SURV-E-2", "name": "LOC_SURV-E-2", "latitude": None, "longitude": None}
    assert loc["rows"][0] == {"loc_id": "LOC-E1", "name": "Edge Plaza", "latitude": 1.0, "longitude": 2.0}

    # LOCATED_AT batches carry no $now (the original per-row statements did not set created_at either)
    assert set(per) == {"rows", "case_id"} and set(veh) == {"rows", "case_id"}
    assert [(r["p_id"], r["log_id"]) for r in per["rows"]] == [("P-E1", "SURV-E-1"), ("P-E2", "SURV-E-1"),
                                                               ("P-E1", "SURV-E-2"), ("P-MISSING", "SURV-E-2"),
                                                               ("P-E2", "SURV-E-3")]
    assert per["rows"][0] == {"p_id": "P-E1", "loc_id": "LOC-E1", "log_id": "SURV-E-1", "timestamp": "2026-01-03T09:00:00Z",
                              "activity": "Meeting", "evidence": "CAM-1.mp4", "sr_id": "SR-E-1"}
    assert [(r["vin"], r["log_id"]) for r in veh["rows"]] == [("VIN-E1", "SURV-E-1"), ("VIN-MISSING", "SURV-E-2")]
    assert veh["rows"][0] == {"vin": "VIN-E1", "loc_id": "LOC-E1", "log_id": "SURV-E-1", "timestamp": "2026-01-03T09:00:00Z", "activity": "Meeting"}
    # observed_phone_numbers is NOT persisted (unchanged behaviour): no statement references it
    assert not any("phone" in _norm(q).lower() and "LOCATED_AT" in q for q, _ in session.queries)


def test_prior_case_rows(monkeypatch):
    case_data = _load(EDGE_FIXTURE)
    session, _ = _ingest(case_data, monkeypatch)
    (_, params), = _find(session, gw.PRIOR_CASES_MERGE)
    assert set(params) == {"rows", "case_id", "now"}
    assert params["rows"][0] == {"prior_id": "CRIM-E-1", "case_num": "CC-E-1", "offense": "Test Offense", "jurisdiction": None,
                                 "status": "CONVICTED", "year": 2020, "person_id": "P-E1"}
    assert [r["person_id"] for r in params["rows"]] == ["P-E1", "P-MISSING", "P-E2"]


def test_intel_report_rows(monkeypatch):
    case_data = _load(EDGE_FIXTURE)
    session, _ = _ingest(case_data, monkeypatch)
    (_, params), = _find(session, gw.INTEL_REPORTS_MERGE)
    assert set(params) == {"rows", "case_id", "now"}
    assert params["rows"] == [
        {"report_id": "INTEL-E-1", "agency": "Unit A", "reliability": 0.9, "content": "First memo"},
        {"report_id": "INTEL-E-2", "agency": "Unit B", "reliability": 1.0, "content": "Second memo"},
        {"report_id": "INTEL-E-1", "agency": "Unit C", "reliability": 0.1, "content": "Duplicate id, must not overwrite"},
    ]
    # entities_mentioned is not persisted (unchanged behaviour)
    assert not any("entities_mentioned" in q for q, _ in session.queries)


# ---------------------------------------------------------------------------
# 4. Cypher text of the batched statements: same MERGE keys / ON CREATE / ON MATCH as the per-row originals
# ---------------------------------------------------------------------------

def test_called_statement_semantics():
    q = _norm(gw.CALLED_MERGE)
    assert "MERGE (p1:Phone {phone_number: row.src_phone}) ON CREATE SET p1.created_at = $now, p1.updated_at = $now, p1.case_ids = [$case_id]" in q
    assert "MERGE (p2:Phone {phone_number: row.dst_phone}) ON CREATE SET p2.created_at = $now, p2.updated_at = $now, p2.case_ids = [$case_id]" in q
    assert "ON MATCH SET p1.updated_at = $now, p1.case_ids = CASE WHEN $case_id IN p1.case_ids THEN p1.case_ids ELSE p1.case_ids + $case_id END" in q
    assert "ON MATCH SET p2.updated_at = $now, p2.case_ids = CASE WHEN $case_id IN p2.case_ids THEN p2.case_ids ELSE p2.case_ids + $case_id END" in q
    assert "MERGE (p1)-[r:CALLED {call_id: row.call_id}]->(p2)" in q
    assert ("ON CREATE SET r.timestamp = row.timestamp, r.duration_seconds = row.duration_seconds, r.type = row.type, "
            "r.cell_tower = row.cell_tower, r.source_record_id = row.source_record_id, r.case_id = $case_id, r.created_at = $now") in q
    assert "ON MATCH SET r.duration_seconds = row.duration_seconds, r.cell_tower = coalesce(row.cell_tower, r.cell_tower)" in q
    assert "RETURN" not in q


def test_transactions_statement_semantics():
    q = _norm(gw.TRANSACTIONS_MERGE)
    assert "MERGE (b1:BankAccount {account_number: row.src_acc}) ON CREATE SET b1.created_at = $now, b1.updated_at = $now, b1.case_ids = [$case_id]" in q
    assert "MERGE (b2:BankAccount {account_number: row.dst_acc}) ON CREATE SET b2.created_at = $now, b2.updated_at = $now, b2.case_ids = [$case_id]" in q
    assert "ON MATCH SET b1.updated_at = $now, b1.case_ids = CASE WHEN $case_id IN b1.case_ids THEN b1.case_ids ELSE b1.case_ids + $case_id END" in q
    assert "ON MATCH SET b2.updated_at = $now, b2.case_ids = CASE WHEN $case_id IN b2.case_ids THEN b2.case_ids ELSE b2.case_ids + $case_id END" in q
    assert ("MERGE (t:Transaction {transaction_id: row.tx_id}) ON CREATE SET t.amount = row.amount, t.currency = row.currency, "
            "t.timestamp = row.timestamp, t.transaction_type = row.tx_type, t.reference_no = row.reference_no, "
            "t.description = row.description, "
            "t.source_record_id = row.source_record_id, t.created_at = $now, t.case_ids = [$case_id]") in q
    assert ("MERGE (b1)-[r:TRANSFERRED_TO {transaction_id: row.tx_id}]->(b2) ON CREATE SET r.amount = row.amount, r.currency = row.currency, "
            "r.timestamp = row.timestamp, r.transaction_type = row.tx_type, r.reference_no = row.reference_no, "
            "r.description = row.description, "
            "r.source_record_id = row.source_record_id, r.case_id = $case_id") in q
    assert "WITH t MATCH (c:Case {case_id: $case_id}) MERGE (c)-[:INVOLVES]->(t) RETURN (t.created_at = $now) AS was_created" in q


def test_surveillance_statements_semantics():
    q = _norm(gw.SURVEILLANCE_LOCATIONS_MERGE)
    assert q == ("UNWIND $rows AS row MERGE (l:Location {location_id: row.loc_id}) ON CREATE SET l.name = row.name, "
                 "l.latitude = row.latitude, l.longitude = row.longitude, l.created_at = $now, l.case_ids = [$case_id]")
    q = _norm(gw.SURVEILLANCE_PERSON_LOCATED_AT)
    assert q == ("UNWIND $rows AS row MATCH (p:Person {person_id: row.p_id}), (l:Location {location_id: row.loc_id}) "
                 "MERGE (p)-[r:LOCATED_AT {log_id: row.log_id}]->(l) ON CREATE SET r.timestamp = row.timestamp, "
                 "r.activity_description = row.activity, r.evidence_ref = row.evidence, r.case_id = $case_id, r.source_record_id = row.sr_id")
    q = _norm(gw.SURVEILLANCE_VEHICLE_LOCATED_AT)
    assert q == ("UNWIND $rows AS row MATCH (v:Vehicle {vin: row.vin}), (l:Location {location_id: row.loc_id}) "
                 "MERGE (v)-[r:LOCATED_AT {log_id: row.log_id}]->(l) ON CREATE SET r.timestamp = row.timestamp, "
                 "r.activity_description = row.activity, r.case_id = $case_id")


def test_prior_case_statement_semantics():
    q = _norm(gw.PRIOR_CASES_MERGE)
    assert ("MERGE (pc:PriorCase {prior_case_id: row.prior_id}) ON CREATE SET pc.case_number = row.case_num, pc.offense = row.offense, "
            "pc.jurisdiction = row.jurisdiction, pc.status = row.status, pc.year = row.year, pc.created_at = $now, pc.updated_at = $now, "
            "pc.case_ids = [$case_id] ON MATCH SET pc.updated_at = $now, "
            "pc.case_ids = CASE WHEN $case_id IN pc.case_ids THEN pc.case_ids ELSE pc.case_ids + $case_id END") in q
    # `row` must be carried through the first WITH so row.person_id is still in scope
    assert "WITH row, pc MATCH (p:Person {person_id: row.person_id}) MERGE (p)-[:HAS_PRIOR_CASE]->(pc)" in q
    assert "WITH pc MATCH (c:Case {case_id: $case_id}) MERGE (c)-[:INVOLVES]->(pc) RETURN (pc.created_at = $now) AS was_created" in q


def test_intel_statement_semantics():
    q = _norm(gw.INTEL_REPORTS_MERGE)
    assert ("MERGE (sr:SourceRecord {source_record_id: row.report_id}) ON CREATE SET sr.source_type = 'INTELLIGENCE_REPORT', "
            "sr.source_agency = row.agency, sr.reliability_score = row.reliability, sr.content = row.content, "
            "sr.created_at = $now, sr.case_ids = [$case_id]") in q
    assert "ON MATCH" not in q  # unchanged: intel SourceRecords are never updated on match
    assert "WITH sr MATCH (c:Case {case_id: $case_id}) MERGE (c)-[:INVOLVES]->(sr) RETURN (sr.created_at = $now) AS was_created" in q


# ---------------------------------------------------------------------------
# 5. Response counts are unchanged (values recorded from the pre-batching code on the same payloads)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("payload, nodes, rels, src, matched", [
    ("dataset/case_001_homicide.json", 21, 41, 1, 0),
    ("dataset/case_002_fraud.json", 10, 18, 0, 0),
    (EDGE_FIXTURE, 20, 44, 4, 0),
])
def test_counts_unchanged_on_all_created_path(payload, nodes, rels, src, matched, monkeypatch):
    _, resp = _ingest(_load(payload), monkeypatch)
    assert (resp.created.nodes, resp.created.relationships, resp.created.source_records, resp.matched_existing_entities) == (nodes, rels, src, matched)


class StatefulMockSession(MockSession):
    """MockSession variant that reports per-row was_created based on a set of pre-existing keys and
    returns NO row for PriorCase records whose Person is missing (as Neo4j does after a failed MATCH)."""

    def __init__(self, existing_keys=(), missing_persons=()):
        super().__init__()
        self.existing = set(existing_keys)
        self.missing_persons = set(missing_persons)

    def run(self, query, parameters=None):
        q = " ".join(query.split())
        params = parameters or {}
        if q.startswith("UNWIND $rows AS row") and "AS was_created" in q:
            self.queries.append((query, params))
            out = []
            for row in params.get("rows", []):
                key = row.get("tx_id") or row.get("prior_id") or row.get("report_id") or row.get("person_id") \
                    or row.get("phone_number") or row.get("account_number") or row.get("source_record_id")
                if "prior_id" in row and row.get("person_id") in self.missing_persons:
                    continue  # MATCH (p:Person) fails -> the row yields nothing
                out.append(MockRecord({"was_created": key not in self.existing}))
            return MockResult(out)
        return super().run(query, parameters)


def test_counts_on_match_and_missing_person_paths(monkeypatch):
    """Batched counting must equal the old per-record arithmetic:
    - per record: was_created -> nodes_created, else -> nodes_matched (including records that returned no row);
    - relationships are counted per input record regardless of outcome (as before)."""
    case_data = _load(EDGE_FIXTURE)
    session = StatefulMockSession(existing_keys={"TX-E-2", "CRIM-E-1", "INTEL-E-2"}, missing_persons={"P-MISSING"})
    _, resp = _ingest(case_data, monkeypatch, session=session)

    # All-created baseline for this fixture is nodes=20, matched=0 (see parametrized test above).
    # Existing TX-E-2 (-1 created, +1 matched), CRIM-E-1 appears twice -> both rows match (-2 created, +2 matched),
    # CRIM-E-2's person is missing -> no row -> matched (-1 created, +1 matched),
    # INTEL-E-2 exists (-1 created, +1 matched).
    assert resp.created.nodes == 20 - 5
    assert resp.matched_existing_entities == 5
    assert resp.created.relationships == 44  # unchanged: counted per input record
    assert resp.created.source_records == 4


# ---------------------------------------------------------------------------
# 6. Backward compatibility of the helper and the shared row builders
# ---------------------------------------------------------------------------

def test_run_batch_helper_is_delegated_and_skips_empty():
    session = MockSession()
    assert IngestionService._run_batch(session, "UNWIND $rows AS row RETURN row", [], {"x": 1}) == []
    assert session.queries == []
    IngestionService._run_batch(session, "UNWIND $rows AS row RETURN row", [{"a": 1}], {"x": 1})
    assert session.queries[0][1] == {"x": 1, "rows": [{"a": 1}]}


def test_shared_row_builders_match_models():
    from backend.models.relationship import CommunicationRecord, SurveillanceLogRecord
    c = CommunicationRecord(source_phone="A", target_phone="B", timestamp="T")
    assert gw.communication_row(c)["call_id"] == "CALL_A_B_T"
    s = SurveillanceLogRecord(log_id="L1", timestamp="T", observed_person_ids=["P1", "P2"], observed_vehicle_vins=["V1"])
    assert gw.surveillance_location_id(s) == "LOC_L1"
    assert gw.surveillance_location_row(s)["name"] == "LOC_L1"
    assert [r["p_id"] for r in gw.surveillance_person_rows(s)] == ["P1", "P2"]
    assert [r["vin"] for r in gw.surveillance_vehicle_rows(s)] == ["V1"]
    assert set(gw.BATCHED_RELATIONSHIP_STATEMENTS) <= set(gw.ALL_WRITE_STATEMENTS)
