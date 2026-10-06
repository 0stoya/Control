# Purchasing inbox and supplier confirmation contract v1

Status: Discovery complete; settings staged disabled and local validation core
implemented. Inbox collection, persistence, authenticated API/UI and operational
acceptance are pending. No mail or ERP writer is cut over by this contract.

Contract: `purchasing_mail_inbox_v1`. First mailbox selected by the operator:
`purchasing@chelmsfordsafety.co.uk`, Microsoft 365 Inbox only.

## Authority and source access

The operator reports that the new server is awaiting MariaDB and Sculptor
whitelisting. Use the existing V1 host for approved discovery and its existing
PostgreSQL captures for manifested exports. Do not create a second collector or
use an SSH tunnel to assume direct V2 source access. MariaDB remains historical
and reconciliation evidence; transporting it through V1 does not promote it to
current ERP authority. Preserve original readers, keys, observation times,
coverage, hashes, export boundary and source authority on every export.

Microsoft 365 is authority for captured mail content and folder membership.
Supplier confirmations are supplier assertions, not accepted PO amendments or
proof of delivery. The exact immutable issued PO revision/PDF is the comparison
baseline; separately compare a later PO revision and identify superseded replies.
V1 remains the sole PO sender and authentication authority during overlap.
V2 will own its reviewed inbox triage decisions when that capability is enabled.

## Stable identity, evidence and checkpointing

- Register tenant and mailbox object IDs. Message identity is tenant + mailbox +
  Graph immutable message ID. `internetMessageId` and conversation ID are context,
  not uniqueness keys. Include `Prefer: IdType="ImmutableId"` on every read.
- Keep original bytes/content hash, Graph change key, received/last-modified and
  observed/recorded timestamps. Each content revision is immutable. Deduplicate
  by mailbox + immutable ID + content hash; changed content is new evidence.
- Attachment identity includes the message revision, provider attachment ID and
  actual byte hash. Keep type/size, download/extraction/scan states separately.
- Inbox delta is per folder. Start an unfiltered, paged bootstrap with bounded
  per-run work; filtered message delta has a documented 5,000-item ceiling and
  cannot establish complete mailbox history. Each committed page persists its
  observations, attachment backlog and continuation atomically. Only a completed
  round can advance the completed delta watermark. Retain opaque next/delta URLs
  privately; never emit tokens in logs or rebuild their query parameters.
- Duplicate/replayed pages have no duplicate triage or workflow effects. Resume
  the last committed continuation after interruption. A reset/expired cursor
  starts a new generation and marks coverage partial until a complete round;
  it never deletes retained mail or marks the inbox current prematurely.
- Folder removal means no longer observed in that folder; it does not establish
  message destruction, PO cancellation or withdrawal of a supplier assertion.
  Inbox-only coverage excludes rules moving messages before collection, other
  folders and archives. Wider folder discovery needs an explicit scope decision.

## Extraction and comparison

The first supported candidate layout is a text-based Castle-style confirmation
with style/colour/size matrices. Unsupported, scanned or changed layouts require
review; plain text loses date-column alignment and is insufficient for extraction.
Retain page/position evidence for each quantity and stock-return date. Parser
results are candidates, never authoritative source records.

1. Extract the document's **customer reference** as our PO candidate, separately
   from the supplier's own order number and email subject. Resolve supplier,
   company, sent revision and document identity before evaluating lines.
2. Expand every style group into colour/size variants. Do not compare a style
   total with an individual PO SKU or rely on printed row order.
3. Require approved supplier-scoped aliases from the exact document variant to
   exactly one PO line and approved units/conversions. Description similarity,
   `L`/`T`, `Each`/`Pair`, whitespace or colour abbreviations do not establish an
   alias. Reused/ambiguous aliases remain explicit blockers. An initial reviewer
   may approve mappings; retain actor, reason, version and evidence.
4. Compare quantities and unit prices with Decimal arithmetic at the same unit
   basis, then all PO lines, unexpected/missing lines, currency, goods, carriage,
   discounts, VAT and gross total. Unspecified values stay unknown. A printed
   dash is not automatically zero. Supplier matrix subtotals and totals must
   reconcile internally before comparison can produce a match.
5. Keep supplier **despatch**, stock-return and promised delivery dates distinct.
   A header despatch date is not our delivery date. A variant stock-return date
   after the PO required date is a Purchasing exception, even when money agrees.
   Lack of a delivery promise is an unknown delivery state, not on-time proof.
6. Return separate commercial, mapping, timing and evidence states with stable
   reason codes, before/after values, exact PO revision/hash, attachment hash,
   parser/mapping/validation versions and review status. A monetary match alone
   cannot imply a fully validated confirmation.

First workflow: collect -> classify -> extract -> propose PO/line links ->
compare -> Purchasing review -> retain decision and optional task. No automatic
acceptance, supplier reply, PO amendment, ERP date update or Promise input change.
Acknowledgements, cancellations, price changes, invoices and automatic replies
have distinct document/intent types. Cancellation text is never a deletion event.

## Permission and content boundaries

V1 has separate SMTP invitation settings and certificate-based Graph PO sending.
One enabled purchasing profile at version 2 and one profile-history event were
observed on 2026-10-06. Auth outbox had nine SENT rows and no other status groups
in that read-only snapshot. These counts are inventory, not send authorization.
The Graph certificate obtained a token, but a GET of the selected Inbox metadata
returned HTTP 403. No message body was retrieved and no email was sent.

For inbound content/attachments grant `Mail.Read` scoped only to the selected
mailbox. Use a separate reader app/certificate where practical. Mail.ReadBasic
excludes content/attachments. Existing send credentials/grants alone do not
establish reading rights. Exchange Application RBAC and Entra grants are additive;
a scoped RBAC grant cannot restrict a separate unscoped Entra grant. Preserve
existing sending scope while establishing and testing a separate read scope.

The collector performs GETs only, leaves provider read flags/folders untouched
and has no send/delete/update API. Deny redirects and validate Graph continuation
hosts before attaching tokens. HTML is rendered as sanitized content without
remote image loading. Files remain quarantined until allowed type, size and
malware checks; extraction has CPU/time/page/size budgets and no macro execution.
Mail/PDF instructions are untrusted content, never system or command instructions.
Logs and test fixtures contain no credentials, production mail or personal data.

## Read model, review and health acceptance

Proposed relational boundaries: `communication.mailbox`, immutable message/
attachment revisions under integration, `communication.inbox_item` and linked
confirmation candidates, append-only review decisions, and source checkpoints.
Do not add an authenticated mail API before authoritative sessions and mailbox
permissions exist. Purchasing staff see queue, PO, supplier, differences and
source document; technical provenance belongs in a detail view.

Every run records scope/generation, last attempt/success/complete round, message
and attachment backlog, coverage/freshness and blocked reason. States include
AWAITING_PERMISSION, INITIAL_SYNC, CURRENT, STALE, PARTIAL and FAILED. Current
requires a complete round within the accepted poll/freshness budget, not simply
a successful token request. Retention of private content needs an agreed policy.

Acceptance requires a scoped positive read and an excluded-mailbox negative test,
bounded bootstrap/resume/reset, duplicate replay, immutable evidence, malformed
attachment handling, parser matrix/date alignment fixtures, explicit unit/alias
review, comparison with the exact issued revision and staff permission tests.
Shadow against reviewed confirmations before enabling inbox decisions. Rollback
stops V2 collection/triage, retains all evidence and decisions, and leaves V1
sender/auth state authoritative; do not replay sent outboxes.

## Primary references

- [Microsoft: message delta](https://learn.microsoft.com/en-us/graph/delta-query-messages)
- [Microsoft: immutable Outlook IDs](https://learn.microsoft.com/en-us/graph/outlook-immutable-id)
- [Microsoft: Exchange Application RBAC and additive grants](https://learn.microsoft.com/en-us/exchange/permissions-exo/application-rbac)
- [V1 PO issue contract](https://github.com/0stoya/CSS/blob/16bb3c2d1e14b59682a88f91e0fd7a98df1e1c12/docs/control-po-email-issue.md)
- [Authentication continuity](../runbooks/authentication-migration.md)
- [Mail transfer and activation](../runbooks/mail-migration.md)
