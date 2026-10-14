"""Pure pre-executor environment admission for the two complete Apple CI commands.

This is not a launcher, a native permission grant or an ownership context. Call
it BEFORE allocating/overlaying the maintained executor's fresh state, Gradle
home and inherited capabilities. Never apply it to an already-owned child: that
would strip or reject its real supervisor context. Returned values stay private.
"""
from __future__ import annotations

import re

from rpc_apple_ci_admission import PROFILES, absolute_path, require


SCOPE = "ORDINARY_CI_APPLE_ENVIRONMENT_NOT_NATIVE_OR_RELEASE_QUALIFICATION"
TRACKING_KEY = "RUNNER_TRACKING_ID"
PATH_KEYS = frozenset((
    "HOME", "TMPDIR", "JAVA_HOME", "P2PKIT_AUDIT_JDK21", "ANDROID_HOME", "ANDROID_SDK_ROOT",
    "DEVELOPER_DIR", "RUNNER_TEMP", "RUNNER_TOOL_CACHE", "AGENT_TOOLSDIRECTORY", "GITHUB_WORKSPACE",
))
LABEL_KEYS = frozenset((
    "USER", "LOGNAME", "LANG", "LC_ALL", "LC_CTYPE", "LC_COLLATE", "LC_MESSAGES", "LC_NUMERIC", "TZ",
    "CI", "GITHUB_ACTIONS", "GITHUB_REPOSITORY", "GITHUB_SERVER_URL", "GITHUB_API_URL", "GITHUB_REF",
    "GITHUB_SHA", "GITHUB_EVENT_NAME", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_JOB",
    "GITHUB_WORKFLOW_REF", "GITHUB_WORKFLOW_SHA", "RUNNER_ENVIRONMENT", "RUNNER_OS", "RUNNER_ARCH", "RUNNER_NAME",
))
REQUIRED_KEYS = frozenset(("PATH", "HOME", "TMPDIR", "USER", "LOGNAME", "JAVA_HOME", TRACKING_KEY))
CONSUMER_DEFAULTS = {
    "P2PKIT_CONSUMER_PROFILE": "complete",
    "P2PKIT_KEEP_CONSUMER_ARTIFACTS": "0",
    "P2PKIT_CONSUMER_AUDIT_METADATA": "0",
}
# These options affect the checked-in Bash wrapper, its Python subprocesses,
# JVM launch, Gradle project properties or the actual platform/native tools.
# Refuse nonempty values rather than silently erase a requested different run.
FORBIDDEN_KEYS = frozenset((
    "P2PKIT_CONSUMER_REPOSITORY_URL", "P2PKIT_CONSUMER_WORK_DIR", "P2PKIT_GRADLE_EXECUTOR",
    "P2PKIT_JMDNS_FIXTURE_IPV4", "GRADLE_USER_HOME", "JAVA_OPTS", "GRADLE_OPTS", "JAVA_TOOL_OPTIONS",
    "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS", "JDK_JAVAC_OPTIONS", "CLASSPATH", "BASH_ENV", "ENV", "SHELLOPTS",
    "BASHOPTS", "CDPATH", "GLOBIGNORE", "IFS", "PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "PYTHONINSPECT",
    "PYTHONUSERBASE", "PYTHONBREAKPOINT", "LD_PRELOAD", "LD_LIBRARY_PATH", "SDKROOT", "TOOLCHAINS",
    "SWIFT_EXEC", "CC", "CXX", "LD", "MACOSX_DEPLOYMENT_TARGET", "IPHONEOS_DEPLOYMENT_TARGET",
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "all_proxy", "no_proxy",
    "RPC_QUALIFY_REQUESTED", "RPC_ADMISSION_ONLY", "RPC_QUALIFICATION_PARENT", "RPC_INTEL_INVESTIGATION",
    "RPC_APPLE_LANE", "RPC_APPLE_AUDIT_CONTEXT", "RPC_APPLE_SSH_CONTEXT", "RPC_APPLE_LAUNCHD_CONTEXT",
    "RPC_APPLE_TERMINAL_CONTEXT", "RPC_APPLE_BONJOUR_ADVERTISING",
))
FORBIDDEN_PREFIXES = ("BASH_FUNC_", "DYLD_", "ORG_GRADLE_PROJECT_", "SIMCTL_CHILD_")


def scalar(value: object) -> bool:
    return type(value) is str and bool(value) and len(value) <= 16384 and not any(
        ord(character) < 32 or ord(character) == 127 for character in value)


def path(value: str) -> None:
    # Setup actions and TMPDIR may supply one trailing slash. Preserve it exactly;
    # lexical admission cannot establish physical location, symlinks or ownership.
    absolute_path(value[:-1] if value.endswith("/") else value, "environment path")


def admit_environment(profile: str, ambient: dict, *, expected_tracking_id: str) -> dict:
    """Return a private pre-executor projection without executing or inspecting OS state.

    The caller independently retains the actual runner cookie; equality is not
    authentication and does not prove propagation into any process. PATH entries
    are preserved (including installed XcodeGen/tool directories), never replaced
    by a system-only fallback. Actual tool provenance, startup/init files, caches,
    SDK/JDK compatibility, source/run admission and ownership remain external.

    Current ownership_environment rejects a conflicting GRADLE_USER_HOME. Hence
    this PRE-allocation function refuses an ambient one; the runtime caller must
    resolve setup-gradle versus the isolated-home contract explicitly, not clear
    it silently. A freshly allocated executor context is applied only afterward.
    """
    require(type(profile) is str and profile in PROFILES, "Unknown complete environment profile")
    require(type(ambient) is dict and len(ambient) <= 2048 and all(
        type(key) is str and key and "=" not in key and "\0" not in key and
        type(value) is str and "\0" not in value for key, value in ambient.items()),
        "Invalid environment mapping")
    # The pinned Actions ScriptHandler selects its Node wrapper on key presence,
    # including an empty value. Dropping it would silently change launch context.
    require("DYLD_INSERT_LIBRARIES" not in ambient, "Wrapper-affecting environment presence refused")
    require(scalar(expected_tracking_id) and
            re.fullmatch(r"[A-Za-z0-9_.-]{1,512}", expected_tracking_id) is not None,
            "Invalid independently observed tracking value")
    require(ambient.get(TRACKING_KEY) == expected_tracking_id, "Runner tracking value absent or changed")
    require(all(scalar(ambient.get(key)) for key in REQUIRED_KEYS), "Required build environment missing or invalid")
    require(any(ambient.get(key) for key in ("ANDROID_HOME", "ANDROID_SDK_ROOT")),
            "Explicit Android SDK environment required")
    for key, value in ambient.items():
        if not value:
            continue
        if key in CONSUMER_DEFAULTS:
            require(value == CONSUMER_DEFAULTS[key], "Complete source-local consumer policy differs")
        else:
            audit_override = key.startswith("P2PKIT_AUDIT_") and key != "P2PKIT_AUDIT_JDK21"
            consumer_override = key.startswith("P2PKIT_CONSUMER_")
            require(not (key in FORBIDDEN_KEYS or key.startswith(FORBIDDEN_PREFIXES) or
                         audit_override or consumer_override), "Ambient execution override refused")
    result = {}
    for key in PATH_KEYS | LABEL_KEYS:
        value = ambient.get(key)
        if value:
            require(scalar(value), "Invalid preserved environment value")
            if key in PATH_KEYS:
                path(value)
            result[key] = value
    entries = ambient["PATH"].split(":")
    require(0 < len(entries) <= 128 and all(entries), "Invalid executable search path")
    for entry in entries:
        path(entry)
    result["PATH"] = ambient["PATH"]
    result[TRACKING_KEY] = ambient[TRACKING_KEY]
    for key in ("PYTHONDONTWRITEBYTECODE", "PYTHONUNBUFFERED"):
        require(ambient.get(key, "") in ("", "1"), "Python execution policy differs")
        result[key] = "1"
    if profile == "consumers-complete":
        result.update(CONSUMER_DEFAULTS)
    return {"scope": SCOPE, "profile": profile, "environment": result,
            "trackingValueMatched": True, "nativeExecutionAuthorized": False, "cleanupVerified": False}
