# Incremental Events API — `POST /api/events/batch`

Applies a batch of incremental records to an **existing** case with exactly the MERGE semantics of bulk
ingestion, then runs only the insight detectors whose dependencies were touched (scoped, global scope).

```
API -> EventBatch -> DeltaProcessor -> graph_writes (single source of write Cypher)
    -> one write transaction -> touched-entity tracking -> scoped detector dispatcher
    -> ScopedInsightsEngine -> EventProcessingResult
```

| | |
|---|---|
| Method / path | `POST /api/events/batch` |
| Tag (OpenAPI) | `Incremental Events` |
| Request body | `EventBatch` (`backend/models/event.py`) |
| Response body | `EventProcessingResult` |
| Success codes | `201 Created` — at least one primary node created and nothing matched; `200 OK` otherwise (same rule as `/api/cases/ingest`) |
| Max batch size | **5000 events** (`min 1`) |

## Request schema (`EventBatch`)

```json
{
  "case_id": "CASE-2024-001",          // required; the Case node MUST already exist
  "batch_id": "optional-client-id",    // echoed back
  "events": [                          // 1..5000, applied in bulk-ingest step order regardless of list order
    { "event_type": "PERSON_UPSERT", "payload": { ...Person... }, "event_id": "optional", "occurred_at": "optional ISO" }
  ]
}
```
`event_type` is the discriminator of a closed tagged union. Envelope and batch use `extra="forbid"`.
Payloads are the **same Pydantic models bulk ingestion uses** (`backend/models/entity.py`, `backend/models/relationship.py`).


### Supported event types (15)

| `event_type` | payload model | graph writes (via `graph_writes`) |
|---|---|---|
| `PERSON_UPSERT` | `Person` | Person + Case INVOLVES |
| `PHONE_UPSERT` | `Phone` | Phone + INVOLVES (+ OWNS if `owner_person_id`) |
| `BANK_ACCOUNT_UPSERT` | `BankAccount` | BankAccount + INVOLVES (+ OWNS) |
| `VEHICLE_UPSERT` | `Vehicle` | Vehicle + INVOLVES (+ OWNS) |
| `SOCIAL_HANDLE_UPSERT` | `SocialHandle` | SocialHandle + INVOLVES (+ HAS_HANDLE) |
| `IP_ADDRESS_UPSERT` | `IPAddress` | IPAddress + INVOLVES **only** (no `LINKED_TO_IP`) |
| `LOCATION_UPSERT` | `Location` | Location + INVOLVES |
| `CELL_TOWER_UPSERT` | `CellTower` | CellTower + INVOLVES (+ LOCATED_AT to its location) |
| `SOURCE_RECORD_UPSERT` | `SourceRecord` | SourceRecord + INVOLVES |
| `FIR_UPSERT` | `FIR` | FIR + HAS_FIR + INVOLVES; FIR→accused INVOLVES after People |
| `COMMUNICATION` | `CommunicationRecord` | `(Phone)-[:CALLED]->(Phone)` (implicit Phones ON CREATE only) |
| `TRANSACTION` | `TransactionRecord` | `TRANSFERRED_TO` + Transaction node (+ INVOLVES) |
| `SURVEILLANCE_LOG` | `SurveillanceLogRecord` | Location (ON CREATE) + Person/Vehicle `LOCATED_AT` |
| `CRIMINAL_HISTORY` | `CriminalHistoryRecord` | PriorCase + `HAS_PRIOR_CASE` + INVOLVES |
| `INTELLIGENCE_REPORT` | `IntelligenceReportRecord` | SourceRecord(`INTELLIGENCE_REPORT`) + INVOLVES |

### Unsupported (rejected with 422, never partially applied)

* Any other `event_type` — in particular **DELETE / RETRACT / CORRECTION / REPLACE** and any **IP-link** event
  (`LINKED_TO_IP` is read-only in this schema; nothing writes it).
* Unknown keys on the envelope or batch (e.g. `"operation": "delete"`, `"mode": "replace"`).
* Case creation: a batch for a non-existent case is rejected with **404**; create the case with `POST /api/cases/ingest`.
* Fields accepted by the models but not persisted by the current schema — `SurveillanceLogRecord.observed_phone_numbers`,
  `IntelligenceReportRecord.entities_mentioned` — are ignored **and reported in `warnings`**.

## Response schema (`EventProcessingResult`)

| field | meaning |
|---|---|
| `case_id`, `batch_id`, `event_ids[]`, `events_by_type{}` | echo / bookkeeping |
| `writes.nodes_created` / `nodes_matched` | primary nodes created vs. matched (or not written because a MATCH target was missing), per input record |
| `writes.relationships_written` | relationship writes counted per input record (bulk-ingest convention) |
| `writes.statements_executed` | Cypher statements in the batch transaction (detectors excluded) |
| `touched` | `persons`, `phones`, `bank_accounts`, `vehicles`, `social_handles`, `ip_addresses`, `locations`, `cell_towers`, `prior_cases`, `relationship_kinds`, `case_ids_changed` (`"<Label>:<key>"` of nodes that gained this case) |
| `detectors_run[]` | every detector the dispatcher selected: `{detector, insight_type, status: ok\|failed, insights, error}` |
| `detectors_failed[]` | names of detectors that raised |
| `detectors_skipped[]` | detectors not selected (no dependency touched) |
| `insights[]` | `InsightItem`s produced by the scoped detectors (same shape/ids as the full engine) |
| `warnings[]`, `processed_at` | |

## Error behaviour

| status | when | body |
|---|---|---|
| 422 | schema violation (unknown type/field, missing required payload field, empty or >5000 batch) | `{"error":"UnprocessableEntityError","message":…,"detail":[pydantic errors]}` — nothing touches the database |
| 404 | case does not exist | `{"error":"HTTPException","message":"Case '…' does not exist; …"}` — nothing written |
| 409 | `ValueError` from the service layer | as above |
| 500 | Cypher/transaction error inside the batch | message contains `rolled back`; **no write of the batch persists** |
| 503 | Neo4j unreachable | |

## Idempotency

Replaying an identical batch re-applies the same MERGE statements as bulk ingestion: `nodes_created = 0`,
`nodes_matched = N`, graph unchanged, `case_ids_changed = []`. Node `case_ids` lists gain a case at most once;
Person `aliases`/`roles` are de-duplicated. Relationship endpoints created implicitly by CALLED/TRANSFERRED_TO
writers do **not** gain `case_ids` on match (pre-existing bulk semantics, deliberately preserved).

## Detector failure behaviour

A detector exception never fails the request and is never swallowed: the batch's writes stay committed, the
failing detector appears in `detectors_run` with `status="failed"` and the error text, and in `detectors_failed`;
the remaining selected detectors still run. Clients must treat `detectors_failed != []` as "insights incomplete",
not as "no insights".

## Scope of the scoped detectors

Detectors run with `case_id=None` (global scope) anchored on the touched identities, so cross-case patterns are
found from either endpoint of a new relationship, from an owner side effect, or from a node that just joined a
case. Semantics, thresholds and `LIMIT`s are those of the full `InsightsEngine` (reference implementation);
equivalence is verified by `tests/test_equivalence_harness.py`.
