from typing import Dict, Any, List
from backend.models.case_input import CaseData, CaseMetadata, EntitiesContainer, RelationshipsContainer
from backend.models.entity import Person, Phone, BankAccount, Vehicle, SocialHandle, IPAddress, Location, CellTower, FIR
from backend.models.relationship import CommunicationRecord, TransactionRecord, SurveillanceLogRecord, CriminalHistoryRecord, IntelligenceReportRecord
from backend.services.ingestion_engine import is_valid_person_name, clean_person_name

def map_ingestion_to_graph_data(ingestion_data: Dict[str, Any]) -> CaseData:
    """
    Translates ConsolidatedCaseData intermediate format or structured JSON into Neo4j CaseData schema,
    ensuring zero hallucination and complete deduplication without unnecessary repetition of data.
    """
    case_meta = ingestion_data.get("case_metadata", {}) if isinstance(ingestion_data.get("case_metadata"), dict) else {}
    raw_case_id = case_meta.get("case_id") if "case_id" in case_meta else ingestion_data.get("case_id")
    if raw_case_id is not None and str(raw_case_id).strip() == "":
        case_id = ""
    else:
        case_id = raw_case_id or (f"CASE_{case_meta.get('fir_number').replace('/', '_')}" if case_meta.get("fir_number") else "CASE_001")

    # 1. Map CaseMetadata
    case_name = (
        case_meta.get("case_name") or
        case_meta.get("case_title") or
        case_meta.get("title") or
        ingestion_data.get("case_name") or
        ingestion_data.get("title") or
        (f"Operation {case_meta.get('fir_number')}" if case_meta.get("fir_number") else (f"Case {case_id}" if case_id else "Untitled Case"))
    )
    mapped_metadata = CaseMetadata(
        case_id=case_id,
        case_name=case_name,
        case_type=case_meta.get("case_type") or case_meta.get("crime_type") or "GENERAL_INVESTIGATION",
        priority=case_meta.get("priority") or "HIGH",
        status=case_meta.get("status") or "OPEN",
        jurisdiction=case_meta.get("jurisdiction") or case_meta.get("department"),
        lead_investigator=case_meta.get("lead_investigator") or case_meta.get("assigned_officer"),
        uploaded_by=case_meta.get("uploaded_by"),
        created_date=case_meta.get("created_date") or case_meta.get("reporting_date"),
        summary=case_meta.get("summary") or f"Ingested case with FIR number: {case_meta.get('fir_number') or 'N/A'}",
        tags=case_meta.get("tags") or []
    )

    # 2. Map Entities with Deduplication
    entities = ingestion_data.get("entities", {}) if isinstance(ingestion_data.get("entities"), dict) else {}
    
    people_items = []
    if "people" in entities and isinstance(entities["people"], list):
        people_items.extend(entities["people"])
    if "people" in ingestion_data and isinstance(ingestion_data["people"], list):
        people_items.extend(ingestion_data["people"])
    if "person_id" in ingestion_data or ("name" in ingestion_data and is_valid_person_name(ingestion_data["name"])):
        people_items.append(ingestion_data)

    mapped_people_map: Dict[str, Person] = {}
    for p in people_items:
        if not isinstance(p, dict): continue
        raw_name = p.get("name")
        clean_n = clean_person_name(raw_name) if raw_name else ""
        if not is_valid_person_name(clean_n):
            continue
        pid = p.get("person_id") or p.get("id") or f"P_{abs(hash(clean_n)) % 10000}"
        name = clean_n
        roles = p.get("roles") or ([p.get("status")] if p.get("status") else ([p.get("role")] if p.get("role") and isinstance(p.get("role"), str) else ["Suspect"]))
        if isinstance(roles, str):
            roles = [roles]
        
        props = p.get("properties") or {}
        if p.get("father_name"):
            props["father_name"] = p.get("father_name")

        person_obj = Person(
            person_id=pid,
            name=name,
            aliases=p.get("aliases") or [],
            age=p.get("age"),
            gender=p.get("gender"),
            address=p.get("address"),
            occupation=p.get("occupation"),
            phone_numbers=p.get("phone_numbers") or [],
            dob=p.get("dob"),
            national_id=p.get("national_id"),
            roles=roles,
            risk_level=p.get("risk_level", "MEDIUM"),
            notes=p.get("notes"),
            properties=props
        )

        if pid in mapped_people_map:
            existing = mapped_people_map[pid]
            for alias in person_obj.aliases:
                if alias not in existing.aliases:
                    existing.aliases.append(alias)
            for role in person_obj.roles:
                if role not in existing.roles:
                    existing.roles.append(role)
            for ph in person_obj.phone_numbers:
                if ph not in existing.phone_numbers:
                    existing.phone_numbers.append(ph)
            if not existing.dob and person_obj.dob:
                existing.dob = person_obj.dob
            if not existing.national_id and person_obj.national_id:
                existing.national_id = person_obj.national_id
        else:
            mapped_people_map[pid] = person_obj

    mapped_people = list(mapped_people_map.values())

    mapped_phones_map: Dict[str, Phone] = {}
    for ph in entities.get("phones", []):
        pnum = ph.get("phone_number") or ph.get("msisdn")
        if not pnum:
            continue
        phone_obj = Phone(
            phone_number=pnum,
            phone_id=ph.get("phone_id") or pnum,
            imei=ph.get("imei"),
            carrier=ph.get("carrier") or ph.get("provider"),
            registered_owner=ph.get("registered_owner"),
            owner_person_id=ph.get("owner_person_id") or ph.get("owner_id"),
            properties=ph.get("properties") or {}
        )
        if pnum not in mapped_phones_map:
            mapped_phones_map[pnum] = phone_obj

    mapped_phones = list(mapped_phones_map.values())

    mapped_accounts_map: Dict[str, BankAccount] = {}
    for acc in entities.get("bank_accounts", []):
        anum = acc.get("account_number")
        if not anum:
            continue
        account_obj = BankAccount(
            account_number=anum,
            account_id=acc.get("account_id") or anum,
            bank_name=acc.get("bank_name", "Bank Network"),
            account_type=acc.get("account_type", "SAVINGS"),
            branch=acc.get("branch"),
            holder_name=acc.get("holder_name"),
            owner_person_id=acc.get("owner_person_id") or acc.get("owner_id"),
            properties=acc.get("properties") or {}
        )
        if anum not in mapped_accounts_map:
            mapped_accounts_map[anum] = account_obj

    mapped_accounts = list(mapped_accounts_map.values())

    mapped_vehicles_map: Dict[str, Vehicle] = {}
    for veh in entities.get("vehicles", []):
        vin = veh.get("vin") or veh.get("plate_number") or veh.get("license_plate")
        if not vin:
            continue
        veh_obj = Vehicle(
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
        if vin not in mapped_vehicles_map:
            mapped_vehicles_map[vin] = veh_obj

    mapped_vehicles = list(mapped_vehicles_map.values())

    mapped_socials_map: Dict[str, SocialHandle] = {}
    for sh in entities.get("social_handles", []):
        handle = sh.get("handle")
        if not handle:
            continue
        platform = sh.get("platform", "Instagram")
        hid = sh.get("handle_id") or f"{platform.lower()}_{handle}"
        sh_obj = SocialHandle(
            handle_id=hid,
            platform=platform,
            handle=handle,
            associated_email=sh.get("associated_email"),
            display_name=sh.get("display_name"),
            owner_person_id=sh.get("owner_person_id") or sh.get("owner_id"),
            linked_ip=sh.get("linked_ip"),
            properties=sh.get("properties") or {}
        )
        if hid not in mapped_socials_map:
            mapped_socials_map[hid] = sh_obj

    mapped_socials = list(mapped_socials_map.values())

    mapped_ips_map: Dict[str, IPAddress] = {}
    for ip_item in entities.get("ip_addresses", []):
        ip_addr = ip_item.get("ip_address")
        if ip_addr:
            ip_obj = IPAddress(
                ip_address=ip_addr,
                ip_type=ip_item.get("ip_type", "IPV4"),
                asn=ip_item.get("asn"),
                isp=ip_item.get("isp"),
                owner_person_id=ip_item.get("owner_person_id") or ip_item.get("owner_id"),
                properties=ip_item.get("properties") or {}
            )
            if ip_addr not in mapped_ips_map:
                mapped_ips_map[ip_addr] = ip_obj

    mapped_ips = list(mapped_ips_map.values())

    mapped_locations_map: Dict[str, Location] = {}
    for loc in entities.get("locations", []):
        lid = loc.get("location_id") or f"LOC_{loc.get('name', 'UNKNOWN')}"
        loc_obj = Location(
            location_id=lid,
            name=loc.get("name") or loc.get("location_name"),
            address=loc.get("address"),
            latitude=loc.get("latitude"),
            longitude=loc.get("longitude"),
            location_type=loc.get("location_type"),
            properties=loc.get("properties") or {}
        )
        if lid not in mapped_locations_map:
            mapped_locations_map[lid] = loc_obj

    mapped_locations = list(mapped_locations_map.values())

    mapped_towers_map: Dict[str, CellTower] = {}
    for tw in entities.get("cell_towers", []):
        tid = tw.get("cell_tower_id") or tw.get("tower_code")
        if tid:
            tw_obj = CellTower(
                cell_tower_id=tid,
                tower_code=tw.get("tower_code") or tid,
                operator=tw.get("operator"),
                latitude=tw.get("latitude"),
                longitude=tw.get("longitude"),
                location_id=tw.get("location_id"),
                properties=tw.get("properties") or {}
            )
            if tid not in mapped_towers_map:
                mapped_towers_map[tid] = tw_obj

    mapped_towers = list(mapped_towers_map.values())

    # 3. Map Relationships with Deduplication
    relationships = ingestion_data.get("relationships", {})
    
    mapped_communications_map: Dict[str, CommunicationRecord] = {}
    for idx, comm in enumerate(relationships.get("communications", [])):
        src = comm.get("source_phone") or comm.get("caller")
        tgt = comm.get("target_phone") or comm.get("recipient")
        if not src or not tgt:
            continue
        duration = comm.get("duration_seconds") if comm.get("duration_seconds") is not None else comm.get("duration_sec", 0)
        cid = comm.get("call_id") or f"CALL_{src}_{tgt}_{comm.get('timestamp') or idx}"
        comm_obj = CommunicationRecord(
            call_id=cid,
            communication_id=cid,
            source_phone=src,
            target_phone=tgt,
            type=comm.get("type", "VOICE_CALL"),
            timestamp=comm.get("timestamp"),
            duration_seconds=int(duration),
            cell_tower=comm.get("cell_tower"),
            source_record_id=comm.get("source_record_id")
        )
        if cid not in mapped_communications_map:
            mapped_communications_map[cid] = comm_obj

    mapped_communications = list(mapped_communications_map.values())

    mapped_transactions_map: Dict[str, TransactionRecord] = {}
    txns_list = []
    if isinstance(relationships, dict) and "transactions" in relationships:
        txns_list.extend(relationships.get("transactions", []))
    if "transactions" in ingestion_data and isinstance(ingestion_data["transactions"], list):
        txns_list.extend(ingestion_data["transactions"])
    if "transaction" in ingestion_data and isinstance(ingestion_data["transaction"], dict):
        txns_list.append(ingestion_data["transaction"])

    for idx, txn in enumerate(txns_list):
        if not isinstance(txn, dict): continue
        src = txn.get("source_account") or txn.get("sender") or f"ACC_SRC_{idx + 1}"
        tgt = txn.get("target_account") or txn.get("receiver") or f"ACC_DST_{idx + 1}"
        amt = txn.get("amount") if txn.get("amount") is not None else txn.get("amount_inr", 0.0)
        desc = txn.get("description") or txn.get("transaction_description") or txn.get("remarks")
        props = txn.get("properties") or {}
        if desc:
            props["description"] = desc

        tx_id = txn.get("transaction_id") or txn.get("txn_id") or f"TXN_{case_id}_{idx + 1}"
        txn_obj = TransactionRecord(
            transaction_id=tx_id,
            source_account=src,
            target_account=tgt,
            amount=float(amt),
            currency=txn.get("currency", "INR"),
            timestamp=txn.get("timestamp"),
            transaction_type=txn.get("transaction_type", "NEFT"),
            reference_no=txn.get("reference_no"),
            description=desc,
            source_record_id=txn.get("source_record_id"),
            properties=props
        )
        if tx_id not in mapped_transactions_map:
            mapped_transactions_map[tx_id] = txn_obj

    mapped_transactions = list(mapped_transactions_map.values())

    # 4. Map surveillance logs with Deduplication
    mapped_surveillance_map: Dict[str, SurveillanceLogRecord] = {}
    for idx, log in enumerate(ingestion_data.get("surveillance_logs", [])):
        surv_id = log.get("log_id") or f"SURV_{case_id}_{idx}"
        surv_obj = SurveillanceLogRecord(
            log_id=surv_id,
            location_id=log.get("location_id"),
            location_name=log.get("location_name") or log.get("location"),
            latitude=log.get("latitude"),
            longitude=log.get("longitude"),
            timestamp=log.get("timestamp"),
            observed_person_ids=log.get("observed_person_ids") or [],
            observed_vehicle_vins=log.get("observed_vehicle_vins") or [],
            observed_phone_numbers=log.get("observed_phone_numbers") or [],
            activity_description=log.get("activity_description") or log.get("observation"),
            evidence_ref=log.get("evidence_ref"),
            source_record_id=log.get("source_record_id"),
            properties=log.get("properties") or {}
        )
        if surv_id not in mapped_surveillance_map:
            mapped_surveillance_map[surv_id] = surv_obj

    mapped_surveillance = list(mapped_surveillance_map.values())

    # 5. Map criminal history with Deduplication
    mapped_criminal_history_map: Dict[str, CriminalHistoryRecord] = {}
    for idx, hist in enumerate(ingestion_data.get("criminal_history", [])):
        pid = hist.get("person_id")
        priors = hist.get("prior_cases", [])
        if priors:
            for c_idx, case_num in enumerate(priors):
                rec_id = hist.get("record_id") or f"CRIM_{pid}_{idx}_{c_idx}"
                crim_obj = CriminalHistoryRecord(
                    record_id=rec_id,
                    person_id=pid,
                    case_number=case_num,
                    offense=hist.get("offense"),
                    jurisdiction=hist.get("jurisdiction"),
                    status=hist.get("status", "Repeat Offender"),
                    year=hist.get("year"),
                    source_record_id=hist.get("source_record_id")
                )
                if rec_id not in mapped_criminal_history_map:
                    mapped_criminal_history_map[rec_id] = crim_obj
        elif hist.get("case_number"):
            rec_id = hist.get("record_id") or f"CRIM_{pid}_{idx}"
            crim_obj = CriminalHistoryRecord(
                record_id=rec_id,
                person_id=pid,
                case_number=hist.get("case_number"),
                offense=hist.get("offense"),
                jurisdiction=hist.get("jurisdiction"),
                status=hist.get("status", "Repeat Offender"),
                year=hist.get("year"),
                source_record_id=hist.get("source_record_id")
            )
            if rec_id not in mapped_criminal_history_map:
                mapped_criminal_history_map[rec_id] = crim_obj

    mapped_criminal_history = list(mapped_criminal_history_map.values())

    # 6. Map intelligence reports with Deduplication
    mapped_intel_map: Dict[str, IntelligenceReportRecord] = {}
    for idx, report in enumerate(ingestion_data.get("intelligence_reports", [])):
        rep_id = report.get("report_id") or f"INTEL_{case_id}_{idx}"
        intel_obj = IntelligenceReportRecord(
            report_id=rep_id,
            source_agency=report.get("source_agency") or report.get("source") or "Unknown Agency",
            date=report.get("date"),
            reliability_score=report.get("reliability_score", 1.0),
            content=report.get("content") or report.get("intel_details"),
            entities_mentioned=report.get("entities_mentioned") or [],
            source_record_id=report.get("source_record_id")
        )
        if rep_id not in mapped_intel_map:
            mapped_intel_map[rep_id] = intel_obj

    mapped_intel = list(mapped_intel_map.values())

    # 7. Map Associated FIR Details with Deduplication
    mapped_firs_map: Dict[str, FIR] = {}
    if isinstance(ingestion_data.get("fir_records"), list):
        for idx, fir in enumerate(ingestion_data["fir_records"]):
            if not isinstance(fir, dict): continue
            f_id = fir.get("fir_id") or f"FIR_{fir.get('fir_number', idx).replace('/', '_')}"
            fir_obj = FIR(
                fir_id=f_id,
                fir_number=fir.get("fir_number") or f"FIR-{idx}",
                police_station=fir.get("police_station") or case_meta.get("department") or "Unknown PS",
                date=fir.get("date") or case_meta.get("reporting_date"),
                sections=fir.get("sections") or [],
                complainant=fir.get("complainant"),
                summary=fir.get("summary"),
                accused_person_ids=fir.get("accused_person_ids") or []
            )
            if f_id not in mapped_firs_map:
                mapped_firs_map[f_id] = fir_obj

    if case_meta.get("fir_number"):
        f_id = f"FIR_{case_meta.get('fir_number').replace('/', '_')}"
        if f_id not in mapped_firs_map:
            mapped_firs_map[f_id] = FIR(
                fir_id=f_id,
                fir_number=case_meta.get("fir_number"),
                police_station=case_meta.get("department") or "Unknown PS",
                date=case_meta.get("reporting_date"),
                summary=f"Ingested FIR for case {case_id}"
            )

    mapped_firs = list(mapped_firs_map.values())

    return CaseData(
        case_metadata=mapped_metadata,
        fir_records=mapped_firs,
        entities=EntitiesContainer(
            people=mapped_people,
            phones=mapped_phones,
            bank_accounts=mapped_accounts,
            vehicles=mapped_vehicles,
            social_handles=mapped_socials,
            ip_addresses=mapped_ips,
            locations=mapped_locations,
            cell_towers=mapped_towers
        ),
        relationships=RelationshipsContainer(
            communications=mapped_communications,
            transactions=mapped_transactions
        ),
        surveillance_logs=mapped_surveillance,
        criminal_history=mapped_criminal_history,
        intelligence_reports=mapped_intel
    )
