from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from backend.models.common import AuditFields


class Person(AuditFields):
    person_id: str = Field(..., description="Unique deterministic identifier for Person")
    name: str = Field(..., description="Full Name")
    aliases: List[str] = Field(default_factory=list, description="Known aliases")
    age: Optional[int] = Field(default=None, description="Age of person")
    gender: Optional[str] = Field(default=None, description="Gender (e.g., Male, Female, Non-Binary)")
    address: Optional[str] = Field(default=None, description="Residential or primary address")
    occupation: Optional[str] = Field(default=None, description="Occupation or professional title")
    phone_numbers: List[str] = Field(default_factory=list, description="Associated phone numbers")
    dob: Optional[str] = Field(default=None, description="Date of birth (YYYY-MM-DD)")
    national_id: Optional[str] = Field(default=None, description="National ID or Passport number")
    roles: List[str] = Field(default_factory=list, description="Roles in case, e.g. Suspect, Victim, Witness, Associate")
    risk_level: Optional[str] = Field(default="MEDIUM", description="Assessed risk level: CRITICAL, HIGH, MEDIUM, LOW")
    notes: Optional[str] = Field(default=None, description="Investigator notes")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Additional arbitrary attributes")


class Phone(AuditFields):
    phone_number: str = Field(..., description="E.164 or canonical phone number")
    phone_id: Optional[str] = Field(default=None, description="Optional phone identifier")
    imei: Optional[str] = Field(default=None, description="Device IMEI")
    carrier: Optional[str] = Field(default=None, description="Telecom carrier / network operator")
    registered_owner: Optional[str] = Field(default=None, description="Registered subscriber name")
    owner_person_id: Optional[str] = Field(default=None, description="Person ID who owns this phone")
    properties: Dict[str, Any] = Field(default_factory=dict)


class BankAccount(AuditFields):
    account_number: str = Field(..., description="Bank Account Number or IBAN")
    account_id: Optional[str] = Field(default=None, description="Optional account identifier")
    bank_name: Optional[str] = Field(default=None, description="Name of financial institution")
    account_type: Optional[str] = Field(default="SAVINGS", description="SAVINGS, CURRENT, ESCROW, OFFSHORE")
    branch: Optional[str] = Field(default=None, description="Bank Branch or IFSC/Routing code")
    holder_name: Optional[str] = Field(default=None, description="Account holder name")
    owner_person_id: Optional[str] = Field(default=None, description="Person ID who owns this account")
    properties: Dict[str, Any] = Field(default_factory=dict)


class Vehicle(AuditFields):
    vin: str = Field(..., description="Vehicle Identification Number (VIN) or normalized Chassis No")
    vehicle_id: Optional[str] = Field(default=None, description="Optional vehicle identifier")
    license_plate: Optional[str] = Field(default=None, description="Registration / License plate")
    make: Optional[str] = Field(default=None, description="Vehicle Make / Manufacturer")
    model: Optional[str] = Field(default=None, description="Vehicle Model")
    color: Optional[str] = Field(default=None, description="Vehicle Color")
    registered_owner: Optional[str] = Field(default=None, description="Registered owner name")
    owner_person_id: Optional[str] = Field(default=None, description="Person ID who owns this vehicle")
    properties: Dict[str, Any] = Field(default_factory=dict)


class SocialHandle(AuditFields):
    handle_id: str = Field(..., description="Unique handle identifier (e.g. twitter_@user)")
    platform: str = Field(..., description="Social platform: Telegram, WhatsApp, Twitter, Instagram, Signal")
    handle: str = Field(..., description="Username or handle")
    associated_email: Optional[str] = Field(default=None, description="Associated email address")
    display_name: Optional[str] = Field(default=None, description="Profile display name")
    owner_person_id: Optional[str] = Field(default=None, description="Person ID who uses this handle")
    linked_ip: Optional[str] = Field(default=None, description="Associated IP address")
    properties: Dict[str, Any] = Field(default_factory=dict)


class IPAddress(AuditFields):
    ip_address: str = Field(..., description="IPv4 or IPv6 Address")
    ip_type: Optional[str] = Field(default="IPV4", description="IPV4 or IPV6")
    asn: Optional[str] = Field(default=None, description="Autonomous System Number")
    isp: Optional[str] = Field(default=None, description="Internet Service Provider")
    owner_person_id: Optional[str] = Field(default=None, description="Person ID who uses this IP address")
    properties: Dict[str, Any] = Field(default_factory=dict)


class Location(AuditFields):
    location_id: str = Field(..., description="Unique location identifier")
    name: Optional[str] = Field(default=None, description="Location name or landmark")
    address: Optional[str] = Field(default=None, description="Street address")
    latitude: Optional[float] = Field(default=None, description="GPS Latitude")
    longitude: Optional[float] = Field(default=None, description="GPS Longitude")
    location_type: Optional[str] = Field(default=None, description="RESIDENCE, CRIME_SCENE, HIDEOUT, COMMERCIAL")
    properties: Dict[str, Any] = Field(default_factory=dict)


class CellTower(AuditFields):
    cell_tower_id: str = Field(..., description="Unique Cell Tower Identifier / CGI")
    tower_code: Optional[str] = Field(default=None, description="Tower code / LAC-CID")
    operator: Optional[str] = Field(default=None, description="Telecom operator")
    latitude: Optional[float] = Field(default=None, description="Latitude")
    longitude: Optional[float] = Field(default=None, description="Longitude")
    location_id: Optional[str] = Field(default=None, description="Associated Location ID")
    properties: Dict[str, Any] = Field(default_factory=dict)


class PriorCase(AuditFields):
    prior_case_id: str = Field(..., description="Unique prior case record ID")
    case_number: str = Field(..., description="Docket / Case reference number")
    offense: Optional[str] = Field(default=None, description="Offense / Section description")
    jurisdiction: Optional[str] = Field(default=None, description="Police station or court jurisdiction")
    status: Optional[str] = Field(default="CONVICTED", description="CONVICTED, ACQUITTED, PENDING, DISMISSED")
    year: Optional[int] = Field(default=None, description="Year of incident")
    person_id: Optional[str] = Field(default=None, description="Person associated with this record")
    properties: Dict[str, Any] = Field(default_factory=dict)


class SourceRecord(AuditFields):
    source_record_id: str = Field(..., description="Unique source record reference")
    source_type: str = Field(..., description="CDR, BANK_STATEMENT, CCTV, POLICE_REPORT, INTEL_MEMO")
    record_type: Optional[str] = Field(default="EVIDENCE", description="EVIDENCE, WITNESS_STATEMENT, FORENSIC")
    raw_reference: Optional[str] = Field(default=None, description="Original document ID or file path")
    ingested_at: str = Field(default_factory=lambda: AuditFields().created_at)
    properties: Dict[str, Any] = Field(default_factory=dict)


class FIR(AuditFields):
    fir_id: str = Field(..., description="Unique FIR identifier")
    fir_number: str = Field(..., description="Official FIR Registration Number")
    police_station: str = Field(..., description="Station Jurisdiction")
    date: Optional[str] = Field(default=None, description="Filing Date (YYYY-MM-DD)")
    sections: List[str] = Field(default_factory=list, description="Penal Code Sections / Acts")
    complainant: Optional[str] = Field(default=None, description="Complainant Name")
    summary: Optional[str] = Field(default=None, description="Brief narrative of the FIR")
    accused_person_ids: List[str] = Field(default_factory=list, description="Person IDs of accused named in FIR")
    properties: Dict[str, Any] = Field(default_factory=dict)

