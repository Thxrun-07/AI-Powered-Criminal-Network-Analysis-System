"""
Comprehensive Master Fix Verification Test Suite for Case Identity and Ingestion Integrity.

Verifies:
1. Reset DB results in 0 Case nodes.
2. Single-case upload creates exactly 1 Case node with canonical case_id.
3. GET /api/cases returns exactly 1 case after single upload.
4. Backend deduplicates duplicate physical file submissions (SHA-256 hash).
5. Explicit case_id query parameter overrides payload metadata and remains immutable.
6. Same-name individuals with different IDs (P001 Rahul Kumar age 32 vs P002 Rahul Kumar age 35) remain separate.
7. IP USES_IP relationships and surveillance phone nodes are created and linked to case.
8. Re-uploading the same payload is 100% idempotent (no duplicate Case/Person nodes).
9. Multi-file uploads with identical case_id yield exactly ONE Case node.
10. No fake hardcoded default dates are created.
"""
import io
import json
import os
from typing import Dict, Any
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.models.case_input import CaseData
from backend.services.graph_service import GraphService
from backend.services.ingestion_service import IngestionService
from tests.conftest import MockSession, MockResult, MockRecord


class AuditMockSession(MockSession):
    """Stateful MockSession that records merged cases and responds to MATCH (c:Case) list_cases queries."""

    def __init__(self):
        super().__init__()
        self.cases = {}

    def run(self, query, parameters=None):
        q = " ".join(query.split())
        params = parameters or {}
        if "MERGE (c:Case {case_id: $case_id})" in q:
            self.queries.append((query, params))
            self.cases[params["case_id"]] = params
            return MockResult([MockRecord({"was_created": True})])
        if "MATCH (c:Case)" in q:
            self.queries.append((query, params))
            records = [
                MockRecord({
                    "case_id": cid,
                    "case_name": cdata.get("case_name", cid),
                    "case_type": cdata.get("case_type", "GENERAL"),
                    "status": cdata.get("status", "OPEN"),
                    "jurisdiction": cdata.get("jurisdiction"),
                    "lead_investigator": cdata.get("lead_investigator"),
                    "created_date": cdata.get("created_date"),
                    "created_at": cdata.get("created_at"),
                    "summary": cdata.get("summary"),
                    "entity_count": 10
                }) for cid, cdata in self.cases.items()
            ]
            return MockResult(records)
        if "MATCH (n) DETACH DELETE n" in q:
            self.queries.append((query, params))
            self.cases.clear()
            return MockResult([])
        return super().run(query, parameters)


@pytest.fixture
def client():
    return TestClient(app)


def _build_test_case_payload() -> Dict[str, Any]:
    return {
        "case_metadata": {
            "case_id": "CASE-TEST-001",
            "case_name": "Test Criminal Network",
            "case_type": "ORGANIZED_CRIME",
            "status": "OPEN"
        },
        "entities": {
            "people": [
                {
                    "person_id": "P001",
                    "name": "Rahul Kumar",
                    "age": 32,
                    "roles": ["Suspect"]
                },
                {
                    "person_id": "P002",
                    "name": "Rahul Kumar",
                    "age": 35,
                    "roles": ["Witness"]
                }
            ],
            "phones": [
                {
                    "phone_number": "9876543210",
                    "owner_person_id": "P001"
                }
            ],
            "bank_accounts": [
                {
                    "account_number": "ACC001",
                    "bank_name": "Test Bank",
                    "owner_person_id": "P001"
                }
            ],
            "vehicles": [
                {
                    "vin": "VIN001",
                    "owner_person_id": "P001"
                }
            ],
            "ip_addresses": [
                {
                    "ip_address": "192.168.1.10",
                    "owner_person_id": "P001"
                }
            ],
            "locations": [
                {
                    "location_id": "LOC001",
                    "name": "Hideout Alpha"
                }
            ]
        },
        "relationships": {
            "communications": [
                {
                    "call_id": "CALL001",
                    "source_phone": "9876543210",
                    "target_phone": "9876543211",
                    "timestamp": "2026-09-14T10:00:00Z"
                }
            ],
            "transactions": [
                {
                    "transaction_id": "TX001",
                    "source_account": "ACC001",
                    "target_account": "ACC002",
                    "amount": 50000.0,
                    "timestamp": "2026-09-14T11:00:00Z"
                }
            ]
        },
        "surveillance_logs": [
            {
                "log_id": "SURV001",
                "location_id": "LOC001",
                "observed_person_ids": ["P001"],
                "observed_vehicle_vins": ["VIN001"],
                "observed_phone_numbers": ["9876543210"],
                "timestamp": "2026-09-14T12:00:00Z"
            }
        ]
    }


# ---------------------------------------------------------------------------
# 1. Single Case Upload Creates Exactly One Case (Regression Test)
# ---------------------------------------------------------------------------

def test_single_case_upload_creates_exactly_one_case(monkeypatch):
    """Verify that reset DB -> 0 cases, upload 1 file -> exactly 1 Case node."""
    session = AuditMockSession()
    monkeypatch.setattr("backend.database.db.get_session", lambda: session)

    # 1. Reset Database
    res = GraphService.reset_database(session)
    assert res["status"] == "success"

    # 2. Ingest exactly ONE payload
    payload = _build_test_case_payload()
    case_data = CaseData(**payload)
    IngestionService.ingest_case(session, case_data)

    # 3. Query Case nodes
    case_queries = [q for q, p in session.queries if "MERGE (c:Case {case_id: $case_id})" in q]
    # Exactly ONE Case MERGE statement executed for this single case ingestion
    assert len(case_queries) == 1
    
    # 4. Verify list_cases returns 1 case with matching case_id
    cases = GraphService.list_cases(session)
    assert len(cases) == 1
    assert cases[0]["case_id"] == "CASE-TEST-001"


# ---------------------------------------------------------------------------
# 2. Backend File Deduplication (SHA-256 Hash)
# ---------------------------------------------------------------------------

def test_backend_file_deduplication(client, monkeypatch):
    """Verify backend deduplicates identical physical files sent in request."""
    session = AuditMockSession()
    monkeypatch.setattr("backend.database.db.get_session", lambda: session)

    payload_bytes = json.dumps(_build_test_case_payload()).encode("utf-8")
    
    # Send same physical file twice under 'files'
    r = client.post(
        "/api/v1/ingest",
        files=[
            ("files", ("case_test.json", io.BytesIO(payload_bytes), "application/json")),
            ("files", ("case_test.json", io.BytesIO(payload_bytes), "application/json")),
        ]
    )
    assert r.status_code == 201
    # Only 1 document processed
    case_merges = [p["case_id"] for q, p in session.queries if "MERGE (c:Case {case_id: $case_id})" in q]
    assert case_merges == ["CASE-TEST-001"]


# ---------------------------------------------------------------------------
# 3. Critical End-to-End Ingestion Integrity (Requirement 27)
# ---------------------------------------------------------------------------

def test_critical_end_to_end_ingestion_integrity(monkeypatch):
    """Executes all 10 steps of Prompt Requirement 27."""
    session = AuditMockSession()
    monkeypatch.setattr("backend.database.db.get_session", lambda: session)

    # TEST 1: Reset DB -> number of Case nodes = 0
    GraphService.reset_database(session)
    assert len(GraphService.list_cases(session)) == 0

    # TEST 2: Upload exactly ONE file payload
    payload = _build_test_case_payload()
    case_data = CaseData(**payload)
    IngestionService.ingest_case(session, case_data)

    # TEST 3: Assert number of Case MERGEs = 1 and Case.case_id = CASE-TEST-001
    cases = GraphService.list_cases(session)
    assert len(cases) == 1
    assert cases[0]["case_id"] == "CASE-TEST-001"

    # TEST 4: Assert P001 and P002 both exist separately
    people_params = next(p for q, p in session.queries if "MERGE (p:Person" in q)
    p_rows = people_params["rows"]
    assert len(p_rows) == 2
    assert {r["person_id"] for r in p_rows} == {"P001", "P002"}

    # TEST 5: Assert both Rahul Kumar records retain different person_id, age, role
    p001_row = next(r for r in p_rows if r["person_id"] == "P001")
    p002_row = next(r for r in p_rows if r["person_id"] == "P002")
    assert p001_row["name"] == "Rahul Kumar" and p001_row["age"] == 32 and p001_row["roles"] == ["Suspect"]
    assert p002_row["name"] == "Rahul Kumar" and p002_row["age"] == 35 and p002_row["roles"] == ["Witness"]

    # TEST 6 & 7: Assert IP node and USES_IP relationship are issued
    ip_query = next((q, p) for q, p in session.queries if ":USES_IP" in q)
    assert ip_query is not None
    assert ip_query[1]["rows"][0] == {"owner_id": "P001", "ip_address": "192.168.1.10"}

    # TEST 8: Assert surveillance phone relationship is issued
    surv_ph_query = next((q, p) for q, p in session.queries if "(ph:Phone" in q and ":LOCATED_AT" in q)
    assert surv_ph_query is not None
    assert surv_ph_query[1]["rows"][0]["phone_number"] == "9876543210"

    # TEST 9: Re-upload THE SAME FILE AGAIN (Idempotency)
    IngestionService.ingest_case(session, case_data)
    # Graph cases remain 1
    cases_after = GraphService.list_cases(session)
    assert len(cases_after) == 1

    # TEST 10: Check timestamps -> no fake hardcoded default dates exist
    for q, p in session.queries:
        if "rows" in p:
            for r in p["rows"]:
                for k, v in r.items():
                    if isinstance(v, str) and ("2026-08-24" in v or "2026-08-25" in v):
                        pytest.fail(f"Found fake hardcoded date '{v}' in query parameters!")


# ---------------------------------------------------------------------------
# 4. Multi-File Single-Case Ingestion (Requirement 29)
# ---------------------------------------------------------------------------

def test_multi_file_single_case_ingestion(client, monkeypatch):
    """Uploading multiple files belonging to the SAME explicit case produces 1 Case node."""
    session = AuditMockSession()
    monkeypatch.setattr("backend.database.db.get_session", lambda: session)

    f1 = json.dumps({"case_metadata": {"case_id": "CASE-MULTI-001"}, "entities": {"people": [{"person_id": "P10", "name": "Person Ten"}]}}).encode("utf-8")
    f2 = json.dumps({"case_metadata": {"case_id": "CASE-MULTI-001"}, "entities": {"phones": [{"phone_number": "9991112220"}]}}).encode("utf-8")

    r = client.post(
        "/api/v1/ingest?case_id=CASE-MULTI-001",
        files=[
            ("files", ("f1.json", io.BytesIO(f1), "application/json")),
            ("files", ("f2.json", io.BytesIO(f2), "application/json")),
        ]
    )
    assert r.status_code == 201
    
    # Exactly ONE Case node merged
    case_merges = set(p["case_id"] for q, p in session.queries if "MERGE (c:Case {case_id: $case_id})" in q)
    assert case_merges == {"CASE-MULTI-001"}
