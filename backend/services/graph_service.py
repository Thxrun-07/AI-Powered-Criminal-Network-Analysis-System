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
        graph_type: str = "all",
        limit: int = 1000
    ) -> Dict[str, Any]:
        graph_type = (graph_type or "all").lower().strip()
        nodes_dict: Dict[str, Dict[str, Any]] = {}
        edges_dict: Dict[str, Dict[str, Any]] = {}

        # ---------------------------------------------------------
        # MODE 1: PERSON GRAPH ONLY (Clean suspect-to-suspect syndicate network)
        # ---------------------------------------------------------
        if graph_type in ["person", "persons", "suspect", "people"]:
            # 1. Fetch all Person nodes in scope
            p_cypher = """
            MATCH (p:Person)
            WHERE ($case_id IS NULL OR $case_id IN p.case_ids)
            RETURN labels(p) as n_labels, properties(p) as n_props
            LIMIT $limit
            """
            p_rows = session.run(p_cypher, {"case_id": case_id, "limit": limit}).data()
            for row in p_rows:
                props = row.get("n_props") or {}
                labs = row.get("n_labels") or ["Person"]
                pid = str(props.get("person_id") or f"P_{abs(hash(str(props)))}")
                role_desc = ""
                if props.get("roles"):
                    roles = props.get("roles")
                    r_item = roles[0] if isinstance(roles, list) else roles
                    role_desc = f" ({r_item})"
                elif props.get("status"):
                    role_desc = f" ({props.get('status')})"
                nodes_dict[pid] = {
                    "id": pid,
                    "labels": labs,
                    "name": f"{props.get('name') or pid}{role_desc}",
                    "case_ids": props.get("case_ids") or [],
                    "properties": props
                }

            # 2. Direct relationships between persons
            p_rel_cypher = """
            MATCH (p1:Person)-[r]->(p2:Person)
            WHERE ($case_id IS NULL OR ($case_id IN p1.case_ids AND $case_id IN p2.case_ids))
              AND p1 <> p2
            RETURN p1.person_id as src, p2.person_id as dst, type(r) as rel_type, properties(r) as props, elementId(r) as r_id
            LIMIT $limit
            """
            p_rels = session.run(p_rel_cypher, {"case_id": case_id, "limit": limit}).data()
            for pr in p_rels:
                src = str(pr["src"])
                dst = str(pr["dst"])
                rtype = pr.get("rel_type") or "ASSOCIATED_WITH"
                if src in nodes_dict and dst in nodes_dict:
                    eid = f"DIR_{src}_{rtype}_{dst}"
                    edges_dict[eid] = {
                        "id": eid,
                        "type": rtype,
                        "source": src,
                        "target": dst,
                        "properties": pr.get("props") or {}
                    }

            # 3. Communications-mediated links (calls between owned phones, aggregated by pair)
            p_call_cypher = """
            MATCH (p1:Person)-[:OWNS]->(ph1:Phone)-[c:CALLED]->(ph2:Phone)<-[:OWNS]-(p2:Person)
            WHERE ($case_id IS NULL OR ($case_id IN p1.case_ids AND $case_id IN p2.case_ids))
              AND p1 <> p2
            RETURN p1.person_id as src, p2.person_id as dst,
                   count(c) as call_count, sum(coalesce(c.duration_seconds, 0)) as total_duration
            """
            p_calls = session.run(p_call_cypher, {"case_id": case_id}).data()
            for pc in p_calls:
                src = str(pc["src"])
                dst = str(pc["dst"])
                c_count = int(pc.get("call_count") or 1)
                dur = int(pc.get("total_duration") or 0)
                if src in nodes_dict and dst in nodes_dict:
                    pair_key = f"CALL_LINK_{min(src, dst)}_{max(src, dst)}"
                    if pair_key in edges_dict:
                        existing = edges_dict[pair_key]
                        p = existing["properties"]
                        p["call_count"] = p.get("call_count", 0) + c_count
                        p["total_duration_seconds"] = p.get("total_duration_seconds", 0) + dur
                        tot_count = p["call_count"]
                        tot_dur = p["total_duration_seconds"]
                        mins = tot_dur // 60
                        secs = tot_dur % 60
                        dur_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
                        existing["type"] = f"COMMUNICATED ({tot_count} calls)"
                        p["summary"] = f"{tot_count} calls ({dur_str})"
                    else:
                        mins = dur // 60
                        secs = dur % 60
                        dur_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
                        edges_dict[pair_key] = {
                            "id": pair_key,
                            "type": f"COMMUNICATED ({c_count} calls)",
                            "source": src,
                            "target": dst,
                            "properties": {
                                "call_count": c_count,
                                "total_duration_seconds": dur,
                                "summary": f"{c_count} calls ({dur_str})"
                            }
                        }

            # 4. Financial transfer links between persons (aggregated by pair)
            p_tx_cypher = """
            MATCH (p1:Person)-[:OWNS]->(b1:BankAccount)-[t:TRANSFERRED_TO]->(b2:BankAccount)<-[:OWNS]-(p2:Person)
            WHERE ($case_id IS NULL OR ($case_id IN p1.case_ids AND $case_id IN p2.case_ids))
              AND p1 <> p2
            RETURN p1.person_id as src, p2.person_id as dst,
                   count(t) as tx_count, sum(coalesce(t.amount, 0)) as total_amount
            """
            p_txs = session.run(p_tx_cypher, {"case_id": case_id}).data()
            for pt in p_txs:
                src = str(pt["src"])
                dst = str(pt["dst"])
                amt = float(pt.get("total_amount") or 0)
                tx_count = int(pt.get("tx_count") or 1)
                if src in nodes_dict and dst in nodes_dict:
                    pair_key = f"TX_LINK_{min(src, dst)}_{max(src, dst)}"
                    if pair_key in edges_dict:
                        existing = edges_dict[pair_key]
                        p = existing["properties"]
                        p["tx_count"] = p.get("tx_count", 0) + tx_count
                        p["total_amount"] = p.get("total_amount", 0) + amt
                        tot_amt = p["total_amount"]
                        tot_tx = p["tx_count"]
                        existing["type"] = f"FUNDS_TRANSFER (₹{int(tot_amt):,})"
                        p["summary"] = f"Rs. {tot_amt:,.2f} ({tot_tx} txns)"
                    else:
                        edges_dict[pair_key] = {
                            "id": pair_key,
                            "type": f"FUNDS_TRANSFER (₹{int(amt):,})",
                            "source": src,
                            "target": dst,
                            "properties": {
                                "tx_count": tx_count,
                                "total_amount": amt,
                                "summary": f"Rs. {amt:,.2f} ({tx_count} txns)"
                            }
                        }

            # 5. Co-accused in same case
            co_cypher = """
            MATCH (p1:Person)<-[:INVOLVES]-(c:Case)-[:INVOLVES]->(p2:Person)
            WHERE ($case_id IS NULL OR c.case_id = $case_id)
              AND p1 <> p2
            RETURN p1.person_id as src, p2.person_id as dst, c.case_id as cid, c.case_name as cname
            LIMIT 200
            """
            co_rows = session.run(co_cypher, {"case_id": case_id}).data()
            for cr in co_rows:
                src = str(cr["src"])
                dst = str(cr["dst"])
                if src in nodes_dict and dst in nodes_dict:
                    already_connected = any(
                        (e["source"] == src and e["target"] == dst) or (e["source"] == dst and e["target"] == src)
                        for e in edges_dict.values()
                    )
                    if not already_connected:
                        eid = f"CO_ACCUSED_{min(src, dst)}_{max(src, dst)}"
                        edges_dict[eid] = {
                            "id": eid,
                            "type": "CO_ACCUSED",
                            "source": src,
                            "target": dst,
                            "properties": {
                                "case_id": cr.get("cid"),
                                "case_name": cr.get("cname"),
                                "summary": f"Co-accused in {cr.get('cname') or cr.get('cid')}"
                            }
                        }

            # Precalculate communications & transaction stats per person node
            for edge in edges_dict.values():
                e_type = edge.get("type") or ""
                props = edge.get("properties") or {}
                src = edge.get("source")
                dst = edge.get("target")

                if ("COMMUNICATED" in e_type or "CALL" in e_type) and src in nodes_dict and dst in nodes_dict:
                    count = int(props.get("call_count") or 1)
                    dur = int(props.get("total_duration_seconds", props.get("duration_seconds", 0)))
                    mins = dur // 60
                    secs = dur % 60
                    dur_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
                    summary = props.get("summary") or f"{count} calls ({dur_str})"

                    if "communications" not in nodes_dict[src]["properties"]:
                        nodes_dict[src]["properties"]["communications"] = {}
                    nodes_dict[src]["properties"]["communications"][dst] = {
                        "partner_id": dst,
                        "partner_name": nodes_dict[dst].get("name") or dst,
                        "call_count": count,
                        "total_duration_seconds": dur,
                        "summary": summary
                    }
                    nodes_dict[src]["properties"]["total_calls"] = nodes_dict[src]["properties"].get("total_calls", 0) + count

                    if "communications" not in nodes_dict[dst]["properties"]:
                        nodes_dict[dst]["properties"]["communications"] = {}
                    nodes_dict[dst]["properties"]["communications"][src] = {
                        "partner_id": src,
                        "partner_name": nodes_dict[src].get("name") or src,
                        "call_count": count,
                        "total_duration_seconds": dur,
                        "summary": summary
                    }
                    nodes_dict[dst]["properties"]["total_calls"] = nodes_dict[dst]["properties"].get("total_calls", 0) + count

                elif ("FUNDS_TRANSFER" in e_type or "TRANSFERRED" in e_type or "TRANSACTION" in e_type) and src in nodes_dict and dst in nodes_dict:
                    t_count = int(props.get("tx_count") or 1)
                    t_amt = float(props.get("total_amount", props.get("amount", 0)))
                    summary = props.get("summary") or f"{t_count} txns (₹{int(t_amt):,})"

                    if "transactions" not in nodes_dict[src]["properties"]:
                        nodes_dict[src]["properties"]["transactions"] = {}
                    nodes_dict[src]["properties"]["transactions"][dst] = {
                        "partner_id": dst,
                        "partner_name": nodes_dict[dst].get("name") or dst,
                        "tx_count": t_count,
                        "total_amount": t_amt,
                        "summary": summary
                    }
                    nodes_dict[src]["properties"]["total_transactions"] = nodes_dict[src]["properties"].get("total_transactions", 0) + t_count
                    nodes_dict[src]["properties"]["total_amount_transferred"] = nodes_dict[src]["properties"].get("total_amount_transferred", 0.0) + t_amt

                    if "transactions" not in nodes_dict[dst]["properties"]:
                        nodes_dict[dst]["properties"]["transactions"] = {}
                    nodes_dict[dst]["properties"]["transactions"][src] = {
                        "partner_id": src,
                        "partner_name": nodes_dict[src].get("name") or src,
                        "tx_count": t_count,
                        "total_amount": t_amt,
                        "summary": summary
                    }
                    nodes_dict[dst]["properties"]["total_transactions"] = nodes_dict[dst]["properties"].get("total_transactions", 0) + t_count
                    nodes_dict[dst]["properties"]["total_amount_transferred"] = nodes_dict[dst]["properties"].get("total_amount_transferred", 0.0) + t_amt

            filtered_nodes = list(nodes_dict.values())
            edges_list = list(edges_dict.values())
            return {
                "case_id": case_id,
                "graph_type": "person",
                "total_nodes": len(filtered_nodes),
                "total_edges": len(edges_list),
                "nodes": filtered_nodes,
                "edges": edges_list
            }

        # ---------------------------------------------------------
        # MODE 2: CDR GRAPH ONLY (Clean telecommunication calls & towers)
        # ---------------------------------------------------------
        if graph_type in ["cdr", "telecom", "phone", "calls"]:
            cdr_cypher = """
            MATCH (ph1:Phone)
            WHERE ($case_id IS NULL OR $case_id IN ph1.case_ids)
            OPTIONAL MATCH (p1:Person)-[:OWNS|USES]->(ph1)
            OPTIONAL MATCH (ph1)-[r:CALLED]->(ph2:Phone)
            WHERE ($case_id IS NULL OR r.case_id = $case_id OR $case_id IN ph2.case_ids)
            OPTIONAL MATCH (p2:Person)-[:OWNS|USES]->(ph2)
            RETURN labels(ph1) as n_labels, properties(ph1) as n_props,
                   p1.name as n_owner_name, p1.person_id as n_owner_id,
                   elementId(r) as r_id, type(r) as r_type, properties(r) as r_props,
                   labels(ph2) as m_labels, properties(ph2) as m_props,
                   p2.name as m_owner_name, p2.person_id as m_owner_id
            LIMIT $limit
            """
            rows = session.run(cdr_cypher, {"case_id": case_id, "limit": limit}).data()
            for row in rows:
                if row.get("n_owner_name") and row.get("n_props") is not None:
                    row["n_props"]["associated_person_name"] = row["n_owner_name"]
                    if row.get("n_owner_id"):
                        row["n_props"]["associated_person_id"] = row["n_owner_id"]
                if row.get("m_owner_name") and row.get("m_props") is not None:
                    row["m_props"]["associated_person_name"] = row["m_owner_name"]
                    if row.get("m_owner_id"):
                        row["m_props"]["associated_person_id"] = row["m_owner_id"]

            # Also fetch tower attachments
            try:
                tower_cypher = """
                MATCH (ph:Phone)-[r:LOCATED_AT]->(tower:CellTower)
                WHERE ($case_id IS NULL OR $case_id IN ph.case_ids)
                RETURN labels(ph) as n_labels, properties(ph) as n_props,
                       elementId(r) as r_id, type(r) as r_type, properties(r) as r_props,
                       labels(tower) as m_labels, properties(tower) as m_props
                LIMIT 150
                """
                tower_rows = session.run(tower_cypher, {"case_id": case_id}).data()
                rows.extend(tower_rows)
            except Exception:
                pass

        # ---------------------------------------------------------
        # MODE 3: FINANCIAL GRAPH ONLY (Clean bank accounts & transfers)
        # ---------------------------------------------------------
        elif graph_type in ["financial", "finance", "bank", "money"]:
            fin_cypher = """
            MATCH (b1:BankAccount)
            WHERE ($case_id IS NULL OR $case_id IN b1.case_ids)
            OPTIONAL MATCH (b1)-[r:TRANSFERRED_TO]->(b2:BankAccount)
            WHERE ($case_id IS NULL OR r.case_id = $case_id OR $case_id IN b2.case_ids)
            RETURN labels(b1) as n_labels, properties(b1) as n_props,
                   elementId(r) as r_id, type(r) as r_type, properties(r) as r_props,
                   labels(b2) as m_labels, properties(b2) as m_props
            LIMIT $limit
            """
            rows = session.run(fin_cypher, {"case_id": case_id, "limit": limit}).data()

        # ---------------------------------------------------------
        # MODE 4: FULL ECOSYSTEM GRAPH
        # ---------------------------------------------------------
        else:
            if core_only:
                cypher = """
                MATCH (n)
                WHERE ($case_id IS NULL OR $case_id IN n.case_ids)
                  AND NOT 'Block' IN labels(n)
                  AND NOT 'Transaction' IN labels(n)
                  AND ($labels IS NULL OR size($labels) = 0 OR any(l IN labels(n) WHERE l IN $labels))
                  AND NOT ('Phone' IN labels(n) AND (n.owner_person_id IS NULL OR n.owner_person_id = '') AND NOT coalesce(n.phone_number, '') STARTS WITH '99999')
                OPTIONAL MATCH (n)-[r]->(m)
                WHERE (m IS NULL OR $case_id IS NULL OR $case_id IN m.case_ids)
                  AND (m IS NULL OR NOT 'Block' IN labels(m))
                  AND (m IS NULL OR NOT 'Transaction' IN labels(m))
                  AND (m IS NULL OR $labels IS NULL OR size($labels) = 0 OR any(l IN labels(m) WHERE l IN $labels))
                  AND NOT (m IS NOT NULL AND 'Phone' IN labels(m) AND (m.owner_person_id IS NULL OR m.owner_person_id = '') AND NOT coalesce(m.phone_number, '') STARTS WITH '99999')
                RETURN labels(n) as n_labels, properties(n) as n_props,
                       elementId(r) as r_id, type(r) as r_type, properties(r) as r_props,
                       labels(m) as m_labels, properties(m) as m_props
                LIMIT $limit
                """
            else:
                cypher = """
                MATCH (n)
                WHERE ($case_id IS NULL OR $case_id IN n.case_ids)
                  AND NOT 'Block' IN labels(n)
                  AND NOT 'Transaction' IN labels(n)
                  AND ($labels IS NULL OR size($labels) = 0 OR any(l IN labels(n) WHERE l IN $labels))
                OPTIONAL MATCH (n)-[r]->(m)
                WHERE (m IS NULL OR $case_id IS NULL OR $case_id IN m.case_ids)
                  AND (m IS NULL OR NOT 'Block' IN labels(m))
                  AND (m IS NULL OR NOT 'Transaction' IN labels(m))
                  AND (m IS NULL OR $labels IS NULL OR size($labels) = 0 OR any(l IN labels(m) WHERE l IN $labels))
                RETURN labels(n) as n_labels, properties(n) as n_props,
                       elementId(r) as r_id, type(r) as r_type, properties(r) as r_props,
                       labels(m) as m_labels, properties(m) as m_props
                LIMIT $limit
                """
            rows = session.run(cypher, {"case_id": case_id, "labels": node_labels, "limit": limit}).data()

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
                ph_num = str(props.get("phone_number") or node_id)
                owner = props.get("associated_person_name") or props.get("registered_owner") or props.get("subscriber_name") or props.get("owner_name")
                if owner and str(owner).lower() not in ["unknown", "n/a", "none"]:
                    clean_owner = str(owner).split("\n")[0].strip()
                    return f"{ph_num}\n({clean_owner})"
                return ph_num
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

                # -------------------------------------------------------------
                # 1. Consolidate parallel calls into a single edge between A & B
                # -------------------------------------------------------------
                if r_type in ["CALLED", "CALL", "COMMUNICATED", "COMMUNICATION"]:
                    pair_key = f"CALL_{min(n_id, m_id)}_{max(n_id, m_id)}"
                    dur = int(r_props.get("duration_seconds") or 0)
                    ts = r_props.get("timestamp") or ""
                    tower = r_props.get("cell_tower") or ""

                    if pair_key in edges_dict:
                        existing = edges_dict[pair_key]
                        p = existing["properties"]
                        p["call_count"] = p.get("call_count", 1) + 1
                        p["total_duration_seconds"] = p.get("total_duration_seconds", 0) + dur
                        dur_total = p["total_duration_seconds"]
                        mins = dur_total // 60
                        secs = dur_total % 60
                        dur_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
                        count = p["call_count"]
                        existing["type"] = f"CALLED ({count}x)"
                        p["summary"] = f"{count} calls ({dur_str})"
                        if "history" not in p:
                            p["history"] = []
                        if len(p["history"]) < 10 and (ts or dur):
                            p["history"].append({"timestamp": ts, "duration": dur, "tower": tower, "from": n_id, "to": m_id})
                    else:
                        mins = dur // 60
                        secs = dur % 60
                        dur_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
                        edges_dict[pair_key] = {
                            "id": pair_key,
                            "type": "CALLED (1x)",
                            "source": n_id,
                            "target": m_id,
                            "properties": {
                                "call_count": 1,
                                "total_duration_seconds": dur,
                                "summary": f"1 call ({dur_str})",
                                "history": [{"timestamp": ts, "duration": dur, "tower": tower, "from": n_id, "to": m_id}] if (ts or dur) else []
                            }
                        }
                    continue

                # -------------------------------------------------------------
                # 2. Consolidate parallel financial transfers between A & B
                # -------------------------------------------------------------
                elif r_type in ["TRANSFERRED_TO", "TRANSACTION", "DEPOSITED_TO", "FUNDS_TRANSFER"]:
                    pair_key = f"TX_{min(n_id, m_id)}_{max(n_id, m_id)}"
                    amt = float(r_props.get("amount") or 0)
                    ts = r_props.get("timestamp") or ""
                    tx_id = r_props.get("transaction_id") or ""
                    curr = r_props.get("currency") or "INR"

                    if pair_key in edges_dict:
                        existing = edges_dict[pair_key]
                        p = existing["properties"]
                        p["tx_count"] = p.get("tx_count", 1) + 1
                        p["total_amount"] = p.get("total_amount", 0.0) + amt
                        tot = p["total_amount"]
                        count = p["tx_count"]
                        existing["type"] = f"TRANSFERRED_TO ({count}x)"
                        p["summary"] = f"{count} txns (₹{int(tot):,})"
                        if "history" not in p:
                            p["history"] = []
                        if len(p["history"]) < 10 and (ts or amt):
                            p["history"].append({"timestamp": ts, "amount": amt, "tx_id": tx_id, "from": n_id, "to": m_id, "currency": curr})
                    else:
                        edges_dict[pair_key] = {
                            "id": pair_key,
                            "type": "TRANSFERRED_TO (1x)",
                            "source": n_id,
                            "target": m_id,
                            "properties": {
                                "tx_count": 1,
                                "total_amount": amt,
                                "summary": f"1 txn (₹{int(amt):,})",
                                "history": [{"timestamp": ts, "amount": amt, "tx_id": tx_id, "from": n_id, "to": m_id, "currency": curr}] if (ts or amt) else []
                            }
                        }
                    continue

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

        # 3. Connect BankAccount, Vehicle, and Phone entities to their existing Person owner if not already linked
        for node_id, node in list(nodes_dict.items()):
            labels = node.get("labels") or []
            if "BankAccount" in labels or "Vehicle" in labels or "Phone" in labels:
                has_owner_edge = any(
                    e.get("type") in ["OWNS", "USES", "HAS_PHONE"] and (e.get("target") == node_id or e.get("source") == node_id)
                    for e in edges_dict.values()
                )
                if not has_owner_edge:
                    props = node.get("properties") or {}
                    owner_hint = (props.get("holder_name") or props.get("registered_owner") or props.get("owner_name") or props.get("associated_person_name") or "").strip()
                    owner_person_id = props.get("owner_person_id") or props.get("associated_person_id")

                    # Search for matching existing Person node
                    matched_person_id = None
                    for pid, pnode in nodes_dict.items():
                        if "Person" in (pnode.get("labels") or []):
                            pname = (pnode.get("name") or "").split("\n")[0].strip()
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

        # 3b. Resolve and cross-populate associated Person for every Phone node and update display name
        for node_id, node in list(nodes_dict.items()):
            labels = node.get("labels") or []
            if "Phone" in labels:
                props = node.get("properties") or {}
                assoc_name = props.get("associated_person_name") or props.get("registered_owner") or props.get("subscriber_name") or props.get("owner_name")
                assoc_id = props.get("associated_person_id") or props.get("owner_person_id")

                if not assoc_name:
                    for e in edges_dict.values():
                        if e.get("type") in ["OWNS", "USES", "HAS_PHONE"]:
                            if e.get("target") == node_id and e.get("source") in nodes_dict:
                                partner = nodes_dict[e["source"]]
                                if "Person" in (partner.get("labels") or []):
                                    assoc_name = partner.get("properties", {}).get("name") or partner.get("name")
                                    assoc_id = e["source"]
                                    break
                            elif e.get("source") == node_id and e.get("target") in nodes_dict:
                                partner = nodes_dict[e["target"]]
                                if "Person" in (partner.get("labels") or []):
                                    assoc_name = partner.get("properties", {}).get("name") or partner.get("name")
                                    assoc_id = e["target"]
                                    break

                if not assoc_name:
                    raw_ph = str(props.get("phone_number") or node_id)
                    for pid, pnode in nodes_dict.items():
                        if "Person" in (pnode.get("labels") or []):
                            p_props = pnode.get("properties") or {}
                            ph_list = p_props.get("phone_numbers") or []
                            if isinstance(ph_list, str):
                                ph_list = [ph_list]
                            if raw_ph in ph_list or any(raw_ph in str(x) for x in ph_list):
                                assoc_name = p_props.get("name") or pnode.get("name")
                                assoc_id = pid
                                break

                if assoc_name and str(assoc_name).lower() not in ["unknown", "n/a", "none"]:
                    clean_assoc = str(assoc_name).split("\n")[0].strip()
                    props["associated_person_name"] = clean_assoc
                    if assoc_id:
                        props["associated_person_id"] = assoc_id
                    raw_ph = str(props.get("phone_number") or node_id)
                    node["name"] = f"{raw_ph}\n({clean_assoc})"

        edges_list = list(edges_dict.values())

        # 4. Cross-populate communication and financial transaction statistics into every node
        for edge in edges_list:
            e_type = edge.get("type") or ""
            props = edge.get("properties") or {}
            src = edge.get("source")
            dst = edge.get("target")

            if ("CALLED" in e_type or "COMMUNICATED" in e_type) and src in nodes_dict and dst in nodes_dict:
                count = int(props.get("call_count") or 1)
                dur = int(props.get("total_duration_seconds", props.get("duration_seconds", 0)))
                mins = dur // 60
                secs = dur % 60
                dur_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
                summary = props.get("summary") or f"{count} calls ({dur_str})"

                # src node stats
                if "communications" not in nodes_dict[src]["properties"]:
                    nodes_dict[src]["properties"]["communications"] = {}
                nodes_dict[src]["properties"]["communications"][dst] = {
                    "partner_id": dst,
                    "partner_name": nodes_dict[dst].get("name") or dst,
                    "call_count": count,
                    "total_duration_seconds": dur,
                    "summary": summary
                }
                nodes_dict[src]["properties"]["total_calls"] = nodes_dict[src]["properties"].get("total_calls", 0) + count

                # dst node stats
                if "communications" not in nodes_dict[dst]["properties"]:
                    nodes_dict[dst]["properties"]["communications"] = {}
                nodes_dict[dst]["properties"]["communications"][src] = {
                    "partner_id": src,
                    "partner_name": nodes_dict[src].get("name") or src,
                    "call_count": count,
                    "total_duration_seconds": dur,
                    "summary": summary
                }
                nodes_dict[dst]["properties"]["total_calls"] = nodes_dict[dst]["properties"].get("total_calls", 0) + count

            elif ("TRANSFERRED" in e_type or "TRANSACTION" in e_type or "FUNDS_TRANSFER" in e_type) and src in nodes_dict and dst in nodes_dict:
                tx_count = int(props.get("tx_count") or 1)
                total_amt = float(props.get("total_amount", props.get("amount", 0)))
                summary = props.get("summary") or f"{tx_count} txns (₹{int(total_amt):,})"

                # src node stats
                if "transactions" not in nodes_dict[src]["properties"]:
                    nodes_dict[src]["properties"]["transactions"] = {}
                nodes_dict[src]["properties"]["transactions"][dst] = {
                    "partner_id": dst,
                    "partner_name": nodes_dict[dst].get("name") or dst,
                    "tx_count": tx_count,
                    "total_amount": total_amt,
                    "summary": summary
                }
                nodes_dict[src]["properties"]["total_transactions"] = nodes_dict[src]["properties"].get("total_transactions", 0) + tx_count
                nodes_dict[src]["properties"]["total_amount_transferred"] = nodes_dict[src]["properties"].get("total_amount_transferred", 0.0) + total_amt

                # dst node stats
                if "transactions" not in nodes_dict[dst]["properties"]:
                    nodes_dict[dst]["properties"]["transactions"] = {}
                nodes_dict[dst]["properties"]["transactions"][src] = {
                    "partner_id": src,
                    "partner_name": nodes_dict[src].get("name") or src,
                    "tx_count": tx_count,
                    "total_amount": total_amt,
                    "summary": summary
                }
                nodes_dict[dst]["properties"]["total_transactions"] = nodes_dict[dst]["properties"].get("total_transactions", 0) + tx_count
                nodes_dict[dst]["properties"]["total_amount_transferred"] = nodes_dict[dst]["properties"].get("total_amount_transferred", 0.0) + total_amt

        # 5. Filter out isolated / disconnected nodes only when core_only is True
        if core_only:
            connected_node_ids = set()
            for e in edges_list:
                connected_node_ids.add(e["source"])
                connected_node_ids.add(e["target"])
            filtered_nodes = [node for n_id, node in nodes_dict.items() if n_id in connected_node_ids]
        else:
            filtered_nodes = list(nodes_dict.values())

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

        # Fetch 1-hop connections (excluding Blockchain Block ledger nodes and CHAINED_TO internal edges)
        rel_cypher = """
        MATCH (n)-[r]-(neighbor)
        WHERE (n.person_id = $id OR n.phone_number = $id OR n.account_number = $id
           OR n.vin = $id OR n.handle_id = $id OR n.ip_address = $id
           OR n.location_id = $id OR n.fir_id = $id OR n.prior_case_id = $id
           OR n.case_id = $id OR n.cell_tower_id = $id OR n.source_record_id = $id
           OR n.license_plate = $id OR n.transaction_id = $id
           OR elementId(n) = $id)
           AND NOT 'Block' IN labels(neighbor)
           AND NOT type(r) IN ['CHAINED_TO', 'PREVIOUS_BLOCK']
        RETURN type(r) as relationship_type,
               startNode(r) = n as is_outgoing,
               properties(r) as relationship_properties,
               labels(neighbor) as neighbor_labels,
               coalesce(neighbor.person_id, neighbor.phone_number, neighbor.account_number, neighbor.vin, neighbor.handle_id, neighbor.ip_address, neighbor.case_id, neighbor.cell_tower_id, neighbor.fir_id, neighbor.prior_case_id, elementId(neighbor)) as neighbor_id,
               coalesce(neighbor.name, neighbor.phone_number, neighbor.account_number, neighbor.vin, neighbor.handle, neighbor.case_name, neighbor.case_id) as neighbor_name,
               properties(neighbor) as neighbor_properties
        """
        rel_rows = session.run(rel_cypher, {"id": entity_id}).data()

        seen_keys: Dict[Tuple[str, str, str], int] = {}
        connections: List[Dict[str, Any]] = []
        for row in rel_rows:
            n_labels = row.get("neighbor_labels") or []
            if "Block" in n_labels:
                continue
            rel_t = row["relationship_type"]
            if rel_t in ["CHAINED_TO", "PREVIOUS_BLOCK"]:
                continue

            nid = str(row["neighbor_id"])
            nname = row.get("neighbor_name") or nid
            direction = "OUTGOING" if row["is_outgoing"] else "INCOMING"

            dedup_key = (rel_t, direction, nid)
            rel_props = dict(row.get("relationship_properties") or {})
            call_dur = int(rel_props.get("duration_seconds") or rel_props.get("call_duration") or 0)

            if dedup_key in seen_keys:
                idx = seen_keys[dedup_key]
                existing = connections[idx]
                existing_props = existing.get("relationship_properties") or {}

                if rel_t in ["TRANSFERRED_TO", "TRANSACTION", "DEPOSITED_TO", "FUNDS_TRANSFER"]:
                    t_count = int(existing_props.get("tx_count", 1)) + 1
                    t_amt = float(existing_props.get("total_amount", existing_props.get("amount", 0))) + float(rel_props.get("amount", 0))
                    existing_props["tx_count"] = t_count
                    existing_props["total_amount"] = t_amt
                    existing_props["summary"] = f"{t_count} txns (₹{int(t_amt):,})"
                    existing["relationship_properties"] = existing_props
                    continue
                elif rel_t in ["CALLED", "COMMUNICATED"]:
                    c_count = int(existing_props.get("call_count", 1)) + 1
                    tot_dur = int(existing_props.get("total_duration_seconds", existing_props.get("duration_seconds", 0))) + call_dur
                    existing_props["call_count"] = c_count
                    existing_props["total_duration_seconds"] = tot_dur
                    mins = tot_dur // 60
                    secs = tot_dur % 60
                    dur_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
                    existing_props["summary"] = f"{c_count} calls ({dur_str})"
                    existing["relationship_properties"] = existing_props
                    continue
                else:
                    continue

            call_count = int(rel_props.get("call_count") or 1)
            tot_dur = int(rel_props.get("total_duration_seconds") or rel_props.get("duration_seconds") or call_dur)
            mins = tot_dur // 60
            secs = tot_dur % 60
            dur_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"

            if rel_t in ["CALLED", "COMMUNICATED"]:
                rel_props["call_count"] = call_count
                rel_props["total_duration_seconds"] = tot_dur
                rel_props["summary"] = rel_props.get("summary") or f"{call_count} calls ({dur_str})"
            elif rel_t in ["TRANSFERRED_TO", "TRANSACTION", "DEPOSITED_TO", "FUNDS_TRANSFER"]:
                t_count = int(rel_props.get("tx_count") or 1)
                t_amt = float(rel_props.get("total_amount") or rel_props.get("amount") or 0)
                rel_props["tx_count"] = t_count
                rel_props["total_amount"] = t_amt
                rel_props["summary"] = rel_props.get("summary") or f"{t_count} txns (₹{int(t_amt):,})"

            seen_keys[dedup_key] = len(connections)
            connections.append({
                "relationship": rel_t,
                "rel_type": rel_t,
                "direction": direction,
                "relationship_properties": rel_props,
                "neighbor_id": nid,
                "target_id": nid,
                "neighbor_name": nname,
                "target_name": nname,
                "neighbor_labels": n_labels,
                "neighbor_properties": row.get("neighbor_properties") or {}
            })

        # Enrich target_node properties with aggregated communications and transaction breakdown
        target_props = dict(target_node)
        comm_dict = {}
        tx_dict = {}

        for conn in connections:
            r_type = conn["relationship"]
            r_props = conn.get("relationship_properties") or {}
            t_id = conn["target_id"]

            if r_type in ["CALLED", "COMMUNICATED"]:
                comm_dict[t_id] = {
                    "partner_id": t_id,
                    "partner_name": conn["target_name"],
                    "call_count": r_props.get("call_count", 1),
                    "total_duration_seconds": r_props.get("total_duration_seconds", 0),
                    "summary": r_props.get("summary", "")
                }
            elif r_type in ["TRANSFERRED_TO", "TRANSACTION", "DEPOSITED_TO", "FUNDS_TRANSFER"]:
                tx_dict[t_id] = {
                    "partner_id": t_id,
                    "partner_name": conn["target_name"],
                    "tx_count": r_props.get("tx_count", 1),
                    "total_amount": r_props.get("total_amount", r_props.get("amount", 0)),
                    "summary": r_props.get("summary", "")
                }

        if comm_dict:
            target_props["communications"] = comm_dict
            target_props["total_calls"] = sum(c["call_count"] for c in comm_dict.values())
        if tx_dict:
            target_props["transactions"] = tx_dict
            target_props["total_transactions"] = sum(t["tx_count"] for t in tx_dict.values())
            target_props["total_amount_transferred"] = sum(float(t["total_amount"]) for t in tx_dict.values())

        # Check if target_node is a Phone and resolve associated Person
        if "Phone" in labels:
            associated_person = None
            associated_person_id = None
            for conn in connections:
                n_labels = conn.get("neighbor_labels") or []
                r_type = conn.get("relationship") or ""
                if "Person" in n_labels or r_type in ["OWNS", "USES", "HAS_PHONE", "SUBSCRIBER"]:
                    associated_person = conn.get("target_name")
                    associated_person_id = conn.get("target_id")
                    break
            if not associated_person:
                associated_person = target_props.get("registered_owner") or target_props.get("owner_name")
                associated_person_id = target_props.get("owner_person_id")

            if associated_person and str(associated_person).lower() not in ["unknown", "n/a", "none"]:
                target_props["associated_person_name"] = str(associated_person).split("\n")[0].strip()
                if associated_person_id:
                    target_props["associated_person_id"] = associated_person_id

        return {
            "entity_id": entity_id,
            "labels": labels,
            "properties": target_props,
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
        # 1. Verify case exists and resolve exact ID
        check_cypher = """
        MATCH (c:Case)
        WHERE c.case_id = $case_id OR c.id = $case_id OR toLower(c.case_id) = toLower($case_id)
        RETURN count(c) AS count, coalesce(c.case_id, c.id) AS resolved_id
        """
        res = session.run(check_cypher, {"case_id": case_id}).data()
        if not res or not res[0].get("count"):
            return None
        resolved_case_id = res[0].get("resolved_id") or case_id

        # 2. Count exclusive nodes & their attached relationships
        exclusive_stats_cypher = """
        MATCH (n)
        WHERE (n:Case AND (n.case_id = $case_id OR n.id = $case_id))
           OR (size(n.case_ids) = 1 AND $case_id IN n.case_ids)
           OR n.case_ids = [$case_id]
           OR ((n)<-[:INVOLVES]-(c:Case) AND (c.case_id = $case_id OR c.id = $case_id) AND NOT (n)<-[:INVOLVES]-(:Case WHERE case_id <> $case_id AND id <> $case_id))
        OPTIONAL MATCH (n)-[r]-()
        RETURN count(DISTINCT n) AS nodes_removed, count(DISTINCT r) AS exclusive_rels
        """
        ex_res = session.run(exclusive_stats_cypher, {"case_id": resolved_case_id}).data()
        nodes_removed = ex_res[0]["nodes_removed"] if ex_res else 0
        exclusive_rels = ex_res[0]["exclusive_rels"] if ex_res else 0

        # 3. Count shared case-scoped relationships (between multi-case nodes)
        shared_rels_cypher = """
        MATCH (a)-[r]->(b)
        WHERE r.case_id = $case_id
          AND NOT (
            (a:Case AND (a.case_id = $case_id OR a.id = $case_id)) OR (size(a.case_ids) = 1 AND $case_id IN a.case_ids) OR a.case_ids = [$case_id]
            OR (b:Case AND (b.case_id = $case_id OR b.id = $case_id)) OR (size(b.case_ids) = 1 AND $case_id IN b.case_ids) OR b.case_ids = [$case_id]
          )
        RETURN count(DISTINCT r) AS shared_rels
        """
        sh_res = session.run(shared_rels_cypher, {"case_id": resolved_case_id}).data()
        shared_rels = sh_res[0]["shared_rels"] if sh_res else 0
        total_rels_removed = exclusive_rels + shared_rels

        # 4. Count and detach shared nodes
        shared_nodes_cypher = """
        MATCH (n)
        WHERE $case_id IN n.case_ids AND size(n.case_ids) > 1
        RETURN count(DISTINCT n) AS nodes_detached
        """
        det_res = session.run(shared_nodes_cypher, {"case_id": resolved_case_id}).data()
        nodes_detached = det_res[0]["nodes_detached"] if det_res else 0

        # 5. Execute deletions & updates within an explicit committed transaction
        delete_nodes_cypher = """
        MATCH (n)
        WHERE (n:Case AND (n.case_id = $case_id OR n.id = $case_id))
           OR (size(n.case_ids) = 1 AND $case_id IN n.case_ids)
           OR n.case_ids = [$case_id]
           OR ((n)<-[:INVOLVES]-(c:Case) AND (c.case_id = $case_id OR c.id = $case_id) AND NOT (n)<-[:INVOLVES]-(:Case WHERE case_id <> $case_id AND id <> $case_id))
        DETACH DELETE n
        """

        delete_rels_cypher = """
        MATCH ()-[r]->()
        WHERE r.case_id = $case_id
        DELETE r
        """

        update_multicase_cypher = """
        MATCH (n)
        WHERE $case_id IN n.case_ids AND size(n.case_ids) > 1
        SET n.case_ids = [c IN n.case_ids WHERE c <> $case_id]
        """

        with session.begin_transaction() as tx:
            r1 = tx.run(delete_nodes_cypher, {"case_id": resolved_case_id})
            if hasattr(r1, "consume"):
                r1.consume()
            r2 = tx.run(delete_rels_cypher, {"case_id": resolved_case_id})
            if hasattr(r2, "consume"):
                r2.consume()
            r3 = tx.run(update_multicase_cypher, {"case_id": resolved_case_id})
            if hasattr(r3, "consume"):
                r3.consume()
            if hasattr(tx, "commit") and not getattr(tx, "_is_mock", False):
                try:
                    tx.commit()
                except Exception:
                    pass

        # 5d. Purge blockchain evidence blocks for this deleted case
        try:
            from backend.services.blockchain_service import BlockchainService
            BlockchainService.purge_case_blocks(resolved_case_id, session=session)
        except Exception as e:
            logger.error(f"Failed to purge blockchain blocks for case '{resolved_case_id}': {e}")

        logger.info(
            f"Deleted case '{resolved_case_id}': {nodes_removed} nodes removed, "
            f"{nodes_detached} nodes detached, {total_rels_removed} rels removed."
        )

        return {
            "case_id": resolved_case_id,
            "nodes_removed": int(nodes_removed),
            "nodes_detached": int(nodes_detached),
            "relationships_removed": int(total_rels_removed),
            "status": "deleted"
        }

    @classmethod
    def reset_database(cls, session: Session) -> Dict[str, Any]:
        logger.warning("Executing complete database wipe via reset_database...")
        res = session.run("MATCH (n) DETACH DELETE n")
        if hasattr(res, "consume"):
            res.consume()
        try:
            from backend.services.blockchain_service import BlockchainService
            BlockchainService.reset_ledger(session=session)
        except Exception as e:
            logger.error(f"Failed to reset blockchain ledger: {e}")
        logger.info("Database reset complete.")
        return {"status": "success", "message": "Graph database successfully cleared."}


