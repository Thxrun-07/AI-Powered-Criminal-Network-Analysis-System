"""
Evidence Relationship Engine.

Responsible for extracting and deriving evidence-backed typed relationships:
- (Person)-[:USES]->(Phone)
- (Person)-[:OWNS]->(BankAccount)
- (Person)-[:USES_VEHICLE]->(Vehicle)
- (Person)-[:SEEN_AT]->(Location)
- (Person)-[:INVOLVED_IN]->(Case)
- (Phone)-[:CALLED]->(Phone)
- (BankAccount)-[:TRANSFERRED_TO]->(BankAccount)
- (Person)-[:ASSOCIATED_WITH]->(Person)

Enforces the strict rule:
Do NOT create a Person -> Person relationship just because two people appear in the same FIR.
Relationships between persons are created ONLY when supported by actual evidence:
- communication (calls/messages between their used phones)
- financial transaction (transfers between their owned bank accounts)
- surveillance co-observation (observed together at the same location & time)
- explicit association in an intelligence report
- shared infrastructure (sharing a vehicle, phone, or IP address)
- investigator validation
"""
import itertools
from typing import Dict, Any, List, Optional, Tuple, Set
from collections import defaultdict

from backend.models.case_input import CaseData
from backend.models.relationship import (
    PersonUsesPhoneRecord,
    PersonOwnsAccountRecord,
    PersonUsesVehicleRecord,
    PersonSeenAtRecord,
    PersonInvolvedInCaseRecord,
    PersonAssociationRecord,
)
from backend.services.normalizer import normalize_phone, normalize_bank_account, normalize_vehicle


class EvidenceRelationshipEngine:
    """
    Derives evidence-backed relationships across entities with strict provenance tracking:
    confidence, source_evidence, first_seen, last_seen, frequency, and validation_status.
    """

    @classmethod
    def extract_all(cls, case_data: CaseData, now_iso: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extracts all 8 evidence-backed relationship groups for a given CaseData payload.
        """
        case_id = case_data.case_metadata.case_id

        # 1. Build lookup maps
        phone_to_persons: Dict[str, Set[str]] = defaultdict(set)
        account_to_persons: Dict[str, Set[str]] = defaultdict(set)
        vehicle_to_persons: Dict[str, Set[str]] = defaultdict(set)
        ip_to_persons: Dict[str, Set[str]] = defaultdict(set)

        # Map from explicit phones
        for ph in getattr(case_data.entities, "phones", []):
            p_num = getattr(ph, "number", None) or getattr(ph, "phone_number", None)
            if p_num:
                norm_p, _ = normalize_phone(p_num)
                key = norm_p or p_num
                if getattr(ph, "owner_person_id", None):
                    phone_to_persons[key].add(ph.owner_person_id)

        # Map from person phone numbers
        for p in getattr(case_data.entities, "people", []):
            p_id = p.person_id
            for p_num in getattr(p, "phone_numbers", []):
                norm_p, _ = normalize_phone(p_num)
                key = norm_p or p_num
                phone_to_persons[key].add(p_id)

        # Map from bank accounts
        for ba in getattr(case_data.entities, "bank_accounts", []):
            acc_num = ba.account_number
            if acc_num and getattr(ba, "owner_person_id", None):
                account_to_persons[acc_num].add(ba.owner_person_id)

        # Map from vehicles
        for v in getattr(case_data.entities, "vehicles", []):
            v_id = getattr(v, "vin", None) or getattr(v, "registration_number", None) or getattr(v, "license_plate", None)
            if v_id and getattr(v, "owner_person_id", None):
                vehicle_to_persons[v_id].add(v.owner_person_id)

        # Map from IP addresses
        for ip in getattr(case_data.entities, "ip_addresses", []):
            if ip.ip_address and getattr(ip, "owner_person_id", None):
                ip_to_persons[ip.ip_address].add(ip.owner_person_id)

        # Source evidence tags
        fir_evidence = [f.fir_number or f.fir_id for f in getattr(case_data, "fir_records", []) if (f.fir_number or f.fir_id)]
        if not fir_evidence and case_id:
            fir_evidence = [f"CASE:{case_id}"]

        # -------------------------------------------------------------
        # 1. (Person)-[:USES]->(Phone)
        # -------------------------------------------------------------
        person_uses_phone_rows: List[Dict[str, Any]] = []
        seen_pup: Set[Tuple[str, str]] = set()

        for ph in getattr(case_data.entities, "phones", []):
            p_num = getattr(ph, "number", None) or getattr(ph, "phone_number", None)
            norm_p, raw_p = normalize_phone(p_num)
            p_clean = norm_p or p_num
            if not p_clean:
                continue

            # Associated persons
            owners = set()
            if getattr(ph, "owner_person_id", None):
                owners.add(ph.owner_person_id)
            for p_id in phone_to_persons.get(p_clean, set()):
                owners.add(p_id)

            for owner_id in owners:
                if (owner_id, p_clean) in seen_pup:
                    continue
                seen_pup.add((owner_id, p_clean))

                evidence_tags = list(fir_evidence)
                if getattr(ph, "imei", None):
                    evidence_tags.append(f"IMEI:{ph.imei}")
                if getattr(ph, "carrier", None):
                    evidence_tags.append(f"CARRIER:{ph.carrier}")
                if getattr(ph, "raw_value", None):
                    evidence_tags.append(f"RAW:{ph.raw_value}")

                person_uses_phone_rows.append({
                    "person_id": owner_id,
                    "phone_number": p_clean,
                    "confidence": 0.94,
                    "source_evidence": evidence_tags,
                    "first_seen": getattr(ph, "created_at", None) or now_iso,
                    "last_seen": getattr(ph, "updated_at", None) or now_iso,
                    "frequency": 1,
                    "validation_status": "VALIDATED",
                })

        # -------------------------------------------------------------
        # 2. (Person)-[:OWNS]->(BankAccount)
        # -------------------------------------------------------------
        person_owns_account_rows: List[Dict[str, Any]] = []
        seen_poa: Set[Tuple[str, str]] = set()

        for ba in getattr(case_data.entities, "bank_accounts", []):
            acc_num = ba.account_number
            if not acc_num:
                continue

            owners = set()
            if getattr(ba, "owner_person_id", None):
                owners.add(ba.owner_person_id)
            for p_id in account_to_persons.get(acc_num, set()):
                owners.add(p_id)

            for owner_id in owners:
                if (owner_id, acc_num) in seen_poa:
                    continue
                seen_poa.add((owner_id, acc_num))

                evidence_tags = list(fir_evidence)
                if getattr(ba, "bank_name", None):
                    evidence_tags.append(f"BANK:{ba.bank_name}")
                if getattr(ba, "branch", None):
                    evidence_tags.append(f"BRANCH:{ba.branch}")
                if getattr(ba, "raw_value", None):
                    evidence_tags.append(f"RAW:{ba.raw_value}")

                person_owns_account_rows.append({
                    "person_id": owner_id,
                    "account_number": acc_num,
                    "confidence": 0.95,
                    "source_evidence": evidence_tags,
                    "first_seen": getattr(ba, "created_at", None) or now_iso,
                    "last_seen": getattr(ba, "updated_at", None) or now_iso,
                    "frequency": 1,
                    "validation_status": "VALIDATED",
                })

        # -------------------------------------------------------------
        # 3. (Person)-[:USES_VEHICLE]->(Vehicle)
        # -------------------------------------------------------------
        person_uses_vehicle_rows: List[Dict[str, Any]] = []
        seen_puv: Set[Tuple[str, str]] = set()

        for v in getattr(case_data.entities, "vehicles", []):
            v_key = getattr(v, "vin", None) or getattr(v, "registration_number", None) or getattr(v, "license_plate", None)
            if not v_key:
                continue

            owners = set()
            if getattr(v, "owner_person_id", None):
                owners.add(v.owner_person_id)
            for p_id in vehicle_to_persons.get(v_key, set()):
                owners.add(p_id)

            for owner_id in owners:
                if (owner_id, v_key) in seen_puv:
                    continue
                seen_puv.add((owner_id, v_key))

                evidence_tags = list(fir_evidence)
                if getattr(v, "make", None) or getattr(v, "model", None):
                    evidence_tags.append(f"MODEL:{v.make or ''} {v.model or ''}".strip())
                if getattr(v, "color", None):
                    evidence_tags.append(f"COLOR:{v.color}")
                if getattr(v, "raw_value", None):
                    evidence_tags.append(f"RAW:{v.raw_value}")

                person_uses_vehicle_rows.append({
                    "person_id": owner_id,
                    "vin": v_key,
                    "confidence": 0.92,
                    "source_evidence": evidence_tags,
                    "first_seen": getattr(v, "created_at", None) or now_iso,
                    "last_seen": getattr(v, "updated_at", None) or now_iso,
                    "frequency": 1,
                    "validation_status": "VALIDATED",
                })

        # -------------------------------------------------------------
        # 4. (Person)-[:SEEN_AT]->(Location)
        # -------------------------------------------------------------
        person_seen_at_rows: List[Dict[str, Any]] = []
        seen_psa: Dict[Tuple[str, str], Dict[str, Any]] = {}

        for s_log in getattr(case_data, "surveillance_logs", []):
            loc_id = s_log.location_id or f"LOC_{s_log.log_id}"
            t_stamp = s_log.timestamp or now_iso

            for p_id in getattr(s_log, "observed_person_ids", []):
                key = (p_id, loc_id)
                ev_tag = f"SURVEILLANCE:{s_log.log_id}"
                if s_log.evidence_ref:
                    ev_tag += f" (Ref:{s_log.evidence_ref})"
                if s_log.activity_description:
                    ev_tag += f" - {s_log.activity_description}"

                if key in seen_psa:
                    entry = seen_psa[key]
                    entry["frequency"] += 1
                    if t_stamp > entry["last_seen"]:
                        entry["last_seen"] = t_stamp
                    if t_stamp < entry["first_seen"]:
                        entry["first_seen"] = t_stamp
                    if ev_tag not in entry["source_evidence"]:
                        entry["source_evidence"].append(ev_tag)
                else:
                    seen_psa[key] = {
                        "person_id": p_id,
                        "location_id": loc_id,
                        "confidence": 0.90,
                        "source_evidence": [ev_tag],
                        "first_seen": t_stamp,
                        "last_seen": t_stamp,
                        "frequency": 1,
                        "validation_status": "VALIDATED",
                    }

        person_seen_at_rows = list(seen_psa.values())

        # -------------------------------------------------------------
        # 5. (Person)-[:INVOLVED_IN]->(Case)
        # -------------------------------------------------------------
        person_involved_case_rows: List[Dict[str, Any]] = []
        for p in getattr(case_data.entities, "people", []):
            role_str = p.roles[0] if getattr(p, "roles", None) else "SUSPECT"
            person_involved_case_rows.append({
                "person_id": p.person_id,
                "case_id": case_id,
                "role": role_str,
                "confidence": getattr(p, "confidence", None) or 0.95,
                "source_evidence": fir_evidence if fir_evidence else [f"CASE:{case_id}"],
                "first_seen": getattr(case_data.case_metadata, "reporting_date", None) or now_iso,
                "last_seen": now_iso,
                "frequency": 1,
                "validation_status": "VALIDATED",
            })

        # -------------------------------------------------------------
        # 6. (Person)-[:ASSOCIATED_WITH]->(Person)  [STRICT EVIDENCE RULE]
        # -------------------------------------------------------------
        person_associations: Dict[Tuple[str, str], Dict[str, Any]] = {}

        def record_association(
            p1: str,
            p2: str,
            assoc_type: str,
            evidence: str,
            conf: float,
            t_stamp: Optional[str] = None
        ) -> None:
            if not p1 or not p2 or p1 == p2:
                return
            # Standardize undirected order so (p1, p2) == (p2, p1)
            pair_key = tuple(sorted([p1, p2]))
            src, tgt = pair_key
            timestamp = t_stamp or now_iso

            if pair_key in person_associations:
                entry = person_associations[pair_key]
                entry["frequency"] += 1
                if conf > entry["confidence"]:
                    entry["confidence"] = conf
                if timestamp > entry["last_seen"]:
                    entry["last_seen"] = timestamp
                if timestamp < entry["first_seen"]:
                    entry["first_seen"] = timestamp
                if evidence not in entry["source_evidence"]:
                    entry["source_evidence"].append(evidence)
                if assoc_type not in entry["association_types"]:
                    entry["association_types"].append(assoc_type)
            else:
                person_associations[pair_key] = {
                    "source_person_id": src,
                    "target_person_id": tgt,
                    "association_type": assoc_type,
                    "association_types": [assoc_type],
                    "confidence": conf,
                    "source_evidence": [evidence],
                    "first_seen": timestamp,
                    "last_seen": timestamp,
                    "frequency": 1,
                    "validation_status": "VALIDATED",
                }

        # 6a. Communication Evidence (calls / messages)
        for comm in getattr(case_data.relationships, "communications", []):
            norm_src, _ = normalize_phone(comm.source_phone)
            norm_dst, _ = normalize_phone(comm.target_phone)
            p_src_list = phone_to_persons.get(norm_src or comm.source_phone, set())
            p_dst_list = phone_to_persons.get(norm_dst or comm.target_phone, set())

            for p1 in p_src_list:
                for p2 in p_dst_list:
                    dur_str = f", dur={comm.duration_seconds}s" if comm.duration_seconds else ""
                    ev = f"COMMUNICATION: {comm.type} call from {comm.source_phone} to {comm.target_phone}{dur_str} (ID: {comm.call_id or comm.communication_id or 'CDR'})"
                    record_association(p1, p2, "COMMUNICATION", ev, 0.95, comm.timestamp)

        # 6b. Financial Transaction Evidence
        for tx in getattr(case_data.relationships, "transactions", []):
            norm_src, _ = normalize_bank_account(tx.source_account)
            norm_dst, _ = normalize_bank_account(tx.target_account)
            p_src_list = account_to_persons.get(norm_src or tx.source_account, set())
            p_dst_list = account_to_persons.get(norm_dst or tx.target_account, set())

            for p1 in p_src_list:
                for p2 in p_dst_list:
                    curr = getattr(tx, "currency", "INR") or "INR"
                    ev = f"FINANCIAL_TRANSACTION: Transfer {tx.transaction_id} of {curr} {tx.amount} from Acc {tx.source_account} to {tx.target_account}"
                    record_association(p1, p2, "FINANCIAL_FLOW", ev, 0.98, tx.timestamp)

        # 6c. Surveillance Co-Observation Evidence
        for s_log in getattr(case_data, "surveillance_logs", []):
            observed = list(set(getattr(s_log, "observed_person_ids", [])))
            if len(observed) >= 2:
                for p1, p2 in itertools.combinations(observed, 2):
                    loc_desc = s_log.location_name or s_log.location_id or "Field Location"
                    ev = f"SURVEILLANCE_CO_OBSERVATION: Co-observed together at {loc_desc} (Log: {s_log.log_id}, Ref: {s_log.evidence_ref or 'Visual Log'})"
                    record_association(p1, p2, "SURVEILLANCE_CO_OBSERVATION", ev, 0.90, s_log.timestamp)

        # 6d. Intelligence Report Co-Mention / Syndicate Link Evidence
        for ir in getattr(case_data, "intelligence_reports", []):
            mentioned = list(set(getattr(ir, "entities_mentioned", [])))
            # Filter to known people
            all_known_people = {p.person_id for p in getattr(case_data.entities, "people", [])}
            people_in_report = [m for m in mentioned if m in all_known_people]
            if len(people_in_report) >= 2:
                for p1, p2 in itertools.combinations(people_in_report, 2):
                    ev = f"INTELLIGENCE_REPORT: Jointly documented in intel report {ir.report_id} by {ir.source_agency}"
                    conf = min(0.92, float(getattr(ir, "reliability_score", 0.85) or 0.85))
                    record_association(p1, p2, "INTELLIGENCE_LINK", ev, conf, getattr(ir, "date", None))

        # 6e. Shared Infrastructure Evidence (Vehicle)
        for v_id, persons in vehicle_to_persons.items():
            if len(persons) >= 2:
                for p1, p2 in itertools.combinations(persons, 2):
                    ev = f"SHARED_INFRASTRUCTURE: Shared vehicle registration / use of {v_id}"
                    record_association(p1, p2, "SHARED_INFRASTRUCTURE", ev, 0.88, now_iso)

        # 6f. Shared Infrastructure Evidence (Phone)
        for ph_num, persons in phone_to_persons.items():
            if len(persons) >= 2:
                for p1, p2 in itertools.combinations(persons, 2):
                    ev = f"SHARED_INFRASTRUCTURE: Co-usage of phone number {ph_num}"
                    record_association(p1, p2, "SHARED_INFRASTRUCTURE", ev, 0.92, now_iso)

        # 6g. Shared Infrastructure Evidence (IP Address)
        for ip_addr, persons in ip_to_persons.items():
            if len(persons) >= 2:
                for p1, p2 in itertools.combinations(persons, 2):
                    ev = f"SHARED_INFRASTRUCTURE: Access from shared IP address {ip_addr}"
                    record_association(p1, p2, "SHARED_INFRASTRUCTURE", ev, 0.82, now_iso)

        person_association_rows = list(person_associations.values())

        return {
            "person_uses_phone": person_uses_phone_rows,
            "person_owns_account": person_owns_account_rows,
            "person_uses_vehicle": person_uses_vehicle_rows,
            "person_seen_at": person_seen_at_rows,
            "person_involved_case": person_involved_case_rows,
            "person_associated_with": person_association_rows,
        }
