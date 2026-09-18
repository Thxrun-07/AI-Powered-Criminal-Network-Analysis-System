from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class CaseMetadata(BaseModel):
    case_id: Optional[str] = Field(default=None, description="Unique case identifier")
    case_name: Optional[str] = Field(default=None, description="Case title or designation")
    case_title: Optional[str] = Field(default=None, description="Alternative case title field")
    title: Optional[str] = Field(default=None, description="Title of the case")
    fir_number: Optional[str] = Field(default=None, description="FIR Number e.g. FIR/0045/2026")
    department: Optional[str] = Field(default=None, description="Department/PS")
    reporting_date: Optional[str] = Field(default=None, description="Reporting date YYYY-MM-DD")
    crime_type: Optional[str] = Field(default=None, description="Primary Crime Category")
    assigned_officer: Optional[str] = Field(default=None, description="Assigned Investigating Officer")


class PersonEntity(BaseModel):
    id: str = Field(description="Unique person entity ID e.g. P_701")
    name: str = Field(description="Full name of person")
    status: str = Field(default="Suspect", description="Status e.g. Suspect, Victim, Complainant, Intermediary")
    age: Optional[int] = Field(default=None, description="Age if available")
    gender: Optional[str] = Field(default=None, description="Gender")
    address: Optional[str] = Field(default=None, description="Address")
    occupation: Optional[str] = Field(default=None, description="Occupation")
    aliases: List[str] = Field(default_factory=list, description="Known aliases")
    roles: List[str] = Field(default_factory=list, description="Roles")
    phone_numbers: List[str] = Field(default_factory=list, description="Phone numbers")
    dob: Optional[str] = Field(default=None, description="Date of birth")
    national_id: Optional[str] = Field(default=None, description="National ID")
    risk_level: Optional[str] = Field(default=None, description="Risk level")
    notes: Optional[str] = Field(default=None, description="Notes")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary custom properties")


class PhoneEntity(BaseModel):
    msisdn: str = Field(description="Mobile phone number")
    owner_id: Optional[str] = Field(default=None, description="Linked person ID")
    provider: Optional[str] = Field(default="Cellular Provider", description="Mobile Telecom Provider")


class BankAccountEntity(BaseModel):
    account_number: str = Field(description="Bank account number")
    bank_name: Optional[str] = Field(default="Bank Network", description="Name of the bank")
    owner_id: Optional[str] = Field(default=None, description="Linked person ID")


class VehicleEntity(BaseModel):
    plate_number: str = Field(description="Vehicle registration plate number")
    owner_id: Optional[str] = Field(default=None, description="Linked person ID")
    model: Optional[str] = Field(default="Vehicle", description="Make and model of vehicle")


class SocialHandleEntity(BaseModel):
    platform: str = Field(default="Instagram", description="Social media platform")
    handle: str = Field(description="User handle e.g. @amit_rider")
    owner_id: Optional[str] = Field(default=None, description="Linked person ID")
    linked_ip: Optional[str] = Field(default=None, description="Associated IP address")


class Entities(BaseModel):
    people: List[PersonEntity] = Field(default_factory=list)
    phones: List[PhoneEntity] = Field(default_factory=list)
    bank_accounts: List[BankAccountEntity] = Field(default_factory=list)
    vehicles: List[VehicleEntity] = Field(default_factory=list)
    social_handles: List[SocialHandleEntity] = Field(default_factory=list)


class CommunicationRelationship(BaseModel):
    caller: str = Field(description="Caller MSISDN")
    recipient: str = Field(description="Recipient MSISDN")
    timestamp: Optional[str] = Field(default=None, description="Call timestamp YYYY-MM-DD HH:MM:SS")
    duration_sec: int = Field(default=0, description="Duration of call in seconds")
    cell_tower: Optional[str] = Field(default=None, description="Cell tower ID")


class TransactionRelationship(BaseModel):
    sender: str = Field(description="Sender account number")
    receiver: str = Field(description="Receiver account number")
    amount_inr: float = Field(default=0.0, description="Transaction amount in INR")
    timestamp: Optional[str] = Field(default=None, description="Transaction timestamp YYYY-MM-DD HH:MM:SS")
    txn_id: str = Field(description="Unique transaction ID")
    description: Optional[str] = Field(default=None, description="Transaction description or notes")


class Relationships(BaseModel):
    communications: List[CommunicationRelationship] = Field(default_factory=list)
    transactions: List[TransactionRelationship] = Field(default_factory=list)


class SurveillanceLog(BaseModel):
    log_id: Optional[str] = Field(default=None, description="Surveillance log ID")
    timestamp: Optional[str] = Field(default=None, description="Timestamp of observation")
    location_id: Optional[str] = Field(default=None, description="Location ID")
    location: Optional[str] = Field(default=None, description="Location of observation")
    location_name: Optional[str] = Field(default=None, description="Location name")
    latitude: Optional[float] = Field(default=None, description="GPS Latitude")
    longitude: Optional[float] = Field(default=None, description="GPS Longitude")
    observation: Optional[str] = Field(default=None, description="Details of observation")
    activity_description: Optional[str] = Field(default=None, description="Activity description")
    observed_person_ids: List[str] = Field(default_factory=list, description="Person IDs observed")
    observed_vehicle_vins: List[str] = Field(default_factory=list, description="Vehicle VINs or plates observed")
    observed_phone_numbers: List[str] = Field(default_factory=list, description="Phone numbers observed")
    evidence_ref: Optional[str] = Field(default=None, description="Evidence reference")
    source_record_id: Optional[str] = Field(default=None, description="Source record ID")



class CriminalHistory(BaseModel):
    person_id: str = Field(description="Linked person ID")
    prior_cases: List[str] = Field(default_factory=list, description="List of prior FIR / case numbers")
    status: str = Field(default="Prior Convict / Charged", description="Legal status e.g. Out on bail, Repeat Offender")


class IntelligenceReport(BaseModel):
    date: str = Field(description="Report date YYYY-MM-DD")
    source: str = Field(description="Source of intelligence e.g. Informant-X, Field Agent")
    intel_details: str = Field(description="Content of intelligence input")


class ConsolidatedCaseData(BaseModel):
    case_metadata: CaseMetadata
    entities: Entities
    relationships: Relationships
    surveillance_logs: List[SurveillanceLog] = Field(default_factory=list)
    criminal_history: List[CriminalHistory] = Field(default_factory=list)
    intelligence_reports: List[IntelligenceReport] = Field(default_factory=list)
