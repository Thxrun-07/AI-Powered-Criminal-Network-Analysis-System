import os
import tempfile
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import db


@pytest.fixture(autouse=True)
def isolate_blockchain_ledger(monkeypatch, tmp_path):
    """Redirect blockchain ledger writes to a temporary file so tests never
    pollute the committed data/blockchain_ledger.json."""
    test_ledger = str(tmp_path / "blockchain_ledger.json")
    monkeypatch.setattr("backend.services.blockchain_service.LEDGER_FILE_PATH", test_ledger)
    # Reset the in-memory chain so each test starts fresh
    from backend.services.blockchain_service import BlockchainService
    BlockchainService._chain = []
    monkeypatch.setattr(BlockchainService, "_load_ledger_from_session", lambda *args, **kwargs: False)
    monkeypatch.setattr(BlockchainService, "_save_ledger_to_session", lambda *args, **kwargs: None)
    monkeypatch.setattr(BlockchainService, "_clean_orphans", lambda *args, **kwargs: 0)


@pytest.fixture(autouse=True)
def isolate_external_api_keys(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)


class MockRecord:
    def __init__(self, data_dict):
        self._data = data_dict

    def data(self):
        return self._data

    def single(self):
        return self._data

    def get(self, key, default=None):
        return self._data.get(key, default)

    def __getitem__(self, key):
        return self._data[key]


class MockResult:
    def __init__(self, records):
        self._records = records
        self._iter = iter(records)

    def data(self):
        return [r._data if isinstance(r, MockRecord) else r for r in self._records]

    def single(self):
        if not self._records:
            return None
        r = self._records[0]
        return r._data if isinstance(r, MockRecord) else r

    def __iter__(self):
        return iter(self._records)


class MockSession:
    def __init__(self):
        self.queries = []
        self.write_transactions = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    # Managed-transaction API (neo4j Session.execute_write / execute_read): the mock
    # session doubles as the transaction object, so tx.run() records into self.queries.
    def execute_write(self, transaction_function, *args, **kwargs):
        self.write_transactions += 1
        return transaction_function(self, *args, **kwargs)

    def execute_read(self, transaction_function, *args, **kwargs):
        return transaction_function(self, *args, **kwargs)

    def begin_transaction(self):
        parent = self
        class MockTx:
            def __enter__(self):
                return parent
            def __exit__(self, exc_type, exc_val, exc_tb):
                pass
            def run(self, query, parameters=None):
                return parent.run(query, parameters)
            def commit(self):
                pass
            def rollback(self):
                pass
        return MockTx()


    def run(self, query, parameters=None):
        self.queries.append((query, parameters or {}))
        q_lower = query.lower()
        
        # dbms.components health check
        if "dbms.components" in q_lower:
            return MockResult([MockRecord({"name": "Neo4j Kernel", "versions": ["5.20.0"], "edition": "community"})])
        
        # gds.version check
        if "gds.version" in q_lower:
            return MockResult([]) # GDS not available by default in base mock
        
        # Batched ingestion (UNWIND) returns one was_created row per input row.
        if "unwind $rows" in q_lower and "as was_created" in q_lower:
            rows = (parameters or {}).get("rows", [])
            return MockResult([MockRecord({"was_created": True}) for _ in rows])

        # Ingestion was_created
        if "return (c.created_at = $now) as was_created" in q_lower:
            return MockResult([MockRecord({"was_created": True})])
        if "return (sr.created_at = $now) as was_created" in q_lower:
            return MockResult([MockRecord({"was_created": True})])
        if "return (f.created_at = $now) as was_created" in q_lower:
            return MockResult([MockRecord({"was_created": True})])
        if "return (p.created_at = $now) as was_created" in q_lower:
            return MockResult([MockRecord({"was_created": True})])
        if "return (ph.created_at = $now) as was_created" in q_lower:
            return MockResult([MockRecord({"was_created": True})])
        if "return (b.created_at = $now) as was_created" in q_lower:
            return MockResult([MockRecord({"was_created": True})])
        if "return (v.created_at = $now) as was_created" in q_lower:
            return MockResult([MockRecord({"was_created": True})])
        if "return (s.created_at = $now) as was_created" in q_lower:
            return MockResult([MockRecord({"was_created": True})])
        if "return (i.created_at = $now) as was_created" in q_lower:
            return MockResult([MockRecord({"was_created": True})])
        if "return (l.created_at = $now) as was_created" in q_lower:
            return MockResult([MockRecord({"was_created": True})])
        if "return (t.created_at = $now) as was_created" in q_lower:
            return MockResult([MockRecord({"was_created": True})])
        if "return (pc.created_at = $now) as was_created" in q_lower:
            return MockResult([MockRecord({"was_created": True})])

        # Person resolution / candidate lookup
        if "match (p:person)" in q_lower:
            return MockResult([
                MockRecord({
                    "person_id": "P-001",
                    "name": "Devendra Sharma",
                    "aliases": ["Deva"],
                    "dob": "1982-06-14",
                    "case_ids": ["CASE-2024-001"]
                })
            ])

        # Default empty result
        return MockResult([])


@pytest.fixture
def mock_session():
    return MockSession()


@pytest.fixture
def client(mock_session):
    with patch.object(db, "get_session", return_value=mock_session):
        with TestClient(app) as test_client:
            yield test_client

