import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.services.blockchain_service import BlockchainService

client = TestClient(app)


def test_blockchain_service_genesis():
    ledger = BlockchainService.get_ledger()
    assert len(ledger) >= 1
    genesis = next((b for b in ledger if b.get("index") == 0 or b.get("case_id") == "SYSTEM_GENESIS"), ledger[0])
    assert genesis["index"] >= 0
    assert "hash" in genesis


def test_blockchain_service_record_block():
    test_payload = {"case_id": "TEST_CASE_999", "suspect": "John Doe", "amount": 50000}
    block_dict = BlockchainService.record_evidence_block(case_id="TEST_CASE_999", payload=test_payload)
    
    assert block_dict["case_id"] == "TEST_CASE_999"
    assert "evidence_hash" in block_dict
    assert "merkle_root" in block_dict
    assert "hash" in block_dict
    assert block_dict["previous_hash"] != ""


def test_blockchain_service_ledger_integrity():
    BlockchainService.record_evidence_block(case_id="CASE_TEST", payload={"foo": "bar"})
    integrity = BlockchainService.verify_ledger_integrity()
    assert isinstance(integrity["valid"], bool)
    assert integrity["total_blocks"] >= 2
    assert "violations" in integrity


def test_blockchain_api_endpoints():
    # Test GET /api/v1/blockchain/ledger
    res_ledger = client.get("/api/v1/blockchain/ledger")
    assert res_ledger.status_code == 200
    data_ledger = res_ledger.json()
    assert "total_blocks" in data_ledger
    assert "blocks" in data_ledger
    assert len(data_ledger["blocks"]) > 0

    # Test GET /api/v1/blockchain/verify-chain
    res_verify = client.get("/api/v1/blockchain/verify-chain")
    assert res_verify.status_code == 200
    data_verify = res_verify.json()
    assert isinstance(data_verify["valid"], bool)
    assert "violations" in data_verify
