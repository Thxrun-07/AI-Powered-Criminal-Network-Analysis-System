from typing import Optional, Union, Dict, Any, List
from fastapi import APIRouter, HTTPException, Query, status, Response, Body
from neo4j.exceptions import ServiceUnavailable, Neo4jError

from backend.database import db
from backend.models.case_input import CaseEnvelope, CaseData, IngestResponse, CaseDeleteRequest, CaseDeleteSummary
from backend.services.ingestion_service import IngestionService
from backend.services.graph_service import GraphService
from backend.services.gemini_service import GeminiService
from backend.logging_config import logger

router = APIRouter(prefix="/api/cases", tags=["Cases & Ingestion"])


@router.post("/ingest", response_model=IngestResponse, summary="Ingest Case Graph JSON")
def ingest_case(
    response: Response,
    payload: Union[CaseEnvelope, CaseData] = Body(..., description="Case Envelope or direct CaseData payload"),
    mode: str = Query("merge", description="Ingestion mode: 'merge' (default) or 'replace'"),
    confirm_replace: bool = Query(False, description="Must be true if mode is 'replace'")
):
    try:
        # Normalize envelope vs direct case_data
        if isinstance(payload, CaseEnvelope):
            case_data = payload.case_data
            dataset_id = payload.dataset_id or "DS-DEFAULT"
            dataset_version = payload.dataset_version or "1.0"
        elif isinstance(payload, CaseData):
            case_data = payload
            dataset_id = "DS-DEFAULT"
            dataset_version = "1.0"
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid payload structure: must be CaseEnvelope or CaseData."
            )

        if not case_data.case_metadata or not case_data.case_metadata.case_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required 'case_metadata.case_id' in ingestion payload."
            )

        with db.get_session() as session:
            ingest_result = IngestionService.ingest_case(
                session=session,
                case_data=case_data,
                dataset_id=dataset_id,
                dataset_version=dataset_version,
                mode=mode,
                confirm_replace=confirm_replace
            )

            # Determine HTTP status: 201 Created if case was newly created, 200 OK if matched/merged
            if ingest_result.created.nodes > 0 and ingest_result.matched_existing_entities == 0:
                response.status_code = status.HTTP_201_CREATED
            else:
                response.status_code = status.HTTP_200_OK

            return ingest_result

    except ValueError as ve:
        # Replace mode confirmation conflict
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(ve)
        )
    except ServiceUnavailable as se:
        logger.error(f"Neo4j database unavailable during ingestion: {se}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database service unavailable: {str(se)}"
        )
    except Neo4jError as ne:
        logger.error(f"Neo4j Cypher error during ingestion: {ne}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Graph database transaction error: {str(ne)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected ingestion error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal ingestion failure: {str(e)}"
        )


@router.get("", summary="List All Ingested Cases")
def list_cases(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by case status"),
    limit: int = Query(50, ge=1, le=200, description="Max cases to return"),
    offset: int = Query(0, ge=0, description="Pagination offset")
):
    try:
        with db.get_session() as session:
            return GraphService.list_cases(session, status=status_filter, limit=limit, offset=offset)
    except ServiceUnavailable as se:
        logger.warning(f"Neo4j connection dropped in list_cases ({se}), reconnecting...")
        try:
            db.reconnect()
            with db.get_session() as session:
                return GraphService.list_cases(session, status=status_filter, limit=limit, offset=offset)
        except Exception as retry_err:
            logger.error(f"Reconnection failed in list_cases: {retry_err}")
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(retry_err))


@router.get("/{case_id}", summary="Get Case Summary & Entity Statistics")
def get_case(case_id: str):
    try:
        with db.get_session() as session:
            case_info = GraphService.get_case_summary(session, case_id)
            if not case_info:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Case with ID '{case_id}' not found."
                )
            return case_info
    except HTTPException:
        raise
    except ServiceUnavailable as se:
        logger.warning(f"Neo4j connection dropped in get_case ({se}), reconnecting...")
        try:
            db.reconnect()
            with db.get_session() as session:
                case_info = GraphService.get_case_summary(session, case_id)
                if not case_info:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Case with ID '{case_id}' not found."
                    )
                return case_info
        except HTTPException:
            raise
        except Exception as retry_err:
            logger.error(f"Reconnection failed in get_case: {retry_err}")
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(retry_err))


@router.delete("/reset", summary="Dev Utility: Reset All Graph Data")
def reset_cases(
    confirm: bool = Query(False, description="Explicit confirmation required to clear all data")
):
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset operation aborted. Set 'confirm=true' to wipe all graph database nodes and relationships."
        )
    try:
        with db.get_session() as session:
            return GraphService.reset_database(session)
    except ServiceUnavailable as se:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(se))


@router.delete("/{case_id}", response_model=CaseDeleteSummary, summary="Delete Case and Its Exclusive Entities")
def delete_case(
    case_id: str,
    confirm: bool = Query(False, description="Explicit confirmation required to delete case"),
    payload: Optional[CaseDeleteRequest] = Body(None, description="Optional request body with confirmation")
):
    is_confirmed = confirm or (payload is not None and payload.confirm)
    if not is_confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Case deletion aborted. Set 'confirm=true' to delete this case and its exclusive entities."
        )
    try:
        with db.get_session() as session:
            result = GraphService.delete_case(session, case_id)
            if result is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Case with ID '{case_id}' not found."
                )
            return result
    except HTTPException:
        raise
    except ServiceUnavailable as se:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(se))
    except Exception as e:
        logger.exception(f"Unexpected error deleting case '{case_id}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete case '{case_id}': {str(e)}"
        )


@router.get("/{case_id}/ai-dossier", summary="Generate AI Executive Case Dossier")
def get_case_ai_dossier(case_id: str):
    """Generates an executive case dossier using Gemini AI or graph heuristic fallback."""
    try:
        with db.get_session() as session:
            dossier = GeminiService.generate_case_brief(session=session, case_id=case_id)
            findings = []
            if dossier.key_suspects:
                findings.append(f"Primary Targets / Suspects: {', '.join(dossier.key_suspects)}")
            if dossier.modus_operandi:
                findings.append(f"Modus Operandi: {dossier.modus_operandi}")
            for anom in (dossier.critical_anomalies or []):
                findings.append(f"Graph Anomaly: {anom}")
            for lead in (dossier.investigative_leads or []):
                findings.append(f"Investigative Lead: {lead}")

            return {
                "case_id": dossier.case_id,
                "case_name": dossier.case_name,
                "status": dossier.status,
                "risk_level": dossier.risk_level,
                "executive_summary": dossier.executive_summary,
                "modus_operandi": dossier.modus_operandi,
                "key_suspects": dossier.key_suspects,
                "critical_anomalies": dossier.critical_anomalies,
                "investigative_leads": dossier.investigative_leads,
                "key_findings": findings,
                "ai_model": dossier.ai_model,
                "title": f"AI Executive Dossier: {dossier.case_name}"
            }
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except ServiceUnavailable as se:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(se))
    except Exception as e:
        logger.exception(f"Error generating AI dossier for case '{case_id}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate AI dossier: {str(e)}"
        )



