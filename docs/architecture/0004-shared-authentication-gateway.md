# ADR 0004: One staff authentication authority during parallel operation

Status: accepted for the first staff shell, 6 October 2026.

V1 and V2 must preserve the same passwords, authenticator enrolments, replay
counters, recovery-code consumption and immediate account/permission changes.
An independently writable restored auth database would split those security
decisions. V1 therefore remains the single authority until a separately rehearsed
auth transfer can move both applications together.

V2 translates its own host-only secure cookie into the authority's opaque cookie
over a pinned, forwarding-only SSH connection. Each protected request validates
the session and explicit control.access entitlement at V1. Positive identity
decisions are never cached. The connection can reach only V1 loopback port 8020;
it cannot obtain a shell or forward other ports.

The first shell uses native FastAPI-served static HTML/CSS/JavaScript. This keeps
the initial sign-in dependency small while the operational UI is developed.
The source-and-authority boundary remains applicable to a later React/Next UI.

Existing accounts need a normal sign-in at the separate V2 hostname. They retain
their password and authenticator. New-account enrolment and required password
changes follow the existing authority's stages. Administration/invitations stay
in V1 for this slice. V1 availability is a current sign-in dependency; loss of
the private link makes protected V2 requests unavailable.

See [the contract](../source-contracts/0004-shared-staff-authentication.md),
[continuity runbook](../runbooks/authentication-migration.md) and
[rollout acceptance](../runbooks/staff-auth-2026-10-06.md).
