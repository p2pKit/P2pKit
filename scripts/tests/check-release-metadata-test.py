#!/usr/bin/env python3
"""Run the real metadata gate against disposable source/release fixtures; no Gradle."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
GROUP = "io.github.apdelrahman1911"
SNAPSHOT = "9.8.7-SNAPSHOT"
RELEASE = "9.8.7-rc6"
PUBLISHED = "9.8.6-rc2"
RECORD = f"docs/releases/{PUBLISHED}.md"
JAVA = "buildSrc/src/main/java/dev/p2pkit/build/P2pPomMetadata.java"
URL = "https://github.com/p2pKit/P2pKit"
DECLARATION = f'private static final String REPOSITORY_URL = "{URL}";'
NEGATIVE_FILES = (
    "README.md", "CLAUDE.md", "gradle.properties", "build.gradle.kts", RECORD,
    "docs/guides/migrating-to-0.7.md", "docs/releasing/maven-central.md",
    "scripts/check-published-consumers.sh",
)


class ReleaseMetadataTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="p2pkit-release-metadata-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        files = {
            "gradle.properties": (
                f"GROUP={GROUP}\nVERSION_NAME={SNAPSHOT}\nLATEST_PUBLISHED_VERSION={PUBLISHED}\n"
            ),
            "README.md": (
                f"**Development version:** `{SNAPSHOT}`.\n"
                f"**Latest published version:** `{PUBLISHED}`.\n`{GROUP}:p2p-core:{PUBLISHED}`\n"
            ),
            "CHANGELOG.md": f"## Unreleased\n## {PUBLISHED} — release candidate\n",
            "CLAUDE.md": "Repository guidance\n",
            "build.gradle.kts": f'group = providers.gradleProperty("GROUP").orNull ?: "{GROUP}"\n',
            "docs/architecture/specification.md": "# Current high-level API and protocol contract\n",
            "docs/guides/migrating-to-0.7.md": f"# Migrating from 0.6.x to {PUBLISHED}\n`{GROUP}`\n",
            RECORD: f"`{GROUP}:p2p-core:{PUBLISHED}`\n",
            "docs/releasing/maven-central.md": f"`{GROUP}`\n",
            "samples/iosApp/Info.plist": "<string>_p2pkit2._tcp</string>\n",
            "samples/iosApp/project.yml": '- "_p2pkit2._tcp"\n',
            "scripts/run-ios-app.sh": "_p2pkit2._tcp\n",
            "scripts/check-published-consumers.sh": "#!/usr/bin/env bash\n",
            JAVA: f"public final class P2pPomMetadata {{\n    {DECLARATION}\n}}\n",
        }
        for module in (
            "p2p-core", "p2p-transport-lan", "p2p-network-provisioning-android",
            "p2p-network-provisioning-desktop",
        ):
            files[f"library/{module}/build.gradle.kts"] = "P2pPomMetadata.configure(this)\n"
        for name, content in files.items():
            self.write(name, content)
        shutil.copyfile(ROOT / "scripts/check-release-metadata.sh", self.root / "scripts/check-release-metadata.sh")

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def replace(self, name, old, new):
        path = self.root / name
        content = path.read_text(encoding="utf-8")
        self.assertEqual(1, content.count(old), f"fixture must replace exactly one {old!r} in {name}")
        self.write(name, content.replace(old, new))

    def check(self, success=True, diagnostic="", env=None):
        result = subprocess.run(
            ["bash", str(self.root / "scripts/check-release-metadata.sh")],
            cwd=self.root, env=env, text=True, capture_output=True, timeout=30,
        )
        self.assertEqual(success, result.returncode == 0, result.stdout + result.stderr)
        if success:
            self.assertIn("RESULT: PASS", result.stdout)
        else:
            self.assertNotIn("RESULT: PASS", result.stdout)
            self.assertIn(diagnostic, result.stderr)

    def select_release(self):
        self.replace("gradle.properties", f"VERSION_NAME={SNAPSHOT}", f"VERSION_NAME={RELEASE}")
        self.replace("README.md", f"**Development version:** `{SNAPSHOT}`.",
                     f"**Current source version:** `{RELEASE}` release candidate.")
        self.replace("CHANGELOG.md", "## Unreleased", f"## {RELEASE} — release candidate")

    def test_snapshot_and_release_branches_accept_consistent_values(self):
        self.check()
        self.select_release()
        self.check()

    def test_formatting_and_java_modifier_order_do_not_change_values(self):
        self.select_release()
        self.replace("README.md", f"**Current source version:** `{RELEASE}` release candidate.",
                     f"__Current  source version__ : {RELEASE}.")
        self.replace("README.md", f"**Latest published version:** `{PUBLISHED}`.",
                     f"Latest published version: `{PUBLISHED}`!")
        self.replace("CHANGELOG.md", f"## {RELEASE} — release candidate", f"##  `{RELEASE}` - release candidate")
        self.replace("CHANGELOG.md", f"## {PUBLISHED} — release candidate", f"## {PUBLISHED} -- release candidate")
        self.replace("docs/guides/migrating-to-0.7.md", f"# Migrating from 0.6.x to {PUBLISHED}",
                     f"#  Migrating  from 0.6.x to `{PUBLISHED}`: upgrade guide")
        self.replace("docs/architecture/specification.md", "# Current high-level API and protocol contract",
                     "#  Current  high-level API and protocol contract  #")
        self.replace(JAVA, DECLARATION,
                     f'final /* field */ private\nstatic String REPOSITORY_URL\n=\n"{URL}"\n;')
        self.check()

    def test_wrong_version_fields_cannot_hide_behind_unrelated_correct_tokens(self):
        for name, old, wrong in (
            ("README.md", f"`{SNAPSHOT}`.", f"`{SNAPSHOT}-extra`."),
            ("README.md", f"`{PUBLISHED}`.", f"`{PUBLISHED}0`."),
            ("CHANGELOG.md", f"## {PUBLISHED}", f"## {PUBLISHED}-extra"),
            ("docs/guides/migrating-to-0.7.md", f"to {PUBLISHED}", f"to {PUBLISHED}0"),
            ("docs/architecture/specification.md", "high-level API and protocol contract",
             "API and protocol specification"),
        ):
            with self.subTest(name=name, wrong=wrong):
                original = (self.root / name).read_text(encoding="utf-8")
                try:
                    self.write(name, original.replace(old, wrong) + f"\nOther text: {SNAPSHOT} {PUBLISHED}\n")
                    self.check(False, "release contract token")
                finally:
                    self.write(name, original)

    def test_wrong_release_day_source_field_is_rejected(self):
        self.select_release()
        self.replace("README.md", f"`{RELEASE}`", f"`{RELEASE}0`")
        self.check(False, "release contract token")

    def test_java_wrong_url_cannot_be_masked_by_comment_or_string_decoys(self):
        original = (self.root / JAVA).read_text(encoding="utf-8")
        for decoy in (f"// {DECLARATION}\n", f"/*\n{DECLARATION}\n*/\n",
                      f'private static final String DECOY = """\n{DECLARATION}\n""";\n'):
            with self.subTest(decoy=decoy):
                self.write(JAVA, original.replace(DECLARATION, DECLARATION.replace(URL, "https://example.invalid")) + decoy)
                self.check(False, "REPOSITORY_URL")

    def test_missing_and_nonregular_negative_only_guard_files_fail_closed(self):
        for name in ("CLAUDE.md", "scripts/check-published-consumers.sh"):
            with self.subTest(name=name):
                path = self.root / name
                original = path.read_text(encoding="utf-8")
                path.unlink()
                try:
                    self.check(False, f"guarded file is missing or unreadable: {name}")
                    path.mkdir()
                    self.check(False, f"guarded file is missing or unreadable: {name}")
                finally:
                    if path.is_dir():
                        path.rmdir()
                    self.write(name, original)

    def test_legacy_group_is_rejected_in_every_guarded_file(self):
        for name in NEGATIVE_FILES:
            with self.subTest(name=name):
                original = (self.root / name).read_text(encoding="utf-8")
                try:
                    self.write(name, original + "\ndev.p2pkit:p2p-core:legacy\n")
                    self.check(False, "former Maven group")
                finally:
                    self.write(name, original)

    def test_legacy_bonjour_remains_forbidden(self):
        for name, legacy in (
            ("samples/iosApp/Info.plist", "<string>_p2pkit._tcp</string>"),
            ("samples/iosApp/project.yml", '- "_p2pkit._tcp"'),
        ):
            with self.subTest(name=name):
                original = (self.root / name).read_text(encoding="utf-8")
                try:
                    self.write(name, original + legacy + "\n")
                    self.check(False, "legacy Bonjour")
                finally:
                    self.write(name, original)

    def test_required_coordinate_and_secure_namespace_claims_remain_guarded(self):
        for name, expected, wrong in (
            ("README.md", f"`{GROUP}:p2p-core:{PUBLISHED}`", f"`{GROUP}:p2p-core:{PUBLISHED}0`"),
            ("samples/iosApp/Info.plist", "_p2pkit2._tcp", "_wrong._tcp"),
            ("samples/iosApp/project.yml", "_p2pkit2._tcp", "_wrong._tcp"),
            ("scripts/run-ios-app.sh", "_p2pkit2._tcp", "_wrong._tcp"),
        ):
            with self.subTest(name=name):
                original = (self.root / name).read_text(encoding="utf-8")
                try:
                    self.replace(name, expected, wrong)
                    self.check(False, "release contract text")
                finally:
                    self.write(name, original)

    def test_wrong_group_source_is_rejected(self):
        self.replace("gradle.properties", f"GROUP={GROUP}", "GROUP=io.github.wrong")
        self.check(False, "owner-verified Central namespace")

    def test_grep_read_error_cannot_pass_a_negative_guard(self):
        # Deterministic rc=2 even when privileged/root tests can read mode-000 files.
        self.write("bin/grep", '#!/usr/bin/env bash\n'
                   'if [[ "${@: -1}" == */CLAUDE.md ]]; then\n'
                   '  echo "fixture grep read error" >&2\n  exit 2\nfi\n'
                   'command -p grep "$@"\n')
        (self.root / "bin/grep").chmod(0o755)
        env = os.environ.copy()
        env["PATH"] = str(self.root / "bin") + os.pathsep + env["PATH"]
        self.check(False, "cannot inspect CLAUDE.md (grep exited 2)", env=env)


if __name__ == "__main__":
    unittest.main()
