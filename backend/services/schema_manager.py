from neo4j import Session
from neo4j.exceptions import ServiceUnavailable, DriverError
from backend.logging_config import logger


CONSTRAINTS = [
    ("constraint_case_id", "CREATE CONSTRAINT constraint_case_id IF NOT EXISTS FOR (c:Case) REQUIRE c.case_id IS UNIQUE"),
    ("constraint_fir_id", "CREATE CONSTRAINT constraint_fir_id IF NOT EXISTS FOR (f:FIR) REQUIRE f.fir_id IS UNIQUE"),
    ("constraint_person_id", "CREATE CONSTRAINT constraint_person_id IF NOT EXISTS FOR (p:Person) REQUIRE p.person_id IS UNIQUE"),
    ("constraint_phone_number", "CREATE CONSTRAINT constraint_phone_number IF NOT EXISTS FOR (ph:Phone) REQUIRE ph.phone_number IS UNIQUE"),
    ("constraint_bank_account", "CREATE CONSTRAINT constraint_bank_account IF NOT EXISTS FOR (b:BankAccount) REQUIRE b.account_number IS UNIQUE"),
    ("constraint_vehicle_vin", "CREATE CONSTRAINT constraint_vehicle_vin IF NOT EXISTS FOR (v:Vehicle) REQUIRE v.vin IS UNIQUE"),
    ("constraint_social_handle", "CREATE CONSTRAINT constraint_social_handle IF NOT EXISTS FOR (s:SocialHandle) REQUIRE s.handle_id IS UNIQUE"),
    ("constraint_ip_address", "CREATE CONSTRAINT constraint_ip_address IF NOT EXISTS FOR (ip:IPAddress) REQUIRE ip.ip_address IS UNIQUE"),
    ("constraint_location_id", "CREATE CONSTRAINT constraint_location_id IF NOT EXISTS FOR (l:Location) REQUIRE l.location_id IS UNIQUE"),
    ("constraint_cell_tower_id", "CREATE CONSTRAINT constraint_cell_tower_id IF NOT EXISTS FOR (ct:CellTower) REQUIRE ct.cell_tower_id IS UNIQUE"),
    ("constraint_transaction_id", "CREATE CONSTRAINT constraint_transaction_id IF NOT EXISTS FOR (t:Transaction) REQUIRE t.transaction_id IS UNIQUE"),
    ("constraint_prior_case_id", "CREATE CONSTRAINT constraint_prior_case_id IF NOT EXISTS FOR (pc:PriorCase) REQUIRE pc.prior_case_id IS UNIQUE"),
    ("constraint_source_record_id", "CREATE CONSTRAINT constraint_source_record_id IF NOT EXISTS FOR (sr:SourceRecord) REQUIRE sr.source_record_id IS UNIQUE"),
    ("constraint_block_index", "CREATE CONSTRAINT constraint_block_index IF NOT EXISTS FOR (b:Block) REQUIRE b.index IS UNIQUE"),
]

INDEXES = [
    ("index_person_name", "CREATE INDEX index_person_name IF NOT EXISTS FOR (p:Person) ON (p.name)"),
    ("index_phone_imei", "CREATE INDEX index_phone_imei IF NOT EXISTS FOR (ph:Phone) ON (ph.imei)"),
    ("index_vehicle_plate", "CREATE INDEX index_vehicle_plate IF NOT EXISTS FOR (v:Vehicle) ON (v.license_plate)"),
    ("index_case_type", "CREATE INDEX index_case_type IF NOT EXISTS FOR (c:Case) ON (c.case_type)"),
    ("index_case_status", "CREATE INDEX index_case_status IF NOT EXISTS FOR (c:Case) ON (c.status)"),
]


def init_schema(session: Session) -> None:
    """
    Initializes uniqueness constraints and performance indexes for all 13 canonical node labels.
    Fails fast if Neo4j database is offline.
    """
    logger.info("Initializing Neo4j schema constraints and indexes...")
    # 1. Quick connectivity probe
    try:
        session.run("RETURN 1").single()
    except (ServiceUnavailable, DriverError, Exception) as e:
        logger.warning(f"Neo4j database is currently unreachable ({e}). Schema initialization deferred until database is online.")
        return

    # 2. Apply constraints
    for name, query in CONSTRAINTS:
        try:
            session.run(query)
            logger.debug(f"Applied constraint: {name}")
        except Exception as e:
            logger.warning(f"Could not apply constraint {name}: {e}")

    # 3. Apply indexes
    for name, query in INDEXES:
        try:
            session.run(query)
            logger.debug(f"Applied index: {name}")
        except Exception as e:
            logger.warning(f"Could not apply index {name}: {e}")
            
    logger.info("Neo4j schema constraints and indexes initialized successfully.")

