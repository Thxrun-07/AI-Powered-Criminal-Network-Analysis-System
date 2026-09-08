import time
from typing import Any, Dict, List, Optional
import neo4j
from neo4j import GraphDatabase, Driver, Session, exceptions
from backend.config import settings
from backend.logging_config import logger


class Neo4jDatabase:
    def __init__(self):
        self._driver: Optional[Driver] = None

    def connect(self) -> Driver:
        if self._driver is None:
            try:
                driver_kwargs = {
                    "auth": (settings.NEO4J_USERNAME, settings.NEO4J_PASSWORD),
                    "max_connection_pool_size": settings.NEO4J_MAX_CONNECTION_POOL_SIZE,
                    "connection_timeout": 15.0,
                    "max_connection_lifetime": 180,  # Recycle connections every 3 mins to prevent idle cloud drops
                    "keep_alive": True,  # Keep TCP socket alive across cloud NAT/firewalls
                    "liveness_check_timeout": 1.0,  # Probe idle pooled connections before reusing
                }
                if hasattr(neo4j, "NotificationMinimumSeverity"):
                    driver_kwargs["notifications_min_severity"] = getattr(neo4j, "NotificationMinimumSeverity").OFF

                self._driver = GraphDatabase.driver(settings.NEO4J_URI, **driver_kwargs)
                logger.info(f"Connected to Neo4j database at {settings.NEO4J_URI}")
            except Exception as e:
                logger.error(f"Failed to create Neo4j driver: {e}")
                raise e
        return self._driver

    def close(self):
        if self._driver is not None:
            try:
                self._driver.close()
            except Exception:
                pass
            self._driver = None
            logger.info("Neo4j driver connection closed.")

    def reconnect(self) -> Driver:
        """Forces the driver pool to reset and reconnects cleanly."""
        self.close()
        return self.connect()

    def get_session(self, database: Optional[str] = None) -> Session:
        driver = self.connect()
        if database:
            return driver.session(database=database)
        if settings.NEO4J_DATABASE and not settings.NEO4J_URI.startswith("neo4j+s://"):
            return driver.session(database=settings.NEO4J_DATABASE)
        return driver.session()

    def execute_read(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        with self.get_session() as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]

    def execute_write(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        with self.get_session() as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]

    def check_health(self) -> Dict[str, Any]:
        start_time = time.time()
        try:
            with self.get_session() as session:
                result = session.run("CALL dbms.components() YIELD name, versions, edition RETURN name, versions, edition")
                records = list(result)
                record = records[0] if records else None
                latency_ms = round((time.time() - start_time) * 1000, 2)
                
                # Check GDS availability
                gds_available = False
                gds_version = None
                try:
                    gds_res = session.run("CALL gds.version() YIELD version RETURN version")
                    gds_record = gds_res.single()
                    if gds_record:
                        gds_available = True
                        gds_version = gds_record["version"]
                except Exception:
                    gds_available = False

                return {
                    "status": "healthy",
                    "database": settings.NEO4J_DATABASE,
                    "version": record["versions"][0] if record and record["versions"] else "unknown",
                    "edition": record["edition"] if record else "community",
                    "gds_available": gds_available,
                    "gds_version": gds_version,
                    "latency_ms": latency_ms
                }
        except Exception as e:
            logger.warning(f"Health check failed ({e}), attempting auto-reconnect...")
            try:
                self.reconnect()
                with self.get_session() as session:
                    result = session.run("CALL dbms.components() YIELD name, versions, edition RETURN name, versions, edition")
                    records = list(result)
                    record = records[0] if records else None
                    latency_ms = round((time.time() - start_time) * 1000, 2)
                    return {
                        "status": "healthy",
                        "database": settings.NEO4J_DATABASE,
                        "version": record["versions"][0] if record and record["versions"] else "unknown",
                        "edition": record["edition"] if record else "community",
                        "gds_available": False,
                        "gds_version": None,
                        "latency_ms": latency_ms
                    }
            except Exception as retry_err:
                logger.error(f"Health check reconnect retry also failed: {retry_err}")
                return {
                    "status": "unhealthy",
                    "database": settings.NEO4J_DATABASE,
                    "error": str(retry_err),
                    "latency_ms": round((time.time() - start_time) * 1000, 2)
                }


db = Neo4jDatabase()

