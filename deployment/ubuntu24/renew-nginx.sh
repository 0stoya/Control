#!/usr/bin/env bash
# Certbot deploy hook: validate configuration before loading the renewed certificate.
set -euo pipefail
/usr/sbin/nginx -t
/bin/systemctl reload nginx.service
