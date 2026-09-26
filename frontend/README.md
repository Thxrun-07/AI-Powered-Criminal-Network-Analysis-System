# 🎨 Frontend Web Application (Analyst Workspace)

The `frontend/` directory contains the modern, responsive Single Page Application (SPA) designed for forensic investigators, intelligence analysts, and law enforcement officers. Built with **React 19**, **TypeScript (strict mode)**, **Tailwind CSS 3.4**, and **Vite 5**, it provides intuitive real-time graph visualization, suspicious pattern exploration, chain-of-custody verification, and an interactive **AI Copilot (Hosted LLM)**.

---

## 📂 Architecture & Component Structure

```
frontend/
├── index.html                   # SPA HTML entry point
├── package.json                 # Dependencies & build scripts
├── tsconfig.json                # TypeScript strict configuration
├── tsconfig.node.json           # Node configuration for Vite
├── tailwind.config.ts           # Custom Atlas forensic theme & design tokens
├── postcss.config.js            # PostCSS pipeline (Tailwind + Autoprefixer)
├── vite.config.ts               # Vite 5 dev server & backend proxy configuration
│
├── dist/                        # Production build output (bundled via tsc && vite build)
│   ├── index.html
│   └── assets/
│
└── src/
    ├── main.tsx                 # React 19 root bootstrap
    ├── App.tsx                  # Top-level state coordinator, theme, & toast alerts
    ├── index.css                # Tailwind directives & glassmorphic UI components
    ├── vite-env.d.ts            # Ambient TypeScript types
    │
    ├── services/
    │   ├── api.ts               # Fully typed REST API client, domain interfaces, & colors
    │   └── fileStore.ts         # Ingested evidence document archive, CSV table parser & LocalCaseStore
    │
    └── components/
        ├── AuthModule.tsx       # Official badge registration, login modal & session management
        ├── HomeModule.tsx       # Interactive landing portal with live tickers & feature breakdown
        ├── Sidebar.tsx          # TopHeader navigation with 4 grouped workflow workspaces & officer pill
        ├── OverviewModule.tsx   # Command Center dashboard with Chart.js analytics & health probe
        ├── GraphExplorerModule.tsx # Vis.js ForceAtlas2 interactive canvas with live oscillation & high-contrast nodes
        ├── EntitySearchModule.tsx  # Multi-criteria entity search with 1-hop neighborhood inspection
        ├── ShortestPathModule.tsx  # Ambiguity-safe Dijkstra shortest path finder with disambiguation
        ├── RankingsModule.tsx      # PageRank, Betweenness & Degree centrality leaderboards
        ├── PatternInsightsModule.tsx # 10 automated suspicious pattern detectors & KPI cards
        ├── BlockchainModule.tsx    # SHA-256 Merkle chain-of-custody inspector & live tamper audit
        ├── CaseRegistryModule.tsx  # Case management, in-app file previewer, CSV table viewer & safe deletion
        ├── DataIngestionModule.tsx # Multi-source payload upload (PDF/CSV/TXT) with officer attribution
        ├── EntityPropertiesTable.tsx # Detailed forensic node property specification table
        ├── FormattedAiMessage.tsx  # Rich markdown tokenizer & renderer for AI chat & insights
        └── Modals.tsx              # Entity 360 dossiers, AI dossiers, and duplicate case alerts
```

---

## 🌟 Key Capabilities & Components

### 1. Interactive ForceAtlas2 Network Studio (`GraphExplorerModule.tsx`)
- **High-Definition Scaled Node Presentation**:
  - Nodes scaled from tiny 13–16px specks to prominent **20–32px** circles (`Case`: 32, `Person`: 26, `Phone/Accounts/Vehicles`: 24, `CellTower`: 26 triangle).
  - Clear typography (**11.5–15px**) surrounded by a crisp **3–4px text-stroke halo** (`#ffffff` in light mode, `#0f172a` in dark mode) for 100% legibility across all backgrounds.
  - Subtle drop shadows (`shadow: { enabled: true, size: 7 }`) and high-contrast borders for 3D visual depth.
- **Continuous Live Physics Oscillation**:
  - Features gentle to-and-fro node movement giving the graph an organic, breathing representation.
  - Investigators can pause or resume physics anytime via the toolbar toggle button.
- **Dedicated Subgraph Extraction Modes**:
  - 🌐 **Full Ecosystem**: Complete multi-domain intelligence view.
  - 📞 **CDR Telecom Graph**: Exclusively isolates telephone nodes, caller-callee links, durations, and connected cell towers (`#06b6d4` triangle nodes).
  - 👥 **Person Syndicate Network**: Exclusively isolates human suspects with synthesized direct associations, communication volumes, and financial flows, filtering intermediate hardware clutter.
  - 💳 **Financial Money Flows**: Exclusively isolates bank accounts, fund transfer trails, and corporate entities for AML tracking.
- **Parallel Edge Consolidation**:
  - Multiple phone calls are aggregated into single `CALLED (nx)` edges displaying total duration and historical timestamps.
  - Multiple bank transfers are aggregated into single `TRANSFERRED_TO (nx)` edges displaying total accumulated sums (`₹X,XXX`) and transaction IDs.
  - Scaled arrowheads (scale factor 0.6) and thickened edge widths (1.3–2.8px) for instant directional comprehension.
- **Node Specification Table (`EntityPropertiesTable.tsx`)**: Inspects any entity with clear, human-readable labels for IMEIs, carriers, IFSC codes, VINs, crime categories, and communications/financial statistics.

### 2. Officer Authentication & Interactive Home Portal (`AuthModule.tsx`, `HomeModule.tsx`)
- **Official Dynamic RBAC**: Supports officer sign-in and registration using Official Badge Number, Officer Name, Security Passcode, Department, and Clearance Level.
- **Interactive Operations Portal**:
  - Hero banner with live KPI counters (Total Cases, Active FIRs, Tracked Suspects, Verified Blocks, DB Latency).
  - Scroll-triggered animated visual walkthrough demonstrating the data ingestion to intelligence graph pipeline.
  - Quick action launchers to jump directly into the Command Center, Network Studio, or open the authentication modal.

### 3. Grouped 4-Hub Workflow Navigation (`Sidebar.tsx`)
- Replaces flat tab lists with a modern, structured top navigation bar organized into 4 workspaces:
  - 🚀 **Command Center**: Ecosystem overview, Chart.js threat distribution charts, active case feed.
  - 🕸️ **Network Studio**: Vis.js interactive topology explorer and ambiguity-safe Dijkstra shortest pathfinder.
  - 🧠 **Intelligence Hub**: 360° entity search, mathematical centrality rankings (PageRank, Betweenness), and 10 automated Cypher pattern detectors.
  - 📁 **Evidence & Cases**: Case Registry with document studio, multi-format file ingestion, and immutable blockchain ledger.
- **Active Officer Pill**: Displays current officer badge number, department, and a one-click session logout option.

### 4. Evidence Document Studio & In-App CSV Table Viewer (`CaseRegistryModule.tsx`, `fileStore.ts`)
- **In-App File Viewer**: Preview attached evidence documents (`viewingFile` modal) directly inside the Case Registry without leaving the application.
- **Interactive CSV Table Viewer**: Automatically formats raw telecom CDR logs and banking transfer CSVs into clean, interactive, sortable HTML tables.
- **Document Search Bar**: Instantly filter case files by filename, document type, or keywords.
- **Officer Case Attribution**: Filter cases by investigating officer badge number (`uploaded_by`).
- **Persistent Client Storage**: Uploaded files and metadata are cached via `FileStore`, with `LocalCaseStore` providing rapid client-side fallback.

### 5. Docked AI Copilot (Hosted LLM) & Autonomous Subgraph Extraction
- **Conversational Intelligence**: Docked side drawer enabling investigators to query graph relationships in natural language.
- **Autonomous Subgraph Extraction**: Copilot understands intent prompts (e.g., *"extract only CDR graph"*, *"show person network"*, *"extract financial flow"*) and automatically toggles the canvas into the corresponding focused subgraph view.
- **Rich Markdown Formatting (`FormattedAiMessage.tsx`)**: Renders inline bold emphasis, code spans, bullet lists, and action badges (Targets 🎯, Associates 👥, Action Leads 🛡️) cleanly.
- **Zero-Downtime Fallback**: If LLM API credits expire or network drops, the backend smoothly switches to an internal heuristic graph analysis engine with zero UI errors.

### 6. Automated Pattern & Centrality Panels (`PatternInsightsModule.tsx`, `RankingsModule.tsx`)
- **Forensic Analytics KPI Banner**: Real-time summary cards for Total AI Detections, Critical Threats, High Threats, and Cross-Case Links.
- **10 Pattern Insight Detectors**: Real-time listing of flagged Hawala rings, mule accounts, SIM swaps, and vehicle convoys with severity badges (`CRITICAL`, `HIGH`, `MEDIUM`).
- **Centrality Leaderboard**: Displays PageRank, Betweenness Centrality, and Degree metrics to identify commanders vs. peripheral mules.
- **Ambiguity-Safe Pathfinding (`ShortestPathModule.tsx`)**: Traces paths between two suspects/entities; renders disambiguation cards when multiple entities share similar names.

### 7. Forensic Evidence & Blockchain Inspector (`BlockchainModule.tsx`)
- **Chain-of-Custody Ledger**: Inspects block indices, timestamps, SHA-256 Merkle roots, and case affiliations.
- **Cryptographic Verification**: Real-time status badge validating ledger integrity via `GET /api/v1/blockchain/verify-chain`.
- **Live Graph Audit**: Audits live Neo4j entities against on-chain block Merkle roots via `GET /api/v1/blockchain/verify-case/{case_id}`.

### 8. Multi-Source Ingestion & Duplicate Case Guard (`DataIngestionModule.tsx`)
- **Multi-Format Ingestion**: Supports `.pdf` FIRs/briefs, CDR `.csv` files, and raw text narratives with officer badge attribution.
- **Duplicate Upload Protection**: If an investigator attempts to upload an already-existing case, the UI displays a `CaseAlreadyExistsModal` alert guiding them to view the case or use the **"Attach Document"** feature instead.
- **Quick Case Deletion**: "🗑️ Delete Case" button embedded directly in the Case Registry details view.

---

## 🚀 Development & Build Workflow

### Prerequisites
- Node.js (v18+)
- npm (v9+)

### 1. Install Dependencies
```powershell
cd frontend
npm install
```

### 2. Run Vite Development Server (Port 3000)
```powershell
npm run dev
```
The dev server starts at **`http://localhost:3000`** and proxies `/api/*` requests to the FastAPI backend at `http://127.0.0.1:8000`.

### 3. Build Production Bundle
```powershell
npm run build
```
Executes TypeScript compilation (`tsc`) and Vite bundling, outputting optimized static assets into `frontend/dist/`.
The FastAPI backend automatically serves `frontend/dist/` at root `http://localhost:8000/`.

---

## 🛠️ Frontend Tech Stack

| Layer | Technology | Version | Purpose |
| :--- | :--- | :---: | :--- |
| **Framework** | React | 19.x | Component SPA architecture |
| **Language** | TypeScript | 5.6 | Strict type safety, interfaces, zero `any` leaks |
| **Styling** | Tailwind CSS | 3.4 | Utility classes + custom Atlas neomorphic tokens |
| **Bundler** | Vite | 5.x | Lightning-fast HMR and optimized Rollup builds |
| **Graph Visualization**| Vis.js Network | 9.1 | ForceAtlas2 canvas with live physics oscillation |
| **Charts** | Chart.js | 4.4 | Centrality and entity distribution histograms |

