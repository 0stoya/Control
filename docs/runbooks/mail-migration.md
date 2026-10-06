# V1 mail settings and Purchasing inbox

Status: Settings staged disabled on 2026-10-06 after explicit operator approval
for SMTP password and Graph private-key transfer. Inbox access and activation
remain pending.

Verified receipt: `/etc/control/mail/imports/v1-20261006T135759Z-1d36d1f2` on
CSS-Live, one profile and one profile-history event, bundle integrity verified.
Directory and import parent are root-owned 0700; all seven files are root-owned
0600. Receipt says enabled=false, worker_installed=false, outboxes_imported=false.
No sender or mail reader was activated and V1 was unchanged.

V1 sending has two lanes: SMTP invitations on the authentication service, and a
certificate-authenticated Graph sender for Purchasing PO PDFs. The database
profile owns sender/reply-to/templates/version/audit; credentials stay in protected
files. Preserve both lanes, but keep V1 the only sender until capability cutover.

## Protected settings staging

From an operator machine with the verified, key-authenticated `FSE-root` and
`CSS-Live` aliases, use the repository script:

```powershell
python scripts/migrate_v1_mail_settings.py
python scripts/migrate_v1_mail_settings.py --apply
```

Check mode reads the settings into process memory and returns counts/presence
only. Apply streams them through verified SSH into a newly named root-only
`/etc/control/mail/imports/v1-...` directory (0700; files 0600). It verifies the
bundle hash. Credentials never pass through local files, repository files or
tool output. Source settings, templates and profile history are preserved.

The receiver records `enabled=false`, installs no service and imports no outbox,
PO issue/resend rows, recipients or invitation state. Source profile `enabled`
means enabled on V1 only. Imported CSS paths and old public origin are evidence,
not runnable V2 configuration. A repeated apply creates a separate snapshot;
there is no automatic merge or overwrite. Protect this directory in the eventual
credential backup plan. Do not use database dumps as its credential backup.

Activation requires reviewed compatible V2 configuration, service-scoped systemd
credentials, a verified current certificate, and the appropriate new public
origin for invitations. Migrate invitation delivery with its single auth writer.
Preserve original issue/revision hashes and actors separately as communication
history; never interpret an imported SENT/GRAPH_ACCEPTED row as a new send job.
Do not automatically resend OUTCOME_UNKNOWN or pending invitations.

## Inbox read permission

The selected mailbox is purchasing@chelmsfordsafety.co.uk. A read-only metadata
probe on 2026-10-06 successfully authenticated the existing certificate but
received HTTP 403 from its Inbox. No messages were returned. The token role list
was empty; that alone does not prove missing effective Exchange RBAC grants.
The failed request establishes that the probed credential cannot currently read
that Inbox; it does not distinguish every possible tenant policy cause.

Provision a separate read-only app/certificate with mailbox-scoped `Mail.Read`.
Verify the application object's identity and Exchange resource scope. Microsoft
documents that Exchange RBAC grants and Entra permissions are additive, so an
unscoped Entra Mail.Read grant cannot be narrowed by simply adding scoped RBAC.
Keep existing PO sending operational while configuring the reader. Follow the
[official Exchange procedure](https://learn.microsoft.com/en-us/exchange/permissions-exo/application-rbac)
and verify a positive purchasing read plus a denied excluded mailbox. Do not add
Mail.ReadWrite, send capability or tenant-wide reading for this inbox.

Record permission verification as redacted status/roles/scope evidence only.
Recheck after propagation; do not repeatedly retry a 403 as a mail backlog job.
Reading messages must never mark them read, move them or send replies.

## Implementation and activation gates

Use the [inbox/source contract](../source-contracts/0003-purchasing-mail-inbox.md).
The local validator consumes extracted candidates and explicit approved mappings;
it has no mail or ERP client. Commercial match, timing exceptions, unknown fields
and review status are independent. A supplier despatch date is not a delivery
promise; stock-return dates are not accepted ERP dates.

The source-specific text/coordinate extractor is initially a local candidate
tool, not an accepted general PDF/OCR service. A changed layout or ambiguous
column/date mapping requires review. Retain original documents privately; only
synthetic regression cases belong in Git.

Before collection is enabled, implement transactional evidence/checkpoints and
attachment backlog, worker health/limits, private content retention and quarantine,
authoritative staff authentication and mailbox permissions, then the Inbox UI.
Shadow comparison against exact sent PO revisions must precede operational use.
SQL changes are forward-only additions; deployed foundation SQL is unchanged.
No public unauthenticated mailbox endpoint should be created for a prototype.
