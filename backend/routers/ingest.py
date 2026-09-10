import json
from typing import List, Optional, Tuple, Dict, Any, Union
from fastapi import APIRouter, File, UploadFile, HTTPException, Header, Query, Body, status, Response
from pydantic import ValidationError
from backend.database import db
from backend.services.ingestion_engine import CaseIngestionEngine
from backend.services.schema_mapper import map_ingestion_to_graph_data
from backend.services.ingestion_service import IngestionService
from backend.models.case_input import CaseData, CaseEnvelope, IngestCreatedCounts, IngestResponse
from backend.logging_config import logger

router = APIRouter(prefix="/api/v1", tags=["Unified Data Ingestion"])

# (case_data, dataset_id, dataset_version): exactly what IngestionService.ingest_case needs.
CaseDocument = Tuple[CaseData, str, str]


def _detect_case_data_document(filename: str, text_content: str) -> Optional[CaseDocument]:
    """Return a validated CaseData document if the uploaded content is a structured JSON case, else ``None``.

    Detection allows structured JSON files (whether CaseEnvelope, CaseData, or ConsolidatedCaseData format)
    to bypass the legacy unstructured extraction engine and proceed directly to graph generation:
      * the content must parse as a JSON object;
      * a CaseEnvelope-shaped object (``{"case_data": {...}}``) is unwrapped;
      * an object declaring ``case_metadata`` is validated as CaseData, or translated via ``map_ingestion_to_graph_data``;
      * non-JSON files or arbitrary JSON without ``case_metadata`` return ``None`` and go through the legacy extraction engine.
    """
    try:
        data = json.loads(text_content)
    except ValueError:  # includes json.JSONDecodeError
        return None
    if not isinstance(data, dict):
        return None

    document: Optional[CaseDocument] = None

    if isinstance(data.get("case_data"), dict):
        try:
            envelope = CaseEnvelope.model_validate(data)
            document = (
                envelope.case_data,
                envelope.dataset_id or "DS-DEFAULT",
                envelope.dataset_version or "1.0",
            )
        except ValidationError:
            pass

    if document is None and "case_metadata" in data:
        # First, attempt strict CaseData validation
        try:
            document = (CaseData.model_validate(data), "DS-DEFAULT", "1.0")
        except ValidationError:
            # Second, attempt direct schema mapping (supports ConsolidatedCaseData & other structured JSON formats)
            try:
                mapped = map_ingestion_to_graph_data(data)
                document = (mapped, "DS-DEFAULT", "1.0")
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"File '{filename}' declares 'case_metadata' but could not be parsed or mapped into a valid CaseData document: {str(exc)}",
                )

    if document is None:
        return None

    if not document[0].case_metadata.case_id:  # same guard as POST /api/cases/ingest
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File '{filename}': missing required 'case_metadata.case_id' in ingestion payload.",
        )
    return document



def _combine_results(results: List[IngestResponse]) -> IngestResponse:
    """One IngestResponse per request: unchanged for a single document, totals for several.

    Several documents occur when a folder upload contains more than one CaseData JSON file
    (legacy files are still consolidated into a single document, as before).  Counts are
    summed, insights are de-duplicated by ``insight_id``, ``case_id`` is the last case
    ingested and a warning lists every case ingested.
    """
    if len(results) == 1:
        return results[0]

    insights, seen_ids = [], set()
    for result in results:
        for insight in result.insights:
            if insight.insight_id not in seen_ids:
                seen_ids.add(insight.insight_id)
                insights.append(insight)

    warnings = [warning for result in results for warning in result.warnings]
    warnings.append(
        f"Ingested {len(results)} case documents in one request "
        f"({', '.join(result.case_id for result in results)}); counts are totals and "
        f"'case_id' is the last case ingested."
    )
    last = results[-1]
    return IngestResponse(
        case_id=last.case_id,
        dataset_id=last.dataset_id,
        dataset_version=last.dataset_version,
        created=IngestCreatedCounts(
            nodes=sum(result.created.nodes for result in results),
            relationships=sum(result.created.relationships for result in results),
            source_records=sum(result.created.source_records for result in results),
        ),
        matched_existing_entities=sum(result.matched_existing_entities for result in results),
        new_cross_case_links=sum(
            1 for insight in insights if insight.insight_type in ["CROSS_CASE_LINK", "SHARED_ENTITY", "BRIDGE_NODE"]
        ),
        new_insights=len(insights),
        warnings=warnings,
        insights=insights,
    )


@router.post("/ingest", response_model=IngestResponse, summary="Ingest case files (structured CSV & unstructured text) to Neo4j")
@router.post("/ingest/file", response_model=IngestResponse, summary="Ingest case files (structured CSV & unstructured text) to Neo4j alias")
async def ingest_files(
    response: Response,
    files: Optional[List[UploadFile]] = File(None),
    file: Optional[UploadFile] = File(None),
    case_id: Optional[str] = Query(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    api_key: Optional[str] = Query(None)
):
    upload_files: List[UploadFile] = []
    if files:
        upload_files.extend(files)
    if file:
        upload_files.append(file)

    if not upload_files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    active_key = x_api_key or api_key
    engine = CaseIngestionEngine(api_key=active_key)
    if case_id:
        engine.case_metadata.case_id = case_id
        engine.case_metadata.case_name = f"Case {case_id}"

    documents: List[CaseDocument] = []
    legacy_files = 0
    for upload_file in upload_files:
        filename = upload_file.filename or "uploaded_file.txt"
        contents = await upload_file.read()
        text_content = contents.decode("utf-8", errors="ignore")

        # CaseData JSON documents take the same pipeline as POST /api/cases/ingest and never
        # enter the legacy CaseIngestionEngine; everything else is parsed exactly as before.
        document = _detect_case_data_document(filename, text_content)
        if document is not None:
            logger.info(
                f"'{filename}' is a CaseData JSON document (case '{document[0].case_metadata.case_id}'); "
                f"bypassing legacy CaseIngestionEngine."
            )
            documents.append(document)
            continue

        engine.parse_file(filename, text_content)
        legacy_files += 1

    if legacy_files:
        consolidated_case = engine.consolidate()
        graph_case_data = map_ingestion_to_graph_data(consolidated_case.model_dump())
        documents.append((graph_case_data, "DS-DEFAULT", "1.0"))

    try:
        with db.get_session() as session:
            results = [
                IngestionService.ingest_case(
                    session=session,
                    case_data=doc_data,
                    dataset_id=doc_ds_id,
                    dataset_version=doc_ds_ver,
                    mode="merge"
                )
                for doc_data, doc_ds_id, doc_ds_ver in documents
            ]
            response.status_code = status.HTTP_201_CREATED
            return _combine_results(results)
    except Exception as e:
        logger.exception(f"Error saving case ingestion to Neo4j: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to ingest case data into Neo4j: {str(e)}"
        )


@router.post("/ingest/case", response_model=IngestResponse, summary="Ingest Case Graph JSON payload")
def ingest_case_json(
    response: Response,
    payload: Dict[str, Any] = Body(..., description="Case Envelope, CaseData, or structured Case JSON payload"),
    mode: str = Query("merge", description="Ingestion mode: 'merge' (default) or 'replace'"),
    confirm_replace: bool = Query(False, description="Must be true if mode is 'replace'")
):
    document: Optional[CaseDocument] = None

    if isinstance(payload.get("case_data"), dict):
        try:
            envelope = CaseEnvelope.model_validate(payload)
            document = (
                envelope.case_data,
                envelope.dataset_id or "DS-DEFAULT",
                envelope.dataset_version or "1.0",
            )
        except ValidationError:
            pass

    if document is None and "case_metadata" in payload:
        try:
            document = (CaseData.model_validate(payload), "DS-DEFAULT", "1.0")
        except ValidationError:
            try:
                mapped = map_ingestion_to_graph_data(payload)
                document = (mapped, "DS-DEFAULT", "1.0")
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Payload declares 'case_metadata' but could not be parsed: {str(exc)}",
                )

    if document is None:
        try:
            mapped = map_ingestion_to_graph_data(payload)
            document = (mapped, "DS-DEFAULT", "1.0")
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid payload structure: could not parse into CaseData: {str(exc)}",
            )

    case_data, dataset_id, dataset_version = document
    if not case_data.case_metadata or not case_data.case_metadata.case_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required 'case_metadata.case_id' in ingestion payload.",
        )

    try:
        with db.get_session() as session:
            ingest_result = IngestionService.ingest_case(
                session=session,
                case_data=case_data,
                dataset_id=dataset_id,
                dataset_version=dataset_version,
                mode=mode,
                confirm_replace=confirm_replace
            )
            if ingest_result.created.nodes > 0 and ingest_result.matched_existing_entities == 0:
                response.status_code = status.HTTP_201_CREATED
            else:
                response.status_code = status.HTTP_200_OK
            return ingest_result
    except Exception as e:
        logger.exception(f"Error saving case JSON ingestion to Neo4j: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to ingest case JSON into Neo4j: {str(e)}"
        )


@router.post("/ingest/text", response_model=IngestResponse, summary="Ingest raw text payload directly to Neo4j")
async def ingest_text(
    response: Response,
    payload: str = Body(..., media_type="text/plain", description="Raw case file narrative, CSV data, or FIR text"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    api_key: Optional[str] = Query(None)
):
    if not payload or not payload.strip():
        raise HTTPException(status_code=400, detail="Payload body cannot be empty.")

    active_key = x_api_key or api_key
    engine = CaseIngestionEngine(api_key=active_key)
    engine.parse_file("input_payload.txt", payload)

    consolidated_case = engine.consolidate()
    graph_case_data = map_ingestion_to_graph_data(consolidated_case.model_dump())

    try:
        with db.get_session() as session:
            ingest_result = IngestionService.ingest_case(
                session=session,
                case_data=graph_case_data,
                dataset_id="DS-DEFAULT",
                dataset_version="1.0",
                mode="merge"
            )
            response.status_code = status.HTTP_201_CREATED
            return ingest_result
    except Exception as e:
        logger.exception(f"Error saving case text ingestion to Neo4j: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to ingest case data into Neo4j: {str(e)}"
        )

