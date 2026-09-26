# Crime & Case Graph Intelligence Platform — Complete System Summary

## 1. What This System Actually Does

The **Crime & Case Graph Intelligence Platform** serves as an enterprise-grade **Database & Graph Intelligence Layer** designed for law enforcement agencies, cybercrime cells, and forensic investigative units. It ingests both structured digital evidence (telecom CDRs, bank transaction logs, cell tower dumps) and unstructured forensic narratives (FIR reports, surveillance notes, intelligence briefings), transforming them into a highly interconnected, queryable **Neo4j knowledge graph** exposed via a high-performance **FastAPI REST API**.

### Primary Operational Capabilities:
1. **Officer Authentication & Dynamic RBAC (`/api/auth/*`)**:
   - Secure officer portal with badge ID, username, and department registration.
   - Salted SHA-256 password security, dynamic session persistence in `data/users.json`, and automatic officer attribution stamped on every ingested case and evidence artifact.
2. **Multi-Modal Evidence Ingestion**:
   - **Bulk Ingestion (`POST /api/cases/ingest`)**: Idempotent Cypher `MERGE`-based ingestion accepting nested case JSON envelopes (`CaseEnvelope`, `CaseData`).
   - **Unified Forensic Parser (`POST /api/v1/ingest`, `POST /api/v1/ingest/text`)**: Ingests folders of mixed files (unstructured FIR text, CDR CSVs, bank CSVs) or raw text payloads directly into graph entities.
3. **Evidence Document Studio & In-App CSV Viewer**:
   - Client-side and server-side evidence registry with real-time file preview for text, JSON, and parsed CSV tables.
   - Investigator filtering, badge search, and full evidence chain-of-custody tracking.
4. **Incremental Real-Time Event Processing (`POST /api/events/batch`)**:
   - High-throughput batch API processing up to 5,000 events atomically in a single Neo4j transaction across 15 canonical event types (`PERSON_UPSERT`, `COMMUNICATION`, `TRANSACTION`, `SURVEILLANCE_LOG`, etc.).
   - Tracks touched graph entities to dynamically trigger only the relevant forensic insight detectors.
5. **10 Automated Forensic Pattern Detectors**:
   - Runs deterministic graph pattern algorithms detecting money laundering chains, burner phone networks, fund pooling (high fan-in), fund dispersal (high fan-out), shared criminal infrastructure, cross-case syndicate links, and physical co-location events.
6. **Cryptographic Blockchain Evidence Chain of Custody (`/api/v1/blockchain/*`)**:
   - Every ingested case and forensic document (FIR, CDR, Bank Statement, Surveillance Log) is cryptographically hashed (SHA-256) and committed as a verifiable block in an immutable ledger with Merkle root verification.
   - Built-in tamper-detection audits live Neo4j graph state against on-chain Merkle roots.
7. **AI Forensic Intelligence Dossier (`GET/POST /api/cases/{case_id}/ai-insights`)**:
   - Gathers multi-hop subgraph context and synthesizes an executive intelligence assessment using **Hosted LLM** (with automatic heuristic fallback when offline).
   - Generates executive summaries, modus operandi analysis, key target suspects, critical anomalies, and actionable next steps under law enforcement procedures (e.g., Section 91 CrPC notices, tower dump warrants).
8. **Ambiguity-Safe Shortest-Path Discovery (`GET /api/cases/shortest-path`)**:
   - Discovers multi-hop relational chains connecting suspects to victims across communications, financial transactions, co-locations, and asset ownership.
   - Provides safe candidate disambiguation when multiple individuals share identical names or aliases without guessing.
9. **Graph Centrality & Kingpin Rankings (`GET /api/cases/rankings`)**:
   - Evaluates network influence and identifies syndicate orchestrators using Degree, Weighted Degree, Cross-Case Relevance, and Neo4j Graph Data Science (GDS) PageRank & Betweenness Centrality.
10. **Interactive 4-Hub Visualizer Dashboard (`GET /`)**:
   - Comprehensive multi-module interface ("Atlas") organized into 4 workflow hubs: Command Center (Home/Overview), Network Studio (Graph Canvas with continuous live physics oscillation), Intelligence Hub (AI Copilot, Patterns, Shortest Path, Centrality), and Evidence & Cases (Registry, Ingestion, Blockchain Ledger).

---

## 2. Professional Directory Structure

```
SIH_189_V2/
├── .env                                # Active environment configuration (Neo4j URI, credentials, ports)
├── .env.example                        # Template environment variables with documentation
├── .gitignore                          # Protected version control exclusions (.env, virtualenvs, cache)
├── Dockerfile                          # Container image definition for FastAPI backend
├── docker-compose.yml                  # Multi-container orchestration (Neo4j 5 Community + FastAPI backend)
├── pytest.ini                          # Test configuration (pythonpath=., testpaths, markers)
├── requirements.txt                    # Pinned Python dependencies (FastAPI, Neo4j, Pydantic v2, GenAI, pdfplumber)
├── start_system.bat                    # 1-Click launcher for both Backend (8000) & Frontend (3000)
├── run_backend.bat                     # 1-Click launcher for FastAPI backend
├── run_frontend.bat                    # 1-Click launcher for Vite React frontend
├── README.md                           # Quickstart showcase, architecture diagrams, and evolution guide
├── SUMMARY.md                          # Comprehensive technical system specification (this document)
│
├── frontend/                           # React 19 + TypeScript + Tailwind CSS Frontend
│   ├── src/                            # Modern SPA component architecture
│   │   ├── components/                 # AuthModule, HomeModule, Sidebar, Overview, GraphExplorer, CaseRegistry, etc.
│   │   ├── services/                   # api.ts (REST client & types), fileStore.ts (in-browser evidence store)
│   │   ├── App.tsx                     # Top-level state coordinator & routing
│   │   └── main.tsx                    # React 19 bootstrap
│   ├── dist/                           # Compiled production build served by FastAPI
│   └── package.json                    # Frontend dependencies & build commands
│
├── backend/                            # Core Intelligence Application Package
│   ├── __init__.py                     # Package marker
│   ├── main.py                         # FastAPI app entrypoint, CORS, global error handlers, frontend mount
│   ├── config.py                       # Pydantic Settings management (.env loader)
│   ├── database.py                     # Neo4j driver pool lifecycle, sessions, and live health probe
│   ├── logging_config.py               # Structured logging with automatic PII & credential masking
│   │
│   ├── models/                         # Pydantic v2 Data Models & Schema Contracts
│   │   ├── __init__.py                 # Public model exports
│   │   ├── case_input.py               # Ingestion payloads (CaseData, CaseEnvelope, IngestResponse, CaseDelete)
│   │   ├── common.py                   # Audit fields, timestamps, and error response models
│   │   ├── entity.py                   # Models for 13 canonical entities (Person, Phone, BankAccount, etc.)
│   │   ├── event.py                    # Incremental event models (EventBatch, GraphEvent, EventProcessingResult)
│   │   ├── ingestion_models.py         # Consolidated models for multi-file/CSV/PDF extraction
│   │   ├── insights.py                 # Forensic insight schemas, AI Copilot & GraphAIChatResponse
│   │   ├── path.py                     # Shortest path response and AmbiguityCandidate models
│   │   ├── rankings.py                 # Centrality ranking responses and metric schemas
│   │   └── relationship.py             # Communication, Transaction, Surveillance, and History models
│   │
│   ├── services/                       # Domain Business Logic & Graph Algorithms
│   │   ├── __init__.py                 # Service exports
│   │   ├── auth_service.py             # PBKDF2/SHA-256 password hashing & officer session state
│   │   ├── blockchain_service.py       # Cryptographic evidence ledger, Merkle roots, and chain verification
│   │   ├── delta_processor.py          # Atomic incremental event batch processor with rollback safety
│   │   ├── evidence_relationship_engine.py # Evidence-backed typed relationship derivation
│   │   ├── evidence_store.py           # Granular CDR and transaction storage & retrieval
│   │   ├── llm_service.py              # Forensic AI intelligence brief synthesis via Hosted LLM
│   │   ├── graph_service.py            # Subgraph extraction (CDR/Person/Financial), call/tx aggregation, dossiers
│   │   ├── graph_writes.py             # Single source of truth for all Neo4j Cypher MERGE/UNWIND statements
│   │   ├── ingestion_engine.py         # Multi-format parser with clean_person_name regex & 40+ non-person filter
│   │   ├── ingestion_service.py        # Atomic case ingestion engine with ACID transaction rollback
│   │   ├── insights_engine.py          # Reference implementations for all 10 forensic insight detectors
│   │   ├── normalizer.py               # E.164 phone & account identifier normalization
│   │   ├── path_service.py             # Shortest path traversal with case-insensitive name/alias resolution
│   │   ├── ranking_service.py          # Degree, Weighted Degree, Cross-Case, and GDS centrality algorithms
│   │   ├── schema_manager.py           # Database constraints and index initializer for all node labels
│   │   ├── schema_mapper.py            # Schema adapter mapping consolidated extraction into CaseData
│   │   └── scoped_detectors.py         # Dependency-dispatched scoped detectors for incremental updates
│   │
│   ├── routers/                        # REST API Route Endpoints
│   │   ├── __init__.py                 # Router exports
│   │   ├── auth.py                     # POST /api/auth/signup, POST /api/auth/login, GET /api/auth/users
│   │   ├── blockchain.py               # GET /api/v1/blockchain/* (Ledger, chain audit, case verification)
│   │   ├── cases.py                    # POST /api/cases/ingest, GET /api/cases, DELETE /api/cases/{case_id}
│   │   ├── events.py                   # POST /api/events/batch (Atomic incremental event processing)
│   │   ├── graph.py                    # GET /api/graph, GET /api/entities/search, GET /api/entities/{id}
│   │   ├── health.py                   # GET /api/health (Database connectivity & health probe)
│   │   ├── ingest.py                   # POST /api/v1/ingest, POST /api/v1/ingest/text (Unified file upload)
│   │   ├── insights.py                 # GET /api/cases/{case_id}/insights, GET /api/cases/{case_id}/ai-insights
│   │   ├── path.py                     # GET /api/cases/shortest-path (Ambiguity-safe pathfinding)
│   │   └── rankings.py                 # GET /api/cases/rankings (Suspect centrality rankings)
│   │
│   └── templates/                      # Fallback Template
│       └── index.html                  # Standalone fallback dashboard
│
├── data/                               # Persistent Storage
│   ├── blockchain_ledger.json          # Cryptographic evidence chain-of-custody ledger
│   └── users.json                      # Registered officer credentials with salted SHA-256 hashes
│
├── docs/                               # Detailed Technical Guides
│   ├── EVENTS_API.md                   # Incremental Events API specification & integration contract
│   ├── SUMMARY.md                      # Comprehensive system summary (this document)
│   └── SYSTEM_ARCHITECTURE_AND_OPERATIONS_GUIDE.md # Operations runbook & deployment guide
│
├── dataset/                            # Realistic Forensic Verification Payloads
│   ├── case_001_homicide.json          # Complete homicide case (FIR, CDR calls, bank transfers, CCTV)
│   ├── case_002_fraud.json             # Corporate fraud case with cross-case overlapping entities
│   └── envelope_sample.json            # Standard envelope wrapper example for automated pipelines
│
└── tests/                              # Automated Test Suite (228 Tests Passing)
    ├── conftest.py                     # Mock Neo4j driver, sessions, TestClient, test ledger isolation
    ├── fixtures/                       # Deterministic test payloads
    │   ├── case_edge_batching.json
    │   └── equivalence_scenarios.json
    ├── unit/                           # Isolated Unit Tests (Fast, mocked dependencies)
    │   ├── test_ai_insights.py
    │   ├── test_auth.py                # Officer signup, login, password salt-hash, and user listing
    │   ├── test_batched_relationship_writers.py
    │   ├── test_blockchain_ledger.py
    │   ├── test_case_delete.py
    │   ├── test_data_ingestion_pipeline_audit.py
    │   ├── test_delta_processor.py
    │   ├── test_entity_search.py
    │   ├── test_event_model.py
    │   ├── test_insights_10_types.py
    │   ├── test_logging_masking.py
    │   ├── test_rankings.py
    │   ├── test_scoped_detectors.py
    │   └── test_shortest_path.py
    ├── integration/                    # API & Ingestion Pipeline Tests
    │   ├── test_case_identity_ingestion_audit.py
    │   ├── test_events_api.py
    │   ├── test_freetext_person_ingestion_audit.py
    │   ├── test_health_and_reset.py
    │   ├── test_ingest_merge.py
    │   ├── test_ingest_ordering.py
    │   ├── test_ingest_replace.py
    │   ├── test_legacy_ingest_casedata.py
    │   └── test_unified_ingest.py
    └── live/                           # Live Neo4j Integration & Parity Verification
        ├── test_equivalence_harness.py
        ├── test_live_neo4j_delta_processor.py
        ├── test_live_neo4j_events_api.py
        ├── test_live_neo4j_legacy_ingest.py
        ├── test_live_neo4j_scoped_detectors.py
        ├── test_live_neo4j_step0.py
        └── test_live_neo4j_step1b.py

```

---

## 3. The 13 Canonical Graph Node Labels & Relationships

### Node Labels
Every node in the graph carries a deterministic primary identifier, a uniqueness constraint, and standardized audit fields (`case_ids`, `source_record_ids`, `created_at`, `updated_at`):

| # | Node Label | Primary Identifier | Description |
| :- | :--- | :--- | :--- |
| 1 | **`Case`** | `case_id` | Top-level case container (`CASE-2024-001`) with investigator, jurisdiction, and status |
| 2 | **`FIR`** | `fir_id` | First Information Report / Police registration with penal sections and complainant |
| 3 | **`Person`** | `person_id` | Individual (Suspect, Victim, Witness, Associate) with aliases, roles, and DOB |
| 4 | **`Phone`** | `phone_number` | Mobile phone subscriber with IMEI hardware identifier and service carrier |
| 5 | **`BankAccount`** | `account_number` | Bank account with bank name, branch, IFSC, and account holder name |
| 6 | **`Vehicle`** | `vin` | Motor vehicle identified by VIN/Chassis number and license plate |
| 7 | **`SocialHandle`** | `handle_id` | Social platform account (Telegram, WhatsApp, Signal, Instagram, Twitter) |
| 8 | **`IPAddress`** | `ip_address` | Network IPv4/IPv6 address, ASN identifier, and ISP provider |
| 9 | **`Location`** | `location_id` | Physical location, crime scene, or landmark with GPS coordinates and address |
| 10 | **`CellTower`** | `cell_tower_id` | Telecom cellular transmission tower with LAC-CID identifier and coordinates |
| 11 | **`Transaction`** | `transaction_id` | Individual financial payment or wire transfer record |
| 12 | **`PriorCase`** | `prior_case_id` | Historical court record, past criminal offense, or conviction archive |
| 13 | **`SourceRecord`** | `source_record_id` | Forensic evidence artifact (CDR extract, bank statement, surveillance memo) |

### Graph Relationships
- `(Person)-[:OWNS]->(Phone | BankAccount | Vehicle)`
- `(Person)-[:HAS_HANDLE]->(SocialHandle)`
- `(Phone)-[:CALLED {call_id, timestamp, duration_seconds, cell_tower}]->(Phone)`
- `(BankAccount)-[:TRANSFERRED_TO {transaction_id, amount, currency, timestamp}]->(BankAccount)`
- `(Person | Phone | Vehicle)-[:LOCATED_AT {timestamp, activity_description}]->(Location)`
- `(CellTower)-[:LOCATED_AT]->(Location)`
- `(Person)-[:HAS_PRIOR_CASE]->(PriorCase)`
- `(Case)-[:HAS_FIR]->(FIR)`
- `(Case)-[:INVOLVES]->(All Entities & Records)`
- `(FIR)-[:INVOLVES]->(Person)`

---

## 4. The 10 Automated Forensic Insight Detectors

When a case is ingested or queried, the system evaluates 10 forensic patterns:

1. **`SHARED_ENTITY`**: Flags when an identical phone number, vehicle VIN/plate, bank account, social handle, or IP address appears across multiple independent investigations.
2. **`CROSS_CASE_LINK`**: Detects direct communication (phone calls) or financial transactions between entities registered in distinct cases.
3. **`BRIDGE_NODE`**: Identifies broker or coordinator suspects holding operational assets across multiple criminal syndicates.
4. **`TRANSFER_CHAIN`**: Detects multi-hop layering in financial transactions ($Account\ A \to Account\ B \to Account\ C$) characteristic of money laundering.
5. **`HIGH_FAN_IN`**: Flags fund pooling or extortion collection accounts receiving transactions/calls from $\ge 3$ distinct sources.
6. **`HIGH_FAN_OUT`**: Flags dispersal accounts distributing funds or communications to $\ge 3$ distinct targets.
7. **`INFRASTRUCTURE_REUSE`**: Detects rotating burner SIM cards on a single physical phone IMEI, or multiple suspects operating from a shared IP address.
8. **`POSSIBLE_CO_LOCATION`**: Detects multiple suspects or surveillance targets logged at the same geographic location within close temporal proximity.
9. **`CROSS_DOMAIN_PATH`**: Uncovers correlated multi-domain interactions (e.g. a phone call immediately followed by a wire transfer between associated accounts).
10. **`PRIOR_CASE_LINK`**: Connects active suspects to historical convictions, previous FIRs, or past court records.

---

## 5. Incremental Event Processing Pipeline

For high-velocity streaming environments, `POST /api/events/batch` allows pushing discrete operational logs without resubmitting complete case payloads:

```
EventBatch -> Pydantic Validation -> DeltaProcessor -> graph_writes statements
           -> Single Write Transaction (Atomic) -> Touched Entity Tracking
           -> Scoped Insight Dispatcher -> EventProcessingResult
```

- **Batch Size**: 1 to 5,000 events per request.
- **Atomicity**: The entire batch is applied in one transaction; any failure triggers an automatic rollback.
- **Scoped Performance**: Evaluates only the insight detectors whose entity types were modified by the batch, reducing Cypher evaluation overhead by over 80%.

---

## 6. Blockchain Evidence Chain of Custody

The platform incorporates an immutable, tamper-evident audit ledger (`app/services/blockchain_service.py`):
- **Evidence Hashing**: Every ingested case and forensic document receives a unique SHA-256 evidence fingerprint.
- **Merkle Tree**: Structured attributes are compiled into a Merkle root representing the exact forensic state at ingestion.
- **Chain Integrity (`GET /api/v1/blockchain/verify-chain`)**: Traverses block hashes to ensure zero tampering across block links.
- **Case Audit (`GET /api/v1/blockchain/verify-case/{case_id}`)**: Audits current live Neo4j graph entities against on-chain block Merkle roots to detect out-of-band database modifications.

---

## 7. Officer Authentication & Dynamic RBAC

The platform provides a secured authentication and role-based access control engine (`routers/auth.py`, `services/auth_service.py`):
- **Officer Signup & Login**:
  - `POST /api/auth/signup`: Registers officers with badge ID, username, and department.
  - `POST /api/auth/login`: Authenticates officers using salted SHA-256 password verification and establishes session state.
  - `GET /api/auth/users`: Lists registered investigative officers and status.
- **Dynamic Credential Store**: Persists user credentials securely in `data/users.json` using unique per-user cryptographic salts.
- **Investigator Attribution**: All newly ingested cases, digital evidence files, and real-time events record the authenticated officer's badge/username for immutable audit compliance.

---

## 8. Evidence Document Studio & CSV Table Viewer

Investigators can view and inspect original source evidence files directly within the platform:
- **In-App Document Viewer**: Provides an interactive side-drawer in the Case Registry for instant preview of uploaded forensic files (FIR text, CDR CSVs, bank statements, CCTV surveillance logs).
- **Interactive CSV Table Viewer**: Automatically parses comma-delimited data (e.g. call records, financial transfers) into formatted tabular views with header sorting and line numbering.
- **Browser & Server Persistence**: Hybrid architecture leveraging `services/fileStore.ts` for instant client-side rendering alongside backend case persistence.
- **Officer-Scoped Evidence Filtering**: Filter evidence and cases by assigned investigator badge ID or name.

---

## 9. Dual AI Intelligence (Hosted LLM)

### 9.1 Case Intelligence Dossier (`GET/POST /api/cases/{case_id}/ai-insights`)
1. Subgraph context (suspect profiles, phone connections, transaction paths, locations) is queried from Neo4j.
2. Formatted data is submitted to **Hosted LLM** with structured JSON output instructions.
3. The response synthesizes an authoritative intelligence assessment:
   - **Executive Summary**: Strategic overview of syndicate hierarchy and operational scope.
   - **Risk Level**: `CRITICAL`, `HIGH`, `MEDIUM`, or `LOW`.
   - **Modus Operandi**: Breakdown of observed methodologies (layering, burner relays, coercion).
   - **Key Suspects**: Primary targets with specific evidence linkage.
   - **Critical Anomalies**: Investigative red flags discovered in graph telemetry.
   - **Actionable Leads**: Concrete procedural steps (e.g., Section 91 CrPC notices, CDR tower dumps).
4. **Heuristic Fallback**: If the LLM is offline or unconfigured, an intelligent heuristic engine synthesizes a baseline dossier from graph topology.

### 9.2 Interactive Graph AI Copilot (`POST /api/graph/ai-query`)
- Docks directly beside the interactive Vis.js graph canvas in the Analyst Dashboard ("Atlas").
- Allows investigators with zero graph or Cypher background to converse with the topology in plain English.
- Accepts targeted questions (*"Who is the kingpin?"*, *"Explain money flow"*, *"Trace burner phones"*) or 1-click entity inspections (*"Analyze connections of Devendra Sharma"*).
- Gathers active subgraph topology, top suspects by degree, communication endpoints, and fund transfers, formulating direct deductive conclusions and immediate field recommendations.

### 9.3 Managing & Replacing API Keys When Quota / Credits Expire
- **Rate Limits**: Hosted LLM providers enforce rate limits (e.g. requests per minute, daily limits). Once exceeded, requests throw HTTP 429 `RESOURCE_EXHAUSTED`.
- **Replacing the Key**:
  1. Generate a new API key from your hosted LLM provider console.
  2. Update `LLM_API_KEY=...` in `.env`, or override via terminal (`$env:LLM_API_KEY="..."` on Windows or `export LLM_API_KEY="..."` on Linux/macOS).
  3. Restart or hot-reload Uvicorn.
- **Zero-Downtime Guarantee**: If the key is not replaced or offline, Atlas **never crashes or returns 500 errors**. The backend automatically intercepts the quota exception and seamlessly switches to the internal **Demonstration Heuristic Graph Inference Engine**, calculating answers directly from live Neo4j degree centrality, transaction paths, and communication hubs.

---

## 10. REST API Quick Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Serves interactive single-page Analyst Dashboard ("Atlas") |
| `GET` | `/api/health` | System health probe, Neo4j connectivity, and GDS availability |
| `POST` | `/api/auth/signup` | Register officer with badge, username, and department |
| `POST` | `/api/auth/login` | Officer login with salted SHA-256 verification & session state |
| `GET` | `/api/auth/users` | List registered investigative officers |
| `POST` | `/api/cases/ingest` | Idempotent bulk case ingestion (`mode=merge` or `mode=replace`) |
| `GET` | `/api/cases` | List all ingested cases with pagination and status filter |
| `GET` | `/api/cases/{case_id}` | Case summary with entity breakdown and metadata |
| `DELETE`| `/api/cases/{case_id}` | Delete case and detach/remove exclusive entities |
| `DELETE`| `/api/cases/reset` | Development utility: clear all database graph elements |
| `POST` | `/api/events/batch` | Atomic incremental event batch ingestion (1–5000 events) |
| `POST` | `/api/v1/ingest` | Multi-file upload (unstructured FIR text, CDR CSV, Bank CSV) |
| `POST` | `/api/v1/ingest/text` | Direct unstructured text payload ingestion |
| `GET` | `/api/cases/{case_id}/insights` | Fetch detected forensic patterns for a case |
| `GET` | `/api/insights/delta` | Fetch cross-case delta insights (shared entities, bridges) |
| `GET` | `/api/cases/{case_id}/ai-insights` | Synthesize forensic AI intelligence assessment |
| `POST` | `/api/graph/ai-query` | Interactive Graph AI Copilot natural language deduction |
| `GET` | `/api/cases/shortest-path` | Ambiguity-safe shortest path between suspect and victim |
| `GET` | `/api/cases/rankings` | Suspect centrality rankings (Degree, Weighted, GDS) |
| `GET` | `/api/graph` | Subgraph retrieval for visual graph rendering |
| `GET` | `/api/entities/search` | Full-text search across all entities (names, phones, accounts) |
| `GET` | `/api/entities/{id}` | Entity 360° profile with 1-hop neighborhood |
| `GET` | `/api/v1/blockchain/ledger` | Fetch immutable evidence ledger blocks |
| `GET` | `/api/v1/blockchain/verify-chain`| Cryptographic verification of full ledger integrity |
| `GET` | `/api/v1/blockchain/verify-case/{case_id}` | Audit case graph evidence against blockchain |

---

## 11. Automated Testing Architecture

The platform features a 228-test automated verification suite organized into clear tiers:

```bash
# Run complete test suite (unit + integration + live skips)
pytest

# Run fast unit tests only (< 1 second)
pytest tests/unit

# Run API integration tests
pytest tests/integration

# Run live Neo4j tests (requires running instance at bolt://localhost:7687)
pytest tests/live
```

- **Unit Tests (`tests/unit/`)**: Verify data models, PII masking filters, batched Cypher writers, scoped detectors, shortest-path alias resolution, blockchain ledger operations, and AI fallback generation using isolated mocks.
- **Integration Tests (`tests/integration/`)**: Test end-to-end FastAPI endpoints, bulk ingestion ordering, replace cleanup safety, event batch atomicity, and multi-file text parsing.
- **Live Tests (`tests/live/`)**: Verify formal equivalence between bulk and incremental ingestion against a live Neo4j database, testing Cypher execution plans, schema constraints, and GDS procedures.
