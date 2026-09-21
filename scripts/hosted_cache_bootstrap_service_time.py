"""Pure bootstrap service-time basis, NOT a job budget or native start reading.

Supplied original responses cannot authenticate themselves. The dormant caller
must retain/rederive this record inside its actual original-chain custody. This
helper neither reads a clock nor admits a duration, deadline, owner or producer.
The conservative translation depends on the existing service-clock assumptions;
it does not qualify HTTP Date correctness, cross-boot reuse or suspend behavior.
"""
from __future__ import annotations

import hosted_cache_bootstrap_origin as origin


SCOPE = "BOOTSTRAP_SERVICE_TIME_BASIS_V1"


class ServiceTimeError(ValueError):
    """Finite source-owned reason, not a private response/path diagnostic."""


def require(value, reason):
    if not value:
        raise ServiceTimeError(reason)


def integer(value):
    require(type(value) is int and 0 <= value <= origin.clocks.UINT64, "BOOTSTRAP_SERVICE_TIME_INTEGER")
    return value


def policy():
    # Do not call ordinary wire.policy(): it selects FULL/Desktop job budgets.
    # Age:0, absent Age and max-age=0 do not reduce the fixed service-cache charge.
    return {"scope": "SERVICE_DATE_TRANSLATION_NOT_NATIVE_START_OR_JOB_ALLOCATION",
            "anchor": "ORIGINAL_JOBS_REQUEST_STARTED_NS", "dateQuantizationSeconds": 1,
            "maximumServiceCacheSeconds": origin.wire.CACHE_SECONDS,
            "clockMarginSeconds": origin.wire.CLOCK_MARGIN_SECONDS}


def basis_arithmetic(jobs_start_ns, job_epoch, service_date):
    """Integer translation only; supplied timestamps establish no provenance.

    Both identity paths use these fixed charges. There is no clock read,
    duration/authority override or admission of the resulting basis.
    """
    jobs_start, job_epoch, service_date = (integer(value) for value in
                                         (jobs_start_ns, job_epoch, service_date))
    age = integer(service_date - job_epoch)
    charges = policy()
    seconds = integer(age + charges["dateQuantizationSeconds"] +
                      charges["maximumServiceCacheSeconds"] + charges["clockMarginSeconds"])
    charged_ns = integer(seconds * origin.NS)
    return {"jobsRequestStartedNs": jobs_start, "jobStartedEpochSeconds": job_epoch,
            "serviceAgeSeconds": age, "chargedAgeNs": charged_ns,
            "jobStartBasisNs": integer(jobs_start - charged_ns)}


def derive(admitted, originals, invocation, clock, runner_name):
    """Derive from the exact two-GET bytes, never an accepted-looking summary.

    The jobs request START precedes the service Date observation. Subtracting
    its complete charged age is conservative under the existing clock policy;
    using response finish, retention or a later clock would renew that basis.
    Integer overflow/underflow refuses instead of clamping to a different epoch.
    Zero is representable and is not itself an observed native job start.
    """
    origin.clocks.validate_identity(clock)
    require(type(originals) is dict and set(originals) == {"attempt", "jobs"} and
            all(type(raw) is bytes for raw in originals.values()), "BOOTSTRAP_SERVICE_TIME_ORIGINALS")
    # Freeze these immutable byte references before parsing and hashing them.
    responses = dict(originals)
    service = origin.service_identity(admitted, responses, invocation, clock, runner_name)
    record = origin.admitted_value(admitted)
    arithmetic = basis_arithmetic(origin.parse(responses["jobs"])["startedNs"],
        origin.wire.utc_epoch(service["jobStartedAt"]), service["originDateEpochSeconds"])
    return {"schema": 1, "scope": SCOPE, "profile": origin.bootstrap.PROFILE,
            "selection": record["selection"], "cacheCohort": record["cacheCohort"],
            "source": record["source"], "github": record["github"],
            "admissionSha256": origin.digest(admitted.record), "clock": origin.clock_value(clock),
            "invocation": invocation, "service": service, "policy": policy(), **arithmetic,
            "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}


def validate_basis(raw, admitted, originals, invocation, clock, runner_name):
    """Rederive a closed retained record, not provenance or budget authority.

    Comparing the actual canonical bytes also refuses bool/int substitutions,
    extra authority fields and reserialization. Changed response bytes require
    a different basis; they cannot validate an earlier retained one.
    """
    expected = derive(admitted, originals, invocation, clock, runner_name)
    require(type(raw) is bytes and raw == origin.encoded(expected), "BOOTSTRAP_SERVICE_TIME_BASIS_CHANGED")
    return expected
