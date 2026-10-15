#!/usr/bin/env python3
"""Actual Java archive transform and existing publication fixtures; no Gradle."""
import ast
import hashlib
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import warnings
import zipfile

ROOT = Path(__file__).resolve().parents[2]
PREFIX = "dev/p2pkit/transport/lan/internal/jmdns/"
NOTICES = "META-INF/p2pkit/third-party/jmdns/"
EMBEDDED = "libs/p2pkit-internal-jmdns.jar"


def pack(entries, duplicate=None):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
        if duplicate:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                archive.writestr(duplicate, entries[duplicate])
    return out.getvalue()


def unpack(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


class AarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.compilation = tempfile.TemporaryDirectory(prefix="jmdns-aar-java-")
        cls.classes = Path(cls.compilation.name)
        driver = cls.classes / "AarTestDriver.java"
        driver.write_text('''import java.nio.file.Path;
import dev.p2pkit.build.EmbeddedJmdnsAar;
public class AarTestDriver {
  public static void main(String[] args) throws Exception {
    EmbeddedJmdnsAar.restore(Path.of(args[0]), Path.of(args[1]), Path.of(args[2]));
  }
}
''')
        binary = lambda name: str(Path(os.environ["JAVA_HOME"]) / "bin" / name) if os.environ.get("JAVA_HOME") else name
        cls.java = binary("java")
        result = subprocess.run([binary("javac"), "-J-Xmx256m", "--release", "17", "-proc:none",
            "-encoding", "UTF-8", "-Xlint:all", "-Werror", "-d", str(cls.classes),
            str(ROOT / "buildSrc/src/main/java/dev/p2pkit/build/EmbeddedJmdnsAar.java"), str(driver)],
            capture_output=True, timeout=30)
        if result.returncode:
            cls.compilation.cleanup()
            raise AssertionError(result.stderr.decode())

    @classmethod
    def tearDownClass(cls):
        cls.compilation.cleanup()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="jmdns-aar-case-")
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)
        self.producer = {PREFIX + "Fixture.class": b"fixture class bytes", PREFIX + "version.properties": b"version=1\n",
            NOTICES + "NOTICE.txt": b"notice", "META-INF/LICENSE": b"canonical license",
            "META-INF/MANIFEST.MF": b"Manifest-Version: 1.0\r\n\r\n"}
        self.local = {name: data for name, data in self.producer.items() if name.endswith(".class")}
        self.module = {"example/Library.class": b"other class", "META-INF/p2p-transport-lan.kotlin_module": b"module",
            "unrelated.properties": b"keep", **{name: data for name, data in self.producer.items()
                if name.startswith(NOTICES) or name.endswith("version.properties")}}
        self.outer = {"AndroidManifest.xml": b"manifest", "META-INF/LICENSE": b"canonical license", "R.txt": b"resources"}

    def invoke(self, aar, producer, output):
        return subprocess.run([self.java, "-Xmx256m", "-XX:ActiveProcessorCount=2", "-cp", str(self.classes),
            "AarTestDriver", str(aar), str(producer), str(output)], capture_output=True, timeout=15)

    def run_fixture(self, *, rejected=False, duplicate=None):
        producer = self.work / "producer.jar"
        producer.write_bytes(pack(self.producer))
        aar = self.work / "input.aar"
        aar.write_bytes(pack({**self.outer, EMBEDDED: pack(self.local), "classes.jar": pack(self.module)}, duplicate))
        before = [hashlib.sha256(path.read_bytes()).digest() for path in (aar, producer)]
        output = self.work / "output.aar"
        output.unlink(missing_ok=True)
        result = self.invoke(aar, producer, output)
        self.assertEqual(before, [hashlib.sha256(path.read_bytes()).digest() for path in (aar, producer)])
        if rejected:
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b"Embedded JmDNS AAR:", result.stderr)
            self.assertFalse(output.exists())
            self.assertFalse(list(self.work.glob("*.aar.tmp")))
            return None
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b"")
        return output.read_bytes()

    def test_exact_producer_and_unrelated_payloads_preserved_deterministically(self):
        result = self.run_fixture()
        actual = unpack(result)
        self.assertEqual(actual[EMBEDDED], pack(self.producer))
        self.assertEqual({name: actual[name] for name in self.outer}, self.outer)
        self.assertEqual(unpack(actual["classes.jar"]), {name: data for name, data in self.module.items()
            if not name.startswith((PREFIX, NOTICES))})
        self.module = dict(reversed(list(self.module.items())))
        self.outer = dict(reversed(list(self.outer.items())))
        self.assertEqual(result, self.run_fixture())
        with zipfile.ZipFile(io.BytesIO(result)) as archive:
            self.assertEqual(archive.namelist(), sorted(archive.namelist()))
            self.assertTrue(all(row.date_time == (1980, 1, 1, 0, 0, 0) for row in archive.infolist()))

    def test_private_classes_must_match_and_never_duplicate(self):
        original = dict(self.local)
        for mutation in ({}, {PREFIX + "Fixture.class": b"changed"},
                         {**original, PREFIX + "Extra.class": b"extra"}):
            with self.subTest(mutation=mutation):
                self.local = mutation
                self.run_fixture(rejected=True)
        self.local = original
        self.module.update(original)
        self.run_fixture(rejected=True)

    def test_missing_changed_and_unknown_private_resources_are_not_repaired(self):
        original = dict(self.module)
        for mutation in ({k: v for k, v in original.items() if not k.endswith("version.properties")},
                         {**original, PREFIX + "version.properties": b"changed"},
                         {**original, NOTICES + "unknown.txt": b"unknown"}):
            with self.subTest(mutation=mutation):
                self.module = mutation
                self.run_fixture(rejected=True)
        self.module = original
        self.local[NOTICES + "NOTICE.txt"] = b"changed"
        self.run_fixture(rejected=True)

    def test_duplicate_and_unsafe_input_entries_refused(self):
        self.run_fixture(rejected=True, duplicate="classes.jar")
        for name in ("../outside", "/absolute", "a\\b", "a//b", "a/./b"):
            with self.subTest(name=name):
                self.outer[name] = b"unexpected"
                self.run_fixture(rejected=True)
                del self.outer[name]

    def test_already_restored_layout_is_idempotent(self):
        first = self.run_fixture()
        aar = self.work / "restored.aar"
        aar.write_bytes(first)
        output = self.work / "twice.aar"
        result = self.invoke(aar, self.work / "producer.jar", output)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(first, output.read_bytes())

    def test_missing_jar_and_input_overwrite_refused(self):
        self.run_fixture()
        producer = self.work / "producer.jar"
        aar = self.work / "missing.aar"
        aar.write_bytes(pack(self.outer))
        result = self.invoke(aar, producer, self.work / "absent.aar")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.work / "absent.aar").exists())
        original = producer.read_bytes()
        self.assertNotEqual(self.invoke(self.work / "input.aar", producer, producer).returncode, 0)
        self.assertEqual(producer.read_bytes(), original)

    def test_transformed_existing_fixture_passes_unchanged_strict_publication_validator(self):
        # Reuse maintained public fixture constructors, not its test loops.
        path = ROOT / "scripts/tests/check-publish-license-test.py"
        tree = ast.parse(path.read_text())
        setup = ast.Module(body=[node for node in tree.body if isinstance(node,
            (ast.Import, ast.ImportFrom, ast.Assign, ast.FunctionDef))], type_ignores=[])
        fixture = {"__file__": str(path)}
        exec(compile(setup, str(path), "exec"), fixture)
        model = fixture["embedded_fixture"](self.work)
        fixture["write_fixture"](model, "valid")
        version = fixture["version"]
        directory = model["base"] / "p2p-transport-lan-android" / version
        aar = directory / ("p2p-transport-lan-android-" + version + ".aar")
        producer = model["root"] / "library/p2p-transport-lan/build/embedded-jmdns/p2pkit-internal-jmdns.jar"
        original = unpack(aar.read_bytes())
        producer_entries = unpack(producer.read_bytes())
        original[EMBEDDED] = pack({k: v for k, v in producer_entries.items() if k.endswith(".class")})
        original["classes.jar"] = pack({**unpack(original["classes.jar"]), **{k: v for k, v in producer_entries.items()
            if not k.endswith(".class") and k != "META-INF/MANIFEST.MF"}})
        aar.write_bytes(pack(original))
        output = self.work / "publication.aar"
        result = self.invoke(aar, producer, output)
        self.assertEqual(result.returncode, 0, result.stderr)
        aar.write_bytes(output.read_bytes())
        sources = directory / ("p2p-transport-lan-android-" + version + "-sources.jar")
        pom, module = fixture["publication_metadata"](model, "android", aar.read_bytes(), sources.read_bytes(), "valid")
        (directory / ("p2p-transport-lan-android-" + version + ".pom")).write_bytes(pom)
        (directory / ("p2p-transport-lan-android-" + version + ".module")).write_bytes(module)
        shell = ('set -euo pipefail\nROOT="$1"\nBASE="$2"\nGROUP="$3"\nVERSION="$4"\n'
                 'KOTLIN_VERSION="$5"\nCOROUTINES_VERSION="$6"\nfail=0\n')
        shell += fixture["embedded_policy"] + '\ncheck_embedded_jmdns\n[[ "$fail" == 0 ]]\n'
        result = subprocess.run(["bash", "-c", shell, "transform-test", str(model["root"]), str(model["base"]),
            fixture["group"], version, fixture["kotlin_version"], fixture["coroutines_version"]],
            capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.count(b"exact embedded producer, corrected sources"), 2)


if __name__ == "__main__":
    unittest.main(failfast=True)
