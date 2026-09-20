# ⚙️ Backend Core (Graph Intelligence & REST API Engine)

The `backend/` directory houses the core intelligence engine for the **AI-Powered Criminal Network Analysis System**, implemented in Python 3.11+ using **FastAPI** and **Neo4j**. It orchestrates forensic graph persistence, real-time event ingestion, 10 suspicious pattern detectors, ambiguity-safe shortest path calculations, graph centrality rankings, cryptographic chain-of-custody ledgers, and the **Hosted LLM AI Copilot**.

---

## 📂 Architecture Overview

```
backend/
├── config.py              # Environment configuration & Pydantic settings
├── database.py            # Neo4j bolt driver lifecycle & session pool
├── logging_config.py      # Structured JSON logging with automatic PII masking
├── main.py                # FastAPI app initialization, middleware & static routing
│
├── models/                # 📐 Pydantic v2 Schemas & Data Contracts
│   ├── case_input.py      # Case envelope, batch payloads, delete contracts
│   ├── common.py          # Audit timestamps, error structures
│   ├── entity.py          # Entity models (Person, Vehicle, Account, Location, etc.)
│   ├── event.py           # Real-time event streaming delta schemas
│   ├── insights.py        # Suspicious pattern items & AI Copilot request/response
│   ├── path.py            # Shortest path & ambiguity candidate schemas
│   ├── rankings.py        # Graph centrality & PageRank models
│   └── relationship.py    # Directional relationship schemas
│
├── routers/               # 🌐 REST API Endpoints
│   ├── blockchain.py      # Chain-of-custody blocks & cryptographic verification
│   ├── cases.py           # Multi-file case ingestion & deletion
│   ├── events.py          # Real-time event streaming (`POST /api/events`)
│   ├── graph.py           # Topology data, search & AI Copilot endpoint
│   ├── health.py          # Liveness probes & database reset utilities
│   ├── ingest.py          # Unified case data ingestion
│   ├── insights.py        # 10 automated pattern detection queries
│   ├── path.py            # Ambiguity-safe pathfinding
│   └── rankings.py        # PageRank, betweenness, and degree centrality
│
└── services/              # 🧠 Domain Intelligence & Business Logic
│   ├── blockchain_service.py  # SHA-256 Merkle root computation & tamper detection
│   ├── delta_processor.py     # Real-time event application with idempotency
│   ├── evidence_relationship_engine.py # Evidence-backed typed relationship derivation
│   ├── evidence_store.py      # Granular CDR and transaction storage & retrieval
│   ├── llm_service.py         # Hosted LLM with offline heuristic fallback
│   ├── graph_service.py       # Graph retrieval, subgraph extraction & call/tx aggregation
│   ├── graph_writes.py        # Batched atomic Cypher writes with business keys
│   ├── ingestion_engine.py    # Forensic case entity & relation extraction
│   ├── ingestion_service.py   # Transactional case persistence coordinator
│   ├── insights_engine.py     # Pattern detection orchestrator
│   ├── normalizer.py          # E.164 phone & account identifier normalization
│   ├── path_service.py        # Breadth-first shortest path with fuzzy resolution
│   ├── ranking_service.py     # Graph centrality algorithms
│   ├── schema_manager.py      # Neo4j uniqueness constraints & schema indexing
│   ├── schema_mapper.py       # Payload normalization mapper
│   └── scoped_detectors.py    # Case-scoped Cypher queries for all 10 detectors
```

---

## 🛡️ Key Modules & Capabilities

### 1. Specialized Subgraph Extraction & Aggregation (`services/graph_service.py`)
- **Extraction Modes (`GET /api/graph?graph_type=...`)**:
  - `all`: Full ecosystem graph with consolidated parallel links.
  - `cdr`: Telecommunications subgraph isolating Phone nodes, caller-callee links, and connected CellTower antenna sectors.
  - `person`: Person-to-person syndicate network synthesizing direct relationships, communication frequencies, and financial flows while filtering intermediate device clutter.
  - `financial`: Money laundering subgraph isolating BankAccounts, transfer amounts, and corporate entities.
- **Parallel Edge Aggregation**:
  - Consolidates repeated phone calls into single `CALLED (nx)` edges with duration and history.
  - Consolidates repeated fund transfers into single `TRANSFERRED_TO (nx)` edges with accumulated sums (`₹X,XXX`) and transaction details.

### 2. AI Copilot & Intent Extraction (`services/llm_service.py`)
- **Model**: Hosted LLM via cloud API integration.
- **Context Injection**: Dynamically compiles graph statistics (node counts, edge types, top suspects, flagged patterns, recent cases) into the LLM system prompt.
- **Autonomous Subgraph Extraction**: Recognizes user intent (e.g., *"extract only CDR graph"*, *"person graph"*, *"extract financial flow"*) and returns `extracted_graph_type` to switch the UI canvas dynamically.
- **Zero-Downtime Heuristic Fallback**: If the API key is not configured, expired, or rate-limited (`429 Quota Exceeded`), the service automatically switches to a deterministic graph topology analysis algorithm. Requests always succeed with HTTP 200.

### 3. The 10 Automated Suspicious Pattern Detectors (`services/scoped_detectors.py`)
1. **Frequent Caller Patterns**: Identifies anomalous communication frequency spikes.
2. **Burner SIM / Multi-SIM Swapping**: Tracks multiple phone numbers registered to identical IMEI hardware.
3. **Hawala / Financial Laundering Rings**: Traces rapid-movement high-volume funds between accounts.
4. **Mule Account Syndicates**: Pinpoints dormant accounts suddenly receiving sudden large-sum deposits.
5. **Cross-Case Suspect Overlap**: Detects individuals appearing across unrelated multi-jurisdiction FIRs.
6. **Vehicle Convoy Movement**: Detects vehicles sharing identical spatial-temporal routes.
7. **Co-Location at Crime Scenes**: Correlates suspects present at identical cell tower sectors during incident windows.
8. **Meeting & Association Clusters**: Identifies dense cliques of co-accused individuals.
9. **Shell Company / Shared Address Rings**: Uncovers entities sharing registered physical addresses or director nodes.
10. **High-Risk Centrality Hubs**: Combines PageRank and betweenness centrality to isolate syndicate commanders.

### 4. Blockchain Evidence Ledger (`services/blockchain_service.py`)
- Computes SHA-256 Merkle trees across all ingested forensic entities and relations.
- **Dual Persistence & Cloud Sync**: Blocks are committed to local JSON (`data/blockchain_ledger.json`) AND synchronized directly to Neo4j Cloud as `:Block` nodes chained via `[:CHAINED_TO]`.
- **Automatic Orphan Pruning**: When a case is deleted via `DELETE /api/cases/{case_id}`, associated evidence blocks are purged and the SHA-256 hash chain is dynamically recalculated.
- Exposes `GET /api/v1/blockchain/verify` (and `GET /api/blockchain/verify`) to validate the cryptographic integrity of the entire chain of custody.

### 5. High-Integrity Ingestion Pipeline (`services/ingestion_service.py`, `services/ingestion_engine.py`)
- **Atomic ACID Transactions**: All graph entity and relation writes are wrapped within `with session.begin_transaction() as tx:` to guarantee atomic rollback on failure.
- **ID-First Identity Resolution (`people_by_id`)**: Primary key identifiers ensure suspects sharing the same name remain distinct nodes.
- **Zero Hallucination Policy**: Purged hardcoded placeholder entities (e.g. "Amit Sharma"); strict prompting ensures no fictitious identities are introduced.
- **Non-Person Words Filter**: `NON_PERSON_WORDS` filter prevents transaction/event descriptions (like "accounts emptied") from creating ghost Person nodes.
- **PDF Extraction**: Integrated `pdfplumber` and `pypdf` in `routers/ingest.py` to extract text from FIR PDFs and intelligence memos with HTTP 422 handling for scanned/corrupt files.
- **New Graph Relationships**: Added `USES_IP` (`(:Person|SocialHandle)-[:USES_IP]->(:IPAddress)`) and `SURVEILLANCE_PHONE_LOCATED_AT`.
- **Payload Deduplication**: Multi-file ingestion calculates SHA-256 hashes to prevent redundant processing of identical files.

### 6. Real-Time Event Streaming Engine (`services/delta_processor.py`)
- Ingests streaming operational events (arrests, seizures, CDR call records, CCTV sightings) via `POST /api/events`.
- Guarantees idempotent MERGE operations with deterministic business keys without rewriting the graph.

---

## 🏃 Running the Backend Locally

### Option 1: 1-Click Launch (Windows)
Double-click [`run_backend.bat`](../run_backend.bat) or [`start_system.bat`](../start_system.bat) from the root folder.

### Option 2: Command Line
```powershell
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run backend server
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Interactive API documentation will be available at:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Analyst Dashboard**: [http://localhost:8000/](http://localhost:8000/) (serves compiled React 19 build from `frontend/dist/`)

