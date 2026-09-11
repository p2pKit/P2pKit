#!/usr/bin/env python3
"""Recording-boundary controls for the real consumer shell gate and metadata helper.

These tests use synthetic local publication bytes and fake Gradle/Xcode/curl
boundaries. They do not claim Gradle resolution, real publication shape, Apple
compilation, artifact authenticity, or native Windows executor ownership.
The explicit cancellation producer is consumed by the separate native executor
selftest; producing its fixture is not a cancellation or cleanup verdict.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
import xml.etree.ElementTree as ET


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import audit_processes as processes


OWNERSHIP_FIELDS = (
    "P2PKIT_AUDIT_JOB_ID", "P2PKIT_AUDIT_OWNERSHIP_CHAIN", "P2PKIT_AUDIT_OWNERSHIP_DOMAINS",
    "P2PKIT_AUDIT_STATE_DIR", "GRADLE_USER_HOME", "P2PKIT_AUDIT_INVOCATION",
    "P2PKIT_AUDIT_FIXTURE_ANCESTOR",
)
NAMESPACE = "https://schema.gradle.org/dependency-verification"
GROUP = "io.github.apdelrahman1911"
# Non-SNAPSHOT source versions are supported too; Gradle's changing-module skip
# must not hide the logical-name contract. These remain fake-boundary tests.
VERSION = "9.11.0"
KOTLIN_VERSION = "91.0.0"
COROUTINES_VERSION = "1.11.0"
EXTERNAL_BYTES = b"independently reviewed external fixture bytes\n"
EXTERNAL_SHA256 = hashlib.sha256(EXTERNAL_BYTES).hexdigest()
CONSUMER_REPORT_BYTES = b'{"fixtureOnly":true,"result":"synthetic-consumer-report-not-compilation"}\n'
PACKAGING_REPORT_BYTES = (
    b"PASS: embedded JmDNS Android D8/R8 plain+coexistence; POM-only runtime graphs\n"
)
PACKAGING_REPORT_PATH = "androidConsumer/build/reports/embedded-jmdns/packaging.txt"
EXPECTED_APKS = {
    "debug": "androidConsumer-debug.apk",
    "release": "androidConsumer-release-unsigned.apk",
    "coexistDebug": "androidConsumer-coexistDebug.apk",
    "coexistRelease": "androidConsumer-coexistRelease-unsigned.apk",
}
# This fixture expectation is deliberately not imported from the implementation.
EXPECTED_PUBLICATIONS = [
    ("p2p-core", ".jar"), ("p2p-core-jvm", ".jar"), ("p2p-core-android", ".aar"),
    ("p2p-transport-lan", ".jar"), ("p2p-transport-lan-jvm", ".jar"), ("p2p-transport-lan-android", ".aar"),
    ("p2p-network-provisioning-android", ".jar"), ("p2p-network-provisioning-android-android", ".aar"),
    ("p2p-network-provisioning-desktop", ".jar"),
    ("p2p-core-iosarm64", ".klib"), ("p2p-transport-lan-iosarm64", ".klib"),
    ("p2p-core-iossimulatorarm64", ".klib"), ("p2p-transport-lan-iossimulatorarm64", ".klib"),
    ("p2p-core-iosx64", ".klib"), ("p2p-transport-lan-iosx64", ".klib"),
]
EXPECTED_TOOLING_PUBLICATIONS = ("p2p-core", "p2p-transport-lan", "p2p-network-provisioning-android")
EXPECTED_NATIVE_PUBLICATIONS = (
    "p2p-core-iosarm64", "p2p-core-iossimulatorarm64", "p2p-core-iosx64",
    "p2p-transport-lan-iosarm64", "p2p-transport-lan-iossimulatorarm64", "p2p-transport-lan-iosx64",
)
EXPECTED_INTEROP_PUBLICATIONS = (
    "p2p-transport-lan-iosarm64", "p2p-transport-lan-iossimulatorarm64", "p2p-transport-lan-iosx64",
)
# Independent logical name -> physical basename expectations from actual GMM.
EXPECTED_LOGICAL_ALIASES = [
    ("p2p-core", f"p2p-core-metadata-{VERSION}.jar", f"p2p-core-{VERSION}.jar"),
    ("p2p-core", f"p2p-core-kotlin-{VERSION}-sources.jar", f"p2p-core-{VERSION}-sources.jar"),
    ("p2p-transport-lan", f"p2p-transport-lan-metadata-{VERSION}.jar", f"p2p-transport-lan-{VERSION}.jar"),
    ("p2p-transport-lan", f"p2p-transport-lan-kotlin-{VERSION}-sources.jar", f"p2p-transport-lan-{VERSION}-sources.jar"),
    ("p2p-network-provisioning-android", f"p2p-network-provisioning-android-metadata-{VERSION}.jar",
     f"p2p-network-provisioning-android-{VERSION}.jar"),
    ("p2p-network-provisioning-android", f"p2p-network-provisioning-android-kotlin-{VERSION}-sources.jar",
     f"p2p-network-provisioning-android-{VERSION}-sources.jar"),
    ("p2p-core-android", "p2p-core.aar", f"p2p-core-android-{VERSION}.aar"),
    ("p2p-transport-lan-android", "p2p-transport-lan.aar", f"p2p-transport-lan-android-{VERSION}.aar"),
    ("p2p-network-provisioning-android-android", "p2p-network-provisioning-android.aar",
     f"p2p-network-provisioning-android-android-{VERSION}.aar"),
    ("p2p-core-iosarm64", f"p2p-core-iosArm64Main-{VERSION}.klib", f"p2p-core-iosarm64-{VERSION}.klib"),
    ("p2p-core-iossimulatorarm64", f"p2p-core-iosSimulatorArm64Main-{VERSION}.klib",
     f"p2p-core-iossimulatorarm64-{VERSION}.klib"),
    ("p2p-core-iosx64", f"p2p-core-iosX64Main-{VERSION}.klib", f"p2p-core-iosx64-{VERSION}.klib"),
    ("p2p-transport-lan-iosarm64", f"p2p-transport-lan-iosArm64Main-{VERSION}.klib",
     f"p2p-transport-lan-iosarm64-{VERSION}.klib"),
    ("p2p-transport-lan-iossimulatorarm64", f"p2p-transport-lan-iosSimulatorArm64Main-{VERSION}.klib",
     f"p2p-transport-lan-iossimulatorarm64-{VERSION}.klib"),
    ("p2p-transport-lan-iosx64", f"p2p-transport-lan-iosX64Main-{VERSION}.klib",
     f"p2p-transport-lan-iosx64-{VERSION}.klib"),
    ("p2p-transport-lan-iosarm64", f"p2p-transport-lan-iosArm64Cinterop-p2pkit_nwMain-{VERSION}.klib",
     f"p2p-transport-lan-iosarm64-{VERSION}-cinterop-p2pkit_nw.klib"),
    ("p2p-transport-lan-iossimulatorarm64", f"p2p-transport-lan-iosSimulatorArm64Cinterop-p2pkit_nwMain-{VERSION}.klib",
     f"p2p-transport-lan-iossimulatorarm64-{VERSION}-cinterop-p2pkit_nw.klib"),
    ("p2p-transport-lan-iosx64", f"p2p-transport-lan-iosX64Cinterop-p2pkit_nwMain-{VERSION}.klib",
     f"p2p-transport-lan-iosx64-{VERSION}-cinterop-p2pkit_nw.klib"),
]
EXPECTED_LEGACY_TASKS = [
    ":coreJvm:compileKotlin", ":coreJvm:compileJava", ":lanJvm:compileKotlin", ":desktopJvm:compileKotlin",
    ":androidConsumer:compileDebugKotlin", ":androidConsumer:processDebugManifest", ":kmpConsumer:compileKotlinJvm",
    ":kmpConsumer:compileAndroidMain", ":kmpConsumer:compileKotlinIosSimulatorArm64",
    ":kmpConsumer:linkDebugFrameworkIosSimulatorArm64",
]
EXPECTED_EMBEDDED_TASKS = [
    ":lanJvm:runEmbeddedJmdnsSmoke",
    ":lanJvm:runEmbeddedJmdnsCoexistenceSmoke",
    ":lanJvm:runEmbeddedJmdnsCoexistenceUpstreamFirstSmoke",
    ":lanJvm:runEmbeddedJmdnsPomSmoke",
    ":androidConsumer:assembleDebug",
    ":androidConsumer:assembleRelease",
    ":androidConsumer:assembleCoexistDebug",
    ":androidConsumer:assembleCoexistRelease",
    ":androidConsumer:verifyEmbeddedJmdnsPackaging",
]
EXPECTED_TASKS = EXPECTED_LEGACY_TASKS + EXPECTED_EMBEDDED_TASKS
EXPECTED_FOCUSED_PUBLICATIONS = [
    ("p2p-core-jvm", ".jar"), ("p2p-core-android", ".aar"),
    ("p2p-transport-lan-jvm", ".jar"), ("p2p-transport-lan-android", ".aar"),
    ("p2p-core", ".jar"),
]
EXPECTED_FOCUSED_PUBLISH_TASKS = [
    ":p2p-core:publishJvmPublicationToMavenLocal",
    ":p2p-core:publishAndroidPublicationToMavenLocal",
    ":p2p-transport-lan:publishJvmPublicationToMavenLocal",
    ":p2p-transport-lan:publishAndroidPublicationToMavenLocal",
    ":p2p-core:publishKotlinMultiplatformPublicationToMavenLocal",
]
PERMISSIONS = [
    "android.permission.INTERNET", "android.permission.ACCESS_NETWORK_STATE",
    "android.permission.ACCESS_WIFI_STATE", "android.permission.CHANGE_WIFI_MULTICAST_STATE",
]
POM_DEPENDENCIES = {
    "p2p-core-jvm": [
        ["kotlinx-coroutines-core-jvm", "compile"], ["kotlinx-io-core-jvm", "compile"],
        ["kotlinx-serialization-json-jvm", "runtime"], ["cryptography-core-jvm", "runtime"],
        ["cryptography-provider-jdk-jvm", "runtime"], ["bcprov-jdk18on", "runtime"],
    ],
    "p2p-transport-lan-jvm": [
        ["p2p-core-jvm", "compile"], ["kotlinx-coroutines-core-jvm", "compile"], ["slf4j-api", "runtime"],
    ],
    "p2p-transport-lan-android": [
        ["p2p-core-android", "compile"], ["kotlinx-coroutines-core-jvm", "compile"], ["slf4j-api", "runtime"],
    ],
    "p2p-network-provisioning-android-android": [["p2p-core-android", "compile"], ["kotlinx-coroutines-core-jvm", "compile"]],
    "p2p-network-provisioning-desktop": [["p2p-core-jvm", "compile"], ["kotlinx-coroutines-core-jvm", "compile"]],
}

BOUNDARY = r'''#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

PUBLICATIONS = __PUBLICATIONS__
FOCUSED_PUBLICATIONS = __FOCUSED_PUBLICATIONS__
FOCUSED_PUBLISH_TASKS = __FOCUSED_PUBLISH_TASKS__
EMBEDDED_TASKS = __EMBEDDED_TASKS__
TOOLING_PUBLICATIONS = __TOOLING_PUBLICATIONS__
NATIVE_PUBLICATIONS = __NATIVE_PUBLICATIONS__
INTEROP_PUBLICATIONS = __INTEROP_PUBLICATIONS__
LOGICAL_ALIASES = __LOGICAL_ALIASES__
DEPS = __DEPS__
PERMISSIONS = __PERMISSIONS__
GROUP = __GROUP__
VERSION = __VERSION__
KOTLIN_VERSION = __KOTLIN_VERSION__
COROUTINES_VERSION = __COROUTINES_VERSION__
EXTERNAL_SHA256 = __EXTERNAL_SHA256__
OWNERSHIP_FIELDS = __OWNERSHIP_FIELDS__
CONSUMER_REPORT_BYTES = __CONSUMER_REPORT_BYTES__
PACKAGING_REPORT_BYTES = __PACKAGING_REPORT_BYTES__
PACKAGING_REPORT_PATH = __PACKAGING_REPORT_PATH__
EXPECTED_APKS = __EXPECTED_APKS__

def record(kind, **fields):
    with open(os.environ["FAKE_CALLS"], "a", encoding="utf-8") as stream:
        stream.write(json.dumps({"kind": kind, "ownership": {
            name: os.environ.get(name) for name in OWNERSHIP_FIELDS}, **fields}, ensure_ascii=False) + "\n")

def snapshot(root):
    def git(*args):
        return subprocess.check_output(["git", "-C", str(root), *args])
    return {
        "commit": git("rev-parse", "HEAD").decode().strip(),
        "tree": git("rev-parse", "HEAD^{tree}").decode().strip(),
        "status": git("status", "--porcelain=v1", "--untracked-files=all").decode(),
        "diffSha256": hashlib.sha256(git("--no-pager", "diff", "--binary", "--no-ext-diff", "--no-textconv", "HEAD", "--")).hexdigest(),
    }

def dependency_identity(name):
    if name.startswith("p2p-"):
        return GROUP, VERSION
    if name.startswith("kotlinx-coroutines-"):
        return "org.jetbrains.kotlinx", COROUTINES_VERSION
    if name == "kotlin-stdlib":
        return "org.jetbrains.kotlin", KOTLIN_VERSION
    if name == "slf4j-api":
        return "org.slf4j", "2.0.7"
    if name == "jmdns":
        return "org.jmdns", "3.6.3"
    return "org.example.synthetic", "1.0"

def pom(artifact):
    deps = [list(pair) for pair in DEPS.get(artifact, [])]
    if os.environ.get("FAKE_LEGACY_JMDNS") and artifact in ("p2p-transport-lan-jvm", "p2p-transport-lan-android"):
        deps = [["jmdns" if name == "slf4j-api" else name, scope] for name, scope in deps]
    for dependency in deps:
        if os.environ.get("FAKE_BAD_SCOPE") == artifact + "|" + dependency[0]:
            dependency[1] = "runtime" if dependency[1] == "compile" else "compile"
    if os.environ.get("FAKE_TEST_ONLY_LAN") and artifact == "p2p-network-provisioning-desktop":
        deps.append(["p2p-transport-lan-jvm", "runtime"])
    group = "invalid.fixture" if os.environ.get("FAKE_BAD_COORDINATE") == artifact else GROUP
    lines = ["<project>", f"<groupId>{group}</groupId>", f"<artifactId>{artifact}</artifactId>",
             f"<version>{VERSION}</version>", "<dependencies>"]
    records = []
    for name, scope in deps:
        dep_group, dep_version = dependency_identity(name)
        records.append({"groupId": dep_group, "artifactId": name, "version": dep_version, "scope": scope})
    if os.environ.get("FAKE_LAN_POM_MUTATION"):
        mutation = json.loads(os.environ["FAKE_LAN_POM_MUTATION"])
        if mutation["artifact"] == artifact:
            name = mutation.get("name")
            if name is None:
                records.append(mutation["values"])
            elif mutation.get("remove"):
                records = [entry for entry in records if entry["artifactId"] != name]
            else:
                next(entry for entry in records if entry["artifactId"] == name).update(mutation["values"])
    for entry in records:
        lines.extend(["<dependency>", *(f"<{key}>{value}</{key}>" for key, value in entry.items()), "</dependency>"])
    return "\n".join(lines + ["</dependencies>", "</project>", ""])

def lan_variants(artifact, variants):
    if artifact not in ("p2p-transport-lan-jvm", "p2p-transport-lan-android"):
        return variants
    for variant in variants:
        if variant["name"] not in ("apiElements", "runtimeElements"):
            continue
        runtime = variant["name"] == "runtimeElements"
        variant["attributes"] = {"org.gradle.usage": "java-runtime" if runtime else "java-api"}
        names = ["p2p-core", "kotlinx-coroutines-core", "kotlin-stdlib"]
        if runtime:
            names.append("jmdns" if os.environ.get("FAKE_LEGACY_JMDNS") else "slf4j-api")
        variant["dependencies"] = [
            {"group": dependency_identity(name)[0], "module": name,
             "version": {"requires": dependency_identity(name)[1]}} for name in names
        ]
    if os.environ.get("FAKE_LAN_MODULE_MUTATION"):
        mutation = json.loads(os.environ["FAKE_LAN_MODULE_MUTATION"])
        if mutation["artifact"] == artifact:
            variant = next(item for item in variants if item["name"] == mutation["variant"])
            if mutation.get("removeVariant"):
                variants.remove(variant)
            elif "attributes" in mutation:
                variant["attributes"] = mutation["attributes"]
            else:
                field = mutation.get("field", "dependencies")
                entries = variant.setdefault(field, [])
                name = mutation.get("name")
                if name is None:
                    entries.extend(dict(mutation["values"]) for _ in range(mutation.get("count", 1)))
                elif mutation.get("remove"):
                    variant[field] = [entry for entry in entries if entry.get("module") != name]
                else:
                    next(entry for entry in entries if entry["module"] == name).update(mutation["values"])
    return variants

def publish(repo, publications):
    for artifact, suffix in publications:
        folder = repo / GROUP.replace(".", "/") / artifact / VERSION
        folder.mkdir(parents=True, exist_ok=True)
        endings = [suffix, "-sources.jar", "-javadoc.jar"]
        if artifact in NATIVE_PUBLICATIONS:
            endings.append("-metadata.jar")
        if artifact in INTEROP_PUBLICATIONS:
            endings.append("-cinterop-p2pkit_nw.klib")
        for ending in endings:
            name = f"{artifact}-{VERSION}{ending}"
            (folder / name).write_bytes(("synthetic fixture artifact " + name + "\n").encode())
        (folder / f"{artifact}-{VERSION}.pom").write_text(pom(artifact))
        component = artifact
        if artifact.startswith("p2p-core-"):
            component = "p2p-core"
        elif artifact.startswith("p2p-transport-lan-"):
            component = "p2p-transport-lan"
        elif artifact == "p2p-network-provisioning-android-android":
            component = "p2p-network-provisioning-android"
        if artifact in TOOLING_PUBLICATIONS and not (
                artifact == "p2p-core" and os.environ.get("FAKE_TOOLING_CHANGE") == "add"):
            (folder / f"{artifact}-{VERSION}-kotlin-tooling-metadata.json").write_text(json.dumps({
                "schemaVersion": "1.1.0", "buildSystem": "Gradle",
                "buildPlugin": "org.jetbrains.kotlin.gradle.plugin.KotlinMultiplatformPluginWrapper",
                "buildPluginVersion": "91.0.0",
            }))
        aliases = {url: name for owner, name, url in LOGICAL_ALIASES if owner == artifact}
        def file_record(ending):
            url = f"{artifact}-{VERSION}{ending}"
            content = (folder / url).read_bytes()
            return {"name": aliases.get(url, url), "url": url, "size": len(content),
                    "sha256": hashlib.sha256(content).hexdigest()}
        api_files = [file_record(suffix)]
        if artifact in INTEROP_PUBLICATIONS:
            api_files.append(file_record("-cinterop-p2pkit_nw.klib"))
        variants = [{"name": "apiElements", "files": api_files},
                    {"name": "sourcesElements", "files": [file_record("-sources.jar")]}]
        if artifact in NATIVE_PUBLICATIONS:
            variants.append({"name": "metadataElements", "files": [file_record("-metadata.jar")]})
        if suffix == ".aar" or artifact.endswith("-jvm") or artifact == "p2p-network-provisioning-desktop":
            variants.append({"name": "runtimeElements", "files": [dict(entry) for entry in api_files]})
        if artifact in TOOLING_PUBLICATIONS:
            target = artifact + "-android"
            variants.append({"name": "androidApiElements-published", "available-at": {
                "url": f"../../{target}/{VERSION}/{target}-{VERSION}.module",
                "group": GROUP, "module": target, "version": VERSION,
            }})
        lan_variants(artifact, variants)
        if artifact == "p2p-core" and os.environ.get("FAKE_MODULE_FILE_CHANGE"):
            change = os.environ["FAKE_MODULE_FILE_CHANGE"]
            entry = api_files[0]
            source_binding = {key: variants[1]["files"][0][key] for key in ("url", "sha256", "size")}
            if change == "missing-alias":
                api_files.clear()
            elif change == "unapproved-name":
                entry["name"] = "unapproved-logical.jar"
            elif change == "wrong-target":
                entry.update(source_binding)
            elif change == "traversal":
                entry["url"] = "../" + entry["url"]
            elif change == "remote":
                entry["url"] = "https://repository.example.invalid/" + entry["url"]
            elif change == "tooling-sidecar":
                api_files.append(file_record("-kotlin-tooling-metadata.json"))
            elif change == "wrong-sha256":
                entry["sha256"] = "0" * 64
            elif change == "wrong-size":
                entry["size"] += 1
            elif change == "conflicting-alias":
                variants.append({"name": "conflictingRuntime", "files": [{**entry, **source_binding}]})
            else:
                raise AssertionError("unknown module file control: " + change)
        module_text = json.dumps({
            "formatVersion": "1.1", "component": {"group": GROUP, "module": component, "version": VERSION},
            "variants": variants,
        })
        if os.environ.get("FAKE_DUPLICATE_MODULE_KEY") == artifact:
            module_text = module_text.replace('"formatVersion": "1.1"', '"formatVersion": "1.1", "formatVersion": "1.1"', 1)
        (folder / f"{artifact}-{VERSION}.module").write_text(module_text)
        (folder.parent / "maven-metadata-local.xml").write_text("<metadata/>\n")
        (folder / "maven-metadata-local.xml").write_text("<metadata/>\n")
    if os.environ.get("FAKE_EXTRA_TOOLING"):
        (repo / GROUP.replace(".", "/") / "p2p-core-jvm" / VERSION /
         f"p2p-core-jvm-{VERSION}-kotlin-tooling-metadata.json").write_text("{}\n")
    if os.environ.get("FAKE_EXTRA_NATIVE_INTEROP"):
        (repo / GROUP.replace(".", "/") / "p2p-core-iosarm64" / VERSION /
         f"p2p-core-iosarm64-{VERSION}-cinterop-p2pkit_nw.klib").write_bytes(b"unapproved interop coordinate")
    for flag, artifact, ending in (
            ("FAKE_MISSING_NATIVE_METADATA", "p2p-core-iosarm64", "-metadata.jar"),
            ("FAKE_MISSING_NATIVE_INTEROP", "p2p-transport-lan-iosarm64", "-cinterop-p2pkit_nw.klib")):
        if os.environ.get(flag):
            (repo / GROUP.replace(".", "/") / artifact / VERSION / f"{artifact}-{VERSION}{ending}").unlink()
    if os.environ.get("FAKE_MISSING_POM"):
        artifact = os.environ["FAKE_MISSING_POM"]
        (repo / GROUP.replace(".", "/") / artifact / VERSION / f"{artifact}-{VERSION}.pom").unlink()
    if os.environ.get("FAKE_MISSING_MODULE"):
        artifact = os.environ["FAKE_MISSING_MODULE"]
        (repo / GROUP.replace(".", "/") / artifact / VERSION / f"{artifact}-{VERSION}.module").unlink()
    if os.environ.get("FAKE_EXTRA_ARTIFACT"):
        (repo / GROUP.replace(".", "/") / "p2p-core-jvm" / VERSION / f"p2p-core-jvm-{VERSION}-debug.jar").write_bytes(b"unapproved variant")
    if os.environ.get("FAKE_EXTRA_GROUP"):
        (repo / "unapproved" / "group").mkdir(parents=True)
    if os.environ.get("FAKE_MISSING_ARTIFACT"):
        (repo / GROUP.replace(".", "/") / "p2p-core-iosx64" / VERSION / f"p2p-core-iosx64-{VERSION}.klib").unlink()
    if os.environ.get("FAKE_SYMLINK_ARTIFACT"):
        target = repo / GROUP.replace(".", "/") / "p2p-core-iosx64" / VERSION / f"p2p-core-iosx64-{VERSION}.klib"
        target.unlink()
        target.symlink_to(os.environ["FAKE_CALLS"])

def build(args):
    fixture = Path(args[args.index("-p") + 1])
    if ":kmpConsumer:linkDebugFrameworkIosSimulatorArm64" in args:
        report = fixture / "kmpConsumer/build/reports/consumer-fixture.json"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_bytes(CONSUMER_REPORT_BYTES)
        if not os.environ.get("FAKE_MISSING_FRAMEWORK"):
            framework = fixture / "kmpConsumer/build/bin/iosSimulatorArm64/debugFramework/P2pKitConsumer.framework/P2pKitConsumer"
            framework.parent.mkdir(parents=True, exist_ok=True)
            framework.write_bytes(b"synthetic Mach-O stand-in, not a real Apple binary")
    manifest = fixture / "androidConsumer/build/intermediates/merged_manifest/debug/processDebugManifest/AndroidManifest.xml"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    permissions = [name for name in PERMISSIONS if name != os.environ.get("FAKE_OMIT_PERMISSION")]
    manifest.write_text("<manifest>\n" + "\n".join(f'<uses-permission android:name="{name}" />' for name in permissions) + "\n</manifest>\n")
    if any(task in args for task in EMBEDDED_TASKS):
        # Deliberately synthetic output contracts for the shell's inspectors.
        # Neither these bytes nor this fake wrapper establish D8/R8/runtime proof.
        if not os.environ.get("FAKE_MISSING_PACKAGING_REPORT"):
            packaging = fixture / PACKAGING_REPORT_PATH
            packaging.parent.mkdir(parents=True, exist_ok=True)
            content = (b"invalid synthetic packaging result\n" if os.environ.get("FAKE_BAD_PACKAGING_REPORT")
                       else PACKAGING_REPORT_BYTES)
            if "FAKE_PACKAGING_REPORT" in os.environ:
                content = os.environ["FAKE_PACKAGING_REPORT"].encode()
            packaging.write_bytes(content)
        for variant, filename in EXPECTED_APKS.items():
            if os.environ.get("FAKE_MISSING_APK") == variant:
                continue
            apk = fixture / "androidConsumer/build/outputs/apk" / variant / filename
            apk.parent.mkdir(parents=True, exist_ok=True)
            apk.write_bytes(b"synthetic APK stand-in, not an Android archive\n")
    if os.environ.get("FAKE_TAMPER_EXTERNAL"):
        metadata = fixture / "gradle/verification-metadata.xml"
        metadata.chmod(0o600)
        metadata.write_text(metadata.read_text().replace(EXTERNAL_SHA256, "0" * 64))
    if os.environ.get("FAKE_TAMPER_LOCAL"):
        repo = Path(next(arg.split("=", 1)[1] for arg in args if arg.startswith("-PconsumerRepo=")))
        (repo / GROUP.replace(".", "/") / "p2p-core-jvm" / VERSION / f"p2p-core-jvm-{VERSION}.jar").write_bytes(b"changed after prepared allowlist")
    for flag, artifact, ending in (
            ("FAKE_TAMPER_NATIVE_METADATA", "p2p-core-iosarm64", "-metadata.jar"),
            ("FAKE_TAMPER_NATIVE_INTEROP", "p2p-transport-lan-iosarm64", "-cinterop-p2pkit_nw.klib")):
        if os.environ.get(flag):
            repo = Path(next(arg.split("=", 1)[1] for arg in args if arg.startswith("-PconsumerRepo=")))
            (repo / GROUP.replace(".", "/") / artifact / VERSION / f"{artifact}-{VERSION}{ending}").write_bytes(b"changed native dependency input")
    if os.environ.get("FAKE_TOOLING_CHANGE"):
        repo = Path(next(arg.split("=", 1)[1] for arg in args if arg.startswith("-PconsumerRepo=")))
        tooling = repo / GROUP.replace(".", "/") / "p2p-core" / VERSION / f"p2p-core-{VERSION}-kotlin-tooling-metadata.json"
        if os.environ["FAKE_TOOLING_CHANGE"] == "delete":
            tooling.unlink()
        else:
            tooling.write_text('{"changedAfterPreparation":true}\n')
    if os.environ.get("FAKE_PLUGIN_INPUT_CHANGE"):
        name = os.environ["FAKE_PLUGIN_INPUT_CHANGE"]
        target = fixture / name
        target.write_bytes(target.read_bytes() + b"\n# changed after preparation\n")

def main():
    name, args = Path(sys.argv[0]).name, sys.argv[1:]
    if name == "git":
        record("git", argv=args, cwd=os.getcwd())
        return subprocess.run([os.environ["FAKE_REAL_GIT"], *args]).returncode
    if name == "executor with spaces":
        parser = argparse.ArgumentParser()
        for option in ["cwd", "wrapper", "purpose", "receipt"]:
            parser.add_argument("--" + option, required=True)
        before_separator = args.index("--")
        request = parser.parse_args(args[:before_separator])
        arguments = args[before_separator + 1:]
        record("executor", argv=args, cwd=os.getcwd(), requested=arguments, purpose=request.purpose)
        if os.environ.get("FAKE_EXECUTOR_FAILURE") == request.purpose:
            return 125
        before = snapshot(request.cwd)
        product = subprocess.run([request.wrapper, *arguments], cwd=request.cwd).returncode
        stop = subprocess.run([request.wrapper, "--stop"], cwd=request.cwd).returncode
        after = snapshot(request.cwd)
        result = 125 if stop != 0 or before != after else product
        receipt = {
            "schema": 1, "id": request.purpose + "-fixture-leaf", "purpose": request.purpose,
            "requestedArgv": arguments, "cwd": request.cwd, "wrapper": request.wrapper,
            "sourceBefore": before, "sourceAfter": after, "sourceUnchanged": before == after,
            "productExitCode": product, "stopExitCode": stop, "finalExitCode": result,
            "ownedSurvivors": [], "errors": [] if result != 125 else ["fixture infrastructure failure"],
        }
        if request.purpose == "consumer-publish" and os.environ.get("FAKE_RECEIPT_MUTATION"):
            receipt.update(json.loads(os.environ["FAKE_RECEIPT_MUTATION"]))
        if request.purpose == "consumer-build" and os.environ.get("FAKE_CONSUMER_RECEIPT_MUTATION"):
            receipt.update(json.loads(os.environ["FAKE_CONSUMER_RECEIPT_MUTATION"]))
        if os.environ.get("FAKE_MISSING_RECEIPT") != request.purpose:
            with open(request.receipt, "x", encoding="utf-8") as stream:
                json.dump(receipt, stream)
        return result
    if name == "gradlew":
        stopping = args and args[0] == "--stop"
        record("gradle-stop" if stopping else "gradle", argv=args, cwd=os.getcwd(), home=os.environ.get("GRADLE_USER_HOME"))
        if stopping:
            native_stop = ["--stop", "--console=plain", "--no-parallel", "--max-workers=2",
                           "-Dorg.gradle.jvmargs=-Xmx2048m -XX:MaxMetaspaceSize=768m -XX:ActiveProcessorCount=2 -Dfile.encoding=UTF-8"]
            assert args == ["--stop"] or args == native_stop, args
            print("SYNTHETIC CONSUMER WRAPPER STOP", flush=True)
            return int(os.environ.get("FAKE_STOP_EXIT", "0"))
        if "publishToMavenLocal" in args or any(task in args for task in FOCUSED_PUBLISH_TASKS):
            repo = Path(next(arg.split("=", 1)[1] for arg in args if arg.startswith("-Dmaven.repo.local=")))
            scoped_tasks = [arg for arg in args if arg.startswith(":")]
            if "publishToMavenLocal" in args:
                assert not scoped_tasks, args
                publish(repo, PUBLICATIONS)
            else:
                assert scoped_tasks == FOCUSED_PUBLISH_TASKS, args
                publish(repo, FOCUSED_PUBLICATIONS)
            if os.environ.get("FAKE_CONSUMER_OWNERSHIP_READY"):
                # Only the explicit native-selftest producer selects this mode.
                # Inherit the actual fixture environment without repairing it:
                # the native enclosing scope must detect any lost ancestor.
                worker = "import json, os, pathlib, signal, sys, time\nfields = " + repr(OWNERSHIP_FIELDS) + "\n" + """
ready = pathlib.Path(sys.argv[1])
signal.signal(signal.SIGTERM, signal.SIG_IGN)
record = {"schema": 1, "kind": "consumer-ownership-cancellation-fixture",
          "workerPid": os.getpid(), "producerPid": int(sys.argv[2]),
          "ownership": {name: os.environ.get(name) for name in fields}}
pending = ready.with_name(ready.name + ".pending")
with pending.open("x", encoding="utf-8") as stream:
    stream.write(json.dumps(record) + "\\n")
    stream.flush()
    os.fsync(stream.fileno())
os.link(pending, ready)
pending.unlink()
time.sleep(120)
"""
                ready = Path(os.environ["FAKE_CONSUMER_OWNERSHIP_READY"])
                subprocess.Popen([sys.executable, "-c", worker, str(ready), str(os.getpid())],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 start_new_session=True)
                deadline = time.monotonic() + 10
                while not ready.exists():
                    if time.monotonic() >= deadline:
                        raise AssertionError("cancellation fixture worker did not become ready")
                    time.sleep(.02)
                time.sleep(120)
                raise AssertionError("native cancellation did not stop the long-lived consumer fixture")
            return int(os.environ.get("FAKE_PUBLISH_EXIT", "0"))
        build(args)
        return int(os.environ.get("FAKE_BUILD_EXIT", "0"))
    if name == "xcrun":
        record("xcrun", argv=args)
        print("platform " + os.environ.get("FAKE_PLATFORM", "IOSSIMULATOR"))
        print("minos " + os.environ.get("FAKE_MINOS", "14.0"))
        return 0
    if name == "curl":
        record("curl", argv=args)
        target = Path(args[args.index("--output") + 1])
        artifact = target.parent.parent.name
        if target.suffix == ".module":
            filename = f"{artifact}-{VERSION}{dict(FOCUSED_PUBLICATIONS)[artifact]}"
            content = ("synthetic fixture artifact " + filename + "\n").encode()
            binary = {"name": filename, "url": filename, "size": len(content),
                      "sha256": hashlib.sha256(content).hexdigest()}
            target.write_text(json.dumps({
                "formatVersion": "1.1", "component": {"group": GROUP, "module": "p2p-transport-lan", "version": VERSION},
                "variants": lan_variants(artifact, [
                    {"name": "apiElements", "files": [dict(binary)]},
                    {"name": "runtimeElements", "files": [dict(binary)]},
                ]),
            }))
        else:
            target.write_text(pom(artifact))
        return 0
    raise AssertionError("unexpected fake tool: " + name)

sys.exit(main())
'''


def source_snapshot(root, env):
    def git(*arguments):
        return subprocess.check_output(["git", "-C", str(root), *arguments], env=env)
    return {
        "commit": git("rev-parse", "HEAD").decode().strip(),
        "tree": git("rev-parse", "HEAD^{tree}").decode().strip(),
        "status": git("status", "--porcelain=v1", "--untracked-files=all").decode(),
        "diffSha256": hashlib.sha256(git("--no-pager", "diff", "--binary", "--no-ext-diff", "--no-textconv", "HEAD", "--")).hexdigest(),
    }


def ownership_observation(environment):
    return {name: environment.get(name) for name in OWNERSHIP_FIELDS}


def write_fixture_record(path, value):
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(value, indent=2) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


class ConsumerGateTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="p2pkit consumer boundary ")
        if getattr(self, "fixture_evidence", None) is None:
            self.addCleanup(self.temporary.cleanup)
        else:
            # Native cancellation may end this producer without finally. Its
            # enclosing fixture owns TMPDIR and removes these bytes only after
            # actual worker drain and evidence retention, never on a fake verdict.
            self.temporary._finalizer.detach()
        self.base = Path(self.temporary.name).resolve()
        if getattr(self, "fixture_evidence", None) is not None:
            write_fixture_record(self.fixture_evidence / "fixture-created.json", {
                "schema": 1, "fixtureBase": str(self.base),
                "retention": "Native enclosing fixture owns this TMPDIR; drain before disposing generated bytes.",
            })
        self.root = self.base / "checkout λ with spaces"
        self.tools = self.base / "tool boundaries with spaces"
        self.state = self.base / "audit state with spaces"
        self.work_root = self.state / "work"
        self.work = self.work_root / "borrowed consumer λ directory"
        self.calls_file = getattr(self, "fixture_evidence", self.base) / "calls.jsonl"
        for path in (self.root / "scripts", self.root / "gradle", self.tools, self.state, self.work_root,
                     self.base / "temporary"):
            path.mkdir(parents=True)
        for name in ("check-published-consumers.sh", "prepare-audit-consumer-metadata.py", "check-audit-receipt.py",
                     "consumer-buildscript.gradle.kts"):
            shutil.copy2(ROOT / "scripts" / name, self.root / "scripts" / name)
        (self.root / "buildscript-gradle.lockfile").write_text(
            "# Synthetic plugin graph data, not a real Gradle-resolution result.\n"
            "org.jetbrains.kotlin.jvm:org.jetbrains.kotlin.jvm.gradle.plugin:91.0.0=classpath\n"
            "org.jetbrains.kotlin.multiplatform:org.jetbrains.kotlin.multiplatform.gradle.plugin:91.0.0=classpath\n"
            "com.android.application:com.android.application.gradle.plugin:92.0.0=classpath\n"
            "com.android.kotlin.multiplatform.library:com.android.kotlin.multiplatform.library.gradle.plugin:92.0.0=classpath\n"
            "org.example.reviewed:external:1.0=classpath\nempty=\n"
        )
        (self.root / "gradle.properties").write_text(
            f"GROUP={GROUP}\nVERSION_NAME={VERSION}\nLATEST_PUBLISHED_VERSION={VERSION.removesuffix('-SNAPSHOT')}\nIOS_MIN_VERSION=14.0\n"
        )
        (self.root / "gradle/libs.versions.toml").write_text(
            f'[versions]\nkotlin = "{KOTLIN_VERSION}"\nagp = "92.0.0"\ncoroutines = "{COROUTINES_VERSION}"\n'
        )
        self.reviewed = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<verification-metadata xmlns="{NAMESPACE}">\n'
            '   <configuration>\n      <verify-metadata>true</verify-metadata>\n'
            '      <verify-signatures>false</verify-signatures>\n   </configuration>\n   <components>\n'
            '      <component group="org.example.reviewed" name="external" version="1.0">\n'
            '         <artifact name="external-1.0.jar">\n'
            f'            <sha256 value="{EXTERNAL_SHA256}" origin="reviewed fixture"/>\n'
            '         </artifact>\n      </component>\n   </components>\n</verification-metadata>\n'
        ).encode()
        (self.root / "gradle/verification-metadata.xml").write_bytes(self.reviewed)
        code = BOUNDARY
        for key, value in {
            "PUBLICATIONS": EXPECTED_PUBLICATIONS, "DEPS": POM_DEPENDENCIES, "PERMISSIONS": PERMISSIONS,
            "FOCUSED_PUBLICATIONS": EXPECTED_FOCUSED_PUBLICATIONS,
            "FOCUSED_PUBLISH_TASKS": EXPECTED_FOCUSED_PUBLISH_TASKS, "EMBEDDED_TASKS": EXPECTED_EMBEDDED_TASKS,
            "TOOLING_PUBLICATIONS": EXPECTED_TOOLING_PUBLICATIONS,
            "NATIVE_PUBLICATIONS": EXPECTED_NATIVE_PUBLICATIONS, "INTEROP_PUBLICATIONS": EXPECTED_INTEROP_PUBLICATIONS,
            "LOGICAL_ALIASES": EXPECTED_LOGICAL_ALIASES,
            "GROUP": GROUP, "VERSION": VERSION, "KOTLIN_VERSION": KOTLIN_VERSION,
            "COROUTINES_VERSION": COROUTINES_VERSION, "EXTERNAL_SHA256": EXTERNAL_SHA256,
            "OWNERSHIP_FIELDS": OWNERSHIP_FIELDS, "CONSUMER_REPORT_BYTES": CONSUMER_REPORT_BYTES,
            "PACKAGING_REPORT_BYTES": PACKAGING_REPORT_BYTES, "PACKAGING_REPORT_PATH": PACKAGING_REPORT_PATH,
            "EXPECTED_APKS": EXPECTED_APKS,
        }.items():
            code = code.replace("__" + key + "__", repr(value))
        for path in (self.root / "gradlew", self.tools / "executor with spaces", self.tools / "xcrun", self.tools / "curl",
                     self.tools / "git"):
            path.write_text(code)
            path.chmod(0o755)
        env = dict(os.environ)
        for key in list(env):
            # Opt-in isolation must never erase the enclosing controller's
            # ownership, including private/future audit ancestor markers.
            if ((key.startswith("P2PKIT_") and not key.startswith("P2PKIT_AUDIT_")) or
                    key in {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "FAKE_CONSUMER_OWNERSHIP_READY"}):
                env.pop(key)
        real_git = shutil.which("git", path=env.get("PATH"))
        self.assertIsNotNone(real_git, "real Git is required for the isolated source fixture")
        env.update({
            "PATH": str(self.tools) + os.pathsep + env["PATH"],
            "TMPDIR": str(self.base / "temporary"), "ANDROID_HOME": str(self.base / "synthetic sdk"),
            "FAKE_CALLS": str(self.calls_file), "FAKE_REAL_GIT": real_git,
            "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
        })
        self.env = env
        for args in (["init", "-q"], ["config", "user.name", "Audit fixture"],
                     ["config", "user.email", "audit-fixture@example.invalid"], ["add", "."],
                     ["-c", "commit.gpgsign=false", "commit", "-qm", "Synthetic consumer fixture"]):
            subprocess.run(["git", "-C", str(self.root), *args], env=self.env, check=True, capture_output=True)
        source = source_snapshot(self.root, self.env)
        self.fixture_job = uuid.uuid4().hex
        (self.state / "gradle-home").mkdir()
        (self.state / "context.json").write_text(json.dumps({
            "schema": 1, "id": self.fixture_job, "root": str(self.root), "expectedCommit": source["commit"],
            "tree": source["tree"], "source": source, "host": "fixture-not-native-host-proof",
            "gradleHome": str(self.state / "gradle-home"), "createdUtc": "2026-09-08T00:00:00+00:00",
        }))

    def fixture_environment(self, home, *, state=None):
        return processes.ownership_environment(self.env, self.fixture_job, uuid.uuid4().hex,
                                               str(self.state if state is None else state), str(home),
                                               allow_new_context=True)

    def run_gate(self, overrides=None, arguments=(), *, home=None, capture_directory=None):
        env = {**(self.env if home is None else self.fixture_environment(home)), **(overrides or {})}
        command = ["bash", str(self.root / "scripts/check-published-consumers.sh"), *arguments]
        if capture_directory is None:
            return subprocess.run(command, cwd=self.base, env=env, text=True, capture_output=True)
        with (capture_directory / "consumer.stdout.log").open("xb") as stdout, \
                (capture_directory / "consumer.stderr.log").open("xb") as stderr:
            result = subprocess.run(command, cwd=self.base, env=env, stdout=stdout, stderr=stderr)
            for stream in (stdout, stderr):
                stream.flush()
                os.fsync(stream.fileno())
            return result

    def adapter_options(self, work=None):
        work = self.work_root / ("borrowed " + uuid.uuid4().hex) if work is None else work
        return {**self.fixture_environment(self.state / "gradle-home"),
                "P2PKIT_GRADLE_EXECUTOR": str(self.tools / "executor with spaces"),
                "P2PKIT_CONSUMER_WORK_DIR": str(work)}

    def audit_options(self):
        return {**self.adapter_options(self.work), "P2PKIT_CONSUMER_AUDIT_METADATA": "1"}

    def calls(self, kind=None):
        rows = [json.loads(line) for line in self.calls_file.read_text().splitlines()] if self.calls_file.exists() else []
        return [row for row in rows if kind is None or row["kind"] == kind]

    def output(self, result):
        return f"exit={result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    def assert_pass(self, result):
        self.assertEqual(result.returncode, 0, self.output(result))
        self.assertIn("RESULT: PASS — published scopes", result.stdout)

    def assert_rejected(self, result, message=None):
        self.assertNotEqual(result.returncode, 0, self.output(result))
        self.assertNotIn("RESULT: PASS", result.stdout)
        if message is not None:
            self.assertIn(message, result.stdout + result.stderr, self.output(result))

    def published_work(self, call):
        repository = next(arg.split("=", 1)[1] for arg in call["argv"] if arg.startswith("-Dmaven.repo.local="))
        return Path(repository).parent

    def assert_complete_arguments(self, leaves):
        self.assertEqual(len(leaves), 2)
        work = self.published_work(leaves[0])
        self.assertEqual(leaves[0]["argv"], ["--no-daemon", "--console=plain", "publishToMavenLocal", f"-Dmaven.repo.local={work / 'repository'}"])
        self.assertEqual(leaves[1]["argv"], ["--no-daemon", "--console=plain", "-p", str(work / "consumer"),
                                                   f"-PconsumerRepo={work / 'repository'}", *EXPECTED_TASKS])
        self.assertEqual([row["cwd"] for row in leaves], [str(self.root), str(self.root)])
        return work

    def assert_ancestor_bindings(self, rows):
        self.assertTrue(rows, "the asserted boundary must actually execute")
        ancestors = processes.ownership_domains(self.env.get(processes.CHAIN_ENV, ""),
                                                 self.env.get(processes.DOMAINS_ENV, ""))
        for row in rows:
            observation = row["ownership"]
            domains = processes.ownership_domains(observation[processes.CHAIN_ENV] or "",
                                                   observation[processes.DOMAINS_ENV] or "")
            self.assertEqual(domains[:len(ancestors)], ancestors, row)
            if domains:
                self.assertEqual(observation[processes.JOB_ENV], domains[-1]["job"], row)
                self.assertEqual(observation[processes.STATE_ENV], domains[-1]["state"], row)
                self.assertEqual(observation["GRADLE_USER_HOME"], domains[-1]["home"], row)
            for name in ("P2PKIT_AUDIT_INVOCATION", "P2PKIT_AUDIT_FIXTURE_ANCESTOR"):
                self.assertEqual(observation[name], self.env.get(name), row)

    def test_recorded_boundaries_preserve_inherited_ownership_and_isolate_non_audit_opt_ins(self):
        for name, value in os.environ.items():
            if name.startswith("P2PKIT_AUDIT_") or name == "GRADLE_USER_HOME":
                self.assertEqual(self.env.get(name), value, name)
        for name in ("P2PKIT_GRADLE_EXECUTOR", "P2PKIT_CONSUMER_WORK_DIR", "P2PKIT_CONSUMER_PROFILE",
                     "P2PKIT_TEST_NON_AUDIT_OPT_IN"):
            self.assertNotIn(name, self.env)

        self.assert_pass(self.run_gate())
        baseline = self.calls()
        self.assertEqual({row["kind"] for row in baseline}, {"git", "gradle", "xcrun"})
        for row in baseline:
            self.assertEqual(row["ownership"], ownership_observation(self.env))
        self.assert_ancestor_bindings(baseline)

        options = self.adapter_options(self.work)
        self.assert_pass(self.run_gate(options))
        nested = self.calls()[len(baseline):]
        self.assertEqual({row["kind"] for row in nested}, {"executor", "git", "gradle", "gradle-stop", "xcrun"})
        for row in nested:
            self.assertEqual(row["ownership"], ownership_observation(options))
        self.assert_ancestor_bindings(nested)
        domains = processes.ownership_domains(options[processes.CHAIN_ENV], options[processes.DOMAINS_ENV])
        self.assertEqual(domains[-1], {"id": options[processes.CHAIN_ENV].split(":")[-1],
                                      "job": self.fixture_job, "state": str(self.state),
                                      "home": str(self.state / "gradle-home")})

    def test_actual_fixture_caller_preserves_two_ancestor_domains(self):
        state = self.base / "synthetic enclosing state"
        state.mkdir()
        home = state / "gradle-home"
        home.mkdir()
        job, outer, inner = (uuid.uuid4().hex for _ in range(3))
        # Start from this interpreter's real caller, not its fake-tool PATH.
        environment = processes.ownership_environment(dict(os.environ), job, outer, str(state), str(home),
                                                       allow_new_context=True)
        environment = processes.ownership_environment(environment, job, inner, str(state), str(home))
        environment.setdefault("P2PKIT_AUDIT_INVOCATION", "private-parent-" + uuid.uuid4().hex)
        environment.update({"P2PKIT_AUDIT_FIXTURE_ANCESTOR": "future ancestor marker must survive",
                            "P2PKIT_GRADLE_EXECUTOR": "/not/a/fixture/executor",
                            "P2PKIT_CONSUMER_WORK_DIR": "/not/a/fixture/work-directory",
                            "P2PKIT_CONSUMER_PROFILE": "lan-jvm-android",
                            "P2PKIT_TEST_NON_AUDIT_OPT_IN": "must be isolated"})
        result = subprocess.run([sys.executable, str(Path(__file__).resolve()),
            "ConsumerGateTest.test_recorded_boundaries_preserve_inherited_ownership_and_isolate_non_audit_opt_ins"],
            cwd=ROOT, env=environment, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, self.output(result))
        self.assertIn("Ran 1 test", result.stderr)

    def test_default_keeps_exact_two_commands_and_disposes_work(self):
        result = self.run_gate(home=self.base / "normal caller home")
        self.assert_pass(result)
        work = self.assert_complete_arguments(self.calls("gradle"))
        self.assertFalse(work.exists())
        self.assertFalse(self.calls("executor"))
        self.assertEqual({row["home"] for row in self.calls("gradle")}, {str(self.base / "normal caller home")})
        self.assert_ancestor_bindings(self.calls("gradle"))

    def test_explicit_complete_profile_keeps_all_publications_native_tasks_and_embedded_tasks(self):
        result = self.run_gate({"P2PKIT_CONSUMER_PROFILE": "complete", "P2PKIT_CONSUMER_WORK_DIR": str(self.work)})
        self.assert_pass(result)
        work = self.assert_complete_arguments(self.calls("gradle"))
        publications = work / "repository" / GROUP.replace(".", "/")
        self.assertEqual({path.name for path in publications.iterdir()}, {name for name, _ in EXPECTED_PUBLICATIONS})
        self.assertEqual(len(self.calls("xcrun")), 1)
        self.assertEqual((work / "consumer" / PACKAGING_REPORT_PATH).read_bytes(), PACKAGING_REPORT_BYTES)

    def test_focused_profile_uses_only_five_publications_and_exact_embedded_tasks_without_native_tools(self):
        result = self.run_gate({"P2PKIT_CONSUMER_PROFILE": "lan-jvm-android",
                                "P2PKIT_CONSUMER_WORK_DIR": str(self.work), "FAKE_MISSING_FRAMEWORK": "1"})
        self.assertEqual(result.returncode, 0, self.output(result))
        self.assertIn("RESULT: PASS", result.stdout)
        self.assertIn("lan-jvm-android", result.stdout)
        self.assertNotIn("JVM/Android/KMP/iOS 14 consumers are complete", result.stdout)
        leaves = self.calls("gradle")
        self.assertEqual(len(leaves), 2)
        self.assertEqual(leaves[0]["argv"], ["--no-daemon", "--console=plain", *EXPECTED_FOCUSED_PUBLISH_TASKS,
                                            f"-Dmaven.repo.local={self.work / 'repository'}"])
        self.assertEqual(leaves[1]["argv"], ["--no-daemon", "--console=plain", "-p", str(self.work / "consumer"),
                                            f"-PconsumerRepo={self.work / 'repository'}", *EXPECTED_EMBEDDED_TASKS])
        self.assertEqual([row["cwd"] for row in leaves], [str(self.root), str(self.root)])
        publications = self.work / "repository" / GROUP.replace(".", "/")
        self.assertEqual({path.name for path in publications.iterdir()},
                         {name for name, _ in EXPECTED_FOCUSED_PUBLICATIONS})
        self.assertFalse(list(publications.rglob("*.klib")))
        settings = (self.work / "consumer/settings.gradle.kts").read_text()
        self.assertIn('":lanJvm"', settings)
        self.assertIn('":androidConsumer"', settings)
        self.assertNotIn('":kmpConsumer"', settings)
        self.assertNotIn('":desktopJvm"', settings)
        android_build = (self.work / "consumer/androidConsumer/build.gradle.kts").read_text()
        self.assertNotIn("p2p-network-provisioning", android_build)
        self.assertEqual((self.work / "consumer" / PACKAGING_REPORT_PATH).read_bytes(), PACKAGING_REPORT_BYTES)
        for variant, filename in EXPECTED_APKS.items():
            self.assertTrue((self.work / "consumer/androidConsumer/build/outputs/apk" / variant / filename).is_file())
        for kind in ("executor", "gradle-stop", "curl", "xcrun"):
            self.assertFalse(self.calls(kind), kind)
        self.assertFalse(list(self.state.glob("consumer-receipts.*")))
        self.assertFalse((self.work / "consumer/gradle/verification-metadata.xml").exists())
        self.assert_ancestor_bindings(leaves)

    def test_focused_executor_keeps_exact_tasks_and_stops_each_leaf_with_retained_receipts(self):
        result = self.run_gate({**self.adapter_options(self.work), "P2PKIT_CONSUMER_PROFILE": "lan-jvm-android",
                                "P2PKIT_CONSUMER_AUDIT_METADATA": "0", "FAKE_MISSING_FRAMEWORK": "1"})
        self.assertEqual(result.returncode, 0, self.output(result))
        self.assertIn("RESULT: PASS — supplemental lan-jvm-android", result.stdout)
        self.assertNotIn("RESULT: PASS — published scopes", result.stdout)
        self.assertEqual([row["kind"] for row in self.calls() if row["kind"] in
                          ("executor", "gradle", "gradle-stop")],
                         ["executor", "gradle", "gradle-stop", "executor", "gradle", "gradle-stop"])
        expected = [
            ["--no-daemon", "--console=plain", *EXPECTED_FOCUSED_PUBLISH_TASKS,
             f"-Dmaven.repo.local={self.work / 'repository'}"],
            ["--no-daemon", "--console=plain", "-p", str(self.work / "consumer"),
             f"-PconsumerRepo={self.work / 'repository'}", *EXPECTED_EMBEDDED_TASKS],
        ]
        leaves = self.calls("gradle")
        requests = self.calls("executor")
        self.assertEqual([row["argv"] for row in leaves], expected)
        self.assertEqual([row["requested"] for row in requests], expected)
        self.assertEqual([row["purpose"] for row in requests], ["consumer-publish", "consumer-build"])
        self.assertEqual([row["cwd"] for row in leaves], [str(self.root), str(self.root)])
        self.assertEqual({row["home"] for row in leaves + self.calls("gradle-stop")},
                         {str(self.state / "gradle-home")})
        receipt_directories = list(self.state.glob("consumer-receipts.*"))
        self.assertEqual(len(receipt_directories), 1)
        for row in requests:
            argv = row["argv"]
            self.assertEqual(argv[argv.index("--cwd") + 1], str(self.root))
            self.assertEqual(argv[argv.index("--wrapper") + 1], str(self.root / "gradlew"))
            receipt = Path(argv[argv.index("--receipt") + 1])
            self.assertEqual(receipt, receipt_directories[0] / (row["purpose"] + ".json"))
            record = json.loads(receipt.read_text())
            self.assertEqual(record["requestedArgv"], row["requested"])
            self.assertEqual([record[key] for key in ("productExitCode", "stopExitCode", "finalExitCode")], [0, 0, 0])
            self.assertTrue(record["sourceUnchanged"])
            self.assertEqual(record["sourceBefore"], record["sourceAfter"])
            self.assertEqual(record["errors"], [])
            self.assertEqual(record["ownedSurvivors"], [])
        publications = self.work / "repository" / GROUP.replace(".", "/")
        self.assertEqual({path.name for path in publications.iterdir()},
                         {name for name, _ in EXPECTED_FOCUSED_PUBLICATIONS})
        self.assertFalse(list(publications.rglob("*.klib")))
        self.assertFalse((receipt_directories[0] / "consumer-admission.json").exists())
        self.assertFalse((self.work / "consumer/gradle/verification-metadata.xml").exists())
        self.assertEqual((self.work / "consumer" / PACKAGING_REPORT_PATH).read_bytes(), PACKAGING_REPORT_BYTES)
        self.assertIn("script-owned=0", result.stderr)
        for kind in ("curl", "xcrun"):
            self.assertFalse(self.calls(kind), kind)
        self.assert_ancestor_bindings(leaves + self.calls("gradle-stop") + requests)

    def test_focused_executor_preserves_leaf_failures_and_borrowed_work(self):
        cases = [
            ({"FAKE_PUBLISH_EXIT": "23"}, 23, 1),
            ({"FAKE_BUILD_EXIT": "29"}, 29, 2),
            ({"FAKE_STOP_EXIT": "17"}, 125, 1),
        ]
        for purpose, mutation_key, count in (
                ("consumer-publish", "FAKE_RECEIPT_MUTATION", 1),
                ("consumer-build", "FAKE_CONSUMER_RECEIPT_MUTATION", 2)):
            cases.append(({"FAKE_MISSING_RECEIPT": purpose}, 125, count))
            for mutation in ({"requestedArgv": []}, {"ownedSurvivors": ["synthetic owned worker"]},
                             {"errors": ["unfinished evidence"]}, {"stopExitCode": 9}, {"sourceUnchanged": False}):
                cases.append(({mutation_key: json.dumps(mutation)}, 125, count))
        for overrides, code, count in cases:
            with self.subTest(overrides=overrides):
                options = self.adapter_options()
                work = Path(options["P2PKIT_CONSUMER_WORK_DIR"])
                before = {kind: len(self.calls(kind)) for kind in ("executor", "gradle", "gradle-stop")}
                result = self.run_gate({**options, "P2PKIT_CONSUMER_PROFILE": "lan-jvm-android", **overrides})
                self.assert_rejected(result, "invalid audit leaf receipt" if code == 125 else None)
                self.assertEqual(result.returncode, code, self.output(result))
                for kind, previous in before.items():
                    self.assertEqual(len(self.calls(kind)) - previous, count, kind)
                self.assertTrue((work / "repository").is_dir())
                self.assertEqual((work / "consumer").exists(), count == 2)
                self.assertFalse((work / "consumer/gradle/verification-metadata.xml").exists())
                self.assertIn("script-owned=0", result.stderr)
        for kind in ("curl", "xcrun"):
            self.assertFalse(self.calls(kind), kind)

    def test_unknown_profile_is_rejected_before_work_or_receipt_allocation(self):
        for profile in ("jvm-android", "complete ", "COMPLETE", "lan-jvm-android,complete", "*"):
            with self.subTest(profile=profile):
                result = self.run_gate({"P2PKIT_CONSUMER_PROFILE": profile, "P2PKIT_CONSUMER_WORK_DIR": str(self.work)})
                self.assert_rejected(result, "P2PKIT_CONSUMER_PROFILE accepts only")
                self.assertEqual(result.returncode, 2)
                self.assertFalse(self.work.exists())
        self.assertFalse(list(self.state.glob("consumer-receipts.*")))
        self.assertEqual(list((self.base / "temporary").iterdir()), [])
        for kind in ("executor", "gradle", "curl", "xcrun"):
            self.assertFalse(self.calls(kind), kind)

    def test_focused_profile_rejects_audit_metadata_remote_and_argument_modes(self):
        cases = [
            ({"P2PKIT_CONSUMER_AUDIT_METADATA": "1"}, ()),
            ({"P2PKIT_CONSUMER_REPOSITORY_URL": "https://repository.example.invalid/maven"}, ()),
            ({}, ("--latest-published",)),
            ({}, ("--bogus",)),
            ({}, ("-PconsumerRepo=/unadmitted",)),
        ]
        for executor in (False, True):
            options = self.adapter_options(self.work) if executor else {"P2PKIT_CONSUMER_WORK_DIR": str(self.work)}
            for overrides, arguments in cases:
                with self.subTest(executor=executor, overrides=overrides, arguments=arguments):
                    result = self.run_gate({**options, "P2PKIT_CONSUMER_PROFILE": "lan-jvm-android",
                                            **overrides}, arguments)
                    self.assert_rejected(result, "lan-jvm-android is source-local")
                    self.assertEqual(result.returncode, 2)
                    self.assertFalse(self.work.exists())
        self.assertFalse(list(self.state.glob("consumer-receipts.*")))
        self.assertEqual(list((self.base / "temporary").iterdir()), [])
        for kind in ("executor", "gradle", "curl", "xcrun"):
            self.assertFalse(self.calls(kind), kind)

    def test_default_failure_disposal_and_real_exit_are_unchanged(self):
        result = self.run_gate({"FAKE_PUBLISH_EXIT": "23"})
        self.assert_rejected(result)
        self.assertEqual(result.returncode, 23)
        self.assertEqual(len(self.calls("gradle")), 1)
        self.assertFalse(self.published_work(self.calls("gradle")[0]).exists())

    def test_kept_owned_work_survives_success_and_failure(self):
        for failure in ("0", "31"):
            with self.subTest(productExit=failure):
                result = self.run_gate({"P2PKIT_KEEP_CONSUMER_ARTIFACTS": "1", "FAKE_BUILD_EXIT": failure})
                self.assert_pass(result) if failure == "0" else self.assert_rejected(result)
                work = self.published_work(self.calls("gradle")[-2])
                self.assertTrue((work / "repository").is_dir())
                self.assertTrue((work / "consumer").is_dir())
                self.assertIn("Retained consumer work directory", result.stderr)

    def test_borrowed_new_and_empty_work_survive_success_and_failure(self):
        for existing, failure in ((False, "0"), (True, "27")):
            with self.subTest(existing=existing, productExit=failure):
                work = self.base / f"borrowed-{existing}"
                if existing:
                    work.mkdir()
                result = self.run_gate({"P2PKIT_CONSUMER_WORK_DIR": str(work), "FAKE_BUILD_EXIT": failure})
                self.assert_pass(result) if failure == "0" else self.assert_rejected(result)
                self.assertTrue((work / "repository").is_dir())
                self.assertTrue((work / "consumer").is_dir())

    def test_bad_borrowed_paths_never_delete_inputs(self):
        target = self.base / "external sentinel directory"
        target.mkdir()
        sentinel = target / "keep.txt"
        sentinel.write_bytes(b"caller bytes")
        symlink = self.base / "borrowed symlink"
        symlink.symlink_to(target, target_is_directory=True)
        ancestor = self.base / "symlink ancestor"
        ancestor.symlink_to(self.base, target_is_directory=True)
        file_path = self.base / "borrowed file"
        file_path.write_bytes(b"file sentinel")
        paths = ["relative", str(target), str(symlink), str(file_path), str(ancestor / "unused")]
        for path in paths:
            with self.subTest(path=path):
                self.assert_rejected(self.run_gate({"P2PKIT_CONSUMER_WORK_DIR": path}))
                self.assertEqual(sentinel.read_bytes(), b"caller bytes")
                self.assertEqual(file_path.read_bytes(), b"file sentinel")
        self.assertTrue(symlink.is_symlink())
        self.assertFalse(self.calls("gradle"))

    def test_bad_flags_and_arguments_leave_borrowed_directory(self):
        self.work.mkdir()
        for overrides, args in (({"P2PKIT_KEEP_CONSUMER_ARTIFACTS": "maybe"}, ()),
                                ({"P2PKIT_CONSUMER_AUDIT_METADATA": "2"}, ()), ({}, ("--bogus",))):
            with self.subTest(overrides=overrides, args=args):
                result = self.run_gate({"P2PKIT_CONSUMER_WORK_DIR": str(self.work), **overrides}, args)
                self.assert_rejected(result)
                self.assertTrue(self.work.is_dir())
                self.assertEqual(list(self.work.iterdir()), [])
        self.assertFalse(self.calls("gradle"))

    def test_supported_borrowed_adapter_preserves_argv_cwd_home_and_retains_work_and_receipts(self):
        result = self.run_gate(self.adapter_options())
        self.assert_pass(result)
        work = self.assert_complete_arguments(self.calls("gradle"))
        self.assertTrue((work / "repository").is_dir())
        self.assertTrue((work / "consumer").is_dir())
        settings = (work / "consumer/settings.gradle.kts").read_text()
        # Kotlin marker bytes differ between Central and the Plugin Portal.
        # Keep the reviewed routing/filter policy, not merely both repositories.
        self.assertEqual(settings.split("\nval currentSourceConsumer =", 1)[0], r'''pluginManagement {
    repositories {
        google {
            content {
                includeGroupByRegex("com\\.android.*")
                includeGroupByRegex("com\\.google.*")
                includeGroupByRegex("androidx.*")
            }
        }
        mavenCentral()
        gradlePluginPortal()
    }
}''')
        self.assertIn("\nval currentSourceConsumer = 1 == 1\n", settings)
        self.assertIn(self.work_root, work.parents)
        self.assertEqual({row["home"] for row in self.calls("gradle") + self.calls("gradle-stop")},
                         {str(self.state / "gradle-home")})
        requests = self.calls("executor")
        self.assertEqual([row["purpose"] for row in requests], ["consumer-publish", "consumer-build"])
        self.assertEqual(len(self.calls("gradle-stop")), 2)
        for row in requests:
            argv = row["argv"]
            self.assertEqual(argv[argv.index("--cwd") + 1], str(self.root))
            self.assertEqual(argv[argv.index("--wrapper") + 1], str(self.root / "gradlew"))
            receipt = Path(argv[argv.index("--receipt") + 1])
            self.assertTrue(receipt.is_file())
            self.assertIn(self.state, receipt.parents)
            self.assertEqual(json.loads(receipt.read_text())["requestedArgv"], row["requested"])

    def test_executor_rejects_implicit_owned_work_before_creating_fixtures_or_receipts(self):
        for keep in ("0", "1"):
            with self.subTest(keep=keep):
                options = self.adapter_options()
                options.pop("P2PKIT_CONSUMER_WORK_DIR")
                result = self.run_gate({**options, "P2PKIT_KEEP_CONSUMER_ARTIFACTS": keep})
                self.assert_rejected(result, "requires an explicit borrowed P2PKIT_CONSUMER_WORK_DIR")
                self.assertEqual(result.returncode, 2)
        self.assertEqual(list(self.work_root.iterdir()), [])
        self.assertEqual(list((self.base / "temporary").iterdir()), [])
        self.assertFalse(list(self.state.glob("consumer-receipts.*")))
        for kind in ("executor", "gradle", "curl", "xcrun"):
            self.assertFalse(self.calls(kind))

    def test_executor_accepts_empty_borrowed_work_with_metadata_explicitly_off_or_on(self):
        for metadata in ("0", "1"):
            with self.subTest(metadata=metadata):
                work = self.work_root / ("existing empty metadata " + metadata)
                work.mkdir()
                result = self.run_gate({**self.adapter_options(work), "P2PKIT_CONSUMER_AUDIT_METADATA": metadata})
                self.assert_pass(result)
                self.assertTrue((work / "repository").is_dir())
                self.assertTrue((work / "consumer").is_dir())
                self.assertEqual((work / "consumer/gradle/verification-metadata.xml").is_file(), metadata == "1")
                self.assertIn("script-owned=0", result.stderr)

    def test_executor_rejects_remote_latest_and_other_modes_before_fixture_creation(self):
        modes = [({}, ("--latest-published",)), ({}, ("--bogus",)),
                 ({"P2PKIT_CONSUMER_REPOSITORY_URL": "https://repository.example.invalid/maven"}, ()),
                 ({"P2PKIT_CONSUMER_REPOSITORY_URL": "https://repository.example.invalid/maven"},
                  ("--latest-published",))]
        for metadata in ("0", "1"):
            for overrides, arguments in modes:
                with self.subTest(metadata=metadata, overrides=overrides, arguments=arguments):
                    options = {**self.adapter_options(), "P2PKIT_CONSUMER_AUDIT_METADATA": metadata, **overrides}
                    result = self.run_gate(options, arguments)
                    self.assert_rejected(result, "supports only source-local publication")
                    self.assertEqual(result.returncode, 2)
                    self.assertFalse(Path(options["P2PKIT_CONSUMER_WORK_DIR"]).exists())
        self.assertFalse(list(self.state.glob("consumer-receipts.*")))
        for kind in ("executor", "gradle", "curl", "xcrun"):
            self.assertFalse(self.calls(kind))

    def test_executor_borrowing_rejects_nonempty_foreign_and_aliased_work_before_product(self):
        outside = self.base / "outside work"
        outside.mkdir()
        sentinel = outside / "sentinel.txt"
        sentinel.write_bytes(b"caller data must survive")
        empty = outside / "empty"
        empty.mkdir()
        nonempty = self.work_root / "not empty"
        nonempty.mkdir()
        (nonempty / "keep.txt").write_bytes(b"borrowed caller data")
        alias = self.work_root / "work alias"
        alias.symlink_to(outside, target_is_directory=True)
        for path in (outside / "new", empty, self.state / "not-work", self.work_root, nonempty, alias / "new"):
            with self.subTest(path=path):
                result = self.run_gate(self.adapter_options(path))
                self.assert_rejected(result)
                self.assertEqual(sentinel.read_bytes(), b"caller data must survive")
                self.assertEqual((nonempty / "keep.txt").read_bytes(), b"borrowed caller data")
        self.assertFalse((outside / "new").exists())
        self.assertFalse((self.state / "not-work").exists())
        self.assertEqual(list(empty.iterdir()), [])
        self.assertTrue(alias.is_symlink())
        self.assertFalse(self.calls("executor"))
        self.assertFalse(list(self.state.glob("consumer-receipts.*")))

    def test_executor_requires_physical_state_work_and_regular_context(self):
        alias = self.base / "state alias"
        alias.symlink_to(self.state, target_is_directory=True)
        options = self.adapter_options()
        options.update(self.fixture_environment(self.state / "gradle-home", state=alias))
        self.assert_rejected(self.run_gate(options), "initialized P2PKIT_AUDIT_STATE_DIR")
        self.work_root.rmdir()
        self.assert_rejected(self.run_gate(self.adapter_options()), "initialized physical STATE/work")
        self.work_root.mkdir()
        context = self.state / "context.json"
        original = self.base / "original-context.json"
        context.rename(original)
        context.symlink_to(original)
        self.assert_rejected(self.run_gate(self.adapter_options()), "initialized P2PKIT_AUDIT_STATE_DIR")
        self.assertTrue(context.is_symlink())
        self.assertTrue(original.is_file())
        self.assertFalse(self.calls("executor"))
        self.assertFalse(list(self.state.glob("consumer-receipts.*")))

    def test_executor_unknown_or_unfinished_cleanup_never_deletes_borrowed_publication(self):
        for mutation in ({"ownedSurvivors": ["synthetic owned worker"]}, {"errors": ["unfinished evidence"]},
                         {"stopExitCode": 9}, {"sourceUnchanged": False}):
            with self.subTest(mutation=mutation):
                options = self.adapter_options()
                work = Path(options["P2PKIT_CONSUMER_WORK_DIR"])
                result = self.run_gate({**options, "FAKE_RECEIPT_MUTATION": json.dumps(mutation)})
                self.assert_rejected(result, "invalid audit leaf receipt")
                self.assertEqual(result.returncode, 125)
                artifact = work / "repository" / GROUP.replace(".", "/") / "p2p-core-jvm" / VERSION / f"p2p-core-jvm-{VERSION}.jar"
                self.assertEqual(artifact.read_bytes(), f"synthetic fixture artifact {artifact.name}\n".encode())
                self.assertIn("script-owned=0", result.stderr)
                self.assertFalse((work / "consumer").exists())

    def test_adapter_nonmetadata_rejects_missing_or_wrong_receipt(self):
        for purpose in ("consumer-publish", "consumer-build"):
            with self.subTest(missingPurpose=purpose):
                result = self.run_gate({**self.adapter_options(), "FAKE_MISSING_RECEIPT": purpose})
                self.assert_rejected(result, "invalid audit leaf receipt")
                self.assertEqual(result.returncode, 125)
        result = self.run_gate({**self.adapter_options(), "FAKE_RECEIPT_MUTATION": json.dumps({"requestedArgv": []})})
        self.assert_rejected(result, "argument vector differs")
        self.assertEqual(result.returncode, 125)

    def test_adapter_product_nonzero_is_not_hidden_or_reclassified(self):
        for name, value in (("FAKE_PUBLISH_EXIT", "23"), ("FAKE_BUILD_EXIT", "29")):
            with self.subTest(failure=name):
                result = self.run_gate({**self.adapter_options(), name: value})
                self.assert_rejected(result)
                self.assertEqual(result.returncode, int(value))

    def test_invalid_executor_never_falls_back_to_wrapper(self):
        nonexec = self.tools / "not executable"
        nonexec.write_text("not an executable")
        for path in ("relative-executor", str(nonexec), str(self.tools / "missing"), str(self.tools / "executor with spaces") + " --pretend"):
            with self.subTest(path=path):
                self.assert_rejected(self.run_gate({**self.adapter_options(), "P2PKIT_GRADLE_EXECUTOR": path}))
        self.assertFalse(self.calls("gradle"))

    def test_executor_failure_blocks_second_leaf_and_keeps_borrowed_bytes(self):
        result = self.run_gate({**self.audit_options(), "FAKE_EXECUTOR_FAILURE": "consumer-build"})
        self.assert_rejected(result)
        self.assertEqual(result.returncode, 125)
        self.assertEqual(len(self.calls("gradle")), 1)
        self.assertTrue((self.work / "repository").is_dir())
        self.assertTrue((self.work / "consumer/gradle/verification-metadata.xml").is_file())

    def test_owned_stop_failure_is_not_a_consumer_pass(self):
        result = self.run_gate({**self.audit_options(), "FAKE_STOP_EXIT": "17"})
        self.assert_rejected(result)
        self.assertEqual(result.returncode, 125)
        self.assertEqual(len(self.calls("gradle")), 1)
        self.assertTrue((self.work / "repository").is_dir())
        receipt = json.loads(next(self.state.glob("consumer-receipts.*/consumer-publish.json")).read_text())
        self.assertEqual(receipt["productExitCode"], 0)
        self.assertEqual(receipt["stopExitCode"], 17)

    def test_remote_mode_keeps_refresh_and_private_home_without_publication(self):
        result = self.run_gate({"P2PKIT_CONSUMER_REPOSITORY_URL": "https://repository.example.invalid/maven",
                                "P2PKIT_CONSUMER_WORK_DIR": str(self.work)}, home=self.work / "gradle-home")
        self.assert_pass(result)
        leaves = self.calls("gradle")
        self.assertEqual(len(leaves), 1)
        self.assertIn("--refresh-dependencies", leaves[0]["argv"])
        self.assertIn("-PconsumerRepo=https://repository.example.invalid/maven", leaves[0]["argv"])
        self.assertEqual(leaves[0]["argv"][-len(EXPECTED_TASKS):], EXPECTED_TASKS)
        self.assertEqual(leaves[0]["home"], str(self.work / "gradle-home"))
        expected_metadata = [
            ("p2p-core-jvm", ".pom"), ("p2p-transport-lan-jvm", ".pom"),
            ("p2p-network-provisioning-android-android", ".pom"), ("p2p-network-provisioning-desktop", ".pom"),
            ("p2p-transport-lan-android", ".pom"), ("p2p-transport-lan-jvm", ".module"),
            ("p2p-transport-lan-android", ".module"),
        ]
        downloads = self.calls("curl")
        self.assertEqual(len(downloads), len(expected_metadata))
        for call, (artifact, suffix) in zip(downloads, expected_metadata):
            relative = f"{GROUP.replace('.', '/')}/{artifact}/{VERSION}/{artifact}-{VERSION}{suffix}"
            self.assertEqual(call["argv"], ["--fail", "--silent", "--show-error", "--location",
                                            f"https://repository.example.invalid/maven/{relative}",
                                            "--output", str(self.work / "repository" / relative)])
        self.assert_ancestor_bindings(self.calls("curl") + self.calls("gradle") + self.calls("xcrun"))

    def test_latest_published_keeps_historical_upstream_graph_and_original_ten_tasks(self):
        result = self.run_gate({"P2PKIT_CONSUMER_REPOSITORY_URL": "https://repository.example.invalid/maven",
                                "P2PKIT_CONSUMER_WORK_DIR": str(self.work), "FAKE_LEGACY_JMDNS": "1",
                                "FAKE_MISSING_PACKAGING_REPORT": "1", "FAKE_MISSING_APK": "debug"},
                               arguments=("--latest-published",), home=self.work / "gradle-home")
        self.assert_pass(result)
        leaves = self.calls("gradle")
        self.assertEqual(len(leaves), 1)
        self.assertEqual(leaves[0]["argv"], ["--no-daemon", "--console=plain", "-p", str(self.work / "consumer"),
                                            "-PconsumerRepo=https://repository.example.invalid/maven",
                                            "--refresh-dependencies", *EXPECTED_LEGACY_TASKS])
        self.assertEqual(leaves[0]["home"], str(self.work / "gradle-home"))
        expected_metadata = ["p2p-core-jvm", "p2p-transport-lan-jvm",
                             "p2p-network-provisioning-android-android", "p2p-network-provisioning-desktop"]
        downloads = self.calls("curl")
        self.assertEqual(len(downloads), 4)
        for call, artifact in zip(downloads, expected_metadata):
            relative = f"{GROUP.replace('.', '/')}/{artifact}/{VERSION}/{artifact}-{VERSION}.pom"
            self.assertEqual(call["argv"], ["--fail", "--silent", "--show-error", "--location",
                                            f"https://repository.example.invalid/maven/{relative}",
                                            "--output", str(self.work / "repository" / relative)])
        self.assertFalse((self.work / "consumer" / PACKAGING_REPORT_PATH).exists())
        self.assertEqual(len(self.calls("xcrun")), 1)
        self.assertFalse(self.calls("executor"))

    def test_current_source_modes_do_not_fall_back_to_the_historical_jmdns_graph(self):
        for repository in ("", "https://repository.example.invalid/maven"):
            with self.subTest(repository=repository):
                count = len(self.calls("gradle"))
                result = self.run_gate({"P2PKIT_CONSUMER_REPOSITORY_URL": repository, "FAKE_LEGACY_JMDNS": "1"})
                self.assert_rejected(result, "slf4j-api scope was")
                self.assertEqual(len(self.calls("gradle")) - count, 0 if repository else 1)
        self.assertFalse(self.calls("xcrun"))

    def test_audit_metadata_is_explicit_local_only(self):
        for overrides, args, message in (
                ({"P2PKIT_CONSUMER_AUDIT_METADATA": "1"}, (), "requires the executor and source-local publication mode"),
                ({**self.audit_options(), "P2PKIT_CONSUMER_REPOSITORY_URL": "https://repo.example.invalid"}, (),
                 "supports only source-local publication"),
                (self.audit_options(), ("--latest-published",), "supports only source-local publication")):
            with self.subTest(overrides=overrides, args=args):
                self.assert_rejected(self.run_gate(overrides, args), message)
        self.assertFalse(self.calls("gradle"))
        self.assertFalse(self.calls("curl"))

    def test_metadata_preserves_external_bytes_and_only_exact_84_local_hashes(self):
        result = self.run_gate(self.audit_options())
        self.assert_pass(result)
        metadata = (self.work / "consumer/gradle/verification-metadata.xml").read_bytes()
        marker = f'      <component group="{GROUP}"'.encode()
        first_local = metadata.index(marker)
        end_local = metadata.index(b"   </components>\n", first_local)
        self.assertEqual(metadata[:first_local] + metadata[end_local:], self.reviewed)
        tree = ET.fromstring(metadata)
        components = tree.find(f"{{{NAMESPACE}}}components")
        local = [node for node in components if node.get("group") == GROUP]
        self.assertEqual({node.get("name") for node in local}, {name for name, _ in EXPECTED_PUBLICATIONS})
        actual = {}
        expected_alias_records = {}
        record_count = 0
        for component in local:
            self.assertEqual(component.get("version"), VERSION)
            module = component.get("name")
            endings = [dict(EXPECTED_PUBLICATIONS)[module], "-sources.jar", "-javadoc.jar", ".pom", ".module"]
            if module in EXPECTED_NATIVE_PUBLICATIONS:
                endings.append("-metadata.jar")
            if module in EXPECTED_INTEROP_PUBLICATIONS:
                endings.append("-cinterop-p2pkit_nw.klib")
            aliases = {name: url for owner, name, url in EXPECTED_LOGICAL_ALIASES if owner == module}
            expected_names = {f"{module}-{VERSION}{ending}": f"{module}-{VERSION}{ending}" for ending in endings}
            expected_names.update(aliases)
            self.assertEqual({artifact.get("name") for artifact in component}, set(expected_names))
            self.assertEqual(len(component), len(expected_names))
            record_count += len(component)
            for artifact in component:
                name = artifact.get("name")
                relative = Path(GROUP.replace(".", "/")) / module / VERSION / expected_names[name]
                content = (self.work / "repository" / relative).read_bytes()
                actual[relative.as_posix()] = artifact[0].get("value")
                self.assertEqual(len(artifact), 1)
                self.assertEqual(artifact[0].tag, f"{{{NAMESPACE}}}sha256")
                self.assertEqual(artifact[0].get("value"), hashlib.sha256(content).hexdigest())
                if name in aliases:
                    expected_alias_records[(module, name)] = {
                        "group": GROUP, "module": module, "version": VERSION, "name": name,
                        "path": relative.as_posix(), "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content),
                    }
        self.assertEqual(len(actual), 84)
        self.assertEqual(len(expected_alias_records), 18)
        self.assertEqual(record_count, 102)
        self.assertNotIn(b"<trust", metadata)
        manifest_path = next(self.state.glob("consumer-receipts.*/consumer-publication-manifest.json"))
        manifest = json.loads(manifest_path.read_text())
        self.assertEqual(manifest["publicationCount"], 15)
        self.assertEqual(manifest["artifactCount"], 84)
        self.assertEqual(manifest["verificationRecordCount"], 102)
        self.assertEqual(len(manifest["localArtifacts"]), 84)
        self.assertEqual(len(manifest["logicalAliases"]), 18)
        self.assertEqual({(row["module"], row["name"]): row for row in manifest["logicalAliases"]}, expected_alias_records)
        self.assertIn("Gradle skips per-artifact verification for changing/SNAPSHOT modules", manifest["limitations"])
        self.assertEqual(len(manifest["repositoryFiles"]), 117)
        for module in EXPECTED_TOOLING_PUBLICATIONS:
            relative = (Path(GROUP.replace(".", "/")) / module / VERSION /
                        f"{module}-{VERSION}-kotlin-tooling-metadata.json").as_posix()
            content = (self.work / "repository" / relative).read_bytes()
            self.assertEqual(manifest["repositoryFiles"][relative],
                             {"bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()})
            self.assertNotIn(relative, actual, "tooling sidecars must not expand the trusted artifact set")
        self.assertEqual({row["path"]: row["sha256"] for row in manifest["localArtifacts"]}, actual)
        evidence = manifest_path.parent
        self.assertEqual((evidence / "reviewed-verification-metadata.xml").read_bytes(), self.reviewed)
        verification = json.loads((evidence / "consumer-metadata-verification.json").read_text())
        self.assertEqual(verification["result"], "PASS")
        self.assertEqual(verification["artifactCount"], 84)
        self.assertEqual(verification["verificationRecordCount"], 102)
        self.assertEqual(manifest["reviewedPluginInputs"], {
            name: hashlib.sha256((self.root / name).read_bytes()).hexdigest()
            for name in ("scripts/consumer-buildscript.gradle.kts", "buildscript-gradle.lockfile")
        })
        self.assertEqual((self.work / "consumer/consumer-plugin-versions.lock").read_bytes(),
                         (self.root / "buildscript-gradle.lockfile").read_bytes())
        build_recipe = (self.work / "consumer/build.gradle.kts").read_text()
        self.assertTrue(build_recipe.startswith((self.root / "scripts/consumer-buildscript.gradle.kts").read_text()))
        self.assertEqual(manifest["consumerRootBuildSha256"], hashlib.sha256(build_recipe.encode()).hexdigest())
        self.assertIn('kotlin("jvm") version "91.0.0"', build_recipe)
        self.assertIn('id("com.android.application") version "92.0.0"', build_recipe)
        self.assertIn('id("com.android.kotlin.multiplatform.library") version "92.0.0"', build_recipe)
        self.assertNotIn('id("com.android.library")', build_recipe)

    def test_consumer_plugin_policy_inputs_cannot_change_after_preparation(self):
        for name, message in (
                ("consumer-plugin-versions.lock", "copied consumer plugin versions differ"),
                ("build.gradle.kts", "prepared consumer publication binding changed: consumerRootBuildSha256")):
            with self.subTest(name=name):
                work = self.work_root / name
                result = self.run_gate({**self.audit_options(), "P2PKIT_CONSUMER_WORK_DIR": str(work),
                                        "FAKE_PLUGIN_INPUT_CHANGE": name})
                self.assert_rejected(result, message)
        self.assertFalse(list(self.state.glob("consumer-receipts.*/consumer-metadata-verification.json")))

    def test_module_file_aliases_cannot_expand_or_rebind_physical_trust(self):
        cases = (
            ("missing-alias", "missing required logical aliases"),
            ("unapproved-name", "unapproved source-local module file name"),
            ("wrong-target", "source-local module file URL mismatch"),
            ("traversal", "source-local module file URL mismatch"),
            ("remote", "source-local module file URL mismatch"),
            ("tooling-sidecar", "unapproved source-local module file name"),
            ("wrong-sha256", "source-local module file content mismatch"),
            ("wrong-size", "source-local module file content mismatch"),
            ("conflicting-alias", "conflicting source-local module file"),
        )
        for change, message in cases:
            with self.subTest(change=change):
                work = self.work_root / change
                result = self.run_gate({**self.audit_options(), "P2PKIT_CONSUMER_WORK_DIR": str(work),
                                        "FAKE_MODULE_FILE_CHANGE": change})
                self.assert_rejected(result, message)
                self.assertEqual(result.returncode, 125)
                self.assertFalse((work / "consumer/gradle/verification-metadata.xml").exists())
        self.assertEqual(len(self.calls("gradle")), len(cases), "only publication may execute for invalid GMM")
        self.assertFalse(list(self.state.glob("consumer-receipts.*/consumer-publication-manifest.json")))

    def test_missing_or_malformed_publication_receipt_cannot_prepare_trust(self):
        mutations = [
            {"schema": 2}, {"productExitCode": 1}, {"stopExitCode": 1}, {"finalExitCode": 125},
            {"sourceUnchanged": False}, {"ownedSurvivors": ["owned-worker"]}, {"errors": ["failed copy"]},
            {"sourceAfter": {}}, {"cwd": "/unexpected"}, {"wrapper": "/unexpected/gradlew"},
            {"purpose": "unrelated"}, {"requestedArgv": ["publishToMavenLocal", "-Dmaven.repo.local=/unexpected"]},
        ]
        for index, mutation in enumerate(mutations):
            with self.subTest(mutation=mutation):
                work = self.work_root / f"receipt mutation {index}"
                result = self.run_gate({**self.audit_options(), "P2PKIT_CONSUMER_WORK_DIR": str(work), "FAKE_RECEIPT_MUTATION": json.dumps(mutation)})
                self.assert_rejected(result)
                self.assertEqual(result.returncode, 125)
                self.assertFalse((work / "consumer/gradle/verification-metadata.xml").exists())
        work = self.work_root / "missing receipt"
        result = self.run_gate({**self.audit_options(), "P2PKIT_CONSUMER_WORK_DIR": str(work), "FAKE_MISSING_RECEIPT": "consumer-publish"})
        self.assert_rejected(result)
        self.assertFalse((work / "consumer/gradle/verification-metadata.xml").exists())

    def test_missing_consumer_receipt_cannot_issue_final_pass(self):
        result = self.run_gate({**self.audit_options(), "FAKE_MISSING_RECEIPT": "consumer-build"})
        self.assert_rejected(result)
        self.assertEqual(result.returncode, 125)
        self.assertEqual(len(self.calls("gradle")), 2)
        self.assertFalse(list(self.state.glob("consumer-receipts.*/consumer-metadata-verification.json")))

    def test_current_source_receipt_cannot_substitute_legacy_focused_or_extra_consumer_tasks(self):
        requests = [EXPECTED_LEGACY_TASKS, EXPECTED_EMBEDDED_TASKS, EXPECTED_TASKS[:-1],
                    [*EXPECTED_TASKS, ":lanJvm:unadmittedTask"]]
        for index, tasks in enumerate(requests):
            with self.subTest(tasks=tasks):
                work = self.work_root / f"substituted tasks {index}"
                arguments = ["--no-daemon", "--console=plain", "-p", str(work / "consumer"),
                             f"-PconsumerRepo={work / 'repository'}", *tasks]
                result = self.run_gate({**self.audit_options(), "P2PKIT_CONSUMER_WORK_DIR": str(work),
                                        "FAKE_CONSUMER_RECEIPT_MUTATION": json.dumps({"requestedArgv": arguments})})
                self.assert_rejected(result, "argument vector differs")
                self.assertEqual(result.returncode, 125)
                self.assertTrue((work / "consumer/gradle/verification-metadata.xml").is_file())
        self.assertFalse(list(self.state.glob("consumer-receipts.*/consumer-metadata-verification.json")))

    def test_unexpected_missing_and_symlink_publications_are_not_trusted(self):
        for flag, text in (("FAKE_EXTRA_ARTIFACT", "unexpected publication artifact"),
                           ("FAKE_EXTRA_TOOLING", "unexpected publication artifact"),
                           ("FAKE_EXTRA_NATIVE_INTEROP", "unexpected publication artifact"),
                           ("FAKE_EXTRA_GROUP", "unexpected publication directory"),
                           ("FAKE_MISSING_ARTIFACT", "missing required artifacts"),
                           ("FAKE_MISSING_NATIVE_METADATA", "missing required artifacts"),
                           ("FAKE_MISSING_NATIVE_INTEROP", "missing required artifacts"),
                           ("FAKE_SYMLINK_ARTIFACT", "not a regular publication file")):
            with self.subTest(flag=flag):
                work = self.work_root / flag
                result = self.run_gate({**self.audit_options(), "P2PKIT_CONSUMER_WORK_DIR": str(work), flag: "1"})
                self.assert_rejected(result, text)
                self.assertFalse((work / "consumer/gradle/verification-metadata.xml").exists())
                self.assertTrue((work / "repository").is_dir())

    def test_wrong_local_pom_coordinate_is_not_trusted(self):
        result = self.run_gate({**self.audit_options(), "FAKE_BAD_COORDINATE": "p2p-core-iosx64"})
        self.assert_rejected(result, "source-local POM coordinate mismatch")
        self.assertFalse((self.work / "consumer/gradle/verification-metadata.xml").exists())

    def test_tampered_external_copy_and_local_artifact_fail_after_build(self):
        for flag, text in (("FAKE_TAMPER_EXTERNAL", "prepared external/local verification metadata was modified"),
                           ("FAKE_TAMPER_LOCAL", "source-local module file content mismatch"),
                           ("FAKE_TAMPER_NATIVE_METADATA", "source-local module file content mismatch"),
                           ("FAKE_TAMPER_NATIVE_INTEROP", "source-local module file content mismatch")):
            with self.subTest(flag=flag):
                work = self.work_root / flag
                result = self.run_gate({**self.audit_options(), "P2PKIT_CONSUMER_WORK_DIR": str(work), flag: "1"})
                self.assert_rejected(result, text)
                self.assertTrue((work / "consumer/gradle/verification-metadata.xml").is_file())
        self.assertFalse(list(self.state.glob("consumer-receipts.*/consumer-metadata-verification.json")))

    def test_tooling_sidecar_mutation_deletion_or_addition_after_preparation_is_rejected(self):
        for change in ("modify", "delete", "add"):
            with self.subTest(change=change):
                work = self.work_root / change
                result = self.run_gate({**self.audit_options(), "P2PKIT_CONSUMER_WORK_DIR": str(work),
                                        "FAKE_TOOLING_CHANGE": change})
                self.assert_rejected(result, "prepared consumer publication binding changed: repositoryFiles")
                self.assertTrue((work / "consumer/gradle/verification-metadata.xml").is_file())
        self.assertFalse(list(self.state.glob("consumer-receipts.*/consumer-metadata-verification.json")))

    def test_dirty_external_source_or_wrong_context_rejected_before_publish(self):
        metadata = self.root / "gradle/verification-metadata.xml"
        metadata.write_bytes(self.reviewed.replace(EXTERNAL_SHA256.encode(), b"0" * 64))
        result = self.run_gate(self.audit_options())
        self.assert_rejected(result, "source is not clean")
        self.assertFalse(self.calls("gradle"))
        metadata.write_bytes(self.reviewed)
        context_path = self.state / "context.json"
        context = json.loads(context_path.read_text())
        context["expectedCommit"] = "0" * 40
        context_path.write_text(json.dumps(context))
        result = self.run_gate(self.audit_options())
        self.assert_rejected(result, "context is not bound")
        self.assertFalse(self.calls("gradle"))

    def test_all_original_scopes_and_test_only_dependency_exclusion_still_block(self):
        for artifact, dependencies in POM_DEPENDENCIES.items():
            for dependency, scope in dependencies:
                with self.subTest(artifact=artifact, dependency=dependency, requiredScope=scope):
                    result = self.run_gate({"FAKE_BAD_SCOPE": artifact + "|" + dependency})
                    self.assert_rejected(result, "scope was")
            with self.subTest(missingPom=artifact):
                self.assert_rejected(self.run_gate({"FAKE_MISSING_POM": artifact}), "missing generated POM")
        self.assert_rejected(self.run_gate({"FAKE_TEST_ONLY_LAN": "1"}), "test-only LAN dependency")

    def test_lan_poms_reject_unpublished_upstream_nondistributable_and_changed_dependency_edges(self):
        slf4j = {"groupId": "org.slf4j", "artifactId": "slf4j-api", "version": "2.0.7", "scope": "runtime"}
        mutations = [
            {"name": "slf4j-api", "values": {"version": "2.0.13"}},
            {"name": "slf4j-api", "values": {"version": "${unreviewed.version}"}},
            {"name": "slf4j-api", "values": {"groupId": "org.unreviewed"}},
            {"name": "slf4j-api", "values": {"systemPath": "/unpublished/private-jmdns.jar"}},
            {"name": "slf4j-api", "values": {"classifier": "private"}},
            {"name": "slf4j-api", "values": {"type": "pom"}},
            {"name": "slf4j-api", "values": {"optional": "true"}},
            {"values": slf4j},
            {"values": {"groupId": "org.jmdns", "artifactId": "jmdns", "version": "3.6.3", "scope": "runtime"}},
            {"values": {"groupId": GROUP, "artifactId": "p2p-embedded-jmdns", "version": VERSION, "scope": "runtime"}},
        ]
        for artifact in ("p2p-transport-lan-jvm", "p2p-transport-lan-android"):
            for mutation in mutations:
                with self.subTest(artifact=artifact, mutation=mutation):
                    before = len(self.calls("gradle"))
                    result = self.run_gate({"FAKE_LAN_POM_MUTATION": json.dumps({"artifact": artifact, **mutation})})
                    self.assert_rejected(result, "embedded LAN publication metadata")
                    self.assertEqual(len(self.calls("gradle")) - before, 1, "invalid POM must block consumer execution")

    def test_lan_modules_reject_private_duplicate_file_and_unpinned_edges_in_both_collections(self):
        slf4j = {"group": "org.slf4j", "module": "slf4j-api", "version": {"requires": "2.0.7"}}
        mutations = [
            {"name": "slf4j-api", "values": {"version": {"requires": "2.0.13"}}},
            {"name": "slf4j-api", "values": {"version": {"requires": "2.+"}}},
            {"name": "slf4j-api", "values": {"version": {"requires": "2.0.7", "prefers": "2.0.13"}}},
            {"name": "slf4j-api", "values": {"files": ["/unpublished/private-jmdns.jar"]}},
            {"values": slf4j},
            {"values": {"group": "org.jmdns", "module": "jmdns", "version": {"requires": "3.6.3"}}},
            {"values": {"group": GROUP, "module": "p2p-embedded-jmdns", "version": {"requires": VERSION}}},
            {"field": "dependencyConstraints", "values": {
                "group": "org.jmdns", "module": "jmdns", "version": {"requires": "3.6.3"}}},
            {"field": "dependencyConstraints", "values": slf4j, "count": 2},
        ]
        for artifact in ("p2p-transport-lan-jvm", "p2p-transport-lan-android"):
            for mutation in mutations:
                with self.subTest(artifact=artifact, mutation=mutation):
                    before = len(self.calls("gradle"))
                    change = {"artifact": artifact, "variant": "runtimeElements", **mutation}
                    result = self.run_gate({"FAKE_LAN_MODULE_MUTATION": json.dumps(change)})
                    self.assert_rejected(result, "embedded LAN publication metadata")
                    self.assertEqual(len(self.calls("gradle")) - before, 1, "invalid GMM must block consumer execution")

    def test_lan_modules_keep_required_api_runtime_edges_and_logging_off_api_classpaths(self):
        mutations = [
            {"variant": "apiElements", "name": "p2p-core", "remove": True},
            {"variant": "runtimeElements", "name": "kotlinx-coroutines-core", "remove": True},
            {"variant": "runtimeElements", "name": "slf4j-api", "remove": True},
            {"variant": "apiElements", "values": {
                "group": "org.slf4j", "module": "slf4j-api", "version": {"requires": "2.0.7"}}},
            {"variant": "apiElements", "removeVariant": True},
            {"variant": "runtimeElements", "attributes": {"org.gradle.usage": "java-api"}},
        ]
        for artifact in ("p2p-transport-lan-jvm", "p2p-transport-lan-android"):
            for mutation in mutations:
                with self.subTest(artifact=artifact, mutation=mutation):
                    result = self.run_gate({"FAKE_LAN_MODULE_MUTATION": json.dumps({"artifact": artifact, **mutation})})
                    self.assert_rejected(result, "embedded LAN publication metadata")
            self.assert_rejected(self.run_gate({"FAKE_MISSING_MODULE": artifact}),
                                 "embedded LAN publication metadata: missing/nonregular metadata "
                                 f"{artifact}-{VERSION}.module")
            self.assert_rejected(self.run_gate({"FAKE_DUPLICATE_MODULE_KEY": artifact}), "duplicate JSON key")

    def test_current_profiles_require_exact_packaging_report_and_all_four_apks(self):
        cases = [
            {"FAKE_MISSING_PACKAGING_REPORT": "1"}, {"FAKE_BAD_PACKAGING_REPORT": "1"},
            {"FAKE_PACKAGING_REPORT": PACKAGING_REPORT_BYTES.decode().removesuffix("\n")},
            {"FAKE_PACKAGING_REPORT": PACKAGING_REPORT_BYTES.decode() + "\n"},
            *({"FAKE_MISSING_APK": variant} for variant in EXPECTED_APKS),
        ]
        for profile in ("complete", "lan-jvm-android"):
            for overrides in cases:
                with self.subTest(profile=profile, overrides=overrides):
                    before = len(self.calls("gradle"))
                    result = self.run_gate({"P2PKIT_CONSUMER_PROFILE": profile, **overrides})
                    self.assert_rejected(result)
                    self.assertEqual(len(self.calls("gradle")) - before, 2,
                                     "the output inspector must reject after the synthetic build")

    def test_focused_profile_preserves_product_failure_codes_and_borrowed_outputs(self):
        for flag, code, leaves in (("FAKE_PUBLISH_EXIT", 23, 1), ("FAKE_BUILD_EXIT", 29, 2)):
            with self.subTest(flag=flag):
                work = self.base / flag
                before = len(self.calls("gradle"))
                result = self.run_gate({"P2PKIT_CONSUMER_PROFILE": "lan-jvm-android",
                                        "P2PKIT_CONSUMER_WORK_DIR": str(work), flag: str(code)})
                self.assert_rejected(result)
                self.assertEqual(result.returncode, code)
                self.assertEqual(len(self.calls("gradle")) - before, leaves)
                self.assertTrue((work / "repository").is_dir())
                self.assertEqual((work / "consumer").exists(), leaves == 2)
        for kind in ("executor", "curl", "xcrun"):
            self.assertFalse(self.calls(kind), kind)

    def test_original_framework_platform_floor_and_permission_checks_still_block(self):
        for overrides, text in (({"FAKE_MISSING_FRAMEWORK": "1"}, "framework was not linked"),
                                ({"FAKE_PLATFORM": "IOS"}, "not an iOS Simulator binary"),
                                ({"FAKE_MINOS": "15.0"}, "deployment floor"),
                                *(({"FAKE_OMIT_PERMISSION": permission}, "merged manifest is missing") for permission in PERMISSIONS)):
            with self.subTest(overrides=overrides):
                self.assert_rejected(self.run_gate(overrides), text)

    def test_missing_marker_is_not_silently_curated(self):
        result = self.run_gate(self.audit_options())
        self.assert_pass(result)
        tree = ET.parse(self.work / "consumer/gradle/verification-metadata.xml")
        coordinates = {(node.get("group"), node.get("name"), node.get("version"))
                       for node in tree.findall(f".//{{{NAMESPACE}}}component")}
        self.assertEqual(len(coordinates), 16)
        self.assertNotIn(("com.android.library", "com.android.library.gradle.plugin", "92.0.0"), coordinates)
        self.assertEqual(len(self.calls("curl")), 0)


def native_fixture_producer(arguments):
    """Supply real caller fixtures; the independent native test owns the verdict."""
    parser = argparse.ArgumentParser(description="Fixture producers for the separate native executor selftest")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--ownership-cancellation-fixture", metavar="READY_JSON")
    mode.add_argument("--executor-integration-fixture", action="store_true")
    parser.add_argument("--fixture-evidence", required=True)
    parser.add_argument("--executor")
    args = parser.parse_args(arguments)
    if os.name != "posix":
        parser.error("These producers exercise the POSIX/mac-policy consumer caller, not Windows consumer acceptance")
    if bool(args.executor) != args.executor_integration_fixture:
        parser.error("Only --executor-integration-fixture requires --executor")

    def require(condition, message):
        if not condition:
            raise ValueError(message)

    state = Path(os.environ.get(processes.STATE_ENV, ""))
    temporary = Path(os.environ.get("TMPDIR", ""))
    for path in (state, state / "work", state / "evidence", temporary):
        require(path.is_absolute() and path.is_dir() and not path.is_symlink() and
                path.resolve(strict=True) == path, "Producer requires physical initialized state/work/evidence/TMPDIR")
    require(state / "work" in temporary.parents, "Producer TMPDIR must be owned below the enclosing state/work")
    evidence = Path(args.fixture_evidence)
    require(evidence.is_absolute() and not evidence.exists() and not evidence.is_symlink() and
            evidence.resolve() == evidence and evidence.parent.is_dir() and state / "evidence" in evidence.parents,
            "Producer evidence must be a new physical directory beneath the enclosing state/evidence")
    ready = Path(args.ownership_cancellation_fixture) if args.ownership_cancellation_fixture else None
    if ready is not None:
        require(ready.is_absolute() and ready.parent == evidence and not ready.exists() and not ready.is_symlink(),
                "Readiness must be a new direct child of the producer evidence directory")
    executor = Path(args.executor) if args.executor else None
    if executor is not None:
        require(executor.is_absolute() and executor.is_file() and not executor.is_symlink() and
                executor.resolve(strict=True) == executor and os.access(executor, os.X_OK),
                "Integration requires the explicit real executable audit executor")

    evidence.mkdir(mode=0o700)
    selected_mode = "ownership-cancellation" if ready is not None else "real-executor-integration"
    write_fixture_record(evidence / "producer-start.json", {
        "schema": 1, "mode": selected_mode, "pid": os.getpid(), "temporaryRoot": str(temporary),
        "parentOwnership": ownership_observation(os.environ),
        "producerSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "consumerScriptSha256": hashlib.sha256((ROOT / "scripts/check-published-consumers.sh").read_bytes()).hexdigest(),
        "scope": "Synthetic consumer bytes; native enclosing selftest independently validates execution and cleanup.",
    })
    fixture = ConsumerGateTest(methodName="test_supported_borrowed_adapter_preserves_argv_cwd_home_and_retains_work_and_receipts")
    fixture.fixture_evidence = evidence
    fixture.setUp()
    require(temporary in fixture.base.parents, "Actual consumer fixture escaped the enclosing owned TMPDIR")
    binding = {
        "schema": 1, "mode": selected_mode, "fixtureBase": str(fixture.base), "fixtureRoot": str(fixture.root),
        "fixtureState": str(fixture.state), "consumerWorkDir": str(fixture.work), "callsFile": str(fixture.calls_file),
        "fixtureSetupOwnership": ownership_observation(fixture.env),
        "retention": "Enclosing native fixture retains evidence and drains actual workers before deleting its TMPDIR.",
    }

    if ready is not None:
        options = fixture.adapter_options(fixture.work)
        write_fixture_record(evidence / "producer.json", {
            **binding, "readyFile": str(ready), "adapterOwnership": ownership_observation(options),
            "executor": options["P2PKIT_GRADLE_EXECUTOR"],
        })
        print("Synthetic consumer cancellation producer; awaiting the enclosing native controller", flush=True)
        result = fixture.run_gate({**options, "FAKE_CONSUMER_OWNERSHIP_READY": str(ready)}, capture_directory=evidence)
        write_fixture_record(evidence / "producer-completion.json", {
            **binding, "exitCode": result.returncode, "unexpectedCompletion": True,
        })
        # No producer-created success can stand in for the native cancellation
        # receipt, retired worker identity, or separately-owned live sentinel.
        return 125

    child_state = fixture.base / "native audit state"
    source = source_snapshot(fixture.root, fixture.env)
    command = [sys.executable, str(executor), "init", "--root", str(fixture.root), "--state", str(child_state),
               "--expected-commit", source["commit"], "--host", processes.host_role()]
    with (evidence / "init.stdout.log").open("xb") as stdout, (evidence / "init.stderr.log").open("xb") as stderr:
        initialized = subprocess.run(command, env=fixture.env, stdout=stdout, stderr=stderr, timeout=30)
        for stream in (stdout, stderr):
            stream.flush()
            os.fsync(stream.fileno())
    write_fixture_record(evidence / "init.json", {"schema": 1, "argv": command, "exitCode": initialized.returncode,
                                                 "childState": str(child_state)})
    require(initialized.returncode == 0, "Actual native executor did not initialize the positive fixture")
    context = json.loads((child_state / "context.json").read_text(encoding="utf-8"))
    require(context.get("root") == str(fixture.root) and context.get("source") == source,
            "Actual native fixture context is not bound to the consumer source")
    work_root = child_state / "work"
    work_root.mkdir(mode=0o700)
    work = work_root / "borrowed consumer λ directory"
    environment = processes.ownership_environment(fixture.env, context["id"], uuid.uuid4().hex,
                                                   str(child_state), context["gradleHome"], allow_new_context=True)
    options = {**environment, "P2PKIT_GRADLE_EXECUTOR": str(executor), "P2PKIT_CONSUMER_WORK_DIR": str(work),
               "P2PKIT_CONSUMER_AUDIT_METADATA": "0"}
    report = work / "consumer/kmpConsumer/build/reports/consumer-fixture.json"
    binding.update({"childState": str(child_state), "consumerWorkDir": str(work), "fixtureReport": str(report),
                    "executor": str(executor), "executorSha256": hashlib.sha256(executor.read_bytes()).hexdigest(),
                    "adapterOwnership": ownership_observation(options)})
    write_fixture_record(evidence / "producer.json", binding)
    result = fixture.run_gate(options, capture_directory=evidence)
    write_fixture_record(evidence / "producer-completion.json", {**binding, "exitCode": result.returncode,
        "fixtureReportSha256": hashlib.sha256(report.read_bytes()).hexdigest() if report.is_file() else None,
        "scope": "Real executor with synthetic wrappers/report; not Gradle resolution, compilation or Apple acceptance."})
    # The native parent inspects and archives actual child context/receipts/raw
    # stop/report evidence before its own guarded TMPDIR teardown. No receipt is
    # fabricated and this producer does not issue an ownership approval.
    return result.returncode


if __name__ == "__main__":
    if any(option in sys.argv[1:] for option in ("--ownership-cancellation-fixture", "--executor-integration-fixture")):
        raise SystemExit(native_fixture_producer(sys.argv[1:]))
    unittest.main(verbosity=2)
