from typing import Dict, Any, List, Optional
from neo4j import Session
from datetime import datetime, timezone
from backend.models.case_input import CaseData, CaseEnvelope, IngestResponse, IngestCreatedCounts
from backend.models.common import get_current_iso_time
from backend.services.insights_engine import InsightsEngine
from backend.services.blockchain_service import BlockchainService
from backend.services import graph_writes as gw
from backend.logging_config import logger


class IngestionService:
    """
    Idempotent MERGE-based and replace-safe Ingestion Engine for forensic case graphs.

    All Cypher write statements and parameter-row builders live in
    ``backend.services.graph_writes`` so that other write paths (e.g. incremental
    event processing) reuse exactly the same MERGE semantics.
    """

    @staticmethod
    def _run_batch(session: Session, cypher: str, rows: List[Dict[str, Any]], common: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute one parameterized UNWIND batch and return its rows.

        Thin wrapper kept for backward compatibility; delegates to
        ``graph_writes.run_batch`` (no query is issued for an empty row list).
        """
        return gw.run_batch(session, cypher, rows, common)

    @classmethod
    def ingest_case(
        cls,
        session: Session,
        case_data: CaseData,
        dataset_id: Optional[str] = "DS-DEFAULT",
        dataset_version: Optional[str] = "1.0",
        mode: str = "merge",
        confirm_replace: bool = False
    ) -> IngestResponse:
        case_meta = case_data.case_metadata
        case_id = case_meta.case_id
        now = get_current_iso_time()
        warnings: List[str] = []

        logger.info(f"Starting case ingestion: case_id='{case_id}', mode='{mode}', dataset_id='{dataset_id}'")

        # Handle replace mode
        if mode.lower() == "replace":
            if not confirm_replace:
                raise ValueError("Replace mode requires 'confirm_replace: true' safety parameter.")
            cls._execute_replace_cleanup(session, case_id)

        # Counter trackers
        nodes_created = 0
        nodes_matched = 0
        rel_created = 0
        source_records_created = 0

        # 1. Merge Case Node
        res_case = session.run(gw.CASE_MERGE, {**gw.case_params(case_meta), "now": now}).single()
        case_already_exists = not bool(res_case and res_case.get("was_created"))
        if not case_already_exists:
            nodes_created += 1
        else:
            nodes_matched += 1

        # 2. Ingest SourceRecords
        source_rows = [gw.source_record_row(sr) for sr in case_data.source_records]
        sr_rows = cls._run_batch(session, gw.SOURCE_RECORDS_MERGE, source_rows, {"case_id": case_id, "now": now})
        source_records_created += len(source_rows)
        nodes_created += sum(1 for r in sr_rows if r.get("was_created"))
        nodes_matched += len(sr_rows) - sum(1 for r in sr_rows if r.get("was_created"))
        rel_created += len(source_rows)

        # 3. Ingest FIR Records
        # FIR -> accused Person links are collected here and written in step 4b,
        # after the Person batch, so the MATCH on Person succeeds on first ingestion.
        fir_accused_links: List[Dict[str, Any]] = []
        for fir in case_data.fir_records:
            res_fir = session.run(gw.FIR_MERGE, {**gw.fir_params(fir), "case_id": case_id, "now": now}).single()
            if res_fir and res_fir["was_created"]:
                nodes_created += 1
            else:
                nodes_matched += 1
            rel_created += 2

            # Accused links are deferred until People exist (see step 4b)
            fir_accused_links.extend(gw.fir_accused_params(fir))

        # 4. Ingest People
        people_rows = [gw.person_row(x) for x in case_data.entities.people]
        people_results = cls._run_batch(session, gw.PEOPLE_MERGE, people_rows, {"case_id": case_id, "now": now})
        created = sum(1 for r in people_results if r.get("was_created"))
        nodes_created += created; nodes_matched += len(people_results)-created; rel_created += len(people_rows)

        # 4b. FIR -> accused Person links (deferred from step 3 so Person nodes exist)
        for acc_params in fir_accused_links:
            session.run(gw.FIR_ACCUSED_INVOLVES, acc_params)
            rel_created += 1

        # 5. Ingest Phones
        phone_rows = [gw.phone_row(x) for x in case_data.entities.phones]
        phone_results = cls._run_batch(session, gw.PHONES_MERGE, phone_rows, {"case_id":case_id,"now":now})
        created=sum(1 for r in phone_results if r.get("was_created")); nodes_created+=created; nodes_matched+=len(phone_results)-created; rel_created+=len(phone_rows)
        owner_rows=gw.phone_owns_rows(phone_rows)
        cls._run_batch(session,gw.PHONE_OWNS,owner_rows,{})
        rel_created+=len(owner_rows)

        # 6. Ingest BankAccounts
        bank_rows=[gw.bank_account_row(x) for x in case_data.entities.bank_accounts]
        bank_results=cls._run_batch(session,gw.BANK_ACCOUNTS_MERGE,bank_rows,{"case_id":case_id,"now":now})
        created=sum(1 for r in bank_results if r.get("was_created")); nodes_created+=created; nodes_matched+=len(bank_results)-created; rel_created+=len(bank_rows)
        owner_rows=gw.bank_owns_rows(bank_rows)
        cls._run_batch(session,gw.BANK_OWNS,owner_rows,{})
        rel_created+=len(owner_rows)

        # 7. Ingest Vehicles
        vehicle_rows=[gw.vehicle_row(x) for x in case_data.entities.vehicles]
        vehicle_results=cls._run_batch(session,gw.VEHICLES_MERGE,vehicle_rows,{"case_id":case_id,"now":now})
        created=sum(1 for r in vehicle_results if r.get("was_created")); nodes_created+=created; nodes_matched+=len(vehicle_results)-created; rel_created+=len(vehicle_rows)
        owner_rows=gw.vehicle_owns_rows(vehicle_rows)
        cls._run_batch(session,gw.VEHICLE_OWNS,owner_rows,{})
        rel_created+=len(owner_rows)

        # 8. Ingest Social Handles
        social_rows=[gw.social_handle_row(x) for x in case_data.entities.social_handles]
        social_results=cls._run_batch(session,gw.SOCIAL_HANDLES_MERGE,social_rows,{"case_id":case_id,"now":now})
        created=sum(1 for r in social_results if r.get("was_created")); nodes_created+=created; nodes_matched+=len(social_results)-created; rel_created+=len(social_rows)
        owner_rows=gw.social_has_handle_rows(social_rows)
        cls._run_batch(session,gw.SOCIAL_HAS_HANDLE,owner_rows,{})
        rel_created+=len(owner_rows)

        # 9. Ingest IP Addresses
        ip_rows=[gw.ip_address_row(x) for x in case_data.entities.ip_addresses]
        ip_results=cls._run_batch(session,gw.IP_ADDRESSES_MERGE,ip_rows,{"case_id":case_id,"now":now})
        created=sum(1 for r in ip_results if r.get("was_created")); nodes_created+=created; nodes_matched+=len(ip_results)-created; rel_created+=len(ip_rows)

        # 10. Ingest Locations & Cell Towers
        loc_rows=[gw.location_row(x) for x in case_data.entities.locations]
        loc_results=cls._run_batch(session,gw.LOCATIONS_MERGE,loc_rows,{"case_id":case_id,"now":now})
        created=sum(1 for r in loc_results if r.get("was_created")); nodes_created+=created; nodes_matched+=len(loc_results)-created; rel_created+=len(loc_rows)
        tower_rows=[gw.cell_tower_row(x) for x in case_data.entities.cell_towers]
        tower_results=cls._run_batch(session,gw.CELL_TOWERS_MERGE,tower_rows,{"case_id":case_id,"now":now})
        created=sum(1 for r in tower_results if r.get("was_created")); nodes_created+=created; nodes_matched+=len(tower_results)-created; rel_created+=len(tower_rows)
        tower_loc=gw.cell_tower_located_at_rows(tower_rows)
        cls._run_batch(session,gw.CELL_TOWER_LOCATED_AT,tower_loc,{})
        rel_created+=len(tower_loc)

        # 11. Ingest Communications (CALLED directed edges) -- one UNWIND batch
        comm_rows = [gw.communication_row(comm) for comm in case_data.relationships.communications]
        cls._run_batch(session, gw.CALLED_MERGE, comm_rows, {"case_id": case_id, "now": now})
        rel_created += len(comm_rows)

        # 12. Ingest Transactions (TRANSFERRED_TO & Transaction Node) -- one UNWIND batch
        tx_rows = [gw.transaction_row(tx) for tx in case_data.relationships.transactions]
        tx_results = cls._run_batch(session, gw.TRANSACTIONS_MERGE, tx_rows, {"case_id": case_id, "now": now})
        # Per input record (as before): created if a row came back with was_created, otherwise matched.
        created = sum(1 for r in tx_results if r.get("was_created"))
        nodes_created += created
        nodes_matched += len(tx_rows) - created
        rel_created += 2 * len(tx_rows)

        # 13. Ingest Surveillance Logs (LOCATED_AT relationships) -- three UNWIND batches
        #     (Location MERGE, Person LOCATED_AT, Vehicle LOCATED_AT), preserving the
        #     original write order: all Locations exist before any LOCATED_AT MATCH.
        surv_loc_rows: List[Dict[str, Any]] = []
        surv_person_rows: List[Dict[str, Any]] = []
        surv_vehicle_rows: List[Dict[str, Any]] = []
        for s_log in case_data.surveillance_logs:
            surv_loc_rows.append(gw.surveillance_location_row(s_log))
            surv_person_rows.extend(gw.surveillance_person_rows(s_log))
            surv_vehicle_rows.extend(gw.surveillance_vehicle_rows(s_log))
        cls._run_batch(session, gw.SURVEILLANCE_LOCATIONS_MERGE, surv_loc_rows, {"case_id": case_id, "now": now})
        cls._run_batch(session, gw.SURVEILLANCE_PERSON_LOCATED_AT, surv_person_rows, {"case_id": case_id})
        rel_created += len(surv_person_rows)
        cls._run_batch(session, gw.SURVEILLANCE_VEHICLE_LOCATED_AT, surv_vehicle_rows, {"case_id": case_id})
        rel_created += len(surv_vehicle_rows)

        # 14. Ingest Criminal History (PriorCase nodes & HAS_PRIOR_CASE) -- one UNWIND batch
        ch_rows = [gw.criminal_history_row(ch) for ch in case_data.criminal_history]
        ch_results = cls._run_batch(session, gw.PRIOR_CASES_MERGE, ch_rows, {"case_id": case_id, "now": now})
        # A record whose Person does not exist returns no row (as before: res_ch is None -> matched).
        created = sum(1 for r in ch_results if r.get("was_created"))
        nodes_created += created
        nodes_matched += len(ch_rows) - created
        rel_created += 2 * len(ch_rows)

        # 15. Ingest Intelligence Reports (SourceRecord representation) -- one UNWIND batch
        ir_rows = [gw.intelligence_report_row(ir) for ir in case_data.intelligence_reports]
        ir_results = cls._run_batch(session, gw.INTEL_REPORTS_MERGE, ir_rows, {"case_id": case_id, "now": now})
        source_records_created += len(ir_rows)
        created = sum(1 for r in ir_results if r.get("was_created"))
        nodes_created += created
        nodes_matched += len(ir_rows) - created
        rel_created += len(ir_rows)

        # Run Insights Engine to compute case and cross-case insights
        insights = InsightsEngine.run_all_detectors(session, case_id=case_id)
        
        # Calculate new cross-case links
        cross_case_links_count = sum(1 for ins in insights if ins.insight_type in ["CROSS_CASE_LINK", "SHARED_ENTITY", "BRIDGE_NODE"])

        # Record document-level cryptographic evidence blocks on immutable Blockchain Ledger
        try:
            payload_dict = case_data.model_dump() if hasattr(case_data, 'model_dump') else (case_data.dict() if hasattr(case_data, 'dict') else str(case_data))
            BlockchainService.record_case_evidence_documents(case_id=case_id, payload_dict=payload_dict)
        except Exception as be:
            logger.warning(f"Could not commit blockchain ledger blocks for case '{case_id}': {be}")

        response = IngestResponse(
            case_id=case_id,
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            created=IngestCreatedCounts(
                nodes=nodes_created,
                relationships=rel_created,
                source_records=source_records_created
            ),
            matched_existing_entities=nodes_matched,
            new_cross_case_links=cross_case_links_count,
            new_insights=len(insights),
            warnings=warnings,
            insights=insights,
            case_already_exists=case_already_exists
        )
        logger.info(f"Completed ingestion for case '{case_id}': created {nodes_created} nodes, {rel_created} rels, generated {len(insights)} insights.")
        return response

    @staticmethod
    def _execute_replace_cleanup(session: Session, case_id: str) -> None:
        """
        Safely removes graph elements exclusively associated with case_id,
        or removes case_id from multi-case entities.
        """
        logger.info(f"Executing replace cleanup for case_id='{case_id}'")
        # 1. For nodes that belong exclusively to this case, delete them
        delete_exclusive_cypher = """
        MATCH (n)
        WHERE n.case_ids = [$case_id]
        DETACH DELETE n
        """
        session.run(delete_exclusive_cypher, {"case_id": case_id})

        # 2. For multi-case nodes, remove case_id from their case_ids list
        update_multicase_cypher = """
        MATCH (n)
        WHERE $case_id IN n.case_ids AND size(n.case_ids) > 1
        SET n.case_ids = [c IN n.case_ids WHERE c <> $case_id]
        """
        session.run(update_multicase_cypher, {"case_id": case_id})

