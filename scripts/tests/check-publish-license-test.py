#!/usr/bin/env python3
"""Exercise actual license/private-component archive checks; no Gradle/publication."""

import copy
import hashlib
import io
import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import warnings
import xml.etree.ElementTree as ET
import zipfile


ROOT = Path(__file__).resolve().parents[2]
script = (ROOT / "scripts/check-publish-artifacts.sh").read_text()
start = "    # Embedded-license policy:"
end = "    # End embedded-license policy."
assert script.count(start) == script.count(end) == 1
policy = script[script.index(start):script.index(end) + len(end)]
license_bytes = (ROOT / "LICENSE").read_bytes()

# This executes the block inside check(), including the archive-class dispatch,
# not the surrounding POM/KLIB/publication checks. The real publication gate
# must still inspect candidate artifacts; these fixtures are not build evidence.
cases = [
    ("main-jar", ".jar", None, "valid"),
    ("main-aar", ".aar", None, "valid"),
    ("klib-main-exempt", ".klib", None, "valid"),
    ("klib-interop-exempt", ".klib", None, "valid"),
    ("missing-source-license", ".jar", "sources", "missing"),
    ("changed-dokka-license", ".jar", "javadoc", "changed"),
    ("duplicate-main-license", ".aar", "main", "duplicate"),
    ("klib-source-not-exempt", ".klib", "sources", "missing"),
    ("klib-metadata-not-exempt", ".klib", "metadata", "missing"),
    ("unreadable-dokka", ".jar", "javadoc", "unreadable"),
    ("unknown-main-policy", ".zip", None, "valid"),
]
for name, suffix, damaged, mode in cases:
    with tempfile.TemporaryDirectory(prefix="p2pkit-license-test-") as temporary:
        work = Path(temporary)
        (work / "LICENSE").write_bytes(license_bytes)
        paths = {"main": work / ("fixture" + suffix),
                 "sources": work / "fixture-sources.jar",
                 "javadoc": work / "fixture-javadoc.jar"}
        if suffix == ".klib":
            paths["metadata"] = work / "fixture-metadata.jar"
        has_interop = name == "klib-interop-exempt"
        if has_interop:
            paths["cinterop"] = work / "fixture-cinterop-p2pkit_nw.klib"
        for role, path in paths.items():
            kind = mode if damaged == role else "valid"
            if kind == "unreadable":
                path.write_bytes(b"not a zip")
                continue
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("fixture.txt", "synthetic")
                if kind != "missing" and not (role in ("main", "cinterop") and suffix == ".klib"):
                    archive.writestr("META-INF/LICENSE", b"changed" if kind == "changed" else license_bytes)
                if kind == "duplicate":
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", UserWarning)
                        archive.writestr("META-INF/LICENSE", license_bytes)
        shell = """set -euo pipefail
ROOT="$1"
INSPECTION_DIR="$1"
run_policy() {
    local artifact=fixture main_suffix="$2" invalid=""
    local main="$1/fixture$2" sources="$1/fixture-sources.jar" javadoc="$1/fixture-javadoc.jar"
    local native_metadata="" cinterop=""
    if [[ "$2" == ".klib" ]]; then native_metadata="$1/fixture-metadata.jar"; fi
    if [[ "$3" == "interop" ]]; then cinterop="$1/fixture-cinterop-p2pkit_nw.klib"; fi
""" + policy + """
    [[ -z "$invalid" ]] || { echo "FAIL $invalid"; return 1; }
}
run_policy "$1" "$2" "$3"
"""
        result = subprocess.run(["bash", "-c", shell, "license-test", str(work), suffix,
                                 "interop" if has_interop else "none"],
                                capture_output=True, text=True, timeout=15)
        expected_pass = damaged is None and suffix != ".zip"
        assert (result.returncode == 0) == expected_pass, (name, result.returncode, result.stdout, result.stderr)
        assert ("EXEMPT " in result.stdout) == (suffix == ".klib"), (name, result.stdout)
        if has_interop:
            assert result.stdout.count("EXEMPT ") == 2, result.stdout
        if expected_pass:
            assert result.stdout.count("one canonical META-INF/LICENSE") == 3, result.stdout
        else:
            assert "FAIL " in result.stdout, (name, result.stdout, result.stderr)
        print(f"OK {name}")
print(f"RESULT: PASS — {len(cases)} embedded-license ZIP fixtures (no build/publication)")


# Use the same marked function the complete and explicitly narrow gate call.
# The real provenance validator and final checked-in vendor inputs are copied,
# not replaced by a permissive fixture parser. Tiny class shapes below are data,
# never compiled/loaded, and supply no runtime/lifecycle or Android acceptance.
start = "# Embedded-JmDNS policy:"
end = "# End embedded-JmDNS policy."
assert script.count(start) == script.count(end) == 1
embedded_policy = script[script.index(start):script.index(end) + len(end)]
assert script.index('if [[ "$EMBEDDED_ONLY" == 1 ]]; then') < script.index("# All hosts:")
assert script.count("\ncheck_embedded_jmdns\n") == 1  # Complete default still checks the new boundary.
prefix = "dev/p2pkit/transport/lan/internal/jmdns/"
notices = "META-INF/p2pkit/third-party/jmdns/"
module_entry = "META-INF/p2p-transport-lan.kotlin_module"
group, version = "fixture.public.group", "1.0-fixture"
kotlin_version, coroutines_version = "2.4.10", "1.11.0"


def class_bytes(name, major=52, extra=()):
    values = [name[:-6].encode(), b"java/lang/Object", *extra]
    # UTF8/class, UTF8/class, then optional UTF8 constants. No methods are run.
    pool = b"\x01" + struct.pack(">H", len(values[0])) + values[0] + b"\x07\x00\x01"
    pool += b"\x01" + struct.pack(">H", len(values[1])) + values[1] + b"\x07\x00\x03"
    for value in values[2:]:
        pool += b"\x01" + struct.pack(">H", len(value)) + value
    return (struct.pack(">IHHH", 0xCAFEBABE, 0, major, 5 + len(extra)) + pool +
            struct.pack(">HHHHHHH", 0x0021, 2, 4, 0, 0, 0, 0))


def zip_bytes(entries, duplicate=None):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
        if duplicate:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                archive.writestr(duplicate, entries[duplicate])
    return stream.getvalue()


def embedded_fixture(work):
    root = work / "checkout"
    vendor = root / "library/p2p-transport-lan/vendor/jmdns"
    shutil.copytree(ROOT / "library/p2p-transport-lan/vendor/jmdns", vendor)
    (root / "scripts").mkdir()
    shutil.copy2(ROOT / "scripts/validate-sbom.py", root / "scripts/validate-sbom.py")
    (root / "LICENSE").write_bytes(license_bytes)
    manifest = json.loads((vendor / "PROVENANCE.json").read_bytes())
    resources = {row["entry"]: (vendor / row["path"]).read_bytes() for row in manifest["resources"]}
    resources[manifest["manifestEntry"]] = (vendor / "PROVENANCE.json").read_bytes()
    for patch in [manifest["lifecyclePatch"], *manifest["followupPatches"]]:
        resources[notices + patch["path"]] = (vendor / patch["path"]).read_bytes()
    sources = {row["path"].removeprefix("src/main/java/"): (vendor / row["path"]).read_bytes()
               for row in manifest["sources"]}
    classes = {}
    for name in sources:
        if name.endswith("/package-info.java"):
            continue
        name = name[:-5] + ".class"
        extra = ()
        if name == prefix + "JmDNS.class":
            extra = ((prefix + "version.properties").encode(),)
        elif name == prefix + "impl/JmDNSImpl.class":
            extra = (("/" + prefix + "version.properties").encode(),)
        classes[name] = class_bytes(name, extra=extra)
    nested = prefix + "JmDNS$Delegate.class"
    classes[nested] = class_bytes(nested)
    wrapper = "dev/p2pkit/transport/lan/Fixture.class"
    kotlin = {wrapper: class_bytes(wrapper, major=61), module_entry: b"synthetic module identity\n"}
    model = {"root": root, "vendor": vendor, "base": work / "repository/fixture/public/group",
             "producer": {"META-INF/MANIFEST.MF": b"Manifest-Version: 1.0\r\n\r\n", **resources, **classes},
             "jvm": {"META-INF/MANIFEST.MF": b"Manifest-Version: 1.0\r\n\r\n", **resources, **classes, **kotlin},
             "android_classes": kotlin.copy(),
             "android_outer": {"META-INF/LICENSE": license_bytes, "AndroidManifest.xml": b"<manifest/>"},
             "jvm_sources": {**resources, **sources, "fixture.kt": b"// synthetic Kotlin source\n"},
             "android_sources": {**resources, **sources, "fixture.kt": b"// synthetic Kotlin source\n"}}
    return model


def publication_metadata(model, suffix, main_bytes, source_bytes, damage):
    artifact = "p2p-transport-lan-" + suffix
    main_name = artifact + "-" + version + (".jar" if suffix == "jvm" else ".aar")
    source_name = artifact + "-" + version + "-sources.jar"
    deps = [(group, "p2p-core-" + suffix, version, "compile"),
            ("org.jetbrains.kotlinx", "kotlinx-coroutines-core-jvm", coroutines_version, "compile"),
            ("org.jetbrains.kotlin", "kotlin-stdlib", kotlin_version, "compile"),
            ("org.slf4j", "slf4j-api", "2.0.7", "runtime")]
    if damage == "pom-original-jmdns" and suffix == "jvm":
        deps.append(("org.jmdns", "jmdns", "3.6.3", "runtime"))
    if damage == "pom-private-dependency" and suffix == "android":
        deps.append(("dev.p2pkit.internal", "jmdns", "3.6.3-p2pkit.410.3", "runtime"))
    if damage == "pom-slf4j-api-edge" and suffix == "jvm":
        deps[-1] = (*deps[-1][:3], "compile")
    if damage == "pom-slf4j-version" and suffix == "jvm":
        deps[-1] = (*deps[-1][:2], "2.0.13", "runtime")
    pom = ET.Element("project", xmlns="http://maven.apache.org/POM/4.0.0")
    for key, value in (("modelVersion", "4.0.0"), ("groupId", group), ("artifactId", artifact), ("version", version)):
        ET.SubElement(pom, key).text = value
    ET.SubElement(pom, "packaging").text = "jar" if suffix == "jvm" else "aar"
    dependencies = ET.SubElement(pom, "dependencies")
    for dep in deps:
        node = ET.SubElement(dependencies, "dependency")
        for key, value in zip(("groupId", "artifactId", "version", "scope"), dep):
            ET.SubElement(node, key).text = value
    if suffix == "jvm":
        if damage == "pom-optional-slf4j":
            ET.SubElement(dependencies[-1], "optional").text = "true"
        elif damage == "pom-excluded-core":
            ET.SubElement(dependencies[0], "exclusions")
        elif damage == "pom-dependency-management":
            pom.remove(dependencies)
            ET.SubElement(pom, "dependencyManagement").append(dependencies)
    common = [{"group": group, "module": "p2p-core", "version": {"requires": version}},
              {"group": "org.jetbrains.kotlinx", "module": "kotlinx-coroutines-core",
               "version": {"requires": coroutines_version}},
              {"group": "org.jetbrains.kotlin", "module": "kotlin-stdlib", "version": {"requires": kotlin_version}}]

    def file_record(name, data):
        return {"name": name, "url": name, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}

    variants = []
    for usage in ("java-api", "java-runtime"):
        variant = {"name": usage, "attributes": {"org.gradle.category": "library", "org.gradle.usage": usage},
                   "dependencies": copy.deepcopy(common), "files": [file_record(main_name, main_bytes)]}
        if usage == "java-runtime":
            variant["dependencies"].append({"group": "org.slf4j", "module": "slf4j-api", "version": {"requires": "2.0.7"}})
        variants.append(variant)
    variants.append({"name": "sources", "attributes": {"org.gradle.category": "documentation",
                                                       "org.gradle.docstype": "sources"},
                     "files": [file_record(source_name, source_bytes)]})
    component = {"group": group, "module": "p2p-transport-lan", "version": version,
                 "url": "../../p2p-transport-lan/" + version + "/p2p-transport-lan-" + version + ".module"}
    module = {"formatVersion": "1.1", "component": component,
              "variants": variants}
    if damage == "valid-with-constraints":
        variants[1]["dependencyConstraints"] = copy.deepcopy(variants[1]["dependencies"])
    if suffix == "android":
        if damage == "valid-android-logical-alias":
            for variant in variants[:2]:
                variant["files"][0]["name"] = "p2p-transport-lan.aar"
        elif damage == "module-private-dependency":
            variants[1]["dependencies"].append({"group": "dev.p2pkit.internal", "module": "jmdns",
                                                "version": {"requires": "3.6.3-p2pkit.410.3"}})
        elif damage == "module-original-jmdns":
            variants[1]["dependencies"].append({"group": "org.jmdns", "module": "jmdns", "version": {"requires": "3.6.3"}})
        elif damage == "module-file-path":
            variants[1]["files"][0]["url"] = "/root/private.jar"
        elif damage == "module-missing-runtime-slf4j":
            variants[1]["dependencies"].pop()
        elif damage == "module-stale-hash":
            variants[0]["files"][0]["sha256"] = "0" * 64
        elif damage == "module-public-id":
            module["component"]["module"] = "p2p-transport-lan-private"
        elif damage == "module-component-redirect":
            module["component"]["url"] = "../../unpublished/component.module"
        elif damage == "module-constraint-not-core-edge":
            variants[0]["dependencyConstraints"] = [variants[0]["dependencies"].pop(0)]
        elif damage == "module-constraint-not-coroutines-edge":
            variants[0]["dependencyConstraints"] = [variants[0]["dependencies"].pop(1)]
        elif damage == "module-constraint-not-slf4j-edge":
            variants[1]["dependencyConstraints"] = [variants[1]["dependencies"].pop()]
        elif damage == "module-version-override":
            variants[1]["dependencies"][-1]["version"]["strictly"] = "2.0.13"
        elif damage == "module-coroutines-version":
            variants[0]["dependencies"][1]["version"]["requires"] = "1.10.2"
        elif damage == "module-dependency-exclusion":
            variants[0]["dependencies"][0]["excludes"] = [{"group": "org.slf4j", "module": "slf4j-api"}]
        elif damage == "module-missing-source-variant":
            variants.pop()
        elif damage == "module-source-redirect":
            variants[-1]["files"][0]["url"] = "../../private-sources.jar"
        elif damage == "module-invalid-dependency-list":
            variants[0]["dependencies"] = {}
    return ET.tostring(pom), json.dumps(module).encode()


def write_fixture(model, damage):
    name = prefix + "JmDNS.class"
    wrapper = "dev/p2pkit/transport/lan/Fixture.class"
    if damage == "jvm-missing-private-class":
        model["jvm"].pop(name)
    elif damage == "jvm-missing-nested-class":
        model["jvm"].pop(prefix + "JmDNS$Delegate.class")
    elif damage == "jvm-changed-private-class":
        model["jvm"][name] = class_bytes(name, extra=(b"different",))
    elif damage == "jvm-original-class":
        old = "javax/jmdns/JmDNS.class"
        model["jvm"][old] = class_bytes(old)
    elif damage == "jvm-original-reference":
        model["jvm"][wrapper] = class_bytes(wrapper, 61, (b"javax/jmdns/JmDNS",))
    elif damage == "jvm-logger-provider":
        provider = "ch/qos/logback/classic/Logger.class"
        model["jvm"][provider] = class_bytes(provider)
    elif damage == "jvm-unsafe-entry":
        model["jvm"]["../escaped.txt"] = b"must not be read as an archive member"
    elif damage == "jvm-null-entry":
        model["jvm"]["unsafe-name-X"] = b"must not be read under a truncated ZIP name"
    elif damage == "producer-java17":
        model["producer"][name] = class_bytes(name, 61)
    elif damage == "producer-missing-top-level":
        model["producer"].pop(prefix + "JmmDNS.class")
    elif damage == "producer-undeclared-class":
        extra = prefix + "Undeclared.class"
        model["producer"][extra] = class_bytes(extra)
    elif damage == "producer-logger-provider":
        extra = "org/slf4j/Logger.class"
        model["producer"][extra] = class_bytes(extra)
    elif damage == "producer-wrong-lookup":
        model["producer"][name] = class_bytes(name, extra=(b"version.properties",))
    elif damage == "producer-changed-notice":
        model["producer"][notices + "NOTICE.txt"] = b"invented attribution\n"
    elif damage == "producer-changed-followup-patch":
        model["producer"][notices + "patches/415-opt-rcode.patch"] += b"undeclared change\n"
    elif damage == "jvm-root-version":
        model["jvm"]["version.properties"] = b"jmdns.version=3.6.3\n"
    elif damage == "jvm-upstream-maven":
        model["jvm"]["META-INF/maven/org.jmdns/jmdns/pom.properties"] = b"version=3.6.3\n"
    elif damage == "jvm-upstream-manifest":
        model["jvm"]["META-INF/MANIFEST.MF"] = b"Manifest-Version: 1.0\nAutomatic-Module-Name: javax.jmdns\n\n"
    elif damage == "jvm-lowercase-main-manifest":
        model["jvm"]["META-INF/MANIFEST.MF"] = b"Manifest-Version: 1.0\nmain-class: example.Main\n\n"
    elif damage == "jvm-missing-version":
        model["jvm"].pop(prefix + "version.properties")
    elif damage == "jvm-missing-notice":
        model["jvm"].pop(notices + "NOTICE.txt")
    elif damage == "jvm-module-identity":
        model["jvm"]["META-INF/wrong.kotlin_module"] = model["jvm"].pop(module_entry)
    elif damage == "aar-duplicate-private":
        model["android_classes"][name] = model["producer"][name]
    elif damage == "aar-original-class":
        old = "javax/jmdns/JmDNS.class"
        model["android_classes"][old] = class_bytes(old)
    elif damage == "aar-nested-classes-jar":
        model["android_classes"]["libs/hidden.jar"] = zip_bytes({"fixture.txt": b"hidden dependency"})
    elif damage == "aar-bad-outer-license":
        model["android_outer"]["META-INF/LICENSE"] = b"not the canonical license"
    elif damage == "source-unpatched-java":
        model["jvm_sources"][prefix + "impl/JmDNSImpl.java"] += b"// not the manifest-bound source\n"
    elif damage == "source-unrelocated-java":
        model["android_sources"]["javax/jmdns/JmDNS.java"] = model["android_sources"].pop(prefix + "JmDNS.java")
    elif damage == "source-missing-patch":
        model["android_sources"].pop(notices + "patches/410-lifecycle.patch")
    elif damage == "source-missing-followup-patch":
        model["android_sources"].pop(notices + "patches/415-opt-rcode.patch")
    elif damage == "source-stale-provenance":
        model["android_sources"][notices + "PROVENANCE.json"] = b"{}\n"
    elif damage == "source-binary-class":
        model["jvm_sources"][name] = model["producer"][name]
    elif damage == "source-missing-license":
        model["android_sources"].pop("META-INF/LICENSE")
    elif damage == "vendor-source-drift":
        path = model["vendor"] / "src/main/java" / (prefix + "JmDNS.java")
        path.write_bytes(path.read_bytes() + b"// unexpected drift\n")

    producer = zip_bytes(model["producer"], name if damage == "producer-duplicate-entry" else None)
    path = model["root"] / "library/p2p-transport-lan/build/embedded-jmdns/p2pkit-internal-jmdns.jar"
    path.parent.mkdir(parents=True)
    if damage != "missing-producer":
        path.write_bytes(producer)
    if damage == "jvm-nested-jar":
        model["jvm"]["libs/p2pkit-internal-jmdns.jar"] = producer
    android = {**model["android_outer"], "classes.jar": zip_bytes(model["android_classes"]),
               "libs/p2pkit-internal-jmdns.jar": producer}
    if damage == "aar-missing-private":
        android.pop("libs/p2pkit-internal-jmdns.jar")
    elif damage == "aar-changed-private-jar":
        android["libs/p2pkit-internal-jmdns.jar"] = producer + b"different ZIP bytes"
    elif damage == "aar-extra-jar":
        android["libs/unpublished.jar"] = zip_bytes({"fixture.txt": b"unexpected local dependency"})
    for suffix, entries in (("jvm", model["jvm"]), ("android", android)):
        artifact = "p2p-transport-lan-" + suffix
        directory = model["base"] / artifact / version
        directory.mkdir(parents=True)
        main = zip_bytes(entries, "META-INF/LICENSE" if damage == "jvm-duplicate-license" and suffix == "jvm" else None)
        if damage == "jvm-null-entry" and suffix == "jvm":
            # ZipInfo normalizes NUL on construction; patch equal-length names in
            # the local/central headers so the fixture preserves the unsafe input.
            main = main.replace(b"unsafe-name-X", b"unsafe-name-\0")
        sources = zip_bytes(model[suffix + "_sources"])
        (directory / (artifact + "-" + version + (".jar" if suffix == "jvm" else ".aar"))).write_bytes(main)
        (directory / (artifact + "-" + version + "-sources.jar")).write_bytes(sources)
        pom, module = publication_metadata(model, suffix, main, sources, damage)
        (directory / (artifact + "-" + version + ".pom")).write_bytes(pom)
        (directory / (artifact + "-" + version + ".module")).write_bytes(module)


embedded_cases = [
    ("valid", None),
    ("valid-with-constraints", None),
    ("valid-android-logical-alias", None),
    ("jvm-nested-jar", "must be flat"),
    ("jvm-missing-private-class", "classes differ"),
    ("jvm-missing-nested-class", "classes differ"),
    ("jvm-changed-private-class", "classes differ"),
    ("jvm-original-class", "upstream/provider entry"),
    ("jvm-original-reference", "unrelocated JmDNS class reference"),
    ("jvm-logger-provider", "bundled non-LAN class"),
    ("jvm-unsafe-entry", "duplicate/unsafe ZIP entry"),
    ("jvm-null-entry", "duplicate/unsafe ZIP entry"),
    ("jvm-duplicate-license", "duplicate/unsafe ZIP entry"),
    ("producer-java17", "not Java 8 bytecode"),
    ("producer-missing-top-level", "missing a declared top-level class"),
    ("producer-undeclared-class", "no declared Java source"),
    ("producer-logger-provider", "upstream/provider entry"),
    ("producer-wrong-lookup", "private resource lookup missing"),
    ("producer-changed-notice", "changed/missing resource"),
    ("producer-changed-followup-patch", "changed/missing resource"),
    ("producer-duplicate-entry", "duplicate/unsafe ZIP entry"),
    ("jvm-root-version", "upstream/provider entry"),
    ("jvm-upstream-maven", "upstream/provider entry"),
    ("jvm-upstream-manifest", "upstream executable/module manifest"),
    ("jvm-lowercase-main-manifest", "upstream executable/module manifest"),
    ("jvm-missing-version", "private resource inventory differs"),
    ("jvm-missing-notice", "private resource inventory differs"),
    ("jvm-module-identity", "public Kotlin module identity changed"),
    ("aar-duplicate-private", "duplicates the private component"),
    ("aar-original-class", "upstream/provider entry"),
    ("aar-nested-classes-jar", "classes.jar contains a nested JAR"),
    ("aar-bad-outer-license", "noncanonical outer license"),
    ("aar-missing-private", "exactly the one declared private JAR"),
    ("aar-changed-private-jar", "embedded JAR differs"),
    ("aar-extra-jar", "exactly the one declared private JAR"),
    ("source-unpatched-java", "corrected Java sources differ"),
    ("source-unrelocated-java", "upstream/provider entry"),
    ("source-missing-patch", "private resource inventory differs"),
    ("source-missing-followup-patch", "private resource inventory differs"),
    ("source-stale-provenance", "changed/missing resource"),
    ("source-binary-class", "corrected Java sources differ"),
    ("source-missing-license", "changed/missing resource"),
    ("vendor-source-drift", "modified source hash differs"),
    ("missing-producer", "missing/nonregular artifact or input"),
    ("pom-original-jmdns", "unexpected/unpublished dependency"),
    ("pom-private-dependency", "unexpected/unpublished dependency"),
    ("pom-slf4j-api-edge", "POM API/runtime edges changed"),
    ("pom-slf4j-version", "wrong published dependency version"),
    ("pom-optional-slf4j", "optional POM dependency"),
    ("pom-excluded-core", "unsupported POM dependency fields"),
    ("pom-dependency-management", "inherited dependency"),
    ("module-private-dependency", "unexpected/unpublished dependency"),
    ("module-original-jmdns", "unexpected/unpublished dependency"),
    ("module-file-path", "nonportable publication metadata"),
    ("module-missing-runtime-slf4j", "SLF4J Gradle runtime edge changed"),
    ("module-stale-hash", "stale Gradle artifact hash/size"),
    ("module-public-id", "public Gradle module identity changed"),
    ("module-component-redirect", "nonpublic Gradle component URL"),
    ("module-constraint-not-core-edge", "LAN Gradle API edges changed"),
    ("module-constraint-not-coroutines-edge", "LAN Gradle API edges changed"),
    ("module-constraint-not-slf4j-edge", "SLF4J Gradle runtime edge changed"),
    ("module-version-override", "invalid Gradle dependency"),
    ("module-coroutines-version", "wrong published dependency version"),
    ("module-dependency-exclusion", "invalid Gradle dependency"),
    ("module-missing-source-variant", "missing/duplicate LAN Gradle sources variant"),
    ("module-source-redirect", "private/unpublished Gradle variant artifact"),
    ("module-invalid-dependency-list", "invalid Gradle dependency list"),
]
for name, diagnostic in embedded_cases:
    with tempfile.TemporaryDirectory(prefix="p2pkit-embedded-artifact-test-") as temporary:
        model = embedded_fixture(Path(temporary))
        write_fixture(model, name)
        shell = ('set -euo pipefail\nROOT="$1"\nBASE="$2"\nGROUP="$3"\nVERSION="$4"\n'
                 'KOTLIN_VERSION="$5"\nCOROUTINES_VERSION="$6"\nfail=0\n')
        shell += embedded_policy + '\ncheck_embedded_jmdns\n[[ "$fail" == 0 ]]\n'
        result = subprocess.run(["bash", "-c", shell, "embedded-test", str(model["root"]), str(model["base"]),
                                 group, version, kotlin_version, coroutines_version],
                                capture_output=True, text=True, timeout=15)
        assert result.returncode == (0 if diagnostic is None else 1), (name, result.returncode, result.stdout, result.stderr)
        if diagnostic is None:
            assert result.stdout.count("exact embedded producer, corrected sources") == 2, result.stdout
            assert "not native lifecycle proof" in result.stdout, result.stdout
        else:
            assert diagnostic in result.stderr, (name, diagnostic, result.stdout, result.stderr)
        print(f"OK {name}")
print(f"RESULT: PASS — {len(embedded_cases)} embedded-JmDNS ZIP/metadata fixtures (no build/publication)")
