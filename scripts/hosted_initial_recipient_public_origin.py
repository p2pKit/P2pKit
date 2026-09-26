"""Distinct public-provider HTTP contract, not a private-reader fallback.

Only the fixed initial-recipient provider acquisition may use these checks.
All endpoint data remain original bytes; public cache metadata is never changed
into private metadata. The existing private freshness function is unchanged.
This module supplies no native owner, current authority or provider admission.
"""
from __future__ import annotations

import os
import re

import hosted_full_job_budget as wire
import hosted_initial_recipient_stages as stages


RESPONSE_SCOPE = "PUBLIC_INITIAL_RECIPIENT_PROVIDER_SERVICE_RESPONSE_V1"
SITES = ("provider-save/native-prepare/begin", "provider-save/native-prepare/final",
         "provider-probe/native-prepare/begin", "provider-probe/native-prepare/final")
CREDENTIAL_NAMES = (wire.TOKEN_ENV, "GH_TOKEN", "GITHUB_TOKEN", "ACTIONS_RUNTIME_TOKEN",
                    "ACTIONS_RESULTS_URL", "ACTIONS_CACHE_SERVICE_V2")
API = "/repos/" + stages.identity.REPOSITORY


def require(value, code):
    wire.require(value, "INITIAL_PUBLIC_PROVIDER_" + code)


def credential_free():
    """Check this actual process; a supplied dictionary is not a boundary."""
    require(not any(name in os.environ for name in CREDENTIAL_NAMES), "CREDENTIAL_BOUNDARY")


def request_count(site):
    """Outstanding GETs in this original provider phase, not a new budget.

    Begin owes its own eight requests AND the final acquisition's eight. Final
    owes only its eight. The enclosing native owner must authenticate site/order;
    this closed spelling is not itself an original capability or reservation.
    """
    require(type(site) is str and site in SITES, "FIXED_SITE")
    return 16 if site.endswith("/begin") else 8


def endpoint(path):
    """The eight fixed endpoint kinds; no alternate origin/query/branch path."""
    require(type(path) is str, "FIXED_ENDPOINT")
    environment = API + "/environments/" + stages.ENVIRONMENT
    fixed = (environment, environment + "/deployment-branch-policies?per_page=100&page=1",
             API + "/git/ref/heads/main", API + "/git/ref/heads/" + stages.SOURCE_REF.removeprefix("refs/heads/"))
    positive = r"[1-9][0-9]{0,19}"
    run = re.escape(API + "/actions/runs/") + positive
    require(path in fixed or re.fullmatch(run + r"/attempts/" + positive +
        r"(?:/jobs\?per_page=100&page=1)?", path) is not None or
        re.fullmatch(run + r"/approvals", path) is not None or
        re.fullmatch(re.escape(API + "/issues/comments/") + positive, path) is not None, "FIXED_ENDPOINT")


def freshness(fields):
    """Same conservative60s service model, distinctly PUBLIC cache policy.

    Public cacheability is not proof of an instantaneous or uncached origin.
    Keep the original Age/intermediary/date checks AND the whole60s allowance.
    Do not project these fields through the private parser with a fake header.
    """
    require(type(fields) is dict, "HTTP_FIELDS")
    require(fields.get("content-type", "").lower() in ("application/json", "application/json; charset=utf-8") and
            fields.get("content-encoding", "identity").lower() == "identity" and
            fields.get("x-github-api-version-selected") == "2022-11-28", "HTTP_TYPE")
    require(type(fields.get("x-github-request-id")) is str and
            re.fullmatch(r"[A-Za-z0-9:-]{8,128}", fields["x-github-request-id"]), "REQUEST_ID")
    require(fields.get("age") in (None, "0") and not any(key in fields for key in
            ("warning", "via", "location", "content-range", "retry-after")) and
            fields.get("x-cache", "MISS").upper() in ("MISS", "BYPASS"), "STALE_OR_INTERMEDIARY")
    cache = {}
    for item in fields.get("cache-control", "").lower().split(","):
        name, equals, value = item.strip().partition("=")
        require(name not in cache and name in {"public", "max-age", "s-maxage"}, "CACHE_POLICY")
        require((name == "public" and not equals) or
                (name != "public" and equals and value == "60"), "CACHE_POLICY")
        cache[name] = value
    require(set(cache) == {"public", "max-age", "s-maxage"} and wire.CACHE_SECONDS == 60, "CACHE_POLICY")
    return wire.http_epoch(fields.get("date"))


def remaining_requests(fields, required):
    """Fail early on known insufficient shared-IP quota; never reserve/renew it.

    Absence provides no quota evidence. A present value must be unambiguous;
    even a sufficient value cannot rule out competing callers before the next
    request. Actual HTTP status/freshness/close checks remain mandatory.
    """
    require(type(required) is int and 0 <= required < 16, "REMAINING_REQUEST_COUNT")
    value = fields.get("x-ratelimit-remaining")
    if value is None:
        return None
    require(type(value) is str and re.fullmatch(r"0|[1-9][0-9]{0,19}", value), "QUOTA_METADATA")
    count = int(value)
    require(count >= required, "INSUFFICIENT_QUOTA")
    return count
