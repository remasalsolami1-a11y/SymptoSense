"""CI unit tests must never deliver email or contact an external service.

Installed only by the test runner's PYTHONPATH, never by the web application.
Loopback connections remain available for local HTTP/database/browser fixtures.
"""
import ipaddress
import socket

_connect = socket.socket.connect
_connect_ex = socket.socket.connect_ex


def _require_local(address):
    if isinstance(address, (str, bytes)):
        return  # Unix-domain sockets
    host = str(address[0]).lower()
    if host == "localhost":
        return
    try:
        if ipaddress.ip_address(host.split("%", 1)[0]).is_loopback:
            return
    except ValueError:
        pass
    raise OSError("UNIT_TEST_NETWORK_BLOCKED: mock external services; no live email or external requests")


def _local_connect(self, address):
    _require_local(address)
    return _connect(self, address)


def _local_connect_ex(self, address):
    _require_local(address)
    return _connect_ex(self, address)


socket.socket.connect = _local_connect
socket.socket.connect_ex = _local_connect_ex

# Reject at HTTP/SMTP entry points too: no DNS lookup or provider fallback is
# attempted. Tests of integrations must mock their client, not use credentials.
from urllib.parse import urlsplit
import requests
import smtplib
import urllib.request
import urllib.error

_request = requests.sessions.Session.request
_smtp_connect = smtplib.SMTP.connect
_urlopen = urllib.request.urlopen


def _local_request(self, method, url, *args, **kwargs):
    parsed = urlsplit(str(url))
    try:
        _require_local((parsed.hostname or "", parsed.port or 443))
    except OSError as error:
        raise requests.exceptions.ConnectionError(str(error)) from None
    return _request(self, method, url, *args, **kwargs)


def _local_smtp_connect(self, host="localhost", port=0, source_address=None):
    try:
        _require_local((host, port))
    except OSError as error:
        raise smtplib.SMTPConnectError(421, str(error)) from None
    return _smtp_connect(self, host, port, source_address)


def _local_urlopen(url, *args, **kwargs):
    parsed = urlsplit(url.full_url if isinstance(url, urllib.request.Request) else str(url))
    if parsed.scheme not in {"file", "data"}:
        try:
            _require_local((parsed.hostname or "", parsed.port or 443))
        except OSError as error:
            raise urllib.error.URLError(str(error)) from None
    return _urlopen(url, *args, **kwargs)


requests.sessions.Session.request = _local_request
smtplib.SMTP.connect = _local_smtp_connect
urllib.request.urlopen = _local_urlopen
