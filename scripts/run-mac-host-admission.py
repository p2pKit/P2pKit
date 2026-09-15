#!/usr/bin/env python3
"""Closed, no-child hosted Mac OS/capacity snapshot; NOT writer admission.

Invoke only through the reviewed Desktop workflow, using Python 3.9+ and -I -B -S.
The intact reviewed script, trusted interpreter/stdlib, genuine hosted runner and
pinned checkout, and absence of a concurrent source/output writer are premises.
No script can authenticate a hostile interpreter or catch its own parse failure.
Root must independently verify GitHub's commit/tree, event/workflow/run/attempt
and actual terminal step/job outcome. A pre-exit file is not an exit receipt.

Only ordinary source trees are supported. Two complete SHA-1 Git-tree hashes
prove observed bytes/Git modes, not atomicity, HEAD/index/history/config, ACLs or
xattrs. No Git, other child, process census, ownership provider, thread, watcher,
network, toolchain, simulator or writer is invoked, even for failure handling.
The 30-second cooperative budget cannot preempt a stuck OS call; the workflow's
outer timeout and genuine terminal outcome remain mandatory.
"""

import sys

try:
    import ctypes
    import errno
    import hashlib
    import json
    import os
    import re
    import stat
    import time
    import unicodedata
except BaseException:
    # No raw import exception, interpreter path, environment or traceback.
    try:
        sys.stderr.write("MAC_HOST_CAPACITY_ERROR:STARTUP\n")
    except BaseException:
        pass
    raise SystemExit(2) from None


SCOPE = "HOST_OS_CAPACITY_SNAPSHOT_ONLY"
REPOSITORY = "p2pKit/P2pKit"
OWNER = "p2pKit"
WORKFLOW = ".github/workflows/desktop-cross-host.yml"
WORKFLOW_NAME = "Desktop cross-host"
SCRIPT = "scripts/run-mac-host-admission.py"
JOB = "mac-host-admission-probe"
OPERATIONS = {
    "macos-arm64-admission": {
        "label": "macos-26", "role": "macos-arm64", "machine": "arm64", "arch": "ARM64",
        "product_major": "26", "kernel_major": "25", "images": ("macos26", "macos26-arm64"),
    },
    "macos-x64-admission": {
        "label": "macos-15-intel", "role": "macos-x64", "machine": "x86_64", "arch": "X64",
        "product_major": "15", "kernel_major": "24", "images": ("macos15", "macos15-intel"),
    },
}
SECONDS = 30
GIB = 1024 ** 3
INITIAL_DISK_BYTES = 16 * GIB
CHUNK_BYTES = 128 * 1024
MAX_FILE_BYTES = 32 * 1024 ** 2
MAX_SOURCE_BYTES = 256 * 1024 ** 2
MAX_ENTRIES = 25000
MAX_DEPTH = 64
MAX_NAME_BYTES = 255
MAX_NAMES_BYTES = 4 * 1024 ** 2
MAX_PATH_BYTES = 4096
MAX_EVENT_BYTES = 256 * 1024
MAX_PUBLIC_BYTES = 64 * 1024
MAX_U64 = 2 ** 64 - 1
HEX40 = r"[0-9a-f]{40}"
HEX64 = r"[0-9a-f]{64}"
DECIMAL_ID = r"[1-9][0-9]{0,19}"
LOGIN = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})(?:\[bot\])?"
PRODUCT_VERSION = r"[0-9]{1,2}\.[0-9]{1,3}(?:\.[0-9]{1,3})?"
BUILD_VERSION = r"[0-9]{1,2}[A-Z][0-9]{1,6}[a-z]?"
KERNEL_RELEASE = r"[0-9]{1,2}\.[0-9]{1,3}\.[0-9]{1,3}"
IMAGE_VERSION = r"[0-9]{8}\.[0-9]{1,6}(?:\.[0-9]{1,6})?"
PUBLIC_NAMES = {b"metadata.json", b"manifest.json"}
READINESS = b"artifacts_ready=true\n"
ERRORS = frozenset({
    "STARTUP", "ARGUMENTS", "RUNTIME", "IDENTITY", "EVENT_JSON",
    "ENVIRONMENT_COUNT", "ENVIRONMENT_KEY", "ENVIRONMENT_PINNED_VALUE", "ENVIRONMENT_REQUIRED",
    "ENVIRONMENT_PYTHON_HOOK", "ENVIRONMENT_LOADER_HOOK", "ENVIRONMENT_GIT_HOOK",
    "ENVIRONMENT_SHELL_HOOK", "ENVIRONMENT_JVM_HOOK", "ENVIRONMENT_BUILD_HOME",
    "ENVIRONMENT_CREDENTIAL_TOKEN", "ENVIRONMENT_CREDENTIAL_PROMPT",
    "ENVIRONMENT_CREDENTIAL_SSH_AGENT", "ENVIRONMENT_CREDENTIAL_GPG_AGENT",
    "ENVIRONMENT_ELEVATION", "ENVIRONMENT_CAMPAIGN_HOOK",
    "PATH", "FILESYSTEM", "SOURCE_UNSUPPORTED", "SOURCE_CHANGED", "SOURCE_LIMIT",
    "SOURCE_TREE_MISMATCH", "DEADLINE", "PUBLIC_SCHEMA", "PUBLIC_TREE", "PUBLIC_HASH",
    "PUBLIC_EXISTS", "OUTPUT", "INTERRUPTED", "INTERNAL",
})
REASONS = frozenset({
    "READ_FAILED", "INVALID_VALUE", "SYSCTL_UNAVAILABLE", "SYSCTL_ERROR",
    "SYSCTL_SIZE_INVALID", "SYSCTL_VALUE_INVALID", "TRANSLATION_KEY_ABSENT",
})
OBSERVATION_NAMES = frozenset({
    "kernel", "product_version", "build_version", "ordinary_uid", "pointer_bits",
    "translation", "physical_memory_bytes", "pressure", "disk",
})
LIMITATIONS = {
    "native_ownership": "NOT_EXECUTED",
    "children_launched": 0,
    "child_retirement": "NOT_APPLICABLE_NO_CHILDREN",
    "toolchains": "NOT_OBSERVED",
    "simulators": "NOT_EXECUTED",
    "available_memory": "NOT_OBSERVED",
    "sustained_writer_fit": "NOT_OBSERVED",
    "writer_admission": "NOT_GRANTED",
    "prior_warn_hold": "NOT_RELEASED",
    "windows_witness": "NOT_EXECUTED",
    "server_identity_verification": "REQUIRED_INDEPENDENTLY",
    "terminal_outcome": "REQUIRES_GENUINE_RUNNER_RECORD",
    "source_atomicity_and_transient_mutation": "NOT_PROVED",
    "git_head_index_refs_history_config": "NOT_INSPECTED",
    "acl_xattr_resource_forks": "NOT_INSPECTED",
    "runner_infrastructure_ownership": "OUTSIDE_COLLECTOR_SCOPE",
}


class Failure(Exception):
    def __init__(self, code):
        self.code = code if code in ERRORS else "INTERNAL"
        super().__init__(self.code)


def require(condition, code):
    if not condition:
        raise Failure(code)


def matches(pattern, value):
    return type(value) is str and re.fullmatch(pattern, value) is not None


def integer(value, minimum, maximum):
    return type(value) is int and minimum <= value <= maximum


def exact_keys(value, names, code="PUBLIC_SCHEMA"):
    require(type(value) is dict and set(value) == set(names), code)


class Budget:
    def __init__(self):
        self.started = time.monotonic()

    def check(self):
        elapsed = time.monotonic() - self.started
        require(0 <= elapsed < SECONDS, "DEADLINE")
        return int(elapsed * 1000)


def runtime_identity():
    require(sys.platform == "darwin" and os.name == "posix" and
            sys.implementation.name == "cpython" and sys.version_info >= (3, 9) and
            sys.flags.isolated == 1 and sys.flags.ignore_environment == 1 and
            sys.flags.no_user_site == 1 and sys.flags.no_site == 1 and
            sys.dont_write_bytecode is True, "RUNTIME")
    version = list(sys.version_info[:3])
    require(version[0] == 3 and all(integer(n, 0, 99) for n in version), "RUNTIME")
    return {"implementation": "cpython", "version": version, "platform": "darwin", "os_name": "posix",
            "isolated": True, "no_site": True, "bytecode_disabled": True}


def check_environment(env):
    # Reject, never remove/rewrite, caller configuration or loader/credential hooks.
    # Normal hosted PATH/HOME/tool installation variables are not toolchain evidence.
    # Report only the first failed predicate's fixed category, never a caller key/value.
    allowed = {"PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1", "GIT_TERMINAL_PROMPT": "0"}
    groups = (
        ("ENVIRONMENT_SHELL_HOOK", ("BASH_ENV", "ENV", "ZDOTDIR", "CDPATH")),
        ("ENVIRONMENT_JVM_HOOK", ("JAVA_OPTS", "GRADLE_OPTS", "JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS")),
        ("ENVIRONMENT_BUILD_HOME", ("GRADLE_USER_HOME",)),
        ("ENVIRONMENT_CREDENTIAL_TOKEN", ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN")),
        ("ENVIRONMENT_CREDENTIAL_PROMPT", ("SSH_ASKPASS",)),
        ("ENVIRONMENT_CREDENTIAL_SSH_AGENT", ("SSH_AUTH_SOCK",)),
        ("ENVIRONMENT_CREDENTIAL_GPG_AGENT", ("GPG_AGENT_INFO",)),
        ("ENVIRONMENT_ELEVATION", ("SUDO_UID", "SUDO_GID", "SUDO_USER", "SUDO_COMMAND")),
    )
    forbidden = {key: code for code, keys in groups for key in keys}
    require(len(env) <= 4096, "ENVIRONMENT_COUNT")
    for key in env:
        require(type(key) is str and len(key) <= 256, "ENVIRONMENT_KEY")
        if key in allowed:
            require(env[key] == allowed[key], "ENVIRONMENT_PINNED_VALUE")
        elif key.startswith("PYTHON"):
            raise Failure("ENVIRONMENT_PYTHON_HOOK")
        elif key.startswith(("DYLD_", "LD_")):
            raise Failure("ENVIRONMENT_LOADER_HOOK")
        elif key.startswith("GIT_"):
            raise Failure("ENVIRONMENT_GIT_HOOK")
        elif key in forbidden:
            raise Failure(forbidden[key])
        elif key.startswith("P2PKIT_"):
            require(key in {"P2PKIT_OPERATION", "P2PKIT_EXPECTED_SHA", "P2PKIT_EXPECTED_TREE"},
                    "ENVIRONMENT_CAMPAIGN_HOOK")
    require(env.get("PYTHONDONTWRITEBYTECODE") == "1" and env.get("PYTHONUNBUFFERED") == "1", "ENVIRONMENT_REQUIRED")


def branch_ref(value):
    if not matches(r"refs/heads/[A-Za-z0-9][A-Za-z0-9._/-]{0,244}", value):
        return False
    branch = value[len("refs/heads/"):]
    return (value != "refs/heads/audit/complete-2026-09-04" and ".." not in branch and
            all(part and not part.startswith(".") and not part.endswith((".", ".lock"))
                for part in branch.split("/")))


def dispatch_identity(env, event):
    operation = env.get("P2PKIT_OPERATION")
    require(type(operation) is str and operation in OPERATIONS, "IDENTITY")
    selected = OPERATIONS[operation]
    sha, tree = env.get("P2PKIT_EXPECTED_SHA"), env.get("P2PKIT_EXPECTED_TREE")
    require(matches(HEX40, sha) and matches(HEX40, tree), "IDENTITY")
    fixed = {
        "GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REPOSITORY": REPOSITORY, "GITHUB_REPOSITORY_OWNER": OWNER,
        "GITHUB_SERVER_URL": "https://github.com", "GITHUB_API_URL": "https://api.github.com",
        "GITHUB_JOB": JOB, "GITHUB_WORKFLOW": WORKFLOW_NAME, "GITHUB_SHA": sha,
        "GITHUB_WORKFLOW_SHA": sha, "GITHUB_REF_TYPE": "branch", "RUNNER_ENVIRONMENT": "github-hosted",
        "RUNNER_OS": "macOS", "RUNNER_ARCH": selected["arch"],
    }
    require(all(env.get(key) == value for key, value in fixed.items()), "IDENTITY")
    ref = env.get("GITHUB_REF")
    require(branch_ref(ref) and env.get("GITHUB_REF_NAME") == ref[len("refs/heads/"):], "IDENTITY")
    workflow_ref = REPOSITORY + "/" + WORKFLOW + "@" + ref
    require(env.get("GITHUB_WORKFLOW_REF") == workflow_ref, "IDENTITY")
    ids = ("GITHUB_REPOSITORY_ID", "GITHUB_REPOSITORY_OWNER_ID", "GITHUB_ACTOR_ID",
           "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_RUN_NUMBER")
    require(all(matches(DECIMAL_ID, env.get(key)) for key in ids), "IDENTITY")
    actor, triggering_actor = env.get("GITHUB_ACTOR"), env.get("GITHUB_TRIGGERING_ACTOR")
    require(matches(LOGIN, actor) and matches(LOGIN, triggering_actor), "IDENTITY")
    require(type(event) is dict, "IDENTITY")
    repository, sender = event.get("repository"), event.get("sender")
    require(type(repository) is dict and type(sender) is dict, "IDENTITY")
    owner = repository.get("owner")
    require(type(owner) is dict and repository.get("full_name") == REPOSITORY and
            repository.get("name") == "P2pKit" and owner.get("login") == OWNER and
            repository.get("html_url") == "https://github.com/" + REPOSITORY and
            repository.get("url") == "https://api.github.com/repos/" + REPOSITORY and
            repository.get("fork") is False, "IDENTITY")
    for value, name in ((repository.get("id"), "GITHUB_REPOSITORY_ID"),
                        (owner.get("id"), "GITHUB_REPOSITORY_OWNER_ID"),
                        (sender.get("id"), "GITHUB_ACTOR_ID")):
        require(integer(value, 1, 10 ** 20 - 1) and str(value) == env[name], "IDENTITY")
    require(sender.get("login") == actor and event.get("ref") in (ref, ref[len("refs/heads/"):]), "IDENTITY")
    inputs = {"operation": operation, "expected_sha": sha, "expected_tree": tree}
    require(type(event.get("inputs")) is dict and event["inputs"] == inputs, "IDENTITY")
    image_os, image_version = env.get("ImageOS"), env.get("ImageVersion")
    require(image_os in selected["images"] and matches(IMAGE_VERSION, image_version), "IDENTITY")
    return {
        "repository": REPOSITORY, "repository_id": env["GITHUB_REPOSITORY_ID"],
        "repository_owner_id": env["GITHUB_REPOSITORY_OWNER_ID"],
        "server": "https://github.com", "api": "https://api.github.com", "event": "workflow_dispatch",
        "ref": ref, "workflow": WORKFLOW, "workflow_name": WORKFLOW_NAME,
        "workflow_ref": workflow_ref, "workflow_sha": sha, "source_sha": sha, "source_tree": tree,
        "job": JOB, "run_id": env["GITHUB_RUN_ID"], "run_attempt": env["GITHUB_RUN_ATTEMPT"],
        "run_number": env["GITHUB_RUN_NUMBER"], "actor": actor, "actor_id": env["GITHUB_ACTOR_ID"],
        "triggering_actor": triggering_actor, "operation": operation,
        "runner_environment": "github-hosted", "selected_runner_label": selected["label"],
        "runner_image_os": image_os, "runner_image_version": image_version,
    }


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "EVENT_JSON")
        result[key] = value
    return result


def json_integer(value):
    require(len(value) <= 21, "EVENT_JSON")
    return int(value)


def reject_json_number(value):
    raise Failure("EVENT_JSON")


def parse_json(raw, limit):
    require(type(raw) is bytes and 0 < len(raw) <= limit, "EVENT_JSON")
    try:
        value = json.loads(raw.decode("utf-8", errors="strict"), object_pairs_hook=unique_object,
                           parse_int=json_integer, parse_float=reject_json_number, parse_constant=reject_json_number)
    except (ValueError, UnicodeError, RecursionError):
        raise Failure("EVENT_JSON") from None
    pending, count = [(value, 0)], 0
    while pending:
        current, depth = pending.pop()
        count += 1
        require(count <= 20000 and depth <= 32, "EVENT_JSON")
        if type(current) is dict:
            pending.extend((member, depth + 1) for member in current.values())
        elif type(current) is list:
            pending.extend((member, depth + 1) for member in current)
        else:
            require(type(current) in (str, int, bool, type(None)), "EVENT_JSON")
    require(type(value) is dict, "EVENT_JSON")
    return value


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False) + "\n").encode("ascii")


def physical_parts(path):
    require(type(path) is str and path.startswith("/") and path != "/" and
            len(os.fsencode(path)) <= MAX_PATH_BYTES and not any(c in path for c in "\x00\r\n"), "PATH")
    parts = path[1:].split("/")
    require(len(parts) <= MAX_DEPTH and all(part and part not in (".", "..") for part in parts), "PATH")
    return parts


def identity_key(value):
    return (value.st_dev, value.st_ino, value.st_mode, value.st_uid, value.st_gid)


def stability_key(value):
    return identity_key(value) + (value.st_nlink, value.st_size, value.st_mtime_ns, value.st_ctime_ns)


def directory_stat(value):
    require(stat.S_ISDIR(value.st_mode) and value.st_nlink > 0, "SOURCE_UNSUPPORTED")


def regular_stat(value, maximum):
    require(stat.S_ISREG(value.st_mode) and value.st_nlink == 1 and
            value.st_mode & 0o444 and not value.st_mode & (stat.S_ISUID | stat.S_ISGID | stat.S_ISVTX),
            "SOURCE_UNSUPPORTED")
    require(integer(value.st_size, 0, maximum), "SOURCE_LIMIT")


class Anchor:
    """Hold/recheck every physical ancestor; never resolve a link or a gitfile."""
    def __init__(self, path, budget):
        self.path, self.budget, self.fds, self.edges = path, budget, [], []
        parts = physical_parts(path)
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        try:
            budget.check()
            self.fds.append(os.open("/", flags))
            directory_stat(os.fstat(self.fds[0]))
            for part in parts:
                budget.check()
                parent = self.fds[-1]
                before = os.stat(part, dir_fd=parent, follow_symlinks=False)
                directory_stat(before)
                child = os.open(part, flags, dir_fd=parent)
                self.fds.append(child)
                require(identity_key(os.fstat(child)) == identity_key(before), "SOURCE_CHANGED")
                self.edges.append((parent, part, child, identity_key(before)))
            self.fd = self.fds[-1]
            self.check()
        except BaseException:
            self.close()
            raise

    def check(self):
        for parent, name, child, original in self.edges:
            self.budget.check()
            require(identity_key(os.stat(name, dir_fd=parent, follow_symlinks=False)) == original and
                    identity_key(os.fstat(child)) == original, "SOURCE_CHANGED")

    def close(self):
        failed = False
        while self.fds:
            try:
                os.close(self.fds.pop())
            except OSError:
                failed = True
        require(not failed, "FILESYSTEM")

    def __enter__(self):
        return self

    def __exit__(self, kind, value, traceback):
        self.close()


def entry_name(raw):
    require(type(raw) is bytes and 0 < len(raw) <= MAX_NAME_BYTES and raw not in (b".", b"..") and
            not any(c < 32 or c == 127 for c in raw) and not any(c in raw for c in (b"/", b"\\", b":")),
            "SOURCE_UNSUPPORTED")
    try:
        decoded = raw.decode("utf-8", errors="strict")
    except UnicodeError:
        raise Failure("SOURCE_UNSUPPORTED") from None
    # Only a collision key, NEVER an object name or an ordering key. A lone
    # filesystem normalization change still fails the literal expected-tree hash.
    return unicodedata.normalize("NFC", decoded).casefold()


def scan_directory(fd, budget):
    entries, aliases = {}, set()
    with os.scandir(fd) as stream:
        for entry in stream:
            budget.check()
            require(len(entries) < MAX_ENTRIES + 1, "SOURCE_LIMIT")
            raw = os.fsencode(entry.name)
            alias = entry_name(raw)
            require(raw not in entries and alias not in aliases, "SOURCE_UNSUPPORTED")
            aliases.add(alias)
            entries[raw] = os.stat(raw, dir_fd=fd, follow_symlinks=False)
    budget.check()
    return entries


def open_regular(parent, name, maximum, budget):
    budget.check()
    before = os.stat(name, dir_fd=parent, follow_symlinks=False)
    regular_stat(before, maximum)
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=parent)
    try:
        require(stability_key(os.fstat(fd)) == stability_key(before), "SOURCE_CHANGED")
    except BaseException:
        os.close(fd)
        raise
    return fd, before


def finish_read(parent, name, fd, before, budget):
    budget.check()
    require(stability_key(os.fstat(fd)) == stability_key(before) and
            stability_key(os.stat(name, dir_fd=parent, follow_symlinks=False)) == stability_key(before),
            "SOURCE_CHANGED")


def read_regular(parent, name, maximum, budget, public=False):
    fd, before = open_regular(parent, name, maximum, budget)
    try:
        if public:
            require(stat.S_IMODE(before.st_mode) == 0o600 and before.st_uid == os.geteuid(), "PUBLIC_TREE")
        chunks, remaining = [], before.st_size
        while remaining:
            budget.check()
            block = os.read(fd, min(CHUNK_BYTES, remaining))
            require(0 < len(block) <= remaining, "SOURCE_CHANGED")
            chunks.append(block)
            remaining -= len(block)
        require(os.read(fd, 1) == b"", "SOURCE_CHANGED")
        finish_read(parent, name, fd, before, budget)
        return b"".join(chunks)
    finally:
        os.close(fd)


def read_external(path, maximum, budget):
    parts = physical_parts(path)
    require(len(parts) > 1, "PATH")
    with Anchor("/" + "/".join(parts[:-1]), budget) as parent:
        raw = read_regular(parent.fd, parts[-1], maximum, budget)
        parent.check()
        return raw


class TreeState:
    def __init__(self, device):
        self.device, self.entries, self.files, self.directories = device, 0, 0, 0
        self.bytes, self.name_bytes, self.identities = 0, 0, set()

    def remember(self, value):
        require(value.st_dev == self.device and (value.st_dev, value.st_ino) not in self.identities,
                "SOURCE_UNSUPPORTED")
        self.identities.add((value.st_dev, value.st_ino))

    def member(self, name, value):
        self.remember(value)
        self.entries += 1
        self.name_bytes += len(name)
        require(self.entries <= MAX_ENTRIES and self.name_bytes <= MAX_NAMES_BYTES, "SOURCE_LIMIT")


def blob_hash(parent, name, original, state, budget):
    regular_stat(original, MAX_FILE_BYTES)
    state.bytes += original.st_size
    state.files += 1
    require(state.bytes <= MAX_SOURCE_BYTES, "SOURCE_LIMIT")
    fd, before = open_regular(parent, name, MAX_FILE_BYTES, budget)
    try:
        require(stability_key(before) == stability_key(original), "SOURCE_CHANGED")
        value = hashlib.sha1(b"blob " + str(before.st_size).encode("ascii") + b"\0")
        remaining = before.st_size
        while remaining:
            budget.check()
            block = os.read(fd, min(CHUNK_BYTES, remaining))
            require(0 < len(block) <= remaining, "SOURCE_CHANGED")
            value.update(block)
            remaining -= len(block)
        require(os.read(fd, 1) == b"", "SOURCE_CHANGED")
        finish_read(parent, name, fd, before, budget)
        return value.digest()
    finally:
        os.close(fd)


def tree_hash(fd, before, state, budget, depth=0, path_bytes=0):
    budget.check()
    require(depth <= MAX_DEPTH, "SOURCE_LIMIT")
    directory_stat(before)
    require(stability_key(os.fstat(fd)) == stability_key(before), "SOURCE_CHANGED")
    entries = scan_directory(fd, budget)
    records = []
    if depth == 0:
        require(b".git" in entries, "SOURCE_UNSUPPORTED")
    for name, value in entries.items():
        budget.check()
        require(path_bytes + len(name) + 1 <= MAX_PATH_BYTES, "SOURCE_LIMIT")
        if depth == 0 and name == b".git":
            # The sole excluded entry must really be a physical directory. No
            # reading its internals; HEAD/index/history/config remain unproved.
            directory_stat(value)
            state.remember(value)
            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
            try:
                require(stability_key(os.fstat(child)) == stability_key(value), "SOURCE_CHANGED")
            finally:
                os.close(child)
            continue
        state.member(name, value)
        if stat.S_ISDIR(value.st_mode):
            state.directories += 1
            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
            try:
                child_hash = tree_hash(child, value, state, budget, depth + 1, path_bytes + len(name) + 1)
            finally:
                os.close(child)
            mode, order = b"40000", name + b"/"
        else:
            child_hash = blob_hash(fd, name, value, state, budget)
            # Git's executable test is OWNER execute, not any execute bit.
            mode = b"100755" if value.st_mode & stat.S_IXUSR else b"100644"
            order = name
        records.append((order, mode + b" " + name + b"\0" + child_hash))
    require(records, "SOURCE_UNSUPPORTED")  # Empty directories and empty gitlinks are not skipped.
    after_entries = scan_directory(fd, budget)
    require(set(after_entries) == set(entries) and all(stability_key(after_entries[name]) == stability_key(value)
            for name, value in entries.items()) and stability_key(os.fstat(fd)) == stability_key(before),
            "SOURCE_CHANGED")
    records.sort(key=lambda record: record[0])
    length = sum(len(record) for _, record in records)
    value = hashlib.sha1(b"tree " + str(length).encode("ascii") + b"\0")
    for _, record in records:
        budget.check()
        value.update(record)
    return value.digest()


def source_tree(anchor, budget):
    anchor.check()
    before = os.fstat(anchor.fd)
    state = TreeState(before.st_dev)
    state.remember(before)
    digest = tree_hash(anchor.fd, before, state, budget).hex()
    anchor.check()
    budget.check()
    return {"tree": digest, "entries": state.entries, "files": state.files,
            "directories": state.directories, "bytes": state.bytes}


def checked_source(anchor, expected_tree, budget):
    result = source_tree(anchor, budget)
    require(result["tree"] == expected_tree, "SOURCE_TREE_MISMATCH")
    return result


def observed(value):
    return {"status": "OBSERVED", "value": value, "reason": "NONE"}


def missing(reason):
    require(reason in REASONS, "INTERNAL")
    return {"status": "NOT_OBSERVED", "value": None, "reason": reason}


def kernel_value(value):
    return (type(value) is dict and set(value) == {"system", "release", "machine"} and
            value["system"] == "Darwin" and matches(KERNEL_RELEASE, value["release"]) and
            value["machine"] in ("arm64", "x86_64"))


def disk_value(value):
    if type(value) is not dict or set(value) != {"block_bytes", "total_bytes", "available_bytes"}:
        return False
    block, total, available = value["block_bytes"], value["total_bytes"], value["available_bytes"]
    return (integer(block, 1, 2 ** 30) and block & (block - 1) == 0 and
            integer(total, 1, MAX_U64) and integer(available, 0, total) and
            total % block == 0 and available % block == 0)


def valid_value(name, value):
    if name == "kernel":
        return kernel_value(value)
    if name == "product_version":
        return matches(PRODUCT_VERSION, value)
    if name == "build_version":
        return matches(BUILD_VERSION, value)
    if name == "ordinary_uid":
        return type(value) is bool
    if name == "pointer_bits":
        return integer(value, 32, 64) and value in (32, 64)
    if name == "translation":
        return integer(value, 0, 1)
    if name == "physical_memory_bytes":
        return integer(value, 1, 64 * 1024 * GIB)
    if name == "pressure":
        return type(value) is str and value in ("NORMAL", "WARN", "CRITICAL")
    if name == "disk":
        return disk_value(value)
    return False


class Sysctl:
    """Five fixed read-only, bounded Darwin queries; no writable new-value pointer."""
    SPECS = {
        "physical_memory_bytes": (b"hw.memsize", ctypes.c_uint64),
        "pressure": (b"kern.memorystatus_vm_pressure_level", ctypes.c_int32),
        "translation": (b"sysctl.proc_translated", ctypes.c_int32),
        "product_version": (b"kern.osproductversion", ctypes.c_char * 64),
        "build_version": (b"kern.osversion", ctypes.c_char * 64),
    }

    def __init__(self, function, library=None):
        self.library, self.function = library, function
        function.argtypes = [ctypes.c_char_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t),
                             ctypes.c_void_p, ctypes.c_size_t]
        function.restype = ctypes.c_int

    @classmethod
    def native(cls):
        # Never ctypes.util/find_library/global-search loading or a caller path.
        library = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
        return cls(library.sysctlbyname, library)

    def read(self, name, budget):
        require(name in self.SPECS, "INTERNAL")
        key, kind = self.SPECS[name]
        value = kind()
        size = ctypes.c_size_t(ctypes.sizeof(value))
        budget.check()
        ctypes.set_errno(0)
        result = self.function(key, ctypes.byref(value), ctypes.byref(size), None, 0)
        error = ctypes.get_errno()
        budget.check()
        if result != 0:
            return missing("TRANSLATION_KEY_ABSENT" if result == -1 and name == "translation" and error == errno.ENOENT
                           else "SYSCTL_ERROR")
        if name in ("product_version", "build_version"):
            if not 2 <= size.value <= ctypes.sizeof(value):
                return missing("SYSCTL_SIZE_INVALID")
            raw = value.raw[:size.value]
            if raw[-1:] != b"\0" or b"\0" in raw[:-1]:
                return missing("SYSCTL_VALUE_INVALID")
            try:
                decoded = raw[:-1].decode("ascii", errors="strict")
            except UnicodeError:
                return missing("SYSCTL_VALUE_INVALID")
        else:
            if size.value != ctypes.sizeof(value):
                return missing("SYSCTL_SIZE_INVALID")
            decoded = value.value
        if name == "pressure":
            decoded = {1: "NORMAL", 2: "WARN", 4: "CRITICAL"}.get(decoded)
        return observed(decoded) if valid_value(name, decoded) else missing("SYSCTL_VALUE_INVALID")


def read_disk(fd, budget):
    budget.check()
    try:
        value = os.statvfs(fd)
        block, total, available = value.f_frsize, value.f_blocks, value.f_bavail
    except OSError:
        budget.check()
        return missing("READ_FAILED")
    budget.check()
    # f_bfree includes blocks unavailable to this UID and is deliberately unused.
    if not (integer(block, 1, 2 ** 30) and integer(total, 1, MAX_U64) and integer(available, 0, total)):
        return missing("INVALID_VALUE")
    result = {"block_bytes": block, "total_bytes": total * block, "available_bytes": available * block}
    return observed(result) if disk_value(result) else missing("INVALID_VALUE")


def collect_host(fd, budget):
    values = {}
    budget.check()
    try:
        raw = os.uname()
        # NEVER copy nodename or uname.version (which can contain a builder path).
        kernel = {"system": raw.sysname, "release": raw.release, "machine": raw.machine}
        values["kernel"] = observed(kernel) if kernel_value(kernel) else missing("INVALID_VALUE")
    except OSError:
        values["kernel"] = missing("READ_FAILED")
    budget.check()
    try:
        uid, effective = os.getuid(), os.geteuid()
        values["ordinary_uid"] = observed(integer(uid, 1, 2 ** 32 - 2) and uid == effective)
    except OSError:
        values["ordinary_uid"] = missing("READ_FAILED")
    bits = ctypes.sizeof(ctypes.c_void_p) * 8
    values["pointer_bits"] = observed(bits) if valid_value("pointer_bits", bits) else missing("INVALID_VALUE")
    budget.check()
    reader = None
    if sys.platform == "darwin" and os.name == "posix" and values["kernel"]["status"] == "OBSERVED":
        try:
            reader = Sysctl.native()
        except (OSError, AttributeError):
            pass
    for name in Sysctl.SPECS:
        budget.check()
        if reader is None:
            values[name] = missing("SYSCTL_UNAVAILABLE")
        else:
            try:
                values[name] = reader.read(name, budget)
            except (OSError, AttributeError):
                values[name] = missing("SYSCTL_ERROR")
    values["disk"] = read_disk(fd, budget)
    budget.check()
    return values


def native_role(values):
    kernel, pointer, translation = values["kernel"], values["pointer_bits"], values["translation"]
    native = ((translation["status"] == "OBSERVED" and translation["value"] == 0) or
              (translation["status"] == "NOT_OBSERVED" and translation["reason"] == "TRANSLATION_KEY_ABSENT"))
    if kernel["status"] == "OBSERVED" and pointer["status"] == "OBSERVED" and pointer["value"] == 64 and native:
        return {"arm64": "macos-arm64", "x86_64": "macos-x64"}.get(kernel["value"]["machine"], "NOT_CONFIRMED")
    return "NOT_CONFIRMED"


def assess(values, operation):
    selected, failures = OPERATIONS[operation], []
    for name in ("kernel", "product_version", "build_version", "physical_memory_bytes"):
        if values[name]["status"] != "OBSERVED":
            failures.append(name.upper() + "_NOT_OBSERVED")
    if values["ordinary_uid"]["status"] != "OBSERVED" or values["ordinary_uid"]["value"] is not True:
        failures.append("ORDINARY_UID_NOT_CONFIRMED")
    role = native_role(values)
    if role != selected["role"]:
        failures.append("NATIVE_ROLE_NOT_CONFIRMED")
    kernel, product, build = values["kernel"], values["product_version"], values["build_version"]
    if ((kernel["status"] == "OBSERVED" and kernel["value"]["release"].split(".")[0] != selected["kernel_major"]) or
            (product["status"] == "OBSERVED" and product["value"].split(".")[0] != selected["product_major"]) or
            (build["status"] == "OBSERVED" and not build["value"].startswith(selected["kernel_major"]))):
        failures.append("OS_IMAGE_ROLE_MISMATCH")
    pressure = values["pressure"]
    if pressure["status"] != "OBSERVED":
        failures.append("PRESSURE_NOT_OBSERVED")
    elif pressure["value"] != "NORMAL":
        failures.append("PRESSURE_NOT_NORMAL")
    disk = values["disk"]
    if disk["status"] != "OBSERVED":
        failures.append("DISK_NOT_OBSERVED")
    elif disk["value"]["available_bytes"] < INITIAL_DISK_BYTES:
        failures.append("INITIAL_DISK_BELOW_16_GIB")
    return {"status": "SNAPSHOT_PREDICATES_MET" if not failures else "SNAPSHOT_PREDICATES_NOT_MET",
            "failures": failures, "native_role_observation": role,
            "minimum_initial_disk_bytes": INITIAL_DISK_BYTES, "required_pressure": "NORMAL",
            "disk_volume": "CHECKOUT_AND_RUNNER_TEMP_SAME_DEVICE"}


def validate_snapshot(value, expected_tree):
    exact_keys(value, {"tree", "entries", "files", "directories", "bytes"})
    require(value["tree"] == expected_tree and matches(HEX40, value["tree"]) and
            integer(value["entries"], 1, MAX_ENTRIES) and integer(value["files"], 1, MAX_ENTRIES) and
            integer(value["directories"], 0, MAX_ENTRIES) and integer(value["bytes"], 0, MAX_SOURCE_BYTES) and
            value["entries"] == value["files"] + value["directories"], "PUBLIC_SCHEMA")


def validate_metadata(value, identity, runtime):
    exact_keys(value, {"schema", "scope", "identity", "runtime", "source", "observations",
                       "assessment", "limitations", "observation_elapsed_ms"})
    require(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == SCOPE and
            value["identity"] == identity and value["runtime"] == runtime and
            value["limitations"] == LIMITATIONS and
            integer(value["observation_elapsed_ms"], 0, SECONDS * 1000 - 1), "PUBLIC_SCHEMA")
    # Equality alone admits bool==int aliases. Canonical bytes preserve exact types
    # throughout fixed identity/runtime/limitations and derived assessment objects.
    for name, expected in (("identity", identity), ("runtime", runtime), ("limitations", LIMITATIONS)):
        require(json_bytes(value[name]) == json_bytes(expected), "PUBLIC_SCHEMA")
    exact_keys(value["source"], {"method", "before", "after"})
    require(value["source"]["method"] == "COMPLETE_FILESYSTEM_GIT_SHA1_TREE", "PUBLIC_SCHEMA")
    for side in ("before", "after"):
        validate_snapshot(value["source"][side], identity["source_tree"])
    require(value["source"]["before"] == value["source"]["after"], "PUBLIC_SCHEMA")
    exact_keys(value["observations"], OBSERVATION_NAMES)
    for name, observation in value["observations"].items():
        exact_keys(observation, {"status", "value", "reason"})
        if observation["status"] == "OBSERVED":
            require(observation["reason"] == "NONE" and valid_value(name, observation["value"]), "PUBLIC_SCHEMA")
        else:
            require(observation["status"] == "NOT_OBSERVED" and observation["value"] is None and
                    type(observation["reason"]) is str and observation["reason"] in REASONS and
                    (observation["reason"] != "TRANSLATION_KEY_ABSENT" or name == "translation"), "PUBLIC_SCHEMA")
    expected_assessment = assess(value["observations"], identity["operation"])
    require(json_bytes(value["assessment"]) == json_bytes(expected_assessment), "PUBLIC_SCHEMA")


def manifest_for(raw, identity):
    return {"schema": 1, "scope": SCOPE, "identity": identity,
            "members": {"metadata.json": {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}}}


def public_directory(temp_path, identity):
    physical_parts(temp_path)
    return temp_path + "/p2pkit-mac-host-capacity-" + identity["run_id"] + "-" + identity["run_attempt"]


def public_tree(anchor, identity, runtime, budget):
    anchor.check()
    before = os.fstat(anchor.fd)
    require(stat.S_IMODE(before.st_mode) == 0o700 and before.st_uid == os.geteuid(), "PUBLIC_TREE")
    entries = scan_directory(anchor.fd, budget)
    require(set(entries) == PUBLIC_NAMES, "PUBLIC_TREE")
    metadata_raw = read_regular(anchor.fd, b"metadata.json", MAX_PUBLIC_BYTES, budget, public=True)
    manifest_raw = read_regular(anchor.fd, b"manifest.json", MAX_PUBLIC_BYTES, budget, public=True)
    metadata, manifest = parse_json(metadata_raw, MAX_PUBLIC_BYTES), parse_json(manifest_raw, MAX_PUBLIC_BYTES)
    validate_metadata(metadata, identity, runtime)
    require(metadata_raw == json_bytes(metadata), "PUBLIC_SCHEMA")
    require(manifest_raw == json_bytes(manifest_for(metadata_raw, identity)), "PUBLIC_HASH")
    after = scan_directory(anchor.fd, budget)
    require(set(after) == set(entries) and all(stability_key(after[name]) == stability_key(value)
            for name, value in entries.items()) and stability_key(os.fstat(anchor.fd)) == stability_key(before),
            "PUBLIC_TREE")
    anchor.check()
    budget.check()
    return metadata_raw, manifest_raw, metadata


def write_public_file(fd, name, raw, budget):
    require(name in PUBLIC_NAMES and type(raw) is bytes and 0 < len(raw) <= MAX_PUBLIC_BYTES, "PUBLIC_SCHEMA")
    budget.check()
    child = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                    0o600, dir_fd=fd)
    try:
        before = os.fstat(child)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == 0 and
                before.st_uid == os.geteuid() and stat.S_IMODE(before.st_mode) == 0o600, "PUBLIC_TREE")
        offset = 0
        while offset < len(raw):
            budget.check()
            size = os.write(child, raw[offset:])
            require(0 < size <= len(raw) - offset, "OUTPUT")
            offset += size
        os.fsync(child)
        after = os.fstat(child)
        require(identity_key(before) == identity_key(after) and after.st_nlink == 1 and after.st_size == len(raw),
                "PUBLIC_TREE")
        budget.check()
    finally:
        os.close(child)


def retain_public(temp, identity, runtime, metadata, budget):
    validate_metadata(metadata, identity, runtime)
    raw = json_bytes(metadata)
    path = public_directory(temp.path, identity)
    name = path.rsplit("/", 1)[1]
    budget.check()
    try:
        os.mkdir(name, 0o700, dir_fd=temp.fd)
    except FileExistsError:
        raise Failure("PUBLIC_EXISTS") from None
    # No replacement, output reuse, best-effort sanitization, cleanup, or extra file.
    with Anchor(path, budget) as public:
        require(os.fstat(public.fd).st_dev == os.fstat(temp.fd).st_dev, "PUBLIC_TREE")
        write_public_file(public.fd, b"metadata.json", raw, budget)
        write_public_file(public.fd, b"manifest.json", json_bytes(manifest_for(raw, identity)), budget)
        os.fsync(public.fd)
        public_tree(public, identity, runtime, budget)
    temp.check()


def append_ready(path, budget):
    parts = physical_parts(path)
    require(len(parts) > 1, "OUTPUT")
    with Anchor("/" + "/".join(parts[:-1]), budget) as parent:
        name = parts[-1]
        before = os.stat(name, dir_fd=parent.fd, follow_symlinks=False)
        regular_stat(before, 0)
        require(before.st_uid == os.geteuid(), "OUTPUT")
        child = os.open(name, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
                        dir_fd=parent.fd)
        try:
            require(stability_key(os.fstat(child)) == stability_key(before), "OUTPUT")
            parent.check()
            budget.check()
            require(os.write(child, READINESS) == len(READINESS), "OUTPUT")
            os.fsync(child)
            budget.check()
        finally:
            os.close(child)
    # This key means only validated finite files are eligible for retention. Even
    # a later timeout/close failure is NOT a successful terminal outcome or admission.


def context(env, budget):
    runtime = runtime_identity()
    check_environment(env)
    workspace, temporary = env.get("GITHUB_WORKSPACE"), env.get("RUNNER_TEMP")
    physical_parts(workspace)
    physical_parts(temporary)
    require(not (temporary == workspace or temporary.startswith(workspace + "/") or
                 workspace.startswith(temporary + "/")), "PATH")
    require(os.getcwd() == workspace and __file__ == workspace + "/" + SCRIPT, "RUNTIME")
    event_path = env.get("GITHUB_EVENT_PATH")
    physical_parts(event_path)
    require(not event_path.startswith(workspace + "/"), "PATH")
    event = parse_json(read_external(event_path, MAX_EVENT_BYTES, budget), MAX_EVENT_BYTES)
    identity = dispatch_identity(env, event)
    budget.check()
    return runtime, identity, workspace, temporary


def run(env, budget):
    runtime, identity, workspace, temporary = context(env, budget)
    with Anchor(workspace, budget) as source, Anchor(temporary, budget) as temp:
        require(os.fstat(source.fd).st_dev == os.fstat(temp.fd).st_dev, "PATH")
        before = checked_source(source, identity["source_tree"], budget)
        observations = collect_host(source.fd, budget)
        after = checked_source(source, identity["source_tree"], budget)
        require(before == after, "SOURCE_CHANGED")
        metadata = {
            "schema": 1, "scope": SCOPE, "identity": identity, "runtime": runtime,
            "source": {"method": "COMPLETE_FILESYSTEM_GIT_SHA1_TREE", "before": before, "after": after},
            "observations": observations, "assessment": assess(observations, identity["operation"]),
            "limitations": dict(LIMITATIONS), "observation_elapsed_ms": budget.check(),
        }
        retain_public(temp, identity, runtime, metadata, budget)
        source.check()
        budget.check()
    return 0 if metadata["assessment"]["status"] == "SNAPSHOT_PREDICATES_MET" else 1


def validate_public(env, budget):
    runtime, identity, workspace, temporary = context(env, budget)
    output = env.get("GITHUB_OUTPUT")
    physical_parts(output)
    require(not (output == workspace or output.startswith(workspace + "/") or
                 output.startswith(public_directory(temporary, identity) + "/")), "PATH")
    with Anchor(workspace, budget) as source, Anchor(temporary, budget) as temp:
        require(os.fstat(source.fd).st_dev == os.fstat(temp.fd).st_dev, "PATH")
        before = checked_source(source, identity["source_tree"], budget)
        with Anchor(public_directory(temporary, identity), budget) as public:
            require(os.fstat(public.fd).st_dev == os.fstat(temp.fd).st_dev, "PUBLIC_TREE")
            original = public_tree(public, identity, runtime, budget)
            require(original[2]["source"]["before"] == before, "PUBLIC_SCHEMA")
            after = checked_source(source, identity["source_tree"], budget)
            require(before == after, "SOURCE_CHANGED")
            require(public_tree(public, identity, runtime, budget) == original, "PUBLIC_HASH")
        source.check()
        temp.check()
        budget.check()
    # All source/public descriptors have closed successfully before exposing ready.
    append_ready(output, budget)
    return 0


def console(raw):
    try:
        os.write(2, raw)
    except BaseException:
        pass


def main(argv):
    try:
        require(argv in (["run"], ["validate-public"]), "ARGUMENTS")
        budget = Budget()
        code = run(os.environ, budget) if argv == ["run"] else validate_public(os.environ, budget)
        budget.check()  # Include successful final descriptor closes in the cooperative envelope.
        console(b"MAC_HOST_CAPACITY_SNAPSHOT_COMPLETE\n" if code == 0 else b"MAC_HOST_CAPACITY_SNAPSHOT_FAILED\n")
        return code
    except Failure as error:
        console(("MAC_HOST_CAPACITY_ERROR:" + error.code + "\n").encode("ascii"))
    except KeyboardInterrupt:
        console(b"MAC_HOST_CAPACITY_ERROR:INTERRUPTED\n")
    except OSError:
        console(b"MAC_HOST_CAPACITY_ERROR:FILESYSTEM\n")
    except BaseException:
        console(b"MAC_HOST_CAPACITY_ERROR:INTERNAL\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
