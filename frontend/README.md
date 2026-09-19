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
        └── Modals.tsx              # Entity 360 dossiers, AI dossiers, and duplicate case alerts
```

---

## 🌟 Key Capabilities & Components

### 1. Interactive ForceAtlas2 Graph Explorer (`GraphExplorerModule.tsx`)
- **Physics-Driven Topology with Post-Stabilization Freeze**: Powered by [Vis.js Network](https://visjs.github.io/vis-network/docs/network/) using `forceAtlas2Based` physics solver.
- **CPU Overheating & Jitter Prevention**: Physics automatically disables upon graph stabilization (`setOptions({ physics: { enabled: false } })`), preventing CPU thrashing and canvas jitter.
- **Dynamic Node & Edge Styling**:
  - **Suspects / Persons**: Red circular nodes with threat badges (`#ef4444`).
  - **Vehicles**: Amber nodes with registration identifiers (`#f59e0b`).
  - **Bank Accounts**: Emerald nodes with financial transaction volumes (`#10b981`).
  - **Locations / Cell Towers**: Cyan nodes with antenna sectors (`#06b6d4`).
  - **Cases / FIRs**: Violet central hub nodes connecting multi-jurisdictional incidents (`#8b5cf6`).
  - **Edges**: Color-coded directional relations (`TRANSFERRED_FUNDS`, `CALLED`, `ASSOCIATE_OF`, `LOCATED_AT`, `REGISTERED_TO`, `USES_IP`).
- **Interactive Multi-Hop Traversal**: Single-click inspects metadata, double-click expands immediate neighbors, and right-click launches shortest path queries.

### 2. Docked Gemini AI Copilot Panel
- **Conversational Intelligence**: Docked side drawer enabling investigators to query graph relationships in natural language.
- **One-Click Prompt Chips**:
  - 🔍 *Summarize Key Suspects*
  - 💸 *Find Financial Laundering Rings*
  - 🌐 *Explain Cross-Case Connections*
  - 👑 *Who is the Central Kingpin?*
- **Offline & Rate-Limit Resilience**: If Gemini credits expire or network drops, the backend smoothly switches to an internal heuristic graph analysis engine with zero UI errors.

### 3. Automated Pattern & Centrality Panels (`PatternInsightsModule.tsx`, `RankingsModule.tsx`)
- **10 Pattern Insight Detectors**: Real-time listing of flagged Hawala rings, mule accounts, SIM swaps, and vehicle convoys with severity badges (`CRITICAL`, `HIGH`, `MEDIUM`).
- **Centrality Leaderboard**: Displays PageRank, Betweenness Centrality, and Degree metrics to identify commanders vs. peripheral mules.
- **Ambiguity-Safe Pathfinding (`ShortestPathModule.tsx`)**: Traces paths between two suspects/entities; renders disambiguation cards when multiple entities share similar names.

### 4. Forensic Evidence & Blockchain Inspector (`BlockchainModule.tsx`)
- **Chain-of-Custody Ledger**: Inspects block indices, timestamps, SHA-256 Merkle roots, and case affiliations.
- **Cryptographic Verification**: Real-time status badge validating ledger integrity via `GET /api/v1/blockchain/verify`.

### 5. Ingestion & Duplicate Case Guard (`CaseRegistryModule.tsx`, `DataIngestionModule.tsx`)
- **Multi-Format Ingestion**: Supports `.json` case dossiers, `.pdf` FIRs/briefs, CDR `.csv` files, and raw text narratives.
- **Duplicate Upload Protection**: If an investigator attempts to upload an already-existing case, the UI displays a `CaseAlreadyExistsModal` alert guiding them to view the case or use the **"Attach Document"** feature instead.

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

