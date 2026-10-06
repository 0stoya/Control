# First Order Timeline release

Implementation: additive migration `0002_sales_order_sample.sql`, exporter
`v1_sales_export_v1`, translator `sales_snapshot_v1`, protected `/orders` and
`/api/orders` routes. Initial source export contains 20 orders, 127 revisions,
636 line inputs and 763 original observations; snapshot membership adds 127 V2
envelopes (890 total). Every sampled order has retained line renumbering history.
The sample is deliberately selected to exercise identity, not represent all orders.

The immutable manifest is
`6de6524936b43d2f85116215425299853573c94354c30d05a3e723de9d8a8dbe`.
Production payloads belong in protected non-Git storage. Counts/hashes in this
runbook do not contain source reference keys or personal data.

Prepare a clean committed release with `scripts.deploy_order_sample --mode prepare`
through the trusted CSS-Live alias. It verifies the manifest, stores its payload
root-only, installs an immutable release, applies both migrations in an isolated
named check database, and proves native import/replay/conflict/rebuild/isolation.
It deletes only that explicitly named disposable check database. Production
schema, API, proxy and V1 collector are untouched during preparation.

Activate the same prepared commit with `--mode activate`. The script saves current
proxy/auth configuration, makes a native backup, applies forward SQL, imports and
verifies exact replay, rehearses feature rollback with working sign-in/readiness,
then enables the protected routes. A populated native backup is checksum-verified
and restored to an isolated named database. All retained table counts and SHA256
fingerprints must match, including identities, evidence, manifests and projections.

Root receipts are retained under `/etc/control/rollback/orders-20261006-<commit>`.
The public gateway must deny anonymous/forged sessions, preserve sign-in, and expose
no health, docs, raw observations or arbitrary files. A staff member reviews the
real timeline through normal sign-in; do not create or borrow a live session for
deployment diagnostics.

To roll back the capability, set `CONTROL_ORDERS_ENABLED=0` in the protected staff
environment file, retain the new schema-compatible app release, restore the saved
preceding proxy configuration, test nginx and restart/reload services. Do not point
readiness at an old release that expects only migration 0001. Do not remove schema
or retained evidence. The deployment script performs this recovery automatically
on activation failure.

No recurring feed exists: refreshing the page reads the saved sample. Freshness
is UNKNOWN and source age is calculated at read time from the oldest input.
Commercial/fulfilment/invoice/payment/Promise states remain UNKNOWN. Assigned Sales
scope is intentionally blocked until account entitlement evidence is available.
After visual acceptance, next work is an accepted incremental/revisit contract and
expanded order population, followed by independent milestone lanes.
