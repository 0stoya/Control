# First Sales Order sample: retained snapshots v1

Accepted implementation scope: 20 orders, read-only shadow, 6 October 2026.
This narrows contract `sales_order_timeline_v1`; it does not cut over ERP,
fulfilment, Promise or financial authority.

The sole collector remains V1. Export the exact `SCULPTOR_LIVE` snapshot selected
by its current Sales Order header, and every retained revision of that exact
source key through the selected snapshot. Select at most 20 orders, preferring
orders with changed native positions; at most 30 revisions and 500 line inputs
per order, 2,000 line inputs overall. Reject budget overflow, ambiguous keys,
missing inputs, schema changes, reader changes and source hash failures.

One repeatable-read, read-only PostgreSQL transaction records its snapshot,
export time, deployment revision, database system identifier/OID, reader file
hashes, selected pointers and exact line membership. Save its immutable export
outside Git. The first epoch is `fse-css-app-20261006-7667602069027910251-23268`.
Register the technical ERP file scope `sculptor:live` / `css-profit-live-main`
for `/usr/livedata/data/`. This is an operating-file namespace, not a CRM legal
company inferred from a field. `cono` is a customer order reference.
A forked/restored database or changed reader requires explicit new acceptance;
the initial adapter refuses another epoch in this namespace.

Accounts use exact case-sensitive `cref`, orders use account plus unsigned
`ordno`, and commercial lines use order plus unsigned `uniqueno`. Native
`itemno` is unique only inside a revision. Canonical UUIDs use a fixed UUID5
namespace and typed JSON keys; no trimming, fuzzy matching or source slot reuse.
Each original observation keeps its epoch-scoped original ID and all captured
hashes, schema, timestamps and keys. Snapshot membership has a separate immutable
observation. The V2 envelope hash uses the foundation JSON law; the original V1
hash uses its own law and is independently checked.

Translator `sales_snapshot_v1` retains typed source order date, SKU, description,
native/logical line numbers, and captured quantity/price as shortest JSON decimal
text without rounding. These are captured reader values, not accepted commercial
amounts. Original decoded floating values remain in evidence. Unit text is
captured, currency and kit/component interpretation remain unknown. There are
no value or quantity totals. Null and zero stay distinct.

Each revision produces only `ORDER_SNAPSHOT_OBSERVED`; `occurred_at` is null.
The original snapshot timestamp may precede its line reads. Retain it unchanged
in evidence; the revision's source observation time is the latest input capture,
with the oldest input capture stored separately. Evaluate age using that oldest
input, and show both ends rather than assuming an atomic ERP read.
Commercial, fulfilment, invoice, payment and Promise dimensions are UNKNOWN.
Source state is PRESENT_IN_CAPTURE, coverage PARTIAL (bounded population/keyset
and retained-history window), authority SHADOW. Show source observation time and
age at request time. No freshness SLO is accepted, so freshness is UNKNOWN.
Line removal from a revision is a changed captured membership, not cancellation.

All ingestion, immutable interpretations, current pointers and the committed
manifest are one transaction. Identical replay verifies every input and typed
interpretation before becoming a no-op. Conflicting reuse aborts the whole batch;
record a separate scrubbed failure audit without advancing a pointer. Rebuild
current pointers from the retained committed manifest and immutable revisions.
The boundary is an initial saved sample, not an incremental cursor: continuation,
late commits, revisit cadence and a recurring feed remain unaccepted.

Each request freshly validates the shared V1 session and `control.access`.
Known purchasing, planning and operations profiles retain V1 general Order access.
Sales with explicit ALL scope may read the sample. ASSIGNED Sales is denied until
V1 account ownership evidence can be enforced; order-header rep is not a substitute
for V1 account entitlements. Unknown profiles/scopes fail closed. Browser headers
never supply identity. Runtime reads selected reporting views only.

Reconcile exact selected IDs, snapshot/line/observation counts and hashes, logical
identities, revision membership and current pointers. Prove replay, conflict
rollback, renumbering, native slot reuse, projection rebuild, runtime isolation,
and a populated isolated PostgreSQL restore. Disable the order feature to roll
back the capability while retaining its schema and evidence. Keep shared sign-in
available; no down migration. This sample is not the full order population.
