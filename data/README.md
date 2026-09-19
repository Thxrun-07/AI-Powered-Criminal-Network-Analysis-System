# 🔒 Blockchain Evidence Ledger

The `data/` directory contains the immutable, cryptographic evidence ledger used to maintain a verifiable **Chain of Custody** for forensic data ingested into the system.

---

## 📁 Directory Contents

```
data/
├── blockchain_ledger.json    # Cryptographic JSON chain-of-custody blocks
└── README.md                 # This guide
```

---

## 🛡️ Architecture & Security Model

In legal proceedings and criminal trials, digital evidence must satisfy strict non-repudiation and chain-of-custody standards (e.g., Section 65B of the Indian Evidence Act / BSA guidelines).

This system implements a local cryptographic blockchain to guarantee that once a case payload (FIR, CDR, Bank transactions) is ingested into the graph database, it cannot be modified or deleted without invalidating the chain.

### 1. Block Structure

```json
{
  "index": 1,
  "timestamp": "2026-09-04T12:00:00Z",
  "case_id": "CASE-2024-001",
  "document_name": "FIR_001_Murder.txt",
  "document_type": "FIR",
  "document_hash": "c8a4129...",
  "previous_hash": "0000000000000000000000000000000000000000000000000000000000000000",
  "merkle_root": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "data_summary": {
    "entity_count": 42,
    "relationship_count": 87
  },
  "hash": "a1b2c3d4e5f6..."
}
```

### 2. Merkle Root Computation & Cloud Persistence
- Every entity (Person, Vehicle, Account) and relationship (CALL, TRANSFER) in a case is normalized and hashed using **SHA-256**.
- A deterministic Merkle Tree is constructed from these hashes, and the resulting `merkle_root` is committed to the block header.
- **Dual Persistence**: Blocks are written to `data/blockchain_ledger.json` and mirrored directly into Neo4j Cloud as `(:Block)` nodes chained via `[:CHAINED_TO]`.
- **Automatic Orphan Pruning**: When a case is deleted via `DELETE /api/cases/{case_id}`, associated evidence blocks are purged from both file and Neo4j, and the chain hashes are dynamically recalculated.

### 3. Cryptographic Chaining
- Each block contains the `previous_hash` of the preceding block.
- Modifying a past block or tampering with graph entities invalidates the cryptographic chain.

---

## 🔍 How to Verify Ledger Integrity

### Via REST API
```powershell
# Verify entire chain of custody
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/blockchain/verify" -Method Get

# Fetch all ledger blocks
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/blockchain/ledger" -Method Get
```

**Expected Verification Response**:
```json
{
  "valid": true,
  "total_blocks": 4,
  "verified_at": "2026-09-18T12:00:00Z",
  "message": "Blockchain ledger integrity verified successfully. All block hashes and chained hashes are valid."
}
```

### Via Analyst Dashboard UI
Open the React 19 dashboard at **`http://localhost:3000/`** (or backend root `http://localhost:8000/`), navigate to the **"Blockchain Ledger"** tab in the sidebar, and inspect each block's Merkle root, timestamp, document hash, and tamper status badge.

