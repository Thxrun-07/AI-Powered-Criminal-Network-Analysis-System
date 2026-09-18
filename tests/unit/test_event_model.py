"""
Phase 2 / A -- app/models/event.py

Validation contract of the incremental event model:
* every supported type validates with the SAME payload models the bulk path uses;
* unsupported types (delete / retract / correction / IP-link / typos) FAIL validation;
* envelope and batch are strict (extra keys rejected, empty batch rejected);
* TouchedEntities helpers.
"""
import json
import os

import pytest
from pydantic import ValidationError

from backend.models.case_input import CaseData
from backend.models.event import (
    EVENT_PAYLOAD_MODELS, EntityKind, EventBatch, EventProcessingResult, EventType, TouchedEntities,
)

SAMPLE = os.path.join("dataset", "case_001_homicide.json")


def _doc():
    with open(SAMPLE, "r", encoding="utf-8") as f:
        return json.load(f)


def test_event_types_cover_exactly_the_persisted_record_kinds():
    assert {e.value for e in EventType} == {
        "PERSON_UPSERT", "PHONE_UPSERT", "BANK_ACCOUNT_UPSERT", "VEHICLE_UPSERT", "SOCIAL_HANDLE_UPSERT",
        "IP_ADDRESS_UPSERT", "LOCATION_UPSERT", "CELL_TOWER_UPSERT", "SOURCE_RECORD_UPSERT", "FIR_UPSERT",
        "COMMUNICATION", "TRANSACTION", "SURVEILLANCE_LOG", "CRIMINAL_HISTORY", "INTELLIGENCE_REPORT",
    }
    assert set(EVENT_PAYLOAD_MODELS) == set(EventType)
    # No IP-link / delete / retract / correction event type exists.
    for forbidden in ("IP_LINK", "LINKED_TO_IP", "DELETE", "RETRACT", "CORRECTION", "REPLACE"):
        assert not any(forbidden in e.value for e in EventType)


def test_payload_models_are_the_bulk_ingestion_models():
    """Events must reuse the CaseData element models, not redefine them."""
    from backend.models.case_input import EntitiesContainer, RelationshipsContainer
    fields = {**EntitiesContainer.model_fields, **RelationshipsContainer.model_fields, **CaseData.model_fields}
    def elem(name):
        return fields[name].annotation.__args__[0]
    assert EVENT_PAYLOAD_MODELS[EventType.PERSON_UPSERT] is elem("people")
    assert EVENT_PAYLOAD_MODELS[EventType.PHONE_UPSERT] is elem("phones")
    assert EVENT_PAYLOAD_MODELS[EventType.BANK_ACCOUNT_UPSERT] is elem("bank_accounts")
    assert EVENT_PAYLOAD_MODELS[EventType.VEHICLE_UPSERT] is elem("vehicles")
    assert EVENT_PAYLOAD_MODELS[EventType.SOCIAL_HANDLE_UPSERT] is elem("social_handles")
    assert EVENT_PAYLOAD_MODELS[EventType.IP_ADDRESS_UPSERT] is elem("ip_addresses")
    assert EVENT_PAYLOAD_MODELS[EventType.LOCATION_UPSERT] is elem("locations")
    assert EVENT_PAYLOAD_MODELS[EventType.CELL_TOWER_UPSERT] is elem("cell_towers")
    assert EVENT_PAYLOAD_MODELS[EventType.SOURCE_RECORD_UPSERT] is elem("source_records")
    assert EVENT_PAYLOAD_MODELS[EventType.FIR_UPSERT] is elem("fir_records")
    assert EVENT_PAYLOAD_MODELS[EventType.COMMUNICATION] is elem("communications")
    assert EVENT_PAYLOAD_MODELS[EventType.TRANSACTION] is elem("transactions")
    assert EVENT_PAYLOAD_MODELS[EventType.SURVEILLANCE_LOG] is elem("surveillance_logs")
    assert EVENT_PAYLOAD_MODELS[EventType.CRIMINAL_HISTORY] is elem("criminal_history")
    assert EVENT_PAYLOAD_MODELS[EventType.INTELLIGENCE_REPORT] is elem("intelligence_reports")


def test_every_sample_record_validates_as_an_event():
    d = _doc()
    mapping = [
        ("FIR_UPSERT", d["fir_records"]), ("PERSON_UPSERT", d["entities"]["people"]),
        ("PHONE_UPSERT", d["entities"]["phones"]), ("BANK_ACCOUNT_UPSERT", d["entities"]["bank_accounts"]),
        ("VEHICLE_UPSERT", d["entities"]["vehicles"]), ("SOCIAL_HANDLE_UPSERT", d["entities"]["social_handles"]),
        ("IP_ADDRESS_UPSERT", d["entities"]["ip_addresses"]), ("LOCATION_UPSERT", d["entities"]["locations"]),
        ("CELL_TOWER_UPSERT", d["entities"]["cell_towers"]), ("COMMUNICATION", d["relationships"]["communications"]),
        ("TRANSACTION", d["relationships"]["transactions"]), ("SURVEILLANCE_LOG", d["surveillance_logs"]),
        ("CRIMINAL_HISTORY", d["criminal_history"]), ("INTELLIGENCE_REPORT", d["intelligence_reports"]),
    ]
    events = [{"event_type": t, "payload": p, "event_id": f"{t}-{i}"} for t, items in mapping for i, p in enumerate(items)]
    batch = EventBatch(case_id="CASE-2024-001", events=events)
    assert len(batch.events) == 23
    # payload is parsed into the very same model instance type CaseData would produce
    cd = CaseData(**d)
    person_ev = next(e for e in batch.events if e.event_type == EventType.PERSON_UPSERT)
    assert type(person_ev.payload) is type(cd.entities.people[0])
    # identical content (AuditFields timestamps are generated per parse, so exclude them)
    audit = {"created_at", "updated_at"}
    assert person_ev.payload.model_dump(exclude=audit) == cd.entities.people[0].model_dump(exclude=audit)
    # round-trips through JSON with the discriminator as a plain string
    dumped = batch.model_dump(mode="json")
    assert dumped["events"][0]["event_type"] == "FIR_UPSERT"
    assert EventBatch(**dumped) == batch


@pytest.mark.parametrize("bad_type", ["DELETE", "RETRACT", "CORRECTION", "IP_LINK", "LINKED_TO_IP", "PERSON_DELETE", "person_upsert", ""])
def test_unsupported_event_types_fail_validation(bad_type):
    with pytest.raises(ValidationError) as exc:
        EventBatch(case_id="C", events=[{"event_type": bad_type, "payload": {"person_id": "P1", "name": "X"}}])
    assert exc.value.errors()[0]["type"] in ("union_tag_invalid", "union_tag_not_found")


def test_payload_validated_against_the_typed_model():
    # Person requires name
    with pytest.raises(ValidationError):
        EventBatch(case_id="C", events=[{"event_type": "PERSON_UPSERT", "payload": {"person_id": "P1"}}])
    # Transaction requires target_account
    with pytest.raises(ValidationError):
        EventBatch(case_id="C", events=[{"event_type": "TRANSACTION", "payload": {"transaction_id": "T", "source_account": "A"}}])
    # Wrong payload shape for the declared type
    with pytest.raises(ValidationError):
        EventBatch(case_id="C", events=[{"event_type": "COMMUNICATION", "payload": {"person_id": "P1", "name": "X"}}])


def test_envelope_and_batch_are_strict():
    ok = {"event_type": "PERSON_UPSERT", "payload": {"person_id": "P1", "name": "X"}}
    with pytest.raises(ValidationError):  # unknown envelope key (e.g. an 'operation': 'delete' smuggled in)
        EventBatch(case_id="C", events=[{**ok, "operation": "delete"}])
    with pytest.raises(ValidationError):  # missing event_type
        EventBatch(case_id="C", events=[{"payload": {"person_id": "P1", "name": "X"}}])
    with pytest.raises(ValidationError):  # empty batch
        EventBatch(case_id="C", events=[])
    with pytest.raises(ValidationError):  # missing case_id
        EventBatch(events=[ok])
    with pytest.raises(ValidationError):  # unknown batch key
        EventBatch(case_id="C", events=[ok], mode="replace")
    b = EventBatch(case_id="C", events=[ok], batch_id="B-1")
    assert b.events[0].event_id is None and b.events[0].occurred_at is None and b.batch_id == "B-1"


def test_touched_entities_helpers():
    t = TouchedEntities()
    assert t.is_empty() and t.kinds() == set()
    t.phones.add("+1"); t.relationship_kinds.add(EntityKind.CALLED)
    assert not t.is_empty()
    assert t.node_kinds() == {EntityKind.PHONE}
    assert t.kinds() == {EntityKind.PHONE, EntityKind.CALLED}
    # EntityKind values name the graph labels / relationship types they stand for
    assert EntityKind.BANK_ACCOUNT.value == "BankAccount" and EntityKind.TRANSFERRED_TO.value == "TRANSFERRED_TO"
    assert "LINKED_TO_IP" not in {k.value for k in EntityKind}


def test_result_model_defaults_and_serialization():
    r = EventProcessingResult(case_id="C")
    assert r.detectors_run == [] and r.detectors_failed == [] and r.insights == [] and r.warnings == []
    assert r.writes.statements_executed == 0
    j = r.model_dump(mode="json")
    assert j["touched"]["persons"] == [] and isinstance(j["processed_at"], str)
