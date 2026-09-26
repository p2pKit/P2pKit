#!/usr/bin/env python3
"""Offline supplied-DATA controls, NOT productive packet qualification.

All comments, IDs, metadata, digests and dates are synthetic. No network, native
owner, private key, archive download/decryption, approval or workflow execution.
"""
from __future__ import annotations

import datetime
import hashlib
from pathlib import Path
import sys
import unittest


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen"):
        raise RuntimeError("OFFLINE_PROCESS_NETWORK_NATIVE_FORBIDDEN")


sys.addaudithook(offline)
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_initial_ordinary_qualification as Q

I, S = Q.I, Q.stages
H1, H2, MERGE = (c * 40 for c in "ace")
START, COMPLETE, CREATED, AUTHORITY = 1789948800, 1789948900, 1789948950, 1789949000
OWNER = {"login": "Apdelrahman1911", "id": 104788132, "type": "User"}
FULL_ZIP = b"MODEL_FULL_ARTIFACT_ZIP_NOT_AN_ACTUAL_ARCHIVE"
INNER = b"MODEL_INNER_CIPHERTEXT"


def utc(value):
    return datetime.datetime.fromtimestamp(value, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def reference(raw, **locator):
    return {**locator, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def artifact(identifier=1001, run_id="301"):
    url = Q.API + "/actions/artifacts/" + str(identifier)
    return {"id": identifier, "url": url, "archive_download_url": url + "/zip", "name": "MODEL-unqualified",
        "size_in_bytes": len(FULL_ZIP), "digest": "sha256:" + hashlib.sha256(FULL_ZIP).hexdigest(),
        "expired": False, "created_at": utc(COMPLETE), "expires_at": utc(COMPLETE + Q.RETENTION_SECONDS),
        "workflow_run": {"id": int(run_id), "head_sha": H1,
            "head_branch": S.SOURCE_REF.removeprefix("refs/heads/")}}


class ReferenceModels(unittest.TestCase):
    def setUp(self):
        self.body = I.encoded({"schema": "MODEL_UNKNOWN_NOT_QUALIFIED", "source": H1}).removesuffix(b"\n")
        self.reference = reference(self.body, commentId=9001)
        self.comment = {"id": 9001, "url": "https://api.github.com" + Q.metadata_path(self.reference),
            "issue_url": Q.API + "/issues/437", "html_url": "https://github.com/p2pKit/P2pKit/issues/437#issuecomment-9001",
            "user": dict(OWNER), "performed_via_github_app": None, "created_at": utc(CREATED),
            "updated_at": utc(CREATED), "body": self.body.decode("ascii")}

    def body_check(self, **options):
        args = dict(comment_raw=I.encoded(self.comment), reference=self.reference,
                    completed_at=COMPLETE, authority_created_at=AUTHORITY)
        args.update(options)
        return Q.metadata_body(**args)

    def test_direct_comment_returns_exact_body_without_minting_schema_acceptance(self):
        self.assertEqual(Q.metadata_path(self.reference), "/repos/p2pKit/P2pKit/issues/comments/9001")
        self.assertEqual(self.body_check(), self.body)
        self.assertIs(type(self.body_check()), bytes)
        envelope = I.encoded(self.comment)
        with self.assertRaisesRegex(I.AdmissionError, "COMMENT_DIGEST"):
            self.body_check(reference=reference(envelope, commentId=9001))

    def test_exact_comment_location_owner_non_app_and_unedited_dates(self):
        for field, bad in (("id", True), ("id", "9001"), ("url", Q.API + "/issues/comments/9002"),
                ("issue_url", Q.API + "/issues/438"), ("html_url", "https://github.com/other"),
                ("user", {**OWNER, "id": True}), ("user", {**OWNER, "login": "other"}),
                ("user", {**OWNER, "type": "Bot"}), ("performed_via_github_app", {"id": 7}),
                ("updated_at", utc(CREATED + 1))):
            with self.subTest(field=field, bad=bad):
                changed = {**self.comment, field: bad}
                with self.assertRaises(I.AdmissionError):
                    self.body_check(comment_raw=I.encoded(changed))
        changed = dict(self.comment)
        del changed["performed_via_github_app"]
        with self.assertRaisesRegex(I.AdmissionError, "COMMENT_AUTHOR"):
            self.body_check(comment_raw=I.encoded(changed))

    def test_metadata_follows_completion_and_strictly_precedes_new_authority(self):
        self.body_check(completed_at=CREATED)
        for options in ({"completed_at": CREATED + 1}, {"authority_created_at": CREATED},
                {"completed_at": True}, {"authority_created_at": float(AUTHORITY)}, {"completed_at": 0}):
            with self.subTest(options=options), self.assertRaisesRegex(I.AdmissionError, "COMMENT_WINDOW"):
                self.body_check(**options)

    def test_body_digest_and_canonical_ascii_json_are_not_normalized(self):
        with self.assertRaisesRegex(I.AdmissionError, "COMMENT_DIGEST"):
            self.body_check(comment_raw=I.encoded({**self.comment, "body": self.comment["body"] + " "}))
        for raw in (self.body + b"\n", b" " + self.body, b'{"x": 1}', b'{"x":1,"x":2}', b"[]", b'{"x":NaN}'):
            with self.subTest(raw=raw[:24]), self.assertRaises(I.AdmissionError):
                self.body_check(comment_raw=I.encoded({**self.comment, "body": raw.decode("ascii")}),
                                reference=reference(raw, commentId=9001))
        with self.assertRaisesRegex(I.AdmissionError, "COMMENT_BODY"):
            self.body_check(comment_raw=I.encoded({**self.comment, "body": "\N{LATIN SMALL LETTER E WITH ACUTE}"}))

    def test_reference_fields_and_original_types_are_closed(self):
        for field, bad in (("commentId", True), ("commentId", "9001"), ("commentId", 0),
                ("bytes", True), ("bytes", 0), ("sha256", "A" * 64), ("url", "https://example.invalid")):
            with self.subTest(field=field), self.assertRaises(I.AdmissionError):
                self.body_check(reference={**self.reference, field: bad})
        for raw in (bytearray(I.encoded(self.comment)), memoryview(I.encoded(self.comment))):
            with self.assertRaisesRegex(I.AdmissionError, "COMMENT_BYTES"):
                self.body_check(comment_raw=raw)

    def test_ordered_inventory_includes_every_page_and_returns_data_only(self):
        rows = [artifact(n) for n in range(1, 102)]
        pages = ((Q.inventory_path("301", 1), I.encoded({"total_count": 101, "artifacts": rows[:100]})),
                 (Q.inventory_path("301", 2), I.encoded({"total_count": 101, "artifacts": rows[100:]})))
        result = Q.complete_inventory(pages, run_id="301")
        self.assertIs(type(result), tuple)
        self.assertEqual(result, tuple(rows))
        self.assertFalse(any("qualification" in item for item in result))
        empty = ((Q.inventory_path("301", 1), I.encoded({"total_count": 0, "artifacts": []})),)
        self.assertEqual(Q.complete_inventory(empty, run_id="301"), ())

    def test_finite_inventory_ceiling_is_ten_complete_pages_not_silent_truncation(self):
        rows = [artifact(n) for n in range(1, 1001)]
        pages = tuple((Q.inventory_path("301", n + 1),
            I.encoded({"total_count": 1000, "artifacts": rows[n * 100:(n + 1) * 100]})) for n in range(10))
        self.assertEqual(len(Q.complete_inventory(pages, run_id="301")), 1000)
        with self.assertRaisesRegex(I.AdmissionError, "PAGES"):
            Q.complete_inventory(pages + (pages[-1],), run_id="301")
        with self.assertRaisesRegex(I.AdmissionError, "INCOMPLETE_INVENTORY"):
            Q.complete_inventory(pages[:-1], run_id="301")

    def test_inventory_refuses_reordered_duplicate_short_changed_total_or_wrong_run(self):
        rows = [artifact(n) for n in range(1, 102)]
        one, two = {"total_count": 101, "artifacts": rows[:100]}, {"total_count": 101, "artifacts": rows[100:]}
        def pages(left, right):
            return ((Q.inventory_path("301", 1), I.encoded(left)), (Q.inventory_path("301", 2), I.encoded(right)))
        for supplied in (tuple(reversed(pages(one, two))), pages(one, {**two, "total_count": 102}),
                pages({**one, "artifacts": rows[:99]}, two), pages(one, {**two, "artifacts": [rows[0]]}),
                pages(one, {**two, "artifacts": [artifact(101, "302")]})):
            with self.subTest(kind=supplied[-1][0]), self.assertRaises(I.AdmissionError):
                Q.complete_inventory(supplied, run_id="301")

    def test_inventory_exact_data_types_and_page_path_cannot_override_equality(self):
        class EqualPath(str):
            def __eq__(self, _other):
                raise AssertionError("non-exact requested-path comparison must not run")
        path = Q.inventory_path("301", 1)
        raw = I.encoded({"total_count": 0, "artifacts": []})
        for supplied in ([(path, raw)], ((EqualPath(path), raw),), ((path, bytearray(raw)),),
                ((path, I.encoded({"total_count": True, "artifacts": []})),),
                ((path, I.encoded({"total_count": 0, "artifacts": [], "next": "other"})),)):
            with self.assertRaises(I.AdmissionError):
                Q.complete_inventory(supplied, run_id="301")
        for run, page in (("01", 1), (True, 1), ("301", True), ("301", 0), ("301", 11)):
            with self.assertRaises(I.AdmissionError):
                Q.inventory_path(run, page)

    def test_artifact_roster_location_and_positive_ids_are_not_external_urls(self):
        for field, bad in (("id", True), ("id", 0), ("url", "https://example.invalid/1"),
                ("archive_download_url", Q.API + "/actions/artifacts/1001/zip/other")):
            row = {**artifact(), field: bad}
            pages = ((Q.inventory_path("301", 1), I.encoded({"total_count": 1, "artifacts": [row]})),)
            with self.subTest(field=field), self.assertRaises(I.AdmissionError):
                Q.complete_inventory(pages, run_id="301")

    def artifact_check(self, **options):
        args = dict(artifact_raw=I.encoded(artifact()), reference=reference(FULL_ZIP, artifactId=1001),
                    run_id="301", reviewed={"commit": H1, "tree": "b" * 40}, now=CREATED)
        args.update(options)
        return Q.artifact_reference(**args)

    def test_artifact_full_zip_reference_is_not_its_inner_ciphertext_or_acceptance(self):
        result = self.artifact_check()
        self.assertEqual(result, artifact())
        self.assertIs(type(result), dict)
        self.assertNotIn("qualification", result)
        with self.assertRaisesRegex(I.AdmissionError, "ARTIFACT_DIGEST_OR_EXPIRY"):
            self.artifact_check(reference=reference(INNER, artifactId=1001))
        with self.assertRaisesRegex(I.AdmissionError, "PACKET_FIELDS"):
            self.artifact_check(reference={**reference(FULL_ZIP, artifactId=1001), "member": "evidence.tar.gz.gpg"})

    def test_artifact_metadata_binds_historical_h1_not_current_h2_or_merge(self):
        for field, bad in (("head_sha", H2), ("head_sha", MERGE), ("id", 401),
                ("id", True), ("head_branch", "main")):
            row = artifact()
            row["workflow_run"][field] = bad
            with self.subTest(field=field), self.assertRaisesRegex(I.AdmissionError, "ARTIFACT_SOURCE"):
                self.artifact_check(artifact_raw=I.encoded(row))

    def test_artifact_digest_size_expiry_and_name_are_exact(self):
        for field, bad in (("id", 1002), ("size_in_bytes", True), ("size_in_bytes", len(INNER)),
                ("digest", "sha256:" + "0" * 64), ("expired", True), ("expired", 0),
                ("name", ""), ("name", "bad\nname")):
            with self.subTest(field=field), self.assertRaises(I.AdmissionError):
                self.artifact_check(artifact_raw=I.encoded({**artifact(), field: bad}))

    def test_artifact_finite_actual_retention_window_is_not_a_requested_policy(self):
        for field, bad in (("created_at", utc(CREATED + 1)), ("expires_at", utc(CREATED)),
                ("expires_at", utc(COMPLETE + Q.RETENTION_SECONDS + 1))):
            with self.subTest(field=field), self.assertRaisesRegex(I.AdmissionError, "ARTIFACT_WINDOW"):
                self.artifact_check(artifact_raw=I.encoded({**artifact(), field: bad}))
        for now in (True, 0, COMPLETE - 1, COMPLETE + Q.RETENTION_SECONDS):
            with self.subTest(now=now), self.assertRaises(I.AdmissionError):
                self.artifact_check(now=now)


if __name__ == "__main__":
    unittest.main(failfast=True)
