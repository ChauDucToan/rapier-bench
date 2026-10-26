"""Rapier Bench: Benchmark Engine package."""

import os

# ponytail: NixOS boxes have no hashed CA dir, so OpenSSL loads an empty trust store and
# every HTTPS download (datasets, WDC-PAVE raw_url) fails with CERTIFICATE_VERIFY_FAILED.
# Set the system bundle explicitly before any ssl context is created. Remove when a
# proper ca-bundle env (SSL_CERT_FILE) is guaranteed on all dev machines.
if not os.environ.get("SSL_CERT_FILE"):
    _ca = "/etc/ssl/certs/ca-certificates.crt"
    if os.path.isfile(_ca):
        os.environ["SSL_CERT_FILE"] = _ca

