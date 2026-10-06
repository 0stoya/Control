# Database redesign and V1-to-V2 migration

Status: Proposed implementation plan; read-only schema inventory completed on 2026-10-06.
No new business schema, data import or authority cutover has been applied.

## Three different operations

1. Schema migrations create/evolve V2 tables, constraints, indexes and grants.
2. Data migration maps accepted source evidence and durable V1 business records
   into those models, with reproducible checkpoints and reconciliation.
3. Authority cutover changes which application owns a capability's writes.

These have separate acceptance gates. A successful SQL migration does not mean
data is complete, current, reconciled or authoritative.

The operator completed V1 development and pulled the local CSS checkout on
2026-10-06. The clean, synchronized source checkpoint is
`16bb3c2d1e14b59682a88f91e0fd7a98df1e1c12`. The live V1 repository is at
`9163fd3d73950b9c737672a47f6f6059d791ad75`, and its current immutable web release
is `26ecb133833c30d26414901480d5c2fa49d9a0e1`. These are separate boundaries;
the local pull did not deploy V1 or freeze its changing business data.
See the [mapping checkpoint and entity diagram](../migration/0001-sales-order-map.md).
No V1 pull, merge or application change is performed by this mapping step.
Acronis is deferred; native local backups and isolated restore checks remain in scope.

## Intended PostgreSQL redesign

Keep one native PostgreSQL 16 application database with explicit domain schemas.
Use durable V2 IDs; retain source identities as scoped external references.
An order number alone is not a universal identity: retain source instance,
company/account and the exact header/line grain. Match names never merge accounts.

| Layer | Proposed responsibility |
| --- | --- |
| integration | Immutable captures, source links, intake runs, cursor/watermark, reconciliation |
| crm | Separate accounts and contacts, typed account relationships, addresses and activities |
| sales | Durable orders/lines, revisions and independently evidenced commercial facts |
| inventory | Exact products/SKUs, separate families/variants, depot observations and recipe relationships |
| fulfilment | Releases, picks, scans, packs, delivery notes and shipments |
| purchasing | POs/lines, receipts, claims and buyer workflow with explicit ownership |
| workflow / sla | CSS-owned tasks, decisions, policy versions, promises and calculation input bundles |
| reporting | Rebuildable, indexed views/aggregates used by API and UI |
| audit | Attributed commands, approvals, attempts and reconciliation outcomes |
| authentication | Retain compatible auth service/schema during the separate single-writer transfer |

Exact table names and constraints are frozen per capability, rather than creating
every proposed schema/table at once. Keep relational columns and constraints for
business facts; raw JSON payloads remain the evidence boundary.

For example, one canonical Sales Order survives its source's live-to-archive move.
Commercial state, picking/despatch, delivery posting, invoice, payment and Promise
state are separate dimensions. A customer group does not collapse ordering,
invoice or price-source accounts. A family groups exact variants without combining
their prices, stock or assembly recipes.

## Read-only inventory and candidate migration classification

The new control_v2 database contains:
- Applied ledger entry: 0001_foundation.sql
- Source observations: 0
- Application schemas: control, integration, audit and reporting
- No business-domain tables or imported staff authentication

V1 css_app has stored relations across 16 schemas. Storage observations include
stock_snapshot approximately 215 GB, sculptor_live 81 GB, ogl_mirror 73 GB and
catalog 15 GB. These are dated PostgreSQL size observations, not exact record
counts or approved migration populations. Relation row estimates were read only
as inventory aids; -1 means unknown statistics, never an empty table.

The following classifications are candidates requiring field-level authority
and retention review:

| V1 examples | Proposed handling |
| --- | --- |
| auth users, roles, scopes, recovery state | Preserve IDs/security semantics; shared authority first, whole compatible auth transfer later |
| fulfilment customer policies, overrides, decision_event, workflow_event / episodes | Migrate durable intent/history into explicit SLA/workflow/domain models with legacy-ID mappings |
| purchasing control_purchase_order / events, claims, work items/events and target-policy history | Preserve durable buyer state and verified native PO/line links; classify imported positions separately |
| catalog Core/family imports, adjudication and component-role reviews, product-control events | Preserve audited CSS classifications and decisions; map exact product identities and retain provenance |
| crm_ops and communication | Inventory content/ownership and migrate durable relationship/communication state where accepted |
| ogl / ogl_mirror / sculptor_live / stock_snapshot / ingest and captured catalog/CRM data | Retain accepted evidence and seed/catch up through the normal versioned translators |
| po_book_read_model, evaluated_blocker and other derived positions/current views | Rebuild from accepted evidence, migrated intent and preserved calculation contracts |

Do not discard old evidence, checkpoints or tables merely because they look like
caches. Verify whether each contains irrecoverable observations, command outcomes
or audit history. Preserve V1 for evidence/rollback until a reviewed retention
decision. Do not clone the entire V1 database into the V2 serving model.

Historical OGL evidence remains historical/reconciliation evidence. Freshness
and authoritative Sculptor facts need their accepted current source contracts.
Reuse the existing controlled captures rather than introducing competing readers.

## Schema migration procedure

Earlier on 2026-10-06, the operator reported that V2 was not yet whitelisted for
MariaDB/Sculptor. Later direct V2 probes passed: authenticated MariaDB SELECT/read
over pinned TLS and Sculptor protocol/dictionary access. See
[source access acceptance](source-connectivity-2026-10-06.md). Durable source
credentials/trust and collector/population acceptance remain separate. Discovery can run through the existing V1 host, using its accepted
captures and retained MariaDB evidence. Any V1-to-V2 export must keep the original
authority, readers, keys, timestamps and immutable manifest; do not assume a new
current source grant or create a competing collector. The
[Purchasing inbox contract](../source-contracts/0003-purchasing-mail-inbox.md)
adds a separate Microsoft 365 evidence lane and V2-native review state. Mail
settings are staged in protected files, not in the V2 PostgreSQL serving schema.
No business or mail schema migration has been applied by this discovery work.

The existing runner is scripts/migrate.py with --check / --apply.
Migration files use ordered NNNN_description.sql names. The ledger records name,
SHA256 and applied time, rejects changed/unknown applied files and verifies the
applied sequence. Never modify deployed 0001_foundation.sql.

For each reviewed capability:
1. Write its authority, stable identity/grain, event and absence/freshness contract.
2. Add forward-only SQL for the needed tables, keys, constraints, indexes and grants.
3. Apply to an isolated database and verify both schema laws and least privilege.
4. Run repeatable import/rebuild fixtures and accepted source reconciliation.
5. Deploy the additive migration with the compatible release; keep the old path
   usable during the migration window.

The current runner executes pending SQL inside one transaction with 60-second
statement and 5-second lock timeouts. Large backfills are separate bounded jobs,
not giant INSERT/UPDATE scripts embedded in the schema migration. Operations that
cannot run in this transaction, such as concurrent index creation, require a
separately reviewed extension/procedure before use.

Evolve populated tables through add, backfill, validate, switch, then later
retire old structures. Roll back application routing/capability activation while
retaining compatible schema and evidence; corrective SQL moves forward.

## Data transfer and cutover sequence

1. Freeze the first capability contract after V1's final checkpoint. Inventory
   identities, constraints, authority, durable state and source update semantics.
2. Record an initial source boundary and export manifest: populations, company/
   depot/currency/unit scope, counts, hashes, source revision, timestamps and
   translator version. Keep payloads and secrets outside Git.
3. Import in resumable, bounded batches through the same translators used for
   ongoing intake. Persistent legacy-to-V2 identity links prevent duplicate
   orders/accounts and retain ambiguity rather than guessing.
4. Replay the same input and prove no duplicate business effects. Rebuild the
   projection and prove stable results; checkpoint only committed accepted work.
5. Catch up from the initial boundary. Choose a proven event/cursor/change-feed
   mechanism for each source; timestamps alone are not assumed to capture every
   update, deletion, archival move or late correction. Mutable old records need revisits.
6. Migrate reviewed CSS-owned state with original actors, effective/recorded
   times, decisions, policy versions and identity mappings. Source refresh cannot
   overwrite that intent. Auth remains a separate shared-authority lane.
7. Compare V1/V2 over the same population: identities, lines, quantities,
   currencies/amounts, lifecycle milestones, permissions and Promise outputs.
   Retain and explain disagreements; do not force parity with stale V1 evidence.
8. Restore an isolated populated copy and verify schema, identity links,
   evidence/projections and eventual credential/login parity.
9. At capability cutover, quiesce only its old authoritative writes, complete
   final catch-up and reconciliation, then enable the new writer. Keep one
   command/scheduled-work authority and a recorded rollback boundary.
10. If V2 has accepted new writes, rollback must preserve/reconcile those writes.
    Returning to an old V1 snapshot would lose decisions or resurrect consumed
    security state; never route to stale writable state.

## Proposed first schema slice

The [first mapping](../migration/0001-sales-order-map.md) now proposes canonical
company/account/order/line identities, source links and distinct lifecycle events
for Sales Order Timeline. Its [source contract](../source-contracts/0002-sales-order-timeline.md)
records native line mapping, delivery-note key scope and overlapping warehouse
captures. The [key proof](../migration/0002-identity-proof-2026-10-06.md) now
validates commercial logical references with revision-scoped native aliases and
the delivery primary key shape. Direct delivery row parity, uncovered history
and warehouse overlap acceptance remain explicit gates before enabling those lanes.
Implement only the CRM/product context needed for that working slice, then its
translator, indexed reporting projection, authenticated API and UI. Use the same
model for precisely named warehouse and settled-despatch views.

The account-relationship design from origin/main is integrated as
[ADR 0002](../architecture/0002-evidence-backed-account-relationships.md).
The native production foundation is [ADR 0003](../architecture/0003-native-production-foundation.md).
Schema migration numbering is separate; deployed `0001_foundation.sql` is unchanged.

Existing design evidence:
- [V2 domain model and delivery sequence](../../README.md#postgresql-domains)
- [Immutable foundation evidence](../source-contracts/0001-foundation-evidence.md)
- [Auth migration: preserve passwords and MFA](authentication-migration.md)
- [V2 redesign brief and pinned CSS design sources](../product/v2-redesign.md)
- [Current backup/deployment decisions](production-launch.md)
