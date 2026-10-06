# ADR 0005: Retained order evidence before lifecycle interpretation

Accepted for the first read-only sample, 6 October 2026.

V2 imports the existing V1 collector's immutable observations and snapshot
membership. It registers an ERP file namespace and a database epoch, then assigns
deterministic canonical account, order and logical-line UUIDs. Native item positions
remain revision-scoped because production evidence proves renumbering and reuse.

The saved export is the reproducible import boundary. Source observations and
translated revisions/events are append-only. A committed manifest selects the
current revision; it can rebuild the read projection without changing identity.
Same-input replay compares retained facts, not just an INSERT conflict or a hash.
The initial database allows one bounded saved sample in its registered epoch;
another population/continuation needs an additive contract and migration.

Header, line and snapshot captures need not share a timestamp. Derived revisions
retain the oldest/latest input bounds without inventing a physical event time.
Captured numeric text preserves reader precision. Currency/unit/kit semantics and
operational milestone lanes are still unaccepted, so there are no totals or inferred
fulfilment/invoice/payment/Promise states.

The API service receives SELECT on typed reporting views only. Every business
request revalidates the existing V1 session. Assigned Sales users remain denied
until the account security object can be enforced from accepted ownership evidence;
header rep is not equivalent to V1's account entitlement rule.

The operator-only initial loader uses the native PostgreSQL owner through trusted
root SSH; it has no source credential or recurring service. No new collector is
installed. A later worker requires its own role, contiguous continuation, revisit
budget and health contract.

Rollback disables the new capability on a schema-compatible release and restores
the preceding proxy route set. Shared sign-in remains available. Evidence and SQL
are retained. See [the sample contract](../source-contracts/0005-sales-order-sample.md).
