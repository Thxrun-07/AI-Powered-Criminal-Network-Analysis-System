from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query, status
from neo4j.exceptions import ServiceUnavailable

from backend.database import db
from backend.services.blockchain_service import BlockchainService
from backend.logging_config import logger

router = APIRouter(prefix="/api/v1/blockchain", tags=["Blockchain Chain of Custody & Evidence Audit"])


@router.get("/ledger", summary="Get Immutable Blockchain Ledger Blocks")
def get_blockchain_ledger(
    case_id: Optional[str] = Query(None, description="Filter ledger blocks by case ID"),
    limit: int = Query(500, ge=1, le=5000, description="Max blocks to retrieve")
):
    """Retrieves recent cryptographic evidence blocks from the blockchain ledger."""
    try:
        return {
            "total_blocks": len(BlockchainService.get_ledger(case_id=case_id, limit=5000)),
            "case_id_filter": case_id,
            "blocks": BlockchainService.get_ledger(case_id=case_id, limit=limit)
        }
    except Exception as e:
        logger.error(f"Error fetching blockchain ledger: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/verify-chain", summary="Verify Full Blockchain Ledger Integrity")
def verify_blockchain_chain():
    """Validates SHA-256 block hashes and hash links across the entire ledger."""
    try:
        return BlockchainService.verify_ledger_integrity()
    except Exception as e:
        logger.error(f"Error validating blockchain ledger: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/verify-case/{case_id}", summary="Audit Case Evidence Against Blockchain Ledger")
def verify_case_evidence(case_id: str):
    """Compares live Neo4j knowledge graph data for a case against on-chain block Merkle hashes."""
    try:
        with db.get_session() as session:
            return BlockchainService.verify_case_integrity(session=session, case_id=case_id)
    except ServiceUnavailable as se:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(se))
    except Exception as e:
        logger.error(f"Error verifying case evidence integrity for {case_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/cases/{case_id}/documents", summary="Get Document-Level Blockchain Audit for Case")
def get_case_documents_blockchain(case_id: str):
    """Returns document-specific cryptographic blocks (FIR, CDR, Bank Statements, Surveillance Logs) for a case."""
    try:
        blocks = BlockchainService.get_ledger(case_id=case_id, limit=500)
        return {
            "case_id": case_id,
            "total_documents": len(blocks),
            "documents": blocks
        }
    except Exception as e:
        logger.error(f"Error fetching case document blocks for {case_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
