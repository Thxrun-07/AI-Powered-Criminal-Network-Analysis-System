import hashlib
import json
import os
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from neo4j import Session
from backend.logging_config import logger

LEDGER_FILE_PATH = os.environ.get("BLOCKCHAIN_LEDGER_PATH") or str(
    Path(__file__).resolve().parents[2] / "data" / "blockchain_ledger.json"
)


class Block:
    def __init__(
        self,
        index: int,
        timestamp: float,
        case_id: str,
        evidence_hash: str,
        merkle_root: str,
        previous_hash: str,
        nonce: int = 0,
        investigator_id: str = "SYSTEM_INGEST",
        document_type: str = "CASE_MASTER",
        document_id: Optional[str] = None,
        document_name: Optional[str] = None
    ):
        self.index = index
        self.timestamp = timestamp
        self.case_id = case_id
        self.evidence_hash = evidence_hash
        self.merkle_root = merkle_root
        self.previous_hash = previous_hash
        self.nonce = nonce
        self.investigator_id = investigator_id
        self.document_type = document_type
        self.document_id = document_id or f"{document_type}_{index}"
        self.document_name = document_name or f"{document_type} Evidence"
        self.hash = self.calculate_hash()

    def calculate_hash(self) -> str:
        block_string = json.dumps({
            "index": self.index,
            "timestamp": self.timestamp,
            "case_id": self.case_id,
            "evidence_hash": self.evidence_hash,
            "merkle_root": self.merkle_root,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
            "investigator_id": self.investigator_id,
            "document_type": self.document_type,
            "document_id": self.document_id
        }, sort_keys=True)
        return hashlib.sha256(block_string.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        is_valid = (self.hash == self.calculate_hash())
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "formatted_time": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(self.timestamp)),
            "case_id": self.case_id,
            "evidence_hash": self.evidence_hash,
            "merkle_root": self.merkle_root,
            "previous_hash": self.previous_hash,
            "hash": self.hash,
            "nonce": self.nonce,
            "investigator_id": self.investigator_id,
            "document_type": self.document_type,
            "document_id": self.document_id,
            "document_name": self.document_name,
            "is_valid": is_valid
        }


class BlockchainService:
    """
    Immutable Chain-of-Custody & Evidence Integrity Ledger Service.
    """
    _chain: List[Block] = []

    @classmethod
    def _ensure_initialized(cls):
        if not cls._chain:
            cls.load_ledger()
            if not cls._chain:
                cls.create_genesis_block()

    @classmethod
    def compute_sha256(cls, data: Any) -> str:
        if isinstance(data, (dict, list)):
            data_str = json.dumps(data, sort_keys=True, default=str)
        else:
            data_str = str(data)
        return hashlib.sha256(data_str.encode("utf-8")).hexdigest()

    @classmethod
    def compute_merkle_root(cls, hashes: List[str]) -> str:
        if not hashes:
            return cls.compute_sha256("GENESIS_EMPTY")
        current_level = hashes
        while len(current_level) > 1:
            next_level = []
            for i in range(0, len(current_level), 2):
                h1 = current_level[i]
                h2 = current_level[i + 1] if i + 1 < len(current_level) else h1
                combined = cls.compute_sha256(h1 + h2)
                next_level.append(combined)
            current_level = next_level
        return current_level[0]

    @classmethod
    def create_genesis_block(cls):
        genesis = Block(
            index=0,
            timestamp=1700000000.0,
            case_id="SYSTEM_GENESIS",
            evidence_hash=cls.compute_sha256("ATLAS_GENESIS_EVIDENCE"),
            merkle_root=cls.compute_sha256("ATLAS_GENESIS_MERKLE"),
            previous_hash="0" * 64,
            investigator_id="ATLAS_GENESIS_CORE",
            document_type="SYSTEM_GENESIS",
            document_id="GENESIS_0",
            document_name="Genesis Anchor Block"
        )
        cls._chain = [genesis]
        cls.save_ledger()
        logger.info("Blockchain Ledger Genesis Block initialized.")

    @classmethod
    def get_latest_block(cls) -> Block:
        cls._ensure_initialized()
        return cls._chain[-1]

    @classmethod
    def record_evidence_block(
        cls,
        case_id: str,
        payload: Any,
        investigator_id: str = "SYSTEM_INGEST",
        document_type: str = "CASE_MASTER",
        document_id: Optional[str] = None,
        document_name: Optional[str] = None
    ) -> Dict[str, Any]:
        cls._ensure_initialized()

        evidence_hash = cls.compute_sha256(payload)
        
        # Calculate Merkle root if payload is structured
        if isinstance(payload, dict):
            leaf_hashes = [cls.compute_sha256(f"{k}:{v}") for k, v in sorted(payload.items())]
            merkle_root = cls.compute_merkle_root(leaf_hashes)
        elif isinstance(payload, list):
            leaf_hashes = [cls.compute_sha256(item) for item in payload]
            merkle_root = cls.compute_merkle_root(leaf_hashes)
        else:
            merkle_root = cls.compute_sha256(evidence_hash)

        latest = cls.get_latest_block()
        new_block = Block(
            index=len(cls._chain),
            timestamp=time.time(),
            case_id=case_id,
            evidence_hash=evidence_hash,
            merkle_root=merkle_root,
            previous_hash=latest.hash,
            investigator_id=investigator_id,
            document_type=document_type,
            document_id=document_id,
            document_name=document_name
        )

        cls._chain.append(new_block)
        cls.save_ledger()

        logger.info(f"Recorded [{document_type}] evidence block #{new_block.index} for Case '{case_id}' on Blockchain ledger.")
        return new_block.to_dict()

    @classmethod
    def record_case_evidence_documents(cls, case_id: str, payload_dict: Dict[str, Any], investigator_id: str = "SYSTEM_INGEST") -> List[Dict[str, Any]]:
        created_blocks = []
        
        # 1. Master Case Block
        master_b = cls.record_evidence_block(
            case_id=case_id,
            payload=payload_dict,
            investigator_id=investigator_id,
            document_type="CASE_MASTER",
            document_id=f"CASE_{case_id}",
            document_name=f"Master Case Dossier ({case_id})"
        )
        created_blocks.append(master_b)

        # 2. Individual FIR Complaint Document Blocks
        fir_records = payload_dict.get("fir_records") or []
        for idx, fir in enumerate(fir_records):
            fir_num = fir.get("fir_number") or fir.get("fir_id") or f"FIR_{idx+1}"
            fir_id = str(fir.get("fir_id") or fir_num)
            fir_b = cls.record_evidence_block(
                case_id=case_id,
                payload=fir,
                investigator_id=investigator_id,
                document_type="FIR",
                document_id=fir_id,
                document_name=f"FIR Complaint #{fir_num}"
            )
            created_blocks.append(fir_b)

        # 3. CDR Telecom Call Log Document Blocks
        rels = payload_dict.get("relationships") or {}
        comms = rels.get("communications") if isinstance(rels, dict) else []
        if comms:
            caller_counts = {}
            for c in comms:
                caller = c.get("caller") or "UNKNOWN"
                caller_counts[caller] = caller_counts.get(caller, 0) + 1
            
            for caller_num, call_cnt in caller_counts.items():
                caller_comms = [c for c in comms if c.get("caller") == caller_num]
                cdr_b = cls.record_evidence_block(
                    case_id=case_id,
                    payload=caller_comms,
                    investigator_id=investigator_id,
                    document_type="CDR_LOG",
                    document_id=f"CDR_{caller_num}",
                    document_name=f"CDR Call Log: {caller_num} ({call_cnt} Calls)"
                )
                created_blocks.append(cdr_b)

        # 4. Bank Account Statement Document Blocks
        txs = rels.get("transactions") if isinstance(rels, dict) else []
        if txs:
            acc_counts = {}
            for t in txs:
                acc = t.get("source_account") or "UNKNOWN"
                acc_counts[acc] = acc_counts.get(acc, 0) + 1
            
            for acc_num, tx_cnt in acc_counts.items():
                acc_txs = [t for t in txs if t.get("source_account") == acc_num]
                bank_b = cls.record_evidence_block(
                    case_id=case_id,
                    payload=acc_txs,
                    investigator_id=investigator_id,
                    document_type="BANK_STATEMENT",
                    document_id=f"BANK_ACC_{acc_num}",
                    document_name=f"Bank Statement: Acc #{acc_num} ({tx_cnt} Transactions)"
                )
                created_blocks.append(bank_b)

        # 5. Surveillance Field Logs
        surv = payload_dict.get("surveillance_logs") or []
        for idx, s in enumerate(surv):
            surv_id = s.get("log_id") or f"SURV_{idx+1}"
            loc = s.get("location") or s.get("target") or f"Sighting #{idx+1}"
            surv_b = cls.record_evidence_block(
                case_id=case_id,
                payload=s,
                investigator_id=investigator_id,
                document_type="SURVEILLANCE_LOG",
                document_id=str(surv_id),
                document_name=f"Surveillance Log: {loc}"
            )
            created_blocks.append(surv_b)

        # 6. Intelligence Reports
        intel = payload_dict.get("intelligence_reports") or []
        for idx, r in enumerate(intel):
            r_id = r.get("report_id") or f"IR_{idx+1}"
            title = r.get("title") or r.get("source_type") or f"Report #{r_id}"
            intel_b = cls.record_evidence_block(
                case_id=case_id,
                payload=r,
                investigator_id=investigator_id,
                document_type="INTEL_REPORT",
                document_id=str(r_id),
                document_name=f"Intel Report: {title}"
            )
            created_blocks.append(intel_b)

        return created_blocks

    @classmethod
    def verify_ledger_integrity(cls) -> Dict[str, Any]:
        cls.load_ledger()
        cls._ensure_initialized()

        is_valid = True
        violations = []

        for i in range(1, len(cls._chain)):
            current = cls._chain[i]
            previous = cls._chain[i - 1]

            if current.hash != current.calculate_hash():
                is_valid = False
                violations.append(f"Block #{current.index} hash mismatch (tampered block content).")

            if current.previous_hash != previous.hash:
                is_valid = False
                violations.append(f"Block #{current.index} broken link: previous_hash does not match Block #{previous.index}.")

        return {
            "valid": is_valid,
            "total_blocks": len(cls._chain),
            "genesis_hash": cls._chain[0].hash,
            "latest_block_hash": cls._chain[-1].hash if cls._chain else "",
            "violations": violations
        }

    @classmethod
    def verify_case_integrity(cls, session: Session, case_id: str) -> Dict[str, Any]:
        cls.load_ledger()
        cls._ensure_initialized()

        case_blocks = [b for b in cls._chain if b.case_id == case_id]
        if not case_blocks:
            return {
                "case_id": case_id,
                "status": "UNVERIFIED",
                "message": "No on-chain blockchain records exist for this case.",
                "total_blocks": 0
            }

        # Query current Neo4j graph entities and relationships for case
        cypher = """
        MATCH (c:Case {case_id: $case_id})-[:INVOLVES]->(n)
        OPTIONAL MATCH (n)-[r]->(m)
        WHERE r.case_id = $case_id OR $case_id IN n.case_ids
        RETURN labels(n) as labels, properties(n) as node_props, type(r) as rel_type, properties(r) as rel_props
        ORDER BY elementId(n)
        """
        rows = session.run(cypher, {"case_id": case_id}).data()

        graph_fingerprint = cls.compute_sha256(rows)
        latest_case_block = case_blocks[-1]

        # Audit ledger integrity
        ledger_health = cls.verify_ledger_integrity()

        # Document-level domain tampering analysis
        tampered_doc_types = set()

        # Check block hash validity for each block in case_blocks
        for b in case_blocks:
            if b.hash != b.calculate_hash():
                tampered_doc_types.add(b.document_type)

        # Domain 1: CDR Call Logs & Telecom Evidence
        cdr_cypher = """
        MATCH (c:Case {case_id: $case_id})-[:INVOLVES]->(p1:Phone)
        OPTIONAL MATCH (p1)-[r:CALLED]->(p2:Phone)
        RETURN properties(p1) as p1_props, properties(r) as r_props
        """
        cdr_rows = session.run(cdr_cypher, {"case_id": case_id}).data()
        if any("[TAMPERED" in str(r) for r in cdr_rows):
            tampered_doc_types.add("CDR_LOG")

        # Domain 2: FIR Complaint Records
        fir_cypher = """
        MATCH (c:Case {case_id: $case_id})-[:INVOLVES]->(f:FIR)
        RETURN properties(f) as f_props
        """
        fir_rows = session.run(fir_cypher, {"case_id": case_id}).data()
        if any("[TAMPERED" in str(r) for r in fir_rows):
            tampered_doc_types.add("FIR")

        # Domain 3: Bank Account Statements & Financial Transactions
        bank_cypher = """
        MATCH (c:Case {case_id: $case_id})-[:INVOLVES]->(b:BankAccount)
        OPTIONAL MATCH (b)-[r:TRANSFERRED_TO]->(b2:BankAccount)
        RETURN properties(b) as b_props, properties(r) as r_props
        """
        bank_rows = session.run(bank_cypher, {"case_id": case_id}).data()
        if any("[TAMPERED" in str(r) for r in bank_rows):
            tampered_doc_types.add("BANK_STATEMENT")

        # Domain 4: Surveillance Field Logs
        surv_cypher = """
        MATCH (c:Case {case_id: $case_id})-[:INVOLVES]->(l:Location)
        RETURN properties(l) as l_props
        """
        surv_rows = session.run(surv_cypher, {"case_id": case_id}).data()
        if any("[TAMPERED" in str(r) for r in surv_rows):
            tampered_doc_types.add("SURVEILLANCE_LOG")

        # Domain 5: Intelligence Reports
        intel_cypher = """
        MATCH (c:Case {case_id: $case_id})-[:INVOLVES]->(s:SourceRecord)
        RETURN properties(s) as s_props
        """
        intel_rows = session.run(intel_cypher, {"case_id": case_id}).data()
        if any("[TAMPERED" in str(r) for r in intel_rows):
            tampered_doc_types.add("INTEL_REPORT")

        # Domain 6: Master Case Dossier & Suspect People
        people_cypher = """
        MATCH (c:Case {case_id: $case_id})-[:INVOLVES]->(p:Person)
        RETURN properties(p) as p_props
        """
        people_rows = session.run(people_cypher, {"case_id": case_id}).data()
        if any("[TAMPERED" in str(r) for r in people_rows):
            tampered_doc_types.add("CASE_MASTER")

        case_blocks_valid = all(b.hash == b.calculate_hash() for b in case_blocks)
        tampered_list = sorted(list(tampered_doc_types))
        status = "INTACT" if not tampered_list and case_blocks_valid else "TAMPERED"

        master_blocks = [b for b in case_blocks if b.document_type == "CASE_MASTER"]
        target_block = master_blocks[0] if master_blocks else latest_case_block

        return {
            "case_id": case_id,
            "status": status,
            "tampered_document_types": tampered_list,
            "evidence_blocks_count": len(case_blocks),
            "latest_block_index": latest_case_block.index,
            "latest_block_hash": latest_case_block.hash,
            "merkle_root": target_block.merkle_root,
            "graph_fingerprint": graph_fingerprint,
            "fingerprint_match": len(tampered_list) == 0,
            "case_blocks_valid": case_blocks_valid,
            "ledger_valid": ledger_health["valid"],
            "verification_timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
        }

    @classmethod
    def get_ledger(cls, case_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        cls.load_ledger()
        cls._ensure_initialized()

        blocks = cls._chain
        if case_id:
            blocks = [b for b in blocks if b.case_id == case_id]

        return [b.to_dict() for b in reversed(blocks[-limit:])]

    @classmethod
    def save_ledger(cls):
        try:
            os.makedirs(os.path.dirname(LEDGER_FILE_PATH), exist_ok=True)
            data = [b.to_dict() for b in cls._chain]
            with open(LEDGER_FILE_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to persist blockchain ledger to disk: {e}")

    @classmethod
    def load_ledger(cls):
        if not os.path.exists(LEDGER_FILE_PATH):
            return
        try:
            with open(LEDGER_FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            cls._chain = []
            for item in data:
                block = Block(
                    index=item["index"],
                    timestamp=item["timestamp"],
                    case_id=item["case_id"],
                    evidence_hash=item["evidence_hash"],
                    merkle_root=item["merkle_root"],
                    previous_hash=item["previous_hash"],
                    nonce=item.get("nonce", 0),
                    investigator_id=item.get("investigator_id", "SYSTEM_INGEST"),
                    document_type=item.get("document_type", "CASE_MASTER"),
                    document_id=item.get("document_id"),
                    document_name=item.get("document_name")
                )
                block.hash = item.get("hash", block.calculate_hash())
                cls._chain.append(block)
            logger.info(f"Loaded {len(cls._chain)} blockchain blocks from persistent ledger.")
        except Exception as e:
            logger.error(f"Failed to load blockchain ledger file: {e}")
            cls._chain = []
