"""
core/ssl_certs.py
Make HTTPS work inside a frozen (PyInstaller) macOS app.

A bundled Python has no system root certificates, so urllib/ssl fail with
CERTIFICATE_VERIFY_FAILED ("unable to get local issuer certificate") for every
call that does not go through `requests`. Point everything at certifi's bundle.
"""
from __future__ import annotations

import os
import ssl

_applied = False


def apply() -> str:
    """Configure the CA bundle for ssl/urllib/requests/httpx. Returns the bundle path ('' if none)."""
    global _applied
    try:
        import certifi
        bundle = certifi.where()
    except Exception:
        return ""
    if not bundle or not os.path.exists(bundle):
        return ""
    os.environ.setdefault("SSL_CERT_FILE", bundle)
    os.environ.setdefault("REQUESTS_CA_BUNDLE", bundle)
    if not _applied:
        try:
            ctx = ssl.create_default_context(cafile=bundle)
            ssl._create_default_https_context = lambda *a, **k: ssl.create_default_context(cafile=bundle)  # type: ignore[assignment]
            del ctx
        except Exception:
            pass
        _applied = True
    return bundle
