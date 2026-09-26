"""
Shared Neo4j write definitions for the case graph.

This module is the single source of truth for every MERGE / write statement the
bulk ingestion path executes, plus the row-builder helpers that turn the
Pydantic ingestion models into the parameter rows those statements expect
(including all fallback / derivation logic such as ``call_id`` defaults).

Any other write path (for example an incremental event processor) MUST import
these definitions instead of re-implementing them, so that there is never a
second, subtly different implementation of the same MERGE semantics.

Conventions
-----------
* Batched statements start with ``UNWIND $rows AS row``; per-row values are
  referenced as ``row.<field>`` and the per-call values as ``$case_id`` /
  ``$now``.
* Statements that end with ``RETURN (<node>.created_at = $now) AS was_created``
  report, per input row, whether the primary node was created during the
  current ingestion call (the same convention Phase 1 introduced).
* ``run_batch`` issues no query at all for an empty row list.
"""
from typing import Any, Dict, List

from neo4j import Session

from backend.models.entity import (
    FIR, BankAccount, CellTower, IPAddress, Location, Person, Phone,
    SocialHandle, SourceRecord, Vehicle,
)
from backend.models.relationship import (
    CommunicationRecord, CriminalHistoryRecord, IntelligenceReportRecord,
    SurveillanceLogRecord, TransactionRecord,
)
from backend.models.case_input import CaseMetadata


# ---------------------------------------------------------------------------
# MERGE keys (label -> property). Every MERGE statement below keys on exactly
# these properties; detectors and the event path anchor on the same values.
# ---------------------------------------------------------------------------

MERGE_KEYS: Dict[str, str] = {
    "Case": "case_id",
    "SourceRecord": "source_record_id",
    "FIR": "fir_id",
    "Person": "person_id",
    "Phone": "phone_number",
    "BankAccount": "account_number",
    "Vehicle": "vin",
    "SocialHandle": "handle_id",
    "IPAddress": "ip_address",
    "Location": "location_id",
    "CellTower": "cell_tower_id",
    "Transaction": "transaction_id",
    "PriorCase": "prior_case_id",
}


# ---------------------------------------------------------------------------
# Execution helper
# ---------------------------------------------------------------------------

def run_batch(session: Session, cypher: str, rows: List[Dict[str, Any]], common: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Execute one parameterized UNWIND batch and return its result rows.

    Keeping batching in one helper makes it harder to accidentally reintroduce
    per-entity Neo4j round trips while preserving the existing session API.
    """
    if not rows:
        return []
    params = dict(common)
    params["rows"] = rows
    return session.run(cypher, params).data()


# ---------------------------------------------------------------------------
# 1. Case
# ---------------------------------------------------------------------------

CASE_MERGE = """
        MERGE (c:Case {case_id: $case_id})
        ON CREATE SET
            c.case_name = $case_name,
            c.case_type = $case_type,
            c.status = $status,
            c.jurisdiction = $jurisdiction,
            c.lead_investigator = $lead_investigator,
            c.uploaded_by = $uploaded_by,
            c.created_date = $created_date,
            c.summary = $summary,
            c.tags = $tags,
            c.created_at = $now,
            c.updated_at = $now,
            c.case_ids = [$case_id]
        ON MATCH SET
            c.case_name = coalesce($case_name, c.case_name),
            c.case_type = coalesce($case_type, c.case_type),
            c.status = coalesce($status, c.status),
            c.jurisdiction = coalesce($jurisdiction, c.jurisdiction),
            c.lead_investigator = coalesce($lead_investigator, c.lead_investigator),
            c.uploaded_by = coalesce($uploaded_by, c.uploaded_by),
            c.summary = coalesce($summary, c.summary),
            c.updated_at = $now
        RETURN (c.created_at = $now) as was_created
        """

# Read-only guard used by write paths that do not carry case metadata (e.g. event batches):
# entity statements MATCH the Case node for INVOLVES edges, so it must exist before they run.
CASE_EXISTS_QUERY = """MATCH (c:Case {case_id: $case_id}) RETURN count(c) > 0 AS exists"""


def case_membership_query(label: str) -> str:
    """Read-only: for existing nodes of ``label`` keyed by MERGE_KEYS[label], report whether
    ``$case_id`` is already in ``case_ids``. Used before a write to detect case-join changes.
    ``label`` must be a key of MERGE_KEYS (never user input)."""
    key = MERGE_KEYS[label]
    return f"MATCH (n:{label}) WHERE n.{key} IN $keys RETURN n.{key} AS key, $case_id IN coalesce(n.case_ids, []) AS in_case"


def case_params(case_meta: CaseMetadata) -> Dict[str, Any]:
    """Parameters for CASE_MERGE (add ``now`` at call time)."""
    return {
        "case_id": case_meta.case_id,
        "case_name": case_meta.case_name,
        "case_type": case_meta.case_type,
        "status": case_meta.status,
        "jurisdiction": case_meta.jurisdiction,
        "lead_investigator": case_meta.lead_investigator,
        "uploaded_by": getattr(case_meta, "uploaded_by", None) or case_meta.lead_investigator,
        "created_date": case_meta.created_date,
        "summary": case_meta.summary,
        "tags": case_meta.tags
    }



# ---------------------------------------------------------------------------
# 2. Source records
# ---------------------------------------------------------------------------

SOURCE_RECORDS_MERGE = """
        UNWIND $rows AS row
        MERGE (sr:SourceRecord {source_record_id: row.source_record_id})
        ON CREATE SET
            sr.source_type = row.source_type, sr.record_type = row.record_type,
            sr.raw_reference = row.raw_reference, sr.ingested_at = $now,
            sr.created_at = $now, sr.updated_at = $now, sr.case_ids = [$case_id]
        ON MATCH SET
            sr.updated_at = $now,
            sr.case_ids = CASE WHEN $case_id IN sr.case_ids THEN sr.case_ids ELSE sr.case_ids + $case_id END
        WITH sr
        MATCH (c:Case {case_id: $case_id})
        MERGE (c)-[:INVOLVES]->(sr)
        RETURN (sr.created_at = $now) AS was_created
        """


def source_record_row(sr: SourceRecord) -> Dict[str, Any]:
    return {
        "source_record_id": sr.source_record_id, "source_type": sr.source_type,
        "record_type": sr.record_type, "raw_reference": sr.raw_reference
    }


# ---------------------------------------------------------------------------
# 3. FIR (single-record statements)
# ---------------------------------------------------------------------------

FIR_MERGE = """
            MERGE (f:FIR {fir_id: $fir_id})
            ON CREATE SET
                f.fir_number = $fir_number,
                f.police_station = $police_station,
                f.date = $date,
                f.sections = $sections,
                f.complainant = $complainant,
                f.summary = $summary,
                f.created_at = $now,
                f.updated_at = $now,
                f.case_ids = [$case_id]
            ON MATCH SET
                f.updated_at = $now,
                f.case_ids = CASE WHEN $case_id IN f.case_ids THEN f.case_ids ELSE f.case_ids + $case_id END
            WITH f
            MATCH (c:Case {case_id: $case_id})
            MERGE (c)-[:HAS_FIR]->(f)
            MERGE (c)-[:INVOLVES]->(f)
            RETURN (f.created_at = $now) as was_created
            """

# Written AFTER the Person batch so the MATCH on Person succeeds on first ingestion.
FIR_ACCUSED_INVOLVES = """
            MATCH (f:FIR {fir_id: $fir_id}), (p:Person {person_id: $acc_id})
            MERGE (f)-[:INVOLVES]->(p)
            """


def fir_params(fir: FIR) -> Dict[str, Any]:
    """Parameters for FIR_MERGE (add ``case_id`` and ``now`` at call time)."""
    return {
        "fir_id": fir.fir_id,
        "fir_number": fir.fir_number,
        "police_station": fir.police_station,
        "date": fir.date,
        "sections": fir.sections,
        "complainant": fir.complainant,
        "summary": fir.summary
    }


def fir_accused_params(fir: FIR) -> List[Dict[str, Any]]:
    """One FIR_ACCUSED_INVOLVES parameter set per accused person (executed after the Person batch)."""
    return [{"fir_id": fir.fir_id, "acc_id": acc_id} for acc_id in fir.accused_person_ids]


# ---------------------------------------------------------------------------
# 4. People
# ---------------------------------------------------------------------------

PEOPLE_MERGE = """
        UNWIND $rows AS row
        MERGE (p:Person {person_id: row.person_id})
        ON CREATE SET p += row.properties, p.name=row.name, p.aliases=row.aliases, p.age=row.age,
            p.gender=row.gender, p.address=row.address, p.occupation=row.occupation,
            p.phone_numbers=row.phone_numbers, p.dob=row.dob,
            p.national_id=row.national_id, p.roles=row.roles, p.risk_level=row.risk_level,
            p.notes=row.notes, p.created_at=$now, p.updated_at=$now,
            p.case_ids=[$case_id], p.source_record_ids=row.source_record_ids
        ON MATCH SET p += row.properties,
            p.name=coalesce(p.name, row.name),
            p.age=coalesce(p.age, row.age),
            p.gender=coalesce(p.gender, row.gender),
            p.address=coalesce(p.address, row.address),
            p.occupation=coalesce(p.occupation, row.occupation),
            p.dob=coalesce(p.dob, row.dob),
            p.national_id=coalesce(p.national_id, row.national_id),
            p.risk_level=coalesce(p.risk_level, row.risk_level),
            p.notes=coalesce(p.notes, row.notes),
            p.updated_at=$now,
            p.case_ids=CASE WHEN $case_id IN p.case_ids THEN p.case_ids ELSE p.case_ids + $case_id END,
            p.aliases=reduce(acc=[], x IN (coalesce(p.aliases,[]) + coalesce(row.aliases,[]) + [CASE WHEN row.name IS NOT NULL AND row.name <> p.name THEN row.name ELSE NULL END]) |
                CASE WHEN x IS NULL OR x IN acc THEN acc ELSE acc + x END),
            p.roles=reduce(acc=[], x IN (coalesce(p.roles,[]) + coalesce(row.roles,[])) |
                CASE WHEN x IS NULL OR x IN acc THEN acc ELSE acc + x END),
            p.phone_numbers=reduce(acc=[], x IN (coalesce(p.phone_numbers,[]) + coalesce(row.phone_numbers,[])) |
                CASE WHEN x IS NULL OR x IN acc THEN acc ELSE acc + x END),
            p.source_record_ids=reduce(acc=[], x IN (coalesce(p.source_record_ids,[]) + coalesce(row.source_record_ids,[])) |
                CASE WHEN x IS NULL OR x IN acc THEN acc ELSE acc + x END)
        WITH p
        MATCH (c:Case {case_id:$case_id})
        MERGE (c)-[:INVOLVES]->(p)
        RETURN (p.created_at=$now) AS was_created
        """


PROTECTED_PERSON_FIELDS = {
    "person_id", "name", "aliases", "age", "gender", "address", "occupation",
    "phone_numbers", "dob", "national_id", "roles", "risk_level", "notes",
    "case_ids", "source_record_ids", "created_at", "updated_at"
}


def person_row(x: Person) -> Dict[str, Any]:
    safe_props = {k: v for k, v in (x.properties or {}).items() if k not in PROTECTED_PERSON_FIELDS}
    return {
        "person_id": x.person_id,
        "name": x.name,
        "aliases": x.aliases,
        "age": x.age,
        "gender": x.gender,
        "address": x.address,
        "occupation": x.occupation,
        "phone_numbers": x.phone_numbers,
        "dob": x.dob,
        "national_id": x.national_id,
        "roles": x.roles,
        "risk_level": x.risk_level,
        "notes": x.notes,
        "source_record_ids": x.source_record_ids,
        "properties": safe_props
    }



# ---------------------------------------------------------------------------
# 5. Phones (+ OWNS)
# ---------------------------------------------------------------------------

PHONES_MERGE = """
        UNWIND $rows AS row
        MERGE (ph:Phone {phone_number:row.phone_number})
        ON CREATE SET ph.phone_id=row.phone_id, ph.imei=row.imei, ph.carrier=row.carrier,
            ph.registered_owner=row.registered_owner, ph.created_at=$now, ph.updated_at=$now,
            ph.case_ids=[$case_id], ph.source_record_ids=row.source_record_ids
        ON MATCH SET ph.imei=coalesce(row.imei,ph.imei), ph.carrier=coalesce(row.carrier,ph.carrier),
            ph.registered_owner=coalesce(row.registered_owner,ph.registered_owner), ph.updated_at=$now,
            ph.case_ids=CASE WHEN $case_id IN ph.case_ids THEN ph.case_ids ELSE ph.case_ids + $case_id END
        WITH ph
        MATCH (c:Case {case_id:$case_id})
        MERGE (c)-[:INVOLVES]->(ph)
        RETURN (ph.created_at=$now) AS was_created
        """

PHONE_OWNS = """UNWIND $rows AS row MATCH (p:Person {person_id:row.owner_id}), (ph:Phone {phone_number:row.phone_number}) MERGE (p)-[:OWNS]->(ph)"""


def phone_row(x: Phone) -> Dict[str, Any]:
    return {
        "phone_number": x.phone_number, "phone_id": x.phone_id or x.phone_number,
        "imei": x.imei, "carrier": x.carrier, "registered_owner": x.registered_owner,
        "source_record_ids": x.source_record_ids, "owner_person_id": x.owner_person_id
    }


def phone_owns_rows(phone_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [{"owner_id": x["owner_person_id"], "phone_number": x["phone_number"]} for x in phone_rows if x["owner_person_id"]]


# ---------------------------------------------------------------------------
# 6. Bank accounts (+ OWNS)
# ---------------------------------------------------------------------------

BANK_ACCOUNTS_MERGE = """UNWIND $rows AS row MERGE (b:BankAccount {account_number:row.account_number}) ON CREATE SET b.account_id=row.account_id,b.bank_name=row.bank_name,b.account_type=row.account_type,b.branch=row.branch,b.holder_name=row.holder_name,b.created_at=$now,b.updated_at=$now,b.case_ids=[$case_id],b.source_record_ids=row.source_record_ids ON MATCH SET b.bank_name=coalesce(row.bank_name,b.bank_name),b.holder_name=coalesce(row.holder_name,b.holder_name),b.updated_at=$now,b.case_ids=CASE WHEN $case_id IN b.case_ids THEN b.case_ids ELSE b.case_ids+$case_id END WITH b MATCH (c:Case {case_id:$case_id}) MERGE (c)-[:INVOLVES]->(b) RETURN (b.created_at=$now) AS was_created"""

BANK_OWNS = """UNWIND $rows AS row MATCH (p:Person {person_id:row.owner_id}), (b:BankAccount {account_number:row.account_number}) MERGE (p)-[:OWNS]->(b)"""


def bank_account_row(x: BankAccount) -> Dict[str, Any]:
    return {"account_number":x.account_number,"account_id":x.account_id or x.account_number,"bank_name":x.bank_name,"account_type":x.account_type,"branch":x.branch,"holder_name":x.holder_name,"source_record_ids":x.source_record_ids,"owner_person_id":x.owner_person_id}


def bank_owns_rows(bank_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [{"owner_id":x["owner_person_id"],"account_number":x["account_number"]} for x in bank_rows if x["owner_person_id"]]


# ---------------------------------------------------------------------------
# 7. Vehicles (+ OWNS)
# ---------------------------------------------------------------------------

VEHICLES_MERGE = """UNWIND $rows AS row MERGE (v:Vehicle {vin:row.vin}) ON CREATE SET v.vehicle_id=row.vehicle_id,v.license_plate=row.license_plate,v.make=row.make,v.model=row.model,v.color=row.color,v.registered_owner=row.registered_owner,v.created_at=$now,v.updated_at=$now,v.case_ids=[$case_id],v.source_record_ids=row.source_record_ids ON MATCH SET v.license_plate=coalesce(row.license_plate,v.license_plate),v.registered_owner=coalesce(row.registered_owner,v.registered_owner),v.updated_at=$now,v.case_ids=CASE WHEN $case_id IN v.case_ids THEN v.case_ids ELSE v.case_ids+$case_id END WITH v MATCH (c:Case {case_id:$case_id}) MERGE (c)-[:INVOLVES]->(v) RETURN (v.created_at=$now) AS was_created"""

VEHICLE_OWNS = """UNWIND $rows AS row MATCH (p:Person {person_id:row.owner_id}), (v:Vehicle {vin:row.vin}) MERGE (p)-[:OWNS]->(v)"""


def vehicle_row(x: Vehicle) -> Dict[str, Any]:
    return {"vin":x.vin,"vehicle_id":x.vehicle_id or x.vin,"license_plate":x.license_plate,"make":x.make,"model":x.model,"color":x.color,"registered_owner":x.registered_owner,"source_record_ids":x.source_record_ids,"owner_person_id":x.owner_person_id}


def vehicle_owns_rows(vehicle_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [{"owner_id":x["owner_person_id"],"vin":x["vin"]} for x in vehicle_rows if x["owner_person_id"]]


# ---------------------------------------------------------------------------
# 8. Social handles (+ HAS_HANDLE)
# ---------------------------------------------------------------------------

SOCIAL_HANDLES_MERGE = """UNWIND $rows AS row MERGE (s:SocialHandle {handle_id:row.handle_id}) ON CREATE SET s.platform=row.platform,s.handle=row.handle,s.associated_email=row.associated_email,s.display_name=row.display_name,s.created_at=$now,s.updated_at=$now,s.case_ids=[$case_id] ON MATCH SET s.updated_at=$now,s.case_ids=CASE WHEN $case_id IN s.case_ids THEN s.case_ids ELSE s.case_ids+$case_id END WITH s MATCH (c:Case {case_id:$case_id}) MERGE (c)-[:INVOLVES]->(s) RETURN (s.created_at=$now) AS was_created"""

SOCIAL_HAS_HANDLE = """UNWIND $rows AS row MATCH (p:Person {person_id:row.owner_id}), (s:SocialHandle {handle_id:row.handle_id}) MERGE (p)-[:HAS_HANDLE]->(s)"""


def social_handle_row(x: SocialHandle) -> Dict[str, Any]:
    return {"handle_id":x.handle_id,"platform":x.platform,"handle":x.handle,"associated_email":x.associated_email,"display_name":x.display_name,"owner_person_id":x.owner_person_id,"linked_ip":getattr(x, "linked_ip", None)}


def social_has_handle_rows(social_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [{"owner_id":x["owner_person_id"],"handle_id":x["handle_id"]} for x in social_rows if x["owner_person_id"]]


# ---------------------------------------------------------------------------
# 9. IP addresses (+ USES_IP)
# ---------------------------------------------------------------------------

IP_ADDRESSES_MERGE = """UNWIND $rows AS row MERGE (i:IPAddress {ip_address:row.ip_address}) ON CREATE SET i.ip_type=row.ip_type,i.asn=row.asn,i.isp=row.isp,i.created_at=$now,i.updated_at=$now,i.case_ids=[$case_id] ON MATCH SET i.updated_at=$now,i.case_ids=CASE WHEN $case_id IN i.case_ids THEN i.case_ids ELSE i.case_ids+$case_id END WITH i MATCH (c:Case {case_id:$case_id}) MERGE (c)-[:INVOLVES]->(i) RETURN (i.created_at=$now) AS was_created"""

PERSON_USES_IP = """UNWIND $rows AS row MATCH (p:Person {person_id:row.owner_id}), (i:IPAddress {ip_address:row.ip_address}) MERGE (p)-[:USES_IP]->(i)"""

SOCIAL_USES_IP = """UNWIND $rows AS row MATCH (s:SocialHandle {handle_id:row.handle_id}), (i:IPAddress {ip_address:row.linked_ip}) MERGE (s)-[:USES_IP]->(i)"""


def ip_address_row(x: IPAddress) -> Dict[str, Any]:
    return {"ip_address":x.ip_address,"ip_type":x.ip_type,"asn":x.asn,"isp":x.isp,"owner_person_id":getattr(x, "owner_person_id", None)}


def person_uses_ip_rows(ip_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [{"owner_id":x["owner_person_id"],"ip_address":x["ip_address"]} for x in ip_rows if x.get("owner_person_id")]


def social_uses_ip_rows(social_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [{"handle_id":x["handle_id"],"linked_ip":x["linked_ip"]} for x in social_rows if x.get("linked_ip")]


# ---------------------------------------------------------------------------
# 10. Locations, cell towers (+ CellTower LOCATED_AT Location)
# ---------------------------------------------------------------------------

LOCATIONS_MERGE = """UNWIND $rows AS row MERGE (l:Location {location_id:row.location_id}) ON CREATE SET l.name=row.name,l.address=row.address,l.latitude=row.latitude,l.longitude=row.longitude,l.location_type=row.location_type,l.created_at=$now,l.updated_at=$now,l.case_ids=[$case_id] ON MATCH SET l.updated_at=$now,l.case_ids=CASE WHEN $case_id IN l.case_ids THEN l.case_ids ELSE l.case_ids+$case_id END WITH l MATCH (c:Case {case_id:$case_id}) MERGE (c)-[:INVOLVES]->(l) RETURN (l.created_at=$now) AS was_created"""

CELL_TOWERS_MERGE = """UNWIND $rows AS row MERGE (t:CellTower {cell_tower_id:row.cell_tower_id}) ON CREATE SET t.tower_code=row.tower_code,t.operator=row.operator,t.latitude=row.latitude,t.longitude=row.longitude,t.created_at=$now,t.updated_at=$now,t.case_ids=[$case_id] ON MATCH SET t.updated_at=$now,t.case_ids=CASE WHEN $case_id IN t.case_ids THEN t.case_ids ELSE t.case_ids+$case_id END WITH t MATCH (c:Case {case_id:$case_id}) MERGE (c)-[:INVOLVES]->(t) RETURN (t.created_at=$now) AS was_created"""

CELL_TOWER_LOCATED_AT = """UNWIND $rows AS row MATCH (t:CellTower {cell_tower_id:row.cell_tower_id}), (l:Location {location_id:row.location_id}) MERGE (t)-[:LOCATED_AT]->(l)"""


def location_row(x: Location) -> Dict[str, Any]:
    return {"location_id":x.location_id,"name":x.name,"address":x.address,"latitude":x.latitude,"longitude":x.longitude,"location_type":x.location_type}


def cell_tower_row(x: CellTower) -> Dict[str, Any]:
    return {"cell_tower_id":x.cell_tower_id,"tower_code":x.tower_code,"operator":x.operator,"latitude":x.latitude,"longitude":x.longitude,"location_id":x.location_id}


def cell_tower_located_at_rows(tower_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [{"cell_tower_id":x["cell_tower_id"],"location_id":x["location_id"]} for x in tower_rows if x["location_id"]]


# ---------------------------------------------------------------------------
# 11. Communications -> (Phone)-[:CALLED]->(Phone)          [batched in Step 1B]
# ---------------------------------------------------------------------------

CALLED_MERGE = """
            UNWIND $rows AS row
            MERGE (p1:Phone {phone_number: row.src_phone})
            ON CREATE SET p1.created_at = $now, p1.updated_at = $now, p1.case_ids = [$case_id]
            ON MATCH SET p1.updated_at = $now, p1.case_ids = CASE WHEN $case_id IN p1.case_ids THEN p1.case_ids ELSE p1.case_ids + $case_id END
            MERGE (p2:Phone {phone_number: row.dst_phone})
            ON CREATE SET p2.created_at = $now, p2.updated_at = $now, p2.case_ids = [$case_id]
            ON MATCH SET p2.updated_at = $now, p2.case_ids = CASE WHEN $case_id IN p2.case_ids THEN p2.case_ids ELSE p2.case_ids + $case_id END
            MERGE (p1)-[r:CALLED {call_id: row.call_id}]->(p2)
            ON CREATE SET
                r.timestamp = row.timestamp,
                r.duration_seconds = row.duration_seconds,
                r.type = row.type,
                r.cell_tower = row.cell_tower,
                r.source_record_id = row.source_record_id,
                r.case_id = $case_id,
                r.created_at = $now
            ON MATCH SET
                r.duration_seconds = row.duration_seconds,
                r.cell_tower = coalesce(row.cell_tower, r.cell_tower)
            """


def communication_row(comm: CommunicationRecord) -> Dict[str, Any]:
    call_id = comm.call_id or comm.communication_id or f"CALL_{comm.source_phone}_{comm.target_phone}_{comm.timestamp}"
    return {
        "src_phone": comm.source_phone,
        "dst_phone": comm.target_phone,
        "call_id": call_id,
        "timestamp": comm.timestamp,
        "duration_seconds": comm.duration_seconds or 0,
        "type": comm.type,
        "cell_tower": comm.cell_tower,
        "source_record_id": comm.source_record_id
    }


# ---------------------------------------------------------------------------
# 12. Transactions -> Transaction node + (BankAccount)-[:TRANSFERRED_TO]->(BankAccount)   [batched in Step 1B]
# ---------------------------------------------------------------------------

TRANSACTIONS_MERGE = """
            UNWIND $rows AS row
            MERGE (b1:BankAccount {account_number: row.src_acc})
            ON CREATE SET b1.created_at = $now, b1.updated_at = $now, b1.case_ids = [$case_id]
            ON MATCH SET b1.updated_at = $now, b1.case_ids = CASE WHEN $case_id IN b1.case_ids THEN b1.case_ids ELSE b1.case_ids + $case_id END
            MERGE (b2:BankAccount {account_number: row.dst_acc})
            ON CREATE SET b2.created_at = $now, b2.updated_at = $now, b2.case_ids = [$case_id]
            ON MATCH SET b2.updated_at = $now, b2.case_ids = CASE WHEN $case_id IN b2.case_ids THEN b2.case_ids ELSE b2.case_ids + $case_id END

            MERGE (t:Transaction {transaction_id: row.tx_id})
            ON CREATE SET
                t.amount = row.amount,
                t.currency = row.currency,
                t.timestamp = row.timestamp,
                t.transaction_type = row.tx_type,
                t.reference_no = row.reference_no,
                t.description = row.description,
                t.source_record_id = row.source_record_id,
                t.created_at = $now,
                t.case_ids = [$case_id]

            MERGE (b1)-[r:TRANSFERRED_TO {transaction_id: row.tx_id}]->(b2)
            ON CREATE SET
                r.amount = row.amount,
                r.currency = row.currency,
                r.timestamp = row.timestamp,
                r.transaction_type = row.tx_type,
                r.reference_no = row.reference_no,
                r.description = row.description,
                r.source_record_id = row.source_record_id,
                r.case_id = $case_id

            WITH t
            MATCH (c:Case {case_id: $case_id})
            MERGE (c)-[:INVOLVES]->(t)
            RETURN (t.created_at = $now) AS was_created
            """


def transaction_row(tx: TransactionRecord) -> Dict[str, Any]:
    desc = tx.description or (tx.properties.get("description") if tx.properties else None)
    return {
        "src_acc": tx.source_account,
        "dst_acc": tx.target_account,
        "tx_id": tx.transaction_id,
        "amount": tx.amount,
        "currency": tx.currency,
        "timestamp": tx.timestamp,
        "tx_type": tx.transaction_type,
        "reference_no": tx.reference_no,
        "description": desc,
        "source_record_id": tx.source_record_id
    }


# ---------------------------------------------------------------------------
# 13. Surveillance logs -> Location + (Person|Vehicle|Phone)-[:LOCATED_AT]->(Location)   [batched in Step 1B]
# ---------------------------------------------------------------------------

SURVEILLANCE_LOCATIONS_MERGE = """
            UNWIND $rows AS row
            MERGE (l:Location {location_id: row.loc_id})
            ON CREATE SET
                l.name = row.name,
                l.latitude = row.latitude,
                l.longitude = row.longitude,
                l.created_at = $now,
                l.case_ids = [$case_id]
            """

SURVEILLANCE_PERSON_LOCATED_AT = """
                UNWIND $rows AS row
                MATCH (p:Person {person_id: row.p_id}), (l:Location {location_id: row.loc_id})
                MERGE (p)-[r:LOCATED_AT {log_id: row.log_id}]->(l)
                ON CREATE SET
                    r.timestamp = row.timestamp,
                    r.activity_description = row.activity,
                    r.evidence_ref = row.evidence,
                    r.case_id = $case_id,
                    r.source_record_id = row.sr_id
                """

SURVEILLANCE_VEHICLE_LOCATED_AT = """
                UNWIND $rows AS row
                MATCH (v:Vehicle {vin: row.vin}), (l:Location {location_id: row.loc_id})
                MERGE (v)-[r:LOCATED_AT {log_id: row.log_id}]->(l)
                ON CREATE SET
                    r.timestamp = row.timestamp,
                    r.activity_description = row.activity,
                    r.case_id = $case_id
                """

SURVEILLANCE_PHONE_LOCATED_AT = """
                UNWIND $rows AS row
                MATCH (ph:Phone {phone_number: row.phone_number}), (l:Location {location_id: row.loc_id})
                MERGE (ph)-[r:LOCATED_AT {log_id: row.log_id}]->(l)
                ON CREATE SET
                    r.timestamp = row.timestamp,
                    r.activity_description = row.activity,
                    r.case_id = $case_id
                """


def surveillance_location_id(s_log: SurveillanceLogRecord) -> str:
    return s_log.location_id or f"LOC_{s_log.log_id}"


def surveillance_location_row(s_log: SurveillanceLogRecord) -> Dict[str, Any]:
    loc_id = surveillance_location_id(s_log)
    return {
        "loc_id": loc_id,
        "name": s_log.location_name or loc_id,
        "latitude": s_log.latitude,
        "longitude": s_log.longitude
    }


def surveillance_person_rows(s_log: SurveillanceLogRecord) -> List[Dict[str, Any]]:
    loc_id = surveillance_location_id(s_log)
    return [{
        "p_id": p_id,
        "loc_id": loc_id,
        "log_id": s_log.log_id,
        "timestamp": s_log.timestamp,
        "activity": s_log.activity_description,
        "evidence": s_log.evidence_ref,
        "sr_id": s_log.source_record_id
    } for p_id in s_log.observed_person_ids]


def surveillance_vehicle_rows(s_log: SurveillanceLogRecord) -> List[Dict[str, Any]]:
    loc_id = surveillance_location_id(s_log)
    return [{
        "vin": vin,
        "loc_id": loc_id,
        "log_id": s_log.log_id,
        "timestamp": s_log.timestamp,
        "activity": s_log.activity_description
    } for vin in s_log.observed_vehicle_vins]


def surveillance_phone_rows(s_log: SurveillanceLogRecord) -> List[Dict[str, Any]]:
    loc_id = surveillance_location_id(s_log)
    return [{
        "phone_number": pnum,
        "loc_id": loc_id,
        "log_id": s_log.log_id,
        "timestamp": s_log.timestamp,
        "activity": s_log.activity_description
    } for pnum in getattr(s_log, 'observed_phone_numbers', []) or []]


# ---------------------------------------------------------------------------
# 14. Criminal history -> PriorCase + (Person)-[:HAS_PRIOR_CASE]->(PriorCase)   [batched in Step 1B]
# ---------------------------------------------------------------------------

PRIOR_CASES_MERGE = """
            UNWIND $rows AS row
            MERGE (pc:PriorCase {prior_case_id: row.prior_id})
            ON CREATE SET
                pc.case_number = row.case_num,
                pc.offense = row.offense,
                pc.jurisdiction = row.jurisdiction,
                pc.status = row.status,
                pc.year = row.year,
                pc.created_at = $now,
                pc.updated_at = $now,
                pc.case_ids = [$case_id]
            ON MATCH SET
                pc.updated_at = $now,
                pc.case_ids = CASE WHEN $case_id IN pc.case_ids THEN pc.case_ids ELSE pc.case_ids + $case_id END
            WITH row, pc
            MATCH (p:Person {person_id: row.person_id})
            MERGE (p)-[:HAS_PRIOR_CASE]->(pc)
            WITH pc
            MATCH (c:Case {case_id: $case_id})
            MERGE (c)-[:INVOLVES]->(pc)
            RETURN (pc.created_at = $now) AS was_created
            """




def criminal_history_row(ch: CriminalHistoryRecord) -> Dict[str, Any]:
    return {
        "prior_id": ch.record_id,
        "case_num": ch.case_number,
        "offense": ch.offense,
        "jurisdiction": ch.jurisdiction,
        "status": ch.status,
        "year": ch.year,
        "person_id": ch.person_id
    }


# ---------------------------------------------------------------------------
# 15. Intelligence reports -> SourceRecord(INTELLIGENCE_REPORT) + Case INVOLVES   [batched in Step 1B]
#
# NOTE: entities_mentioned is not persisted by the current code and is therefore not written here.
# ---------------------------------------------------------------------------

INTEL_REPORTS_MERGE = """
            UNWIND $rows AS row
            MERGE (sr:SourceRecord {source_record_id: row.report_id})
            ON CREATE SET
                sr.source_type = 'INTELLIGENCE_REPORT',
                sr.source_agency = row.agency,
                sr.reliability_score = row.reliability,
                sr.content = row.content,
                sr.created_at = $now,
                sr.case_ids = [$case_id]
            WITH sr
            MATCH (c:Case {case_id: $case_id})
            MERGE (c)-[:INVOLVES]->(sr)
            RETURN (sr.created_at = $now) AS was_created
            """


def intelligence_report_row(ir: IntelligenceReportRecord) -> Dict[str, Any]:
    return {
        "report_id": ir.report_id,
        "agency": ir.source_agency,
        "reliability": ir.reliability_score,
        "content": ir.content
    }


# ---------------------------------------------------------------------------
# Registry of every write statement (used by tests to enforce that the
# ingestion path issues no Cypher outside this module).
# ---------------------------------------------------------------------------

ALL_WRITE_STATEMENTS: Dict[str, str] = {
    name: value for name, value in globals().items()
    if name.isupper() and isinstance(value, str) and not name.startswith("_") and not name.endswith("_QUERY")
}

BATCHED_RELATIONSHIP_STATEMENTS: Dict[str, str] = {
    "CALLED_MERGE": CALLED_MERGE,
    "TRANSACTIONS_MERGE": TRANSACTIONS_MERGE,
    "SURVEILLANCE_LOCATIONS_MERGE": SURVEILLANCE_LOCATIONS_MERGE,
    "SURVEILLANCE_PERSON_LOCATED_AT": SURVEILLANCE_PERSON_LOCATED_AT,
    "SURVEILLANCE_VEHICLE_LOCATED_AT": SURVEILLANCE_VEHICLE_LOCATED_AT,
    "SURVEILLANCE_PHONE_LOCATED_AT": SURVEILLANCE_PHONE_LOCATED_AT,
    "PERSON_USES_IP": PERSON_USES_IP,
    "SOCIAL_USES_IP": SOCIAL_USES_IP,
    "PRIOR_CASES_MERGE": PRIOR_CASES_MERGE,
    "INTEL_REPORTS_MERGE": INTEL_REPORTS_MERGE,
}
