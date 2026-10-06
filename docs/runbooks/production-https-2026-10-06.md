# Control V2 HTTPS setup acceptance — 2026-10-06

Status: Public HTTPS setup endpoint deployed and verified; renewal simulation and reload hook passed.

## DNS and exposure

The operator updated the DNS zone. Observed on 2026-10-06:
- A: 85.215.119.154
- AAAA: 2a01:239:0:e0::1, matching eth0's assigned global IPv6 address
- Authoritative server ns1042.ui-dns.de returned both records.
- Client/server lookups agreed; 1.1.1.1 and 8.8.8.8 returned the new A record.

Native Nginx 1.24.0 is active and enabled. UFW permits rate-limited SSH and
80/443 for both address families. PostgreSQL remains at 127.0.0.1:5432 and
the foundation API at 127.0.0.1:8100. API readiness remains READY and no failed
systemd units were observed.

HTTPS serves a static setup page with HTTP 503 and a link to current Control.
The stylesheet returns 200. Authentication and API routes return the same setup
response; no app/auth upstream is configured. This is a public infrastructure
endpoint, not staff sign-in or a business-capability deployment.

## Certificate and renewal

Native Ubuntu Certbot 2.9.0 issued an ECDSA certificate through HTTP-01 webroot:
- Hostname: control.csscdn.co.uk
- Issuer: Let's Encrypt YE1
- Not before: 2026-10-06 10:04:46 UTC
- Not after: 2027-01-04 10:04:45 UTC
- Runtime certificate directory: /etc/letsencrypt/live/control.csscdn.co.uk
- Webroot: /var/www/control-acme
- Automatic renewal: enabled certbot.timer
- Deploy hook: /etc/letsencrypt/renewal-hooks/deploy/control-nginx.sh;
  validates Nginx configuration before reloading.

No account email was invented; the ACME account was registered without email.
Certificate and account private keys remain root-controlled on the server,
outside the repository. Backup planning includes /etc/letsencrypt; the existing
local PostgreSQL dump job does not by itself back up these TLS credentials.

The staging renewal simulation completed with exit status zero and all simulated
renewals successful. The deploy hook validated configuration and reloaded Nginx.
Nginx's successful syntax messages were written to stderr, which Certbot labels
as hook error output; the hook and renewal completed successfully. The production
certificate dates remained unchanged. Certbot's non-interactive test included a
198.7-second randomized delay before execution.

The private key is root:root mode 0600; live/archive directories are root:root
mode 0700. No private-key content was retrieved.

## Verification

At 2026-10-06 11:05:45 UTC (12:05:45 Europe/London), external probes from FSE-root
to the public hostname verified:
- IPv4 HTTPS: trusted certificate and expected 503 HTML setup response.
- IPv6 HTTPS: trusted certificate and expected 503 HTML setup response.
- HTTP: 308 to https://control.csscdn.co.uk/.
- Security headers: HSTS, content-type protection, denied framing, restrictive
  static-page CSP and no-store.
- Setup response body SHA256 matches the deployed source.

A separate HTTPS probe from the operator's PC also verified the certificate.
The first sandboxed Windows curl probe failed in the local Schannel credential
provider; an unsandboxed probe succeeded. This was a local tooling limitation.

Native TLS checks accepted TLS 1.2 and TLS 1.3 with certificate verification.
TLS 1.1 was rejected with protocol-version alert 70. Unknown SNI was rejected
with unrecognized-name alert 112. Nginx syntax validation and renewal-hook shell
syntax validation passed. Public auth/API paths remained 503.

## Deployed sources and recovery

Source archive: control-edge-20261006.tar.gz
SHA256: 82af08b10c531d1e311bc067301b4907ff9fc9be93419c1cc88b4a05e32e1c62

Reviewed source files:
- deployment/nginx/control-http-bootstrap.conf
- deployment/nginx/control.csscdn.co.uk.conf
- deployment/nginx/setup.html
- deployment/nginx/setup.css
- deployment/ubuntu24/renew-nginx.sh

Active configuration: /etc/nginx/sites-available/control-v2, linked from
sites-enabled/control-v2. Original Nginx and UFW configuration copies plus the
HTTP bootstrap config are retained under /root/control-edge.YJITb53Z.
The original default site file was retained; only its enabled symlink was replaced.

Deployed hashes:
- Nginx TLS config: 3140c9296a448cfd2b4cd83c001c9c4cb39ccb56907d84884e168500dbd601c1
- Setup HTML: dd852cdfbbf17fb0db1a66ed8dea27a79840ee73560470b33559f662af0c13ca
- Setup CSS: 24d32c1bef2c3d7d3bd58ab7ef2476f208018bb0b3da86a37a868b406f176123

Keep deployment recovery scoped to the reviewed web configuration and web
firewall rules. Do not reset UFW, alter SSH access or overwrite an application
release. The existing API release and migration were unchanged.

The renewal hook follows [Certbot's documented deploy-hook mechanism](https://eff-certbot.readthedocs.io/en/stable/using.html#renewing-certificates).
HTTP-01 checks must continue to work on the published IPv6 address;
[Let's Encrypt documents its IPv6 validation preference](https://letsencrypt.org/docs/ipv6-support/).
Unknown TLS hostnames are rejected using
[Nginx's ssl_reject_handshake directive](https://nginx.org/en/docs/http/ngx_http_ssl_module.html#ssl_reject_handshake).
