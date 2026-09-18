"""
Phase 2 / stage 4 -- POST /api/events/batch (API-level, mock session).

Covers the required cases:
  A valid single event                 B valid multi-event batch        C batch at the supported maximum
  D invalid discriminator              E DELETE / RETRACT / CORRECTION   F IP_LINK
  G unknown event fields rejected      H nonexistent case rejected       I idempotent replay
  J mixed event types in one batch     K detector failure is visible     L rollback on mid-batch failure
  M default dispatcher is actually used N explicit detector opt-out still works
plus router wiring / OpenAPI discoverability and error mapping.

Live counterparts: tests/test_live_neo4j_events_api.py.
"""
import json
import os
import sys
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from neo4j.exceptions import ClientError, ServiceUnavailable

from tests.conftest import MockRecord, MockResult  # noqa: E402
from tests.unit.test_delta_processor import EventMockSession, events_from_case_doc  # noqa: E402

from backend.database import db  # noqa: E402
from backend.main import app  # noqa: E402
from backend.models.event import EventBatch, EventType  # noqa: E402
from backend.routers import events as events_router_module  # noqa: E402
from backend.services import graph_writes as gw  # noqa: E402
from backend.services.delta_processor import DeltaProcessor, _no_detectors  # noqa: E402

URL = "/api/events/batch"
SAMPLE_001 = os.path.join("dataset", "case_001_homicide.json")
EDGE = os.path.join(os.path.dirname(__file__), "..", "fixtures", "case_edge_batching.json")


def _doc(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _person(pid="P-1", name="X", **extra):
    return {"event_type": "PERSON_UPSERT", "payload": {"person_id": pid, "name": name, **extra}}


@contextmanager
def _client(make_session):
    """TestClient with db.get_session() patched to ``make_session()``. The app lifespan calls get_session()
    once at startup (schema init); that session is dropped from ``sessions`` so tests only see request sessions."""
    sessions = []

    def factory(*_a, **_k):
        s = make_session()
        sessions.append(s)
        return s

    with patch.object(db, "get_session", side_effect=factory):
        with TestClient(app) as client:
            sessions.clear()  # discard the lifespan/startup session
            yield client, sessions


@pytest.fixture
def api():
    """TestClient whose db.get_session() yields a fresh EventMockSession per request; request sessions are collected."""
    with _client(EventMockSession) as (client, sessions):
        yield client, sessions


# ---------------------------------------------------------------------------
# wiring / discoverability
# ---------------------------------------------------------------------------

def test_router_is_wired_once_and_existing_routes_unchanged():
    paths = sorted(app.openapi()["paths"])
    assert "/api/events/batch" in paths
    assert paths.count("/api/events/batch") == 1
    for existing in ("/api/cases/ingest", "/api/cases/{case_id}/insights", "/api/insights/delta", "/api/v1/ingest", "/api/health"):
        assert existing in paths
    post = app.openapi()["paths"]["/api/events/batch"]["post"]
    assert post["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith("/EventBatch")
    assert post["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("/EventProcessingResult")
    mapping = app.openapi()["components"]["schemas"]["EventBatch"]["properties"]["events"]["items"]["discriminator"]["mapping"]
    assert set(mapping) == {e.value for e in EventType} and len(mapping) == 15
    assert not any(k in mapping for k in ("IP_LINK", "LINKED_TO_IP", "DELETE", "RETRACT", "CORRECTION"))


def test_router_uses_delta_processor_with_default_scoped_runner():
    proc = events_router_module._processor
    assert isinstance(proc, DeltaProcessor)
    assert proc._detector_runner.__name__ == "_default_scoped_runner"


# ---------------------------------------------------------------------------
# A / B / C -- valid batches
# ---------------------------------------------------------------------------

def test_a_valid_single_event(api):
    client, sessions = api
    r = client.post(URL, json={"case_id": "CASE-1", "events": [_person()], "batch_id": "B-A"})
    assert r.status_code == 201
    j = r.json()
    assert j["case_id"] == "CASE-1" and j["batch_id"] == "B-A" and j["event_ids"] == [None]
    assert j["events_by_type"] == {"PERSON_UPSERT": 1}
    assert j["writes"] == {"nodes_created": 1, "nodes_matched": 0, "relationships_written": 1, "statements_executed": 1}
    assert j["touched"]["persons"] == ["P-1"] and j["touched"]["case_ids_changed"] == []
    assert {d["insight_type"] for d in j["detectors_run"]} == {"SHARED_ENTITY", "BRIDGE_NODE", "POSSIBLE_CO_LOCATION", "CROSS_DOMAIN_PATH", "PRIOR_CASE_LINK"}
    assert j["detectors_failed"] == [] and j["insights"] == []
    assert set(j["detectors_skipped"]) == {"CROSS_CASE_LINK", "TRANSFER_CHAIN", "HIGH_FAN_IN", "HIGH_FAN_OUT", "INFRASTRUCTURE_REUSE"}
    assert "processed_at" in j and j["warnings"] == []
    assert sessions[-1].write_transactions == 1


def test_b_valid_multi_event_batch(api):
    client, sessions = api
    evs = [_person("P-1", "One"), _person("P-2", "Two"),
           {"event_type": "PHONE_UPSERT", "payload": {"phone_number": "+1", "owner_person_id": "P-1"}},
           {"event_type": "COMMUNICATION", "payload": {"source_phone": "+1", "target_phone": "+2", "timestamp": "T"}, "event_id": "E-3"}]
    r = client.post(URL, json={"case_id": "CASE-1", "events": evs})
    assert r.status_code == 201
    j = r.json()
    assert j["event_ids"] == [None, None, None, "E-3"]
    assert j["events_by_type"] == {"PERSON_UPSERT": 2, "PHONE_UPSERT": 1, "COMMUNICATION": 1}
    assert j["writes"]["statements_executed"] == 4  # PEOPLE, PHONES, PHONE_OWNS, CALLED
    assert sorted(j["touched"]["phones"]) == ["+1", "+2"] and sorted(j["touched"]["persons"]) == ["P-1", "P-2"]
    assert set(j["touched"]["relationship_kinds"]) == {"OWNS", "CALLED"}
    assert sessions[-1].write_transactions == 1


def test_c_batch_at_supported_maximum_and_one_over(api):
    client, _ = api
    maximum = EventBatch.model_fields["events"].metadata[1].max_length  # 5000
    evs = [_person(f"P-{i}", f"N{i}") for i in range(maximum)]
    r = client.post(URL, json={"case_id": "CASE-1", "events": evs})
    assert r.status_code == 201
    assert r.json()["events_by_type"] == {"PERSON_UPSERT": maximum}
    assert r.json()["writes"]["nodes_created"] == maximum and r.json()["writes"]["statements_executed"] == 1
    r = client.post(URL, json={"case_id": "CASE-1", "events": evs + [_person("P-over", "over")]})
    assert r.status_code == 422 and r.json()["detail"][0]["type"] == "too_long"


# ---------------------------------------------------------------------------
# D / E / F / G -- validation failures (422 through the app-wide handler)
# ---------------------------------------------------------------------------

def test_d_invalid_discriminator(api):
    client, sessions = api
    for bad in ("PERSON", "person_upsert", "Phone", "", "PERSON_UPSERT "):
        r = client.post(URL, json={"case_id": "C", "events": [{"event_type": bad, "payload": {"person_id": "P", "name": "N"}}]})
        assert r.status_code == 422, bad
        assert r.json()["error"] == "UnprocessableEntityError"
        assert r.json()["detail"][0]["type"] == "union_tag_invalid"
    r = client.post(URL, json={"case_id": "C", "events": [{"payload": {"person_id": "P", "name": "N"}}]})
    assert r.status_code == 422 and r.json()["detail"][0]["type"] == "union_tag_not_found"
    assert sessions == []  # nothing reached the database


@pytest.mark.parametrize("op", ["DELETE", "RETRACT", "CORRECTION", "PERSON_DELETE", "REPLACE", "PHONE_RETRACT"])
def test_e_unsupported_delete_retract_correction(api, op):
    client, sessions = api
    r = client.post(URL, json={"case_id": "C", "events": [{"event_type": op, "payload": {"person_id": "P"}}]})
    assert r.status_code == 422 and r.json()["detail"][0]["type"] == "union_tag_invalid"
    # smuggling the operation into the envelope or the batch is rejected too
    r = client.post(URL, json={"case_id": "C", "events": [{**_person(), "operation": op.lower()}]})
    assert r.status_code == 422 and r.json()["detail"][0]["type"] == "extra_forbidden"
    r = client.post(URL, json={"case_id": "C", "mode": op.lower(), "events": [_person()]})
    assert r.status_code == 422 and r.json()["detail"][0]["type"] == "extra_forbidden"
    assert sessions == []


@pytest.mark.parametrize("op", ["IP_LINK", "LINKED_TO_IP", "IP_LINK_UPSERT", "LINK_IP"])
def test_f_unsupported_ip_link(api, op):
    client, sessions = api
    r = client.post(URL, json={"case_id": "C", "events": [{"event_type": op, "payload": {"ip_address": "1.1.1.1", "person_id": "P"}}]})
    assert r.status_code == 422 and r.json()["detail"][0]["type"] == "union_tag_invalid"
    assert sessions == []


def test_g_unknown_event_fields_rejected(api):
    client, sessions = api
    # unknown envelope key
    r = client.post(URL, json={"case_id": "C", "events": [{**_person(), "linked_ip": "1.1.1.1"}]})
    assert r.status_code == 422 and r.json()["detail"][0]["type"] == "extra_forbidden"
    # unknown batch key
    r = client.post(URL, json={"case_id": "C", "events": [_person()], "confirm_replace": True})
    assert r.status_code == 422 and r.json()["detail"][0]["type"] == "extra_forbidden"
    # payload validated against the typed model (missing required field / wrong shape)
    r = client.post(URL, json={"case_id": "C", "events": [{"event_type": "TRANSACTION", "payload": {"transaction_id": "T", "source_account": "A"}}]})
    assert r.status_code == 422 and {e["type"] for e in r.json()["detail"]} == {"missing"}
    # missing case_id / empty batch
    assert client.post(URL, json={"events": [_person()]}).status_code == 422
    assert client.post(URL, json={"case_id": "C", "events": []}).json()["detail"][0]["type"] == "too_short"
    assert sessions == []


# ---------------------------------------------------------------------------
# H -- nonexistent case
# ---------------------------------------------------------------------------

def test_h_nonexistent_case_rejected_with_404_and_no_writes():
    with _client(lambda: EventMockSession(case_exists=False)) as (client, sessions):
        r = client.post(URL, json={"case_id": "NOPE", "events": [_person()]})
    assert r.status_code == 404
    assert r.json()["error"] == "HTTPException" and "does not exist" in r.json()["message"]
    (s,) = sessions
    assert s.write_transactions == 0
    assert all(" ".join(q.split()) == " ".join(gw.CASE_EXISTS_QUERY.split()) for q, _ in s.queries)


# ---------------------------------------------------------------------------
# I / J -- idempotent replay, mixed types
# ---------------------------------------------------------------------------

def test_i_idempotent_replay_uses_same_statements_and_reports_matched():
    """First replay: all created (201). Second replay (mock reports pre-existing): all matched (200), same statements."""
    d = _doc(SAMPLE_001)
    evs = events_from_case_doc(d)

    class SecondRunSession(EventMockSession):
        """Everything already exists and already carries the case."""
        def run(self, query, parameters=None):
            q = " ".join(query.split())
            if q.startswith("UNWIND $rows AS row") and "AS was_created" in q:
                self.queries.append((query, parameters or {}))
                return MockResult([MockRecord({"was_created": False}) for _ in parameters["rows"]])
            if q.startswith("MERGE (f:FIR"):
                self.queries.append((query, parameters or {}))
                return MockResult([MockRecord({"was_created": False})])
            return super().run(query, parameters)

    # request 1 -> fresh EventMockSession (everything created); request 2 -> SecondRunSession (everything matched).
    # The lifespan/startup session is created before the first request, hence the leading entry.
    kinds = iter([EventMockSession, EventMockSession, SecondRunSession])
    with _client(lambda: next(kinds, SecondRunSession)()) as (client, runs):
        r1 = client.post(URL, json={"case_id": "CASE-2024-001", "events": evs})
        r2 = client.post(URL, json={"case_id": "CASE-2024-001", "events": evs})
    assert r1.status_code == 201 and r1.json()["writes"] == {"nodes_created": 20, "nodes_matched": 0, "relationships_written": 41, "statements_executed": 24}
    assert r2.status_code == 200 and r2.json()["writes"] == {"nodes_created": 0, "nodes_matched": 20, "relationships_written": 41, "statements_executed": 24}
    known = {" ".join(s.split()) for s in gw.ALL_WRITE_STATEMENTS.values()}
    w1 = [(" ".join(q.split()), {k: v for k, v in p.items() if k != "now"}) for q, p in runs[0].queries if " ".join(q.split()) in known]
    w2 = [(" ".join(q.split()), {k: v for k, v in p.items() if k != "now"}) for q, p in runs[1].queries if " ".join(q.split()) in known]
    assert w1 == w2 and len(w1) == 24


def test_j_mixed_event_types_in_one_batch_plan_order_and_counts(api):
    client, sessions = api
    d = _doc(EDGE)
    evs = list(reversed(events_from_case_doc(d)))  # deliberately scrambled order
    r = client.post(URL, json={"case_id": "CASE-EDGE-001", "events": evs})
    assert r.status_code == 201
    j = r.json()
    assert len(j["events_by_type"]) == 12 and sum(j["events_by_type"].values()) == len(evs)
    assert j["writes"] == {"nodes_created": 19, "nodes_matched": 0, "relationships_written": 44, "statements_executed": 19}
    # write order is the bulk-ingest order regardless of event order
    known = {" ".join(s.split()): n for n, s in gw.ALL_WRITE_STATEMENTS.items()}
    names = [known[" ".join(q.split())] for q, _ in sessions[-1].queries if " ".join(q.split()) in known]
    assert names.index("PEOPLE_MERGE") < names.index("FIR_ACCUSED_INVOLVES") < names.index("PHONE_OWNS")
    assert names.index("SURVEILLANCE_LOCATIONS_MERGE") < names.index("SURVEILLANCE_PERSON_LOCATED_AT") < names.index("PRIOR_CASES_MERGE") < names.index("INTEL_REPORTS_MERGE")
    assert sorted(j["touched"]["phones"]) == ["+91E1", "+91E2", "+91E3"] and sorted(j["touched"]["persons"]) == ["P-E1", "P-E2", "P-MISSING"]
    assert j["warnings"] == [] and j["detectors_skipped"] == []  # every kind touched -> every detector selected


# ---------------------------------------------------------------------------
# K -- detector failure visible; not a successful empty result
# ---------------------------------------------------------------------------

def test_k_detector_failure_is_visible_in_response():
    class FailingCoLocationSession(EventMockSession):
        def run(self, query, parameters=None):
            if "LOCATED_AT]->(loc:Location)<-[l2:LOCATED_AT]" in query and "CALL {" in query:
                self.queries.append((query, parameters or {}))
                raise ClientError("Neo.ClientError.Statement.ExecutionFailed", "simulated co-location failure")
            return super().run(query, parameters)

    with _client(FailingCoLocationSession) as (client, _sessions):
        r = client.post(URL, json={"case_id": "C", "events": [
            {"event_type": "SURVEILLANCE_LOG", "payload": {"log_id": "S1", "timestamp": "T", "location_id": "L1", "observed_person_ids": ["P-1"]}}]})
    # writes succeeded (200: a surveillance-only batch creates no *primary* node); the detector failure is
    # reported in the body, never turned into an HTTP error or a silent empty success
    assert r.status_code == 200
    j = r.json()
    assert "detect_possible_co_location_scoped" in j["detectors_failed"]
    failed = next(d for d in j["detectors_run"] if d["insight_type"] == "POSSIBLE_CO_LOCATION")
    assert failed["status"] == "failed" and failed["insights"] == 0 and "simulated co-location failure" in failed["error"]
    # other selected detectors still ran and report ok (Person touched -> shared/bridge/cross-domain/prior)
    ok = {d["insight_type"] for d in j["detectors_run"] if d["status"] == "ok"}
    assert {"SHARED_ENTITY", "BRIDGE_NODE", "CROSS_DOMAIN_PATH", "PRIOR_CASE_LINK"} <= ok
    assert j["insights"] == []  # empty AND flagged as failed -- never a silent empty success


# ---------------------------------------------------------------------------
# L -- rollback on mid-batch failure
# ---------------------------------------------------------------------------

def test_l_mid_batch_failure_rolls_back_and_maps_to_500():
    class TxSession(EventMockSession):
        """Simulates a managed transaction: raising inside the tx function propagates; nothing is committed."""
        committed = False

        def execute_write(self, fn, *args, **kwargs):
            self.write_transactions += 1
            try:
                out = fn(self, *args, **kwargs)
            except Exception:
                self.rolled_back = True
                raise
            self.committed = True
            return out

        def run(self, query, parameters=None):
            if " ".join(query.split()).startswith(" ".join(gw.TRANSACTIONS_MERGE.split())):
                self.queries.append((query, parameters or {}))
                raise ClientError("Neo.ClientError.Schema.ConstraintValidationFailed", "simulated failure in TRANSACTIONS_MERGE")
            return super().run(query, parameters)

    with _client(TxSession) as (client, holder):
        r = client.post(URL, json={"case_id": "C", "events": [
            _person("P-1"),
            {"event_type": "TRANSACTION", "payload": {"transaction_id": "T", "source_account": "A", "target_account": "B", "amount": 1.0, "timestamp": "T"}}]})
    assert r.status_code == 500
    assert "rolled back" in r.json()["message"] and "simulated failure in TRANSACTIONS_MERGE" in r.json()["message"]
    (s,) = holder
    assert s.write_transactions == 1 and getattr(s, "rolled_back", False) and not s.committed
    # no detector query was issued after the failed transaction
    assert not any("CALL {" in q for q, _ in s.queries)


def test_service_unavailable_maps_to_503():
    class DownSession(EventMockSession):
        def run(self, query, parameters=None):
            raise ServiceUnavailable("neo4j down")
    with _client(DownSession) as (client, _sessions):
        r = client.post(URL, json={"case_id": "C", "events": [_person()]})
    assert r.status_code == 503 and "unavailable" in r.json()["message"].lower()


# ---------------------------------------------------------------------------
# M / N -- default dispatcher used; explicit opt-out still possible at service level
# ---------------------------------------------------------------------------

def test_m_default_dispatcher_is_actually_used(api):
    client, sessions = api
    r = client.post(URL, json={"case_id": "C", "events": [
        {"event_type": "TRANSACTION", "payload": {"transaction_id": "T", "source_account": "A", "target_account": "B", "amount": 1.0, "timestamp": "T"}}]})
    j = r.json()
    # BankAccount (both endpoints) + TRANSFERRED_TO touched -> exactly the matrix selection, in engine order
    assert [d["insight_type"] for d in j["detectors_run"]] == ["SHARED_ENTITY", "BRIDGE_NODE", "TRANSFER_CHAIN", "HIGH_FAN_IN", "HIGH_FAN_OUT", "CROSS_DOMAIN_PATH"]
    assert all(d["detector"].endswith("_scoped") and d["status"] == "ok" for d in j["detectors_run"])
    assert set(j["detectors_skipped"]) == {"CROSS_CASE_LINK", "INFRASTRUCTURE_REUSE", "POSSIBLE_CO_LOCATION", "PRIOR_CASE_LINK"}
    assert "No scoped detector runner configured" not in " ".join(j["warnings"])
    # scoped Cypher was executed in GLOBAL scope with both endpoints anchored
    s = sessions[-1]
    scoped_calls = [(q, p) for q, p in s.queries if "$bank_accounts" in q]
    assert scoped_calls and all(p["bank_accounts"] == ["A", "B"] for _, p in scoped_calls)
    assert all(p.get("case_id") is None for _, p in scoped_calls if "case_id" in p)


def test_n_explicit_detector_opt_out_still_works_at_service_level():
    """The router always uses the default dispatcher; the opt-out remains available to callers of the service
    (e.g. bulk replays that will run the full engine afterwards) and is always visible via a warning."""
    from backend.models.event import EventBatch as EB
    s = EventMockSession()
    res = DeltaProcessor(detector_runner=_no_detectors).process_events(s, EB(case_id="C", events=[_person()]))
    assert res.detectors_run == [] and res.detectors_failed == [] and res.insights == []
    assert any("No scoped detector runner configured" in w for w in res.warnings)
    assert s.write_transactions == 1
