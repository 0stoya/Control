# ADR 0002: Evidence-backed account relationships

Status: Proposed

Date: 2026-09-19

## Context

Control V2 needs to represent groups of customer accounts without collapsing
their separate ordering, portal, contact, pricing and invoicing identities.

Reviewed legacy evidence already shows that one account can refer to another for
specific purposes. For example, `BIO019` retains its own portal users and CRM
contacts while its legacy customer record identifies `BIO002` as both its
invoice reference and price source. A separate reviewed hierarchy mapping also
identifies these parent relationships:

| Company reference | Parent reference |
| --- | --- |
| `BIO007` | `BIO002` |
| `BIO026` | `BIO002` |
| `BIO027` | `BIO002` |
| `BIO028` | `BIO002` |
| `BIO029` | `BIO002` |
| `BIO030` | `BIO002` |
| `BIO002` | *(none evidenced)* |

These facts do not prove that every relationship has the same meaning. A parent
relationship, an invoice-account relationship and a price-source relationship
must remain distinguishable.

MariaDB/OGL remains historical and reconciliation evidence. Importing these
relationships does not make it current operational authority.

## Decision

V2 will retain every customer account as a separate canonical account and model
links between accounts as typed, provenance-bearing relationships.

The initial relationship types are:

| Relationship type | Meaning |
| --- | --- |
| `PARENT_ACCOUNT` | An explicitly reviewed account hierarchy link |
| `INVOICE_ACCOUNT` | The account referenced for invoicing |
| `PRICE_SOURCE` | The account whose price evidence applies |

The direction is always `subject_account -> related_account`. A blank parent in
an imported hierarchy row creates no relationship. It records that the export
did not evidence a parent for that account. It must not create a self-link such
as `BIO002 -> BIO002` and must not be interpreted as proof that the account is a
corporate root outside the scope of that export.

No translator may derive `PARENT_ACCOUNT` from `invref`, `pricesrc`, a shared
name, an SKU prefix or category membership. Each relationship type requires its
own accepted source fact or reviewed mapping.

Relationships are effective-dated facts. Changes append new evidence and update
a rebuildable current projection; they do not overwrite the evidence that
supported an earlier relationship.

## Export contract

The portable hierarchy export is a UTF-8 CSV with this exact grain:

```csv
company_reference,parent_reference
BIO007,BIO002
BIO026,BIO002
BIO027,BIO002
BIO028,BIO002
BIO029,BIO002
BIO030,BIO002
BIO002,
```

The CSV carries the reviewed hierarchy values. Its adjacent manifest carries
the evidence and reproducibility metadata:

```text
export_id
contract_version
source_system
source_dataset_or_mapping
source_snapshot_or_watermark
source_observed_at
exported_at
row_count
content_sha256
translator_version
review_reference
```

Import validation must fail the batch before projection when:

- a company reference is blank;
- a child occurs more than once with different parents;
- a row links an account to itself;
- the proposed relationships contain a cycle;
- a nonblank parent cannot be resolved to an imported or existing canonical
  account;
- the manifest count or content hash does not match the CSV.

References are normalized only by the accepted account-reference contract.
Case changes, whitespace removal or alias resolution must not silently merge two
source identities.

## Proposed relational shape

```text
crm.account
  account_id
  display_name

crm.account_source_identity
  account_id
  source_system
  source_dataset
  source_reference

crm.account_relationship_evidence
  relationship_evidence_id
  subject_account_id
  relationship_type
  related_account_id
  source_observation_id
  effective_at
  source_observed_at
  recorded_at
  translator_version
  payload_hash

crm.current_account_relationship
  subject_account_id
  relationship_type
  related_account_id
  relationship_evidence_id
  projected_at
```

A uniqueness rule will allow at most one current related account per subject and
single-valued relationship type. Historical evidence remains append-only.
Future multi-valued types must be introduced explicitly rather than weakening
this invariant globally.

## Consequences

- BIO accounts remain independently addressable for users, contacts, orders and
  audit history.
- The UI can show an account group without treating all members as one customer.
- Pricing and invoicing can follow their own accepted relationships even when
  the hierarchy differs.
- Exports are small and portable while a manifest retains the evidence needed
  to reproduce and review them.
- Missing, stale or contradictory relationship evidence remains visible rather
  than being replaced by name-based inference.

## Acceptance work

1. Identify and document the source of the reviewed parent mapping, including
   its observation time or snapshot.
2. Capture `invref` and `pricesrc` under their own source contract and reconcile
   the BIO019/BIO002 example.
3. Prove account-reference normalization and canonical identity resolution.
4. Run duplicate, unresolved-parent, self-link and cycle validation against the
   complete proposed export.
5. Reconcile imported counts and relationship values against the reviewed
   source snapshot.
6. Define revisit, expiry and absence semantics before any relationship becomes
   operationally authoritative.
7. Keep portal users and CRM contacts attached to their original account unless
   a separate, reviewed identity relationship proves otherwise.
