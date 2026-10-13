#!/usr/bin/env python3
"""Synthetic public receipt bytes, ZIP and service joins; no live acquisition."""
from copy import deepcopy
import hashlib
import importlib.util
import io
from pathlib import Path
import struct
import sys
import unittest
import warnings
import zipfile

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import hosted_initial_artifact_productive_delivery as D
import hosted_initial_ordinary_productive_qualification as Q
spec = importlib.util.spec_from_file_location("public_receipt_data_fixture",
    Path(__file__).with_name("hosted-initial-artifact-productive-delivery-test.py"))
F = importlib.util.module_from_spec(spec)
spec.loader.exec_module(F)


def fixture():
    f = F.qualification_fixture()
    upload, after = f["upload"], f["after"]
    expected = {"schema": 1, "source": deepcopy(upload["source"]), "github": {key: upload["github"][key]
        for key in ("repository", "runId", "runAttempt", "job")}, "selection": upload["selection"]}
    expected["github"]["ref"] = D.S.SOURCE_REF
    expected["upload"] = {"artifactId": upload["artifact"]["id"], "sha256": D.sha(f["upload_raw"]),
        **after["uploadCarrier"]}
    expected["after"] = {"artifactId": after["artifact"]["id"], "sha256": D.sha(f["after_raw"]),
        "directoryIdentitySha256": expected["upload"]["directoryIdentitySha256"],
        "fileMetadataSha256": F.model_hash("original-after-file"), "fileOwnerCloseSha256": F.model_hash("original-after-close")}
    observations = {stem + suffix + "Sha256": expected[role][field]
        for stem, role, field in (("directory", "upload", "directoryIdentitySha256"),
            ("upload", "upload", "fileMetadataSha256"), ("after", "after", "fileMetadataSha256"))
        for suffix in ("Before", "After")}
    args = dict(input_close_raw=b"SYNTHETIC_INPUT_CLOSE_NOT_NATIVE", first_ns=int(after["times"]["pendingPreparedNs"]) + D.NS,
        input_closed_ns=int(after["times"]["pendingPreparedNs"]) + 2 * D.NS,
        captured_at=F.MODEL_EPOCH + 5130, observations=observations)
    manifest = D.public_receipt_manifest(f["upload_raw"], f["after_raw"], expected, **args)
    return f, expected, args, {D.UPLOAD_FILE: f["upload_raw"], D.AFTER_FILE: f["after_raw"], D.PUBLIC_RECEIPT_FILE: manifest}


def archive(members, *, compression=zipfile.ZIP_STORED, descriptor=False):
    class Sequential(io.BytesIO):
        def seekable(self): return False
        def seek(self, *args): raise io.UnsupportedOperation("synthetic streaming ZIP")
    buffer = Sequential() if descriptor else io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=compression) as output:
        for name, raw in members.items():
            output.writestr(name, raw)
    raw = buffer.getvalue()
    return raw, {"artifactId": 2002, "bytes": len(raw), "sha256": D.sha(raw)}


def service_fixture(f, packet):
    entry = {"runId": f["after"]["github"]["runId"], "runAttempt": f["after"]["github"]["runAttempt"],
        "selection": f["after"]["selection"], "completedAt": F.MODEL_EPOCH + 5133,
        "packet": {"artifactId": int(f["after"]["artifact"]["id"]), "bytes": f["after"]["artifact"]["zipBytes"],
            "sha256": f["after"]["artifact"]["zipSha256"]}}
    def item(packet, name, created):
        url = Q.references.API + "/actions/artifacts/" + str(packet["artifactId"])
        return {"id": packet["artifactId"], "name": name, "url": url, "archive_download_url": url + "/zip",
            "size_in_bytes": packet["bytes"], "digest": "sha256:" + packet["sha256"], "expired": False,
            "created_at": F.utc(created), "expires_at": F.utc(created + 14 * 86400),
            "workflow_run": {"id": int(entry["runId"]), "head_sha": f["after"]["source"]["commit"],
                "head_branch": D.S.SOURCE_REF.removeprefix("refs/heads/")}}
    suffix = entry["runId"] + "-" + entry["runAttempt"] + "-worker-" + entry["selection"]
    companion = item(packet, "initial-recipient-productive-receipts-" + suffix, F.MODEL_EPOCH + 5132)
    primary = item(entry["packet"], "initial-recipient-productive-custody-" + suffix, F.MODEL_EPOCH + 5101)
    pages = ((Q.references.inventory_path(entry["runId"], 1), D.encoded({"total_count": 2,
        "artifacts": [primary, companion]}, Q.references.PAGE_LIMIT)),)
    return entry, primary, companion, pages


class PublicReceiptDataTests(unittest.TestCase):
    def setUp(self):
        self.f, self.expected, self.args, self.members = fixture()

    def manifest(self, **changes):
        return D.public_receipt_manifest(self.f["upload_raw"], self.f["after_raw"], self.expected, **{**self.args, **changes})

    def test_original_pair_manifest_is_not_native_or_private_qualification(self):
        value = D.public_receipt_manifest_inputs(self.members[D.PUBLIC_RECEIPT_FILE], self.f["upload_raw"], self.f["after_raw"])
        self.assertEqual(value["qualification"], "NOT_ESTABLISHED")
        self.assertEqual(value["privateOriginals"], "TERMINAL_SELF_TAIL_NOT_DELIVERED")
        self.assertEqual(value["inputReadClose"]["sha256"], D.sha(self.args["input_close_raw"]))
        self.assertNotIn("outputClose", value)
        self.assertEqual(D.public_receipt_service_inputs(self.members[D.PUBLIC_RECEIPT_FILE], self.f["upload_raw"],
            self.f["after_raw"], self.f["job_raw"], self.f["service_date"]), value)

    def test_expected_environment_and_no_receipt_base64_input(self):
        env = {"P2PKIT_EXPECTED_SHA": self.expected["source"]["commit"], "P2PKIT_EXPECTED_TREE": self.expected["source"]["tree"],
            "P2PKIT_INITIAL_SELECTION": self.expected["selection"], "GITHUB_SHA": self.expected["source"]["commit"]}
        env.update({"GITHUB_" + key: self.expected["github"][field] for key, field in
            (("REPOSITORY", "repository"), ("REF", "ref"), ("RUN_ID", "runId"), ("RUN_ATTEMPT", "runAttempt"), ("JOB", "job"))})
        for role in ("upload", "after"):
            prefix = "P2PKIT_RECEIPT_" + role.upper() + "_"
            env[prefix + "OUTCOME"] = "success"
            env.update({prefix + suffix: self.expected[role][field] for field, suffix in zip(D.PUBLIC_RECEIPT_ANCHORS,
                ("ARTIFACT_ID", "SHA256", "DIRECTORY_SHA256", "FILE_METADATA_SHA256", "OWNER_CLOSE_SHA256"))})
        self.assertEqual(D.public_receipt_expectations(env), self.expected)
        for key, value in (("GITHUB_SHA", "f" * 40), ("P2PKIT_RECEIPT_UPLOAD_OUTCOME", "failure"),
                ("P2PKIT_RECEIPT_AFTER_OUTCOME", "skipped"), ("P2PKIT_RECEIPT_UPLOAD_BASE64", "e30=")):
            with self.subTest(key=key), self.assertRaises(D.DeliveryError):
                D.public_receipt_expectations({**env, key: value})

    def test_original_pair_hash_carrier_source_and_run_substitution_rejected(self):
        for section, field, value in (("source", "commit", "f" * 40), ("source", "tree", "f" * 40),
                ("github", "runId", "999"), ("github", "runAttempt", "99"), ("github", "job", "other"),
                ("upload", "sha256", "f" * 64), ("after", "sha256", "f" * 64),
                ("upload", "fileOwnerCloseSha256", "f" * 64)):
            changed = deepcopy(self.expected); changed[section][field] = value
            with self.subTest(section=section, field=field), self.assertRaises(D.DeliveryError):
                D.public_receipt_pair(self.f["upload_raw"], self.f["after_raw"], changed, now=self.args["captured_at"])
        with self.assertRaises(D.DeliveryError):
            D.public_receipt_pair(D.encoded(self.f["upload"])[1:], self.f["after_raw"], self.expected, now=self.args["captured_at"])

    def test_manifest_closed_fields_hashes_bounds_and_no_self_acceptance(self):
        baseline = D.canonical(self.manifest())
        for field, value in (("qualification", "PASS"), ("privateOriginals", "DELIVERED"),
                ("jobId", 999), ("path", "/private/unexpected"), ("capturedAt", self.f["after"]["authorityExpiresAt"]),
                ("files", [])):
            with self.subTest(field=field), self.assertRaises(D.DeliveryError):
                D.public_receipt_manifest_inputs(D.encoded({**baseline, field: value}), self.f["upload_raw"], self.f["after_raw"])
        for container, field in (("primary", "zipBytes"), ("primary", "requestedRetentionDays"), ("files", "bytes")):
            changed = deepcopy(baseline)
            row = changed[container][0] if container == "files" else changed[container]
            row[field] = float(row[field])
            with self.subTest(container=container, field=field), self.assertRaises(D.DeliveryError):
                D.public_receipt_manifest_inputs(D.encoded(changed), self.f["upload_raw"], self.f["after_raw"])
        for key in D.PUBLIC_RECEIPT_OBSERVATIONS:
            with self.subTest(key=key), self.assertRaises(D.DeliveryError):
                self.manifest(observations={**self.args["observations"], key: "f" * 64})
        for changes in ({"input_closed_ns": self.args["first_ns"] - 1},
                {"input_closed_ns": self.args["first_ns"] + 20 * D.NS},
                {"first_ns": self.f["proposal"]["proposedJobEndNs"]}, {"input_close_raw": b""}):
            with self.subTest(changes=tuple(changes)), self.assertRaises(D.DeliveryError): self.manifest(**changes)

    def test_completed_input_close_and_utc_headroom_boundaries_are_strict(self):
        job_end = self.f["proposal"]["proposedJobEndNs"]
        for extra in (0, 1):
            with self.subTest(extra=extra), self.assertRaisesRegex(D.DeliveryError, "PUBLIC_RECEIPT_ORIGINAL_HEADROOM"):
                self.manifest(first_ns=job_end - 211 * D.NS, input_closed_ns=job_end - 210 * D.NS + extra)
        expiry = min(self.f["after"]["policyExpiresAt"], self.f["after"]["authorityExpiresAt"])
        with self.assertRaisesRegex(D.DeliveryError, "PUBLIC_RECEIPT_ORIGINAL_HEADROOM"):
            self.manifest(captured_at=expiry - 210)

    def test_exact_new_steps_and_old_adjacency_both_required(self):
        for index in (3, 4, 5, 6, 7):
            for field, value in (("conclusion", "skipped"), ("status", "pending"), ("number", 20)):
                job = deepcopy(self.f["job"]); job["steps"][index][field] = value
                with self.subTest(index=index, field=field), self.assertRaises(D.DeliveryError):
                    D.public_receipt_steps(job, self.f["service_date"])
        for index in (6, 7):
            job = deepcopy(self.f["job"]); del job["steps"][index]
            with self.assertRaises(D.DeliveryError): D.public_receipt_steps(job, self.f["service_date"])

    def test_future_pending_and_queued_only_after_unique_current_frontier(self):
        for mode, index in (("upload", 4), ("after", 5)):
            for state in ("pending", "queued"):
                job = deepcopy(self.f["job"])
                job["steps"][index].update(status="in_progress", conclusion=None, completed_at=None)
                for row in job["steps"][index + 1:]:
                    row.update(status=state, conclusion=None, started_at=None, completed_at=None)
                D.service_steps(job, self.f["service_date"], mode)
                for bad in ("in_progress", "completed"):
                    changed = deepcopy(job); changed["steps"][-1]["status"] = bad
                    with self.assertRaises(D.DeliveryError): D.service_steps(changed, self.f["service_date"], mode)
                changed = deepcopy(job); changed["steps"][0].update(status=state, conclusion=None, started_at=None, completed_at=None)
                with self.assertRaises(D.DeliveryError): D.service_steps(changed, self.f["service_date"], mode)

    def test_ordinary_zip_stored_deflate_and_descriptors_preserve_original_bytes(self):
        for compression in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            for descriptor in (False, True):
                raw, packet = archive(self.members, compression=compression, descriptor=descriptor)
                self.assertEqual(Q.read_public_receipt_zip(io.BytesIO(raw), packet, lambda: None), self.members)

    def test_zip_missing_extra_duplicate_traversal_noncanonical_rejected(self):
        variations = [dict(list(self.members.items())[:2]), {**self.members, "extra": b"no"},
            {"../" + key: value for key, value in self.members.items()},
            {**self.members, D.PUBLIC_RECEIPT_FILE: self.members[D.PUBLIC_RECEIPT_FILE] + b" "},
            {**self.members, D.UPLOAD_FILE: b"x" * (D.LIMIT + 1)}]
        for members in variations:
            raw, packet = archive(members)
            with self.subTest(members=tuple(members)), self.assertRaises(Exception):
                Q.read_public_receipt_zip(io.BytesIO(raw), packet, lambda: None)
        buffer = io.BytesIO()
        with warnings.catch_warnings(record=True) as emitted:
            warnings.simplefilter("always", UserWarning)
            with zipfile.ZipFile(buffer, "w") as duplicate:
                for name in (D.UPLOAD_FILE, D.UPLOAD_FILE, D.PUBLIC_RECEIPT_FILE):
                    duplicate.writestr(name, self.members[name])
        self.assertEqual(len(emitted), 1)
        duplicated = buffer.getvalue()
        with self.assertRaises(Exception):
            Q.read_public_receipt_zip(io.BytesIO(duplicated), {"artifactId": 2002, "bytes": len(duplicated),
                "sha256": D.sha(duplicated)}, lambda: None)
        raw, packet = archive(self.members)
        for changed in (raw[:-1], raw + b"junk", b"prefix" + raw):
            bad = {**packet, "bytes": len(changed), "sha256": D.sha(changed)}
            with self.assertRaises(Exception): Q.read_public_receipt_zip(io.BytesIO(changed), bad, lambda: None)

    def test_zip_local_crc_bytes_metadata_or_archive_digest_substitution_rejected(self):
        raw, packet = archive(self.members)
        for offset in (14, 18, 26, 30, 90):
            changed = bytearray(raw); changed[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(Exception):
                Q.read_public_receipt_zip(io.BytesIO(bytes(changed)), {**packet, "sha256": D.sha(bytes(changed))}, lambda: None)
        with self.assertRaises(Exception):
            Q.read_public_receipt_zip(io.BytesIO(raw), {**packet, "sha256": "f" * 64}, lambda: None)
        def cancel(): raise InterruptedError("synthetic cancellation")
        with self.assertRaises(InterruptedError): Q.read_public_receipt_zip(io.BytesIO(raw), packet, cancel)

    def test_artifact_identity_complete_inventory_attempt_and_primary_join(self):
        raw, packet = archive(self.members)
        entry, primary, artifact, pages = service_fixture(self.f, packet)
        self.assertEqual(Q.public_receipt_artifact(D.encoded(artifact), pages, entry, self.f["after"]["source"],
            self.f["service_date"]), (artifact, packet))
        for field, value in (("name", artifact["name"].replace("-2-worker-", "-1-worker-")),
                ("expired", True), ("size_in_bytes", 65537), ("digest", "sha256:" + "f" * 64)):
            with self.subTest(field=field), self.assertRaises(Exception):
                Q.public_receipt_artifact(D.encoded({**artifact, field: value}), pages, entry,
                    self.f["after"]["source"], self.f["service_date"])
        duplicate = {**artifact, "id": 9009, "url": artifact["url"].replace("2002", "9009"),
            "archive_download_url": artifact["archive_download_url"].replace("2002", "9009")}
        for rows in ([primary], [artifact], [primary, artifact, duplicate], [primary, artifact, artifact]):
            broken = ((pages[0][0], D.encoded({"total_count": len(rows), "artifacts": rows})),)
            with self.assertRaises(Exception): Q.public_receipt_artifact(D.encoded(artifact), broken, entry,
                self.f["after"]["source"], self.f["service_date"])

    def test_completed_service_cannot_extend_original_job_or_capture_window(self):
        for key, value in (("completed_at", F.utc(F.MODEL_EPOCH + 5400)), ("run_attempt", 3), ("id", 999)):
            job = {**self.f["job"], key: value}
            with self.subTest(key=key), self.assertRaises(D.DeliveryError):
                D.public_receipt_service_inputs(self.members[D.PUBLIC_RECEIPT_FILE], self.f["upload_raw"],
                    self.f["after_raw"], D.encoded(job), F.MODEL_EPOCH + 5401)
        for index, duration in ((6, 61), (7, 121)):
            job = deepcopy(self.f["job"])
            job["steps"][index]["completed_at"] = F.utc(F.MODEL_EPOCH + 5130 + index - 6 + duration)
            if index == 6:
                job["steps"][7]["started_at"] = job["steps"][6]["completed_at"]
                job["steps"][7]["completed_at"] = F.utc(F.MODEL_EPOCH + 5192)
            job["completed_at"] = F.utc(F.MODEL_EPOCH + 5300)
            with self.assertRaisesRegex(D.DeliveryError, "PUBLIC_RECEIPT_STEP_TIME_CAP"):
                D.public_receipt_service_inputs(self.members[D.PUBLIC_RECEIPT_FILE], self.f["upload_raw"],
                    self.f["after_raw"], D.encoded(job), F.MODEL_EPOCH + 5301)
        job = deepcopy(self.f["job"]); job["steps"][6]["started_at"] = F.utc(F.MODEL_EPOCH + 5131)
        with self.assertRaises(D.DeliveryError): D.public_receipt_service_inputs(self.members[D.PUBLIC_RECEIPT_FILE],
            self.f["upload_raw"], self.f["after_raw"], D.encoded(job), self.f["service_date"])


if __name__ == "__main__":
    unittest.main(failfast=True)
