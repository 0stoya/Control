# Sales Order Timeline source contract v1

Status: Proposed; grounded in the completed CSS source checkpoint and focused
live metadata inventory on 2026-10-06. Adapter, business migrations, translators,
API and UI are not implemented or deployed by this contract.

Update: [Scoped key proof](../migration/0002-identity-proof-2026-10-06.md)
validates commercial-line/native key mapping and delivery key shape. Local
identity safeguards and synthetic regressions are implemented. Direct
delivery-note row parity and full historical coverage are still pending.

Contract identifier: `sales_order_timeline_v1`.

Use the [field/entity map and pinned source evidence](../migration/0001-sales-order-map.md)
with the deployed [foundation envelope contract](0001-foundation-evidence.md).
The mapping's source and runtime revisions are separate. Contract acceptance is
per lane and population; a source config flag does not alone attest freshness,
deployment or current operational authority.

## Authority and first population

Sculptor/Profit+ remains ERP authority, V1 CSS remains operational/calculation
authority, V2 owns newly accepted V2 workflow intent, and OGL is retained historical/
reconciliation evidence. Initial delivery is a read-only shadow capability.

Start with an explicitly manifested order population and the existing bounded
CSS captures. Record registered ERP instance/company, datasets, order scope,
snapshot boundary, line-keyset method, known gaps and continuation mechanism.
Do not create a competing direct Sculptor collector for this initial feed.
Until a population has complete coverage, a global count or daily total cannot
claim to cover all orders.

## Stable identities and export adapter

Resolve native header/line keys exactly as recorded in the entity map. Retain
CRM company and ordering-account identities separately. A line alias requires
proof; unresolved `itemno` / `uniqueno` joins are not approximate matches.
For the proved commercial-line scope, use order plus `uniqueno` as the logical
reference and retain native `(ordno, itemno)` per revision. Native item slots
are reused and renumbered; they cannot own a lifetime-unique canonical line ID.
Each accepted revision must have unambiguous logical aliases and exact ownership.

The adapter must register a stable V1 database identity epoch; a restore that
forks history or reuses sequences cannot silently inherit the same namespace.
Preserve the original ERP source instance and dataset. For example, a Sculptor
observation exported from V1 can use:

```text
source_system = sculptor:<registered-erp-instance>
source_dataset = <original contracted dataset>
source_observation_id = v1:<registered-database-epoch>:observation:<original-id>
```

Composite capture rows use the registered epoch, relation/lane, original capture
ID and the complete typed source-row key. Original reader/schema versions,
source instance, native keys, payload/raw-record hashes and source timestamps
remain in the retained envelope payload/manifest. Envelope `reader_version`
identifies the export adapter version; it does not discard the original reader.

A snapshot of a mutable view needs an immutable export boundary plus full row
identity and bytes. Its identity includes the saved snapshot ID. Re-importing
that snapshot reuses those IDs. A later observation of identical business values
is a new observation at its own boundary. Export batch IDs and newly generated
UUIDs are not stable observation IDs.
The effective q31 view reuses `(sync_run_id, row_no)` pairs; preserve those as
provenance rather than observation IDs. Its immutable export must identify each
scoped semantic/native row independently and bind the complete manifest/hash.

Canonical key serialization preserves field names/types and distinguishes null,
blank and zero. Case folding, trimming reference keys, reordering source line
numbers or guessing aliases is prohibited without an accepted key contract.
Payload hashing follows the foundation's Python JSON law. Preserve original V1
hashes separately if their hash law differs; never relabel them as envelope hashes.
Money/quantity translation uses contracted numeric units and precision, not
invented rounding of retained binary-float reader values.

## Evidence and event grain

| Lane | Source grain / inputs | Interpretation |
| --- | --- | --- |
| Order revision | Immutable accepted header plus exact snapshot line membership | Observation of fields, coverage and source presence |
| BWMS row | `(pick_no, pick_suffix, order_no, item_no, kit_indicator, line_no, batch_no, bin_no)` within source scope and capture | Native row; retain `unique_no`, SKU and row role separately |
| BWMS movement | Same native row across named from/to captures, counter endpoints and accepted row role | Positive movement observed over a comparison interval |
| Delivery note | `(delno, delsfx, printind, ordno, itemno, kitind, uniqueno)` within source scope | Native posted quantity/value at native business date |
| Settled despatch | Exact delivery-note identity plus retained settled source/version | Commercial settlement evidence for the same line, separately interpreted |
| CSS workflow | Registered V1 instance + original episode/event ID | Attributed operator intent/history with original version and timestamps |

Order snapshots do not create confirmation, packing, cancellation, closure,
invoice or payment events from presence alone. Unknown dimension states remain
unknown. Archive membership needs an accepted cross-file identity/absence
contract; it does not prove completion in other dimensions.

For BWMS, positive equal `this_pick` and `scan_quantity` deltas support the
scanner-confirmed pick lane. Positive `this_despatched` deltas support the
warehouse-despatch lane. NEW_ROW and MISSING_FROM_LATEST are not movement.
Regressions are anomaly/correction evidence, not automatically negative shipments.
Rows with different ordered/component roles or quantity units are not summed.
Curated order-line evidence omits `kitind`; that missing field is not a blank
indicator or evidence that a line has no kit/component relationship.

V1's hot/complete overlay is the reference implementation for parity, not a
universal deduplication theorem. Its positive-activity exclusion compares exact
native row identity, observation ordering and cumulative counter endpoints.
Retain both raw streams and prove overlapping windows, successive advances,
resets and corrections against fixtures before a merged lane is accepted.
Two source IDs alone cannot establish that movements are distinct.

Delivery lines have native primary key `(delno,delsfx,ordno,itemno,kitind)`.
`printind` comes from the header, and `uniqueno` is a separate line field. The
deployed reader's schema/key and duplicate guards support the stored capture PK;
the missing `unique_no` PK column does not itself evidence collapsed source rows.
Preserve all seven fields for posting/settlement identity. The checked direct
capture population is empty, so direct-to-settled row/value parity remains
blocked until a nonempty accepted capture is reconciled. Structural key proof
does not make empty data a successful end-to-end parity test.

Match a delivery's order-line reference through exact scoped customer/order and
`uniqueno`, against an accepted line revision. Its native delivery `itemno` may
differ from the current order position. Retain unresolved history rather than
falling back to matching positions or SKU names.

Retain every delivery-note amendment. Use the latest accepted observation for
current posting values, not the sum of its revisions. A settled row matched on
all seven semantic fields replaces the direct row's contribution to an effective
despatch-value view. It does not delete the direct evidence or collapse separate
delivery-note and settlement milestones. Conflicting multiple settled rows at
that grain require a reviewed amendment/credit rule before aggregation.

Native delivery-note `thisdesp` / line `lineval` support posted quantity/net
goods value. Blank currency has a specific V1 dataset inclusion rule; preserve
raw currency and record the named policy. Do not broaden that rule globally or
convert nonblank currencies without accepted exchange-rate semantics. Warehouse
BWMS contains no independently accepted commercial-value law.

## Time, freshness and coverage

- `source_observed_at`: source capture time. `recorded_at`: V2 persistence time.
  Neither is an invented physical despatch time.
- BWMS movement retains comparison-window start/end; `occurred_at` remains null
  unless an independently accepted event timestamp exists. A daily BWMS grouping
  based on observation date must be labelled as observation-window activity.
- Delivery-note business date and raw native time remain available independently.
  Only populate a timezone-aware event timestamp after validating native time
  encoding and timezone, including invalid/ambiguous times and daylight saving.
- A bundle's line completeness is limited to its accepted enumeration/keyset
  method and scope. Do not infer completeness from whichever rows happened to join.
- Configure and accept per-lane source cadence, freshness threshold, coverage
  checks and revisit budget before enabling that lane. No numeric SLA or universal
  expiry is assumed in this proposal.
- Missing, stale and partial inputs remain visible. An empty/failed capture is
  not deletion, voiding, archival, settlement, zero backlog or zero value.
- A current-day Sales Status summary cannot supply line-level event evidence.
  It retains no individual rows; preserve its different summary metric separately.

## Translation, replay and read projections

Retain all inputs before projection. Validate exact replay against every
envelope fact; identical input is a no-op, conflicting reuse of an ID fails with
retained conflict evidence. Do not skip conflicting rows and advance their cursor.

Use versioned deterministic translators for both bulk import and ongoing intake.
Persist canonical entity identities and unique typed source mappings. Events
have an immutable derivation identity and translator version, with all source
inputs retained. A translator correction creates a new interpretation; current
projections select one accepted version rather than accumulating both versions.

Commit each bounded evidence/translation/projection checkpoint atomically.
A rebuild may use a separate staging generation and atomic current-pointer switch;
its accepted intake checkpoint must not claim an incomplete generation is served.
Store input manifest/hash, source watermarks, versions, scope, coverage,
reconciliation and calculated time. Use exact numeric amounts with separately
named currencies/units in typed domain tables.

API reads use PostgreSQL projections and evaluate freshness at read time. Return
structured UNKNOWN/PARTIAL/STALE/BLOCKED states and provenance. Totals report
included population, unresolved/excluded counts, unit/currency policy and coverage.
A partial monetary sum is not a complete daily value. Staff workflow events and
owner intent are not overwritten by source refresh.

## Import manifest and contiguous continuation

Each import records contract/export ID, registered instances/epoch, consistent
snapshot or verified source boundary, source/deployed revision, source keys,
scope/population, counts/hashes, reader and translator versions, source/export/
start/end times, coverage, reconciliation, conflicts and last committed checkpoint.
Manifests containing source keys or personal data belong in protected storage;
Git contains only schema/contract evidence and synthetic fixtures.

Record a proven continuation for each lane. Immutable observation IDs can bound
an append log only after committed ordering/late transactions are handled.
Mutable workflow/policy tables need an accepted change feed or a controlled
write-quiescence/final snapshot; an updated timestamp alone is insufficient.
Do not lose updates while bulk import and catch-up overlap. Preserve the
rollback population and record the one authoritative writer for each capability.

## Acceptance and rollback

Before a lane serves staff or contributes totals, prove:
1. Full scoped identity/collision and unresolved-reference reconciliation.
2. Same-input replay, conflicting-ID rejection and versioned projection rebuild.
3. Null/zero, partial/stale, kit/component, split/amended line and archive behavior.
4. Hot/complete overlapping movement windows and counter-regression behavior.
5. Delivery posting/revision and exact settled exclusion, units and currency rules.
6. Count/quantity/value reconciliation over the same accepted V1/V2 population.
7. Bounded intake health: freshness, coverage, backlog, last success and blocked reason.
8. Least privilege and isolated populated restore with evidence/identity parity.

Only applicable lanes enter the first accepted release; unsupported lanes stay
explicitly blocked. Auth follows the [single-writer continuity runbook](../runbooks/authentication-migration.md)
and preserves existing credential/MFA semantics. Do not write a new parallel
staff database during this read-only business shadow.

Rollback stops the shadow feed or routes the affected capability to its retained
V1 path; keep new schema, evidence and manifests. Applied SQL moves forward.
A later writable cutover needs its own quiescence, final catch-up and reconciliation
plan. After V2 accepts writes, rollback must preserve those writes rather than
restoring stale workflow or security state.
