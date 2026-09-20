from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query, status
from neo4j.exceptions import ServiceUnavailable

from backend.database import db
from backend.services.graph_service import GraphService
from backend.logging_config import logger

router = APIRouter(tags=["Graph & Entity Operations"])


@router.get("/api/graph", summary="Retrieve Graph Subgraph for Visualization")
def get_graph(
    case_id: Optional[str] = Query(None, description="Filter by case ID"),
    node_labels: Optional[List[str]] = Query(None, description="Filter by node labels"),
    core_only: bool = Query(False, description="Restrict to core target suspects and owned assets"),
    graph_type: str = Query("all", description="Filter graph by extraction type: all, cdr, person, financial"),
    limit: int = Query(1000, ge=1, le=5000, description="Max elements to fetch")
):
    try:
        with db.get_session() as session:
            return GraphService.get_subgraph(
                session,
                case_id=case_id,
                node_labels=node_labels,
                core_only=core_only,
                graph_type=graph_type,
                limit=limit
            )
    except ServiceUnavailable as se:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(se))




@router.get("/api/entities/search", summary="Search Entities Across Graph")
def search_entities(
    q: str = Query(..., min_length=1, description="Search query string (name, phone, account, VIN, etc.)"),
    entity_type: Optional[str] = Query(None, description="Optional entity label filter (Person, Phone, BankAccount, etc.)"),
    case_id: Optional[str] = Query(None, description="Optional case ID filter"),
    limit: int = Query(25, ge=1, le=100, description="Max search results")
):
    try:
        with db.get_session() as session:
            return GraphService.search_entities(
                session=session,
                query=q,
                entity_type=entity_type,
                case_id=case_id,
                limit=limit
            )
    except ServiceUnavailable as se:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(se))


@router.get("/api/entities/{entity_id}", summary="Entity 360 Profile & 1-Hop Neighbors")
def get_entity(entity_id: str):
    try:
        with db.get_session() as session:
            entity_data = GraphService.get_entity_360(session, entity_id)
            if not entity_data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Entity with ID '{entity_id}' not found in graph."
                )
            return entity_data
    except ServiceUnavailable as se:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(se))


@router.get("/api/relationships/{relationship_id}", summary="Get Relationship Details")
def get_relationship(relationship_id: str):
    try:
        with db.get_session() as session:
            rel_data = GraphService.get_relationship_by_id(session, relationship_id)
            if not rel_data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Relationship with ID '{relationship_id}' not found."
                )
            return rel_data
    except ServiceUnavailable as se:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(se))


@router.post("/api/graph/ai-query", summary="Interactive AI Graph Copilot Query with Gemini")
def ask_graph_copilot(payload: dict):
    """
    Accepts natural-language queries about the visible graph topology from investigators
    and returns a structured deductive intelligence response using Gemini 2.5 Flash
    (with heuristic fallback).
    """
    from backend.services.gemini_service import GeminiService
    question = payload.get("question", "").strip()
    if not question:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Question is required.")
    
    case_id = payload.get("case_id") or None
    nodes_count = payload.get("nodes_count")
    edges_count = payload.get("edges_count")
    selected_node_id = payload.get("selected_node_id")

    try:
        with db.get_session() as session:
            return GeminiService.answer_graph_query(
                session=session,
                question=question,
                case_id=case_id,
                nodes_count=nodes_count,
                edges_count=edges_count,
                selected_node_id=selected_node_id
            )
    except ServiceUnavailable as se:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(se))
    except Exception as e:
        logger.error(f"Error querying graph copilot: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


