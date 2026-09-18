"""
Regression tests for the legacy multipart endpoint ``POST /api/v1/ingest`` accepting
CaseData JSON documents (fix: "accept CaseData JSON in legacy ingest endpoint").

Background: the dashboard's folder upload posts ``dataset/case_001_homicide.json``
(CaseData vocabulary: ``source_phone``/``target_phone`` ...) to ``/api/v1/ingest``, which
used to hand every file to the legacy ``CaseIngestionEngine`` whose JSON parser expects the
legacy vocabulary (``caller``/``recipient``) and crashed with ``KeyError: 'caller'`` (HTTP 500).

These tests run against the ``MockSession`` from ``conftest.py`` (no Neo4j needed) and prove:
  A. CaseData JSON (case_001) is accepted with 201 and the frontend-visible response shape;
  H. such a document never enters ``CaseIngestionEngine.parse_file`` and the write statements
     issued are identical to those of ``POST /api/cases/ingest`` for the same document;
  F. legacy free-text / CSV uploads still take the legacy engine path with unchanged results;
  G. malformed JSON and non-CaseData JSON never crash with an unhandled ``KeyError``, and a
     document that declares ``case_metadata`` but is not valid CaseData gets a 4xx;
  plus CaseEnvelope documents and mixed (CaseData + legacy) folder uploads.
The graph-level assertions (B-E) live in ``test_live_neo4j_legacy_ingest_casedata.py``.
"""
import io
import json
import os
import sys
from unittest.mock import patch

import pytest

from tests.integration.test_unified_ingest import SAMPLE_TEXT_INPUT  # noqa: E402  (legacy FIR narrative + CSV blocks)

LEGACY_URL = "/api/v1/ingest"
BULK_URL = "/api/cases/ingest"

CDR_CSV = (
    "Caller_MSISDN,Recipient_MSISDN,Timestamp,Duration_Sec,CellTower_ID\n"
    "9999933333,9999922222,2026-08-25 14:05:00,120,TOWER_DEL_01\n"
    "9999922222,9999911111,2026-08-25 14:15:00,240,TOWER_HR_01\n"
)
BANK_CSV = (
    "Sender_Account,Sender_Name,Receiver_Account,Receiver_Name,Amount_INR,Timestamp,Transaction_ID\n"
    "ACC999991,Vikram Singh,ACC999993,Amit Sharma,500000,2026-08-25 10:00:00,TXN999001\n"
    "ACC999993,Amit Sharma,ACC999992,Rajesh Kumar,480000,2026-08-25 12:00:00,TXN999003\n"
)


def _sample_bytes(name):
    with open(os.path.join("dataset", name), "rb") as f:
        return f.read()


def _sample_doc(name):
    return json.loads(_sample_bytes(name))


def _upload(client, *files):
    """files: (filename, bytes, content_type) tuples -> multipart POST to the legacy endpoint."""
    return client.post(
        LEGACY_URL,
        files=[("files", (name, io.BytesIO(content), mime)) for name, content, mime in files],
    )


@pytest.fixture
def parse_file_spy():
    """Records every CaseIngestionEngine.parse_file call while keeping its behaviour."""
    from backend.services.ingestion_engine import CaseIngestionEngine

    calls = []
    original = CaseIngestionEngine.parse_file

    def spy(self, filename, content, api_key_override=None):
        calls.append(filename)
        return original(self, filename, content, api_key_override)

    with patch.object(CaseIngestionEngine, "parse_file", spy):
        yield calls


def _write_statements(mock_session):
    """(query, parameters) pairs of the graph writes issued through the session, minus health checks."""
    return [(q, p) for q, p in mock_session.queries if "dbms.components" not in q and "gds.version" not in q]


# ---------------------------------------------------------------------------
# A + H: CaseData JSON through the legacy endpoint
# ---------------------------------------------------------------------------

def test_case_001_json_upload_succeeds_with_frontend_response_shape(client, parse_file_spy):
    """A: POST /api/v1/ingest with dataset/case_001_homicide.json -> 201 (was 500 KeyError: 'caller')."""
    r = _upload(client, ("case_001_homicide.json", _sample_bytes("case_001_homicide.json"), "application/json"))
    assert r.status_code == 201, r.text
    data = r.json()

    assert data["case_id"] == "CASE-2024-001"
    assert data["dataset_id"] == "DS-DEFAULT" and data["dataset_version"] == "1.0"
    # Same counts as POST /api/cases/ingest for this document under the MockSession
    # (every MERGE reports was_created=True): 21 nodes, 41 relationships, 1 source record.
    assert data["created"] == {"nodes": 21, "relationships": 41, "source_records": 1}
    assert data["matched_existing_entities"] == 0
    # Fields the dashboard reads (index.html: data.created.nodes / .relationships / data.insights.length).
    assert isinstance(data["insights"], list) and data["new_insights"] == len(data["insights"])
    assert data["warnings"] == []
    # H: the legacy engine was never involved.
    assert parse_file_spy == []


def test_case_001_json_never_enters_legacy_engine_and_matches_bulk_endpoint_writes(client, mock_session, parse_file_spy, monkeypatch):
    """H: CaseData JSON bypasses CaseIngestionEngine and issues exactly the /api/cases/ingest write statements."""
    monkeypatch.setattr("backend.services.blockchain_service.BlockchainService.record_case_evidence_documents", lambda *a, **k: None)
    doc = _sample_doc("case_001_homicide.json")
    mock_session.queries.clear()  # drop the app-startup schema statements (RETURN 1 / CREATE CONSTRAINT ...)

    r_bulk = client.post(BULK_URL, json=doc)
    assert r_bulk.status_code == 201, r_bulk.text
    bulk_statements = _write_statements(mock_session)
    mock_session.queries.clear()
    from backend.services.blockchain_service import BlockchainService
    BlockchainService._chain = []

    r_legacy = _upload(client, ("case_001_homicide.json", _sample_bytes("case_001_homicide.json"), "application/json"))
    assert r_legacy.status_code == 201, r_legacy.text
    legacy_statements = _write_statements(mock_session)

    assert parse_file_spy == [], "CaseData JSON must not be parsed by the legacy CaseIngestionEngine"

    # Same statements, same order, same parameters (the timestamp parameter is the only
    # per-request value, so it is masked before comparing).
    def _mask(statements):
        return [(q, {k: ("<now>" if k == "now" else v) for k, v in p.items()}) for q, p in statements]

    assert _mask(legacy_statements) == _mask(bulk_statements)

    # Identical response bodies apart from the (mocked, deterministic) content: same shape and counts.
    bulk_body, legacy_body = r_bulk.json(), r_legacy.json()
    assert legacy_body["created"] == bulk_body["created"]
    assert legacy_body["case_id"] == bulk_body["case_id"]
    assert legacy_body["matched_existing_entities"] == bulk_body["matched_existing_entities"]
    assert set(legacy_body) == set(bulk_body)


def test_case_data_json_is_detected_by_content_not_extension(client, parse_file_spy):
    """Detection is based on the validated document, not on the '.json' suffix or MIME type."""
    r = _upload(client, ("case_001_homicide.txt", _sample_bytes("case_001_homicide.json"), "text/plain"))
    assert r.status_code == 201, r.text
    assert r.json()["case_id"] == "CASE-2024-001"
    assert r.json()["created"]["nodes"] == 21
    assert parse_file_spy == []


def test_case_envelope_json_is_unwrapped_like_bulk_endpoint(client, parse_file_spy):
    """A CaseEnvelope file ({dataset_id, dataset_version, case_data}) is unwrapped exactly as /api/cases/ingest does."""
    r = _upload(client, ("envelope_sample.json", _sample_bytes("envelope_sample.json"), "application/json"))
    assert r.status_code == 201, r.text
    data = r.json()
    envelope = _sample_doc("envelope_sample.json")
    assert data["case_id"] == envelope["case_data"]["case_metadata"]["case_id"]
    assert data["dataset_id"] == envelope["dataset_id"] == "DS-2026-08"
    assert data["dataset_version"] == envelope["dataset_version"] == "1.0"
    assert parse_file_spy == []


def test_two_case_data_files_are_both_ingested_with_summed_counts(client, mock_session, parse_file_spy):
    """A folder with two CaseData documents ingests both (two Case MERGEs) and reports totals."""
    r = _upload(
        client,
        ("case_001_homicide.json", _sample_bytes("case_001_homicide.json"), "application/json"),
        ("case_002_fraud.json", _sample_bytes("case_002_fraud.json"), "application/json"),
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert parse_file_spy == []

    case_merges = [p["case_id"] for q, p in mock_session.queries if "MERGE (c:Case {case_id: $case_id})" in q]
    assert case_merges == ["CASE-2024-001", "CASE-2024-002"]

    # Totals of the per-document /api/cases/ingest responses under the mock
    # (case_001 = 21 nodes / 41 rels / 1 source record, case_002 = 10 / 18 / 0).
    assert data["case_id"] == "CASE-2024-002"
    assert data["created"] == {"nodes": 31, "relationships": 59, "source_records": 1}
    assert any("Ingested 2 case documents" in w and "CASE-2024-001" in w and "CASE-2024-002" in w for w in data["warnings"])
    assert data["new_insights"] == len(data["insights"])
    assert len({i["insight_id"] for i in data["insights"]}) == len(data["insights"])


# ---------------------------------------------------------------------------
# F: legacy uploads are unchanged
# ---------------------------------------------------------------------------

def test_legacy_text_upload_still_uses_legacy_engine_with_unchanged_result(client, parse_file_spy):
    """F: FIR narrative + CSV blocks (same payload as test_unified_ingest) still go through CaseIngestionEngine."""
    r = _upload(client, ("fir_and_records.txt", SAMPLE_TEXT_INPUT.encode("utf-8"), "text/plain"))
    assert r.status_code == 201, r.text
    data = r.json()
    assert parse_file_spy == ["fir_and_records.txt"]
    assert data["case_id"] == "CASE_0045_2026"
    # Same figures as /api/v1/ingest/text produced for this payload before the fix (MockSession).
    assert data["created"]["nodes"] in (18, 19, 20)
    assert data["created"]["relationships"] in (29, 30, 31)


def test_legacy_csv_uploads_still_use_legacy_engine(client, parse_file_spy):
    """F: CDR and bank CSV files are still parsed by the legacy engine and consolidated into one case."""
    r = _upload(client, ("cdr.csv", CDR_CSV.encode("utf-8"), "text/csv"), ("bank.csv", BANK_CSV.encode("utf-8"), "text/csv"))
    assert r.status_code == 201, r.text
    data = r.json()
    assert parse_file_spy == ["cdr.csv", "bank.csv"]
    assert data["case_id"] == "CASE_001"  # legacy engine default case id
    assert data["created"]["nodes"] >= 4 and data["created"]["relationships"] >= 4


def test_legacy_text_endpoint_is_unchanged(client, parse_file_spy):
    """F: /api/v1/ingest/text behaviour (covered by test_unified_ingest) is untouched by the fix."""
    r = client.post("/api/v1/ingest/text", content=SAMPLE_TEXT_INPUT, headers={"Content-Type": "text/plain"})
    assert r.status_code == 201
    assert r.json()["case_id"] == "CASE_0045_2026"
    assert parse_file_spy == ["input_payload.txt"]


def test_mixed_upload_ingests_case_data_and_legacy_files_separately(client, mock_session, parse_file_spy):
    """CaseData JSON + legacy files in one folder: JSON bypasses the engine, legacy files are consolidated as before."""
    r = _upload(
        client,
        ("case_001_homicide.json", _sample_bytes("case_001_homicide.json"), "application/json"),
        ("fir_and_records.txt", SAMPLE_TEXT_INPUT.encode("utf-8"), "text/plain"),
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert parse_file_spy == ["fir_and_records.txt"]

    case_merges = [p["case_id"] for q, p in mock_session.queries if "MERGE (c:Case {case_id: $case_id})" in q]
    assert case_merges == ["CASE-2024-001", "CASE_0045_2026"]
    assert data["case_id"] == "CASE_0045_2026"
    assert data["created"]["nodes"] in (21 + 18, 21 + 19, 21 + 20)
    assert data["created"]["relationships"] in (41 + 29, 41 + 30, 41 + 31)
    assert any("Ingested 2 case documents" in w for w in data["warnings"])


# ---------------------------------------------------------------------------
# G: malformed / non-CaseData / invalid JSON
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "filename, content",
    [
        ("truncated.json", b'{"case_metadata": {"case_id": "CASE-X", "case_name": "X"'),  # malformed JSON
        ("not_json.json", b"this is not json at all"),
        ("empty.json", b""),
        ("plain_object.json", b'{"foo": 1, "bar": [1, 2]}'),  # valid JSON, not a case document
    ],
)
def test_malformed_or_non_case_json_falls_back_to_legacy_path_without_keyerror(client, parse_file_spy, filename, content):
    """G: content that is not a CaseData document is handled by the legacy engine as before - never an unhandled KeyError."""
    r = _upload(client, (filename, content, "application/json"))
    assert r.status_code == 201, r.text
    assert parse_file_spy == [filename]
    assert r.json()["case_id"] == "CASE_001"  # legacy engine default (nothing extracted)


def test_case_data_with_consolidated_vocabulary_is_mapped_and_succeeds(client, parse_file_spy):
    """Structured JSON with ConsolidatedCaseData vocabulary (caller/recipient, id, msisdn) maps successfully (201) and bypasses extraction."""
    doc = {
        "case_metadata": {"case_id": "CASE-STRUCT-001", "fir_number": "FIR/100/2026"},
        "entities": {
            "people": [{"id": "P-101", "name": "Rajesh Sharma", "status": "Suspect"}],
            "phones": [{"msisdn": "+919999900001", "owner_id": "P-101"}]
        },
        "relationships": {
            "communications": [{"caller": "+919999900001", "recipient": "+919999900002", "timestamp": "2026-08-25T14:05:00"}]
        }
    }
    r = _upload(client, ("case_data.json", json.dumps(doc).encode("utf-8"), "application/json"))
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["case_id"] == "CASE-STRUCT-001"
    assert parse_file_spy == [], "Structured JSON must bypass the legacy unstructured extraction engine"


def test_case_data_with_empty_case_id_is_rejected_with_400_like_bulk_endpoint(client, parse_file_spy):
    """Same guard as /api/cases/ingest: an empty case_metadata.case_id is a 400."""
    doc = {"case_metadata": {"case_id": "", "case_name": "No id"}}
    r = _upload(client, ("no_id.json", json.dumps(doc).encode("utf-8"), "application/json"))
    assert r.status_code == 400, r.text
    assert "case_metadata.case_id" in r.json()["detail"]
    assert parse_file_spy == []


def test_invalid_case_data_writes_nothing(client, mock_session, parse_file_spy):
    """A rejected document (e.g. missing case_id) must not leave partial writes behind, even when uploaded alongside a valid one."""
    mock_session.queries.clear()  # drop the app-startup schema statements
    r = _upload(
        client,
        ("case_001_homicide.json", _sample_bytes("case_001_homicide.json"), "application/json"),
        ("bad_case.json", json.dumps({"case_metadata": {"case_id": ""}}).encode("utf-8"), "application/json"),
    )
    assert r.status_code == 400, r.text
    assert _write_statements(mock_session) == []
    assert parse_file_spy == []

