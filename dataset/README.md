# 📂 Forensic Evidence Datasets

The `dataset/` directory contains structured, realistic forensic investigation datasets used to benchmark graph ingestion, pattern detection, cross-case link discovery, and blockchain evidence integrity verification.

---

## 📁 Directory Contents

```
dataset/
├── case_001_homicide.json   # Multi-source homicide case (FIR, CDR, Bank, CCTV)
├── case_002_fraud.json      # Corporate money laundering & Hawala fraud ring
├── envelope_sample.json     # Standard streaming event envelope schema
└── README.md                # This guide
```

---

## 🔍 Dataset Breakdown

### 1. `case_001_homicide.json` (Homicide Investigation)
- **Case Summary**: A targeted homicide involving coordinated syndicate operatives, vehicle convoys, and burner SIM cards.
- **Evidence Streams**:
  - **FIR Data**: Case registration, incident date, police station jurisdiction, IPC sections.
  - **Call Detail Records (CDR)**: Timestamps, caller/receiver MSISDNs, duration, and cell tower IDs.
  - **Hardware Identifiers**: IMEI numbers linking suspects who swap SIM cards on shared physical devices.
  - **Bank Transactions**: Rapid fund transfers preceding the incident window.
  - **CCTV Sightings**: Automated number plate recognition (ANPR) logs tracking suspect vehicles at key intersections.

### 2. `case_002_fraud.json` (Corporate Fraud & Hawala Ring)
- **Case Summary**: Large-scale financial embezzlement and money laundering across multiple jurisdiction bank accounts.
- **Evidence Streams**:
  - **Corporate Entities**: Shell companies, registered physical business addresses, and dummy directors.
  - **Mule Bank Accounts**: High-velocity layer-and-integrate wire transfers.
  - **Cross-Case Overlap**: Shared phone numbers and bank accounts connecting directly to individuals in `case_001_homicide.json`. This proves the platform's ability to reveal multi-case syndicates automatically.

### 3. `envelope_sample.json` (Streaming Event Envelope)
- **Schema**: Standardized streaming event envelope format for operational law enforcement feeds.
- **Fields**: `event_id`, `timestamp`, `event_type` (`FIR`, `ARREST`, `SEIZURE`, `CDR_CALL`, `TRANSACTION`), `case_id`, `data` payload, and `audit` fields.

---

## 📥 How to Ingest Datasets

### Option A: Via Web UI
1. Open the analyst workspace at **`http://localhost:3000/`** (or backend root **`http://localhost:8000/`**).
2. Click **"Case Registry"** in the sidebar, then click the **"+ Ingest New Case"** button.
3. Choose your ingestion mode:
   - **Upload File**: Select `case_001_homicide.json` or `case_002_fraud.json` (also supports `.pdf`, `.csv`, `.txt`).
   - **Structured JSON**: Paste the JSON payload directly.
   - **Raw Narrative**: Paste unstructured police complaints or informant memos.
4. Click **Submit**.
   - *Duplicate Guard*: If the case already exists in the system, a **"Case Already Uploaded"** alert popup prevents duplicate clutter and directs you to view or attach documents to the existing case.
   - The graph topology renders automatically, cross-case bridges are computed, and a verifiable SHA-256 evidence block is minted.

### Option B: Via Terminal (PowerShell)
```powershell
# Ingest Case 001 (Homicide Investigation)
Invoke-RestMethod -Uri "http://localhost:8000/api/cases/ingest" `
  -Method Post `
  -InFile "dataset/case_001_homicide.json" `
  -ContentType "application/json"

# Ingest Case 002 (Cross-Case Hawala Fraud)
Invoke-RestMethod -Uri "http://localhost:8000/api/cases/ingest" `
  -Method Post `
  -InFile "dataset/case_002_fraud.json" `
  -ContentType "application/json"
```

### Option C: Via cURL
```bash
curl -X POST "http://localhost:8000/api/cases/ingest" \
  -H "Content-Type: application/json" \
  -d @dataset/case_001_homicide.json
```

