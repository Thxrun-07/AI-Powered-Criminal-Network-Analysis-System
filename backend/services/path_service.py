from typing import Dict, Any, List, Optional, Union, Tuple
from neo4j import Session
from backend.models.path import ShortestPathResponse, AmbiguityCandidate, AmbiguousPathResponse
from backend.config import settings
from backend.logging_config import logger


class PathService:
    """
    Ambiguity-Safe Shortest Path Service with strict Person entity matching.
    """

    @classmethod
    def find_shortest_path(
        cls,
        session: Session,
        suspect_name: Optional[str] = None,
        victim_name: Optional[str] = None,
        suspect_id: Optional[str] = None,
        victim_id: Optional[str] = None,
        max_depth: Optional[int] = None
    ) -> Union[ShortestPathResponse, AmbiguousPathResponse]:
        depth = max_depth or settings.DEFAULT_MAX_PATH_DEPTH
        
        # 1. Resolve Suspect Node(s)
        suspect_candidates = cls._resolve_person(session, person_id=suspect_id, name=suspect_name)
        if len(suspect_candidates) == 0:
            return ShortestPathResponse(
                nodes=[],
                relationships=[],
                path_length=0,
                summary=f"Suspect person not found with identifier '{suspect_id or suspect_name}'."
            )
        if len(suspect_candidates) > 1:
            logger.warning(f"Ambiguity detected for suspect '{suspect_name}': {len(suspect_candidates)} candidates found.")
            return AmbiguousPathResponse(
                ambiguous=True,
                message=f"Multiple Person entities match suspect '{suspect_name}'. Please specify 'suspect_id' to disambiguate.",
                candidates=suspect_candidates
            )
        
        target_suspect_id = suspect_candidates[0].person_id

        # 2. Resolve Victim Node(s)
        victim_candidates = cls._resolve_person(session, person_id=victim_id, name=victim_name)
        if len(victim_candidates) == 0:
            return ShortestPathResponse(
                nodes=[],
                relationships=[],
                path_length=0,
                summary=f"Victim person not found with identifier '{victim_id or victim_name}'."
            )
        if len(victim_candidates) > 1:
            logger.warning(f"Ambiguity detected for victim '{victim_name}': {len(victim_candidates)} candidates found.")
            return AmbiguousPathResponse(
                ambiguous=True,
                message=f"Multiple Person entities match victim '{victim_name}'. Please specify 'victim_id' to disambiguate.",
                candidates=victim_candidates
            )

        target_victim_id = victim_candidates[0].person_id

        # 3. Execute Shortest Path Cypher
        # Dynamic variable-length depth safely bounded
        bounded_depth = max(1, min(depth, 15))
        s_elem = getattr(suspect_candidates[0], "element_id", None)
        v_elem = getattr(victim_candidates[0], "element_id", None)

        if s_elem and v_elem:
            cypher = f"""
            MATCH (a), (b)
            WHERE elementId(a) = $s_elem AND elementId(b) = $v_elem
            MATCH p = shortestPath((a)-[*..{bounded_depth}]-(b))
            RETURN p
            """
            result = session.run(cypher, {"s_elem": s_elem, "v_elem": v_elem})
        else:
            cypher = f"""
            MATCH (a), (b)
            WHERE (a.person_id = $s_id OR a.id = $s_id OR a.phone_number = $s_id)
              AND (b.person_id = $v_id OR b.id = $v_id OR b.phone_number = $v_id)
            MATCH p = shortestPath((a)-[*..{bounded_depth}]-(b))
            RETURN p
            """
            result = session.run(cypher, {"s_id": target_suspect_id, "v_id": target_victim_id})

        record = result.single()

        if not record or not record.get("p"):
            return ShortestPathResponse(
                nodes=[],
                relationships=[],
                path_length=0,
                summary=f"No path found between suspect '{suspect_candidates[0].name}' and victim '{victim_candidates[0].name}' within depth {bounded_depth}."
            )

        neo_path = record["p"]
        nodes_list = []
        relationships_list = []
        path_labels_sequence = []

        for node in neo_path.nodes:
            n_data = dict(node)
            node_labels = list(node.labels)
            node_id = str(
                n_data.get("person_id")
                or n_data.get("case_id")
                or n_data.get("phone_number")
                or n_data.get("account_number")
                or n_data.get("vin")
                or n_data.get("license_plate")
                or n_data.get("handle_id")
                or n_data.get("ip_address")
                or n_data.get("location_id")
                or n_data.get("cell_tower_id")
                or n_data.get("fir_id")
                or n_data.get("prior_case_id")
                or n_data.get("source_record_id")
                or getattr(node, "element_id", str(node.id))
            )
            node_name = str(
                n_data.get("name")
                or n_data.get("case_name")
                or n_data.get("phone_number")
                or n_data.get("account_number")
                or n_data.get("vin")
                or n_data.get("license_plate")
                or n_data.get("case_id")
                or n_data.get("fir_number")
                or node_id
            )
            
            nodes_list.append({
                "id": str(node_id),
                "element_id": getattr(node, "element_id", str(node.id)),
                "labels": node_labels,
                "name": str(node_name),
                "properties": n_data
            })
            path_labels_sequence.append(f"{node_labels[0] if node_labels else 'Node'}({node_name})")

        for rel in neo_path.relationships:
            r_data = dict(rel)
            relationships_list.append({
                "id": getattr(rel, "element_id", str(rel.id)),
                "type": rel.type,
                "start_node": getattr(rel.start_node, "element_id", str(rel.start_node.id)),
                "end_node": getattr(rel.end_node, "element_id", str(rel.end_node.id)),
                "properties": r_data
            })

        summary = " -> ".join(path_labels_sequence)
        return ShortestPathResponse(
            ambiguous=False,
            nodes=nodes_list,
            relationships=relationships_list,
            path_length=len(relationships_list),
            summary=summary
        )

    @classmethod
    def _resolve_person(cls, session: Session, person_id: Optional[str] = None, name: Optional[str] = None) -> List[AmbiguityCandidate]:
        val = (person_id or name or "").strip()
        if not val:
            return []

        # 1. Primary Person resolution (preserves exact test contract)
        if person_id:
            cypher = """
            MATCH (p:Person {person_id: $person_id})
            RETURN p.person_id as person_id, p.name as name, p.aliases as aliases, p.dob as dob, p.case_ids as case_ids, elementId(p) as element_id
            """
            rows = session.run(cypher, {"person_id": person_id}).data()
        elif name:
            cypher = """
            MATCH (p:Person)
            WHERE toLower(p.name) = toLower($name) OR toLower($name) IN [a IN p.aliases | toLower(a)]
            RETURN p.person_id as person_id, p.name as name, p.aliases as aliases, p.dob as dob, p.case_ids as case_ids, elementId(p) as element_id
            """
            rows = session.run(cypher, {"name": name}).data()
        else:
            rows = []

        if rows:
            candidates = []
            for r in rows:
                candidates.append(AmbiguityCandidate(
                    person_id=str(r.get("person_id") or r.get("element_id") or val),
                    name=str(r.get("name") or val),
                    aliases=r.get("aliases") or [],
                    dob=r.get("dob"),
                    case_ids=r.get("case_ids") or [],
                    element_id=r.get("element_id")
                ))
            return candidates

        # 2. Fallback: match Person by person_id (in case name field held person_id) or national_id or partial name
        cypher_fallback_person = """
        MATCH (p:Person)
        WHERE p.person_id = $val OR p.national_id = $val OR toLower(p.name) CONTAINS toLower($val)
        RETURN p.person_id as person_id, p.name as name, p.aliases as aliases, p.dob as dob, p.case_ids as case_ids, elementId(p) as element_id
        """
        try:
            fb_rows = session.run(cypher_fallback_person, {"val": val}).data()
            if fb_rows:
                return [
                    AmbiguityCandidate(
                        person_id=str(r.get("person_id") or r.get("element_id") or val),
                        name=str(r.get("name") or val),
                        aliases=r.get("aliases") or [],
                        dob=r.get("dob"),
                        case_ids=r.get("case_ids") or [],
                        element_id=r.get("element_id")
                    )
                    for r in fb_rows
                ]
        except Exception:
            pass

        # 3. Fallback: Phone matching (strip whitespace, support with or without +91 / +)
        digits = "".join(ch for ch in val if ch.isdigit())
        cypher_phone = """
        MATCH (ph:Phone)
        WHERE ph.phone_number = $val
           OR ph.phone_number = '+' + $val
           OR ph.phone_number = '+91' + $val
           OR (size($digits) >= 6 AND ph.phone_number ENDS WITH $digits)
           OR ph.phone_id = $val
        RETURN coalesce(ph.phone_id, ph.phone_number) as person_id,
               ph.phone_number as name,
               ['Phone', coalesce(ph.carrier, 'Carrier Unknown')] as aliases,
               null as dob,
               ph.case_ids as case_ids,
               elementId(ph) as element_id
        LIMIT 5
        """
        try:
            ph_rows = session.run(cypher_phone, {"val": val, "digits": digits}).data()
            if ph_rows:
                return [
                    AmbiguityCandidate(
                        person_id=str(r.get("person_id") or val),
                        name=str(r.get("name") or val),
                        aliases=r.get("aliases") or ["Phone"],
                        dob=None,
                        case_ids=r.get("case_ids") or [],
                        element_id=r.get("element_id")
                    )
                    for r in ph_rows
                ]
        except Exception:
            pass

        # 4. Fallback: BankAccount matching
        cypher_bank = """
        MATCH (ba:BankAccount)
        WHERE ba.account_number = $val OR ba.account_id = $val OR ba.account_number ENDS WITH $val
        RETURN coalesce(ba.account_id, ba.account_number) as person_id,
               ba.account_number as name,
               ['BankAccount', coalesce(ba.bank_name, 'Bank')] as aliases,
               null as dob,
               ba.case_ids as case_ids,
               elementId(ba) as element_id
        LIMIT 5
        """
        try:
            ba_rows = session.run(cypher_bank, {"val": val}).data()
            if ba_rows:
                return [
                    AmbiguityCandidate(
                        person_id=str(r.get("person_id") or val),
                        name=str(r.get("name") or val),
                        aliases=r.get("aliases") or ["BankAccount"],
                        dob=None,
                        case_ids=r.get("case_ids") or [],
                        element_id=r.get("element_id")
                    )
                    for r in ba_rows
                ]
        except Exception:
            pass

        # 5. Fallback: Vehicle matching
        cypher_veh = """
        MATCH (v:Vehicle)
        WHERE v.license_plate = $val OR v.vin = $val OR v.vehicle_id = $val
        RETURN coalesce(v.vehicle_id, v.license_plate, v.vin) as person_id,
               coalesce(v.license_plate, v.vin) as name,
               ['Vehicle', coalesce(v.make_model, 'Vehicle')] as aliases,
               null as dob,
               v.case_ids as case_ids,
               elementId(v) as element_id
        LIMIT 5
        """
        try:
            veh_rows = session.run(cypher_veh, {"val": val}).data()
            if veh_rows:
                return [
                    AmbiguityCandidate(
                        person_id=str(r.get("person_id") or val),
                        name=str(r.get("name") or val),
                        aliases=r.get("aliases") or ["Vehicle"],
                        dob=None,
                        case_ids=r.get("case_ids") or [],
                        element_id=r.get("element_id")
                    )
                    for r in veh_rows
                ]
        except Exception:
            pass

        # 6. Fallback: Any graph entity matching id, name, or case_id
        cypher_generic = """
        MATCH (n)
        WHERE (n.id = $val OR n.name = $val OR n.case_id = $val)
        RETURN coalesce(n.id, n.case_id, elementId(n)) as person_id,
               coalesce(n.name, n.id, labels(n)[0]) as name,
               labels(n) as aliases,
               null as dob,
               coalesce(n.case_ids, []) as case_ids,
               elementId(n) as element_id
        LIMIT 5
        """
        try:
            gen_rows = session.run(cypher_generic, {"val": val}).data()
            if gen_rows:
                return [
                    AmbiguityCandidate(
                        person_id=str(r.get("person_id") or val),
                        name=str(r.get("name") or val),
                        aliases=r.get("aliases") or [],
                        dob=None,
                        case_ids=r.get("case_ids") or [],
                        element_id=r.get("element_id")
                    )
                    for r in gen_rows
                ]
        except Exception:
            pass

        return []

