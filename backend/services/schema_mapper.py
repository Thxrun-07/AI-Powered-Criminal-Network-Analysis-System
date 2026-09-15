from typing import Dict, Any, List
from backend.models.case_input import CaseData, CaseMetadata, EntitiesContainer, RelationshipsContainer
from backend.models.entity import Person, Phone, BankAccount, Vehicle, SocialHandle, FIR
from backend.models.relationship import CommunicationRecord, TransactionRecord, SurveillanceLogRecord, CriminalHistoryRecord, IntelligenceReportRecord

def map_ingestion_to_graph_data(ingestion_data: Dict[str, Any]) -> CaseData:
    """
    Translates ConsolidatedCaseData intermediate format or structured JSON into Neo4j CaseData schema.
    """
    case_meta = ingestion_data.get("case_metadata", {})
    case_id = case_meta.get("case_id") if case_meta.get("case_id") is not None else "CASE_001"

    
    # 1. Map CaseMetadata
    case_name = (
        case_meta.get("case_name") or
        case_meta.get("case_title") or
        case_meta.get("title") or
        (f"Operation {case_meta.get('fir_number')}" if case_meta.get("fir_number") else f"Case {case_id}")
    )
    mapped_metadata = CaseMetadata(
        case_id=case_id,
        case_name=case_name,
        case_type=case_meta.get("case_type") or case_meta.get("crime_type") or "GENERAL_INVESTIGATION",
        status=case_meta.get("status") or "OPEN",
        jurisdiction=case_meta.get("jurisdiction") or case_meta.get("department"),
        lead_investigator=case_meta.get("lead_investigator") or case_meta.get("assigned_officer"),
        created_date=case_meta.get("created_date") or case_meta.get("reporting_date"),
        summary=case_meta.get("summary") or f"Ingested case with FIR number: {case_meta.get('fir_number') or 'N/A'}"
    )

    # 2. Map Entities
    entities = ingestion_data.get("entities", {})
    
    mapped_people = []
    for p in entities.get("people", []):
        pid = p.get("person_id") or p.get("id")
        name = p.get("name")
        if not pid or not name:
            continue
        roles = p.get("roles") or ([p.get("status")] if p.get("status") else ["Suspect"])
        mapped_people.append(
            Person(
                person_id=pid,
                name=name,
                aliases=p.get("aliases") or [],
                dob=p.get("dob"),
                national_id=p.get("national_id"),
                roles=roles,
                risk_level=p.get("risk_level", "MEDIUM"),
                notes=p.get("notes"),
                properties=p.get("properties") or {}
            )
        )

    mapped_phones = []
    for ph in entities.get("phones", []):
        pnum = ph.get("phone_number") or ph.get("msisdn")
        if not pnum:
            continue
        mapped_phones.append(
            Phone(
                phone_number=pnum,
                phone_id=ph.get("phone_id") or pnum,
                imei=ph.get("imei"),
                carrier=ph.get("carrier") or ph.get("provider"),
                registered_owner=ph.get("registered_owner"),
                owner_person_id=ph.get("owner_person_id") or ph.get("owner_id"),
                properties=ph.get("properties") or {}
            )
        )

    mapped_accounts = []
    for acc in entities.get("bank_accounts", []):
        anum = acc.get("account_number")
        if not anum:
            continue
        mapped_accounts.append(
            BankAccount(
                account_number=anum,
                account_id=acc.get("account_id") or anum,
                bank_name=acc.get("bank_name", "Bank Network"),
                account_type=acc.get("account_type", "SAVINGS"),
                branch=acc.get("branch"),
                holder_name=acc.get("holder_name"),
                owner_person_id=acc.get("owner_person_id") or acc.get("owner_id"),
                properties=acc.get("properties") or {}
            )
        )

    mapped_vehicles = []
    for veh in entities.get("vehicles", []):
        vin = veh.get("vin") or veh.get("plate_number") or veh.get("license_plate")
        if not vin:
            continue
        mapped_vehicles.append(
            Vehicle(
                vin=vin,
                vehicle_id=veh.get("vehicle_id") or vin,
                license_plate=veh.get("license_plate") or veh.get("plate_number"),
                make=veh.get("make"),
                model=veh.get("model", "Vehicle"),
                color=veh.get("color"),
                registered_owner=veh.get("registered_owner"),
                owner_person_id=veh.get("owner_person_id") or veh.get("owner_id"),
                properties=veh.get("properties") or {}
            )
        )

    mapped_socials = []
    for sh in entities.get("social_handles", []):
        handle = sh.get("handle")
        if not handle:
            continue
        platform = sh.get("platform", "Instagram")
        hid = sh.get("handle_id") or f"{platform.lower()}_{handle}"
        mapped_socials.append(
            SocialHandle(
                handle_id=hid,
                platform=platform,
                handle=handle,
                associated_email=sh.get("associated_email"),
                display_name=sh.get("display_name"),
                owner_person_id=sh.get("owner_person_id") or sh.get("owner_id"),
                properties=sh.get("properties") or {}
            )
        )

    # 3. Map Relationships
    relationships = ingestion_data.get("relationships", {})
    
    mapped_communications = []
    for idx, comm in enumerate(relationships.get("communications", [])):
        src = comm.get("source_phone") or comm.get("caller")
        tgt = comm.get("target_phone") or comm.get("recipient")
        if not src or not tgt:
            continue
        duration = comm.get("duration_seconds") if comm.get("duration_seconds") is not None else comm.get("duration_sec", 0)
        mapped_communications.append(
            CommunicationRecord(
                call_id=comm.get("call_id") or f"CALL_{src}_{tgt}_{idx}",
                source_phone=src,
                target_phone=tgt,
                timestamp=comm.get("timestamp") or "2026-01-01 00:00:00",
                duration_seconds=int(duration),
                cell_tower=comm.get("cell_tower")
            )
        )

    mapped_transactions = []
    for idx, txn in enumerate(relationships.get("transactions", [])):
        src = txn.get("source_account") or txn.get("sender")
        tgt = txn.get("target_account") or txn.get("receiver")
        if not src or not tgt:
            continue
        amt = txn.get("amount") if txn.get("amount") is not None else txn.get("amount_inr", 0.0)
        mapped_transactions.append(
            TransactionRecord(
                transaction_id=txn.get("transaction_id") or txn.get("txn_id") or f"TXN_{idx}",
                source_account=src,
                target_account=tgt,
                amount=float(amt),
                timestamp=txn.get("timestamp") or "2026-01-01 00:00:00"
            )
        )

    # 4. Map surveillance logs
    mapped_surveillance = []
    for idx, log in enumerate(ingestion_data.get("surveillance_logs", [])):
        mapped_surveillance.append(
            SurveillanceLogRecord(
                log_id=log.get("log_id") or f"SURV_{case_id}_{idx}",
                location_name=log.get("location_name") or log.get("location"),
                timestamp=log.get("timestamp") or "2026-01-01 00:00:00",
                activity_description=log.get("activity_description") or log.get("observation")
            )
        )

    # 5. Map criminal history
    mapped_criminal_history = []
    for idx, hist in enumerate(ingestion_data.get("criminal_history", [])):
        pid = hist.get("person_id")
        priors = hist.get("prior_cases", [])
        if priors:
            for c_idx, case_num in enumerate(priors):
                mapped_criminal_history.append(
                    CriminalHistoryRecord(
                        record_id=hist.get("record_id") or f"CRIM_{pid}_{idx}_{c_idx}",
                        person_id=pid,
                        case_number=case_num,
                        status=hist.get("status", "Repeat Offender")
                    )
                )
        elif hist.get("case_number"):
            mapped_criminal_history.append(
                CriminalHistoryRecord(
                    record_id=hist.get("record_id") or f"CRIM_{pid}_{idx}",
                    person_id=pid,
                    case_number=hist.get("case_number"),
                    status=hist.get("status", "Repeat Offender")
                )
            )

    # 6. Map intelligence reports
    mapped_intel = []
    for idx, report in enumerate(ingestion_data.get("intelligence_reports", [])):
        mapped_intel.append(
            IntelligenceReportRecord(
                report_id=report.get("report_id") or f"INTEL_{case_id}_{idx}",
                source_agency=report.get("source_agency") or report.get("source"),
                date=report.get("date") or "2026-01-01",
                content=report.get("content") or report.get("intel_details")
            )
        )

    # 7. Map Associated FIR Details
    mapped_firs = []
    if case_meta.get("fir_number"):
        mapped_firs.append(
            FIR(
                fir_id=f"FIR_{case_meta.get('fir_number').replace('/', '_')}",
                fir_number=case_meta.get("fir_number"),
                police_station=case_meta.get("department") or "Unknown PS",
                date=case_meta.get("reporting_date"),
                summary=f"Ingested FIR for case {case_id}"
            )
        )

    return CaseData(
        case_metadata=mapped_metadata,
        fir_records=mapped_firs,
        entities=EntitiesContainer(
            people=mapped_people,
            phones=mapped_phones,
            bank_accounts=mapped_accounts,
            vehicles=mapped_vehicles,
            social_handles=mapped_socials
        ),
        relationships=RelationshipsContainer(
            communications=mapped_communications,
            transactions=mapped_transactions
        ),
        surveillance_logs=mapped_surveillance,
        criminal_history=mapped_criminal_history,
        intelligence_reports=mapped_intel
    )


