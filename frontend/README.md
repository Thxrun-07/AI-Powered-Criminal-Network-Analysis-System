# 🎨 Frontend Web Application (Analyst Workspace)

The `frontend/` directory contains the modern, responsive Single Page Application (SPA) designed for forensic investigators, intelligence analysts, and law enforcement officers. Built with **React 19**, **TypeScript (strict mode)**, **Tailwind CSS 3.4**, and **Vite 5**, it provides intuitive real-time graph visualization, suspicious pattern exploration, chain-of-custody verification, and an interactive **Gemini AI Copilot**.

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
    │   └── api.ts               # Fully typed REST API client, domain interfaces, & colors
    │
    └── components/
        ├── Sidebar.tsx          # Navigation rail, theme toggle, and database health badge
        ├── OverviewModule.tsx   # Command Center dashboard with Chart.js analytics
        ├── GraphExplorerModule.tsx # Vis.js ForceAtlas2 interactive canvas with auto-stabilization
        ├── EntitySearchModule.tsx  # Multi-criteria entity search with 1-hop inspection
        ├── ShortestPathModule.tsx  # Ambiguity-safe Dijkstra shortest path finder
        ├── RankingsModule.tsx      # PageRank & Betweenness centrality leaderboards
        ├── PatternInsightsModule.tsx # 10 automated suspicious pattern detectors
        ├── BlockchainModule.tsx    # SHA-256 Merkle chain-of-custody inspector
        ├── CaseRegistryModule.tsx  # Case list, mini-graphs, embed ingestion, & document attachment
        ├── DataIngestionModule.tsx # Multi-source payload upload (JSON, CSV, PDF, text)
        ├── EntityPropertiesTable.tsx # Detailed forensic node property specification table
        ├── FormattedAiMessage.tsx  # Rich markdown tokenizer & renderer for AI chat & insights
        └── Modals.tsx              # Entity 360 dossiers, AI dossiers, and duplicate case alerts
```

---

## 🌟 Key Capabilities & Components

### 1. Interactive ForceAtlas2 Graph Explorer (`GraphExplorerModule.tsx`)
- **Physics-Driven Topology with Post-Stabilization Freeze**: Powered by [Vis.js Network](https://visjs.github.io/vis-network/docs/network/) using `forceAtlas2Based` physics solver.
- **CPU Overheating & Jitter Prevention**: Physics automatically disables upon graph stabilization (`setOptions({ physics: { enabled: false } })`), preventing CPU thrashing and canvas jitter.
- **Dedicated Subgraph Extraction Modes**:
  - 🌐 **Full Ecosystem**: Complete multi-domain intelligence view.
  - 📞 **CDR Telecom Graph**: Exclusively isolates telephone nodes, caller-callee links, durations, and connected cell towers (`#06b6d4` triangle nodes).
  - 👥 **Person Syndicate Network**: Exclusively isolates human suspects with synthesized direct associations, communication volumes, and financial flows, filtering intermediate hardware clutter.
  - 💳 **Financial Money Flows**: Exclusively isolates bank accounts, fund transfer trails, and corporate entities for AML tracking.
- **Dynamic Color-Coded Entity Styling**:
  - **Suspects / Persons**: Blue circular nodes (`#3b82f6`) with roles and degrees.
  - **Phones**: Vibrant orange nodes (`#f97316`) with subscriber annotations.
  - **Bank Accounts**: Emerald nodes (`#10b981`) with balance and holder names.
  - **Vehicles**: Pink nodes (`#ec4899`) with VIN and registration plates.
  - **Locations**: Lime green nodes (`#84cc16`) with addresses and geocodes.
  - **Cell Towers**: Cyan triangle nodes (`#06b6d4`) with sector IDs.
  - **Cases / FIRs**: Red hub nodes (`#ef4444`) connecting multi-jurisdictional incidents.
  - **Organizations**: Forest green nodes (`#059669`).
- **Parallel Edge Consolidation**:
  - Multiple phone calls are aggregated into single `CALLED (nx)` edges displaying total duration and historical timestamps.
  - Multiple bank transfers are aggregated into single `TRANSFERRED_TO (nx)` edges displaying total accumulated sums (`₹X,XXX`) and transaction IDs.
- **Node Specification Table (`EntityPropertiesTable.tsx`)**: Inspects any entity with clear, human-readable labels for IMEIs, carriers, IFSC codes, VINs, crime categories, and communications/financial statistics.

### 2. Docked Gemini AI Copilot & Autonomous Subgraph Extraction
- **Conversational Intelligence**: Docked side drawer enabling investigators to query graph relationships in natural language.
- **Autonomous Subgraph Extraction**: Copilot understands intent prompts (e.g., *"extract only CDR graph"*, *"show person network"*, *"extract financial flow"*) and automatically toggles the canvas into the corresponding focused subgraph view.
- **Rich Markdown Formatting (`FormattedAiMessage.tsx`)**: Renders inline bold emphasis, code spans, bullet lists, and action items cleanly without unparsed raw asterisks.
- **One-Click Prompt Chips**:
  - 📞 *Extract only CDR graph*
  - 👥 *Extract Person graph*
  - 💳 *Extract Financial flow*
  - 🌐 *Reset full graph*
  - 🎯 *Who are the main targets?*
  - 💸 *Money laundering flow*
- **Offline & Rate-Limit Resilience**: If Gemini credits expire or network drops, the backend smoothly switches to an internal heuristic graph analysis engine with zero UI errors.

### 3. Automated Pattern & Centrality Panels (`PatternInsightsModule.tsx`, `RankingsModule.tsx`)
- **Forensic Analytics KPI Banner**: Real-time summary cards for Total AI Detections, Critical Threats, High Threats, and Cross-Case Links.
- **Live Search & Filter**: Instant filtering of detected patterns by title, description, or observed facts.
- **10 Pattern Insight Detectors**: Real-time listing of flagged Hawala rings, mule accounts, SIM swaps, and vehicle convoys with severity badges (`CRITICAL`, `HIGH`, `MEDIUM`).
- **Centrality Leaderboard**: Displays PageRank, Betweenness Centrality, and Degree metrics to identify commanders vs. peripheral mules.
- **Ambiguity-Safe Pathfinding (`ShortestPathModule.tsx`)**: Traces paths between two suspects/entities; renders disambiguation cards when multiple entities share similar names.

### 4. Forensic Evidence & Blockchain Inspector (`BlockchainModule.tsx`)
- **Chain-of-Custody Ledger**: Inspects block indices, timestamps, SHA-256 Merkle roots, and case affiliations.
- **Cryptographic Verification**: Real-time status badge validating ledger integrity via `GET /api/blockchain/verify`.

### 5. Ingestion & Duplicate Case Guard (`CaseRegistryModule.tsx`, `DataIngestionModule.tsx`)
- **Multi-Format Ingestion**: Dedicated Data Ingestion module supporting `.json` case dossiers, `.pdf` FIRs/briefs, CDR `.csv` files, and raw text narratives.
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
| **Graph Visualization**| Vis.js Network | 9.1 | ForceAtlas2 canvas with post-stabilization freeze |
| **Charts** | Chart.js | 4.4 | Centrality and entity distribution histograms |

