# V1 order-line and delivery-note identity proof

Status: Native key shape and scoped commercial-line mapping validated against
the observed V1 population; direct delivery-note row parity and full historical
coverage remain pending. No schema migration, source write, data transfer or
capability cutover was performed.

Date: 2026-10-06. Checks ran from 12:21 to 12:33 UTC / 13:21 to 13:33 BST.

## Decisions for the first V2 schema

1. Keep the scoped order header identity `(cref, ordno)`.
2. Within an accepted commercial-line revision, use the scoped order plus
   `uniqueno` as the operational line reference. Retain `(ordno, itemno)`
   as the physical native key, mapped to that logical line **per revision**.
   Do not give the native item slot a lifetime-unique canonical line mapping.
3. Join delivery evidence to an accepted order-line revision by exact scope,
   customer/order and `uniqueno`. Its delivery `itemno` is preserved as a
   document/native position; it is not the current order-line position.
4. Preserve both the five-field native delivery-line key and the seven-field
   posting/settlement identity. `uniqueno` is a retained field outside the
   native primary key. A later changed field is a new observation/revision.
5. Export views behind an immutable, hashed snapshot manifest and full native/
   semantic row keys. The effective settled view's `(sync_run_id, row_no)`
   pairs are not stable, unique acquisition identities.
6. Reject ambiguous aliases, mixed owners and conflicting capture identities.
   Unresolved historical references stay counted and retained; no matching by
   order number alone, native position alone or SKU similarity.

These are identity decisions for read-only shadow import and schema design,
not an assertion that all orders are current, fully captured or operationally
authoritative. Source instance/company namespaces must be registered before
intake. Account/CRM references retain their existing separate contracts.

## Source and deployed-reader proof

The pinned local CSS checkpoint is
`16bb3c2d1e14b59682a88f91e0fd7a98df1e1c12`. At 12:21:44 UTC the live
`/srv/css/repository` also reported that revision, with no changes in the seven
inspected reader/contract paths. All seven live file SHA256 hashes match their
Git blobs at the pinned commit. This is a later observation than the map's
earlier live repository checkpoint; this audit did not pull or deploy V1.

The [aggregate evidence JSON](v1-identity-checks-2026-10-06.json) records hashes,
frozen dictionary key layouts and each query's scope/time/counts. It contains no
business payloads, customer references, stock codes, credentials or source row keys.

| Native file | Primary key | Separate retained reference |
| --- | --- | --- |
| orders | `cref(6), ordno(4)` | Preserve customer/account scope |
| orditem | `ordno(4), itemno(2)` | `uniqueno` at byte offset 274 |
| orddelnthdr | `printind(1), delno(4), delsfx(1), ordno(4)` | Header print state and customer reference |
| orddelnt | `delno(4), delsfx(1), ordno(4), itemno(2), kitind(1)` | `uniqueno` at byte offset 423 |
| ordpickbwms | `pckno, pcksfx, ordno, itemno, kitind, lineno, batchno, binno` | `uniqueno` and SKU remain separate attributes |

Parenthesized widths are bytes; offsets are zero-based. The delivery line key
is 12 bytes and does not contain print state or `uniqueno`. V1 composes the
header print state with the line key for storage and adds the separate logical
reference for posting/settlement matching.

The frozen delivery dictionary fixtures originate in test data and have different
whole-schema hashes from the guarded live dictionaries. They must not be
mislabelled as live hashes. Deployed Java guards the live schema hashes, validates
each native line key against its record's first 12 bytes, requires strictly
advancing keys and fails before saving partial/bounded-overrun results.
Python rejects duplicate native/header row identities before its transaction;
its inserts do not upsert or silently deduplicate lines.

All 8,124 retained direct capture rows attest the same guarded live schema pair,
end-of-index and zero full-file enumeration/locking/write counters. Those are
capture metadata observations, not nonempty line-value parity.

## Current captured order population

Observed at 12:22:51 UTC / 13:22:51 BST:

| Check | Result |
| --- | ---: |
| Current Sales Order headers | 5,707 |
| Selected live Sculptor snapshots | 4,181 |
| OGL-selected headers without a live snapshot | 1,526 |
| Lines in the selected immutable snapshots | 19,339 |
| Header identity, snapshot count/keyset or line identity disagreements | 0 |
| Missing/invalid logical line reference | 0 |
| Multiple native items for one logical reference within a revision | 0 |
| `itemno = uniqueno` | 17,801 |
| `itemno != uniqueno` | 1,538 |
| Order numbers attached to multiple accounts in this population | 0 |

All captured line source keys match `(ordno, itemno)`; snapshot `line_no`
matches native `itemno`. The separately retained `uniqueno` is not that
position. No universal or inferred equality conversion is safe.

The 1,526 OGL-selected orders remain an explicit live-evidence coverage gap.
Zero account collisions in this population does not remove company/customer
scope from future keys. Snapshot ages range from 12 September to 6 October;
identity validity does not grant freshness or lifecycle authority.

## Retained revision / renumbering proof

Observed at 12:25:31 UTC / 13:25:31 BST:

| Check | Result |
| --- | ---: |
| Retained Sales Order snapshots | 16,847 |
| Exact snapshot-member line observations | 134,528 |
| Header/line/native-key disagreements | 0 |
| Missing/invalid `uniqueno` | 0 |
| Logical aliases ambiguous inside one revision | 0 |
| Logical references associated with different native item numbers over history | 303 |
| Native item slots associated with different logical references over history | 364 |
| Native item slots associated with different SKUs over history | 351 |
| Logical references associated with different SKUs over retained history | 0 |

This proves why native-position aliases belong to revisions. It does not prove
that an operational logical reference can never be reused outside this retained
window, or that a shared SKU identifies a line. Preserve source observations and
flag contradictory/reused logical references for review rather than silently
merging histories.

The curated order-line payload does not include `kitind`. A later focused
coverage check found it absent from all 134,544 then-retained line observations.
The earlier query's zero nonblank-kit count cannot classify rows as non-kit.
These independently timed counts differ because ingestion continued. Kit/component
classification, assembly relationships and mixed-grain quantities need their
separate accepted evidence; no kit hierarchy was proved here.

## Delivery-note proof and its limit

Observed at 12:23:40 UTC / 13:23:40 BST, the direct delivery-note capture table
contained 8,124 captures and **zero nonempty captures / line observations**.
Native schema and reader/storage key compatibility are proved structurally.
Direct line values, header/line parity and direct-to-settled exclusion are not
data-proved by that empty population. No missing line is interpreted as deletion,
voiding, settlement or a zero despatch total.

Observed at 12:27:47 UTC / 13:27:47 BST, the effective settled q31 view contained:

| Check | Result |
| --- | ---: |
| Rows / distinct seven-field semantic identities | 32,112 / 32,112 |
| Missing semantic identity fields | 0 |
| Duplicate seven-field identities | 0 |
| Native delivery/header key groups carrying multiple `uniqueno` values | 0 |
| Delivery item number differs from logical line reference | 2,462 |
| Exact matches to current captured logical order lines | 10,795 |
| Matched rows with SKU disagreement | 0 |
| Matched rows whose current item position differs from delivery item position | 200 |
| A naive `uniqueno -> current itemno` join would hit a different line | 693 |

The settled business-date range was 27 July to 5 October; it is the observed
effective view population, not proof of complete current-day coverage.
Posting and settlement remain distinct from warehouse movement, invoices and
revenue. Nonblank kit flags are preserved without assigning component semantics.

The historical reconciliation at 12:30:54 UTC matched 10,959 settled rows to
retained logical line evidence with zero SKU disagreements/ambiguities.
The remaining 21,153 rows have no matching retained snapshot line reference.
195 matched rows have delivery positions absent from the captured native-position
history. Preserve their explicit logical reference; do not fabricate a position
mapping or infer that an unmatched order is archived/completed.

## Acquisition identity and replay

At 12:32:31 UTC, 708 `(sync_run_id, row_no)` groups in the settled view were
reused, covering 2,651 rows with up to four rows per pair. Its rolling-day
publication projects narrow capture rows under a baseline sync ID. Those pairs
are presentation/backing positions, not global observation identities.

Use an immutable saved export ID plus exact scoped semantic/native row identity
for view snapshots. Validate manifest population/hash and compare every envelope
fact on replay. Preserve original row positions as provenance, but do not use them
to deduplicate business facts. A later boundary is a new observation even when
business values are unchanged. New IDs per retry are prohibited.

## Implemented local safeguards and reproduction

[Identity contracts](../../packages/contracts/sales_order_identity.py) preserve
scoped logical/native keys and reject mixed owners, ambiguous revision aliases,
duplicate capture rows and out-of-range source keys. The exact delivery resolver
returns unresolved when no accepted logical reference matches; it has no position
or SKU fallback. It assigns no canonical UUID, freshness, authority or kit role.

[18 synthetic identity regressions](../../tests/test_sales_order_identity.py)
cover renumbering, reused positions, wrong-line joins, company/customer scope,
capture duplicates, print/suffix/kit fields, missing evidence and snapshot identity.
Together with the existing 18 foundation tests, 36 Python tests passed locally.

The six [read-only SQL probes](../../scripts/reconciliation/current-sales-order-identity.sql)
are retained under `scripts/reconciliation/`. Each uses its own read-only
repeatable-read transaction, 20–25 second statement timeout and 2-second lock
timeout. Run them sequentially; no source connector or business payload export
is involved. For example, from the Control repository in PowerShell:

```powershell
Get-Content -Raw -LiteralPath '.\scripts\reconciliation\current-sales-order-identity.sql' |
  ssh.exe -o BatchMode=yes -o StrictHostKeyChecking=yes FSE-root 'runuser -u postgres -- psql -X -q -A -t -d css_app -v ON_ERROR_STOP=1 -f -'
```

The recorded checks are separate observations while V1 ingestion continued;
they are not an export snapshot/watermark. SQL probes and source/contract hashes
make the results reproducible without committing production records.

## Acceptance boundary

The first additive order/line schema can now enforce the proved scoped identity
and revision-alias laws. Historical uncovered rows remain explicit, and retained
Sculptor evidence does not become fresh by import.

Before enabling direct posting/settlement overlays, require a nonempty direct
capture and exact seven-field identity/value reconciliation, accepted currency/
unit/time semantics and amendment behavior. That pending data gate does not
invalidate the structural delivery key proof. No new collector, timer, ERP write,
authentication change or authority transfer was made in this step.
