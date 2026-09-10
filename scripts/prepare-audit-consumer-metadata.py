#!/usr/bin/env python3
"""Prepare strict metadata for an explicitly opted-in source-local audit consumer.

The shell gate calls admit before publication, prepare after its successful owned
executor receipt, then verify after the consumer and its original inspectors.
All paths are caller-owned, absolute, physical paths. Evidence lives below the
initialized P2PKIT_AUDIT_STATE_DIR, outside the disposable consumer directory.

This helper never resolves dependencies, downloads checksums, adds broad trust,
changes source metadata, or substitutes for check-publish-artifacts.sh. Its first
read of source-built publications assumes exclusive access to the just-admitted
empty repository through publication and preparation. The executor must finish
its source check, wrapper stop, and owned-worker drain before returning a receipt.
Subsequent verification rejects changed/missing/extra publication bytes and any
change to the copied external allowlist. External authenticity remains that of
the reviewed committed allowlist; hosted consumers are not release acceptance.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from datetime import datetime, timezone
import uuid
import xml.etree.ElementTree as ET
from xml.sax.saxutils import quoteattr


# Independent narrow publication-shape policy; review together with the 15
# check() calls/expanded iOS loop in scripts/check-publish-artifacts.sh. Do not
# replace this with a scan that trusts any file found in a Maven repository.
PUBLICATIONS = {
    "p2p-core": ".jar",
    "p2p-core-jvm": ".jar",
    "p2p-core-android": ".aar",
    "p2p-core-iosarm64": ".klib",
    "p2p-core-iossimulatorarm64": ".klib",
    "p2p-core-iosx64": ".klib",
    "p2p-transport-lan": ".jar",
    "p2p-transport-lan-jvm": ".jar",
    "p2p-transport-lan-android": ".aar",
    "p2p-transport-lan-iosarm64": ".klib",
    "p2p-transport-lan-iossimulatorarm64": ".klib",
    "p2p-transport-lan-iosx64": ".klib",
    "p2p-network-provisioning-android": ".jar",
    "p2p-network-provisioning-android-android": ".aar",
    "p2p-network-provisioning-desktop": ".jar",
}
# Native publications also carry their shared metadata and LAN's named C interop.
# These are dependency inputs, not optional tooling sidecars. Keep each admitted
# coordinate/classifier explicit and include its checksum in the local allowlist.
NATIVE_ARTIFACT_SUFFIXES = {
    "p2p-core-iosarm64": ("-metadata.jar",),
    "p2p-core-iossimulatorarm64": ("-metadata.jar",),
    "p2p-core-iosx64": ("-metadata.jar",),
    "p2p-transport-lan-iosarm64": ("-metadata.jar", "-cinterop-p2pkit_nw.klib"),
    "p2p-transport-lan-iossimulatorarm64": ("-metadata.jar", "-cinterop-p2pkit_nw.klib"),
    "p2p-transport-lan-iosx64": ("-metadata.jar", "-cinterop-p2pkit_nw.klib"),
}
CONSUMER_TASKS = [
    ":coreJvm:compileKotlin",
    ":coreJvm:compileJava",
    ":lanJvm:compileKotlin",
    ":desktopJvm:compileKotlin",
    ":androidConsumer:compileDebugKotlin",
    ":androidConsumer:processDebugManifest",
    ":kmpConsumer:compileKotlinJvm",
    ":kmpConsumer:compileAndroidMain",
    ":kmpConsumer:compileKotlinIosSimulatorArm64",
    ":kmpConsumer:linkDebugFrameworkIosSimulatorArm64",
]
NAMESPACE = "https://schema.gradle.org/dependency-verification"
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
MAX_DOCUMENT_BYTES = 16 * 1024 * 1024


class Rejected(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Rejected(message)


def sha256(value):
    return hashlib.sha256(value).hexdigest()


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def physical_directory(value):
    path = Path(value)
    require(path.is_absolute() and not path.is_symlink(), f"not an absolute real directory: {path}")
    require(path.resolve(strict=True) == path and path.is_dir(), f"not a physical directory: {path}")
    return path


def bounded_bytes(path):
    require(not path.is_symlink() and path.is_file(), f"not a regular input file: {path}")
    require(path.parent.resolve(strict=True) == path.parent, f"input has a symlink/nonphysical parent: {path}")
    with path.open("rb") as stream:
        data = stream.read(MAX_DOCUMENT_BYTES + 1)
    require(len(data) <= MAX_DOCUMENT_BYTES, f"input exceeds document limit: {path}")
    return data


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def parse_json(data):
    return json.loads(data.decode("utf-8"), object_pairs_hook=unique_object)


def read_json(path):
    value = parse_json(bounded_bytes(path))
    require(isinstance(value, dict), f"expected JSON object: {path}")
    return value


def write_new(path, data):
    # Never replace evidence or follow a supplied leaf symlink. Failed/partial
    # creation remains evidence instead of being silently overwritten/retried.
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    path.chmod(0o444)


def write_json(path, value):
    write_new(path, (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def git(root, *arguments):
    return subprocess.run(
        ["git", "-C", str(root), *arguments], check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ).stdout


def source_snapshot(root):
    require(git(root, "rev-parse", "--show-toplevel").decode().strip() == str(root), "root is not the Git root")
    result = {
        "commit": git(root, "rev-parse", "HEAD").decode().strip(),
        "tree": git(root, "rev-parse", "HEAD^{tree}").decode().strip(),
        "status": git(root, "status", "--porcelain=v1", "--untracked-files=all").decode("utf-8"),
        "diffSha256": sha256(git(root, "--no-pager", "diff", "--binary", "--no-ext-diff", "--no-textconv", "HEAD", "--")),
    }
    require(result["status"] == "" and result["diffSha256"] == EMPTY_SHA256, "audit consumer source is not clean")
    return result


def parse_xml(data, description):
    require(not re.search(br"<!\s*(DOCTYPE|ENTITY)\b", data, re.IGNORECASE), f"DTD/entity forbidden: {description}")
    return ET.fromstring(data)


def reviewed_metadata(root, group, version):
    data = bounded_bytes(root / "gradle/verification-metadata.xml")
    require(data == git(root, "cat-file", "blob", "HEAD:gradle/verification-metadata.xml"),
            "external verification metadata differs from the committed reviewed bytes")
    tree = parse_xml(data, "reviewed verification metadata")
    tag = lambda name: f"{{{NAMESPACE}}}{name}"
    require(tree.tag == tag("verification-metadata"), "unexpected verification metadata namespace")
    require(len(tree.findall(tag("components"))) == 1, "expected exactly one components block")
    require(len(tree.findall(tag("configuration"))) == 1, "expected exactly one configuration block")
    config = tree.find(tag("configuration"))
    require([(item.tag, item.text) for item in config] == [
        (tag("verify-metadata"), "true"), (tag("verify-signatures"), "false"),
    ], "reviewed strict verification configuration changed")
    forbidden = {"trusted-artifacts", "trusted-keys", "ignored-keys", "trust", "sha1", "md5"}
    require(not any(node.tag.rsplit("}", 1)[-1] in forbidden for node in tree.iter()), "broad or weak verification trust is forbidden")
    components = set()
    for component in tree.find(tag("components")):
        require(component.tag == tag("component"), "unexpected external metadata component")
        key = tuple(component.get(name, "") for name in ("group", "name", "version"))
        require(all(key) and key not in components, "duplicate/invalid external component")
        components.add(key)
        require(not (key[0] == group and key[1] in PUBLICATIONS and key[2] == version),
                "reviewed metadata already contains a source-local coordinate; do not replace it")
        artifacts = set()
        for artifact in component:
            require(artifact.tag == tag("artifact") and artifact.get("name"), "invalid external artifact")
            require(artifact.get("name") not in artifacts, "duplicate external artifact")
            artifacts.add(artifact.get("name"))
            checksums = list(artifact)
            require(len(checksums) == 1 and checksums[0].tag == tag("sha256") and
                    re.fullmatch(r"[0-9a-f]{64}", checksums[0].get("value", "")),
                    "external artifact must retain one exact SHA-256")
    require(components, "empty reviewed external verification allowlist")
    require(data.count(b"   </components>\n") == 1, "metadata insertion point changed; review the generator")
    return data


def coordinates(root):
    properties = bounded_bytes(root / "gradle.properties").decode("utf-8")
    values = []
    for name in ("GROUP", "VERSION_NAME"):
        matches = re.findall(rf"^{name}=(.*)$", properties, re.MULTILINE)
        require(len(matches) == 1, f"expected one {name} source property")
        value = "".join(matches[0].split())
        require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value), f"invalid coordinate property: {name}")
        values.append(value)
    require(all(values[0].split(".")), "invalid group path")
    return tuple(values)


def setup(args):
    root = physical_directory(args.root)
    work = physical_directory(args.work_dir)
    state = physical_directory(os.environ.get("P2PKIT_AUDIT_STATE_DIR", ""))
    require(root != work and root not in work.parents, "audit consumer work must be outside the source checkout")
    require(work != state and work not in state.parents, "audit evidence must be outside disposable consumer work")
    receipt = Path(args.publication_receipt)
    evidence = physical_directory(str(receipt.parent))
    require(receipt.is_absolute() and receipt.name == "consumer-publish.json" and not receipt.is_symlink(),
            "publication receipt must name a new consumer-publish.json file")
    require(state in evidence.parents, "consumer receipts must be beneath the initialized audit state")
    source = source_snapshot(root)
    context_bytes = bounded_bytes(state / "context.json")
    context = parse_json(context_bytes)
    require(isinstance(context, dict) and type(context.get("schema")) is int and context["schema"] == 1,
            "invalid audit context schema")
    require(context.get("root") == str(root) and context.get("expectedCommit") == source["commit"] and
            context.get("tree") == source["tree"] and context.get("source") == source,
            "audit context is not bound to this exact clean source")
    require(isinstance(context.get("id"), str) and context["id"], "audit context has no ownership id")
    group, version = coordinates(root)
    reviewed = reviewed_metadata(root, group, version)
    return {
        "root": root, "work": work, "state": state, "evidence": evidence, "receipt": receipt,
        "repository": work / "repository", "fixture": work / "consumer", "source": source,
        "contextSha256": sha256(context_bytes), "contextId": context["id"],
        "group": group, "version": version, "reviewed": reviewed,
    }


def publish_arguments(context):
    return ["--no-daemon", "--console=plain", "publishToMavenLocal", f"-Dmaven.repo.local={context['repository']}"]


def consumer_arguments(context):
    return ["--no-daemon", "--console=plain", "-p", str(context["fixture"]),
            f"-PconsumerRepo={context['repository']}", *CONSUMER_TASKS]


def validate_receipt(path, context, purpose, arguments):
    data = bounded_bytes(path)
    receipt = parse_json(data)
    require(isinstance(receipt, dict) and type(receipt.get("schema")) is int and receipt["schema"] == 1,
            f"invalid {purpose} receipt schema")
    require(isinstance(receipt.get("id"), str) and receipt["id"], f"missing {purpose} invocation id")
    require(receipt.get("purpose") == purpose and receipt.get("requestedArgv") == arguments,
            f"{purpose} receipt does not name the exact isolated request")
    require(receipt.get("cwd") == str(context["root"]) and receipt.get("wrapper") == str(context["root"] / "gradlew"),
            f"{purpose} receipt has a different cwd/wrapper")
    for key in ("productExitCode", "stopExitCode", "finalExitCode"):
        require(type(receipt.get(key)) is int and receipt[key] == 0, f"{purpose} receipt has unsuccessful {key}")
    require(receipt.get("sourceBefore") == context["source"] and receipt.get("sourceAfter") == context["source"] and
            receipt.get("sourceUnchanged") is True, f"{purpose} receipt has a different/changed source")
    require(receipt.get("ownedSurvivors") == [] and receipt.get("errors") == [], f"{purpose} receipt has unfinished cleanup")
    return sha256(data), receipt["id"]


def admission_fields(context):
    return {
        "schema": 1, "root": str(context["root"]), "workDir": str(context["work"]),
        "repository": str(context["repository"]), "fixture": str(context["fixture"]),
        "source": context["source"], "contextSha256": context["contextSha256"],
        "contextId": context["contextId"], "publicationReceipt": str(context["receipt"]),
        "requestedPublishArgv": publish_arguments(context), "reviewedMetadataSha256": sha256(context["reviewed"]),
    }


def admit(context, ownership):
    require(not any(context["work"].iterdir()), "consumer work was not empty before publication admission")
    require(not context["receipt"].exists(), "publication receipt already exists before admission")
    value = admission_fields(context)
    value.update({"ownership": ownership, "admittedUtc": utc_now(), "repositoryInitiallyAbsent": True})
    require(source_snapshot(context["root"]) == context["source"], "source changed during admission")
    write_new(context["evidence"] / "reviewed-verification-metadata.xml", context["reviewed"])
    write_json(context["evidence"] / "consumer-admission.json", value)
    print("==> Admitted empty source-local consumer repository; retained immutable external metadata")


def validate_admission(context):
    path = context["evidence"] / "consumer-admission.json"
    value = read_json(path)
    for key, expected in admission_fields(context).items():
        require(value.get(key) == expected, f"consumer admission changed: {key}")
    require(value.get("repositoryInitiallyAbsent") is True and value.get("ownership") in ("owned", "borrowed"),
            "consumer repository was not admitted empty with explicit ownership")
    require(bounded_bytes(context["evidence"] / "reviewed-verification-metadata.xml") == context["reviewed"],
            "retained external metadata was modified")
    return sha256(bounded_bytes(path))


def file_digest(path):
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode), f"not a regular publication file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        require((before.st_dev, before.st_ino) == (opened.st_dev, opened.st_ino), f"publication replaced while opening: {path}")
        for block in iter(lambda: stream.read(512 * 1024), b""):
            digest.update(block)
        after = os.fstat(stream.fileno())
    identity = lambda item: (item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns, item.st_ctime_ns)
    require(identity(before) == identity(after) == identity(path.lstat()), f"publication changed while hashing: {path}")
    return {"sha256": digest.hexdigest(), "bytes": before.st_size}


def inspect_repository(context):
    repo = physical_directory(str(context["repository"]))
    group, version = context["group"], context["version"]
    group_path = Path(*group.split("."))
    required = {}
    optional = set()
    for artifact, suffix in PUBLICATIONS.items():
        directory = group_path / artifact / version
        for ending in (suffix, "-sources.jar", "-javadoc.jar", ".pom", ".module",
                       *NATIVE_ARTIFACT_SUFFIXES.get(artifact, ())):
            relative = directory / f"{artifact}-{version}{ending}"
            required[relative.as_posix()] = (artifact, relative.name)
        # Maven-local housekeeping is recorded, never added as trusted artifacts.
        optional.add((group_path / artifact / "maven-metadata-local.xml").as_posix())
        optional.add((directory / "maven-metadata-local.xml").as_posix())
        # KMP emits one tooling sidecar for each root publication. Like Maven
        # housekeeping, bind these bytes for the final unchanged-repository check
        # without adding them to the dependency-verification allowlist.
        if artifact in ("p2p-core", "p2p-transport-lan", "p2p-network-provisioning-android"):
            optional.add((directory / f"{artifact}-{version}-kotlin-tooling-metadata.json").as_posix())
    allowed_files = set(required) | optional
    allowed_dirs = {"."}
    for name in allowed_files:
        allowed_dirs.update(parent.as_posix() for parent in Path(name).parents)
    files = {}
    for directory, children, filenames in os.walk(repo, followlinks=False):
        children.sort()
        for name in children:
            child = Path(directory) / name
            relative = child.relative_to(repo).as_posix()
            require(not child.is_symlink() and child.is_dir() and relative in allowed_dirs,
                    f"unexpected publication directory: {relative}")
        for name in sorted(filenames):
            path = Path(directory) / name
            relative = path.relative_to(repo).as_posix()
            require(relative in allowed_files, f"unexpected publication artifact: {relative}")
            files[relative] = file_digest(path)
    require(set(required).issubset(files), "publication is missing required artifacts: " + ", ".join(sorted(set(required) - files.keys())))
    artifacts = []
    for relative, (artifact, filename) in sorted(required.items()):
        artifacts.append({"group": group, "module": artifact, "version": version, "name": filename,
                          "path": relative, **files[relative]})
    for artifact in PUBLICATIONS:
        directory = repo / group_path / artifact / version
        pom = parse_xml(bounded_bytes(directory / f"{artifact}-{version}.pom"), "local POM")
        direct = {child.tag.rsplit("}", 1)[-1]: child.text for child in pom}
        require(all(sum(child.tag.rsplit("}", 1)[-1] == key for child in pom) == 1
                    for key in ("groupId", "artifactId", "version")), f"ambiguous source-local POM coordinate: {artifact}")
        require(pom.tag.rsplit("}", 1)[-1] == "project" and
                (direct.get("groupId"), direct.get("artifactId"), direct.get("version")) == (group, artifact, version),
                f"source-local POM coordinate mismatch: {artifact}")
        module = read_json(directory / f"{artifact}-{version}.module")
        component_module = artifact
        if artifact.startswith("p2p-core-"):
            component_module = "p2p-core"
        elif artifact.startswith("p2p-transport-lan-"):
            component_module = "p2p-transport-lan"
        elif artifact == "p2p-network-provisioning-android-android":
            component_module = "p2p-network-provisioning-android"
        component = module.get("component", {})
        require(isinstance(component, dict) and module.get("formatVersion") == "1.1" and
                (component.get("group"), component.get("module"), component.get("version")) == (group, component_module, version),
                f"source-local module coordinate mismatch: {artifact}")
    return files, artifacts


def render_metadata(context, artifacts, publication_id):
    additions = []
    origin = f"Source-built audit consumer; commit {context['source']['commit']}; publication {publication_id}"
    for module in sorted(PUBLICATIONS):
        additions.append(f"      <component group={quoteattr(context['group'])} name={quoteattr(module)} version={quoteattr(context['version'])}>\n")
        for artifact in artifacts:
            if artifact["module"] == module:
                additions.extend([
                    f"         <artifact name={quoteattr(artifact['name'])}>\n",
                    f"            <sha256 value={quoteattr(artifact['sha256'])} origin={quoteattr(origin)}/>\n",
                    "         </artifact>\n",
                ])
        additions.append("      </component>\n")
    insertion = "".join(additions).encode("utf-8")
    return context["reviewed"].replace(b"   </components>\n", insertion + b"   </components>\n", 1)


def prepared_fields(context):
    admission_sha = validate_admission(context)
    receipt_sha, receipt_id = validate_receipt(context["receipt"], context, "consumer-publish", publish_arguments(context))
    files, artifacts = inspect_repository(context)
    prepared = render_metadata(context, artifacts, receipt_id)
    fields = {
        "schema": 1, "source": context["source"], "root": str(context["root"]), "workDir": str(context["work"]),
        "contextSha256": context["contextSha256"], "admissionSha256": admission_sha,
        "publicationReceiptSha256": receipt_sha, "publicationId": receipt_id,
        "reviewedMetadataSha256": sha256(context["reviewed"]), "preparedMetadataSha256": sha256(prepared),
        "publicationCount": len(PUBLICATIONS), "artifactCount": len(artifacts),
        "localArtifacts": artifacts, "repositoryFiles": files,
    }
    return fields, prepared


def prepare(context):
    fields, prepared = prepared_fields(context)
    physical_directory(str(context["fixture"]))
    gradle = context["fixture"] / "gradle"
    require(not gradle.exists() and not gradle.is_symlink(), "fixture already has Gradle verification inputs")
    gradle.mkdir(mode=0o700)
    require(source_snapshot(context["root"]) == context["source"], "source changed during metadata preparation")
    write_new(gradle / "verification-metadata.xml", prepared)
    fields["preparedUtc"] = utc_now()
    fields["limitations"] = "Source-local first-read checksums, not external authentication or release acceptance; exclusive owned repository required."
    write_json(context["evidence"] / "consumer-publication-manifest.json", fields)
    print(f"==> Prepared strict consumer metadata: unchanged external allowlist + "
          f"{fields['publicationCount']} source-local publications / {fields['artifactCount']} artifacts")


def verify(context):
    fields, prepared = prepared_fields(context)
    manifest = read_json(context["evidence"] / "consumer-publication-manifest.json")
    for key, expected in fields.items():
        require(manifest.get(key) == expected, f"prepared consumer publication binding changed: {key}")
    require(bounded_bytes(context["fixture"] / "gradle/verification-metadata.xml") == prepared,
            "prepared external/local verification metadata was modified")
    build_sha, build_id = validate_receipt(context["evidence"] / "consumer-build.json", context,
                                         "consumer-build", consumer_arguments(context))
    require(source_snapshot(context["root"]) == context["source"], "source changed during consumer verification")
    write_json(context["evidence"] / "consumer-metadata-verification.json", {
        "schema": 1, "verifiedUtc": utc_now(), "source": context["source"],
        "publicationManifestSha256": sha256(bounded_bytes(context["evidence"] / "consumer-publication-manifest.json")),
        "consumerBuildReceiptSha256": build_sha, "consumerBuildId": build_id,
        "preparedMetadataSha256": fields["preparedMetadataSha256"],
        "publicationCount": fields["publicationCount"], "artifactCount": fields["artifactCount"],
        "result": "PASS", "scope": "unchanged source-local publication bytes and strict fixture allowlist only",
    })
    print("==> Verified unchanged source-local publication bytes, original external metadata, and both finalized leaf receipts")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("admit", "prepare", "verify"))
    parser.add_argument("--root", required=True)
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--publication-receipt", required=True)
    parser.add_argument("--ownership", choices=("owned", "borrowed"))
    args = parser.parse_args()
    context = None
    try:
        require((args.mode == "admit") == (args.ownership is not None), "only admit requires --ownership")
        context = setup(args)
        if args.mode == "admit":
            admit(context, args.ownership)
        elif args.mode == "prepare":
            prepare(context)
        else:
            verify(context)
        return 0
    except (OSError, ValueError, ET.ParseError, subprocess.CalledProcessError) as error:
        message = f"audit consumer metadata {args.mode}: {error}"
        print(f"FAIL: {message}", file=sys.stderr)
        if context is not None:
            try:
                write_json(context["evidence"] / f"consumer-metadata-failure-{uuid.uuid4().hex}.json", {
                    "schema": 1, "mode": args.mode, "failedUtc": utc_now(), "error": message,
                    "sourceAtAdmission": context["source"], "finalExitCode": 125,
                })
            except OSError as evidence_error:
                print(f"FAIL: could not retain metadata failure receipt: {evidence_error}", file=sys.stderr)
        return 125


if __name__ == "__main__":
    sys.exit(main())
