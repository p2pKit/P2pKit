"""Bounded private worker-return transport, NOT provider/runner acceptance.

One fixed packet carries exact capture bytes; stdout carries only its small ACK.
These codecs check supplied consistency. Only the original sender/receiver owns
file/return custody, and neither transport nor a hash supplies source admission.
The decoded type is deliberately NOT an in-process CapturedProvider.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
import hashlib
import json
import re

import hosted_cache_provider_lifecycle as lifecycle


PACKET_NAME = "worker-return.json"
PACKET_BYTES = 6 * 1024 * 1024
ACK_BYTES = 1024
FAILED_CAPTURE_EXIT = 65  # Known failed capture/transport, never step success.
INCOMPLETE_EXIT = 66
_LIMITS = {"command": 4096, "stdout": 1024 * 1024, "stderr": 1024 * 1024,
           "nativeRetirement": 2 * 1024 * 1024}
_PENDING = {"enclosingOwnerRetirement": "NOT_OBSERVED", "originalStepOutcome": "NOT_OBSERVED",
            "providerAcceptance": "NOT_ESTABLISHED"}
_KEYS = {"schema", "requestSha256", "role", "job", "outerId", "innerId", "kind", "phase",
         "exitCode", "observedNs", "closedResources", "captureScope", "outputs", *_LIMITS, *_PENDING}
_ACK_KEYS = {"schema", "requestSha256", "packetSha256", "packetBytes", "packetIdentity"}


class ProviderReturnError(RuntimeError):
    """Fixed reason only; packets, logs and original exceptions remain private."""


def require(value, reason):
    if not value:
        raise ProviderReturnError(reason)


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")


def _parse(raw, maximum):
    require(type(raw) is bytes and 0 < len(raw) <= maximum, "PROVIDER_RETURN_BYTE_BOUND")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "PROVIDER_RETURN_DUPLICATE_KEY")
            result[key] = value
        return result
    try:
        value = json.loads(raw.decode("ascii"), object_pairs_hook=unique,
                           parse_constant=lambda _: require(False, "PROVIDER_RETURN_JSON"))
    except (UnicodeError, ValueError, RecursionError):
        raise ProviderReturnError("PROVIDER_RETURN_JSON") from None
    require(type(value) is dict, "PROVIDER_RETURN_OBJECT")
    return value


def _context(request):
    # The actual original launcher validates the entire frame. The exact digest
    # binds its other fields too; this projection is not a second admission API.
    value = _parse(request, 16 * 1024)
    require(request == _json(value), "PROVIDER_RETURN_REQUEST_CANONICAL")
    require(value.get("role") in ("linux-x64", "windows-x64", "macos-arm64", "macos-x64") and
            value.get("phase") in ("save", "lookup"), "PROVIDER_RETURN_CONTEXT")
    require(all(type(value.get(key)) is str and re.fullmatch(r"[0-9a-f]{32}", value[key])
                for key in ("job", "outerId", "innerId")) and value["outerId"] != value["innerId"],
            "PROVIDER_RETURN_CONTEXT")
    for key in ("issuedNs", "workerCutoffNs"):
        require(type(value.get(key)) is str and re.fullmatch(r"0|[1-9][0-9]{0,19}", value[key]) and
                int(value[key]) < 2 ** 64, "PROVIDER_RETURN_CONTEXT")
    require(int(value["issuedNs"]) < int(value["workerCutoffNs"]), "PROVIDER_RETURN_CONTEXT")
    return value, hashlib.sha256(request).hexdigest()


def _file_identity(value, role):
    require(type(value) in (tuple, list) and len(value) == 2 and type(value[0]) is int and
            0 <= value[0] < 2 ** 64, "PROVIDER_RETURN_FILE_IDENTITY")
    require((type(value[1]) is str and re.fullmatch(r"[0-9a-f]{32}", value[1])) if role == "windows-x64" else
            (type(value[1]) is int and 0 < value[1] < 2 ** 64), "PROVIDER_RETURN_FILE_IDENTITY")
    return tuple(value)


def file_identity(info, role):
    """Stable native/POSIX identity only; pre-close Windows times are not final."""
    return _file_identity(info.identity if role == "windows-x64" else (info.device, info.inode), role)


@dataclass(frozen=True)
class Acknowledgement:
    request_sha256: str
    packet_sha256: str
    packet_bytes: int
    packet_identity: tuple


@dataclass(frozen=True, repr=False)
class TransportedProvider:
    kind: str
    phase: str
    exit_code: int | None
    command: bytes = field(repr=False)
    stdout: bytes = field(repr=False)
    stderr: bytes = field(repr=False)
    native_retirement: bytes = field(repr=False)
    outputs: tuple | None
    observed_ns: int
    closed_resources: tuple
    capture_scope: str
    request_sha256: str
    packet_sha256: str
    scope: str = "TRANSPORTED_PROVIDER_CAPTURE_ONLY_V1"
    enclosing_owner_retirement: str = "NOT_OBSERVED"
    original_step_outcome: str = "NOT_OBSERVED"
    provider_acceptance: str = "NOT_ESTABLISHED"


def _capture_fields(value, context):
    kind = value["kind"]
    require(kind in ("success", "failed") and value["phase"] == context["phase"], "PROVIDER_RETURN_CAPTURE_KIND")
    code = value["exitCode"]
    require((type(code) is int and -(2 ** 31) <= code < 2 ** 32) or (kind == "failed" and code is None),
            "PROVIDER_RETURN_EXIT_CODE")
    require(kind != "success" or code == 0, "PROVIDER_RETURN_SUCCESS_EXIT")
    require(type(value["observedNs"]) is str and re.fullmatch(r"0|[1-9][0-9]{0,19}", value["observedNs"]) and
            int(context["issuedNs"]) <= int(value["observedNs"]) < int(context["workerCutoffNs"]),
            "PROVIDER_RETURN_CAPTURE_TIME")
    names = lifecycle.ProviderCapture._NAMES
    expected = list(names if context["role"] != "windows-x64" else names[:-2])
    require(value["closedResources"] == expected and type(value["closedResources"]) is list,
            "PROVIDER_RETURN_CAPTURE_CLOSES")
    expected_scope = ("PROVIDER_CAPTURE_ONLY_PENDING_ENCLOSING_RETURN_V1" if kind == "success" else
                      "FAILED_PROVIDER_CAPTURE_ONLY_PENDING_ENCLOSING_RETURN_V1")
    require(value["captureScope"] == expected_scope and all(value[key] == expected for key, expected in _PENDING.items()),
            "PROVIDER_RETURN_PENDING_SCOPE")


def encode(capture, request):
    """Serialize a supplied immutable capture; its genuine origin is the caller's obligation."""
    require(type(capture) in (lifecycle.CapturedProvider, lifecycle.FailedProviderCapture), "PROVIDER_RETURN_CAPTURE_TYPE")
    context, digest = _context(request)
    success = type(capture) is lifecycle.CapturedProvider
    require(type(capture.observed_ns) is int and type(capture.closed_resources) is tuple and
            len(capture.closed_resources) <= len(lifecycle.ProviderCapture._NAMES), "PROVIDER_RETURN_CAPTURE_FIELDS")
    if success:
        require(type(capture.outputs) is tuple and len(capture.outputs) <= 3 and
                all(type(row) is tuple and len(row) == 2 and type(row[0]) is str and
                    row[0] in lifecycle.cache.RESTORE_OUTPUTS and type(row[1]) is str and
                    len(row[1]) <= 512 and all(32 <= ord(char) < 127 for char in row[1]) for row in capture.outputs),
                "PROVIDER_RETURN_CAPTURE_FIELDS")
    value = {"schema": "P2PKIT_PROVIDER_RETURN_V1", "requestSha256": digest,
        **{key: context[key] for key in ("role", "job", "outerId", "innerId")},
        "kind": "success" if success else "failed", "phase": capture.phase, "exitCode": capture.exit_code,
        "observedNs": str(capture.observed_ns), "closedResources": list(capture.closed_resources),
        "captureScope": capture.scope, "outputs": [list(row) for row in capture.outputs] if success else None,
        "enclosingOwnerRetirement": capture.enclosing_owner_retirement,
        "originalStepOutcome": capture.original_step_outcome, "providerAcceptance": capture.provider_acceptance}
    _capture_fields(value, context)
    raw_fields = (capture.command, capture.stdout, capture.stderr, capture.native_retirement)
    for (key, maximum), raw in zip(_LIMITS.items(), raw_fields):
        require(type(raw) is bytes and len(raw) <= maximum and (key != "nativeRetirement" or raw),
                "PROVIDER_RETURN_FIELD_BOUND")
        value[key] = base64.b64encode(raw).decode("ascii")
    raw = _json(value) + b"\n"
    require(len(raw) <= PACKET_BYTES, "PROVIDER_RETURN_BYTE_BOUND")
    return raw


def acknowledge(packet, identity, request):
    context, digest = _context(request)
    require(type(packet) is bytes and 0 < len(packet) <= PACKET_BYTES, "PROVIDER_RETURN_BYTE_BOUND")
    value = {"schema": "P2PKIT_PROVIDER_RETURN_ACK_V1", "requestSha256": digest,
             "packetSha256": hashlib.sha256(packet).hexdigest(), "packetBytes": len(packet),
             "packetIdentity": list(_file_identity(identity, context["role"]))}
    raw = _json(value) + b"\n"
    require(len(raw) <= ACK_BYTES, "PROVIDER_RETURN_ACK_BOUND")
    return raw


def read_ack(raw, request):
    context, digest = _context(request)
    value = _parse(raw, ACK_BYTES)
    require(set(value) == _ACK_KEYS and value["schema"] == "P2PKIT_PROVIDER_RETURN_ACK_V1" and
            raw == _json(value) + b"\n", "PROVIDER_RETURN_ACK_CANONICAL")
    require(value["requestSha256"] == digest and type(value["packetSha256"]) is str and
            re.fullmatch(r"[0-9a-f]{64}", value["packetSha256"]), "PROVIDER_RETURN_ACK_BINDING")
    require(type(value["packetBytes"]) is int and 0 < value["packetBytes"] <= PACKET_BYTES,
            "PROVIDER_RETURN_ACK_SIZE")
    return Acknowledgement(digest, value["packetSha256"], value["packetBytes"],
                           _file_identity(value["packetIdentity"], context["role"]))


def decode(packet, ack, request, worker_exit):
    """Transported observation only, and only for the exact completed worker exit contract."""
    context, digest = _context(request)
    require(type(ack) is Acknowledgement and ack.request_sha256 == digest and type(packet) is bytes and
            type(ack.packet_bytes) is int and 0 < len(packet) == ack.packet_bytes <= PACKET_BYTES and
            hashlib.sha256(packet).hexdigest() == ack.packet_sha256,
            "PROVIDER_RETURN_PACKET_BINDING")
    value = _parse(packet, PACKET_BYTES)
    require(set(value) == _KEYS and value["schema"] == "P2PKIT_PROVIDER_RETURN_V1" and
            value["requestSha256"] == digest and all(value[key] == context[key] for key in ("role", "job", "outerId", "innerId")) and
            packet == _json(value) + b"\n", "PROVIDER_RETURN_PACKET_CANONICAL")
    _capture_fields(value, context)
    require(type(worker_exit) is int and worker_exit == (0 if value["kind"] == "success" else FAILED_CAPTURE_EXIT),
            "PROVIDER_RETURN_WORKER_OUTCOME")
    decoded = {}
    for key, maximum in _LIMITS.items():
        text = value[key]
        require(type(text) is str and len(text) <= 4 * ((maximum + 2) // 3), "PROVIDER_RETURN_FIELD_BOUND")
        try:
            raw = base64.b64decode(text, validate=True)
        except (ValueError, UnicodeError):
            raise ProviderReturnError("PROVIDER_RETURN_BASE64") from None
        require(len(raw) <= maximum and (key != "nativeRetirement" or raw) and
                base64.b64encode(raw).decode("ascii") == text, "PROVIDER_RETURN_BASE64")
        decoded[key] = raw
    if value["kind"] == "success":
        outputs = lifecycle.cache.provider_command_outputs(decoded["command"], phase=value["phase"], role=context["role"])
        require(value["outputs"] == [list(row) for row in sorted(outputs.items())], "PROVIDER_RETURN_OUTPUTS_CHANGED")
        outputs = tuple(sorted(outputs.items()))
    else:
        require(value["outputs"] is None, "PROVIDER_RETURN_FAILED_OUTPUTS")
        outputs = None  # Failed bytes are never sent through the success parser/classifier.
    return TransportedProvider(value["kind"], value["phase"], value["exitCode"], decoded["command"], decoded["stdout"],
        decoded["stderr"], decoded["nativeRetirement"], outputs, int(value["observedNs"]), tuple(value["closedResources"]),
        value["captureScope"], digest, ack.packet_sha256)
