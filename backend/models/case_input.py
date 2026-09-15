from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
from backend.models.entity import (
    Person, Phone, BankAccount, Vehicle, SocialHandle,
    IPAddress, Location, CellTower, PriorCase, SourceRecord, FIR
)
from backend.models.relationship import (
    CommunicationRecord, TransactionRecord, SurveillanceLogRecord,
    CriminalHistoryRecord, IntelligenceReportRecord
)
from backend.models.insights import InsightItem


class CaseMetadata(BaseModel):
    case_id: str = Field(..., description="Unique Case Identifier (e.g. CASE-2024-001)")
    case_name: str = Field(..., description="Case title or operation name")
    case_type: Optional[str] = Field(default="GENERAL_INVESTIGATION", description="HOMICIDE, FRAUD, NARCOTICS, CYBERCRIME, etc.")
    status: Optional[str] = Field(default="OPEN", description="OPEN, UNDER_INVESTIGATION, CHARGED, CLOSED")
    jurisdiction: Optional[str] = Field(default=None, description="Department or state jurisdiction")
    lead_investigator: Optional[str] = Field(default=None, description="Name or badge of lead investigator")
    created_date: Optional[str] = Field(default=None, description="Case creation date (YYYY-MM-DD)")
    summary: Optional[str] = Field(default=None, description="High-level narrative summary of the case")
    tags: List[str] = Field(default_factory=list, description="Investigative tags")
    properties: Dict[str, Any] = Field(default_factory=dict)


class EntitiesContainer(BaseModel):
    people: List[Person] = Field(default_factory=list)
    phones: List[Phone] = Field(default_factory=list)
    bank_accounts: List[BankAccount] = Field(default_factory=list)
    vehicles: List[Vehicle] = Field(default_factory=list)
    social_handles: List[SocialHandle] = Field(default_factory=list)
    ip_addresses: List[IPAddress] = Field(default_factory=list)
    cell_towers: List[CellTower] = Field(default_factory=list)
    locations: List[Location] = Field(default_factory=list)


class RelationshipsContainer(BaseModel):
    communications: List[CommunicationRecord] = Field(default_factory=list)
    transactions: List[TransactionRecord] = Field(default_factory=list)


class CaseData(BaseModel):
    case_metadata: CaseMetadata = Field(..., description="Primary case metadata")
    fir_records: List[FIR] = Field(default_factory=list, description="Associated FIR / Police records")
    entities: EntitiesContainer = Field(default_factory=EntitiesContainer, description="Structured entity collections")
    relationships: RelationshipsContainer = Field(default_factory=RelationshipsContainer, description="Communications and financial flows")
    surveillance_logs: List[SurveillanceLogRecord] = Field(default_factory=list, description="Physical and electronic surveillance records")
    criminal_history: List[CriminalHistoryRecord] = Field(default_factory=list, description="Prior criminal offense history")
    intelligence_reports: List[IntelligenceReportRecord] = Field(default_factory=list, description="Intelligence agency or informant memos")
    source_records: List[SourceRecord] = Field(default_factory=list, description="Explicit source records if provided")


class CaseEnvelope(BaseModel):
    dataset_id: Optional[str] = Field(default="DS-DEFAULT", description="Dataset batch identifier")
    dataset_version: Optional[str] = Field(default="1.0", description="Dataset schema version")
    source_model: Optional[str] = Field(default="direct_ingestion", description="Upstream producer / extraction model")
    case_data: CaseData = Field(..., description="Inner case data object")


class IngestCreatedCounts(BaseModel):
    nodes: int = Field(default=0, description="Total nodes created")
    relationships: int = Field(default=0, description="Total relationships created")
    source_records: int = Field(default=0, description="Source records registered")


class IngestResponse(BaseModel):
    case_id: str = Field(..., description="Case identifier")
    dataset_id: Optional[str] = Field(default=None)
    dataset_version: Optional[str] = Field(default=None)
    created: IngestCreatedCounts = Field(default_factory=IngestCreatedCounts)
    matched_existing_entities: int = Field(default=0, description="Pre-existing entities matched and updated")
    new_cross_case_links: int = Field(default=0, description="Cross-case links established")
    new_insights: int = Field(default=0, description="Insights generated during this ingestion")
    warnings: List[str] = Field(default_factory=list, description="Ingestion warnings or anomalies")
    insights: List[InsightItem] = Field(default_factory=list, description="Generated case and cross-case insights")
    case_already_exists: bool = Field(default=False, description="True if case was already present in database")


class CaseDeleteRequest(BaseModel):
    """Request body for per-case deletion requiring explicit confirmation."""
    confirm: bool = Field(default=False, description="Must be true to confirm case deletion")


class CaseDeleteSummary(BaseModel):
    """Summary of what was removed/detached during a case deletion."""
    case_id: str = Field(..., description="The deleted case identifier")
    nodes_removed: int = Field(default=0, description="Nodes exclusively owned by this case that were deleted")
    nodes_detached: int = Field(default=0, description="Shared nodes where this case_id was removed from case_ids")
    relationships_removed: int = Field(default=0, description="Relationships deleted")
    status: str = Field(default="deleted", description="Deletion status")

