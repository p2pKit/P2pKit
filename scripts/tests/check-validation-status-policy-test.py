#!/usr/bin/env python3
"""Check mutable campaign-status entry points, not dated history/security disclaimers."""
import re
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
CANONICAL = "docs/validation/README.md"
POINTERS = {
    "README.md": "docs/validation/README.md#current-status",
    "CLAUDE.md": "docs/validation/README.md#current-status",
    "docs/testing/validation-status.md": "../validation/README.md#current-status",
    "docs/testing/external-validation.md": "../validation/README.md",
    "docs/testing/wire-goldens.md": "../validation/README.md#independent-interop",
    "docs/validation/test-catalog.md": "README.md#current-status",
    **{"docs/validation/" + name + ".md": "README.md#" + anchor for name, anchor in (
        ("android-physical-device", "android-physical"),
        ("apple-physical-awdl", "apple-physical"),
        ("hostile-network", "hostile-network"),
        ("cli-desktop-faults", "cli-desktop"),
        ("secure-v2-interoperability", "independent-interop"),
        ("secure-v2-wire-candidate", "independent-interop"),
        ("cryptographic-audit-preparation", "professional-crypto"),
    )},
}
HISTORICAL = "docs/testing/mac-handoff.md"
HISTORICAL_MARKER = "Frozen historical status at the consolidation handoff"
HISTORICAL_TARGET = "../validation/README.md#current-status"


def check(files):
    authority = files[CANONICAL]
    assert "sole mutable campaign-status authority" in authority, "missing authority"
    for path, target in POINTERS.items():
        text = files[path]
        assert "](" + target + ")" in text, path + ": missing canonical pointer"
        if "#" in target:
            anchor = target.split("#")[1]
            assert ('id="' + anchor + '"') in authority or anchor == "current-status", "missing anchor"
        flat = " ".join(text.split())
        assert not re.search(r"\bsix\b[^.!?]{0,180}\b(?:remain|are)\s+(?:explicitly\s+)?pending\b", flat, re.I), path + ": blanket mutable status"
        assert not re.search(r"\b(?:NOT[ _]STARTED|PARTIALLY[ _]VALIDATED|EXTERNAL[ _]AUDIT[ _]REQUIRED)\b", text), path + ": copied campaign label"
    assert "do not promote them from compilation or simulator results" in files["CLAUDE.md"], "lost evidence constraint"
    assert HISTORICAL_MARKER in files[HISTORICAL], "missing historical boundary"
    assert "](" + HISTORICAL_TARGET + ")" in files[HISTORICAL], "missing historical current-status pointer"


class StatusPolicyTest(unittest.TestCase):
    def setUp(self):
        self.files = {path: (ROOT / path).read_text() for path in (CANONICAL, *POINTERS, HISTORICAL)}

    def test_current(self):
        check(self.files)

    def test_each_pointer_required(self):
        for path, target in POINTERS.items():
            with self.subTest(path=path), self.assertRaisesRegex(AssertionError, "missing canonical pointer"):
                check({**self.files, path: self.files[path].replace(target, "missing.md")})

    def test_original_blanket_duplicates_rejected(self):
        for path in ("CLAUDE.md", "docs/validation/test-catalog.md"):
            with self.subTest(path=path), self.assertRaisesRegex(AssertionError, "blanket mutable status"):
                check({**self.files, path: self.files[path] + "\nThe six external areas\nremain pending.\n"})

    def test_copied_per_area_label_rejected(self):
        for path in POINTERS:
            for label in ("NOT STARTED", "PARTIALLY VALIDATED", "EXTERNAL AUDIT REQUIRED", "NOT_STARTED"):
                with self.subTest(path=path, label=label), self.assertRaisesRegex(AssertionError, "copied campaign label"):
                    check({**self.files, path: self.files[path] + "\nCLI/Desktop: " + label})

    def test_historical_boundary_and_current_pointer_required(self):
        for text, error in ((HISTORICAL_MARKER, "missing historical boundary"),
                            (HISTORICAL_TARGET, "missing historical current-status pointer")):
            with self.subTest(text=text), self.assertRaisesRegex(AssertionError, error):
                check({**self.files, HISTORICAL: self.files[HISTORICAL].replace(text, "")})

    def test_each_status_can_change_in_canonical_file_only(self):
        # Synthetic source-only fixture: never advances a real campaign.
        for line in self.files[CANONICAL].splitlines():
            if line.startswith('| <a id="'):
                with self.subTest(row=line.split("|")[1]):
                    changed = re.sub(r"\*\*[^*]+\*\*", "**COMPLETED (fixture only)**", line)
                    check({**self.files, CANONICAL: self.files[CANONICAL].replace(line, changed)})

    def test_evidence_constraint_required(self):
        with self.assertRaisesRegex(AssertionError, "lost evidence constraint"):
            check({**self.files, "CLAUDE.md": self.files["CLAUDE.md"].replace("do not promote them from compilation or simulator results", "")})


if __name__ == "__main__":
    unittest.main()
