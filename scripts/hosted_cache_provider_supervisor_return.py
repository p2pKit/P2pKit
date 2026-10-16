"""Fixed outer-provider ACK grammar; supplied consistency, NOT runner authority.

Only references cross stdout. Original native/log/worker-packet bytes stay in
the same private directory. Neither this codec nor a matching exit authenticates
the source, the enclosing Node/runner return, or a provider/cache result.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re

import hosted_cache_provider_return as worker


NATIVE_NAME = "supervisor-retirement.json"
NATIVE_BYTES = 2 * 1024 * 1024
ACK_BYTES = 4096
FAILED_EXIT = 65
INCOMPLETE_EXIT = 66
_LIMITS = {"native": NATIVE_BYTES, "stdout": 1024 * 1024, "stderr": 1024 * 1024,
           "packet": worker.PACKET_BYTES}
_REQUEST_KEYS = {"schema", "role", "frequency", "firstNs", "issuedNs", "hardEndNs", "workerCutoffNs",
                 "phase", "job", "outerId", "innerId", "directory", "directoryIdentity", "home", "homeIdentity",
                 "node", "toolPath", "plan"}
_PENDING = {"enclosingNodeReturn": "NOT_OBSERVED", "originalRunnerOutcome": "NOT_OBSERVED",
            "providerAcceptance": "NOT_ESTABLISHED"}
_ACK_KEYS = {"schema", "invocationSha256", "workerRequestSha256", "kind", "workerExitCode", "providerKind",
             "observedNs", "closedResources", "files", *_PENDING}


def require(value, reason):
    worker.require(value, reason)


def _context(request):
    value, digest = worker._context(request)
    require(set(value) == _REQUEST_KEYS and value["schema"] == "P2PKIT_PROVIDER_SUPERVISOR_REQUEST_V1",
            "SUPERVISOR_RETURN_REQUEST")
    for name in ("firstNs", "hardEndNs"):
        require(type(value[name]) is str and re.fullmatch(r"0|[1-9][0-9]{0,19}", value[name]) and
                int(value[name]) < 2 ** 64, "SUPERVISOR_RETURN_WINDOW")
    issued, first, cut, end = (int(value[key]) for key in ("issuedNs", "firstNs", "workerCutoffNs", "hardEndNs"))
    require(issued <= first < cut < end <= issued + 180 * 10 ** 9 and issued + 45 * 10 ** 9 < cut,
            "SUPERVISOR_RETURN_WINDOW")
    require(type(value["frequency"]) is int and 0 < value["frequency"] < 2 ** 64 and
            type(value["plan"]) is dict and all(type(value[name]) is str and value[name]
                for name in ("directory", "home", "node", "toolPath")), "SUPERVISOR_RETURN_REQUEST")
    # The original launcher owns full native/path/plan admission. These are
    # closed wire identities, not another authority or command-selection API.
    for name in ("directoryIdentity", "homeIdentity"):
        worker._file_identity(value[name], value["role"])
    require(value["directoryIdentity"] != value["homeIdentity"], "SUPERVISOR_RETURN_REQUEST")
    return value, digest


@dataclass(frozen=True)
class FileReference:
    size: int
    sha256: str
    identity: tuple


@dataclass(frozen=True)
class Acknowledgement:
    invocation_sha256: str
    worker_request_sha256: str
    kind: str
    worker_exit_code: int | None
    provider_kind: str | None
    observed_ns: int
    closed_resources: tuple
    files: tuple
    enclosing_node_return: str = "NOT_OBSERVED"
    original_runner_outcome: str = "NOT_OBSERVED"
    provider_acceptance: str = "NOT_ESTABLISHED"


def _reference(value, slot, role):
    require(type(value) is dict and set(value) == {"bytes", "sha256", "identity"}, "SUPERVISOR_RETURN_FILE")
    require(type(value["bytes"]) is int and 0 <= value["bytes"] <= _LIMITS[slot] and
            (slot in ("stdout", "stderr") or value["bytes"] > 0), "SUPERVISOR_RETURN_FILE_SIZE")
    require(type(value["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", value["sha256"]),
            "SUPERVISOR_RETURN_FILE_HASH")
    return FileReference(value["bytes"], value["sha256"], worker._file_identity(value["identity"], role))


def reference(raw, info, role, slot):
    """Reference actual caller-retained bytes/info, not an original file read."""
    require(slot in _LIMITS and type(raw) is bytes and len(raw) == info.size, "SUPERVISOR_RETURN_FILE_SIZE")
    return _reference({"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
        "identity": list(worker.file_identity(info, role))}, slot, role)


def _wire_reference(value, slot, role):
    require(type(value) is FileReference, "SUPERVISOR_RETURN_FILE_TYPE")
    result = {"bytes": value.size, "sha256": value.sha256, "identity": list(value.identity)}
    _reference(result, slot, role)
    return result


def acknowledge(request, worker_request, transcript, references):
    """The sender must supply its actual completed same-call transcript."""
    context, digest = _context(request)
    worker_context, worker_digest = worker._context(worker_request)
    require(all(worker_context.get(name) == value for name, value in context.items()
                if name not in ("schema", "firstNs")), "SUPERVISOR_RETURN_WORKER_REQUEST")
    require(type(references) is tuple and len(references) == len(_LIMITS), "SUPERVISOR_RETURN_FILES")
    files = {name: (None if name == "packet" and value is None else _wire_reference(value, name, context["role"]))
             for name, value in zip(_LIMITS, references)}
    require(type(transcript.failed) is bool and type(transcript.observed_ns) is int, "SUPERVISOR_RETURN_TRANSCRIPT")
    value = {"schema": "P2PKIT_PROVIDER_SUPERVISOR_ACK_V1", "invocationSha256": digest,
        "workerRequestSha256": worker_digest, "kind": "failed" if transcript.failed else "success",
        "workerExitCode": transcript.worker_exit_code,
        "providerKind": None if transcript.provider_return is None else transcript.provider_return.kind,
        "observedNs": str(transcript.observed_ns), "closedResources": list(transcript.closed_resources),
        "files": files, **_PENDING}
    raw = worker._json(value) + b"\n"
    read_ack(raw, request, FAILED_EXIT if transcript.failed else 0)
    return raw


def read_ack(raw, request, supervisor_exit):
    """Supplied ACK/exit consistency only; actual asynchronous close is external."""
    context, digest = _context(request)
    value = worker._parse(raw, ACK_BYTES)
    require(set(value) == _ACK_KEYS and value["schema"] == "P2PKIT_PROVIDER_SUPERVISOR_ACK_V1" and
            raw == worker._json(value) + b"\n", "SUPERVISOR_RETURN_ACK_CANONICAL")
    require(value["invocationSha256"] == digest and type(value["workerRequestSha256"]) is str and
            re.fullmatch(r"[0-9a-f]{64}", value["workerRequestSha256"]) and
            all(value[key] == expected for key, expected in _PENDING.items()), "SUPERVISOR_RETURN_ACK_BINDING")
    require(value["kind"] in ("success", "failed") and type(supervisor_exit) is int and
            supervisor_exit == (0 if value["kind"] == "success" else FAILED_EXIT), "SUPERVISOR_RETURN_EXIT")
    code, provider = value["workerExitCode"], value["providerKind"]
    require(code is None or (type(code) is int and -(2 ** 31) <= code < 2 ** 32), "SUPERVISOR_RETURN_WORKER_EXIT")
    require(provider in (None, "success", "failed") and
            (provider is None or code == (0 if provider == "success" else worker.FAILED_CAPTURE_EXIT)) and
            (value["kind"] == "failed" or (code == 0 and provider == "success")), "SUPERVISOR_RETURN_KIND")
    require(type(value["observedNs"]) is str and re.fullmatch(r"0|[1-9][0-9]{0,19}", value["observedNs"]) and
            int(context["firstNs"]) <= int(value["observedNs"]) < int(context["hardEndNs"]), "SUPERVISOR_RETURN_TIME")
    require(type(value["files"]) is dict and set(value["files"]) == set(_LIMITS), "SUPERVISOR_RETURN_FILES")
    files = tuple((name, None if name == "packet" and value["files"][name] is None else
                   _reference(value["files"][name], name, context["role"])) for name in _LIMITS)
    has_packet = dict(files)["packet"] is not None
    require(provider is None or has_packet, "SUPERVISOR_RETURN_PACKET_REQUIRED")
    closes = ["scope", "retirement-writer"]
    if context["role"] != "windows-x64":
        closes += ["stdout-reader", "stderr-reader"]
    if has_packet:
        closes += ["packet-reader"]
    closes += ["stderr", "stdout", "bundle", "capture_directory", "home", "directory"]
    require(type(value["closedResources"]) is list and value["closedResources"] == closes,
            "SUPERVISOR_RETURN_CLOSES")
    identities = [ref.identity for _, ref in files if ref is not None]
    require(len(set(identities)) == len(identities), "SUPERVISOR_RETURN_FILE_ALIAS")
    return Acknowledgement(digest, value["workerRequestSha256"], value["kind"], code, provider,
        int(value["observedNs"]), tuple(closes), files)
