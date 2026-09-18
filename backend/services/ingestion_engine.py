import re
import csv
import json
import os
import io
from typing import List, Dict, Tuple, Any, Optional
from backend.logging_config import logger
from backend.models.ingestion_models import (
    ConsolidatedCaseData, CaseMetadata, Entities, Relationships,
    PersonEntity, PhoneEntity, BankAccountEntity, VehicleEntity, SocialHandleEntity,
    CommunicationRelationship, TransactionRelationship,
    SurveillanceLog, CriminalHistory, IntelligenceReport
)

from backend.models.case_input import CaseData


try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False
NON_PERSON_WORDS = {
    "account", "accounts", "emptied", "within", "hours", "hour", "day", "days",
    "money", "cash", "fund", "funds", "transfer", "transferred", "withdrawal", "withdrawn",
    "closed", "opened", "created", "deleted", "escaped", "switched", "received", "sent",
    "logged", "observed", "accessed", "cleared", "scammed", "blocked", "refunded",
    "pending", "failed", "success", "completed", "processing", "vehicle", "phone",
    "device", "card", "bank", "system", "page", "log", "details", "description",
    "summary", "note", "notes", "remark", "remarks", "comment", "comments", "status",
    "evidence", "activity", "event", "narrative", "reason", "observation", "text",
    "message", "unknown", "unmapped", "amount", "transaction", "balance", "total",
    "unknown person", "n/a", "none", "null", "undefined", "user", "users"
}


def is_valid_person_name(name: Optional[str]) -> bool:
    if not name or not isinstance(name, str):
        return False
    clean = name.strip()
    if not clean:
        return False

    tokens = [w.lower() for w in re.findall(r"\b[a-zA-Z0-9_]+\b", clean)]
    if not tokens:
        return False

    for token in tokens:
        if token in NON_PERSON_WORDS:
            return False

    if len(clean) > 50:
        return False

    if re.search(r"[0-9!@#$%^&*()_=+\[\]{};:\",<>?/\\]", clean):
        return False

    return True


class CaseIngestionEngine:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        self.reset()

    def reset(self):
        self.case_metadata = CaseMetadata()
        self.people_by_id: Dict[str, PersonEntity] = {}
        self.people_by_name: Dict[str, PersonEntity] = {}
        self.phones_by_msisdn: Dict[str, PhoneEntity] = {}
        self.accounts_by_num: Dict[str, BankAccountEntity] = {}
        self.vehicles_by_plate: Dict[str, VehicleEntity] = {}
        self.social_by_handle: Dict[str, SocialHandleEntity] = {}
        self.communications: List[CommunicationRelationship] = []
        self.transactions: List[TransactionRelationship] = []
        self.surveillance_logs: List[SurveillanceLog] = []
        self.criminal_histories_by_person: Dict[str, CriminalHistory] = {}
        self.intel_reports: List[IntelligenceReport] = []
        self.person_id_counter = 701

    def parse_with_llm_api(self, content: str, api_key: str) -> bool:
        """Parses operational data using Gemini API structured output."""
        if not HAS_GENAI or not api_key:
            return False

        try:
            client = genai.Client(api_key=api_key)
            prompt = f"""
You are an expert law enforcement intelligence data analyst.
Extract all case metadata, entities (people, phones, bank accounts, vehicles, social handles, ip addresses, cell towers, locations), relationships (communications, transactions), surveillance logs, criminal history, and intelligence reports from the following case data.

CRITICAL DIRECTIVES & CONSTRAINTS:
1. STRICT NON-HALLUCINATION: Extract ONLY facts, entities, dates, and relationships explicitly present in the provided content. DO NOT invent, assume, or generate fictitious names, phone numbers, account numbers, FIR numbers, or mock transactions.
2. NO DUMMY DATA: If a field or entity type is absent in the document, return an empty list or null value. Do NOT insert placeholder names like 'Unknown Person', 'John Doe', or fake IDs.
3. ZERO REPETITION: Deduplicate all extracted entities and relationships. Merge duplicate mentions of the same person, phone, or bank account into a single record.

CASE OPERATIONAL DATA:
{content}
            """
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=CaseData,
                    temperature=0.1
                )
            )
            if response.text:
                data = json.loads(response.text)
                self.parse_json_data(data)
                return True
        except Exception as e:
            logger.warning(f"LLM API Extraction failed or API key invalid ({e}). Falling back to engine parser.")
            return False
        return False

    def _get_or_create_person(
        self,
        name: str,
        status: str = "Suspect",
        age: Optional[int] = None,
        person_id: Optional[str] = None,
        gender: Optional[str] = None,
        address: Optional[str] = None,
        occupation: Optional[str] = None,
        aliases: Optional[List[str]] = None,
        roles: Optional[List[str]] = None,
        phone_numbers: Optional[List[str]] = None
    ) -> Optional[PersonEntity]:
        clean_name = name.strip() if name else ""
        clean_name = re.sub(r"^(Shri|Smt|Ms\.|Mr\.|Dr\.|Coordinator|Command|Driver)\s+", "", clean_name, flags=re.IGNORECASE).strip()

        # NEVER convert arbitrary free-text into a Person when no explicit person_id is provided
        if not person_id and not is_valid_person_name(clean_name):
            return None

        if not clean_name:
            clean_name = f"Person {person_id}" if person_id else "Unknown Person"

        # 1. Identity Hierarchy: Explicit person_id is primary
        if person_id:
            if person_id in self.people_by_id:
                existing = self.people_by_id[person_id]
                if clean_name and clean_name != "Unknown Person":
                    existing.name = clean_name
                if status != "Suspect" and existing.status == "Suspect":
                    existing.status = status
                if age is not None and existing.age is None:
                    existing.age = age
                if gender and not existing.gender:
                    existing.gender = gender
                if address and not existing.address:
                    existing.address = address
                if occupation and not existing.occupation:
                    existing.occupation = occupation
                if aliases:
                    for a in aliases:
                        if a not in existing.aliases:
                            existing.aliases.append(a)
                if roles:
                    for r in roles:
                        if r not in existing.roles:
                            existing.roles.append(r)
                if phone_numbers:
                    for ph in phone_numbers:
                        if ph not in existing.phone_numbers:
                            existing.phone_numbers.append(ph)
                return existing
            else:
                p_roles = roles or ([status] if status else ["Suspect"])
                person = PersonEntity(
                    id=person_id,
                    name=clean_name,
                    status=status,
                    age=age,
                    gender=gender,
                    address=address,
                    occupation=occupation,
                    aliases=aliases or [],
                    roles=p_roles,
                    phone_numbers=phone_numbers or []
                )
                self.people_by_id[person_id] = person
                self.people_by_name[clean_name.lower()] = person
                return person

        # 2. Secondary fallback: Controlled name lookup only within local document scope when no ID is available
        if clean_name.lower() in self.people_by_name:
            existing = self.people_by_name[clean_name.lower()]
            if status != "Suspect" and existing.status == "Suspect":
                existing.status = status
            if age is not None and existing.age is None:
                existing.age = age
            if gender and not existing.gender:
                existing.gender = gender
            if address and not existing.address:
                existing.address = address
            if occupation and not existing.occupation:
                existing.occupation = occupation
            return existing

        # 3. Create new entity with generated ID
        generated_id = f"P_{self.person_id_counter}"
        self.person_id_counter += 1
        p_roles = roles or ([status] if status else ["Suspect"])
        person = PersonEntity(
            id=generated_id,
            name=clean_name,
            status=status,
            age=age,
            gender=gender,
            address=address,
            occupation=occupation,
            aliases=aliases or [],
            roles=p_roles,
            phone_numbers=phone_numbers or []
        )
        self.people_by_id[generated_id] = person
        self.people_by_name[clean_name.lower()] = person
        return person


    def parse_file(self, filename: str, content: str, api_key_override: Optional[str] = None) -> None:
        """Determines file type and routes to appropriate parser."""
        active_api_key = api_key_override or self.api_key
        
        if active_api_key:
            success = self.parse_with_llm_api(content, active_api_key)
            if success:
                return

        filename_lower = filename.lower()
        content_trim = content.strip()

        # 1. JSON file check
        if filename_lower.endswith(".json") or (content_trim.startswith("{") and content_trim.endswith("}")):
            try:
                data = json.loads(content_trim)
                self.parse_json_data(data)
                return
            except json.JSONDecodeError:
                pass

        # 2. CSV file check
        lines = [line for line in content_trim.splitlines() if line.strip()]
        if len(lines) > 0 and ("," in lines[0] or filename_lower.endswith(".csv")):
            header = lines[0].lower()
            if any(k in header for k in ["sender_account", "receiver_account", "amount", "transaction_id", "source_account"]):
                self.parse_bank_csv(lines)
                return
            elif any(k in header for k in ["caller_msisdn", "recipient_msisdn", "duration_sec", "celltower_id", "caller"]):
                self.parse_cdr_csv(lines)
                return
            elif filename_lower.endswith(".csv"):
                if any(k in header for k in ["account", "amount", "bank", "txn"]):
                    self.parse_bank_csv(lines)
                    return
                elif any(k in header for k in ["phone", "call", "msisdn", "tower"]):
                    self.parse_cdr_csv(lines)
                    return

        # 3. Unstructured text parser (FIRs, intel briefs, surveillance notes, criminal histories)
        self.parse_unstructured_text(content, filename_lower)

    def parse_json_data(self, data: Dict[str, Any]) -> None:
        """Parses a structured JSON payload directly matching or partially matching the model schema."""
        if "case_id" in data and data["case_id"]:
            self.case_metadata.case_id = str(data["case_id"])

        if "case_metadata" in data and isinstance(data["case_metadata"], dict):
            meta = data["case_metadata"]
            self.case_metadata = CaseMetadata(
                case_id=meta.get("case_id", self.case_metadata.case_id),
                fir_number=meta.get("fir_number", self.case_metadata.fir_number),
                department=meta.get("department", self.case_metadata.department),
                reporting_date=meta.get("reporting_date", self.case_metadata.reporting_date),
                crime_type=meta.get("crime_type", self.case_metadata.crime_type),
                assigned_officer=meta.get("assigned_officer", self.case_metadata.assigned_officer)
            )

        entities_dict = data.get("entities", {}) if isinstance(data.get("entities"), dict) else {}
        people_items = []
        if "people" in entities_dict and isinstance(entities_dict["people"], list):
            people_items.extend(entities_dict["people"])
        if "people" in data and isinstance(data["people"], list):
            people_items.extend(data["people"])
        if ("name" in data or "person_id" in data) and "transactions" not in data and "description" not in data:
            people_items.append(data)

        for p in people_items:
            if not isinstance(p, dict):
                continue
            pid = p.get("person_id") or p.get("id")
            name = p.get("name", "")
            if not pid and not is_valid_person_name(name):
                continue
            role_val = p.get("status") or p.get("role")
            if isinstance(role_val, list) and role_val:
                role_val = role_val[0]
            status = str(role_val) if role_val else "Suspect"
            self._get_or_create_person(
                name=name,
                status=status,
                age=p.get("age"),
                person_id=pid,
                gender=p.get("gender"),
                address=p.get("address"),
                occupation=p.get("occupation"),
                aliases=p.get("aliases"),
                roles=p.get("roles") or ([status] if status else None),
                phone_numbers=p.get("phone_numbers")
            )

        phones_items = entities_dict.get("phones", []) or data.get("phones", [])
        if isinstance(phones_items, list):
            for ph in phones_items:
                if not isinstance(ph, dict): continue
                msisdn = ph.get("msisdn") or ph.get("phone_number")
                if msisdn:
                    self.phones_by_msisdn[msisdn] = PhoneEntity(
                        msisdn=msisdn,
                        owner_id=ph.get("owner_id") or ph.get("owner_person_id"),
                        provider=ph.get("provider") or ph.get("carrier", "Cellular Provider")
                    )

        accounts_items = entities_dict.get("bank_accounts", []) or data.get("bank_accounts", [])
        if isinstance(accounts_items, list):
            for acc in accounts_items:
                if not isinstance(acc, dict): continue
                num = acc.get("account_number")
                if num:
                    self.accounts_by_num[num] = BankAccountEntity(
                        account_number=num,
                        bank_name=acc.get("bank_name", "Bank Network"),
                        owner_id=acc.get("owner_id") or acc.get("owner_person_id")
                    )

        vehicles_items = entities_dict.get("vehicles", []) or data.get("vehicles", [])
        if isinstance(vehicles_items, list):
            for veh in vehicles_items:
                if not isinstance(veh, dict): continue
                plate = veh.get("plate_number") or veh.get("license_plate") or veh.get("vin")
                if plate:
                    self.vehicles_by_plate[plate] = VehicleEntity(
                        plate_number=plate,
                        owner_id=veh.get("owner_id") or veh.get("owner_person_id"),
                        model=veh.get("model", "Vehicle")
                    )

        social_items = entities_dict.get("social_handles", []) or data.get("social_handles", [])
        if isinstance(social_items, list):
            for sh in social_items:
                if not isinstance(sh, dict): continue
                handle = sh.get("handle")
                if handle:
                    self.social_by_handle[handle] = SocialHandleEntity(
                        platform=sh.get("platform", "Instagram"),
                        handle=handle,
                        owner_id=sh.get("owner_id") or sh.get("owner_person_id"),
                        linked_ip=sh.get("linked_ip")
                    )

        rel = data.get("relationships", {}) if isinstance(data.get("relationships"), dict) else {}
        comms_items = rel.get("communications", []) or data.get("communications", [])
        if isinstance(comms_items, list):
            for c in comms_items:
                if not isinstance(c, dict): continue
                caller = c.get("caller") or c.get("source_phone")
                recipient = c.get("recipient") or c.get("target_phone")
                if caller and recipient:
                    dur = c.get("duration_sec") if c.get("duration_sec") is not None else c.get("duration_seconds", 0)
                    self.communications.append(CommunicationRelationship(
                        caller=caller,
                        recipient=recipient,
                        timestamp=c.get("timestamp"),
                        duration_sec=int(dur),
                        cell_tower=c.get("cell_tower")
                    ))

        txns_items = []
        if "transactions" in rel and isinstance(rel["transactions"], list):
            txns_items.extend(rel["transactions"])
        if "transactions" in data and isinstance(data["transactions"], list):
            txns_items.extend(data["transactions"])
        if "transaction" in data and isinstance(data["transaction"], dict):
            txns_items.append(data["transaction"])

        for idx, t in enumerate(txns_items):
            if not isinstance(t, dict): continue
            sender = t.get("sender") or t.get("source_account") or f"ACC_SRC_{idx + 1}"
            receiver = t.get("receiver") or t.get("target_account") or f"ACC_DST_{idx + 1}"
            amt = t.get("amount_inr") if t.get("amount_inr") is not None else t.get("amount", 0.0)
            txn_id = t.get("txn_id") or t.get("transaction_id") or f"TXN_{len(self.transactions) + 1}"
            desc = t.get("description") or t.get("transaction_description") or t.get("remarks")
            self.transactions.append(TransactionRelationship(
                sender=sender,
                receiver=receiver,
                amount_inr=float(amt),
                timestamp=t.get("timestamp"),
                txn_id=txn_id,
                description=desc
            ))

        for s in data.get("surveillance_logs", []):
            self.surveillance_logs.append(SurveillanceLog(
                log_id=s.get("log_id"),
                timestamp=s.get("timestamp"),
                location_id=s.get("location_id"),
                location=s.get("location") or s.get("location_name"),
                location_name=s.get("location_name") or s.get("location"),
                latitude=s.get("latitude"),
                longitude=s.get("longitude"),
                observation=s.get("observation") or s.get("activity_description"),
                activity_description=s.get("activity_description") or s.get("observation"),
                observed_person_ids=s.get("observed_person_ids", []),
                observed_vehicle_vins=s.get("observed_vehicle_vins", []),
                observed_phone_numbers=s.get("observed_phone_numbers", []),
                evidence_ref=s.get("evidence_ref"),
                source_record_id=s.get("source_record_id")
            ))


        for ch in data.get("criminal_history", []):
            p_id = ch["person_id"]
            priors = ch.get("prior_cases", [])
            status = ch.get("status", "Repeat Offender")
            if p_id in self.criminal_histories_by_person:
                existing = self.criminal_histories_by_person[p_id]
                for pr in priors:
                    if pr not in existing.prior_cases:
                        existing.prior_cases.append(pr)
            else:
                self.criminal_histories_by_person[p_id] = CriminalHistory(
                    person_id=p_id,
                    prior_cases=priors,
                    status=status
                )

        for ir in data.get("intelligence_reports", []):
            self.intel_reports.append(IntelligenceReport(
                date=ir["date"],
                source=ir["source"],
                intel_details=ir["intel_details"]
            ))

    def parse_bank_csv(self, lines: List[str]) -> None:
        reader = csv.DictReader(lines)
        row_idx = 0
        for row in reader:
            row_idx += 1
            def get_val(*keys):
                for k in keys:
                    for row_k, v in row.items():
                        if row_k and row_k.strip().lower() == k.lower():
                            return (v or "").strip()
                return ""

            sender_acc = get_val("Sender_Account", "source_account", "sender_account_no", "sender_acc", "from_account", "sender")
            sender_name = get_val("Sender_Name", "source_name", "from_name", "sender_owner")
            receiver_acc = get_val("Receiver_Account", "target_account", "receiver_account_no", "receiver_acc", "to_account", "receiver")
            receiver_name = get_val("Receiver_Name", "target_name", "to_name", "receiver_owner")
            amount_str = get_val("Amount_INR", "amount", "amt", "value") or "0"
            timestamp = get_val("Timestamp", "time", "date", "datetime", "txn_date") or "2026-01-01 00:00:00"
            txn_id = get_val("Transaction_ID", "txn_id", "id", "ref_no", "reference_id") or f"TXN_{row_idx}"

            if not sender_acc or not receiver_acc:
                continue

            try:
                amount = float(amount_str)
            except ValueError:
                amount = 0.0

            sender_person = None
            if sender_name and not sender_name.startswith("User_") and is_valid_person_name(sender_name):
                sender_person = self._get_or_create_person(sender_name, "Suspect")

            if sender_acc and sender_acc not in self.accounts_by_num:
                self.accounts_by_num[sender_acc] = BankAccountEntity(
                    account_number=sender_acc,
                    bank_name="State Bank of India",
                    owner_id=sender_person.id if sender_person else None
                )

            receiver_person = None
            if receiver_name and not receiver_name.startswith("User_") and is_valid_person_name(receiver_name):
                receiver_person = self._get_or_create_person(receiver_name, "Suspect")

            if receiver_acc and receiver_acc not in self.accounts_by_num:
                self.accounts_by_num[receiver_acc] = BankAccountEntity(
                    account_number=receiver_acc,
                    bank_name="State Bank of India",
                    owner_id=receiver_person.id if receiver_person else None
                )

            self.transactions.append(TransactionRelationship(
                sender=sender_acc,
                receiver=receiver_acc,
                amount_inr=amount,
                timestamp=timestamp,
                txn_id=txn_id
            ))

    def parse_cdr_csv(self, lines: List[str]) -> None:
        reader = csv.DictReader(lines)
        for row in reader:
            def get_val(*keys):
                for k in keys:
                    for row_k, v in row.items():
                        if row_k and row_k.strip().lower() == k.lower():
                            return (v or "").strip()
                return ""

            caller = get_val("Caller_MSISDN", "source_phone", "caller", "calling_number", "caller_number", "from_msisdn")
            recipient = get_val("Recipient_MSISDN", "target_phone", "recipient", "callee", "called_number", "to_msisdn")
            timestamp = get_val("Timestamp", "time", "date", "datetime", "call_date") or "2026-01-01 00:00:00"
            duration_str = get_val("Duration_Sec", "duration", "duration_seconds", "call_duration") or "0"
            cell_tower = get_val("CellTower_ID", "cell_tower", "tower_id", "tower") or None

            if not caller or not recipient:
                continue

            try:
                duration = int(duration_str)
            except ValueError:
                duration = 0

            # Add to raw communications relationship log
            self.communications.append(CommunicationRelationship(
                caller=caller,
                recipient=recipient,
                timestamp=timestamp,
                duration_sec=duration,
                cell_tower=cell_tower
            ))

            # Register phone entities for all call record MSISDNs
            for msisdn in [caller, recipient]:
                if msisdn and msisdn not in self.phones_by_msisdn:
                    provider = "Reliance Jio" if msisdn.startswith("99999") else "Cellular Provider"
                    self.phones_by_msisdn[msisdn] = PhoneEntity(msisdn=msisdn, provider=provider)


    def parse_unstructured_text(self, text: str, filename: str = "") -> None:
        lines = text.splitlines()
        csv_bank_lines = []
        csv_cdr_lines = []
        in_bank = False
        in_cdr = False

        for line in lines:
            if "sender_account" in line.lower():
                in_bank = True
                in_cdr = False
                csv_bank_lines.append(line)
                continue
            elif "caller_msisdn" in line.lower():
                in_cdr = True
                in_bank = False
                csv_cdr_lines.append(line)
                continue
            
            if in_bank:
                if "," in line and len(line.split(",")) >= 5:
                    csv_bank_lines.append(line)
                else:
                    in_bank = False

            if in_cdr:
                if "," in line and len(line.split(",")) >= 4:
                    csv_cdr_lines.append(line)
                else:
                    in_cdr = False

        if len(csv_bank_lines) > 1:
            self.parse_bank_csv(csv_bank_lines)
        if len(csv_cdr_lines) > 1:
            self.parse_cdr_csv(csv_cdr_lines)

        # 1. FIR Number & Metadata
        fir_match = re.search(r"\bFIR\s*(?:No|NO|#)?[:\s]*([0-9]{3,4}/[0-9]{4}|FIR/[0-9]+/[0-9]{4}|[0-9]{4}/[0-9]{4})", text, re.IGNORECASE)
        if fir_match:
            self.case_metadata.fir_number = fir_match.group(1).strip()
            if not self.case_metadata.case_id:
                self.case_metadata.case_id = f"CASE_{self.case_metadata.fir_number.replace('/', '_')}"

        dept_match = re.search(r"(?:Police Station|PS|Department)[:\s]*([^\n|]+)", text, re.IGNORECASE)
        if dept_match:
            self.case_metadata.department = dept_match.group(1).strip()

        date_match = re.search(r"\b(202[0-9]-[0-1][0-9]-[0-3][0-9])\b", text)
        if date_match:
            self.case_metadata.reporting_date = date_match.group(1)

        officer_match = re.search(r"(?:Recorded by|Assigned Officer)[:\s]+([^|\n\r]+)", text, re.IGNORECASE)
        if officer_match:
            self.case_metadata.assigned_officer = officer_match.group(1).strip()

        # 2. Extract People dynamically from text
        # 2a. Direct structured person blocks:
        # - Name: Suresh Kumar
        # - Local record ID: P-001-REF01
        # - Contact observed/recorded: 9801017001
        structured_person_blocks = re.findall(
            r"-\s*Name[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)(?:\s*\n\s*-\s*Local record ID[:\s]+([A-Za-z0-9_\-]+))?(?:\s*\n\s*-\s*Contact[^\n]*?[:\s]+(\d+))?",
            text, re.IGNORECASE
        )
        for name_str, record_id, phone_str in structured_person_blocks:
            c_name = name_str.strip()
            if is_valid_person_name(c_name):
                pid = record_id.strip() if record_id else None
                person = self._get_or_create_person(c_name, "Complainant", person_id=pid)
                if person and phone_str:
                    msisdn = phone_str.strip()
                    if msisdn not in self.phones_by_msisdn:
                        self.phones_by_msisdn[msisdn] = PhoneEntity(msisdn=msisdn, owner_id=person.id, provider="Cellular Provider")
                    else:
                        self.phones_by_msisdn[msisdn].owner_id = person.id

        # 2b. Complainant / Informant: Suresh Kumar
        complainant_matches = re.findall(
            r"(?:Complainant\s*/\s*Informant|Complainant|Informant)[:\s]+(?:Mr\.|Ms\.|Shri|Smt\.)?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
            text, re.IGNORECASE
        )
        for c_name in complainant_matches:
            c_name_clean = c_name.strip()
            if is_valid_person_name(c_name_clean):
                self._get_or_create_person(c_name_clean, "Complainant")

        # 2c. Observation Subject: Suresh Kumar (local record P-001-REF01)
        obs_subject_matches = re.findall(
            r"Observation Subject[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)(?:\s*\([^)]*?(P-[A-Za-z0-9_\-]+)\))?",
            text, re.IGNORECASE
        )
        for sub_name, rec_id in obs_subject_matches:
            c_name_clean = sub_name.strip()
            if is_valid_person_name(c_name_clean):
                pid = rec_id.strip() if rec_id else None
                self._get_or_create_person(c_name_clean, "Suspect", person_id=pid)

        # 2d. General Name + Local Record ID pattern
        general_id_matches = re.findall(
            r"([A-Z][a-z]+\s+[A-Z][a-z]+)\s*\([^)]*?(?:local record|record ID|person_id)[:\s]*([P\-[A-Za-z0-9_\-]+)\)",
            text, re.IGNORECASE
        )
        for g_name, g_id in general_id_matches:
            g_name_clean = g_name.strip()
            if is_valid_person_name(g_name_clean):
                self._get_or_create_person(g_name_clean, "Person of Interest", person_id=g_id.strip())

        victim_match = re.search(r"(?:Victim|daughter of the complainant)[,\s:]+(?:Ms\.\s*)?([A-Z][a-z]+\s+[A-Z][a-z]+)(?:[,\s]+(?:age|Mobile)[:\s]*(\d+))?", text, re.IGNORECASE)
        if victim_match:
            v_name = victim_match.group(1).strip()
            if is_valid_person_name(v_name):
                v_age = int(victim_match.group(2)) if victim_match.group(2) else None
                victim_p = self._get_or_create_person(v_name, "Victim", v_age)
                if victim_p:
                    v_phone_match = re.search(rf"{re.escape(v_name)}[^\n]*?(?:Mobile|Phone)[:\s]*(\d{{10}})", text, re.IGNORECASE)
                    if v_phone_match:
                        msisdn = v_phone_match.group(1)
                        self.phones_by_msisdn[msisdn] = PhoneEntity(msisdn=msisdn, owner_id=victim_p.id, provider="Bharti Airtel")

        person_matches = re.findall(
            r"\b(Suspect|Accused|Complainant|Victim|Witness)[:\s]+(?:Mr\.|Ms\.|Shri|Smt\.)?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)(?:[,\s]+(?:age|aged)[:\s]*(\d+))?",
            text, re.IGNORECASE
        )
        for role_str, name_str, age_str in person_matches:
            c_name = name_str.strip()
            if is_valid_person_name(c_name):
                role_title = role_str.capitalize()
                p_age = int(age_str) if age_str else None

                dob_m = re.search(rf"{re.escape(c_name)}[^\n]*?(?:DOB|Date of Birth)[:\s]*(\d{{4}}-\d{{2}}-\d{{2}})", text, re.IGNORECASE)
                dob_val = dob_m.group(1) if dob_m else None
                if not dob_val:
                    gen_dob = re.search(r"(?:DOB|Date of Birth)[:\s]*(\d{4}-\d{2}-\d{2})", text, re.IGNORECASE)
                    dob_val = gen_dob.group(1) if gen_dob else None

                alias_m = re.search(rf"{re.escape(c_name)}[^\n]*?(?:alias|a\.k\.a\.)[:\s]*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", text, re.IGNORECASE)
                alias_list = [alias_m.group(1).strip()] if alias_m else []

                father_m = re.search(rf"{re.escape(c_name)}[^\n]*?(?:father|father_name|S/o)[:\s]*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)", text, re.IGNORECASE)
                if not father_m:
                    father_m = re.search(r"(?:father|father_name|S/o)[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)", text, re.IGNORECASE)
                father_val = father_m.group(1).strip() if father_m else None

                person = self._get_or_create_person(
                    c_name,
                    role_title,
                    p_age,
                    aliases=alias_list if alias_list else None
                )
                if person:
                    if dob_val and not person.dob:
                        person.dob = dob_val
                    if father_val and "father_name" not in person.properties:
                        person.properties["father_name"] = father_val
                    phone_m = re.search(rf"{re.escape(c_name)}[^\n]*?(\d{{10}})", text, re.IGNORECASE)
                    if phone_m:
                        s_phone = phone_m.group(1)
                        self.phones_by_msisdn[s_phone] = PhoneEntity(msisdn=s_phone, owner_id=person.id, provider="Cellular Provider")
                    acc_m = re.search(rf"{re.escape(c_name)}[^\n]*?(ACC\d+)", text, re.IGNORECASE)
                    if acc_m:
                        s_acc = acc_m.group(1)
                        self.accounts_by_num[s_acc] = BankAccountEntity(account_number=s_acc, bank_name="Bank Network", owner_id=person.id)

        # 3. Vehicle Details
        veh_match = re.search(r"([A-Z]{2}-\d[A-Z]+-[A-Z]+-\d{4}|\b[A-Z]{2}-\d{2}-[A-Z]+-\d{4}\b)[^\n]*?(Scorpio|Mahindra|SUV|Car|Vehicle)?", text, re.IGNORECASE)
        if veh_match:
            plate = veh_match.group(1).strip()
            model = veh_match.group(2) if veh_match.group(2) else "Vehicle"
            owner_id = list(self.people_by_id.keys())[0] if self.people_by_id else None
            self.vehicles_by_plate[plate] = VehicleEntity(plate_number=plate, owner_id=owner_id, model=model)

        # 4. Social Media Handles & IP
        social_match = re.search(r"(@[a-zA-Z0-9_]+)[^\n]*?(Instagram|Twitter|Facebook)?[^\n]*?(?:IP[^\d]*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}))?", text, re.IGNORECASE)
        if social_match:
            handle = social_match.group(1).strip()
            platform = social_match.group(2) if social_match.group(2) else "Instagram"
            ip = social_match.group(3) if social_match.group(3) else None
            owner_id = list(self.people_by_id.keys())[0] if self.people_by_id else None
            self.social_by_handle[handle] = SocialHandleEntity(platform=platform, handle=handle, owner_id=owner_id, linked_ip=ip)

        # 5. Criminal History / Prior Arrest Records Extraction
        fir_patterns = re.findall(r"((?:FIR\s*|FIR/)[0-9]+/[0-9]{4})", text, re.IGNORECASE)
        for fir_no in fir_patterns:
            clean_fir = fir_no.upper().replace(" ", "")
            if not clean_fir.startswith("FIR/"):
                clean_fir = "FIR/" + clean_fir.replace("FIR", "")

            # Ignore the main case FIR number
            if self.case_metadata.fir_number and (self.case_metadata.fir_number in clean_fir or clean_fir.endswith(self.case_metadata.fir_number)):
                continue

            # Link to first extracted suspect or person
            target_p = list(self.people_by_id.values())[0] if self.people_by_id else None
            if target_p:
                p_id = target_p.id
                if p_id in self.criminal_histories_by_person:
                    if clean_fir not in self.criminal_histories_by_person[p_id].prior_cases:
                        self.criminal_histories_by_person[p_id].prior_cases.append(clean_fir)
                else:
                    self.criminal_histories_by_person[p_id] = CriminalHistory(
                        person_id=p_id,
                        prior_cases=[clean_fir],
                        status="Repeat Offender"
                    )

        # Additional Criminal History regex for person name + status
        priors = re.findall(r"([A-Z][a-z]+\s+[A-Z][a-z]+)[^\n]*?(?:prior|arrest|extortion|charged|convict)[^\n]*?((?:FIR\s*|FIR/)?\d+/\d{4})?", text, re.IGNORECASE)
        for person_name, fir_no in priors:
            clean_name = re.sub(r"^(Shri|Smt|Ms\.|Mr\.|Dr\.|Coordinator|Command|Driver)\s+", "", person_name, flags=re.IGNORECASE).strip()
            if clean_name in self.people_by_name:
                p_id = self.people_by_name[clean_name].id
                cases = []
                if fir_no:
                    cf = fir_no.upper().replace(" ", "")
                    if not cf.startswith("FIR/"): cf = "FIR/" + cf.replace("FIR", "")
                    cases.append(cf)

                if p_id in self.criminal_histories_by_person:
                    for c in cases:
                        if c not in self.criminal_histories_by_person[p_id].prior_cases:
                            self.criminal_histories_by_person[p_id].prior_cases.append(c)
                elif cases:
                    self.criminal_histories_by_person[p_id] = CriminalHistory(
                        person_id=p_id,
                        prior_cases=cases,
                        status="Repeat Offender"
                    )

        # 6. Intelligence Reports Extraction
        intel_matches = re.findall(r"((?:Source\s+)?Informant-[A-Z0-9]+|Field Agent|Source\s+[A-Za-z0-9_-]+)[:\s]*([^\n]+)", text, re.IGNORECASE)
        for src, details in intel_matches:
            clean_src = src.strip()
            clean_details = details.strip()
            clean_details = re.sub(r"^(states|indicates|reports|details)[:\s]*", "", clean_details, flags=re.IGNORECASE).strip()
            self.intel_reports.append(IntelligenceReport(
                date=self.case_metadata.reporting_date or "",
                source=clean_src,
                intel_details=clean_details
            ))

        # Fallback if filename or content contains intelligence keyword
        if ("intel" in filename or "informant" in text.lower()) and not self.intel_reports:
            for line in lines:
                if "informant" in line.lower() or "source" in line.lower() or "intel" in line.lower():
                    self.intel_reports.append(IntelligenceReport(
                        date=self.case_metadata.reporting_date or "",
                        source="Informant-X",
                        intel_details=line.strip()
                    ))

        # 7. Surveillance Logs
        surv_matches = re.findall(r"(\d{2}:\d{2}(?::\d{2})?)\s*-\s*([^\n]+)", text)
        for ts, obs in surv_matches:
            loc_match = re.search(r"(Lajpat Nagar|Noida Sector \d+|Gurugram|Delhi)", obs, re.IGNORECASE)
            loc = loc_match.group(1) if loc_match else "Delhi NCR"
            time_str = ts if len(ts.split(":")) == 3 else f"{ts}:00"
            stamp = f"{self.case_metadata.reporting_date} {time_str}" if self.case_metadata.reporting_date else time_str
            self.surveillance_logs.append(SurveillanceLog(
                timestamp=stamp,
                location=loc,
                observation=obs.strip()
            ))

    def consolidate(self) -> ConsolidatedCaseData:
        return ConsolidatedCaseData(
            case_metadata=self.case_metadata,
            entities=Entities(
                people=list(self.people_by_id.values()),
                phones=list(self.phones_by_msisdn.values()),
                bank_accounts=list(self.accounts_by_num.values()),
                vehicles=list(self.vehicles_by_plate.values()),
                social_handles=list(self.social_by_handle.values())
            ),

            relationships=Relationships(
                communications=self.communications,
                transactions=self.transactions
            ),
            surveillance_logs=self.surveillance_logs,
            criminal_history=list(self.criminal_histories_by_person.values()),
            intelligence_reports=self.intel_reports
        )


