"""
Evidence Storage and Retrieval Service (Phase 3).

Maintains and queries granular, individual forensic records (CDR calls and bank transactions)
separated from high-level aggregated graph pattern relationships.
"""
from typing import Dict, Any, List, Optional
from neo4j import Session
from backend.logging_config import logger


class EvidenceStore:
    """
    Evidence store layer for individual detailed forensic records.
    Provides targeted lookups for call records and transactions between specific entity endpoints.
    """

    @classmethod
    def get_calls_for_pair(
        cls,
        session: Session,
        src_phone: str,
        dst_phone: str,
        case_id: Optional[str] = None,
        limit: int = 200
    ) -> List[Dict[str, Any]]:
        """
        Retrieves all individual call records between src_phone and dst_phone.
        """
        from backend.services.normalizer import normalize_phone
        norm_src, _ = normalize_phone(src_phone)
        norm_dst, _ = normalize_phone(dst_phone)
        src_vars = list({v for v in [src_phone, norm_src, f"+91{norm_src}" if norm_src else None] if v})
        dst_vars = list({v for v in [dst_phone, norm_dst, f"+91{norm_dst}" if norm_dst else None] if v})

        cypher = """
        MATCH (cr:CallRecord)
        WHERE ((cr.source_phone IN $src_vars AND cr.target_phone IN $dst_vars)
           OR (cr.source_phone IN $dst_vars AND cr.target_phone IN $src_vars))
           AND ($case_id IS NULL OR $case_id IN cr.case_ids)
        RETURN cr.call_id as call_id,
               cr.source_phone as source_phone,
               cr.target_phone as target_phone,
               cr.timestamp as timestamp,
               cr.duration_seconds as duration_seconds,
               cr.type as type,
               cr.cell_tower as cell_tower,
               cr.source_record_id as source_record_id,
               cr.case_ids as case_ids
        ORDER BY cr.timestamp ASC
        LIMIT $limit
        """
        try:
            rows = session.run(cypher, {"src_vars": src_vars, "dst_vars": dst_vars, "case_id": case_id, "limit": limit}).data()
            return rows
        except Exception as e:
            logger.error(f"Error querying call records for pair ({src_phone} -> {dst_phone}): {e}")
            return []

    @classmethod
    def get_transactions_for_pair(
        cls,
        session: Session,
        src_acc: str,
        dst_acc: str,
        case_id: Optional[str] = None,
        limit: int = 200
    ) -> List[Dict[str, Any]]:
        """
        Retrieves all individual transactions between src_acc and dst_acc.
        """
        from backend.services.normalizer import normalize_bank_account
        norm_src, _ = normalize_bank_account(src_acc)
        norm_dst, _ = normalize_bank_account(dst_acc)
        src_vars = list({v for v in [src_acc, norm_src, src_acc.replace("-", ""), src_acc.replace(" ", "")] if v})
        dst_vars = list({v for v in [dst_acc, norm_dst, dst_acc.replace("-", ""), dst_acc.replace(" ", "")] if v})

        cypher = """
        MATCH (t:Transaction)
        WHERE ((t.source_account IN $src_vars AND t.target_account IN $dst_vars)
           OR (t.source_account IN $dst_vars AND t.target_account IN $src_vars))
           AND ($case_id IS NULL OR $case_id IN t.case_ids)
        RETURN t.transaction_id as transaction_id,
               t.source_account as source_account,
               t.target_account as target_account,
               t.amount as amount,
               t.currency as currency,
               t.timestamp as timestamp,
               t.transaction_type as transaction_type,
               t.reference_no as reference_no,
               t.description as description,
               t.source_record_id as source_record_id,
               t.case_ids as case_ids
        ORDER BY t.timestamp ASC
        LIMIT $limit
        """
        try:
            rows = session.run(cypher, {"src_vars": src_vars, "dst_vars": dst_vars, "case_id": case_id, "limit": limit}).data()
            return rows
        except Exception as e:
            logger.error(f"Error querying transactions for pair ({src_acc} -> {dst_acc}): {e}")
            return []

    @classmethod
    def get_underlying_records_for_relationship(
        cls,
        session: Session,
        relationship_id: str,
        source: Optional[str] = None,
        target: Optional[str] = None,
        rel_type: Optional[str] = None,
        case_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Resolves a graph relationship and returns its pattern summary alongside all individual detailed records.
        """
        resolved_src = source
        resolved_dst = target
        resolved_type = rel_type
        edge_props: Dict[str, Any] = {}

        if not (resolved_src and resolved_dst and resolved_type):
            cypher = """
            MATCH (n)-[r]->(m)
            WHERE elementId(r) = $id
               OR r.call_id = $id
               OR r.transaction_id = $id
               OR r.relationship_id = $id
            RETURN type(r) as type, properties(r) as props,
                   coalesce(n.phone_number, n.number, n.account_number, n.account_id, n.person_id, elementId(n)) as src,
                   coalesce(m.phone_number, m.number, m.account_number, m.account_id, m.person_id, elementId(m)) as dst
            LIMIT 1
            """
            rows = session.run(cypher, {"id": relationship_id}).data()
            if rows:
                r_info = rows[0]
                resolved_type = r_info.get("type")
                resolved_src = r_info.get("src")
                resolved_dst = r_info.get("dst")
                edge_props = r_info.get("props") or {}

        if not (resolved_src and resolved_dst and resolved_type) and "_" in relationship_id:
            parts = relationship_id.split("_")
            if len(parts) >= 3:
                if parts[0] in ["CALLED", "TRANSFERRED", "TRANSFERRED_TO"]:
                    resolved_type = "CALLED" if parts[0] == "CALLED" else "TRANSFERRED_TO"
                    resolved_src = parts[1]
                    resolved_dst = parts[2]
                elif parts[1] in ["CALLED", "TRANSFERRED_TO", "USES", "OWNS"]:
                    resolved_src = parts[0]
                    resolved_type = parts[1]
                    resolved_dst = parts[2]

        records: List[Dict[str, Any]] = []
        if resolved_type == "CALLED" and resolved_src and resolved_dst:
            try:
                res_cypher = """
                MATCH (n:Phone)
                WHERE n.phone_id = $val OR n.phone_number = $val OR n.number = $val
                RETURN coalesce(n.phone_number, n.number) AS num LIMIT 1
                """
                s_row = session.run(res_cypher, {"val": resolved_src}).data()
                if s_row and s_row[0].get("num"):
                    resolved_src = s_row[0]["num"]
                d_row = session.run(res_cypher, {"val": resolved_dst}).data()
                if d_row and d_row[0].get("num"):
                    resolved_dst = d_row[0]["num"]
            except Exception:
                pass
            records = cls.get_calls_for_pair(session, resolved_src, resolved_dst, case_id=case_id)
        elif resolved_type == "TRANSFERRED_TO" and resolved_src and resolved_dst:
            try:
                res_cypher = """
                MATCH (b:BankAccount)
                WHERE b.account_id = $val OR b.account_number = $val
                RETURN coalesce(b.account_number, b.account_id) AS acc LIMIT 1
                """
                s_row = session.run(res_cypher, {"val": resolved_src}).data()
                if s_row and s_row[0].get("acc"):
                    resolved_src = s_row[0]["acc"]
                d_row = session.run(res_cypher, {"val": resolved_dst}).data()
                if d_row and d_row[0].get("acc"):
                    resolved_dst = d_row[0]["acc"]
            except Exception:
                pass
            records = cls.get_transactions_for_pair(session, resolved_src, resolved_dst, case_id=case_id)

        return {
            "relationship_id": relationship_id,
            "type": resolved_type or "UNKNOWN",
            "source": resolved_src,
            "target": resolved_dst,
            "properties": edge_props,
            "total_records": len(records),
            "records": records
        }
