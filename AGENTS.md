# AGENTS.md

These instructions apply to the entire Control V2 repository.

## Mission

Build a modern operational platform without losing the business rules, source
semantics or audit evidence proved in the existing CSS system. Prefer explicit
domain contracts and reproducible state over source-shaped shortcuts.

## Authority boundaries

- Sculptor/Profit+ remains the ERP authority until a capability has an explicit
  reviewed cutover.
- Existing CSS remains the operational and Promise calculation authority during
  migration.
- V2 owns V2-native workflow state, tasks, decisions and audit records.
- MariaDB/OGL is historical and reconciliation evidence. Do not silently use it
  as current authority.
- A row being present in PostgreSQL does not establish freshness or completeness.
- Collector deployment, projection availability, UI use and operational
  authority are separate acceptance gates.

## Non-negotiable architecture rules

1. Browser requests never contact Sculptor, MariaDB or another source system
   directly.
2. Normal API and Promise/SLA requests read PostgreSQL projections only.
3. Source observations are immutable and retain their source keys, observation
   time, schema/reader version and payload hash.
4. Translators are versioned, deterministic, idempotent and replayable.
5. Derived current state must be rebuildable from retained evidence.
6. Missing, stale or partial evidence must remain explicit. Never reinterpret it
   as zero, complete, cancelled, archived or deleted.
7. Source absence is not a lifecycle transition without an accepted
   domain-specific absence contract.
8. Current/archive file movement is source evidence, not the V2 domain model.
9. Do not collapse picking, warehouse despatch, delivery-note posting, settled
   despatch, invoicing and revenue into one status or metric.
10. Preserve money currency and quantity unit/grain. Never sum unlike currencies,
    units or mixed-grain records.
11. Writes use a durable command, reviewed preconditions, an explicit result,
    independent source read-back and reconciliation.
12. Do not introduce a second collector for a fact without a documented
    ownership, deduplication and cutover plan.

## Domain design

- Use explicit relational tables and constraints for core domain data.
- Keep raw evidence under `integration`; do not expose source payloads as the
  default application model.
- Keep CRM, sales, inventory, fulfilment, purchasing, finance, SLA and workflow
  boundaries explicit.
- Model order lifecycle with independent commercial, fulfilment, invoice,
  payment, promise and source-state dimensions.
- Store business events append-only. Correct bad interpretations with a new
  translator version or superseding event/projection, not destructive history
  edits.
- Give canonical entities durable V2 identifiers while retaining every legacy
  source identifier needed for reconciliation.
- Use `occurred_at`/`effective_at`, `source_observed_at` and `recorded_at`
  deliberately; they are not interchangeable.

## Source and migration work

- Consult the accepted source contracts and evidence in
  [0stoya/CSS](https://github.com/0stoya/CSS) before assigning business meaning
  to a Sculptor/OGL field.
- Import historical data through the normal versioned translators. Do not create
  a separate one-off interpretation for the initial migration.
- Record every import manifest: source snapshot/watermark, counts, hashes,
  translator versions, start/end times and reconciliation results.
- Advance an ingestion checkpoint only after observation persistence and required
  projection updates commit.
- Keep initial bulk import and incremental continuation contiguous at a recorded
  watermark.
- Never copy secrets, production payloads or personally identifiable fixtures
  into Git.

## Promise and SLA work

- Preserve existing accepted formulas before changing business behavior.
- Introduce new source adapters behind a versioned SLA input bundle.
- Each calculation must retain the exact input versions, policy version,
  calculation version, freshness, coverage and authority used.
- Shadow V1 and V2 over the same order population. Explain differences caused by
  freshness or intentional semantic changes; do not force V2 to reproduce stale
  V1 output.
- Any incomplete decision-critical input must follow an explicit reviewed rule
  or fail closed.

## Implementation workflow

Before implementing a capability:

1. Write or update its source-and-authority contract.
2. State the business grain and stable identity.
3. Define event semantics and current projection behavior.
4. Define freshness, completeness, revisit and absence rules.
5. Define reconciliation and rollback evidence.
6. Then implement migrations, translators, APIs and UI.

Keep changes vertical and reviewable. A useful slice normally includes the
contract, migration, translation, projection, API, focused UI, health signal and
meaningful tests required to prove one behavior.

## Database changes

- Use forward-only migrations with deterministic names and ordering.
- Add primary keys, foreign keys, uniqueness and checks that protect domain
  invariants.
- Make event and observation ingestion idempotent with database-enforced unique
  identities.
- Avoid destructive migrations during migration/cutover phases. Use expand,
  backfill, verify and contract steps.
- Do not edit already-applied migrations; add a corrective migration.
- Every materialized/read projection must identify its source watermark or input
  versions and calculation time.

## API and UI

- APIs return structured states, reason codes, timestamps and provenance rather
  than requiring clients to reconstruct business rules.
- UI code presents domain results and captures user intent. It does not duplicate
  Promise, blocker, allocation, finance, lifecycle or queue-ranking rules.
- Name metrics precisely. For example, use `warehouse_despatched_today` or
  `settled_despatch_value_today`, not an ambiguous `despatched_today` where the
  distinction matters.
- Show stale, partial, unknown and blocked states clearly.

## Testing and evidence

- Test translation laws with representative source fixtures, including null,
  zero, stale, duplicate, amendment, split-line, partial and archive cases.
- Test idempotent replay and projection rebuilds.
- Test boundaries and failure behavior, not implementation duplication.
- Add parity/reconciliation tests for migrated V1 behavior.
- Do not claim authority from unit tests alone. Record production-like shadow,
  operational recovery and reconciliation evidence for cutover decisions.
- Run the smallest relevant checks while developing, then the repository's full
  required checks before publishing a pull request.

## Operations and security

- Keep credentials outside Git and grant least privilege to each service.
- Collectors and translators need bounded read/time budgets and structured run
  results.
- Every recurring worker needs health, freshness, backlog, last-success and
  blocked-state reporting.
- Backups are incomplete until restore has been exercised.
- Logs must not emit source records, credentials or unnecessary personal data.
- Production commands must be attributable to an authenticated actor and a
  retained authorization decision.

## Documentation

- Record material architectural choices as short ADRs under
  `docs/architecture/`.
- Keep the root README focused on the current target and delivery sequence.
- Distinguish clearly between proposed, implemented, deployed, observed and
  authoritative states.
- Link to detailed legacy evidence instead of copying large historical research
  documents into this repository.
