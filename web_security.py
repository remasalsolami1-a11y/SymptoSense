"""Pure, framework-independent web security helpers for SymptoSense.

Keeping URL, host and script-context escaping here makes the rules testable
without importing Flask or initializing the application/database.
"""
from __future__ import annotations

import json
import os
import re
from urllib.parse import unquote, urlsplit

_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


def json_for_script(value, *, ensure_ascii: bool = False) -> str:
    """Serialize JSON safely when embedding it inside a ``<script>`` block.

    JSON encoding alone does not stop ``</script>`` from terminating the HTML
    element. Escaping ``<``, ``>``, ``&`` and Unicode line separators makes the
    serialized value safe for JavaScript data literals in HTML script contexts.
    """
    return (
        json.dumps(value, ensure_ascii=ensure_ascii, separators=(",", ":"))
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def safe_internal_path(target, default: str = "/home") -> str:
    """Return a same-origin absolute path or ``default``.

    The check is intentionally stricter than a simple ``startswith('/')`` and
    also validates one URL-decoded pass so encoded network-path redirects such
    as ``/%2f%2fevil.example`` do not slip through.
    """
    default = str(default or "/home")
    value = str(target or default).strip()
    if not value or len(value) > 2048 or _CONTROL_RE.search(value):
        return default

    for candidate in (value, unquote(value)):
        if _CONTROL_RE.search(candidate):
            return default
        if not candidate.startswith("/") or candidate.startswith("//") or "\\" in candidate:
            return default
        parts = urlsplit(candidate)
        if parts.scheme or parts.netloc:
            return default
    return value



def normalize_public_base_url(value: str, default: str = "") -> str:
    """Return a clean HTTP(S) origin suitable for links and metadata.

    Deployment URLs are configuration, but treating them as untrusted keeps a
    typo, control character, credential-bearing URL, or path from leaking into
    email links, canonical tags, robots.txt, and XML output.
    """
    raw = str(value or "").strip()
    if not raw or _CONTROL_RE.search(raw):
        return default
    if "://" not in raw:
        raw = "https://" + raw.lstrip("/")
    try:
        parts = urlsplit(raw)
        if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
            return default
        if parts.username is not None or parts.password is not None:
            return default
        port = parts.port  # also validates the port syntax/range
        host = parts.hostname.lower().rstrip(".")
        if not host or _CONTROL_RE.search(host):
            return default
        rendered_host = f"[{host}]" if ":" in host else host
        netloc = rendered_host + (f":{port}" if port is not None else "")
        return f"{parts.scheme.lower()}://{netloc}"
    except (ValueError, UnicodeError):
        return default

def _host_from_url(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        return ""
    if "://" not in value:
        value = "https://" + value
    try:
        return (urlsplit(value).hostname or "").strip().lower().rstrip(".")
    except ValueError:
        return ""


def trusted_hosts_from_environment(environ=None) -> list[str]:
    """Build Flask's host allow-list from explicit and deployment settings.

    ``TRUSTED_HOSTS`` is comma-separated. ``SITE_URL`` and Railway's public
    domain are added automatically so normal custom-domain + Railway traffic
    remains valid. Local development returns an empty list (no host restriction).
    """
    env = os.environ if environ is None else environ
    hosts: list[str] = []

    def add(host: str) -> None:
        host = str(host or "").strip().lower().rstrip(".")
        if not host:
            return
        # Flask/Werkzeug accepts a leading dot as a subdomain wildcard. Keep it
        # only when the operator explicitly supplied it via TRUSTED_HOSTS.
        normalized = host if host.startswith(".") else _host_from_url(host)
        if normalized and normalized not in hosts:
            hosts.append(normalized)

    for item in str(env.get("TRUSTED_HOSTS", "") or "").split(","):
        item = item.strip()
        if not item:
            continue
        if item.startswith("."):
            if item not in hosts:
                hosts.append(item.lower().rstrip("."))
        else:
            add(item)

    site_host = _host_from_url(env.get("SITE_URL", ""))
    if site_host:
        add(site_host)
        # Common canonical-domain alias; exact only, not an arbitrary wildcard.
        if site_host.startswith("www."):
            add(site_host[4:])
        elif "." in site_host and site_host not in {"localhost"}:
            add("www." + site_host)

    add(env.get("RAILWAY_PUBLIC_DOMAIN", ""))
    add(env.get("RAILWAY_PRIVATE_DOMAIN", ""))

    # Railway performs deploy-time health checks with this Host header.
    # Flask/Werkzeug 3.1 rejects requests whose Host is not in TRUSTED_HOSTS,
    # so a perfectly healthy container would otherwise fail Railway's network
    # healthcheck with HTTP 400 / service unavailable. Keep the exception
    # narrowly scoped to Railway environments instead of weakening host checks.
    railway_runtime = any(str(env.get(name, "") or "").strip() for name in (
        "RAILWAY_ENVIRONMENT",
        "RAILWAY_ENVIRONMENT_NAME",
        "RAILWAY_PROJECT_ID",
        "RAILWAY_PUBLIC_DOMAIN",
        "RAILWAY_PRIVATE_DOMAIN",
    ))
    if railway_runtime:
        add("healthcheck.railway.app")

    return hosts


def build_csp(*, secure_transport: bool = False, nonce: str = "") -> str:
    """Return the enforced CSP for the server-rendered application.

    Inline ``<script>`` blocks are authorized with a per-request nonce instead
    of the broad ``script-src 'unsafe-inline'`` permission. Inline event
    attributes are blocked outright; a same-origin compatibility bridge removes
    legacy attributes and safely rebinds a restricted set through
    ``addEventListener`` without eval/new Function.
    """
    clean_nonce = re.sub(r"[^A-Za-z0-9_-]", "", str(nonce or ""))
    script_src = "script-src 'self'" + (f" 'nonce-{clean_nonce}'" if clean_nonce else "")
    script_elem = "script-src-elem 'self'" + (f" 'nonce-{clean_nonce}'" if clean_nonce else "")
    style_src = "style-src 'self' https://fonts.googleapis.com" + (f" 'nonce-{clean_nonce}'" if clean_nonce else "")
    style_elem = "style-src-elem 'self' https://fonts.googleapis.com" + (f" 'nonce-{clean_nonce}'" if clean_nonce else "")
    directives = [
        "default-src 'self'",
        script_src,
        script_elem,
        "script-src-attr 'none'",
        style_src,
        style_elem,
        # Many legacy components still use non-executable style attributes.
        # Keep that compatibility scoped to attributes rather than all styles.
        "style-src-attr 'unsafe-inline'",
        "font-src 'self' https://fonts.gstatic.com",
        "img-src 'self' data: https:",
        "connect-src 'self'",
        "frame-src 'self' https://www.youtube-nocookie.com",
        "worker-src 'self'",
        "manifest-src 'self'",
        "media-src 'self'",
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
    if secure_transport:
        directives.append("upgrade-insecure-requests")
    return "; ".join(directives)

def build_strict_script_csp_report_only(*, nonce: str = "") -> str:
    """Strict migration policy that reports any remaining inline handlers."""
    clean_nonce = re.sub(r"[^A-Za-z0-9_-]", "", str(nonce or ""))
    script_src = "script-src 'self'" + (f" 'nonce-{clean_nonce}'" if clean_nonce else "")
    return "; ".join([
        "default-src 'self'",
        script_src,
        "script-src-attr 'none'",
        "object-src 'none'",
        "base-uri 'none'",
        "frame-ancestors 'none'",
    ])

