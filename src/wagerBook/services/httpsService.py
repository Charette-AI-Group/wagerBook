"""Opening https addresses with a certificate list that travels with the app.

Python checks a site's certificate against a list of trusted authorities. On
Windows it borrows the system's list; a standalone macOS build often finds no
list at all, and then every https request fails as if the site were down -
Update Prices would report "could not reach" for every wager, with the
network working fine. certifi ships the list inside the app, so the answer is
the same from source, from the Windows installer and from the Mac bundle.
"""

from __future__ import annotations

import ssl
import urllib.request
from functools import cache


@cache
def sslContext() -> ssl.SSLContext:
    try:
        import certifi
    except ImportError:  # pragma: no cover - certifi is a dependency
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())


def trustedAuthorityCount() -> int:
    """How many certificate authorities requests are checked against; 0 means none work."""
    return sslContext().cert_store_stats().get("x509_ca", 0)


def openUrl(request: urllib.request.Request | str, timeout: float):
    """urllib.request.urlopen, with the app's own certificate list."""
    return urllib.request.urlopen(request, timeout=timeout, context=sslContext())
