from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class CommunicationRecord(BaseModel):
    call_id: Optional[str] = Field(default=None, description="Unique call/SMS identifier")
    communication_id: Optional[str] = Field(default=None, description="Alias for call_id")
    source_phone: str = Field(..., description="Calling/Originating Phone Number")
    target_phone: str = Field(..., description="Receiving/Target Phone Number")
    type: str = Field(default="VOICE_CALL", description="VOICE_CALL, SMS, WHATSAPP, VOIP")
    timestamp: Optional[str] = Field(default=None, description="Call initiation timestamp (ISO 8601)")
    duration_seconds: Optional[int] = Field(default=0, description="Call duration in seconds")
    cell_tower: Optional[str] = Field(default=None, description="Cell tower identifier")
    source_record_id: Optional[str] = Field(default=None, description="CDR source record ID")
    properties: Dict[str, Any] = Field(default_factory=dict)


class TransactionRecord(BaseModel):
    transaction_id: str = Field(..., description="Unique Financial Transaction Reference")
    source_account: str = Field(..., description="Originating Bank Account Number")
    target_account: str = Field(..., description="Destination Bank Account Number")
    amount: float = Field(default=0.0, description="Transaction monetary amount")
    currency: str = Field(default="INR", description="Currency code (e.g. INR, USD)")
    timestamp: Optional[str] = Field(default=None, description="Transaction execution timestamp (ISO 8601)")
    transaction_type: Optional[str] = Field(default="NEFT", description="NEFT, RTGS, IMPS, UPI, WIRE, CASH")
    reference_no: Optional[str] = Field(default=None, description="Bank UTR / Reference No")
    description: Optional[str] = Field(default=None, description="Transaction description or event notes")
    source_record_id: Optional[str] = Field(default=None, description="Bank Statement Source Record ID")
    properties: Dict[str, Any] = Field(default_factory=dict)


class SurveillanceLogRecord(BaseModel):
    log_id: str = Field(..., description="Surveillance log ID")
    location_id: Optional[str] = Field(default=None, description="Location identifier")
    location_name: Optional[str] = Field(default=None, description="Location name / description")
    latitude: Optional[float] = Field(default=None, description="GPS Latitude")
    longitude: Optional[float] = Field(default=None, description="GPS Longitude")
    timestamp: Optional[str] = Field(default=None, description="Observation timestamp (ISO 8601)")

    observed_person_ids: List[str] = Field(default_factory=list, description="Person IDs observed")
    observed_vehicle_vins: List[str] = Field(default_factory=list, description="Vehicle VINs or plates observed")
    observed_phone_numbers: List[str] = Field(default_factory=list, description="Phone numbers active/intercepted")
    activity_description: Optional[str] = Field(default=None, description="Observed action details")
    evidence_ref: Optional[str] = Field(default=None, description="CCTV footage / photo log reference")
    source_record_id: Optional[str] = Field(default=None, description="Surveillance source record ID")
    properties: Dict[str, Any] = Field(default_factory=dict)


class CriminalHistoryRecord(BaseModel):
    record_id: str = Field(..., description="Criminal record ID")
    person_id: str = Field(..., description="Person ID associated with this prior history")
    case_number: str = Field(..., description="Prior case registration number")
    offense: Optional[str] = Field(default=None, description="Offense / Crime description")
    jurisdiction: Optional[str] = Field(default=None, description="Police station or court name")
    status: Optional[str] = Field(default="CONVICTED", description="CONVICTED, CHARGESHEETED, PENDING")
    year: Optional[int] = Field(default=None, description="Year of offense")
    source_record_id: Optional[str] = Field(default=None, description="Court / Police record ID")
    properties: Dict[str, Any] = Field(default_factory=dict)


class IntelligenceReportRecord(BaseModel):
    report_id: str = Field(..., description="Intel report ID")
    source_agency: str = Field(..., description="Originating intelligence agency or informant unit")
    date: Optional[str] = Field(default=None, description="Report date")
    reliability_score: Optional[float] = Field(default=1.0, description="Source reliability score (0.0 - 1.0)")
    content: Optional[str] = Field(default=None, description="Intel report text / assessment")
    entities_mentioned: List[str] = Field(default_factory=list, description="Entity IDs mentioned in report")
    source_record_id: Optional[str] = Field(default=None, description="Raw document reference ID")
    properties: Dict[str, Any] = Field(default_factory=dict)

