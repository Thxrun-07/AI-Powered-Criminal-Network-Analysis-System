# 🛡️ Atlas Criminal Network Intelligence: System Architecture & Operations Guide

> **Official Technical Reference & Operations Runbook**  
> *Authoritative guide covering system functionality, internal mechanics, Neo4j graph topology, AI Copilot, rate-limit resilience, and operational procedures.*

---

## 📑 Table of Contents
1. [System Overview & Mission](#1-system-overview--mission)
2. [What the System Does & How It Does It](#2-what-the-system-does--how-it-does-it)
3. [System Architecture & Data Flow](#3-system-architecture--data-flow)
4. [Hosted LLM: Rate Limits, Quota Expiry & Fallback Engine](#4-hosted-llm-rate-limits-quota-expiry--fallback-engine)
5. [Step-by-Step Instructions: Managing & Replacing API Keys](#5-step-by-step-instructions-managing--replacing-api-keys)
6. [Complete Operational Instructions (Runbook)](#6-complete-operational-instructions-runbook)
7. [Troubleshooting & Common Scenarios](#7-troubleshooting--common-scenarios)

---

## 1. System Overview & Mission

**Atlas** is an end-to-end criminal intelligence and forensic graph analysis platform built for law enforcement, cybercrime cells, and financial fraud intelligence units.

### The Problem It Solves
Criminal syndicates operate across jurisdictional boundaries, frequently splitting actions across burner SIMs, mule bank accounts, encrypted handles, and multiple police stations (FIRs). Traditional relational databases store this data in siloed rows and tables, making it virtually impossible for investigators to see:
- That two separate kidnapping or fraud FIRs share the same burner phone or bank account.
- Multi-hop transaction layering (smurfing/mule account fan-outs).
- High-degree kingpins who never appear at the scene of the crime but control the network via telecom hubs.

### The Solution
Atlas ingests both structured evidence (Call Detail Records CSVs, Bank Transaction CSVs) and unstructured forensic narratives (FIR text files, intelligence briefs), resolves entity identities into a unified Neo4j Knowledge Graph, executes 10 automated algorithmic detectors, and provides:
1. **Interactive Topological Graph Exploration** with tuned elastic physics and deterministic seeds.
2. **Automated Forensic Anomaly Detection** (circular laundering, mule accounts, burner phone relays).
3. **Executive AI Case Summaries** (powered by Hosted LLM).
4. **Interactive Graph AI Copilot** docked in the Graph Explorer, enabling investigators to ask conversational questions about the visible graph when visual inference is difficult.

---

## 2. What the System Does & How It Does It

### 2.1 Unified Data Ingestion & Identity Resolution
- **Input Data**: Raw CSVs (CDR logs with caller, receiver, duration, tower cell; Bank statements with account, transfer amount, timestamp) and TXT files (FIR reports with suspect names, complainant, narrative).
- **Extraction & Normalization**: The `IngestionEngine` normalizes names, cleans phone numbers to standard 10/12-digit formats, standardizes account numbers, and strips duplicate whitespace.
- **Identity Resolution**: Entities are matched against existing nodes in Neo4j. If a phone number or suspect appears in Case A and Case B, Atlas updates the existing node's `case_ids` array rather than duplicating it. This preserves cross-case correlation without phantom duplicates.
- **Atomic Cypher Writes**: Uses batched parameter transactions (`UNWIND $batch AS row ... MERGE`) to write hundreds of nodes and relationships in milliseconds while enforcing unique constraints.

### 2.2 Knowledge Graph Schema
- **Nodes**:
  - `Person`: Suspects, victims, account holders (`name`, `person_id`, `roles`, `case_ids`).
  - `Phone`: Telecom endpoints (`phone_number`, `subscriber_name`, `carrier`, `case_ids`).
  - `BankAccount`: Financial endpoints (`account_number`, `bank_name`, `holder_name`, `case_ids`).
  - `Vehicle`: Transportation assets (`registration_number`, `make_model`, `case_ids`).
  - `FIR`: Case documents and legal filings (`case_id`, `police_station`, `date_filed`, `status`).
  - `IPAddress`: Digital telemetry (`ip_address`, `vpn_flag`, `case_ids`).
  - `Organization`: Corporate entities and banks (`name`, `reg_id`, `case_ids`).
- **Relationships**:
  - `[:CALLED {timestamp, duration, cell_tower}]`
  - `[:TRANSFERRED_TO {amount, timestamp, tx_id}]`
  - `[:OWNS]`, `[:ASSOCIATED_WITH]`, `[:INVOLVES]`, `[:REGISTERED_TO]`

### 2.3 Graph Visualization, Specialized Subgraphs & Edge Aggregation
- **Vis.js Network Canvas**: Interactive, draggable, zoomable WebGL/HTML5 canvas with live physics oscillation to prevent CPU thrashing.
- **Dedicated Subgraph Extraction Modes**:
  - *🌐 Full Ecosystem*: Complete holistic network view.
  - *📞 CDR Telecom Graph*: Filters out bank accounts and non-telecom clutter; isolates caller-callee links, durations, and connected cell tower triangles (`#06b6d4`).
  - *👥 Person Syndicate Network*: Synthesizes human-to-human links, communication frequencies, and financial flows while filtering device and document clutter.
  - *💳 Financial Money Flows*: Isolates bank accounts, wire trails, and corporate organizations for anti-money-laundering tracking.
- **Parallel Edge Aggregation**:
  - Repeated calls between identical phone endpoints are consolidated into single `CALLED (nx)` edges displaying total duration and call history.
  - Repeated bank transfers are consolidated into single `TRANSFERRED_TO (nx)` edges displaying accumulated amount (`₹X,XXX`) and transaction IDs.
- **Node Specification & Explanation Table**: Inspects any entity with human-readable keys for carriers, IMEIs, IFSC codes, registration numbers, and crime categories.
- **Deterministic Numerical Seed**: Derived from the Case ID (e.g. `CASE_008` produces seed `1347895`). Every time you open a case, its layout renders identically and reproducibly.
- **Multi-Structure Layouts**:
  - *Structured Organic (Reduced Bounce)*: Natural cluster formation.
  - *Hierarchical (Top-Down)*: Command-and-control syndicate hierarchy.
  - *Pipeline (Left-to-Right)*: Financial laundering hop progression.
  - *Radial Orbit*: Hub-and-spoke visualization with kingpin in center.

### 2.4 Automated Forensic Detectors (10 Algorithmic Scanners)
The platform runs automated Cypher pattern detectors across the graph:
1. **Shared Telecom Hub**: Discovers phone numbers used by multiple suspects across separate FIRs.
2. **Mule Account Fan-Out**: Identifies high-velocity inflows dispersed to 3+ accounts within 24 hours.
3. **Circular Fund Layering**: Detects funds cycling `A -> B -> C -> A` to disguise proceeds of crime.
4. **Burner Phone Relays**: Identifies pairs of phones activated and discarded in rapid succession.
5. **Cross-Case Syndicate Overlap**: Detects shared assets connecting seemingly unrelated police cases.
6. **High-Frequency Communication Bursts**: Pre-crime coordination spikes.
7. **Dormant Account Reactivation**: Accounts idle for >90 days suddenly receiving large wire amounts.
8. **Geographic Tower Co-location**: Suspects pinging the same cell tower during critical incident windows.
9. **Bridge Operative Identification**: Single persons connecting two otherwise disconnected crime groups.
10. **Layered Smurfing Transfers**: Multiple sub-threshold transactions structured to evade KYC limits.

### 2.5 Centrality Rankings & Shortest Path
- Computes **Degree Centrality**, **Weighted Degree**, and **Cross-Case Relevance** directly via Cypher.
- If Neo4j Graph Data Science (GDS) is unavailable on the host, the UI displays a clean `"Data not found"` message instead of raw server errors.
- Shortest path queries (Dijkstra) compute direct connection paths between suspects and victims.

### 2.6 Dual AI Capabilities: Executive Summary & Graph Copilot
1. **Case Summary**: Synthesizes structured forensic intelligence dossiers (Executive Summary, Risk Level, Modus Operandi, Suspects, Red Flags, Law Enforcement Next Steps) with inline markdown parsing.
2. **Graph AI Copilot & Autonomous Extraction**: A dedicated side-panel docked beside the network graph that accepts natural-language questions. In addition to textual answers, it detects intent commands (e.g., *"extract only CDR graph"*, *"person graph"*, *"extract financial flow"*) and autonomously shifts the canvas into the focused subgraph view.

### 2.7 Cryptographic Blockchain Evidence Chain of Custody
- **SHA-256 Block Hashing**: Every ingested case and individual forensic artifact (FIR, CDR, Bank Statement, Surveillance Log) receives a verifiable cryptographic hash.
- **Merkle Root Validation**: Structural attributes are committed to an immutable ledger (`data/blockchain_ledger.json`).
- **Tamper Detection (`/api/v1/blockchain/verify-*`)**: Cross-verifies active Neo4j graph entities against immutable blockchain Merkle roots to detect unauthorized database tampering.

---

## 3. System Architecture & Data Flow

```mermaid
flowchart TB
    subgraph Presentation_Layer["Presentation Layer (Client Browser - Vanilla JS SPA)"]
        UI["Modern Glass/Neumorphic UI (index.html)"]
        VisJS["Vis.js Graph Network (ForceAtlas2 Engine)"]
        CopilotUI["AI Copilot Side-Box (Interactive Inference)"]
        CaseRegistry["Case Registry & Summary Modals"]
    end

    subgraph API_Gateway["API & Application Layer (FastAPI / Uvicorn)"]
        MainApp["FastAPI Core (app.main)"]
        RouterCases["/api/cases (Registry & Deletion)"]
        RouterGraph["/api/graph & /api/graph/ai-query"]
        RouterInsights["/api/insights & /api/cases/{id}/ai-insights"]
        RouterHealth["/api/health & /api/entities"]
    end

    subgraph Business_Engines["Intelligence & Forensic Services"]
        GraphService["GraphService (Subgraphs, 360 Profiles, Search)"]
        LLMService["LLMService (Hosted LLM + Fallback Engine)"]
        Detectors["ScopedDetectors (10 Forensic Anomaly Detectors)"]
        RankingService["RankingService (Centrality & Relevance)"]
        IngestionEngine["IngestionEngine (CSV/FIR Parsing & Deduplication)"]
    end

    subgraph Storage_and_AI["Data & Intelligence Backends"]
        Neo4j[("Neo4j Graph Database (Aura / Local Bolt)")]
        HostedLLMAPI["Hosted LLM API (Cloud)"]
        FallbackEngine["Intelligent Fallback Demonstration Engine (Internal)"]
    end

    UI -->|HTTP / JSON| MainApp
    VisJS <--> UI
    CopilotUI -->|POST /api/graph/ai-query| RouterGraph
    CaseRegistry -->|GET /api/cases/{id}/ai-insights| RouterInsights

    MainApp --> RouterCases
    MainApp --> RouterGraph
    MainApp --> RouterInsights
    MainApp --> RouterHealth

    RouterGraph --> GraphService
    RouterGraph --> LLMService
    RouterInsights --> LLMService
    RouterInsights --> Detectors
    RouterCases --> RankingService

    GraphService <-->|Cypher Bolt Driver| Neo4j
    Detectors <-->|Pattern Queries| Neo4j
    LLMService -->|Live Context Generation| Neo4j
    LLMService -->|HTTP API Call| HostedLLMAPI
    LLMService -.->|Quota 429 Fallback| FallbackEngine
```

---

## 4. Hosted LLM: Rate Limits, Quota Expiry & Fallback Engine

### 4.1 Understanding Hosted LLM Rate Limits & Quotas
The hosted LLM provider offers API keys with standard rate limits:
- **Requests Per Minute (RPM)**: Standard provider rate window
- **Requests Per Day (RPD)**: Provider-specified daily quota
- **Token Limits**: Provider token context ceiling

When the quota limit is exhausted, the provider API returns:
```json
{
  "error": {
    "code": 429,
    "message": "You exceeded your current quota... Quota exceeded for metric: generate_content_requests",
    "status": "RESOURCE_EXHAUSTED"
  }
}
```

### 4.2 How Atlas Handles Quota Expiration: Zero-Crash Architecture
In most applications, a `429 RESOURCE_EXHAUSTED` causes an HTTP 500 error, broken frontend modals, or red failure text.

**In Atlas, your demonstration and operations NEVER break.** Both `LLMService.generate_case_brief` and `LLMService.answer_graph_query` are wrapped in an autonomous safety harness:

```python
try:
    # 1. Attempt Hosted LLM cloud generation
    response = client.models.generate_content(model="hosted-llm", contents=prompt)
    return format_llm_response(response.text)
except Exception as e:
    # 2. Automatically caught: Logged as a warning, no crash!
    logger.warning(f"LLM API limit reached ({e}). Engaging Demonstration Inference Engine.")
    # 3. Executes deterministic graph topology calculations from live Neo4j database
    return compute_heuristic_graph_inference(session, case_id, question)
```

### 4.3 What the Fallback Engine Does Under the Hood
When the LLM is rate-limited or offline, the fallback engine:
1. Queries the active Neo4j database for top suspects by degree centrality.
2. Identifies communication hubs (telecom lines with the highest call edges).
3. Identifies financial accounts and recent transaction flows.
4. Categorizes the user's question into investigative domains:
   - **Kingpins / Suspects**: Identifies the primary hub, associates, and operational role.
   - **Financial / Laundering**: Identifies monitored accounts, flow patterns, and mule accounts.
   - **Telecom / Burners**: Identifies active subscriber lines and call patterns.
   - **General Inferences / Structure**: Explains the hub-and-spoke structure in clear detective terms.
5. Badges the response with `[Hosted LLM (Demonstration Engine)]` so observers know real graph data is answering their questions.

---

## 5. Step-by-Step Instructions: Managing & Replacing API Keys

When you want to replace an exhausted API key with a fresh one, follow these steps:

### Step 1: Generate a Free API Key
1. Visit your hosted LLM provider console.
2. Sign in with your developer account.
3. Click **"Get API key"** / **"Create API key"** in the console dashboard.
4. Select or create an investigative workspace project.
5. Copy the generated key string.

> [!TIP]
> **Pro Tip for Hackathons and Live Demos**: Create 2 or 3 separate API keys in your provider console. Each project receives its own request quota. Keep the keys handy so you can rotate them if needed.

### Step 2: Configure the API Key in Atlas
You have three methods to set the key (in order of priority):

#### Method A: Inside `.env` File (Recommended & Permanent)
Open the `.env` file in the project root (`c:\Users\shinc\projects\SIH-189-completed\.env`) in any text editor and update:
```env
LLM_API_KEY=your_new_api_key_here
```
Save the file.

#### Method B: Temporary Environment Variable in PowerShell
Before starting the backend, set the variable in your current terminal:
```powershell
$env:LLM_API_KEY="your_new_api_key_here"
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

#### Method C: Linux / Mac Bash
```bash
export LLM_API_KEY="your_new_api_key_here"
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

### Step 3: Verify the Key
Run this quick terminal command to verify your key is active:
```powershell
python -c "from backend.database import db; from backend.services.llm_service import LLMService; s = db.get_session(); res = LLMService.answer_graph_query(s, 'Who are the primary targets?'); print('Model:', res.ai_model); print('Answer preview:', res.answer[:80])"
```
- If it prints `Model: hosted-llm`, the new key is fully active!
- If it prints `Model: hosted-llm (Demonstration Engine)`, the key is either unset or quota-exhausted, and the automatic heuristic engine is safely serving results.

---

## 6. Complete Operational Instructions (Runbook)

### 6.1 Prerequisites
- **Python**: 3.10 to 3.14
- **Node.js**: v18+ and npm (for frontend development)
- **Neo4j**: Neo4j AuraDB (Cloud) or Local Neo4j Desktop / Community Edition (v5.x+)
- **OS**: Windows, macOS, or Linux

### 6.2 Installation
In the project directory (`c:\Users\shinc\projects\SIH-189-completed`):
```powershell
# 1. Install Python backend dependencies
pip install -r requirements.txt

# 2. Install React frontend dependencies
cd frontend
npm install
cd ..
```

### 6.3 Configuring `.env`
Ensure your `.env` file contains your database credentials and API key:
```env
# Neo4j Database Connection
NEO4J_URI=neo4j+s://128dd2a6.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password_here
NEO4J_DATABASE=neo4j

# Application Settings
APP_NAME=Case-Graph-Intelligence-Backend
APP_ENV=development
APP_HOST=127.0.0.1
APP_PORT=8000
LOG_LEVEL=INFO
DEBUG=True

# AI Intelligence
LLM_API_KEY=your_llm_api_key_here
```

### 6.4 Starting the System

#### Option 1: 1-Click Launch (Windows — Recommended)
Double-click [`start_system.bat`](../start_system.bat) from the project root. This will launch:
1. **FastAPI Backend**: `http://127.0.0.1:8000`
2. **React 19 Frontend**: `http://localhost:3000`

#### Option 2: Run in Two Terminals
```powershell
# Terminal 1 (Backend)
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2 (Frontend)
cd frontend
npm run dev
```

Open your browser and navigate to:
👉 **`http://localhost:3000/`** (Interactive React 19 Frontend)  
👉 **`http://127.0.0.1:8000/docs`** (Swagger API Documentation)

### 6.5 Running Tests
To verify all services, endpoints, and deletion handlers:
```bash
# Run all unit tests (fast, mock-based)
python -m pytest tests/unit/ -v

# Run the complete test suite (226 passing tests)
python -m pytest tests/unit tests/integration -q
```

### 6.6 How to Use Each Screen in the Web App

| Screen | Key Features |
|---|---|
| **Command Center** | Live ecosystem metrics, entity breakdown histograms, active FIR investigations, and system health status. |
| **Graph Explorer** | Interactive vis.js canvas with ForceAtlas2 physics, live physics oscillation, layout selector (Organic, Hierarchical, Radial, Pipeline), and docked **AI Copilot** with quick prompt chips. |
| **Entity Search** | 360° entity lookup by name, phone, account number, or VIN. Displays 1-hop neighborhood and properties. |
| **Shortest Path** | Computes shortest evidentiary bridge between any two entities (suspect -> victim) with candidate disambiguation. |
| **Centrality Rankings**| Ranks key operators by Degree, Weighted Degree, or Cross-case Relevance. Cleanly displays "Data not found" if GDS is absent. |
| **Automated Detectors**| Scans for 10 forensic patterns (mule accounts, burner loops, cyclic laundering) + **✨ AI Dossier** synthesis. |
| **Case Registry** | View all filed FIRs, entity counts, status filters, **Embed Case Ingest**, **Attach Document**, and **Per-Case Safe Deletion**. |
| **Data Ingestion** | Multi-format case ingestion supporting `.json` dossiers, `.pdf` FIRs, CDR `.csv`, and raw text with duplicate detection. |
| **Blockchain Ledger** | Verifies cryptographic chain of custody, SHA-256 Merkle roots, and tamper status across all blocks. |

---

## 7. Troubleshooting & Common Scenarios

### Scenario 1: Port 8000 Already in Use
**Error**: `[Errno 10048] error while attempting to bind on address ('127.0.0.1', 8000): only one usage of each socket address is normally permitted`  
**Fix**: Identify and stop the occupying process:
```powershell
# In PowerShell:
$p = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
Stop-Process -Id $p -Force
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

### Scenario 2: Neo4j Cloud Aura Connection Timeout / Defunct Connection
**Error**: `Failed to read from defunct connection IPv4Address... ConnectionResetError(10054)`  
**Explanation**: Cloud Neo4j Aura instances silently close idle connections after a period of inactivity.  
**Fix**: Atlas handles this automatically via its connection pool and automatic reconnection logic in `backend/routers/cases.py`. Refresh the page; the driver will reconnect on the next transaction. If Aura was paused, visit the [Neo4j Aura Console](https://console.neo4j.io/) to unpause the database.

### Scenario 3: "Neo4j Graph Data Science (GDS) library is not installed"
**Fix**: On standard Aura instances or local community editions where GDS is not installed, Atlas automatically intercepts GDS calls and displays a clean `"Data not found"` message instead of an ugly stack trace. If you wish to enable native GDS:
- Deploy Neo4j Enterprise or Neo4j AuraDS.
- In `backend/config.py`, ensure `ENABLE_GDS = True`.

### Scenario 4: Deleting a Single Case Safely
**Feature**: `DELETE /api/cases/{case_id}?confirm=true`  
**Behavior**:
- Permanently deletes nodes owned *exclusively* by that case.
- Preserves nodes shared with other cases (removes the deleted `case_id` from their `case_ids` array).
- Deletes case-specific transaction and communication edges.
- Purges associated blockchain evidence blocks and recalculates the SHA-256 hash chain.
- Click **"Delete"** on any row in the **Case Registry** tab to trigger this workflow.

