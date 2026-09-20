"""Closed supplied service fields for the future fixed cache provider.

This is NOT environment acquisition, an authenticated runner bridge or a complete
launch environment. Returned values are sensitive in-memory inputs only: never
serialize, hash, print or route them through the Git-query/producer records.
"""
from __future__ import annotations

from ipaddress import IPv6Address
import re
from urllib.parse import urlsplit


SERVICE_FIELDS = frozenset({"ACTIONS_RUNTIME_TOKEN", "ACTIONS_RESULTS_URL", "ACTIONS_CACHE_SERVICE_V2"})
FIELD_LIMIT = 4096


class ProviderEnvironmentError(RuntimeError):
    """Fixed public-safe reason, never the supplied credential or endpoint."""


def require(value, reason):
    if not value:
        raise ProviderEnvironmentError(reason)


def runtime_service_fragment(fields):
    """Validate three explicit fields, preserving their original spelling.

    The future caller must authenticate the original runner/service source and
    GitHub.com admission, then construct a NEW closed native-owned environment.
    Shape/presence cannot prove that provenance. In the inspected runner source,
    URL/flag setters are conditional and do not clear preexisting values.
    """
    require(type(fields) is dict and all(type(name) is str for name in fields) and
            set(fields) == SERVICE_FIELDS, "CACHE_PROVIDER_RUNTIME_FIELDS")
    require(all(type(value) is str and 0 < len(value) <= FIELD_LIMIT and
                all(33 <= ord(char) < 127 for char in value) for value in fields.values()),
            "CACHE_PROVIDER_RUNTIME_VALUE")
    # Runner397b032c's bool.TrueString is exactly "True". The pinned supplier
    # treats even "false" as truthy; do not coerce, normalize or invent this flag.
    require(fields["ACTIONS_CACHE_SERVICE_V2"] == "True", "CACHE_PROVIDER_RUNTIME_V2")
    value = fields["ACTIONS_RESULTS_URL"]
    require(value.startswith("https://") and not any(char in value for char in '\\%?#"<>`{}|^'),
            "CACHE_PROVIDER_RUNTIME_URL")
    try:
        parsed = urlsplit(value)
        port = parsed.port
        authority = value[len("https://"):].split("/", 1)[0]
        # Do not depend on a particular Python patch level's bracket checks.
        # The fixed Node supplier uses WHATWG URLs, not RFC IPvFuture literals.
        ipv6 = authority.startswith("[")
        host_pattern = r"\[([0-9A-Fa-f:.]+)\]" if ipv6 else r"([A-Za-z0-9._~!$&'()*+,;=-]+)"
        match = re.fullmatch(host_pattern + r"(?::([1-9][0-9]{0,4}))?", authority)
        require(match is not None, "CACHE_PROVIDER_RUNTIME_URL")
        host, original_port = match.groups()
        if ipv6:
            IPv6Address(host)  # Validation only; never substitute its normalization.
        valid = (parsed.scheme == "https" and bool(parsed.hostname) and
                 parsed.username is None and parsed.password is None and
                 not parsed.query and not parsed.fragment and parsed.netloc == authority and
                 parsed.hostname == host.lower() and
                 port == (None if original_port is None else int(original_port)) and
                 (port is None or 0 < port <= 65535))
    except ValueError:
        # urllib diagnostics can contain the private endpoint. Do not chain it.
        raise ProviderEnvironmentError("CACHE_PROVIDER_RUNTIME_URL") from None
    require(valid, "CACHE_PROVIDER_RUNTIME_URL")
    # No endpoint allowlist, token authentication or redirect confinement is
    # established here. No ambient dictionary is copied or modified.
    return dict(fields)
