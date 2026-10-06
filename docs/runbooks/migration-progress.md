# Control V2 migration progress and priorities

Status snapshot: 6 October 2026, 15:14 BST. This records observed deployment and
local implementation separately; it is not a release or authority cutover.

## Completed and verified

| Area | State and evidence |
| --- | --- |
| Native production foundation | Ubuntu 24, no Docker; key-only root SSH, firewall/fail2ban, private PostgreSQL/API and public HTTPS setup endpoint were deployed and verified |
| Current service health | At this check, V2 API LIVE/READY; API, nginx, PostgreSQL, fail2ban and backup timer active. V1 auth/API/Control active; auth health ok |
| Backup baseline | Daily local backup and isolated restore were verified in foundation acceptance; off-server backup deferred by the operator |
| V1 development checkpoint | Completed CSS checkout pinned at 16bb3c2d; current local main clean and aligned with origin |
| Database design and identity | V1 inventory, first business mapping and read-only order/line key proof retained; logical versus revision-specific native identities have tested safeguards |
| Authentication discovery | Existing Argon2/MFA security semantics and live schema inventory documented; no auth state transferred or login parity acceptance claimed |
| Purchasing mail | Approved SMTP/Graph settings and credentials staged root-only and disabled on V2; no worker activated |
| Confirmation comparison | Local coordinate-aware matrix extractor and comparison core committed at 358460b; 54 Python tests and six foundation database checks passed; production documents remain outside Git |

The V2 database currently has only `0001_foundation.sql` and zero source
observations. There are no deployed business schemas, imported staff accounts,
authenticated V2 application or operationally authoritative V2 business views.
The public site is the HTTPS setup page. Infrastructure readiness does not mean
the staff application is ready.

## Main gates and workarounds

| Priority | Gate | Type / current state | Work that can proceed |
| --- | --- | --- | --- |
| 1 | Existing staff sign-in and protected V2 shell | Implementation pending; V1 remains the single auth authority | Private authenticated connection, same-origin routes, session/CSRF/MFA/permission integration and shell; keep password and authenticator continuity |
| 2 | First business schema, intake and useful screen | Implementation pending; mapping/key proof complete for its accepted scope | Additive order/account/line migration, versioned V1 export adapter, replay/checkpoint tests, a bounded reconciled import and read-only Sales Order Timeline |
| 3 | Direct MariaDB/Sculptor access from V2 | External whitelisting pending, as reported by the operator | Use V1 for controlled discovery and existing captures; preserve authority, source timestamps and manifested export boundaries |
| 4 | Delivery/history coverage and business semantics | Data acceptance pending for some overlays | Prove missing direct delivery-note population, historical gaps, units/currencies and amendment rules before enabling the affected metrics; retain explicit gaps in the first timeline |
| Parked | Purchasing mailbox read access | Operator says REQUESTED; last observed read HTTP 403 | Local PDF candidates, comparison, review workflow and inbox UI preparation. Resume scoped access tests once availability is confirmed; no automatic polling |

Mailbox access blocks automatic mail collection, not the main platform build.
Source whitelisting blocks moving direct collectors, not design or V1-backed
intake. Authentication and a first demonstrated data import are the largest
engineering gates to a usable V2. Remaining supplier size/unit alias approval is
a Purchasing validation gate, not a reason to block all domain development.

## Next implementation milestone

Deliver an authenticated V2 shell using the existing single auth authority, then
the first additive business migration and a small reconciled V1-backed order
population with a useful read-only timeline. Preserve the old application's
operational authority until parity and capability-specific cutover are accepted.

Purchasing confirmation review can continue with local attachments and exact sent
PO revisions while mailbox permission is pending. No percentage-complete or
calendar estimate is asserted before this first end-to-end business slice exists.

## Detailed evidence

- [Foundation acceptance](production-foundation-2026-10-06.md)
- [Authentication continuity](authentication-migration.md)
- [Database migration](database-migration.md)
- [Order/line identity proof](../migration/0002-identity-proof-2026-10-06.md)
- [Pinned mail dependency and transferred settings](mail-migration.md)
- [V2 redesign and delivery sequence](../product/v2-redesign.md)
