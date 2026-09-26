#!/usr/bin/env python3
"""Owned adapter for the disposable-key Central bundle regression, never a publisher.

Only P2PKIT_CENTRAL_BUNDLE_AUDIT=1 selects this contract. The outer canonical
command owns the borrowed work and both short GPG homes. Inner gpgconf results
are stop observations, NOT native-retirement evidence. `finish` retains selected
originals and deliberately leaves all work/homes reachable. After the command
returns, its controller must call `retire --outer-receipt ...`; only the original
successful canonical ownership/stop receipt can authorize scoped removal.

The version-dirty detached worktree preserves Git-derived BuildInfo identity.
Its complete tracked bytes and one permitted version delta are checked before
and after publication; the admitted ROOT wrapper uses -p, not a dirty-source
audit state. No dependency writer, download, upload, native process-discovery
backend or recipient-policy authority is implemented here.
"""

import argparse
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import zipfile


EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
MAX_DOCUMENT = 16 * 1024 * 1024
MAX_FILES = 50000
MAX_RETAINED_BYTES = 512 * 1024 * 1024
PASSWORD = "p2pkit-disposable-test-key"
TEST = "scripts/tests/build-central-portal-bundle-test.sh"
HELPER = "scripts/prepare-audit-central-bundle-metadata.py"
PURPOSE = "central-bundle-publish"
BACKENDS = {"macos-arm64": "darwin-libproc-audit-token", "macos-x64": "darwin-libproc-audit-token",
            "linux-x64": "linux-proc-pidfd", "windows-x64": "windows-job-list-suspended"}


# Only the ordinary-FULL post-return prepare action installs this bound. It is
# shared across context/source/metadata/Git/file work, never renewed per helper.
BOUND_CHECK = lambda: None
BOUND_REMAINING = lambda: 60.0
BOUND_RAW_END = None


def bounded_retirement(raw_end):
    global BOUND_CHECK, BOUND_REMAINING, BOUND_RAW_END
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import hosted_full_job_budget as budget
    first = budget.raw_now()
    require(type(raw_end) is int and first < raw_end <= first + 285 * budget.NS, "Central original retirement bound invalid")
    BOUND_RAW_END = raw_end
    previous = [first]
    def remaining():
        previous[0] = budget.raw_now(previous[0])
        require(previous[0] < raw_end, "Central original retirement bound exhausted")
        return min(60.0, (raw_end - previous[0]) / budget.NS)
    BOUND_REMAINING = remaining
    BOUND_CHECK = lambda: remaining()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def physical(value, *, directory=True, missing=False):
    BOUND_CHECK()
    path = Path(value)
    require(path.is_absolute() and path.resolve() == path and not path.is_symlink(),
            "expected an absolute physical non-symlink path")
    require(path.parent.is_dir(), "physical parent is missing")
    if not missing or path.exists():
        require(path.is_dir() if directory else path.is_file(), "unexpected physical path type")
    return path


def identity(path):
    info = path.lstat()
    require(stat.S_ISDIR(info.st_mode) and not path.is_symlink(), "owned directory was replaced")
    return {"device": info.st_dev, "inode": info.st_ino}


def read_bytes(path, limit=MAX_DOCUMENT):
    physical(path, directory=False)
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    BOUND_CHECK()
    require(len(data) <= limit, "input exceeds its bounded document size")
    return data


def unique(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, "duplicate JSON key")
        value[key] = item
    return value


def read_json(path):
    value = json.loads(read_bytes(path), object_pairs_hook=unique)
    require(type(value) is dict, "expected a JSON object")
    return value


def write_new(path, data):
    BOUND_CHECK()
    physical(path, directory=False, missing=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    path.chmod(0o444)
    BOUND_CHECK()


def write_json(path, value):
    write_new(path, (json.dumps(value, sort_keys=True, indent=2) + "\n").encode())


def git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args], check=True, timeout=BOUND_REMAINING(),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
    BOUND_CHECK()
    return result


def snapshot(root):
    require(git(root, "rev-parse", "--show-toplevel").decode().strip() == str(root), "not the exact Git root")
    return {"commit": git(root, "rev-parse", "HEAD").decode().strip(),
            "tree": git(root, "rev-parse", "HEAD^{tree}").decode().strip(),
            "status": git(root, "status", "--porcelain=v1", "--untracked-files=all").decode(),
            "diffSha256": digest(git(root, "diff", "--binary", "--no-ext-diff", "--no-textconv", "HEAD"))}


def file_record(path):
    physical(path, directory=False)
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode), "nonregular source/evidence input")
    sha = hashlib.sha256()
    blob = hashlib.sha1(("blob " + str(before.st_size) + "\0").encode())
    with path.open("rb") as stream:
        require(os.fstat(stream.fileno()) == before, "file changed while opening")
        for chunk in iter(lambda: stream.read(512 * 1024), b""):
            BOUND_CHECK()
            sha.update(chunk)
            blob.update(chunk)
        after = os.fstat(stream.fileno())
    stable = lambda value: (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)
    require(stable(before) == stable(after) == stable(path.lstat()), "file changed while hashing")
    return {"sha256": sha.hexdigest(), "bytes": before.st_size, "gitBlob": blob.hexdigest(),
            "mode": "100755" if before.st_mode & 0o111 else "100644"}


def tracked(root):
    rows = {}
    for row in git(root, "ls-tree", "-r", "-z", "--full-tree", "HEAD").split(b"\0"):
        if not row:
            continue
        header, encoded = row.split(b"\t", 1)
        mode, kind, blob = header.decode().split()
        name = encoded.decode("utf-8")
        require(kind == "blob" and mode in ("100644", "100755") and "\n" not in name,
                "unsupported tracked source type/path")
        value = file_record(root / name)
        require(value["mode"] == mode and value["gitBlob"] == blob, "source differs from committed bytes: " + name)
        rows[name] = value
        require(len(rows) <= MAX_FILES, "excessive tracked source entries")
    require(rows, "empty source manifest")
    return rows


def coordinates(data):
    result = []
    for name in ("GROUP", "VERSION_NAME"):
        values = re.findall(rb"(?m)^" + name.encode() + rb"=([^\r\n]*)$", data)
        require(len(values) == 1, "expected one " + name + " declaration")
        value = values[0].decode("ascii")
        require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value) and ".." not in value,
                "invalid source coordinate")
        result.append(value)
    return result


def load_module(root, name):
    spec = importlib.util.spec_from_file_location("central_" + name.replace("-", "_"), root / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def context(*, active=True):
    require(os.environ.get("P2PKIT_CENTRAL_BUNDLE_AUDIT") == "1", "explicit Central bundle audit opt-in required")
    state = physical(os.environ.get("P2PKIT_AUDIT_STATE_DIR", ""))
    raw = read_bytes(state / "context.json")
    value = read_json(state / "context.json")
    require(type(value.get("schema")) is int and value["schema"] == 1 and
            re.fullmatch(r"[0-9a-f]{32}", value.get("id", "")), "invalid canonical context")
    root = physical(value.get("root", ""))
    home = physical(value.get("gradleHome", ""))
    require(home == state / "gradle-home" and root not in state.parents and state not in root.parents and root != state,
            "context root/state/home overlap")
    require(value.get("host") in BACKENDS, "unsupported context host")
    source = snapshot(root)
    require(source == value.get("source") and source["commit"] == value.get("expectedCommit") and
            source["tree"] == value.get("tree") and source["status"] == "" and source["diffSha256"] == EMPTY_SHA256,
            "context does not bind the exact clean source")
    require(digest(read_bytes(home / "gradle.properties")) == value.get("gradlePropertiesSha256"),
            "owned Gradle resource policy changed")
    work = physical(os.environ.get("P2PKIT_CENTRAL_BUNDLE_WORK_DIR", ""), missing=True)
    evidence = physical(os.environ.get("P2PKIT_CENTRAL_BUNDLE_EVIDENCE_DIR", ""), missing=True)
    require(work.parent == physical(state / "work") and evidence.parent == physical(state / "evidence"),
            "bundle work/evidence require distinct direct children of STATE/work and STATE/evidence")
    result = {"state": state, "root": root, "home": home, "work": work, "evidence": evidence,
              "fixture": work / "release-source", "repository": work / "repository", "value": value,
              "source": source, "contextSha256": digest(raw)}
    if active:
        require(os.environ.get("P2PKIT_GRADLE_EXECUTOR") == str(root / "scripts/run-audit-command.py") and
                os.environ.get("GRADLE_USER_HOME") == str(home) and os.environ.get("P2PKIT_AUDIT_JOB_ID") == value["id"],
                "executor/current job/home mismatch")
        # Pure parser only: do not instantiate another process-ownership backend.
        ownership = load_module(root, "audit_processes")
        try:
            domains = ownership.ownership_domains(os.environ.get("P2PKIT_AUDIT_OWNERSHIP_CHAIN", ""),
                                                  os.environ.get("P2PKIT_AUDIT_OWNERSHIP_DOMAINS", ""))
        except ownership.OwnershipError as error:
            raise ValueError("invalid enclosing ownership chain/domain") from error
        require(domains and domains[-1] == {"id": domains[-1]["id"], "job": value["id"],
                                           "state": str(state), "home": str(home)}, "missing enclosing ownership domain")
        result["domains"] = domains
    return result


def admission(c, *, active=True):
    a = read_json(c["evidence"] / "admission.json")
    for key, expected in (("root", str(c["root"])), ("work", str(c["work"])), ("state", str(c["state"])),
                          ("contextSha256", c["contextSha256"]), ("source", c["source"]),
                          ("workIdentity", identity(c["work"])), ("evidenceIdentity", identity(c["evidence"]))):
        require(a.get(key) == expected, "admission changed: " + key)
    require(tracked(c["root"]) == a["trackedSource"], "admitted source inputs changed")
    require(a.get("workInitiallyEmpty") is True, "borrowed work was not admitted empty")
    require(digest(read_bytes(c["state"] / "evidence" / a["outerId"] / "start.json")) == a["outerStartSha256"],
            "original outer start was replaced")
    if active:
        require(a["ownershipDomains"] == c["domains"], "enclosing ownership chain changed")
    return a


def derivative(c, a):
    original = read_bytes(c["root"] / "gradle.properties")
    group, version = coordinates(original)
    release = "9.8.7-rc6" if version.endswith("-SNAPSHOT") else version
    derived = re.sub(rb"(?m)^VERSION_NAME=[^\r\n]*", ("VERSION_NAME=" + release).encode(), original)
    rows = dict(a["trackedSource"])
    rows["gradle.properties"] = {
        "sha256": digest(derived), "bytes": len(derived), "mode": rows["gradle.properties"]["mode"],
        "gitBlob": hashlib.sha1(("blob " + str(len(derived)) + "\0").encode() + derived).hexdigest()}
    modules = [str(PurePosixPath(name).parent) for name in rows if name.endswith("/build.gradle.kts") and
               len(PurePosixPath(name).parts) == 3 and PurePosixPath(name).parts[0] in ("library", "samples")]
    outputs = sorted({"build", "buildSrc/build", *[name + "/build" for name in modules]})
    return original, derived, {"group": group, "originalVersion": version, "version": release,
                              "tracked": rows, "outputRoots": outputs,
                              "cacheRoots": [".gradle", ".kotlin", "buildSrc/.gradle", "buildSrc/.kotlin"]}


def admit(c, root):
    require(physical(root) == c["root"] and Path(__file__).resolve() == c["root"] / HELPER,
            "admission must use the admitted source helper")
    for key in ("work", "evidence"):
        path = c[key]
        require(not path.exists() or not any(path.iterdir()), "borrowed " + key + " directory is not empty")
    for name in ("ORG_GRADLE_PROJECT_signingInMemoryKey", "ORG_GRADLE_PROJECT_signingInMemoryKeyBase64",
                 "ORG_GRADLE_PROJECT_signingInMemoryKeyPassword", "MAVEN_SIGNING_KEY_FINGERPRINT"):
        require(not os.environ.get(name), "disposable regression must not inherit signing credentials")
    outer = c["domains"][-1]["id"]
    directory = physical(c["state"] / "evidence" / outer)
    start = read_json(directory / "start.json")
    require(not (directory / "receipt.json").exists(), "enclosing command is already finalized")
    expected = {"schema": 1, "id": outer, "jobId": c["value"]["id"], "kind": "command",
                "cwd": str(c["root"]), "wrapper": str(c["root"] / "gradlew"), "gradleHome": str(c["home"]),
                "ancestorInvocationIds": [row["id"] for row in c["domains"][:-1]]}
    require(all(start.get(key) == item for key, item in expected.items()), "outer start identity/request mismatch")
    require(start.get("requestedArgv") in (["bash", TEST], ["bash", str(c["root"] / TEST)]),
            "outer command is not the exact signed-bundle regression")
    require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}", start.get("purpose", "")), "invalid outer purpose")
    inputs = tracked(c["root"])
    for key in ("work", "evidence"):
        if not c[key].exists():
            c[key].mkdir(mode=0o700)
    write_json(c["evidence"] / "admission.json", {
        "schema": 1, "root": str(c["root"]), "state": str(c["state"]), "work": str(c["work"]),
        "contextSha256": c["contextSha256"], "source": c["source"], "trackedSource": inputs,
        "workIdentity": identity(c["work"]), "evidenceIdentity": identity(c["evidence"]),
        "ownershipDomains": c["domains"], "outerId": outer, "outerStart": start,
        "outerStartSha256": digest(read_bytes(directory / "start.json")), "workInitiallyEmpty": True})


def fixture(c):
    a = admission(c)
    require(not c["fixture"].exists(), "release fixture already exists")
    with (c["work"] / "worktree.stdout.log").open("xb") as out, (c["work"] / "worktree.stderr.log").open("xb") as err:
        result = subprocess.run(["git", "-C", str(c["root"]), "worktree", "add", "--detach",
                                 str(c["fixture"]), c["source"]["commit"]], stdout=out, stderr=err, timeout=60)
    require(result.returncode == 0, "detached release fixture creation failed; originals retained")
    require(tracked(c["fixture"]) == a["trackedSource"], "new worktree differs from admitted source")
    original, derived, expected = derivative(c, a)
    (c["fixture"] / "gradle.properties").write_bytes(derived)
    diff = git(c["fixture"], "diff", "--binary", "--no-ext-diff", "--no-textconv", "HEAD")
    write_new(c["evidence"] / "original-gradle.properties", original)
    write_new(c["evidence"] / "fixture-gradle.properties", derived)
    write_new(c["evidence"] / "fixture-version.diff", diff)
    write_json(c["evidence"] / "fixture.json", {
        "schema": 1, "admissionSha256": digest(read_bytes(c["evidence"] / "admission.json")),
        "path": str(c["fixture"]), "identity": identity(c["fixture"]), "source": snapshot(c["fixture"]),
        "gitFileSha256": digest(read_bytes(c["fixture"] / ".git")), "versionDiffSha256": digest(diff), **expected,
        "derivativeNotReleaseSource": True, "copiedLocalProperties": False})
    check_fixture(c, before_publication=True)


def walk_files(directory, *, skip=(), check=None):
    check = check or BOUND_CHECK
    result, pending, count = [], [(directory, 0)], 0
    while pending:
        check()
        parent, depth = pending.pop()
        require(depth < 64, "excessive directory nesting")
        for path in sorted(parent.iterdir()):
            check()
            count += 1
            require(count <= MAX_FILES, "excessive directory entries")
            info = path.lstat()
            require(not stat.S_ISLNK(info.st_mode), "symlink in owned work/evidence")
            if path in skip:
                require(stat.S_ISDIR(info.st_mode), "generated output root is not a directory")
            elif stat.S_ISDIR(info.st_mode):
                pending.append((path, depth + 1))
            else:
                require(stat.S_ISREG(info.st_mode), "nonregular owned file")
                result.append(path)
    return sorted(result)


def check_fixture(c, *, before_publication=False):
    a = admission(c)
    f = read_json(c["evidence"] / "fixture.json")
    original, derived, expected = derivative(c, a)
    require(all(f.get(key) == value for key, value in expected.items()), "fixture manifest is not the exact version-only derivative")
    require(read_bytes(c["evidence"] / "original-gradle.properties") == original and
            read_bytes(c["evidence"] / "fixture-gradle.properties") == derived and
            read_bytes(c["fixture"] / "gradle.properties") == derived, "retained/source version delta changed")
    require(f["admissionSha256"] == digest(read_bytes(c["evidence"] / "admission.json")) and
            f["path"] == str(c["fixture"]) and f["identity"] == identity(c["fixture"]), "fixture identity changed")
    require(f["source"] == snapshot(c["fixture"]) and f["source"]["commit"] == c["source"]["commit"] and
            f["source"]["tree"] == c["source"]["tree"], "fixture Git/version delta changed")
    require(digest(read_bytes(c["fixture"] / ".git")) == f["gitFileSha256"], "fixture Git linkage changed")
    require(f["versionDiffSha256"] == f["source"]["diffSha256"] == digest(read_bytes(c["evidence"] / "fixture-version.diff")),
            "retained complete version diff changed")
    require(set(f["tracked"]) == set(a["trackedSource"]), "fixture tracked file membership changed")
    for name, expected in f["tracked"].items():
        require(file_record(c["fixture"] / name) == expected, "fixture source changed: " + name)
    allowed = [c["fixture"] / name for name in f["outputRoots"] + f["cacheRoots"]]
    if before_publication:
        require(all(not os.path.lexists(path) for path in allowed),
                "pre-publication generated path already exists in the fresh derivative")
    for path in walk_files(c["fixture"], skip=allowed):
        require(str(path.relative_to(c["fixture"])) in f["tracked"] or path == c["fixture"] / ".git",
                "unexpected fixture input (including ignored local settings)")
    return f


def allocate_home(c, role):
    a = admission(c)
    supplied = os.environ.get("P2PKIT_GPG_TMPDIR")
    parent = physical(supplied if supplied is not None else str(Path("/tmp").resolve()))
    require(len(os.fsencode(str(parent / ("p2pkit-gpg." + "x" * 8) / "S.gpg-agent.browser"))) < 103,
            "GPG socket path is too long; use a shorter physical P2PKIT_GPG_TMPDIR")
    require(not (c["evidence"] / (role + "-home.json")).exists(), "GPG role already allocated")
    path = Path(tempfile.mkdtemp(prefix="p2pkit-gpg.", dir=parent))
    path.chmod(0o700)
    # If evidence cannot be written, print only the reachable path, not secret data.
    try:
        record = {
            "schema": 1, "role": role, "path": str(path), "identity": identity(path),
            "admissionSha256": digest(read_bytes(c["evidence"] / "admission.json")),
            "outerId": a["outerId"], "ownershipDomains": c["domains"],
            "retirement": "REQUIRES_ENCLOSING_CANONICAL_RECEIPT"}
        write_json(path / "p2pkit-home-owner.json", record)
        write_json(c["evidence"] / (role + "-home.json"), record)
    except BaseException:
        print("HOLD: unrecorded owned GPG home retained at " + str(path), file=sys.stderr)
        raise
    print(path)


def home_record(c, role, a):
    record = read_json(c["evidence"] / (role + "-home.json"))
    path = physical(record["path"])
    require(record.get("role") == role and record.get("identity") == identity(path) and
            record.get("ownershipDomains") == a["ownershipDomains"] and stat.S_IMODE(path.stat().st_mode) == 0o700,
            "GPG home ownership changed")
    require(record == read_json(path / "p2pkit-home-owner.json") and record.get("outerId") == a["outerId"] and
            record.get("admissionSha256") == digest(read_bytes(c["evidence"] / "admission.json")),
            "GPG home does not retain its original allocation binding")
    return record, path


def stop_home(c, role):
    a = admission(c)
    record, path = home_record(c, role, a)
    command = ["gpgconf", "--homedir", str(path), "--kill", "all"]
    status, error = None, None
    try:
        with (c["work"] / (role + "-stop.stdout.log")).open("xb") as out, \
                (c["work"] / (role + "-stop.stderr.log")).open("xb") as err:
            status = subprocess.run(command, stdout=out, stderr=err, timeout=30).returncode
    except (OSError, subprocess.SubprocessError) as problem:
        error = type(problem).__name__
    write_json(c["evidence"] / (role + "-stop.json"), {
        "schema": 1, "role": role, "homeSha256": digest(read_bytes(c["evidence"] / (role + "-home.json"))),
        "argv": command, "exitCode": status, "errorType": error,
        "nativeRetirement": "REQUIRES_ENCLOSING_CANONICAL_RECEIPT"})
    require(status == 0 and error is None, "GPG stop failed; reachable owned home retained")


def builder(c, root, output):
    f = check_fixture(c, before_publication=True)
    require(physical(root) == c["fixture"] and output == str(c["work"] / "p2pkit-test-central-bundle.zip"),
            "builder source/output is not the admitted fixture")
    require(Path(__file__).resolve() in (c["root"] / HELPER, c["fixture"] / HELPER), "unexpected builder helper")
    require(not c["repository"].exists(), "publication repository is not fresh")
    key = read_bytes(c["work"] / "key.asc")
    require(key and not os.environ.get("ORG_GRADLE_PROJECT_signingInMemoryKey") and
            os.environ.get("ORG_GRADLE_PROJECT_signingInMemoryKeyBase64") == base64.b64encode(key).decode() and
            os.environ.get("ORG_GRADLE_PROJECT_signingInMemoryKeyPassword") == PASSWORD,
            "builder signing input differs from this disposable fixture")
    fingerprint = os.environ.get("MAVEN_SIGNING_KEY_FINGERPRINT", "")
    require(re.fullmatch(r"[A-F0-9]{40}", fingerprint), "invalid disposable public fingerprint")
    c["repository"].mkdir(mode=0o700)
    (c["work"] / "signatures").mkdir(mode=0o700)
    write_json(c["evidence"] / "builder-admission.json", {
        "schema": 1, "fixtureSha256": digest(read_bytes(c["evidence"] / "fixture.json")),
        "repositoryIdentity": identity(c["repository"]), "output": output,
        "version": f["version"], "fingerprint": fingerprint})
    print(c["root"])


def publish_arguments(c):
    return ["--no-daemon", "--no-build-cache", "--rerun-tasks", "--console=plain", "-p", str(c["fixture"]),
            "publishToMavenLocal", "-PsigningInMemoryKey=", "-PreleasePublication=true",
            "-Dmaven.repo.local=" + str(c["repository"])]


def canonical_receipt(c, path, status, purpose, arguments, kind, ancestors):
    raw = read_bytes(path)
    receipt = read_json(path)
    load_module(c["root"], "check-audit-receipt").validate(
        receipt, status, purpose, str(c["root"]), str(c["root"] / "gradlew"), arguments)
    identifier = receipt["id"]
    require(re.fullmatch(r"[0-9a-f]{32}", identifier), "invalid canonical invocation id")
    directory = physical(c["state"] / "evidence" / identifier)
    require(raw == read_bytes(directory / "receipt.json") and receipt.get("evidenceDirectory") == str(directory),
            "optional and original canonical receipts differ")
    require(receipt.get("kind") == kind and receipt.get("jobId") == c["value"]["id"] and
            receipt.get("gradleHome") == str(c["home"]) and receipt.get("host") == c["value"]["host"] and
            receipt.get("sourceBefore") == c["source"] and receipt.get("ancestorInvocationIds") == ancestors,
            "receipt source/context/home/ancestor binding differs")
    ownership = receipt.get("ownership", {})
    require(ownership.get("backend") == BACKENDS[c["value"]["host"]] and ownership.get("job") == c["value"]["id"] and
            ownership.get("invocation") == identifier and ownership.get("discoveryErrors") == [],
            "receipt lacks matching known native ownership finalization")
    start = read_json(directory / "start.json")
    for field in ("schema", "id", "kind", "purpose", "cwd", "wrapper", "jobId", "gradleHome", "requestedArgv",
                  "ancestorInvocationIds"):
        require(start.get(field) == receipt.get(field), "original start/final receipt binding differs: " + field)
    return receipt, directory


def publish(c):
    check_fixture(c, before_publication=True)
    b = read_json(c["evidence"] / "builder-admission.json")
    require(b["fixtureSha256"] == digest(read_bytes(c["evidence"] / "fixture.json")) and
            b["repositoryIdentity"] == identity(c["repository"]), "publication repository/builder binding changed")
    require({path.name for path in c["repository"].iterdir()} == {"release-key.asc"} and
            read_bytes(c["repository"] / "release-key.asc") == read_bytes(c["work"] / "key.asc"),
            "pre-publication repository contains inputs not created by this disposable signer")
    requested = publish_arguments(c)
    command = [sys.executable, str(c["root"] / "scripts/run-audit-command.py"), "--cwd", str(c["root"]),
               "--wrapper", str(c["root"] / "gradlew"), "--kind", "gradle", "--purpose", PURPOSE,
               "--timeout", "3600", "--receipt", str(c["evidence"] / "publish.json"), "--", *requested]
    write_json(c["evidence"] / "publish-request.json", {
        "schema": 1, "argv": command, "fixtureSha256": digest(read_bytes(c["evidence"] / "fixture.json"))})
    # The maintained leaf owns timeout/cancellation, same-home stop, lease and
    # native drain. Do not race it with an independent process-killing backend.
    result = subprocess.run(command, cwd=c["root"])
    errors = []
    try:
        canonical_receipt(c, c["evidence"] / "publish.json", result.returncode, PURPOSE, requested, "gradle",
                          [row["id"] for row in c["domains"]])
    except (OSError, ValueError, TypeError, KeyError) as error:
        errors.append("canonical receipt: " + type(error).__name__)
    try:
        check_fixture(c)
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as error:
        errors.append("post-publication fixture: " + type(error).__name__)
    write_json(c["evidence"] / "publish-validation.json", {
        "schema": 1, "invocationExitCode": result.returncode, "errors": errors,
        "finalExitCode": 125 if errors else result.returncode})
    return 125 if errors else result.returncode


def signature(c, args):
    a = read_json(c["evidence"] / "builder-admission.json")
    name = PurePosixPath(args.artifact)
    require(not name.is_absolute() and ".." not in name.parts and "\\" not in args.artifact,
            "invalid signature artifact path")
    status = physical(args.status_file, directory=False)
    require(status.parent == c["work"] / "signatures" and re.fullmatch(r"[1-9][0-9]*\.status", status.name),
            "signature status is not the owned observation")
    require(args.fingerprint == "" or re.fullmatch(r"[A-F0-9]{40,64}", args.fingerprint), "invalid observed fingerprint")
    write_json(status.with_suffix(".json"), {
        "schema": 1, "artifact": args.artifact, "statusFile": status.name, "statusSha256": digest(read_bytes(status)),
        "exitCode": args.status, "fingerprint": args.fingerprint,
        "expectedFingerprint": a["fingerprint"], "valid": args.status == 0 and args.fingerprint == a["fingerprint"]})


def finish_builder(c, status):
    stop = read_json(c["evidence"] / "verifier-stop.json") if (c["evidence"] / "verifier-stop.json").exists() else None
    write_json(c["evidence"] / "builder-result.json", {
        "schema": 1, "productExitCode": status, "verifierStopExitCode": stop["exitCode"] if stop else None,
        "nativeRetirement": "REQUIRES_ENCLOSING_CANONICAL_RECEIPT"})


def bundle_check(c):
    f = check_fixture(c)
    a = read_json(c["evidence"] / "builder-admission.json")
    output = c["work"] / "p2pkit-test-central-bundle.zip"
    manifest = output.with_suffix(".manifest.sha256")
    summary = read_json(output.with_suffix(".summary.json"))
    product = file_record(output)
    require(product["bytes"] < 1073741824, "bundle exceeds original 1 GiB upload bound")
    rows = {}
    for line in read_bytes(manifest).decode().splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        require(match, "invalid bundle manifest line")
        sha, name = match.groups()
        path = PurePosixPath(name)
        require(not path.is_absolute() and ".." not in path.parts and "\\" not in name and name not in rows,
                "unsafe/duplicate bundle manifest path")
        rows[name] = sha
    group = f["group"].replace(".", "/")
    files = walk_files(physical(c["repository"] / group))
    actual = {str(path.relative_to(c["repository"])): file_record(path)["sha256"] for path in files}
    require(rows and rows == actual, "actual publication and manifest differ")
    signed = [name for name in rows if not name.endswith((".asc", ".md5", ".sha1", ".sha256", ".sha512"))]
    for name in signed:
        hashes = {algorithm: hashlib.new(algorithm) for algorithm in ("md5", "sha1", "sha256", "sha512")}
        with (c["repository"] / name).open("rb") as stream:
            for chunk in iter(lambda: stream.read(512 * 1024), b""):
                for value in hashes.values():
                    value.update(chunk)
        for algorithm, value in hashes.items():
            require(read_bytes(c["repository"] / (name + "." + algorithm)) == (value.hexdigest() + "\n").encode(),
                    "publication checksum sidecar differs from actual bytes")
    expected = {"schemaVersion": 1, "group": f["group"], "version": f["version"], "signingKeyFingerprint": a["fingerprint"],
                "bundleFile": output.name, "bundleSha256": product["sha256"], "bundleSizeBytes": product["bytes"],
                "signedFiles": len(signed)}
    require(summary == expected and signed, "bundle summary differs from actual bytes/identity")
    signatures = [read_json(path) for path in sorted((c["work"] / "signatures").glob("*.json"))]
    require(len(signatures) == len(signed) and {row["artifact"] for row in signatures} == set(signed) and
            all(row["valid"] is True and row["exitCode"] == 0 and row["fingerprint"] == a["fingerprint"] and
                digest(read_bytes(c["work"] / "signatures" / row["statusFile"])) == row["statusSha256"]
                for row in signatures), "missing/failed original signature observations")
    with zipfile.ZipFile(output) as archive:
        members = [row for row in archive.infolist() if not row.is_dir()]
        require(len(members) == len(rows) and len({row.filename for row in members}) == len(rows) and
                {row.filename for row in members} == set(rows) and sum(row.file_size for row in members) <= 2 * 1073741824,
                "ZIP membership/size differs from manifest")
        for row in members:
            sha = hashlib.sha256()
            with archive.open(row) as stream:
                for chunk in iter(lambda: stream.read(512 * 1024), b""):
                    sha.update(chunk)
            require(sha.hexdigest() == rows[row.filename], "ZIP bytes differ from manifest")
    return {"sha256": product["sha256"], "bytes": product["bytes"], "zipBytesRetained": False,
            "retention": "original summary/manifest, signature observations and ZIP hash/size; not ZIP bytes"}


def secret_needles(c):
    values = [PASSWORD.encode(), b"-----BEGIN PGP PRIVATE KEY BLOCK-----"]
    for path in (c["work"] / "key.asc", c["repository"] / "release-key.asc"):
        BOUND_CHECK()
        if path.exists():
            key = read_bytes(path)
            values.extend([key, base64.b64encode(key)])
            values.extend(line for line in key.splitlines() if len(line) >= 32)
    needles = set()
    for value in values:
        for offset in range(0, len(value), 128):
            BOUND_CHECK()
            part = value[offset:offset + 128]
            if len(part) >= 16:
                needles.add(part)
    return needles


def safe_file(path, needles):
    tail = b""
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(512 * 1024), b""):
            data = tail + chunk
            require(not any(needle in data for needle in needles), "credential fragment in original evidence; quarantine required")
            tail = data[-256:]


def retain(c):
    needles, selected = secret_needles(c), []
    for path in sorted(c["work"].glob("*.log")):
        selected.append(("logs/" + path.name, path))
    for suffix in ("manifest.sha256", "summary.json"):
        path = c["work"] / ("p2pkit-test-central-bundle." + suffix)
        if path.exists():
            selected.append((path.name, path))
    if (c["work"] / "signatures").exists():
        selected.extend(("signatures/" + path.name, path) for path in walk_files(c["work"] / "signatures"))
    if (c["evidence"] / "fixture.json").exists() and c["fixture"].exists():
        f = read_json(c["evidence"] / "fixture.json")
        for output in f["outputRoots"]:
            for name in ("reports", "test-results"):
                path = c["fixture"] / output / name
                if path.exists():
                    selected.extend(("reports/" + str(item.relative_to(c["fixture"])), item) for item in walk_files(physical(path)))
    if c["repository"].exists():
        group, _ = coordinates(read_bytes(c["root"] / "gradle.properties"))
        path = c["repository"] / group.replace(".", "/")
        if path.exists():
            # Retain selected actual publication metadata, not only its hashes.
            # Binary artifacts, signatures and transient key exports stay out.
            selected.extend(("metadata/" + str(item.relative_to(c["repository"])), item)
                            for item in walk_files(physical(path)) if item.suffix in (".pom", ".module"))
    # Retain exact original leaf files, including a failed receipt. Validation is
    # separate: a failed/missing receipt must not erase its decisive diagnostics.
    if (c["evidence"] / "publish.json").exists():
        r = read_json(c["evidence"] / "publish.json")
        require(re.fullmatch(r"[0-9a-f]{32}", r.get("id", "")), "invalid publication evidence id")
        directory = physical(c["state"] / "evidence" / r["id"])
        for name in ("start.json", "receipt.json", "product.stdout.log", "product.stderr.log", "stop.stdout.log", "stop.stderr.log"):
            path = directory / name
            if path.exists():
                selected.append(("publication/" + name, path))
    require(len(selected) <= MAX_FILES, "excessive selected evidence")
    records, total = [], 0
    # Validate and scan every selected original before copying any log. Originals
    # remain private/reachable on failure; do not sanitize and relabel them.
    for name, path in selected:
        row = file_record(path)
        total += row["bytes"]
        require(total <= MAX_RETAINED_BYTES, "selected evidence exceeds retention bound")
        safe_file(path, needles)
        records.append({"name": name, "source": str(path), **row})
    destination = c["evidence"] / "originals"
    destination.mkdir(mode=0o700)
    for row in records:
        path, target = Path(row["source"]), destination / row["name"]
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with path.open("rb") as source, target.open("xb") as out:
            shutil.copyfileobj(source, out, 512 * 1024)
        target.chmod(0o444)
        require(file_record(target)["sha256"] == row["sha256"] and file_record(path)["sha256"] == row["sha256"],
                "original evidence changed during retention")
    write_json(c["evidence"] / "retained.json", {"schema": 1, "files": records, "bytes": total})


def finish(c, status, phase):
    a = admission(c)
    errors, bundle = [], None
    if status == 0:
        try:
            bundle = bundle_check(c)
            require(read_json(c["evidence"] / "publish-validation.json")["finalExitCode"] == 0,
                    "publication did not pass its exact fixture/receipt checks")
        except (OSError, ValueError, TypeError, KeyError, zipfile.BadZipFile, subprocess.SubprocessError) as error:
            errors.append("bundle/fixture verification: " + type(error).__name__)
    stops = {}
    for role in ("signer", "verifier"):
        if (c["evidence"] / (role + "-home.json")).exists():
            try:
                home_record(c, role, a)
                stop = read_json(c["evidence"] / (role + "-stop.json"))
                stops[role] = stop["exitCode"]
                require(stop["exitCode"] == 0 and stop["errorType"] is None, "GPG stop failed")
            except (OSError, ValueError, TypeError, KeyError) as error:
                errors.append(role + " stop: " + type(error).__name__)
    retained = False
    try:
        retain(c)
        retained = True
    except (OSError, ValueError, TypeError, KeyError) as error:
        errors.append("original retention/quarantine: " + type(error).__name__)
    code = 125 if errors else status
    bindings = {path.name: digest(read_bytes(path)) for path in c["evidence"].glob("*.json")}
    write_json(c["evidence"] / "result.json", {
        "schema": 1, "outerId": a["outerId"], "productExitCode": status, "phase": phase,
        "gpgStopExitCodes": stops, "retentionStatus": "RETAINED" if retained else "HOLD_PRIVATE_QUARANTINE",
        "errors": errors, "finalExitCode": code, "bundle": bundle, "metadataBindings": bindings,
        "nativeRetirement": "REQUIRES_ENCLOSING_CANONICAL_RECEIPT", "workRemoved": False})
    return code


def retire(c, receipt_path, *, prepare_only=False):
    a = admission(c, active=False)
    r = read_json(c["evidence"] / "result.json")
    require(r["outerId"] == a["outerId"] and r["retentionStatus"] == "RETAINED" and r["errors"] == [],
            "failed/missing retention or stop remains a HOLD; do not remove reachable work")
    for name, sha in r["metadataBindings"].items():
        require(digest(read_bytes(c["evidence"] / name)) == sha, "retained metadata changed")
    receipt, directory = canonical_receipt(c, physical(receipt_path, directory=False), r["finalExitCode"],
                                         a["outerStart"]["purpose"], a["outerStart"]["requestedArgv"], "command",
                                         a["outerStart"]["ancestorInvocationIds"])
    require(receipt["id"] == a["outerId"], "retirement requires this exact enclosing command receipt")
    homes = []
    for role in ("signer", "verifier"):
        if role in r["gpgStopExitCodes"]:
            record, path = home_record(c, role, a)
            stop = read_json(c["evidence"] / (role + "-stop.json"))
            require(stop["exitCode"] == 0 and stop["errorType"] is None and
                    stop["argv"] == ["gpgconf", "--homedir", str(path), "--kill", "all"] and
                    stop["homeSha256"] == digest(read_bytes(c["evidence"] / (role + "-home.json"))),
                    "original per-home GPG stop evidence differs")
            homes.append(path)
    retained = read_json(c["evidence"] / "retained.json")
    for row in retained["files"]:
        require(file_record(c["evidence"] / "originals" / row["name"])["sha256"] == row["sha256"],
                "retained original bytes changed before cleanup")
    if c["fixture"].exists():
        # Failed source mutation remains inspectable; cleanup must not hide it.
        check_fixture_for_retirement(c)
    allowed = {"release-source", "repository", "signatures", "key.asc", "p2pkit-test-central-bundle.zip",
               "p2pkit-test-central-bundle.manifest.sha256", "p2pkit-test-central-bundle.summary.json",
               "snapshot.log", "missing-key.log", "keygen.log", "bundle.log", "worktree.stdout.log", "worktree.stderr.log",
               "signer-stop.stdout.log", "signer-stop.stderr.log", "verifier-stop.stdout.log", "verifier-stop.stderr.log"}
    require(all(path.name in allowed and not path.is_symlink() for path in c["work"].iterdir()),
            "unexpected borrowed work entry; preserve it")
    write_json(c["evidence"] / "retirement-admission.json", {
        "schema": 1, "outerReceiptSha256": digest(read_bytes(directory / "receipt.json")),
        "resultSha256": digest(read_bytes(c["evidence"] / "result.json")), "nativeRetirement": "KNOWN",
        "authority": "original enclosing canonical native ownership/stop receipt", "homePaths": [str(path) for path in homes]})
    if c["fixture"].exists():
        removal = {"argv": ["git", "-C", str(c["root"]), "worktree", "remove", "--force", str(c["fixture"])],
                   "exitCode": None, "errorType": None}
        registry = {"argv": ["git", "-C", str(c["root"]), "worktree", "list", "--porcelain", "-z"],
                    "exitCode": None, "errorType": None}
        for observation, prefix in ((removal, "worktree-remove"), (registry, "worktree-registry")):
            # Direct files preserve partial original output even on timeout.
            try:
                with (c["evidence"] / (prefix + ".stdout.log")).open("xb") as out, \
                        (c["evidence"] / (prefix + ".stderr.log")).open("xb") as err:
                    observation["exitCode"] = subprocess.run(observation["argv"], stdout=out, stderr=err,
                                                             timeout=BOUND_REMAINING()).returncode
                    BOUND_CHECK()
            except (OSError, subprocess.SubprocessError) as error:
                observation["errorType"] = type(error).__name__
            for suffix in (".stdout.log", ".stderr.log"):
                path = c["evidence"] / (prefix + suffix)
                if path.is_file():
                    path.chmod(0o444)
        path_absent, path_error, registry_absent = None, None, None
        try:
            c["fixture"].lstat()
            path_absent = False
        except FileNotFoundError:
            path_absent = True
        except OSError as error:
            path_error = type(error).__name__
        if registry["exitCode"] == 0 and registry["errorType"] is None:
            try:
                raw = read_bytes(c["evidence"] / "worktree-registry.stdout.log")
                paths = [field[len(b"worktree "):] for field in raw.split(b"\0") if field.startswith(b"worktree ")]
                require(raw.endswith(b"\0") and os.fsencode(c["root"]) in paths, "invalid worktree registry observation")
                registry_absent = os.fsencode(c["fixture"]) not in paths
            except (OSError, ValueError) as error:
                registry["errorType"] = type(error).__name__
        # Preserve exact failure/unknown observations before deciding whether
        # any reachable homes or remaining borrowed work may be removed.
        write_json(c["evidence"] / "worktree-removal.json", {
            "schema": 1, **removal, "pathAbsent": path_absent, "pathErrorType": path_error,
            "registry": registry, "registryAbsent": registry_absent})
        require(removal["exitCode"] == 0 and removal["errorType"] is None and path_absent is True and
                registry["exitCode"] == 0 and registry["errorType"] is None and registry_absent is True,
                "owned worktree removal/registry retirement failed")
    if prepare_only:
        require(BOUND_RAW_END is not None, "bounded prepare-only retirement required")
        # Keep actual key inputs and homes reachable while the enclosing native
        # helper/stop captures close. The controller screens them before removal.
        keys = key_input_records(c, r)
        write_json(c["evidence"] / "retirement-prepared.json", {
            "schema": 1, "scope": "CENTRAL_POST_RETURN_PREPARED_NOT_REMOVED", "contextSha256": c["contextSha256"],
            "source": c["source"], "workIdentity": a["workIdentity"], "outerId": a["outerId"],
            "outerReceiptSha256": digest(read_bytes(directory / "receipt.json")),
            "admissionSha256": digest(read_bytes(c["evidence"] / "admission.json")),
            "resultSha256": digest(read_bytes(c["evidence"] / "result.json")),
            "deadlineRawNs": BOUND_RAW_END, "keyInputs": keys,
            "homes": [{"path": str(path), "identity": identity(path)} for path in homes],
            "metadata": {path.name: file_record(path) for path in sorted(c["evidence"].glob("*.json"))}})
        return
    for path in homes:
        shutil.rmtree(path)
        require(not path.exists(), "owned GPG home removal failed")
    require(identity(c["work"]) == a["workIdentity"], "borrowed work was replaced before removal")
    shutil.rmtree(c["work"])
    require(not c["work"].exists(), "borrowed work removal failed")
    write_json(c["evidence"] / "retirement.json", {
        "schema": 1, "nativeRetirement": "KNOWN", "workRemoved": True, "gpgHomesRemoved": True,
        "outerReceiptSha256": digest(read_bytes(directory / "receipt.json")),
        "productExitCode": r["productExitCode"], "productPassed": r["finalExitCode"] == 0})


def key_input_records(c, result):
    BOUND_CHECK()
    expected = []
    if "signer" in result["gpgStopExitCodes"]:
        expected.append(c["work"] / "key.asc")
    if (c["evidence"] / "builder-admission.json").exists():
        expected.append(c["repository"] / "release-key.asc")
    for path in (c["work"] / "key.asc", c["repository"] / "release-key.asc"):
        if path.exists() and path not in expected:
            expected.append(path)
    records = []
    for path in expected:
        BOUND_CHECK()
        data = read_bytes(path)
        require(data, "original disposable key input missing; quarantine required")
        records.append({"relative": str(path.relative_to(c["work"])), "sha256": digest(data), "bytes": len(data)})
    return records


def complete_prepared_retirement(c, prepared_raw, *, check):
    """File-only tail, called by the same owning controller after closed-stream screening.

    No CLI exposes this removal authority. The caller holds the original native
    return and exact prepare bytes; revalidate original inactive O and every
    admitted path/content here, without impersonating O or launching a child.
    """
    global BOUND_CHECK
    old_check = BOUND_CHECK
    BOUND_CHECK = check
    try:
        check()
        require(read_bytes(c["evidence"] / "retirement-prepared.json") == prepared_raw, "Central prepare original changed")
        prepared = json.loads(prepared_raw, object_pairs_hook=unique)
        a, r = read_json(c["evidence"] / "admission.json"), read_json(c["evidence"] / "result.json")
        require(prepared["schema"] == 1 and prepared["scope"] == "CENTRAL_POST_RETURN_PREPARED_NOT_REMOVED" and
                prepared["contextSha256"] == c["contextSha256"] and prepared["source"] == c["source"] and
                prepared["outerId"] == a["outerId"] == r["outerId"] and prepared["workIdentity"] == identity(c["work"]) == a["workIdentity"] and
                a["root"] == str(c["root"]) and a["state"] == str(c["state"]) and a["work"] == str(c["work"]) and
                prepared["admissionSha256"] == digest(read_bytes(c["evidence"] / "admission.json")) and
                prepared["resultSha256"] == digest(read_bytes(c["evidence"] / "result.json")) and
                r["retentionStatus"] == "RETAINED" and r["errors"] == [], "Central original prepare authority changed")
        for name, record in prepared["metadata"].items():
            require(Path(name).name == name and name.endswith(".json") and file_record(c["evidence"] / name) == record,
                    "Central original prepare metadata changed")
        for name, record in a["trackedSource"].items():
            require(file_record(c["root"] / name) == record, "Central source changed after prepare")
        receipt, directory = canonical_receipt(c, c["state"] / "evidence" / a["outerId"] / "receipt.json", r["finalExitCode"],
            a["outerStart"]["purpose"], a["outerStart"]["requestedArgv"], "command", a["outerStart"]["ancestorInvocationIds"])
        require(digest(read_bytes(directory / "receipt.json")) == prepared["outerReceiptSha256"] and
                not c["fixture"].exists() and key_input_records(c, r) == prepared["keyInputs"],
                "Central source/keys/outer changed before removal")
        homes = []
        for role in ("signer", "verifier"):
            if role in r["gpgStopExitCodes"]:
                _record, path = home_record(c, role, a)
                homes.append(path)
        require([{ "path": str(path), "identity": identity(path)} for path in homes] == prepared["homes"],
                "Central prepared home roster changed")
        for path, expected in zip(homes, prepared["homes"]):
            remove_bounded_tree(path, expected["identity"], check)
        require(identity(c["work"]) == a["workIdentity"], "Central work replaced before removal")
        remove_bounded_tree(c["work"], a["workIdentity"], check)
        check()
        return {"schema": 1, "workRemoved": not os.path.lexists(c["work"]),
                "gpgHomesRemoved": all(not os.path.lexists(path) for path in homes),
                "preparedSha256": digest(prepared_raw), "outerReceiptSha256": prepared["outerReceiptSha256"],
                "productExitCode": r["productExitCode"], "productPassed": r["finalExitCode"] == 0}
    finally:
        BOUND_CHECK = old_check


def remove_bounded_tree(path, expected, check):
    """Only a previously admitted Central root; no new process or cleanup lease.

    Open the actual physical ancestor chain and root BEFORE walking. fwalk and
    all deletions are fd-relative, never a path-following recursive remover. The
    original root must still name that same object before each destructive step;
    an unverified replacement is not disposable. Symlink children are unlinked,
    not entered. Every operation shares the caller's original RAW transaction.
    """
    require(os.name == "posix" and path.is_absolute() and path != Path("/") and ".." not in path.parts and
            type(expected) is dict and set(expected) == {"device", "inode"}, "Central removal original root required")
    handles, anchors, walker, failure = [], [], None, None
    def stamp(info):
        return info.st_dev, info.st_ino, info.st_mode
    def guard():
        check()
        for original, record in anchors:
            require(stamp(original.lstat()) == record and stat.S_ISDIR(record[2]), "Central removal ancestor replaced")
        if handles and len(anchors) == len(path.parts):
            info = os.fstat(handles[-1])
            require({"device": info.st_dev, "inode": info.st_ino} == expected and
                    stamp(os.stat(path.name, dir_fd=handles[-2], follow_symlinks=False)) == stamp(info),
                    "Central removal original root replaced")
    try:
        current = Path("/")
        for part in path.parts:
            check()
            if part != "/":
                current = current / part
            before = current.lstat()
            require(stat.S_ISDIR(before.st_mode) and not stat.S_ISLNK(before.st_mode), "Central removal physical ancestor required")
            fd = os.open("/" if part == "/" else part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                         **({"dir_fd": handles[-1]} if handles else {}))
            handles.append(fd)
            require(stamp(os.fstat(fd)) == stamp(before), "Central removal opened ancestor changed")
            anchors.append((current, stamp(before)))
        guard()
        require(len(handles) > 1 and stat.S_IMODE(os.fstat(handles[-1]).st_mode) == 0o700,
                "Central removal private original root required")
        # Bound depth/count before bottom-up fwalk can descend to its first
        # yield. This read-only preflight grants no path-based deletion rights.
        walk_files(path, check=guard)
        guard()
        walker = os.fwalk(".", topdown=False, follow_symlinks=False, dir_fd=handles[-1])
        count = 0
        for relative, directories, leaves, fd in walker:
            guard()
            require(len(Path(relative).parts) <= 64, "Central removal nesting bound")
            for name in [*leaves, *directories]:
                guard()
                count += 1
                require(count <= MAX_FILES, "Central removal entry bound")
                info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                if stat.S_ISDIR(info.st_mode):
                    os.rmdir(name, dir_fd=fd)
                else:
                    require(stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode), "Central removal special entry")
                    os.unlink(name, dir_fd=fd)
                guard()
        guard()
        os.rmdir(path.name, dir_fd=handles[-2])
        check()
        require(not os.path.lexists(path), "Central removed root replaced")
    except BaseException as error:
        failure = error
    finally:
        # No ambiguous descriptor close is retried. UNKNOWN is carried through
        # the maintained controller exception graph and blocks further removal.
        if walker is not None:
            try:
                walker.close()
            except BaseException as error:
                failure = failure or error
                failure.__notes__ = [*getattr(failure, "__notes__", ()), "Central fwalk retirement UNKNOWN"]
        for fd in reversed(handles):
            try:
                os.close(fd)
            except BaseException as error:
                failure = failure or error
                failure.__notes__ = [*getattr(failure, "__notes__", ()), "Central removal descriptor retirement UNKNOWN"]
        try:
            check()
        except BaseException as error:
            failure = failure or error
    if failure is not None:
        raise failure


def check_fixture_for_retirement(c):
    # The same byte checks apply after the outer command, without impersonating
    # its now-finished environment/ownership domain.
    c = dict(c)
    c["domains"] = read_json(c["evidence"] / "admission.json")["ownershipDomains"]
    check_fixture(c)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("admit", "fixture", "home", "stop", "builder", "publish", "signature",
                                           "finish-builder", "finish", "retire", "prepare-retire"))
    parser.add_argument("--root")
    parser.add_argument("--output")
    parser.add_argument("--role", choices=("signer", "verifier"))
    parser.add_argument("--status", type=int)
    parser.add_argument("--phase")
    parser.add_argument("--artifact")
    parser.add_argument("--status-file")
    parser.add_argument("--fingerprint")
    parser.add_argument("--outer-receipt")
    parser.add_argument("--deadline-raw-ns", type=int)
    args = parser.parse_args()
    try:
        if args.action == "prepare-retire":
            bounded_retirement(args.deadline_raw_ns)
        else:
            require(args.deadline_raw_ns is None, "Central deadline applies only to bounded prepare retirement")
        c = context(active=args.action not in ("retire", "prepare-retire"))
        if args.action == "admit":
            admit(c, args.root)
        elif args.action == "fixture":
            fixture(c)
        elif args.action == "home":
            require(args.role in ("signer", "verifier"), "GPG role required")
            allocate_home(c, args.role)
        elif args.action == "stop":
            require(args.role in ("signer", "verifier"), "GPG role required")
            stop_home(c, args.role)
        elif args.action == "builder":
            builder(c, args.root, args.output)
        elif args.action == "publish":
            return publish(c)
        elif args.action == "signature":
            signature(c, args)
        elif args.action == "finish-builder":
            finish_builder(c, args.status)
        elif args.action == "finish":
            return finish(c, args.status, args.phase)
        else:
            retire(c, args.outer_receipt, prepare_only=args.action == "prepare-retire")
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError, zipfile.BadZipFile) as error:
        # Do not dump child output or key-bearing values on exceptional paths.
        print("HOLD: Central bundle adapter: " + type(error).__name__ + ": " +
              (str(error) if isinstance(error, ValueError) else "operation failed; originals retained"), file=sys.stderr)
        return 125
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
