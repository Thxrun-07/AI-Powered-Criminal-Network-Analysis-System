"""
DeltaProcessor -- incremental event processing (Phase 2).

Pipeline for one ``EventBatch``:

    events  ->  group by type  ->  build rows with graph_writes.*_row()  ->
    ONE write transaction executing graph_writes.* statements in bulk-ingest order  ->
    TouchedEntities (payload keys + owners + both relationship endpoints + case_ids joins)  ->
    scoped detectors (dependency-dispatched, global scope)  ->  EventProcessingResult

Guarantees:

* **No write logic of its own.** Every Cypher statement and every parameter-row
  builder comes from ``backend.services.graph_writes`` -- the same objects the bulk
  ``IngestionService`` uses -- so MERGE keys, ON CREATE / ON MATCH behaviour,
  relationship ``case_id`` scalars and node ``case_ids`` lists are identical by
  construction. (``tests`` assert the processor issues no statement outside
  ``graph_writes.ALL_WRITE_STATEMENTS``.)
* **Same write order as bulk ingestion** within the batch, so e.g. Person rows
  are merged before OWNS / FIR-accused / HAS_PRIOR_CASE MATCH them, and all
  Locations exist before LOCATED_AT.
* **One transaction per batch** (``session.execute_write``); a failure rolls
  back every write of the batch.
* **Events never create a Case node.** The case must exist (``CaseNotFoundError``).
* **Touched-entity tracking is deliberately generous** (owner Persons, both
  endpoints, implicit Phones/BankAccounts/Locations created by relationship
  writers, case-join changes) -- running an extra detector is preferred over a
  false negative.
* **Detector failures are surfaced**, never swallowed: the injected detector
  runner returns per-detector status which is copied into the result.

Explicitly unsupported (fail validation upstream, see ``backend.models.event``):
delete / retract / correction events, IP-link events (``LINKED_TO_IP`` is not a
written relationship), and ``observed_phone_numbers`` / ``entities_mentioned``
(not persisted by the bulk path either).
"""
from collections import Counter, defaultdict
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

from neo4j import Session

from backend.logging_config import logger
from backend.models.common import get_current_iso_time
from backend.models.event import (
    DetectorRun, EntityKind, EventBatch, EventProcessingResult, EventType,
    TouchedEntities, WriteCounts,
)
from backend.models.insights import InsightItem
from backend.services import graph_writes as gw
from backend.services.scoped_detectors import run_scoped_detectors


class CaseNotFoundError(LookupError):
    """Raised when an EventBatch targets a case that does not exist in the graph."""


#: Signature of the pluggable scoped-detector runner (Phase 2 step 3 provides the real one):
#:   runner(session, touched) -> (insights, detector_runs, detectors_skipped)
DetectorRunner = Callable[[Session, TouchedEntities], Tuple[List[InsightItem], List[DetectorRun], List[str]]]


def _no_detectors(session: Session, touched: TouchedEntities) -> Tuple[List[InsightItem], List[DetectorRun], List[str]]:
    """Explicit opt-out runner (``DeltaProcessor(detector_runner=_no_detectors)``): runs nothing;
    process_events adds NO_DETECTOR_RUNNER_WARNING so the omission is visible in the response."""
    return [], [], []


def _default_scoped_runner(session: Session, touched: TouchedEntities) -> Tuple[List[InsightItem], List[DetectorRun], List[str]]:
    """Default runner: the dependency-dispatched scoped detectors in GLOBAL scope (case_id=None),
    so cross-case patterns reachable from touched identities are never missed."""
    return run_scoped_detectors(session, touched, case_id=None)


NO_DETECTOR_RUNNER_WARNING = "No scoped detector runner configured: writes were applied but no insights were computed for this batch."


# Labels whose case_ids membership we pre-read to detect case joins (SHARED_ENTITY / BRIDGE etc. triggers).
_CASE_JOIN_LABELS: Tuple[Tuple[str, str], ...] = (
    ("Person", "persons"), ("Phone", "phones"), ("BankAccount", "bank_accounts"), ("Vehicle", "vehicles"),
    ("SocialHandle", "social_handles"), ("IPAddress", "ip_addresses"), ("Location", "locations"),
    ("CellTower", "cell_towers"), ("PriorCase", "prior_cases"),
)


class DeltaProcessor:
    """Applies event batches with bulk-ingest write semantics and reports touched entities."""

    def __init__(self, detector_runner: Optional[DetectorRunner] = None):
        self._detector_runner: DetectorRunner = detector_runner or _default_scoped_runner

    # ------------------------------------------------------------------ public

    def process_events(self, session: Session, batch: EventBatch) -> EventProcessingResult:
        """Validate the case, apply the batch in one write transaction, derive touched
        entities, run the scoped detectors and return a full EventProcessingResult."""
        case_id = batch.case_id
        now = get_current_iso_time()

        if not self._case_exists(session, case_id):
            raise CaseNotFoundError(
                f"Case '{case_id}' does not exist; events never create Case nodes -- ingest the case first."
            )

        plan = self.build_plan(batch, now)
        touched = self.touched_from_batch(batch)

        counts, case_joins = session.execute_write(self._apply_plan, plan, case_id, touched)
        touched.case_ids_changed.update(case_joins)

        insights, detector_runs, skipped = self._detector_runner(session, touched)
        failed = [d.detector for d in detector_runs if d.status == "failed"]
        warnings = self._warnings_for(batch)
        if self._detector_runner is _no_detectors:
            warnings.append(NO_DETECTOR_RUNNER_WARNING)

        result = EventProcessingResult(
            case_id=case_id,
            batch_id=batch.batch_id,
            event_ids=[e.event_id for e in batch.events],
            events_by_type=dict(Counter(e.event_type.value for e in batch.events)),
            writes=counts,
            touched=touched,
            detectors_run=detector_runs,
            detectors_failed=failed,
            detectors_skipped=skipped,
            insights=insights,
            warnings=warnings,
        )
        logger.info(
            f"Processed {len(batch.events)} event(s) for case '{case_id}': "
            f"{counts.statements_executed} statements, {counts.nodes_created} nodes created, "
            f"{len(insights)} scoped insight(s), {len(failed)} detector failure(s)."
        )
        return result

    # ------------------------------------------------------------------ plan

    @staticmethod
    def build_plan(batch: EventBatch, now: str) -> List[Dict[str, Any]]:
        """
        Turn a batch into an ordered list of write steps, each referencing a
        ``graph_writes`` statement by name:

            {"name": <ALL_WRITE_STATEMENTS key>, "mode": "batch"|"single",
             "rows": [...] | "params": {...}, "count": <"node"|"rel"|None>, "rel_per_row": int}

        Order mirrors IngestionService.ingest_case steps 2-15 (there is no Case step:
        events never create or update Case metadata).
        """
        case_id = batch.case_id
        common = {"case_id": case_id, "now": now}
        by_type: Dict[EventType, List[Any]] = defaultdict(list)
        for ev in batch.events:
            by_type[ev.event_type].append(ev.payload)

        plan: List[Dict[str, Any]] = []

        def batch_step(name: str, rows: List[Dict[str, Any]], params: Dict[str, Any], count_nodes: bool, rel_per_row: int):
            if rows:
                plan.append({"name": name, "mode": "batch", "rows": rows, "params": params,
                             "count_nodes": count_nodes, "rel_per_row": rel_per_row})

        # 2. SourceRecords
        batch_step("SOURCE_RECORDS_MERGE", [gw.source_record_row(x) for x in by_type[EventType.SOURCE_RECORD_UPSERT]],
                   common, True, 1)

        # 3. FIR (single-record statement, as in bulk ingest); accused links deferred to after People
        firs = by_type[EventType.FIR_UPSERT]
        for fir in firs:
            plan.append({"name": "FIR_MERGE", "mode": "single", "params": {**gw.fir_params(fir), **common},
                         "count_nodes": True, "rel_per_row": 2})

        # 4. People
        batch_step("PEOPLE_MERGE", [gw.person_row(x) for x in by_type[EventType.PERSON_UPSERT]], common, True, 1)

        # 4b. FIR -> accused (after People exist)
        for fir in firs:
            for acc in gw.fir_accused_params(fir):
                plan.append({"name": "FIR_ACCUSED_INVOLVES", "mode": "single", "params": acc,
                             "count_nodes": False, "rel_per_row": 1})

        # 5. Phones (+ OWNS)
        phone_rows = [gw.phone_row(x) for x in by_type[EventType.PHONE_UPSERT]]
        batch_step("PHONES_MERGE", phone_rows, common, True, 1)
        batch_step("PHONE_OWNS", gw.phone_owns_rows(phone_rows), {}, False, 1)

        # 6. Bank accounts (+ OWNS)
        bank_rows = [gw.bank_account_row(x) for x in by_type[EventType.BANK_ACCOUNT_UPSERT]]
        batch_step("BANK_ACCOUNTS_MERGE", bank_rows, common, True, 1)
        batch_step("BANK_OWNS", gw.bank_owns_rows(bank_rows), {}, False, 1)

        # 7. Vehicles (+ OWNS)
        vehicle_rows = [gw.vehicle_row(x) for x in by_type[EventType.VEHICLE_UPSERT]]
        batch_step("VEHICLES_MERGE", vehicle_rows, common, True, 1)
        batch_step("VEHICLE_OWNS", gw.vehicle_owns_rows(vehicle_rows), {}, False, 1)

        # 8. Social handles (+ HAS_HANDLE)
        social_rows = [gw.social_handle_row(x) for x in by_type[EventType.SOCIAL_HANDLE_UPSERT]]
        batch_step("SOCIAL_HANDLES_MERGE", social_rows, common, True, 1)
        batch_step("SOCIAL_HAS_HANDLE", gw.social_has_handle_rows(social_rows), {}, False, 1)

        # 9. IP addresses (node + Case INVOLVES + USES_IP)
        ip_rows = [gw.ip_address_row(x) for x in by_type[EventType.IP_ADDRESS_UPSERT]]
        batch_step("IP_ADDRESSES_MERGE", ip_rows, common, True, 1)
        batch_step("PERSON_USES_IP", gw.person_uses_ip_rows(ip_rows), {}, False, 1)
        batch_step("SOCIAL_USES_IP", gw.social_uses_ip_rows(social_rows), {}, False, 1)

        # 10. Locations, cell towers (+ tower LOCATED_AT)
        batch_step("LOCATIONS_MERGE", [gw.location_row(x) for x in by_type[EventType.LOCATION_UPSERT]], common, True, 1)
        tower_rows = [gw.cell_tower_row(x) for x in by_type[EventType.CELL_TOWER_UPSERT]]
        batch_step("CELL_TOWERS_MERGE", tower_rows, common, True, 1)
        batch_step("CELL_TOWER_LOCATED_AT", gw.cell_tower_located_at_rows(tower_rows), {}, False, 1)

        # 11. Communications -> CALLED
        batch_step("CALLED_MERGE", [gw.communication_row(x) for x in by_type[EventType.COMMUNICATION]], common, False, 1)

        # 12. Transactions -> TRANSFERRED_TO + Transaction node
        batch_step("TRANSACTIONS_MERGE", [gw.transaction_row(x) for x in by_type[EventType.TRANSACTION]], common, True, 2)

        # 13. Surveillance -> Location, Person LOCATED_AT, Vehicle LOCATED_AT, Phone LOCATED_AT
        logs = by_type[EventType.SURVEILLANCE_LOG]
        surv_loc, surv_p, surv_v, surv_ph = [], [], [], []
        for lg in logs:
            surv_loc.append(gw.surveillance_location_row(lg))
            surv_p.extend(gw.surveillance_person_rows(lg))
            surv_v.extend(gw.surveillance_vehicle_rows(lg))
            surv_ph.extend(gw.surveillance_phone_rows(lg))
        batch_step("SURVEILLANCE_LOCATIONS_MERGE", surv_loc, common, False, 0)
        batch_step("SURVEILLANCE_PERSON_LOCATED_AT", surv_p, {"case_id": case_id}, False, 1)
        batch_step("SURVEILLANCE_VEHICLE_LOCATED_AT", surv_v, {"case_id": case_id}, False, 1)
        batch_step("SURVEILLANCE_PHONE_LOCATED_AT", surv_ph, {"case_id": case_id}, False, 1)

        # 14. Criminal history -> PriorCase + HAS_PRIOR_CASE
        batch_step("PRIOR_CASES_MERGE", [gw.criminal_history_row(x) for x in by_type[EventType.CRIMINAL_HISTORY]], common, True, 2)

        # 15. Intelligence reports -> SourceRecord(INTELLIGENCE_REPORT)
        batch_step("INTEL_REPORTS_MERGE", [gw.intelligence_report_row(x) for x in by_type[EventType.INTELLIGENCE_REPORT]], common, True, 1)

        return plan

    # ------------------------------------------------------------------ touched entities

    @staticmethod
    def touched_from_batch(batch: EventBatch) -> TouchedEntities:
        """
        Static touched-set derivation (no DB access):

        * entity upserts -> their MERGE key; ``owner_person_id`` -> owner Person + OWNS/HAS_HANDLE kind;
        * COMMUNICATION -> both phones (implicitly MERGEd by the writer) + CALLED;
        * TRANSACTION -> both accounts (implicitly MERGEd) + TRANSFERRED_TO;
        * SURVEILLANCE_LOG -> location (explicit or ``LOC_<log_id>`` fallback), observed persons & vehicles + LOCATED_AT;
        * CRIMINAL_HISTORY -> person + PriorCase(record_id) + HAS_PRIOR_CASE;
        * CELL_TOWER with location_id -> tower + location + LOCATED_AT;
        * FIR accused -> persons (FIR-INVOLVES is not read by any detector, but the Person identity is cheap to include).

        SOURCE_RECORD / INTELLIGENCE_REPORT / FIR nodes themselves are not detector inputs and are not tracked.
        """
        t = TouchedEntities()
        for ev in batch.events:
            p = ev.payload
            et = ev.event_type
            if et == EventType.PERSON_UPSERT:
                t.persons.add(p.person_id)
            elif et == EventType.PHONE_UPSERT:
                t.phones.add(p.phone_number)
                if p.owner_person_id:
                    t.persons.add(p.owner_person_id); t.relationship_kinds.add(EntityKind.OWNS)
            elif et == EventType.BANK_ACCOUNT_UPSERT:
                t.bank_accounts.add(p.account_number)
                if p.owner_person_id:
                    t.persons.add(p.owner_person_id); t.relationship_kinds.add(EntityKind.OWNS)
            elif et == EventType.VEHICLE_UPSERT:
                t.vehicles.add(p.vin)
                if p.owner_person_id:
                    t.persons.add(p.owner_person_id); t.relationship_kinds.add(EntityKind.OWNS)
            elif et == EventType.SOCIAL_HANDLE_UPSERT:
                t.social_handles.add(p.handle_id)
                if p.owner_person_id:
                    t.persons.add(p.owner_person_id); t.relationship_kinds.add(EntityKind.HAS_HANDLE)
            elif et == EventType.IP_ADDRESS_UPSERT:
                t.ip_addresses.add(p.ip_address)
            elif et == EventType.LOCATION_UPSERT:
                t.locations.add(p.location_id)
            elif et == EventType.CELL_TOWER_UPSERT:
                t.cell_towers.add(p.cell_tower_id)
                if p.location_id:
                    t.locations.add(p.location_id); t.relationship_kinds.add(EntityKind.LOCATED_AT)
            elif et == EventType.FIR_UPSERT:
                t.persons.update(p.accused_person_ids)
            elif et == EventType.COMMUNICATION:
                t.phones.update((p.source_phone, p.target_phone)); t.relationship_kinds.add(EntityKind.CALLED)
            elif et == EventType.TRANSACTION:
                t.bank_accounts.update((p.source_account, p.target_account)); t.relationship_kinds.add(EntityKind.TRANSFERRED_TO)
            elif et == EventType.SURVEILLANCE_LOG:
                t.locations.add(gw.surveillance_location_id(p))
                t.persons.update(p.observed_person_ids); t.vehicles.update(p.observed_vehicle_vins)
                t.relationship_kinds.add(EntityKind.LOCATED_AT)
            elif et == EventType.CRIMINAL_HISTORY:
                t.persons.add(p.person_id); t.prior_cases.add(p.record_id)
                t.relationship_kinds.add(EntityKind.HAS_PRIOR_CASE)
            # SOURCE_RECORD_UPSERT / INTELLIGENCE_REPORT: no detector reads them
        return t

    # ------------------------------------------------------------------ transaction body

    @classmethod
    def _apply_plan(cls, tx, plan: List[Dict[str, Any]], case_id: str, touched: TouchedEntities) -> Tuple[WriteCounts, Set[str]]:
        """Runs inside ONE write transaction. Returns write counts and the set of
        '<Label>:<key>' nodes that joined ``case_id`` during this batch."""
        # Pre-read: which touched nodes already exist WITHOUT this case in case_ids?
        # After the writes, those that now exist have (by MERGE semantics) gained the case.
        candidates: Set[str] = set()
        for label, attr in _CASE_JOIN_LABELS:
            keys = sorted(getattr(touched, attr))
            if not keys:
                continue
            for rec in tx.run(gw.case_membership_query(label), {"keys": keys, "case_id": case_id}):
                if not rec["in_case"]:
                    candidates.add(f"{label}:{rec['key']}")

        counts = WriteCounts()
        for step in plan:
            cypher = gw.ALL_WRITE_STATEMENTS[step["name"]]
            if step["mode"] == "batch":
                params = dict(step["params"]); params["rows"] = step["rows"]
                rows = tx.run(cypher, params).data()
                n_in = len(step["rows"])
                if step["count_nodes"]:
                    created = sum(1 for r in rows if r.get("was_created"))
                    counts.nodes_created += created
                    counts.nodes_matched += n_in - created
                counts.relationships_written += step["rel_per_row"] * n_in
            else:
                res = tx.run(cypher, step["params"])
                rec = res.single()
                if step["count_nodes"]:
                    if rec and rec["was_created"]:
                        counts.nodes_created += 1
                    else:
                        counts.nodes_matched += 1
                counts.relationships_written += step["rel_per_row"]
            counts.statements_executed += 1

        # Post-read only for candidates: still absent => never written (e.g. missing MATCH target), not a join.
        joined: Set[str] = set()
        if candidates:
            by_label: Dict[str, List[str]] = defaultdict(list)
            for item in candidates:
                label, key = item.split(":", 1)
                by_label[label].append(key)
            for label, keys in by_label.items():
                for rec in tx.run(gw.case_membership_query(label), {"keys": keys, "case_id": case_id}):
                    if rec["in_case"]:
                        joined.add(f"{label}:{rec['key']}")
        return counts, joined

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _case_exists(session: Session, case_id: str) -> bool:
        rec = session.run(gw.CASE_EXISTS_QUERY, {"case_id": case_id}).single()
        return bool(rec and rec["exists"])

    @staticmethod
    def _warnings_for(batch: EventBatch) -> List[str]:
        """Surface payload fields the write path (bulk and event alike) does not persist."""
        warnings: List[str] = []
        dropped_phones = sum(len(e.payload.observed_phone_numbers) for e in batch.events
                             if e.event_type == EventType.SURVEILLANCE_LOG)
        if dropped_phones:
            warnings.append(f"{dropped_phones} observed_phone_numbers value(s) ignored: not persisted by the current schema.")
        dropped_mentions = sum(len(e.payload.entities_mentioned) for e in batch.events
                               if e.event_type == EventType.INTELLIGENCE_REPORT)
        if dropped_mentions:
            warnings.append(f"{dropped_mentions} entities_mentioned value(s) ignored: not persisted by the current schema.")
        return warnings
