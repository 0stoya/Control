# Control V2

Control V2 is the next generation CSS operational platform for CRM, sales orders,
fulfilment, purchasing, warehouse progress, despatch and Promise/SLA decisions.

It is being built on a fresh server, in a fresh repository, with a fresh PostgreSQL
database. The new platform will preserve the business rules and source contracts
already proved in [CSS](https://github.com/0stoya/CSS), while replacing its
source-shaped application models with durable business entities, events and
versioned projections.

## Current status

**Staff sign-in and protected shell deployed; existing-account sign-in confirmed.** Control V2 has
native Ubuntu 24.04 deployment scripts, a running private FastAPI health service,
checksum-verified PostgreSQL migrations, an immutable evidence envelope/storage
contract and focused foundation tests. No business capability is deployed or
operationally authoritative yet. Sculptor/Profit+ remains the ERP authority,
the existing CSS platform remains the calculation and operational authority,
and MariaDB/OGL remains historical and reconciliation evidence.

The production target is `85.215.119.154`, using native systemd services with
**no Docker**. Root SSH is secured with public keys, password SSH is disabled,
and the firewall permits rate-limited SSH plus public HTTP/HTTPS. The API and
database remain private. The staff gateway uses the existing single V1 auth
authority, preserving existing passwords and authenticator enrolments. Public
boundaries, native synthetic auth and rollback passed; an existing staff member
confirmed successful existing-account sign-in at the V2 hostname.

The initial public hostname is `control.csscdn.co.uk`; the later business
hostname is `control.chelmsfordsafety.co.uk`. IONOS Acronis is deferred at the
operator's request. Daily local PostgreSQL backup and restore checks remain in
the migration plan; off-server protection is not configured.
DNS, HTTPS and the public staff gateway are verified. See
[staff sign-in acceptance](docs/runbooks/staff-auth-2026-10-06.md) and the earlier
[HTTPS foundation acceptance](docs/runbooks/production-https-2026-10-06.md).
See [launch configuration](docs/runbooks/production-launch.md) and the
[V2 redesign brief](docs/product/v2-redesign.md) for the recorded decisions,
existing design evidence and proposed delivery sequence.

Start with [first root key login](docs/runbooks/ssh-key-first-login.md), then
[the production server runbook](docs/runbooks/production-server.md). Read
[authentication continuity](docs/runbooks/authentication-migration.md),
[ADR 0003](docs/architecture/0003-native-production-foundation.md) and
[the foundation evidence contract](docs/source-contracts/0001-foundation-evidence.md).

See [the deployed foundation and acceptance record](docs/runbooks/production-foundation-2026-10-06.md)
for the installed release, native tests, backup restore and remaining public rollout gates.

## Goals

- Present one durable identity and timeline for an order across current records,
  picking, despatch, invoicing and archive transitions.
- Serve Control entirely from PostgreSQL-backed APIs; browser requests must never
  contact Sculptor or MariaDB directly.
- Preserve proven Promise/SLA calculation rules while replacing their data
  adapters with explicit, fresh and reproducible input bundles.
- Separate CRM, order management, inventory, fulfilment, purchasing, finance,
  SLA and workflow concerns.
- Retain source provenance, observation time, completeness, freshness and
  authority for every decision-critical fact.
- Make imports and projections deterministic, idempotent and replayable.
- Move operational authority from V1 one capability at a time, with shadow
  comparisons and an explicit rollback path.

## Target architecture

```text
Sculptor live files                 OGL / MariaDB history
         |                                   |
         +---------- bounded evidence -------+
                             |
                             v
                immutable source observations
                             |
                    versioned translators
                             |
             canonical entities + business events
                             |
                  typed operational projections
                             |
                +------------+-------------+
                |                          |
        Promise / SLA engine          Control V2 API
                |                          |
                +------------+-------------+
                             |
                        Control V2 UI
```

The initial transition may consume a versioned evidence feed from the existing
CSS PostgreSQL platform. Proven bounded collectors can move to the V2 server
individually after parity, failure recovery and source-load behaviour are
accepted. There must never be two uncoordinated collectors claiming authority
for the same fact.

## Proposed repository shape

```text
apps/
  control-web/          React/Next.js presentation
services/
  api/                  authenticated V2 application API
  ingestion/            evidence intake and checkpoints
  translation/          versioned source-to-domain translators
  promise/              preserved Promise/SLA calculation capability
  scheduler/            bounded recurring work
domains/
  crm/
  sales/
  inventory/
  fulfilment/
  purchasing/
  finance/
  sla/
  workflow/
packages/
  contracts/            versioned messages and API contracts
  database/             database access and migration support
  observability/        health, metrics and structured logging
  testing/              fixtures and parity helpers
migrations/             fresh forward-only PostgreSQL migrations
deployment/             service, proxy, backup and restore definitions
docs/
  architecture/         architecture decisions and diagrams
  source-contracts/     accepted source semantics
  runbooks/             operating and recovery procedures
tests/
  contract/
  translation/
  parity/
  integration/
```

This starts as a modular monolith. Services should be separated further only
when scaling, isolation, ownership or deployment evidence justifies it.

## PostgreSQL domains

See the [database redesign and migration plan](docs/runbooks/database-migration.md)
for the separation between schema migrations, data transfer and authority cutover.
The [first V1-to-V2 mapping and entity diagram](docs/migration/0001-sales-order-map.md)
pins the completed local CSS checkout at `16bb3c2d` and records the distinct live
runtime revisions. Its [Sales Order Timeline contract](docs/source-contracts/0002-sales-order-timeline.md)
defines the identity and reconciliation work required before business intake.
The [key proof and acceptance limits](docs/migration/0002-identity-proof-2026-10-06.md)
record live reconciliation, native-slot reuse, delivery keys and tested local safeguards.

The operator also selected a Purchasing email inbox and supplier-confirmation
validation. [Its source contract](docs/source-contracts/0003-purchasing-mail-inbox.md)
defines immutable mail evidence, exact sent-PO revision comparison, reviewed
variant/unit mappings and independent delivery exceptions. Local coordinate-aware
candidate extraction and comparison tests are implemented; mail collection and
authenticated UI are pending. [Mail migration](docs/runbooks/mail-migration.md)
records protected disabled settings staging and the unresolved inbox read grant.
While V2 awaits MariaDB/Sculptor access, use V1 for controlled discovery/exports
under existing authority and provenance contracts.

The V2 database will use explicit domain schemas rather than reproducing legacy
file families:

| Schema | Responsibility |
| --- | --- |
| `integration` | Source observations, source keys, checkpoints, translation and reconciliation |
| `crm` | Accounts, contacts, addresses, relationships and activities |
| `sales` | Sales orders, order lines, revisions, holds and customer references |
| `inventory` | Products, depot balances, reservations and allocations |
| `fulfilment` | Releases, pick tasks, scans, packs, shipments and delivery notes |
| `purchasing` | Purchase orders, lines, inbound cover and goods receipts |
| `finance` | Credit status, invoices, credits and payments once authority is proved |
| `sla` | Versioned input bundles, evaluations, promises, blockers and policy versions |
| `workflow` | CSS-owned assignments, decisions, tasks and operator actions |
| `reporting` | Rebuildable read projections and aggregates |
| `audit` | Commands, approvals, attempts and reconciliation outcomes |

Raw source evidence, canonical domain data and derived projections must remain
separate. A current projection must be rebuildable from retained evidence and
versioned translation rules.

## Order lifecycle

V2 will not model an order with one overloaded status. It will retain independent
dimensions such as:

```text
commercial:  DRAFT | CONFIRMED | ON_HOLD | CANCELLED | CLOSED
fulfilment:  UNRELEASED | RELEASED | PICKING | PACKED |
              PART_DESPATCHED | DESPATCHED
invoice:     NOT_INVOICED | PART_INVOICED | INVOICED | CREDITED
payment:     NOT_REQUIRED | DUE | PART_PAID | PAID | OVERDUE | UNKNOWN
promise:     NOT_CALCULATED | ON_TRACK | AT_RISK | BREACHED | BLOCKED
source:      CURRENT | ARCHIVE_CONFIRMED | ABSENT_CONFIRMED |
              REVISIT_DUE | UNKNOWN
```

An archive transition is retained as evidence. It must not silently imply that
the order was picked, despatched, invoiced, paid and commercially closed unless
those individual facts are independently proved.

## Despatch semantics

V2 will keep operational and commercial milestones distinct:

- picked today;
- warehouse despatched today;
- delivery notes posted today;
- settled despatch value today;
- invoiced today;
- revenue posted today.

Each metric must name its event, business date, quantity/value law, currency,
freshness and authority. Warehouse movement, delivery-note posting, settled
despatch and invoice posting must not be merged into one ambiguous number.

## Product families and variants

V2 will represent a displayable product family separately from its exact
sellable variants. Legacy web-category evidence shows that a grouped category
can hold ordered size variants while each exact SKU retains its own price,
stock and Q24 assembly recipe. A friendly unsized family key may be created for
the V2 experience, but it is not an ERP stock code.

Family membership must come from accepted relationship evidence rather than SKU
parsing. Customer catalogue placement, exact variant identity and variant recipe
remain separate, provenance-bearing facts. See
[ADR 0001: Category-backed product families](docs/architecture/0001-category-backed-product-families.md).

## CRM account relationships

V2 will preserve each customer reference as a separate account and represent
links between accounts as typed facts. Account hierarchy, invoice-account and
price-source relationships have different meanings and retain independent
source evidence. A shared name or an invoice/price reference cannot silently
create a parent relationship.

Portable hierarchy exports use one row per company reference with a nullable
parent reference plus a manifest containing the source snapshot, observation
time, row count, hash and translator version. Imports reject duplicate children,
self-links, cycles and unresolved parents before updating projections. See
[ADR 0002: Evidence-backed account relationships](docs/architecture/0002-evidence-backed-account-relationships.md).

## Evidence and event contract

Every imported observation or event must carry enough information to reproduce
and explain the resulting state:

```text
event_id
event_type
schema_version
source_system
source_dataset
source_business_key
source_observation_id
source_observed_at
effective_at / occurred_at
recorded_at
coverage_state
freshness_state
authority_state
translator_version
payload_hash
payload
```

Consumption must be idempotent. Checkpoints advance only after evidence and its
projection commit successfully. Missing or stale evidence is not zero, complete,
cancelled or deleted.

## Migration approach

1. **Freeze contracts and identities.** Document source keys, meanings,
   freshness targets, authority and unsupported semantics.
2. **Create the V2 foundation.** Establish the repository, PostgreSQL schemas,
   authentication, migrations, evidence envelope, health and deployment.
3. **Import through translators.** Load existing evidence into staging and run it
   through the same versioned translators used for incremental updates.
4. **Deliver the first vertical slice.** Build a Sales Order Timeline and
   Despatched Today view from current orders, archive membership, picking,
   warehouse movement, delivery notes and settled despatch evidence.
5. **Introduce `sla_input_bundle_v1`.** Preserve the existing Promise formulas,
   stamp exact input versions and shadow-compare V1 and V2 results.
6. **Close authority gaps.** Complete old-order revisit/lifecycle handling,
   reservations, finance gates, scheduled state and accepted invoice sources.
7. **Move commands deliberately.** Execute writes through a durable command
   gateway, followed by independent source read-back and reconciliation.
8. **Transfer authority by capability.** Cut over individual workflows only
   after parity, failure and rollback acceptance; retire each V1/OGL dependency
   separately.

## First vertical slice

The first end-to-end V2 feature should be **Sales Order Timeline and Despatched
Today**. It will:

- create one durable identity for current and archived Sales Orders;
- translate release, picking, warehouse movement, delivery-note and settled
  despatch facts into separate milestones;
- expose source, freshness and completeness for every milestone;
- distinguish operational despatch from settled commercial value;
- reconcile order counts, quantities and values against the existing Control and
  Despatch Tracker outputs;
- prove that all projections can be rebuilt from imported evidence.

## Definition of done for a migrated capability

A V2 capability is not authoritative until:

1. its source schema, keys and business semantics are accepted;
2. collection is bounded, observable and recoverable;
3. evidence is persisted with provenance and freshness;
4. mutable records have a suitable revisit/change strategy;
5. historical import and incremental processing use the same translators;
6. V1/V2 differences are explained and reviewed;
7. partial, missing and stale evidence fails safely;
8. backup and restore are tested;
9. operational rollback is documented;
10. the old dependency is explicitly retired.

## Related system

The existing implementation, evidence, source research and accepted business
rules remain in [0stoya/CSS](https://github.com/0stoya/CSS). Control V2 should
reference that evidence while keeping its own domain contracts and architecture
decisions concise and current.

## Foundation development

Use Python 3.12. The native Linux service uses local peer authentication; local
health tests can run without a database. No source systems are contacted.

```bash
python -m venv .venv
# Linux: source .venv/bin/activate; Windows: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip check
python -m unittest discover -s tests -v
npm ci --ignore-scripts
npm run test:database
```

The Node dependency is test-only: it executes PostgreSQL SQL in PGlite to prove
constraints, append-only evidence and runtime privilege isolation. Production
uses native PostgreSQL 16. OS peer authentication, systemd, RAID, firewall, TLS,
backup restore and live auth migration require separate host acceptance.
