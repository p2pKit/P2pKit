"""Narrow initialization inputs/readback, not an executor or admission.

Installed-tool paths are inspected, never invoked or downloaded. Context and
policy checks are independent counterparts of the canonical initializer; they
cannot prove its original launch/return, native retirement or enclosing clocks.
Only the separate same-call parent may supply those facts from live ownership.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import re

import hosted_cache_bootstrap_producer as producer
import hosted_initial_recipient_bootstrap_identity as initial_identity


def require(value, reason):
    producer.require(value, reason)


def _stamp(path):
    info = path.stat()
    return (str(path), info.st_dev, info.st_ino, info.st_mode, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns, getattr(info, "st_file_attributes", 0))


def _installed():
    """Two explicit installed homes, not JDK version/runtime qualification."""
    rows = []
    for name in ("JAVA_HOME", "P2PKIT_AUDIT_JDK21"):
        value = os.environ.get(name)
        require(type(value) is str and 0 < len(value) <= 4096 and
                not any(ord(char) < 32 or ord(char) == 127 or char == "," for char in value) and
                Path(value).is_absolute(), "BOOTSTRAP_INIT_EXPLICIT_JDKS")
        home = Path(value).resolve(strict=True)
        require(home.is_dir(), "BOOTSTRAP_INIT_INSTALLED_JDK")
        binaries = tuple((home / "bin" / (binary + (".exe" if os.name == "nt" else ""))).resolve(strict=True)
                         for binary in ("java", "javac"))
        require(all(path.is_file() and (os.name == "nt" or os.access(path, os.X_OK)) for path in binaries),
                "BOOTSTRAP_INIT_INSTALLED_JDK")
        # Canonical setup-java aliases are allowed at the supplied home. Retain
        # that original text AND the resolved installation/binary identities.
        rows.append((name, value, str(home), tuple(_stamp(path) for path in (home, *binaries))))
    return tuple(rows)


@dataclass(frozen=True)
class InstalledToolchains:
    originals: tuple

    def checked(self):
        require(type(self) is InstalledToolchains and self.originals == _installed(),
                "BOOTSTRAP_INIT_JDK_CHANGED")
        return self

    def environment(self):
        self.checked()
        return {name: home for name, _supplied, home, _identities in self.originals}

    def homes(self):
        self.checked()
        return tuple(dict.fromkeys(home for _name, _supplied, home, _identities in self.originals))


def installed_toolchains():
    result = InstalledToolchains(_installed())
    return result.checked()


def properties(homes):
    """Exact Java-Properties encoding, with auto-detection/download disabled."""
    require(type(homes) is tuple and 1 <= len(homes) <= 2 and len(set(homes)) == len(homes) and
            all(type(home) is str and 0 < len(home) <= 4096 for home in homes), "BOOTSTRAP_INIT_JDK_PATHS")
    escaped = []
    for home in homes:
        require(not any(char in home for char in ("\0", "\r", "\n", ",")), "BOOTSTRAP_INIT_JDK_PATHS")
        pieces = []
        for char in home.replace("\\", "/"):
            if char in " :=#!":
                pieces.append("\\" + char)
            elif not 0x20 <= ord(char) <= 0x7e:
                raw = char.encode("utf-16-be")
                pieces.extend("\\u" + raw[index:index + 2].hex() for index in range(0, len(raw), 2))
            else:
                pieces.append(char)
        escaped.append("".join(pieces))
    return ("\n".join((
        "org.gradle.jvmargs=" + producer.JVM_ARGUMENTS, "org.gradle.workers.max=2", "org.gradle.parallel=false",
        "org.gradle.caching=false", "org.gradle.configuration-cache=false", "org.gradle.daemon=false",
        "kotlin.compiler.execution.strategy=in-process", "org.gradle.java.installations.auto-download=false",
        "org.gradle.java.installations.auto-detect=false", "org.gradle.java.installations.paths=" + ",".join(escaped),
    )) + "\n").encode("utf-8")


def stdout_path(state, role):
    """Closed ASCII path contract, independent of redirected Python encoding.

    The canonical command uses text print, not filesystem-encoded binary I/O.
    ASCII runner-state paths have the same encoding on supported hosted Python
    consoles/pipes. Refuse unsupported Unicode paths BEFORE native launch rather
    than silently assuming Windows filesystem UTF-8 is its redirected stdout.
    """
    require(role in ("linux-x64", "windows-x64", "macos-arm64", "macos-x64"), "BOOTSTRAP_INIT_STDOUT_ROLE")
    path = str(producer._path(state, role) / "context.json")
    require(path.isascii(), "BOOTSTRAP_INIT_STDOUT_ASCII_PATH_REQUIRED")
    return path.encode("ascii") + (b"\r\n" if role == "windows-x64" else b"\n")


def _context_values(raw, identity_raw):
    value, admitted = producer.parse(raw), producer.parse(identity_raw)
    require(set(value) == producer.CONTEXT_FIELDS and type(value["schema"]) is int and value["schema"] == 1,
            "BOOTSTRAP_INIT_CONTEXT_FIELDS")
    return value, admitted


def _context_fields(value, admitted, *, root, state, role, outer_job, homes, policy_raw):
    """Common canonical grammar only; the fixed public entries own their routes."""
    root_path, state_path = producer._path(root, role), producer._path(state, role)
    require(root_path != state_path and root_path not in state_path.parents and state_path not in root_path.parents,
            "BOOTSTRAP_INIT_CONTEXT_PATHS")
    source = {**admitted["source"], "status": "", "diffSha256": producer.digest(b"")}
    require(type(value["source"]) is dict and value["source"] == source and
            value["expectedCommit"] == source["commit"] and value["tree"] == source["tree"] and
            value["host"] == role and value["root"] == root and value["gradleHome"] == str(state_path / "gradle-home"),
            "BOOTSTRAP_INIT_CONTEXT_BINDING")
    require(type(value["id"]) is str and re.fullmatch(r"[0-9a-f]{32}", value["id"]) and
            type(outer_job) is str and re.fullmatch(r"[0-9a-f]{32}", outer_job) and value["id"] != outer_job,
            "BOOTSTRAP_INIT_CONTEXT_JOB")
    require(type(homes) is tuple and value["javaHomes"] == list(homes) and type(value["javaHomes"]) is list and
            type(policy_raw) is bytes and policy_raw == properties(homes) and
            value["gradlePropertiesSha256"] == producer.digest(policy_raw), "BOOTSTRAP_INIT_CONTEXT_POLICY")
    require(type(value["preexistingOutputPaths"]) is list and value["preexistingOutputPaths"] == [],
            "BOOTSTRAP_INIT_PREEXISTING_OUTPUTS")
    stamp = value["createdUtc"]
    require(type(stamp) is str and 0 < len(stamp) <= 40, "BOOTSTRAP_INIT_CONTEXT_UTC")
    try:
        require(datetime.fromisoformat(stamp).tzinfo == timezone.utc, "BOOTSTRAP_INIT_CONTEXT_UTC")
    except ValueError:
        raise producer.ProducerError("BOOTSTRAP_INIT_CONTEXT_UTC") from None
    # Timestamp is a label only. No RAW/LOCAL budget or ordering is inferred.
    return value


def context_record(raw, *, admitted_raw, root, state, role, outer_job, homes, policy_raw):
    """Strict trusted-main supplied-byte check; read only after native close."""
    value, admitted = _context_values(raw, admitted_raw)
    require(type(root) is str and type(state) is str and type(role) is str and
            producer.bootstrap.cache_cohort(admitted_raw)[1] == role, "BOOTSTRAP_INIT_CONTEXT_ROLE")
    return _context_fields(value, admitted, root=root, state=state, role=role, outer_job=outer_job,
                           homes=homes, policy_raw=policy_raw)


def initial_recipient_context_record(raw, *, worker_raw, root, state, role, outer_job, homes, policy_raw):
    """Stage1-only supplied-context check, not original custody or live authority.

    No Admission is constructed and no old identity route is widened. The future
    owner must independently acquire current authority and original output after
    native/capture retirement. Matching or repeated bytes do not supply those
    facts, validate the recipient, or admit initialization/producer execution.
    """
    require(type(raw) is bytes and type(worker_raw) is bytes, "BOOTSTRAP_INIT_INITIAL_RECIPIENT_BYTES")
    value, worker = _context_values(raw, worker_raw)
    cohort = initial_identity.cache_cohort(worker_raw)
    require(cohort is not None, "BOOTSTRAP_INIT_INITIAL_RECIPIENT_REQUIRED")
    require(type(root) is str and type(state) is str and type(role) is str and cohort[1] == role,
            "BOOTSTRAP_INIT_CONTEXT_ROLE")
    return _context_fields(value, worker, root=root, state=state, role=role, outer_job=outer_job,
                           homes=homes, policy_raw=policy_raw)
