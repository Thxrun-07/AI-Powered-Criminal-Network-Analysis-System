# 🧪 Automated Test Suite

The `tests/` directory contains an enterprise-grade automated test suite ensuring forensic accuracy, data model integrity, API stability, PII data masking, and live Neo4j equivalence.

---

## 📁 Directory Structure

```
tests/
├── conftest.py              # Pytest fixtures, mock drivers & tmp_path ledger isolation
├── fixtures/                # Mock case payloads & streaming event envelopes
│
├── unit/                    # 🔬 Isolated Unit Tests (Fast & Offline)
│   ├── test_ai_insights.py               # AI Copilot & heuristic fallback
│   ├── test_batched_relationship_writers.py # Batched Cypher query generators
│   ├── test_blockchain_ledger.py         # Merkle root & SHA-256 chain verification
│   ├── test_case_delete.py               # Cascading case deletion & graph pruning
│   ├── test_data_ingestion_pipeline_audit.py # Pipeline audit: PDF extraction, timestamps, deduplication
│   ├── test_delta_processor.py           # Real-time event application & AST cypher guard
│   ├── test_entity_search.py             # Entity fuzzy search & regex queries
│   ├── test_event_model.py               # Pydantic v2 event schema validation
│   ├── test_insights_10_types.py         # 10 suspicious pattern detector engines
│   ├── test_logging_masking.py           # Phone/Aadhaar/Account PII masking
│   ├── test_rankings.py                  # PageRank & Betweenness calculations
│   ├── test_scoped_detectors.py          # Cypher read-only AST safety validation
│   └── test_shortest_path.py             # Ambiguity-safe pathfinding resolution
│
├── integration/             # 🔗 API & Workflow Integration Tests
│   ├── test_case_identity_ingestion_audit.py # ID-first person identity resolution audit
│   ├── test_events_api.py                # Streaming event ingestion endpoint (`/api/events`)
│   ├── test_freetext_person_ingestion_audit.py # Non-person words filter against ghost nodes
│   ├── test_health_and_reset.py          # Liveness & database reset routes
│   ├── test_ingest_merge.py              # Upsert & deduplication logic
│   ├── test_ingest_ordering.py           # Out-of-order temporal event ingestion
│   ├── test_ingest_replace.py            # Conflict resolution semantics
│   ├── test_legacy_ingest_casedata.py    # Backward compatibility with legacy schema
│   └── test_unified_ingest.py            # Unified ingestion pipeline
│
└── live/                    # ⚡ Live Neo4j Parity Tests (`@pytest.mark.live_neo4j`)
    ├── test_equivalence_harness.py       # Full graph topology parity check
    ├── test_live_neo4j_delta_processor.py # Live Cypher event execution
    ├── test_live_neo4j_events_api.py     # Live REST API to Neo4j ingestion
    ├── test_live_neo4j_legacy_ingest.py  # Live case data ingestion
    ├── test_live_neo4j_scoped_detectors.py # Live pattern execution on live graph
    ├── test_live_neo4j_step0.py          # Base schema & constraints check
    └── test_live_neo4j_step1b.py         # Live multi-case link validation
```

---

## 🚀 Running the Tests

### 1. Run All Standard Unit & Integration Tests (Offline)
These tests require **zero external dependencies** (no Neo4j server or internet needed) and run in **~4 seconds**:

```powershell
pytest tests/unit tests/integration
```

**Output**:
```text
======================= 226 passed in 4.13s =======================
```


### 2. Run Only Unit Tests
```powershell
pytest tests/unit
```

### 3. Run Only Integration Tests
```powershell
pytest tests/integration
```

### 4. Run Live Neo4j Tests (Optional)
When an active Neo4j database is running (e.g. via `docker-compose up -d neo4j`):

```powershell
pytest tests/live -m live_neo4j
```

*(If Neo4j is offline, these tests automatically skip without failing).*

---

## 🛡️ Test Safety & Isolation Guarantees

1. **Blockchain Ledger Protection**: All unit and integration tests redirect the blockchain file to pytest's temporary directory (`tmp_path`), ensuring that production `data/blockchain_ledger.json` is never altered.
2. **PII Masking Safeguards**: Unit tests verify that sensitive personal data (phone numbers, account numbers, government IDs) are automatically masked in log outputs.
3. **AST Cypher Read-Only Guard**: Abstract Syntax Tree (AST) analysis tests confirm that detector queries in `backend/services/scoped_detectors.py` strictly perform read-only graph queries and contain zero write operations.
