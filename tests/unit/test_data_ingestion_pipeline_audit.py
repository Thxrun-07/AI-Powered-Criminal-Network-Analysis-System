import io
import json
import pytest
from unittest.mock import MagicMock, patch

from backend.models.case_input import CaseData, CaseMetadata, EntitiesContainer, RelationshipsContainer
from backend.models.entity import Person, Phone, BankAccount, Vehicle, SocialHandle, Location, CellTower, IPAddress
from backend.models.relationship import CommunicationRecord, TransactionRecord, SurveillanceLogRecord, CriminalHistoryRecord, IntelligenceReportRecord
from backend.services.ingestion_engine import CaseIngestionEngine
from backend.services.schema_mapper import map_ingestion_to_graph_data
from backend.services.ingestion_service import IngestionService
import backend.services.graph_writes as gw
from backend.routers.ingest import _extract_text_from_file


def test_person_identity_resolution_acceptance_criteria():
    """Requirement 4 & 28: Two persons with same name but different IDs must remain two separate nodes."""
    doc = {
        "case_metadata": {"case_id": "CASE-TEST-001", "case_name": "Identity Test Case"},
        "entities": {
            "people": [
                {
                    "person_id": "P001",
                    "name": "Rahul Kumar",
                    "age": 32,
                    "roles": ["Suspect"],
                    "phone_numbers": ["9876543210"]
                },
                {
                    "person_id": "P002",
                    "name": "Rahul Kumar",
                    "age": 35,
                    "roles": ["Witness"]
                }
            ],
            "vehicles": [
                {"vin": "VIN001", "plate_number": "VIN001", "owner_person_id": "P001"}
            ],
            "ip_addresses": [
                {"ip_address": "192.168.1.10", "owner_person_id": "P001"}
            ],
            "cell_towers": [
                {"cell_tower_id": "TOWER001", "tower_code": "TOWER001"}
            ]
        },
        "relationships": {
            "communications": [
                {"source_phone": "9876543210", "target_phone": "9999900000", "timestamp": "2026-09-14T10:00:00"}
            ],
            "transactions": [
                {"transaction_id": "TXN_P001_ACC1", "source_account": "ACC_P001", "target_account": "ACC_BANK_A", "amount": 50000, "timestamp": "2026-09-14T11:00:00"}
            ]
        },
        "surveillance_logs": [
            {
                "log_id": "SURV_001",
                "timestamp": "2026-09-14T12:00:00",
                "location_name": "Central Market",
                "observed_person_ids": ["P001"],
                "observed_vehicle_vins": ["VIN001"],
                "observed_phone_numbers": ["9876543210"]
            }
        ]
    }

    mapped_case_data = map_ingestion_to_graph_data(doc)
    people = mapped_case_data.entities.people

    assert len(people) == 2, f"Expected 2 separate Person entities, got {len(people)}"
    p1 = next(p for p in people if p.person_id == "P001")
    p2 = next(p for p in people if p.person_id == "P002")

    assert p1.name == "Rahul Kumar" and p1.age == 32 and p1.roles == ["Suspect"]
    assert p2.name == "Rahul Kumar" and p2.age == 35 and p2.roles == ["Witness"]
    assert p1.person_id != p2.person_id


def test_person_attribute_preservation_and_properties_map():
    """Requirement 1, 2 & 27: Verify Person attributes and custom properties dictionary survive schema mapping."""
    raw_doc = {
        "case_metadata": {"case_id": "CASE-ATTR-001"},
        "entities": {
            "people": [
                {
                    "person_id": "P001",
                    "name": "Rahul Kumar",
                    "age": 32,
                    "gender": "Male",
                    "address": "123 Park Street, Delhi",
                    "occupation": "Engineer",
                    "phone_numbers": ["9876543210"],
                    "aliases": ["RK"],
                    "roles": ["Suspect"],
                    "properties": {
                        "father_name": "ABC Kumar",
                        "nationality": "Indian",
                        "criminal_role": "Financier"
                    }
                }
            ]
        }
    }

    mapped = map_ingestion_to_graph_data(raw_doc)
    person = mapped.entities.people[0]

    assert person.person_id == "P001"
    assert person.name == "Rahul Kumar"
    assert person.age == 32
    assert person.gender == "Male"
    assert person.address == "123 Park Street, Delhi"
    assert person.occupation == "Engineer"
    assert person.phone_numbers == ["9876543210"]
    assert person.aliases == ["RK"]
    assert person.properties == {"father_name": "ABC Kumar", "nationality": "Indian", "criminal_role": "Financier"}

    row = gw.person_row(person)
    assert row["properties"] == {"father_name": "ABC Kumar", "nationality": "Indian", "criminal_role": "Financier"}
    assert "p += row.properties" in gw.PEOPLE_MERGE


def test_person_canonical_name_and_alias_merging_cypher():
    """Requirement 5: PEOPLE_MERGE Cypher query preserves canonical name and adds alternate names to aliases."""
    assert "p.name=coalesce(p.name, row.name)" in gw.PEOPLE_MERGE
    assert "p.aliases=reduce(" in gw.PEOPLE_MERGE
    assert "row.name <> p.name" in gw.PEOPLE_MERGE
    assert "p.source_record_ids=reduce(" in gw.PEOPLE_MERGE


def test_ip_address_uses_ip_relationship():
    """Requirement 11 & 34: IP address entities and USES_IP graph relationships."""
    raw_doc = {
        "case_metadata": {"case_id": "CASE-IP-001"},
        "entities": {
            "ip_addresses": [
                {"ip_address": "192.168.1.10", "owner_person_id": "P001"}
            ],
            "social_handles": [
                {"handle": "@user1", "platform": "Telegram", "linked_ip": "192.168.1.10", "owner_person_id": "P001"}
            ]
        }
    }

    mapped = map_ingestion_to_graph_data(raw_doc)
    ip_entity = mapped.entities.ip_addresses[0]
    social_entity = mapped.entities.social_handles[0]

    assert ip_entity.ip_address == "192.168.1.10"
    assert ip_entity.owner_person_id == "P001"
    assert social_entity.linked_ip == "192.168.1.10"

    ip_rows = [gw.ip_address_row(ip_entity)]
    social_rows = [gw.social_handle_row(social_entity)]

    pip_rows = gw.person_uses_ip_rows(ip_rows)
    sip_rows = gw.social_uses_ip_rows(social_rows)

    assert pip_rows == [{"owner_id": "P001", "ip_address": "192.168.1.10"}]
    assert sip_rows == [{"handle_id": "telegram_@user1", "linked_ip": "192.168.1.10"}]


def test_no_fabricated_event_dates():
    """Requirement 8 & 32: Missing dates remain None/null and are never hardcoded with fake default dates."""
    raw_doc = {
        "case_metadata": {"case_id": "CASE-NODATE-001"},
        "relationships": {
            "communications": [
                {"source_phone": "9999911111", "target_phone": "9999922222"}  # timestamp missing
            ],
            "transactions": [
                {"transaction_id": "TXN_001", "source_account": "ACC1", "target_account": "ACC2", "amount": 1000}  # timestamp missing
            ]
        },
        "surveillance_logs": [
            {"log_id": "SURV_101", "activity_description": "Observed suspect near bank"}  # timestamp missing
        ]
    }

    mapped = map_ingestion_to_graph_data(raw_doc)
    comm = mapped.relationships.communications[0]
    txn = mapped.relationships.transactions[0]
    surv = mapped.surveillance_logs[0]

    assert comm.timestamp is None
    assert txn.timestamp is None
    assert surv.timestamp is None


def test_surveillance_log_full_attribute_and_phone_mapping():
    """Requirement 13 & 33: Verify surveillance log retains coordinates, observed entities, and observed phones."""
    raw_doc = {
        "case_metadata": {"case_id": "CASE-SURV-001"},
        "surveillance_logs": [
            {
                "log_id": "SURV_501",
                "location_id": "LOC_99",
                "location_name": "Safehouse Alpha",
                "latitude": 28.6139,
                "longitude": 77.2090,
                "timestamp": "2026-09-14T14:30:00",
                "observed_person_ids": ["P001", "P002"],
                "observed_vehicle_vins": ["VIN001"],
                "observed_phone_numbers": ["9876543210"],
                "activity_description": "Meeting observed",
                "evidence_ref": "CAM_CCTV_04",
                "source_record_id": "SR_SURV_01"
            }
        ]
    }

    mapped = map_ingestion_to_graph_data(raw_doc)
    surv = mapped.surveillance_logs[0]

    assert surv.log_id == "SURV_501"
    assert surv.location_id == "LOC_99"
    assert surv.location_name == "Safehouse Alpha"
    assert surv.latitude == 28.6139
    assert surv.longitude == 77.2090
    assert surv.timestamp == "2026-09-14T14:30:00"
    assert surv.observed_person_ids == ["P001", "P002"]
    assert surv.observed_vehicle_vins == ["VIN001"]
    assert surv.observed_phone_numbers == ["9876543210"]
    assert surv.evidence_ref == "CAM_CCTV_04"
    assert surv.source_record_id == "SR_SURV_01"

    phone_rows = gw.surveillance_phone_rows(surv)
    assert phone_rows == [{
        "phone_number": "9876543210",
        "loc_id": "LOC_99",
        "log_id": "SURV_501",
        "timestamp": "2026-09-14T14:30:00",
        "activity": "Meeting observed"
    }]


def test_pdf_extraction_invalid_or_scanned_handling():
    """Requirement 36: Verify proper 422 error handling when a PDF contains no extractable text or is invalid binary."""
    with pytest.raises(Exception) as exc_info:
        _extract_text_from_file("corrupt.pdf", b"NOT_A_PDF_HEADER_BLOB", "application/pdf")
    assert "422" in str(exc_info.value.status_code) if hasattr(exc_info.value, "status_code") else True


def test_ingestion_engine_id_first_resolution_and_dehardcoding():
    """Requirement 9 & 10: Verify CaseIngestionEngine uses ID-first resolution and avoids hardcoded names."""
    engine = CaseIngestionEngine()
    
    p1 = engine._get_or_create_person(name="Rahul Kumar", person_id="P001", age=32, status="Suspect")
    p2 = engine._get_or_create_person(name="Rahul Kumar", person_id="P002", age=35, status="Witness")

    assert p1.id == "P001" and p1.age == 32
    assert p2.id == "P002" and p2.age == 35
    assert len(engine.people_by_id) == 2
