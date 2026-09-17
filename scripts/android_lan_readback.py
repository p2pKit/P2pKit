"""Bounded #372 readback *content* checks, never Android runtime admission.

The producer/loaded API37 semantics are not qualified. Both the supplied record
and the independently supplied expected binding are declarations, not authority.
Even matching true/true reads remain RECORDED_INPUT_ONLY / COMPAT_STATE_UNPROVEN.
There is deliberately no trusted/qualified switch, I/O, collector or CLI here.

A future ordinary-UID collector must observe one actual public AconfigPackage
instance, false then true defaults, and preserve original command/profile/APK
evidence. Equal serialized reader IDs do not prove object identity; equal values
do not prove valid storage, an atomic snapshot, generated getter/cache state or
permission enforcement. Do not call the hidden platform delegate or promote the
separate legacy android_compat_model. The old peer terminal stays unchanged.
"""

from dataclasses import dataclass, field
from enum import Enum
import json
import re
from typing import Optional


SCHEMA = "p2pkit-android-lan-readback/1"
MODE = "profile-readback"
APP_PACKAGE = "dev.p2pkit.sample.android"
READER_CLASS = "android.os.flagging.AconfigPackage"
FLAG_PACKAGE = "android.permission.flags"
FLAG_NAME = "access_local_network_permission_enabled"
STORAGE_ERROR = "android.os.flagging.AconfigStorageReadException"
MAX_RECORD_BYTES = 16 * 1024
LONG_MAX = (1 << 63) - 1
_CLASS_NAME = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)+")
_HEX_FIELDS = {
    "token": 32, "sourceCommit": 40, "sourceTree": 40,
    "appApkSha256": 64, "testApkSha256": 64, "profileSha256": 64, "installId": 32,
}
_BINDING_KEYS = set(_HEX_FIELDS) | {
    "packageName", "user", "uid", "pid", "processStartElapsedMillis", "installEpochMillis",
    "sdkInt", "targetSdk", "codename", "previewSdkInt", "buildDirty",
}


class Hold(str, Enum):
    INPUT_TYPE = "INPUT_TYPE"
    RECORD_LIMIT = "RECORD_LIMIT"
    JSON_SYNTAX = "JSON_SYNTAX"
    DUPLICATE_FIELD = "DUPLICATE_FIELD"
    NUMBER_FORMAT = "NUMBER_FORMAT"
    SCHEMA = "SCHEMA"
    EXPECTED_BINDING = "EXPECTED_BINDING"
    BINDING = "BINDING"
    BINDING_DRIFT = "BINDING_DRIFT"
    EVENT_ORDER = "EVENT_ORDER"
    READER_IDENTITY = "READER_IDENTITY"
    DEFAULT_ORDER = "DEFAULT_ORDER"
    CLOCK_RECORD = "CLOCK_RECORD"
    OUTCOME = "OUTCOME"
    ERROR_RECORD = "ERROR_RECORD"
    LOAD_ERROR = "LOAD_ERROR"
    READ_ERROR = "READ_ERROR"
    INCOMPLETE = "INCOMPLETE"
    LOOKUP_UNRESOLVED_OR_DRIFT = "LOOKUP_UNRESOLVED_OR_DRIFT"
    INCONSISTENT_OR_DRIFT = "INCONSISTENT_OR_DRIFT"


@dataclass(frozen=True)
class ReadbackContent:
    original: Optional[bytes] = field(repr=False)
    classification: str
    declared_value: Optional[bool]
    content_hold: Optional[Hold]
    evidence_level: str = field(default="RECORDED_INPUT_ONLY", init=False)
    runtime_state: str = field(default="COMPAT_STATE_UNPROVEN", init=False)
    qualification: str = field(default="HOLD_UNQUALIFIED_RUNTIME_SEMANTICS", init=False)
    permission_enforcement: str = field(default="NOT_PROVEN", init=False)
    same_instance_revocation: str = field(default="NOT_EXECUTED", init=False)


class _Invalid(ValueError):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason.value)


def _need(condition, reason):
    if not condition:
        raise _Invalid(reason)


def _keys(value, expected, reason=Hold.SCHEMA):
    _need(type(value) is dict and set(value) == set(expected), reason)


def _integer(value, minimum=0, maximum=LONG_MAX):
    return type(value) is int and minimum <= value <= maximum


def _hex(value, length):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{%d}" % length, value) is not None


def _binding(value, reason=Hold.BINDING):
    _keys(value, _BINDING_KEYS, reason)
    _need(all(_hex(value[key], size) for key, size in _HEX_FIELDS.items()), reason)
    _need(value["packageName"] == APP_PACKAGE and type(value["packageName"]) is str, reason)
    _need(_integer(value["user"], 0, 0) and _integer(value["uid"], 10000, 19999)
          and _integer(value["pid"], 1, (1 << 31) - 1), reason)
    _need(_integer(value["processStartElapsedMillis"]) and _integer(value["installEpochMillis"], 1), reason)
    _need(_integer(value["sdkInt"], 37, 37) and _integer(value["targetSdk"], 37, 37)
          and _integer(value["previewSdkInt"], 0, 0) and value["codename"] == "REL"
          and type(value["codename"]) is str and value["buildDirty"] is False, reason)


def _unique(pairs):
    result = {}
    for key, value in pairs:
        _need(key not in result, Hold.DUPLICATE_FIELD)
        result[key] = value
    return result


def _json_integer(value):
    _need(len(value.lstrip("-")) <= 19 and value != "-0", Hold.NUMBER_FORMAT)
    return int(value)


def _not_integer(_value):
    raise _Invalid(Hold.NUMBER_FORMAT)


def _stamp(value):
    _keys(value, ("epochMillis", "elapsedMillis"), Hold.CLOCK_RECORD)
    _need(_integer(value["epochMillis"], 1) and _integer(value["elapsedMillis"]), Hold.CLOCK_RECORD)
    return value["epochMillis"], value["elapsedMillis"]


def _error(outcome):
    _keys(outcome, ("kind", "errorType", "errorCode"), Hold.ERROR_RECORD)
    name, code = outcome["errorType"], outcome["errorCode"]
    _need(type(name) is str and len(name) <= 255 and _CLASS_NAME.fullmatch(name) is not None,
          Hold.ERROR_RECORD)
    # Codes 0..4 are the retained public surface, not clean-absence witnesses.
    # Other errors have no AconfigStorageReadException.getErrorCode() value.
    _need(_integer(code, 0, 4) if name == STORAGE_ERROR else code is None, Hold.ERROR_RECORD)


def validate_readback(original, expected_binding):
    """Check a declared, bounded profile-readback record against separate facts.

    Returns only content consistency. Neither argument authenticates the source,
    installed APKs/profile, ordinary UID, same Java instance or actual execution.
    Every return keeps qualification HOLD, including a matching true/true pair.
    Original bytes are retained by reference (also on failure), never truncated
    or emitted. The caller must retain them privately alongside original receipts.
    """
    raw = original if type(original) is bytes else None

    def held(reason):
        return ReadbackContent(raw, "CONTENT_HOLD", None, reason)

    if raw is None:
        return held(Hold.INPUT_TYPE)
    if len(raw) > MAX_RECORD_BYTES:
        return held(Hold.RECORD_LIMIT)
    try:
        _binding(expected_binding, Hold.EXPECTED_BINDING)
        record = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique,
                            parse_int=_json_integer, parse_float=_not_integer, parse_constant=_not_integer)
        _keys(record, ("schema", "mode", "binding", "readerClass", "flagPackage", "flagName", "events"))
        _need((record["schema"], record["mode"], record["readerClass"], record["flagPackage"], record["flagName"])
              == (SCHEMA, MODE, READER_CLASS, FLAG_PACKAGE, FLAG_NAME), Hold.SCHEMA)
        _binding(record["binding"])
        _need(record["binding"] == expected_binding, Hold.BINDING_DRIFT)
        events = record["events"]
        _need(type(events) is list and 1 <= len(events) <= 3, Hold.INCOMPLETE)
        reader_id, last_end, values = None, None, []
        for index, event in enumerate(events):
            fields = {"phase", "binding", "readerId", "start", "end", "outcome"}
            if index:
                fields.add("default")
            _keys(event, fields, Hold.EVENT_ORDER)
            _need(event["phase"] == ("load" if index == 0 else "read"), Hold.EVENT_ORDER)
            _binding(event["binding"])
            _need(event["binding"] == expected_binding, Hold.BINDING_DRIFT)
            start, end = _stamp(event["start"]), _stamp(event["end"])
            _need(start[0] >= expected_binding["installEpochMillis"]
                  and start[1] >= expected_binding["processStartElapsedMillis"]
                  and end[0] >= start[0] and end[1] >= start[1], Hold.CLOCK_RECORD)
            if last_end is not None:
                _need(start[0] >= last_end[0] and start[1] >= last_end[1], Hold.CLOCK_RECORD)
            last_end = end
            # Epoch and elapsed clocks are ordered separately, never compared
            # with each other or interpreted as a loaded-state atomicity proof.
            outcome = event["outcome"]
            _need(type(outcome) is dict and type(outcome.get("kind")) is str, Hold.OUTCOME)
            if index:
                _need(type(event["default"]) is bool and event["default"] is (index == 2), Hold.DEFAULT_ORDER)
                _need(_hex(event["readerId"], 32) and event["readerId"] == reader_id, Hold.READER_IDENTITY)
            if outcome["kind"] == "ERROR":
                _error(outcome)
                _need(index == len(events) - 1, Hold.EVENT_ORDER)
                if index == 0:
                    _need(event["readerId"] is None, Hold.READER_IDENTITY)
                return held(Hold.LOAD_ERROR if index == 0 else Hold.READ_ERROR)
            if index == 0:
                _keys(outcome, ("kind",), Hold.OUTCOME)
                _need(outcome["kind"] == "LOADED" and _hex(event["readerId"], 32), Hold.READER_IDENTITY)
                reader_id = event["readerId"]
            else:
                _keys(outcome, ("kind", "value"), Hold.OUTCOME)
                _need(outcome["kind"] == "RETURNED" and type(outcome["value"]) is bool, Hold.OUTCOME)
                values.append(outcome["value"])
        _need(len(events) == 3, Hold.INCOMPLETE)
        if values == [False, True]:
            return held(Hold.LOOKUP_UNRESOLVED_OR_DRIFT)
        if values == [True, False]:
            return held(Hold.INCONSISTENT_OR_DRIFT)
        value = values[0]
        return ReadbackContent(raw, "MATCHING_DECLARED_TRUE" if value else "MATCHING_DECLARED_FALSE", value, None)
    except _Invalid as error:
        return held(error.reason)
    except (ValueError, UnicodeError, RecursionError):
        return held(Hold.JSON_SYNTAX)
