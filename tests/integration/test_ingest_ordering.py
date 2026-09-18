"""
Step 0 regression tests (mock-session level).

Defect 1: FIR -> accused Person INVOLVES links were written BEFORE the Person
batch, so on first ingestion the `MATCH (p:Person ...)` found nothing and the
relationship was silently skipped while still being counted.

Defect 2: Person.aliases / Person.roles ON MATCH concatenated lists without
de-duplication, so every re-ingestion of the same case appended duplicates.

These tests inspect the exact Cypher statements and their order using the
repository's own MockSession (tests/conftest.py). Live-Neo4j behaviour is
covered separately in tests/test_live_neo4j_step0.py.
"""
import json
import os
import re
import sys

import pytest

from tests.conftest import MockSession  # noqa: E402

from backend.models.case_input import CaseData  # noqa: E402
from backend.services.ingestion_service import IngestionService  # noqa: E402
from backend.services.insights_engine import InsightsEngine  # noqa: E402


def _load_case(filename: str) -> CaseData:
    path = os.path.join("dataset", filename)
    with open(path, "r", encoding="utf-8") as f:
        return CaseData(**json.load(f))


def _norm(q: str) -> str:
    return " ".join(q.split())


def _ingest_with_query_log(case_data: CaseData, monkeypatch):
    session = MockSession()
    # Insights are out of scope for these tests; keep the log to ingestion writes only.
    monkeypatch.setattr(InsightsEngine, "run_all_detectors", staticmethod(lambda *a, **k: []))
    response = IngestionService.ingest_case(session, case_data)
    return session, response


def test_fir_accused_links_written_after_person_batch(monkeypatch):
    case_data = _load_case("case_001_homicide.json")
    assert case_data.fir_records and case_data.fir_records[0].accused_person_ids, "fixture must contain accused ids"

    session, _ = _ingest_with_query_log(case_data, monkeypatch)
    queries = [_norm(q) for q, _ in session.queries]

    person_batch_idx = [i for i, q in enumerate(queries) if q.startswith("UNWIND $rows AS row MERGE (p:Person")]
    accused_idx = [i for i, q in enumerate(queries) if "MATCH (f:FIR {fir_id: $fir_id}), (p:Person {person_id: $acc_id})" in q]

    assert len(person_batch_idx) == 1, "expected exactly one Person UNWIND batch"
    assert len(accused_idx) == len(case_data.fir_records[0].accused_person_ids)
    # The defect: accused links ran BEFORE the Person batch. They must now run AFTER it.
    assert all(i > person_batch_idx[0] for i in accused_idx), (
        f"FIR->accused links at {accused_idx} must come after Person batch at {person_batch_idx[0]}"
    )


def test_fir_accused_links_use_original_merge_and_params(monkeypatch):
    """The deferred write must be the exact same MATCH/MERGE statement and parameters as before."""
    case_data = _load_case("case_001_homicide.json")
    session, _ = _ingest_with_query_log(case_data, monkeypatch)

    accused = [(q, p) for q, p in session.queries if "person_id: $acc_id" in q]
    expected_ids = case_data.fir_records[0].accused_person_ids
    assert [p["acc_id"] for _, p in accused] == expected_ids
    for q, p in accused:
        assert p["fir_id"] == case_data.fir_records[0].fir_id
        assert "MERGE (f)-[:INVOLVES]->(p)" in _norm(q)
        assert set(p.keys()) == {"fir_id", "acc_id"}


def test_fir_accused_relationship_count_unchanged(monkeypatch):
    """Reordering must not change the reported relationship counts (semantics preserved)."""
    case_data = _load_case("case_001_homicide.json")
    _, response = _ingest_with_query_log(case_data, monkeypatch)
    # Value observed on the unmodified baseline for this fixture (see verification report).
    assert response.created.relationships == 41
    assert response.created.nodes == 21


def test_person_on_match_deduplicates_aliases_and_roles(monkeypatch):
    """The Person ON MATCH clause must de-duplicate aliases and roles instead of blind concatenation."""
    case_data = _load_case("case_001_homicide.json")
    session, _ = _ingest_with_query_log(case_data, monkeypatch)

    person_q = next(_norm(q) for q, _ in session.queries if q.lstrip().startswith("UNWIND $rows AS row") and "MERGE (p:Person" in q)

    # Old (defective) expressions must be gone.
    assert "p.aliases=[x IN (coalesce(p.aliases,[]) + coalesce(row.aliases,[])) WHERE x IS NOT NULL]" not in person_q
    assert "p.roles=[x IN (coalesce(p.roles,[]) + coalesce(row.roles,[])) WHERE x IS NOT NULL]" not in person_q

    # New expressions: order-preserving reduce() with membership check, still dropping NULLs.
    for prop in ("aliases", "roles"):
        m = re.search(
            rf"p\.{prop}=reduce\(acc=\[\], x IN \(coalesce\(p\.{prop},\[\]\) \+ coalesce\(row\.{prop},\[\]\)(?: \+ \[.*?\])?\) \| "
            rf"CASE WHEN x IS NULL OR x IN acc THEN acc ELSE acc \+ x END\)",
            person_q,
        )
        assert m, f"expected de-duplicating reduce() for p.{prop}, got:\n{person_q}"

    # Everything else in the ON MATCH clause is unchanged.
    for unchanged in (
        "p.name=coalesce(p.name, row.name)",
        "p.dob=coalesce(p.dob, row.dob)",
        "p.national_id=coalesce(p.national_id, row.national_id)",
        "p.risk_level=coalesce(p.risk_level, row.risk_level)",
        "p.case_ids=CASE WHEN $case_id IN p.case_ids THEN p.case_ids ELSE p.case_ids + $case_id END",
    ):
        assert unchanged in person_q


def test_person_on_create_unchanged(monkeypatch):
    case_data = _load_case("case_001_homicide.json")
    session, _ = _ingest_with_query_log(case_data, monkeypatch)
    person_q = next(_norm(q) for q, _ in session.queries if q.lstrip().startswith("UNWIND $rows AS row") and "MERGE (p:Person" in q)
    for expected in ["ON CREATE SET", "p.name=row.name", "p.aliases=row.aliases", "p.age=row.age", "p.dob=row.dob"]:
        assert expected in person_q
    assert "p.case_ids=[$case_id], p.source_record_ids=row.source_record_ids" in person_q


def test_requirements_include_python_multipart():
    with open("requirements.txt", "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip()]
    assert any(l.startswith("python-multipart") for l in lines), "python-multipart missing from requirements.txt"
    # Style: one dependency per line with a >= pin, like the rest of the file.
    assert any(re.fullmatch(r"python-multipart>=\d+\.\d+\.\d+", l) for l in lines)
