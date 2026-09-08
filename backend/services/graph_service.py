from typing import Dict, Any, List, Optional
from neo4j import Session
from backend.logging_config import logger


class GraphService:
    """
    Graph Retrieval, Entity 360, Relationship Inspection, and Case Listing Service.
    """

    @classmethod
    def get_subgraph(
        cls,
        session: Session,
        case_id: Optional[str] = None,
        node_labels: Optional[List[str]] = None,
        core_only: bool = False,
        limit: int = 1000
    ) -> Dict[str, Any]:
        if core_only:
            cypher = """
            MATCH (n)
            WHERE ($case_id IS NULL OR $case_id IN n.case_ids)
              AND ($labels IS NULL OR size($labels) = 0 OR any(l IN labels(n) WHERE l IN $labels))
              AND NOT ('Phone' IN labels(n) AND (n.owner_person_id IS NULL OR n.owner_person_id = '') AND NOT coalesce(n.phone_number, '') STARTS WITH '99999')
            OPTIONAL MATCH (n)-[r]->(m)
            WHERE ($case_id IS NULL OR $case_id IN m.case_ids)
              AND ($labels IS NULL OR size($labels) = 0 OR any(l IN labels(m) WHERE l IN $labels))
              AND NOT ('Phone' IN labels(m) AND (m.owner_person_id IS NULL OR m.owner_person_id = '') AND NOT coalesce(m.phone_number, '') STARTS WITH '99999')
            RETURN labels(n) as n_labels, properties(n) as n_props,
                   elementId(r) as r_id, type(r) as r_type, properties(r) as r_props,
                   labels(m) as m_labels, properties(m) as m_props
            LIMIT $limit
            """
        else:
            cypher = """
            MATCH (n)
            WHERE ($case_id IS NULL OR $case_id IN n.case_ids)
              AND ($labels IS NULL OR size($labels) = 0 OR any(l IN labels(n) WHERE l IN $labels))
            OPTIONAL MATCH (n)-[r]->(m)
            WHERE ($case_id IS NULL OR $case_id IN m.case_ids)
              AND ($labels IS NULL OR size($labels) = 0 OR any(l IN labels(m) WHERE l IN $labels))
            RETURN labels(n) as n_labels, properties(n) as n_props,
                   elementId(r) as r_id, type(r) as r_type, properties(r) as r_props,
                   labels(m) as m_labels, properties(m) as m_props
            LIMIT $limit
            """

        rows = session.run(cypher, {"case_id": case_id, "labels": node_labels, "limit": limit}).data()

        nodes_dict: Dict[str, Dict[str, Any]] = {}
        edges_dict: Dict[str, Dict[str, Any]] = {}

        def get_node_id(labels: List[str], props: Dict[str, Any]) -> str:
            return str(
                props.get("person_id")
                or props.get("phone_number")
                or props.get("account_number")
                or props.get("vin")
                or props.get("license_plate")
                or props.get("handle_id")
                or props.get("ip_address")
                or props.get("location_id")
                or props.get("cell_tower_id")
                or props.get("fir_id")
                or props.get("prior_case_id")
                or props.get("source_record_id")
                or props.get("transaction_id")
                or props.get("record_id")
                or props.get("report_id")
                or props.get("log_id")
                or props.get("case_id")
                or (f"{labels[0] if labels else 'Node'}_{abs(hash(str(props)))}" if props else "node_unknown")
            )

        def format_display_name(labels: List[str], props: Dict[str, Any], node_id: str) -> str:
            primary_label = labels[0] if labels else "Entity"
            if "Person" in labels or primary_label == "Person":
                return str(props.get("name") or node_id)
            if "Phone" in labels or primary_label == "Phone":
                return str(props.get("phone_number") or node_id)
            if "BankAccount" in labels or primary_label == "BankAccount":
                acc = props.get("account_number") or node_id
                bank = props.get("bank_name")
                holder = props.get("holder_name") or props.get("owner_name")
                if bank and holder:
                    return f"{bank}: {acc} ({holder})"
                elif bank:
                    return f"{bank}: {acc}"
                elif holder:
                    return f"Acc: {acc} ({holder})"
                return f"Acc: {acc}"

            if "Vehicle" in labels or primary_label == "Vehicle":
                plate = props.get("license_plate") or props.get("vin") or node_id
                model = props.get("model")
                return f"{plate} ({model})" if model else plate
            if "FIR" in labels or primary_label == "FIR":
                return f"FIR {props.get('fir_number') or node_id}"
            if "Case" in labels or primary_label == "Case":
                return str(props.get("case_name") or props.get("case_id") or node_id)
            if "SocialHandle" in labels or primary_label == "SocialHandle":
                return str(props.get("handle") or props.get("handle_id") or node_id)
            if "IPAddress" in labels or primary_label == "IPAddress":
                return str(props.get("ip_address") or node_id)
            if "Location" in labels or primary_label == "Location":
                return str(props.get("name") or props.get("address") or props.get("location_id") or node_id)
            if "CellTower" in labels or primary_label == "CellTower":
                return f"Tower {props.get('tower_code') or props.get('cell_tower_id') or node_id}"
            if "PriorCase" in labels or primary_label == "PriorCase":
                return f"Prior: {props.get('case_number') or node_id}"
            if "SourceRecord" in labels or primary_label == "SourceRecord":
                return f"Doc: {props.get('source_type') or props.get('record_type') or node_id}"
            if "Transaction" in labels or primary_label == "Transaction":
                amt = props.get("amount")
                return f"Txn Rs.{amt}" if amt else f"Txn: {node_id}"
            return str(props.get("name") or props.get("case_name") or props.get("fir_number") or props.get("phone_number") or props.get("account_number") or props.get("license_plate") or props.get("source_record_id") or props.get("log_id") or node_id)

        for row in rows:
            n_props = row.get("n_props") or {}
            n_labels = row.get("n_labels") or ["Entity"]
            if n_props:
                n_id = get_node_id(n_labels, n_props)
                if n_id not in nodes_dict:
                    nodes_dict[n_id] = {
                        "id": n_id,
                        "labels": n_labels,
                        "name": format_display_name(n_labels, n_props, n_id),
                        "case_ids": n_props.get("case_ids") or [],
                        "properties": n_props
                    }

            m_props = row.get("m_props") or {}
            m_labels = row.get("m_labels") or ["Entity"]
            if m_props:
                m_id = get_node_id(m_labels, m_props)
                if m_id not in nodes_dict:
                    nodes_dict[m_id] = {
                        "id": m_id,
                        "labels": m_labels,
                        "name": format_display_name(m_labels, m_props, m_id),
                        "case_ids": m_props.get("case_ids") or [],
                        "properties": m_props
                    }

            r_type = row.get("r_type")
            r_props = row.get("r_props") or {}
            if r_type and n_props and m_props:
                n_id = get_node_id(n_labels, n_props)
                m_id = get_node_id(m_labels, m_props)
                edge_id = str(
                    row.get("r_id")
                    or r_props.get("call_id")
                    or r_props.get("transaction_id")
                    or f"{n_id}_{r_type}_{m_id}"
                )
                if edge_id in edges_dict:
                    edge_id = f"{edge_id}_{len(edges_dict)}"
                edges_dict[edge_id] = {
                    "id": edge_id,
                    "type": r_type,
                    "source": n_id,
                    "target": m_id,
                    "properties": r_props
                }

        # 1. Connect BankAccount and Vehicle entities to their existing Person owner if not already linked
        for node_id, node in list(nodes_dict.items()):
            labels = node.get("labels") or []
            if "BankAccount" in labels or "Vehicle" in labels:
                has_owner_edge = any(
                    e.get("type") == "OWNS" and e.get("target") == node_id
                    for e in edges_dict.values()
                )
                if not has_owner_edge:
                    props = node.get("properties") or {}
                    owner_hint = (props.get("holder_name") or props.get("registered_owner") or props.get("owner_name") or "").strip()
                    owner_person_id = props.get("owner_person_id")

                    # Search for matching existing Person node
                    matched_person_id = None
                    for pid, pnode in nodes_dict.items():
                        if "Person" in (pnode.get("labels") or []):
                            pname = (pnode.get("name") or "").strip()
                            if owner_person_id and pid == owner_person_id:
                                matched_person_id = pid
                                break
                            if owner_hint and owner_hint.lower() not in ["unknown", "n/a", "none"] and pname.lower() == owner_hint.lower():
                                matched_person_id = pid
                                break

                    if matched_person_id:
                        syn_edge_id = f"OWNS_{matched_person_id}_{node_id}"
                        if syn_edge_id in edges_dict:
                            syn_edge_id = f"{syn_edge_id}_{len(edges_dict)}"
                        edges_dict[syn_edge_id] = {
                            "id": syn_edge_id,
                            "type": "OWNS",
                            "source": matched_person_id,
                            "target": node_id,
                            "properties": {"status": "Owner Relationship"}
                        }

        edges_list = list(edges_dict.values())

        # 2. Filter out isolated / disconnected nodes (nodes without any relationship)
        connected_node_ids = set()
        for e in edges_list:
            connected_node_ids.add(e["source"])
            connected_node_ids.add(e["target"])

        filtered_nodes = [node for n_id, node in nodes_dict.items() if n_id in connected_node_ids]

        return {
            "case_id": case_id,
            "total_nodes": len(filtered_nodes),
            "total_edges": len(edges_list),
            "nodes": filtered_nodes,
            "edges": edges_list
        }


    @classmethod
    def search_entities(
        cls,
        session: Session,
        query: str,
        entity_type: Optional[str] = None,
        case_id: Optional[str] = None,
        limit: int = 25
    ) -> List[Dict[str, Any]]:
        cypher = """
        MATCH (n)
        WHERE ($entity_type IS NULL OR $entity_type IN labels(n))
          AND ($case_id IS NULL OR $case_id IN n.case_ids)
          AND (
            toLower(coalesce(n.name, '')) CONTAINS toLower($q)
            OR toLower(coalesce(n.person_id, '')) CONTAINS toLower($q)
            OR toLower(coalesce(n.phone_number, '')) CONTAINS toLower($q)
            OR toLower(coalesce(n.account_number, '')) CONTAINS toLower($q)
            OR toLower(coalesce(n.vin, '')) CONTAINS toLower($q)
            OR toLower(coalesce(n.license_plate, '')) CONTAINS toLower($q)
            OR toLower(coalesce(n.handle, '')) CONTAINS toLower($q)
            OR toLower(coalesce(n.ip_address, '')) CONTAINS toLower($q)
            OR toLower(coalesce(n.case_name, '')) CONTAINS toLower($q)
            OR any(a IN coalesce(n.aliases, []) WHERE toLower(a) CONTAINS toLower($q))
          )
        RETURN coalesce(n.person_id, n.phone_number, n.account_number, n.vin, n.handle_id, n.ip_address, n.location_id, elementId(n)) as id,
               coalesce(n.name, n.phone_number, n.account_number, n.vin, n.handle, n.ip_address) as display_name,
               labels(n) as labels,
               n.case_ids as case_ids,
               properties(n) as properties
        LIMIT $limit
        """
        rows = session.run(cypher, {"q": query, "entity_type": entity_type, "case_id": case_id, "limit": limit}).data()
        results = []
        for r in rows:
            results.append({
                "entity_id": str(r["id"]),
                "display_name": r.get("display_name"),
                "labels": r.get("labels") or [],
                "case_ids": r.get("case_ids") or [],
                "properties": r.get("properties") or {}
            })
        return results

    @classmethod
    def get_entity_360(cls, session: Session, entity_id: str) -> Optional[Dict[str, Any]]:
        # Fetch target node
        node_cypher = """
        MATCH (n)
        WHERE n.person_id = $id OR n.phone_number = $id OR n.account_number = $id
           OR n.vin = $id OR n.handle_id = $id OR n.ip_address = $id
           OR n.location_id = $id OR n.fir_id = $id OR n.prior_case_id = $id
           OR n.case_id = $id OR n.cell_tower_id = $id OR n.source_record_id = $id
           OR n.license_plate = $id OR n.transaction_id = $id
           OR elementId(n) = $id
        RETURN n, labels(n) as labels
        """
        node_res = session.run(node_cypher, {"id": entity_id}).data()
        if not node_res:
            return None

        target_node = node_res[0]["n"]
        labels = node_res[0]["labels"]

        # Fetch 1-hop connections
        rel_cypher = """
        MATCH (n)-[r]-(neighbor)
        WHERE n.person_id = $id OR n.phone_number = $id OR n.account_number = $id
           OR n.vin = $id OR n.handle_id = $id OR n.ip_address = $id
           OR n.location_id = $id OR n.fir_id = $id OR n.prior_case_id = $id
           OR n.case_id = $id OR n.cell_tower_id = $id OR n.source_record_id = $id
           OR n.license_plate = $id OR n.transaction_id = $id
           OR elementId(n) = $id
        RETURN type(r) as relationship_type,
               startNode(r) = n as is_outgoing,
               properties(r) as relationship_properties,
               labels(neighbor) as neighbor_labels,
               coalesce(neighbor.person_id, neighbor.phone_number, neighbor.account_number, neighbor.vin, neighbor.handle_id, neighbor.ip_address, neighbor.case_id, neighbor.cell_tower_id, neighbor.fir_id, neighbor.prior_case_id, elementId(neighbor)) as neighbor_id,
               coalesce(neighbor.name, neighbor.phone_number, neighbor.account_number, neighbor.vin, neighbor.handle, neighbor.case_name, neighbor.case_id) as neighbor_name,
               properties(neighbor) as neighbor_properties
        """
        rel_rows = session.run(rel_cypher, {"id": entity_id}).data()

        connections = []
        for row in rel_rows:
            connections.append({
                "relationship": row["relationship_type"],
                "direction": "OUTGOING" if row["is_outgoing"] else "INCOMING",
                "relationship_properties": row["relationship_properties"],
                "neighbor_id": str(row["neighbor_id"]),
                "neighbor_name": row.get("neighbor_name"),
                "neighbor_labels": row.get("neighbor_labels") or [],
                "neighbor_properties": row.get("neighbor_properties") or {}
            })

        return {
            "entity_id": entity_id,
            "labels": labels,
            "properties": dict(target_node),
            "total_connections": len(connections),
            "connections": connections
        }

    @classmethod
    def get_relationship_by_id(cls, session: Session, relationship_id: str) -> Optional[Dict[str, Any]]:
        cypher = """
        MATCH (n)-[r]->(m)
        WHERE r.call_id = $id OR r.transaction_id = $id OR r.log_id = $id
        RETURN type(r) as type, properties(r) as properties,
               labels(n) as source_labels,
               coalesce(n.person_id, n.phone_number, n.account_number, n.vin, id(n)) as source_id,
               coalesce(n.name, n.phone_number, n.account_number, n.vin) as source_name,
               labels(m) as target_labels,
               coalesce(m.person_id, m.phone_number, m.account_number, m.vin, id(m)) as target_id,
               coalesce(m.name, m.phone_number, m.account_number, m.vin) as target_name
        """
        rows = session.run(cypher, {"id": relationship_id}).data()
        if not rows:
            return None
        r = rows[0]
        return {
            "relationship_id": relationship_id,
            "type": r["type"],
            "properties": r.get("properties") or {},
            "source": {
                "id": str(r["source_id"]),
                "name": r.get("source_name"),
                "labels": r.get("source_labels") or []
            },
            "target": {
                "id": str(r["target_id"]),
                "name": r.get("target_name"),
                "labels": r.get("target_labels") or []
            }
        }

    @classmethod
    def list_cases(cls, session: Session, status: Optional[str] = None, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        cypher = """
        MATCH (c:Case)
        WHERE ($status IS NULL OR c.status = $status)
        OPTIONAL MATCH (c)-[:INVOLVES]->(n)
        WITH c, count(DISTINCT n) as entity_count
        ORDER BY c.created_at DESC
        SKIP $offset
        LIMIT $limit
        RETURN c.case_id as case_id,
               c.case_name as case_name,
               c.case_type as case_type,
               c.status as status,
               c.jurisdiction as jurisdiction,
               c.lead_investigator as lead_investigator,
               c.created_date as created_date,
               c.created_at as created_at,
               c.summary as summary,
               entity_count
        """
        rows = session.run(cypher, {"status": status, "limit": limit, "offset": offset}).data()
        cases = []
        for r in rows:
            cases.append({
                "case_id": r["case_id"],
                "case_name": r.get("case_name"),
                "case_type": r.get("case_type"),
                "status": r.get("status"),
                "jurisdiction": r.get("jurisdiction"),
                "lead_investigator": r.get("lead_investigator"),
                "created_date": r.get("created_date"),
                "created_at": r.get("created_at"),
                "summary": r.get("summary"),
                "total_entities": int(r.get("entity_count") or 0)
            })
        return cases

    @classmethod
    def get_case_summary(cls, session: Session, case_id: str) -> Optional[Dict[str, Any]]:
        # 1. Fetch Case node
        cypher_case = """
        MATCH (c:Case {case_id: $case_id})
        RETURN c
        """
        case_res = session.run(cypher_case, {"case_id": case_id}).data()
        if not case_res:
            return None
        case_node = dict(case_res[0]["c"])

        # 2. Extract FIR node details if linked
        fir_res = session.run("""
            MATCH (c:Case {case_id: $case_id})-[:INVOLVES]->(f:FIR)
            RETURN f.fir_number as fir_num, f.incident_date as inc_date, f.offense as offense
            LIMIT 1
        """, {"case_id": case_id}).single()
        
        fir_number = None
        incident_date = None
        if fir_res:
            fir_number = fir_res.get("fir_num")
            incident_date = fir_res.get("inc_date")

        if not fir_number:
            fir_number = case_node.get("fir_number")
        if not fir_number:
            c_name = str(case_node.get("case_name") or "")
            if "FIR" in c_name:
                import re
                m = re.search(r'FIR[/_\-\s]?(\w+[/_\-]?\w*)', c_name, re.IGNORECASE)
                fir_number = m.group(0) if m else c_name
            else:
                fir_number = f"FIR/{case_id}"

        # Formatted date
        case_date = incident_date or case_node.get("incident_date") or case_node.get("created_at") or "2026-09-02"
        if isinstance(case_date, str) and "T" in case_date:
            case_date = case_date.split("T")[0]

        # Crime Category
        category_of_crime = case_node.get("case_type") or case_node.get("category") or "Criminal Network Investigation"

        # 3. People (Suspects vs Victims categorization)
        people_res = session.run("""
            MATCH (c:Case {case_id: $case_id})-[:INVOLVES]->(p:Person)
            OPTIONAL MATCH (p)-[r]-(x) WHERE r.case_id = $case_id
            RETURN p.name as name, p.roles as roles, p.role as role, p.person_id as person_id, count(r) as degree
            ORDER BY degree DESC
        """, {"case_id": case_id}).data()

        suspects = []
        victims = []
        for p in people_res:
            p_name = p.get("name") or p.get("person_id") or "Unknown Person"
            roles = [str(r).lower() for r in (p.get("roles") or [])]
            if p.get("role"):
                roles.append(str(p["role"]).lower())

            person_entry = {
                "name": p_name,
                "person_id": p.get("person_id"),
                "roles": p.get("roles") or ([p["role"]] if p.get("role") else ["Actor"]),
                "degree": p.get("degree", 0)
            }

            if any(s in roles for s in ["victim", "complainant"]):
                victims.append(person_entry)
            elif any(s in roles for s in ["suspect", "accused", "director", "shooter", "organizer", "courier", "mule", "operator"]):
                suspects.append(person_entry)
            else:
                suspects.append(person_entry)

        # 4. Entity breakdown and collected evidences
        cypher_counts = """
        MATCH (c:Case {case_id: $case_id})-[:INVOLVES]->(n)
        RETURN labels(n)[0] as label, count(n) as count
        """
        counts_res = session.run(cypher_counts, {"case_id": case_id}).data()
        entity_breakdown = {r["label"]: r["count"] for r in counts_res if r.get("label")}

        evidences_collected = []
        if entity_breakdown.get("Phone"):
            evidences_collected.append({
                "type": "CDR_LOGS",
                "name": f"{entity_breakdown['Phone']} Phone Numbers & CDR Telecom Records",
                "count": entity_breakdown["Phone"],
                "icon": "📞"
            })
        if entity_breakdown.get("BankAccount") or entity_breakdown.get("Transaction"):
            fin_cnt = entity_breakdown.get("BankAccount", 0) + entity_breakdown.get("Transaction", 0)
            evidences_collected.append({
                "type": "FINANCIAL",
                "name": f"{fin_cnt} Bank Statements & Transaction Records",
                "count": fin_cnt,
                "icon": "💳"
            })
        if entity_breakdown.get("Location") or entity_breakdown.get("CellTower"):
            surv_cnt = entity_breakdown.get("Location", 0) + entity_breakdown.get("CellTower", 0)
            evidences_collected.append({
                "type": "SURVEILLANCE",
                "name": f"{surv_cnt} Surveillance Field Logs & Cell Tower Geotags",
                "count": surv_cnt,
                "icon": "📍"
            })
        if entity_breakdown.get("Vehicle"):
            evidences_collected.append({
                "type": "VEHICLE",
                "name": f"{entity_breakdown['Vehicle']} Registered Vehicle & ANPR Records",
                "count": entity_breakdown["Vehicle"],
                "icon": "🚗"
            })
        if entity_breakdown.get("FIR"):
            evidences_collected.append({
                "type": "LEGAL",
                "name": "Registered Police FIR Complaint Record",
                "count": 1,
                "icon": "📜"
            })
        if entity_breakdown.get("PriorCase"):
            evidences_collected.append({
                "type": "CRIMINAL_HISTORY",
                "name": f"{entity_breakdown['PriorCase']} Prior Criminal Case Dockets",
                "count": entity_breakdown["PriorCase"],
                "icon": "📂"
            })
        if entity_breakdown.get("SourceRecord"):
            evidences_collected.append({
                "type": "INTELLIGENCE",
                "name": "Field Informant Intelligence Source Log",
                "count": entity_breakdown["SourceRecord"],
                "icon": "📄"
            })
        if not evidences_collected:
            evidences_collected.append({
                "type": "GENERAL",
                "name": f"{sum(entity_breakdown.values())} Network Graph Entities",
                "count": sum(entity_breakdown.values()),
                "icon": "🔍"
            })

        # 5. Cross-Case Overlap Query
        overlap_cypher = """
        MATCH (c1:Case {case_id: $case_id})-[:INVOLVES]->(e)<-[:INVOLVES]-(c2:Case)
        WHERE c2.case_id <> $case_id
        RETURN c2.case_id as id, c2.case_name as name, count(DISTINCT e) as shared_count,
               collect(DISTINCT coalesce(e.name, e.phone_number, e.account_number, elementId(e)))[0..4] as sample_entities
        ORDER BY shared_count DESC
        """
        overlap_res = session.run(overlap_cypher, {"case_id": case_id}).data()
        overlapping_cases = []
        for o in overlap_res:
            overlapping_cases.append({
                "case_id": o["id"],
                "case_name": o.get("name") or o["id"],
                "shared_count": o["shared_count"],
                "sample_entities": [str(x) for x in (o.get("sample_entities") or [])]
            })

        case_overlap = {
            "has_overlap": len(overlapping_cases) > 0,
            "overlap_count": len(overlapping_cases),
            "overlapping_cases": overlapping_cases
        }

        return {
            "case_id": case_id,
            "case_name": case_node.get("case_name") or f"Case {case_id}",
            "case_type": case_node.get("case_type") or "Criminal Investigation",
            "fir_number": fir_number,
            "date": case_date,
            "incident_date": case_date,
            "category_of_crime": category_of_crime,
            "status": case_node.get("status") or "OPEN",
            "priority": case_node.get("priority") or "MEDIUM",
            "lead_investigator": case_node.get("lead_investigator") or case_node.get("investigator") or "Special Investigation Team",
            "jurisdiction": case_node.get("jurisdiction") or "Law Enforcement",
            "summary": case_node.get("summary") or "Forensic case dossier records active graph connections across subjects, financial flows, and telecom communications.",
            "created_at": case_node.get("created_at") or case_date,
            "primary_suspects": suspects,
            "victims": victims,
            "evidences_collected": evidences_collected,
            "case_overlap": case_overlap,
            "metadata": case_node,
            "entity_breakdown": entity_breakdown,
            "total_entities": sum(entity_breakdown.values())
        }

    @classmethod
    def delete_case(cls, session: Session, case_id: str) -> Optional[Dict[str, Any]]:
        """
        Deletes a single case and detaches/removes exclusively-owned nodes and relationships,
        while preserving any entities shared with other cases (removing case_id from case_ids).
        Returns a dictionary summary or None if the case does not exist.
        """
        # 1. Verify case exists
        check_cypher = "MATCH (c:Case {case_id: $case_id}) RETURN count(c) AS count"
        res = session.run(check_cypher, {"case_id": case_id}).data()
        count = res[0]["count"] if res and "count" in res[0] else 0
        if not count:
            return None

        # 2. Count exclusive nodes & their attached relationships
        exclusive_stats_cypher = """
        MATCH (n)
        WHERE (n:Case AND n.case_id = $case_id)
           OR (size(n.case_ids) = 1 AND $case_id IN n.case_ids)
           OR n.case_ids = [$case_id]
        OPTIONAL MATCH (n)-[r]-()
        RETURN count(DISTINCT n) AS nodes_removed, count(DISTINCT r) AS exclusive_rels
        """
        ex_res = session.run(exclusive_stats_cypher, {"case_id": case_id}).data()
        nodes_removed = ex_res[0]["nodes_removed"] if ex_res else 0
        exclusive_rels = ex_res[0]["exclusive_rels"] if ex_res else 0

        # 3. Count shared case-scoped relationships (between multi-case nodes)
        shared_rels_cypher = """
        MATCH (a)-[r]->(b)
        WHERE r.case_id = $case_id
          AND NOT (
            (a:Case AND a.case_id = $case_id) OR (size(a.case_ids) = 1 AND $case_id IN a.case_ids) OR a.case_ids = [$case_id]
            OR (b:Case AND b.case_id = $case_id) OR (size(b.case_ids) = 1 AND $case_id IN b.case_ids) OR b.case_ids = [$case_id]
          )
        RETURN count(DISTINCT r) AS shared_rels
        """
        sh_res = session.run(shared_rels_cypher, {"case_id": case_id}).data()
        shared_rels = sh_res[0]["shared_rels"] if sh_res else 0
        total_rels_removed = exclusive_rels + shared_rels

        # 4. Count and detach shared nodes
        shared_nodes_cypher = """
        MATCH (n)
        WHERE $case_id IN n.case_ids AND size(n.case_ids) > 1
        RETURN count(DISTINCT n) AS nodes_detached
        """
        det_res = session.run(shared_nodes_cypher, {"case_id": case_id}).data()
        nodes_detached = det_res[0]["nodes_detached"] if det_res else 0

        # 5. Execute deletions & updates
        # 5a. Detach delete exclusively-owned nodes (and case node itself)
        delete_nodes_cypher = """
        MATCH (n)
        WHERE (n:Case AND n.case_id = $case_id)
           OR (size(n.case_ids) = 1 AND $case_id IN n.case_ids)
           OR n.case_ids = [$case_id]
        DETACH DELETE n
        """
        session.run(delete_nodes_cypher, {"case_id": case_id})

        # 5b. Delete any remaining relationships scoped to this case
        delete_rels_cypher = """
        MATCH ()-[r]->()
        WHERE r.case_id = $case_id
        DELETE r
        """
        session.run(delete_rels_cypher, {"case_id": case_id})

        # 5c. Update multi-case nodes: remove case_id from their array
        update_multicase_cypher = """
        MATCH (n)
        WHERE $case_id IN n.case_ids AND size(n.case_ids) > 1
        SET n.case_ids = [c IN n.case_ids WHERE c <> $case_id]
        """
        session.run(update_multicase_cypher, {"case_id": case_id})

        logger.info(
            f"Deleted case '{case_id}': {nodes_removed} nodes removed, "
            f"{nodes_detached} nodes detached, {total_rels_removed} rels removed."
        )

        return {
            "case_id": case_id,
            "nodes_removed": int(nodes_removed),
            "nodes_detached": int(nodes_detached),
            "relationships_removed": int(total_rels_removed),
            "status": "deleted"
        }

    @classmethod
    def reset_database(cls, session: Session) -> Dict[str, Any]:
        logger.warning("Executing complete database wipe via reset_database...")
        res = session.run("MATCH (n) DETACH DELETE n")
        logger.info("Database reset complete.")
        return {"status": "success", "message": "Graph database successfully cleared."}


