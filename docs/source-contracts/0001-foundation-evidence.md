# Foundation evidence contract v1

Status: Envelope and storage deployed privately; source acceptance and intake pending

## Authority and grain

The first stored grain is one source observation, not an order, a status or a
business event. Its durable V2 UUID is separate from its original source identity.
Replay identity is `(source_system, source_dataset, source_observation_id)`.
A source adapter must define how it obtains a stable observation ID before intake
is enabled. Arrival time or a newly generated UUID cannot stand in for that ID.

Sculptor/Profit+ remains ERP authority, CSS remains the operational/calculation
authority during migration, and OGL remains historical/reconciliation evidence.
An envelope's `authority_state` is a claim that intake must check against the
accepted source contract; it does not grant authority by itself.

## Envelope and immutable storage

`packages/contracts/observation.py` requires the version, original business key,
reader version, timezone-aware observation time, explicit coverage, freshness
and authority, payload and SHA256 hash. `occurred_at` is optional; it must remain
null when not known. The database adds `recorded_at`, which is never used as
source freshness or event time.

Hash law: SHA256 of UTF-8 JSON with recursively sorted object keys, no ASCII
escaping, separators `,` and `:`, and no NaN/Infinity. This is a Python JSON
contract, not RFC 8785. Do not introduce another-language producer without
cross-language canonicalization fixtures. Null and zero differ. Quantity and
money must use explicitly contracted units/currencies; decimal strings are
preferred over binary floating point for future monetary payloads.

The Python validator checks the hash. PostgreSQL checks the hash format, states,
JSON-object payload and identity uniqueness. It does not compute or attest that
hash. An accepted future intake service must validate before insertion.

UPDATE, DELETE and TRUNCATE of observations are rejected by triggers. The runtime
API has no evidence privileges. A future ingestion identity will receive only
the required insertion access after collector ownership is agreed.

## Replay, projection and absence

An identical replay is a no-op only after comparing all retained envelope facts.
Reusing an observation ID with different bytes, reader version, timestamps or
states must fail and retain conflict evidence; never silently use
`ON CONFLICT DO NOTHING` for an unverified replay. No intake implementation is
shipped in this foundation.

Translation belongs to the next accepted domain contract. No business events,
order statuses, quantities or monetary aggregates are inferred here. Projections
will retain the input observation IDs, watermark, translator version and
calculation time. They must be rebuildable from this evidence.

Captured freshness is historical evidence. Read projections must evaluate
freshness at read/calculation time using their source-specific policy. There is
no universal TTL. COMPLETE means only the coverage specified by a source
contract. PARTIAL, UNKNOWN, missing and stale inputs never become zero. Absence
cannot delete or archive an entity without an accepted source absence contract.

## Reconciliation and rollback

Each intake release must include a manifest with source watermark, counts,
hashes, reader/translator versions, times and reconciliation results. Checkpoints
advance only with committed observations and required projections. Historical
and incremental imports use the same translators at a contiguous watermark.

Foundation rollback stops V2 services and retains its new database. V1 continues
unchanged. Database migrations move forward; do not remove evidence or rewrite
applied SQL to roll back.
