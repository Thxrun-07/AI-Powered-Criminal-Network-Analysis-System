import json
import pytest
import io
from typing import List, Dict, Any, Tuple
from backend.services.graph_service import GraphService
from backend.services.ingestion_service import IngestionService
from backend.services.schema_mapper import map_ingestion_to_graph_data


class AuditMockSession:
    """Mock session capturing all Cypher MERGE queries for graph assertion."""
    def __init__(self):
        self.queries: List[Tuple[str, Dict[str, Any]]] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def run(self, query: str, parameters: Dict[str, Any] = None, **kwargs):
        params = parameters or kwargs or {}
        self.queries.append((query, params))

        class MockResult:
            def single(self):
                return None
            def data(self):
                return []
            def __iter__(self):
                return iter([])

        return MockResult()

    def begin_transaction(self):
        class MockTx:
            def __enter__(inner_self):
                return inner_self
            def __exit__(inner_self, exc_type, exc_val, exc_tb):
                pass
            def run(inner_self, query: str, parameters: Dict[str, Any] = None, **kwargs):
                return self.run(query, parameters, **kwargs)
        return MockTx()


def _get_merged_people_rows(session: AuditMockSession) -> List[Dict[str, Any]]:
    """Extracts all Person node parameter rows from session queries."""
    rows = []
    for q, p in session.queries:
        if "MERGE (p:Person" in q and "rows" in p:
            rows.extend(p["rows"])
    return rows


def _get_merged_transaction_rows(session: AuditMockSession) -> List[Dict[str, Any]]:
    """Extracts all Transaction node parameter rows from session queries."""
    rows = []
    for q, p in session.queries:
        if "MERGE (t:Transaction" in q and "rows" in p:
            rows.extend(p["rows"])
    return rows


# ---------------------------------------------------------------------------
# 1. Regression Test: Free-Text Transaction Descriptions Must NOT Create Persons
# ---------------------------------------------------------------------------

def test_free_text_descriptions_never_create_persons(monkeypatch):
    """
    Test input with free-text descriptions:
    "accounts emptied", "accounts emptied within 24 hours".
    - Person count MUST be 0.
    - P_701 / P_702 MUST NOT be generated.
    - Transaction records MUST exist containing the descriptions.
    """
    session = AuditMockSession()
    monkeypatch.setattr("backend.database.db.get_session", lambda: session)

    payload = {
        "case_id": "CASE-TEST-001",
        "transactions": [
            {
                "description": "accounts emptied"
            },
            {
                "description": "accounts emptied within 24 hours"
            }
        ]
    }

    graph_case_data = map_ingestion_to_graph_data(payload)
    IngestionService.ingest_case(session, graph_case_data)

    people_rows = _get_merged_people_rows(session)
    assert len(people_rows) == 0, f"Expected 0 Person nodes, but found: {people_rows}"

    tx_rows = _get_merged_transaction_rows(session)
    assert len(tx_rows) == 2, f"Expected 2 Transaction records, found: {len(tx_rows)}"

    descriptions = [r.get("description") for r in tx_rows]
    assert "accounts emptied" in descriptions
    assert "accounts emptied within 24 hours" in descriptions

    # Ensure no P_701 / P_702 IDs exist in any generated query params
    for q, p in session.queries:
        param_str = json.dumps(p)
        assert "P_701" not in param_str, "P_701 found in Cypher parameters!"
        assert "P_702" not in param_str, "P_702 found in Cypher parameters!"


# ---------------------------------------------------------------------------
# 2. Mixed Test: Legitimate Person + Transaction Description
# ---------------------------------------------------------------------------

def test_mixed_payload_creates_only_explicit_person(monkeypatch):
    """
    Test input with 1 explicit Person + 1 Transaction description:
    {
        "case_id": "CASE-TEST-001",
        "person_id": "P001",
        "name": "Rahul Kumar",
        "role": "Suspect",
        "transaction": {
            "description": "accounts emptied"
        }
    }
    - Person count MUST be 1 (P001 / Rahul Kumar).
    - "accounts emptied" MUST NOT become a Person.
    """
    session = AuditMockSession()
    monkeypatch.setattr("backend.database.db.get_session", lambda: session)

    payload = {
        "case_id": "CASE-TEST-001",
        "person_id": "P001",
        "name": "Rahul Kumar",
        "role": "Suspect",
        "transaction": {
            "description": "accounts emptied"
        }
    }

    graph_case_data = map_ingestion_to_graph_data(payload)
    IngestionService.ingest_case(session, graph_case_data)

    people_rows = _get_merged_people_rows(session)
    assert len(people_rows) == 1, f"Expected exactly 1 Person node, found: {len(people_rows)}"
    assert people_rows[0]["person_id"] == "P001"
    assert people_rows[0]["name"] == "Rahul Kumar"

    tx_rows = _get_merged_transaction_rows(session)
    assert len(tx_rows) == 1
    assert tx_rows[0]["description"] == "accounts emptied"


# ---------------------------------------------------------------------------
# 3. HTTP End-to-End API Test for Free-Text Rejection
# ---------------------------------------------------------------------------

def test_http_api_ingest_free_text_payload(client, monkeypatch):
    """HTTP API POST /api/v1/ingest with descriptive text payload."""
    session = AuditMockSession()
    monkeypatch.setattr("backend.database.db.get_session", lambda: session)

    payload_bytes = json.dumps({
        "case_id": "CASE-TEST-001",
        "transactions": [
            {"description": "accounts emptied"},
            {"description": "accounts emptied within 24 hours"}
        ]
    }).encode("utf-8")

    r = client.post(
        "/api/v1/ingest",
        files=[("files", ("freetext.json", io.BytesIO(payload_bytes), "application/json"))]
    )

    assert r.status_code == 201
    people_rows = _get_merged_people_rows(session)
    assert len(people_rows) == 0
