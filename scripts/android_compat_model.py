"""Pure candidate-source model, NOT Android runtime/compat admission (#372).

The pins below identify inspected sources, not an installed image or active
module. CompatChange.isEnabled/toString and PlatformCompat's ordinary-UID AND
are modeled; collection completeness, loaded-code equivalence, cache state,
the mandatory system flag and permission propagation are not. In particular,
RESTRICT_LOCAL_NETWORK is the disabled legacy developer opt-in, not mandatory
target37 ACCESS_LOCAL_NETWORK enforcement.

Only the REL/SDK37/preview0 classifier and declared primary-user application
UIDs 10000..19999 are in this initial model's scope. These are input restrictions,
not proof of live identity or complete package enumeration. Package names use a
bounded dotted-ASCII identifier subset. No I/O, controller or admission API is
provided. Every success and HOLD remains MODEL_ONLY / COMPAT_STATE_UNPROVEN.
"""

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Optional, Tuple


FRAMEWORKS_BASE_REVISION = "94b4c163b7dfe5ce3607f7bb8456f9573f7de57d"
CONNECTIVITY_REVISION = "347fbd34b368d19f0d87e908ea101eed3601a731"
ROW_SCHEMA = "CompatChange.toString/candidate-v1"
CANDIDATE_PROFILE_ID = ":".join((ROW_SCHEMA, FRAMEWORKS_BASE_REVISION, CONNECTIVITY_REVISION))
RESTRICT_LOCAL_NETWORK = 365139289
CHANGE_KIND = "LEGACY_DEVELOPER_OPT_IN"
MAX_ROW_BYTES = 16 * 1024
MAX_OVERRIDES = 128
MAX_UID_PACKAGES = 128
_INT_MAX = (1 << 31) - 1
_LONG_MAX = (1 << 63) - 1
_PACKAGE = re.compile(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+")
_DECIMAL = re.compile(r"-?(?:0|[1-9][0-9]*)")


class HoldReason(str, Enum):
    INPUT_TYPE = "INPUT_TYPE"
    ROW_LIMIT = "ROW_LIMIT"
    ROW_SYNTAX = "ROW_SYNTAX"
    UNKNOWN_FIELD = "UNKNOWN_FIELD"
    DUPLICATE_FIELD = "DUPLICATE_FIELD"
    FIELD_ORDER = "FIELD_ORDER"
    RAW_OVERRIDES_UNQUALIFIED = "RAW_OVERRIDES_UNQUALIFIED"
    OVERRIDE_LIMIT = "OVERRIDE_LIMIT"
    INVALID_OVERRIDE = "INVALID_OVERRIDE"
    DUPLICATE_OVERRIDE = "DUPLICATE_OVERRIDE"
    UNSUPPORTED_DEFINITION = "UNSUPPORTED_DEFINITION"
    UNSUPPORTED_PROFILE = "UNSUPPORTED_PROFILE"
    UNSUPPORTED_CLASSIFIER = "UNSUPPORTED_CLASSIFIER"
    UID_SCOPE = "UID_SCOPE"
    UID_FACTS = "UID_FACTS"
    UID_MEMBERSHIP = "UID_MEMBERSHIP"


@dataclass(frozen=True)
class EvaluatedOverride:
    package_name: str
    enabled: bool


@dataclass(frozen=True)
class CandidateRow:
    change_id: int
    name: Optional[str] = None
    enable_since_target_sdk: int = -1
    disabled: bool = False
    logging_only: bool = False
    no_logging: bool = False
    evaluated_overrides: Tuple[EvaluatedOverride, ...] = ()
    raw_overrides: Optional[str] = None
    overridable: bool = False


CANDIDATE_DEFINITION = CandidateRow(RESTRICT_LOCAL_NETWORK, "RESTRICT_LOCAL_NETWORK", disabled=True)


@dataclass(frozen=True)
class Classifier:
    codename: str
    sdk_int: int
    preview_sdk_int: int


@dataclass(frozen=True)
class PackageFacts:
    package_name: str
    uid: int
    user_id: int
    target_sdk: int


@dataclass(frozen=True)
class DeclaredUidFacts:
    uid: int
    user_id: int
    member_names: Tuple[str, ...]
    packages: Tuple[PackageFacts, ...]


@dataclass(frozen=True)
class _ModelOnlyResult:
    scope: str = field(default="CANDIDATE_SOURCE_MODEL", init=False)
    evidence_level: str = field(default="MODEL_ONLY", init=False)
    runtime_state: str = field(default="COMPAT_STATE_UNPROVEN", init=False)
    change_kind: str = field(default=CHANGE_KIND, init=False)
    mandatory_system_flag: str = field(default="UNKNOWN", init=False)
    permission_propagation: str = field(default="UNKNOWN", init=False)


@dataclass(frozen=True)
class RowResult(_ModelOnlyResult):
    # Bytes are retained verbatim even on oversize/malformed HOLD. Nonbytes -> None.
    original: Optional[bytes]
    # A syntactically parsed row may be diagnostic only; see hold_reason.
    row: Optional[CandidateRow]
    hold_reason: Optional[HoldReason]


@dataclass(frozen=True)
class ModelResult(_ModelOnlyResult):
    enabled: Optional[bool]
    declared_package_values: Tuple[Tuple[str, bool], ...]
    hold_reason: Optional[HoldReason]


def _integer(value: object, minimum: int, maximum: int) -> bool:
    return type(value) is int and minimum <= value <= maximum


def _package_name(value: object) -> bool:
    return type(value) is str and len(value) <= 255 and _PACKAGE.fullmatch(value) is not None


def _decimal(value: str, minimum: int, maximum: int) -> Optional[int]:
    if len(value) > 20 or _DECIMAL.fullmatch(value) is None or value == "-0":
        return None
    number = int(value)
    return number if minimum <= number <= maximum else None


def _row_hold(row: CandidateRow) -> Optional[HoldReason]:
    if type(row) is not CandidateRow:
        return HoldReason.INPUT_TYPE
    if row.raw_overrides is not None:
        return HoldReason.RAW_OVERRIDES_UNQUALIFIED
    flags = (row.disabled, row.logging_only, row.no_logging, row.overridable)
    if (not _integer(row.change_id, -_LONG_MAX - 1, _LONG_MAX)
            or not _integer(row.enable_since_target_sdk, -1, _INT_MAX)
            or any(type(flag) is not bool for flag in flags)
            or type(row.name) is not str
            or (row.change_id, row.name, row.enable_since_target_sdk, *flags)
            != (RESTRICT_LOCAL_NETWORK, "RESTRICT_LOCAL_NETWORK", -1, True, False, False, False)):
        return HoldReason.UNSUPPORTED_DEFINITION
    if type(row.evaluated_overrides) is not tuple:
        return HoldReason.INVALID_OVERRIDE
    if len(row.evaluated_overrides) > MAX_OVERRIDES:
        return HoldReason.OVERRIDE_LIMIT
    seen = set()
    for override in row.evaluated_overrides:
        if (type(override) is not EvaluatedOverride or not _package_name(override.package_name)
                or type(override.enabled) is not bool):
            return HoldReason.INVALID_OVERRIDE
        if override.package_name in seen:
            return HoldReason.DUPLICATE_OVERRIDE
        seen.add(override.package_name)
    return None


def parse_candidate_row(original: bytes) -> RowResult:
    """Parse one bounded candidate row, never a complete/atomic live dump.

    One optional final LF belongs to the retained bytes, not a completeness
    certificate. RawOverride serialization is unqualified: any rawOverrides
    field is HOLD, with its original bytes preserved, and is never evaluated.
    """
    if type(original) is not bytes:
        return RowResult(None, None, HoldReason.INPUT_TYPE)

    def hold(reason: HoldReason) -> RowResult:
        return RowResult(original, None, reason)

    if len(original) > MAX_ROW_BYTES:
        return hold(HoldReason.ROW_LIMIT)
    body = original[:-1] if original.endswith(b"\n") else original
    if any(character < 32 or character > 126 for character in body):
        return hold(HoldReason.ROW_SYNTAX)
    line = body.decode("ascii")
    if not line.startswith("ChangeId(") or not line.endswith(")"):
        return hold(HoldReason.ROW_SYNTAX)
    parts = line[9:-1].split("; ")
    change_id = _decimal(parts[0], -_LONG_MAX - 1, _LONG_MAX)
    if change_id is None:
        return hold(HoldReason.ROW_SYNTAX)
    order = ("name", "enableSinceTargetSdk", "disabled", "loggingOnly", "noLogging",
             "packageOverrides", "rawOverrides", "overridable")
    fields = {}
    previous = -1
    for part in parts[1:]:
        key, separator, value = part.partition("=")
        if key not in order:
            return hold(HoldReason.UNKNOWN_FIELD)
        if key in fields:
            return hold(HoldReason.DUPLICATE_FIELD)
        position = order.index(key)
        if position <= previous:
            return hold(HoldReason.FIELD_ORDER)
        previous = position
        if key == "rawOverrides":
            return hold(HoldReason.RAW_OVERRIDES_UNQUALIFIED)
        if key in ("disabled", "loggingOnly", "noLogging", "overridable"):
            if separator:
                return hold(HoldReason.ROW_SYNTAX)
            fields[key] = True
        elif not separator or not value:
            return hold(HoldReason.ROW_SYNTAX)
        elif key == "enableSinceTargetSdk":
            threshold = _decimal(value, 0, _INT_MAX)
            # The -1 sentinel is omitted by toString(), never printed explicitly.
            if threshold is None:
                return hold(HoldReason.ROW_SYNTAX)
            fields[key] = threshold
        elif key == "packageOverrides":
            if not value.startswith("{") or not value.endswith("}") or value == "{}":
                return hold(HoldReason.ROW_SYNTAX)
            entries = value[1:-1].split(", ")
            if len(entries) > MAX_OVERRIDES:
                return hold(HoldReason.OVERRIDE_LIMIT)
            overrides = []
            names = set()
            for entry in entries:
                name, equals, enabled = entry.partition("=")
                if not _package_name(name) or equals != "=" or enabled not in ("true", "false"):
                    return hold(HoldReason.INVALID_OVERRIDE)
                if name in names:
                    return hold(HoldReason.DUPLICATE_OVERRIDE)
                names.add(name)
                overrides.append(EvaluatedOverride(name, enabled == "true"))
            fields[key] = tuple(overrides)
        else:
            fields[key] = value
    row = CandidateRow(change_id, fields.get("name"), fields.get("enableSinceTargetSdk", -1),
                       fields.get("disabled", False), fields.get("loggingOnly", False),
                       fields.get("noLogging", False), fields.get("packageOverrides", ()),
                       overridable=fields.get("overridable", False))
    return RowResult(original, row, _row_hold(row))


def _uid_hold(facts: DeclaredUidFacts) -> Optional[HoldReason]:
    if type(facts) is not DeclaredUidFacts:
        return HoldReason.UID_FACTS
    # A deliberately narrow scope, not a claim that supplied identities are live.
    if not _integer(facts.uid, 10000, 19999) or not _integer(facts.user_id, 0, 0):
        return HoldReason.UID_SCOPE
    if (type(facts.member_names) is not tuple or type(facts.packages) is not tuple
            or not 1 <= len(facts.member_names) <= MAX_UID_PACKAGES
            or not 1 <= len(facts.packages) <= MAX_UID_PACKAGES):
        return HoldReason.UID_FACTS
    names = set()
    for name in facts.member_names:
        if not _package_name(name) or name in names:
            return HoldReason.UID_MEMBERSHIP
        names.add(name)
    supplied = set()
    for package in facts.packages:
        if (type(package) is not PackageFacts or not _package_name(package.package_name)
                or not _integer(package.uid, 10000, 19999)
                or not _integer(package.user_id, 0, 0)
                or not _integer(package.target_sdk, 1, _INT_MAX)
                or package.uid != facts.uid or package.user_id != facts.user_id):
            return HoldReason.UID_FACTS
        if package.package_name in supplied:
            return HoldReason.UID_MEMBERSHIP
        supplied.add(package.package_name)
    return None if supplied == names else HoldReason.UID_MEMBERSHIP


def _enabled_for_package(row: CandidateRow, package: PackageFacts, platform_target: int) -> bool:
    """Arithmetic kernel for validated inputs; synthetic tests may exercise thresholds.

    The public resolver rejects synthetic definitions, regardless of this result.
    This mirrors candidate CompatChange.isEnabled, not permission enforcement.
    """
    for override in row.evaluated_overrides:
        if override.package_name == package.package_name:
            return override.enabled
    if row.disabled:
        return False
    if row.enable_since_target_sdk != -1:
        return min(package.target_sdk, platform_target) >= row.enable_since_target_sdk
    return True


def resolve_candidate_uid(row: CandidateRow, declared_uid_facts: DeclaredUidFacts,
                          classifier: Classifier, profile_id: str) -> ModelResult:
    """Resolve declared inputs only; there is intentionally no trusted/live switch.

    Revalidate even manually constructed rows. Exact unique declared membership
    proves input consistency only, not PackageManager enumeration or cache state.
    Missing identities HOLD instead of inheriting the platform fallback default.
    """
    def hold(reason: HoldReason) -> ModelResult:
        return ModelResult(None, (), reason)

    if type(profile_id) is not str or profile_id != CANDIDATE_PROFILE_ID:
        return hold(HoldReason.UNSUPPORTED_PROFILE)
    reason = _row_hold(row)
    if reason is not None:
        return hold(reason)
    if (type(classifier) is not Classifier or type(classifier.codename) is not str
            or classifier.codename != "REL" or not _integer(classifier.sdk_int, 37, 37)
            or not _integer(classifier.preview_sdk_int, 0, 0)):
        return hold(HoldReason.UNSUPPORTED_CLASSIFIER)
    reason = _uid_hold(declared_uid_facts)
    if reason is not None:
        return hold(reason)
    values = tuple(sorted((package.package_name, _enabled_for_package(row, package, classifier.sdk_int))
                          for package in declared_uid_facts.packages))
    return ModelResult(all(enabled for _, enabled in values), values, None)
