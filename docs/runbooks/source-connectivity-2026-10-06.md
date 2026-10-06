# New-server MariaDB and Sculptor access

6 October 2026, 17:26 BST onward. The operator requested fresh connection tests
from CSS-Live (85.215.119.154) before the first business import.

## Observed

| Source | Endpoint | Network | Application read |
| --- | --- | --- | --- |
| MariaDB | 20.90.29.189:3306 | TCP connected; protocol-10 greeting | Authenticated livedata connection, SELECT 1 and one bounded table read passed over pinned TLS 1.3 |
| Sculptor | 20.90.29.189:5343 | TCP connected | Sculptor 5.9.9/protocol 1.9 handshake and bounded stock dictionary read passed |

Identical TCP control probes from FSE-root succeeded. This resolves the earlier
assumption that the new server cannot reach either endpoint. It does not prove
permissions beyond the tested MariaDB read, recurring ingestion, data coverage
or authority cutover.

The existing, inspected read-only Sculptor probe was transferred into a temporary
directory, SHA256 verified and executed using native Java. It read stock.d
(11,507 bytes), closed its handles/session and removed the temporary artifact.
No business records, lock operations, writes or file enumerations were requested.
The [metadata evidence](../migration/source-connectivity-2026-10-06.json) retains
probe and dictionary hashes, versions and observed scope without business payloads.

Native Ubuntu openjdk-17-jre-headless and python3-pymysql packages were installed
for diagnostics. No source environment file, daemon, timer or collector was
activated. Existing V1 remains the collector/operational authority.

## MariaDB authenticated read acceptance

The server advertises TLS, but default certificate validation fails because its
chain is self-signed. V1's existing ODBC template has SSLVERIFY=0 and no configured
CA file was found. No credential was sent by these network/TLS diagnostics.

A concrete one-off probe was executed: obtain the exact public server certificate
through the trusted FSE-root management connection, bind V2 to that certificate
with TLS verification and an exact fingerprint check before authentication, use
the existing credential only in process memory over trusted SSH, select the
livedata database and execute SELECT 1 plus one bounded read inside a read-only
transaction. Roll back/close and retain only sanitized results.

Automatic approval review rejected running that probe because the connectivity
request did not explicitly authorize using/transferring the privileged MariaDB
credential. The operator then explicitly approved the one-off read-only test;
the approved probe ran successfully. This approval was distinct from the earlier
approved mail-credential transfer.

Observed result: AUTHENTICATED_READ_OK, authenticated=true,
bounded_source_table_read=true, TLSv1.3. The certificate pin was
02036952a45bbabfadc42668ef4be53a4210b80c375548bc3b2ad5a8a3fe0e44.
Certificate validity/trust against the pinned leaf and the exact peer fingerprint
were checked before authentication. No credential or table payload was persisted;
no source writes were performed. Staff API/bridge/nginx/PostgreSQL/backup health
remained active and the private application remained READY.

Before recurring MariaDB access, configure reviewed durable CA/certificate trust
and protected credentials with the appropriate source permissions. A temporary
probe pin is not a persistent production connection configuration.
