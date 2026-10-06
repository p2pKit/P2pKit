#!/usr/bin/env python3
"""New supplied-DATA controls; NOT native/provider/crypto/hosted qualification.

Every comment, approval, ZIP and provider row is explicitly synthetic. Only the
existing committed PUBLIC policy fixture is read. No private key, process, native
backend, archive download, network, build or earlier test method is executed.
The complete productive-codec join has separate connected controls; individual
helper success here cannot establish ProductiveQualification or current authority.
"""
from __future__ import annotations

import base64
import copy
import ctypes  # Initialize stdlib before forbidding any native loader below.
import hashlib
import importlib.util
import io
from pathlib import Path
import struct
import sys
import unittest


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen"):
        raise RuntimeError("OFFLINE_PROCESS_NETWORK_NATIVE_FORBIDDEN")


sys.addaudithook(offline)
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_initial_ordinary_productive_qualification as Q

spec = importlib.util.spec_from_file_location("initial_ordinary_productive_stage_fixture",
    Path(__file__).with_name("hosted-initial-recipient-stages-test.py"))
F = importlib.util.module_from_spec(spec)
spec.loader.exec_module(F)
delivery_spec = importlib.util.spec_from_file_location("initial_ordinary_productive_delivery_fixture",
    Path(__file__).with_name("hosted-initial-artifact-productive-delivery-test.py"))
DF = importlib.util.module_from_spec(delivery_spec)
delivery_spec.loader.exec_module(DF)
# Join only this private delivery fixture to the policy-relative stage fixture.
# Preserve its original offset: 1790000000 - 1789948800 = 51_200 seconds.
DF.MODEL_EPOCH = F.START + 51_200
S, I, Z = Q.S, Q.I, Q.ZIP


def encoded64(raw):
    return base64.b64encode(raw).decode("ascii")


def zip_fixture():
    contents = (b"SYNTHETIC_FINAL_CIPHERTEXT_NOT_ENCRYPTED", b'{"synthetic":"final"}\n',
                b"SYNTHETIC_TAIL_CIPHERTEXT_NOT_ENCRYPTED", b'{"synthetic":"tail"}\n')
    members = [{"name": name, "bytes": len(raw), "sha256": Q.digest(raw)} for name, raw in zip(Z.MEMBERS, contents)]
    raw = b"".join(Z.stored_zip(members, lambda index: iter((contents[index],))))
    packet = {"artifactId": 1001, "bytes": len(raw), "sha256": Q.digest(raw)}
    return contents, members, raw, packet


def inputs_fixture():
    return {"seed": {"files": {name: "1" * 64 for name in Q.seed.INPUTS}, "allowlistSha256": "2" * 64,
        "artifacts": 2, "components": 1, "policy": Q.seed.policy()},
        "provider": {name: "3" * 64 for name in Q.PROVIDER_INPUTS}}


def version_fixture(literal_path, compression, role):
    """Independent synthetic expectation for the fixed supplier salt/crossOS policy."""
    parts = [literal_path, compression]
    if role == "windows-x64":
        parts.append("windows-only")
    return hashlib.sha256("|".join([*parts, "1.0"]).encode("utf-8")).hexdigest()


class MetadataFixture:
    """Only fixture builders. No previously authored test methods are reused."""

    def __init__(self):
        self.declaration, histories = F.stage2(F.stage1())
        self.authority_at = F.START + 200
        self.entry = self.declaration["qualifications"][0]
        self.history = histories[0]
        _contents, self.members, self.zip, self.packet = zip_fixture()
        self.entry["packet"] = self.packet
        self.inputs = inputs_fixture()
        source = self.declaration["stage1"]["reviewed"]
        self.final = {"source": copy.deepcopy(source), "productive": {"afterSaveSha256": "4" * 64,
            "probeSha256": "5" * 64, "compatibilityInputsSha256": Q.source_compatibility.envelope_digest(
                Q.source_compatibility.envelope(source, self.inputs))}}
        provider = {"schema": 1, "scope": "INITIAL_PRODUCTIVE_CACHE_COMPATIBILITY_V1",
            "action": Q.cache._provider(), "key": Q.cache.cache_key("desktop", "linux-x64",
                self.inputs["seed"]["allowlistSha256"], self.inputs["seed"]["files"][Q.seed.INPUTS[1]]),
            "literalPath": "/runner/temp/p2pkit-dependency-seed-desktop-linux-x64/restore-home/caches/modules-2/files-2.1",
            "compression": "zstd-without-long",
            "cacheEntry": {"id": 9001, "bytes": 2048, "createdAt": F.DONE1 - 1},
            "refs": {"savedRef": S.SOURCE_REF, "headRef": S.SOURCE_REF, "baseRef": "refs/heads/main",
                "mergeRef": "refs/pull/999/merge"}, "afterSaveSha256": "4" * 64, "probeSha256": "5" * 64,
            "nativeRecordSha256": "7" * 64, "resolverRecordSha256": "8" * 64}
        provider["cacheVersion"] = version_fixture(provider["literalPath"], provider["compression"], "linux-x64")
        self.provider = provider
        common = {"schema": 1, "repository": I.REPOSITORY, "source": self.declaration["stage1"]["reviewed"],
            **{name: self.entry[name] for name in ("selection", "runId", "runAttempt", "completedAt", "packet")}}
        history = {"comment": self.history.comment_raw, "observation": self.history.observation_raw,
            "basePolicyEntry": self.history.base_policy_entry, "ancestry": self.history.ancestry_raw,
            "candidatePolicyEntry": self.history.candidate_policy_entry, "candidatePolicy": self.history.candidate_policy_raw,
            "match": self.history.expected.record}
        self.documents = {"inventory": {**common, "scope": Q.INVENTORY_SCOPE, "sourceRef": S.SOURCE_REF,
            "members": self.members, "history": {name: encoded64(raw) for name, raw in history.items()},
            "productiveEvidence": {"finalManifestSha256": self.members[1]["sha256"],
                "tailManifestSha256": self.members[3]["sha256"], "upload": encoded64(b"SYNTHETIC_NOT_U"),
                "after": encoded64(b"SYNTHETIC_NOT_A")}}}
        target = {"head": self.declaration["reviewed"], "merge": self.declaration["firstPullRequest"]["merge"]}
        self.documents["compatibility"] = {**common, "scope": Q.COMPATIBILITY_SCOPE, "target": target,
            "inventoryBodySha256": self.body_hash("inventory"), "inputs": self.inputs, "provider": provider}
        self.documents["review"] = {**common, "scope": Q.REVIEW_SCOPE, "target": target,
            "inventoryBodySha256": self.body_hash("inventory"),
            "compatibilityBodySha256": self.body_hash("compatibility"), "decision": Q.REVIEW_DECISION,
            "inspection": {**{name: "9" * 64 for name in
                ("finalPlaintextSha256", "tailPlaintextSha256", "privateRecordSha256")},
                **{name: "PASS_ORIGINAL_PRIVATE_INSPECTION" for name in
                    ("originals", "source", "nativeRetirement", "provider", "resolver", "custody", "timing")}}}
        self.originals = {}
        self.reseal()

    def body(self, name):
        return I.encoded(self.documents[name]).removesuffix(b"\n")

    def body_hash(self, name):
        return Q.digest(self.body(name))

    def reseal(self):
        self.documents["compatibility"]["inventoryBodySha256"] = self.body_hash("inventory")
        self.documents["review"]["inventoryBodySha256"] = self.body_hash("inventory")
        self.documents["review"]["compatibilityBodySha256"] = self.body_hash("compatibility")
        for number, name in enumerate(("inventory", "compatibility", "review"), 1):
            raw, identifier, created = self.body(name), 9000 + number, self.entry["completedAt"] + number
            self.entry[name] = {"commentId": identifier, "bytes": len(raw), "sha256": Q.digest(raw)}
            self.originals[name] = I.encoded({"id": identifier, "user": dict(F.OWNER), "performed_via_github_app": None,
                "created_at": F.utc(created), "updated_at": F.utc(created), "body": raw.decode("ascii"),
                "url": "https://api.github.com" + Q.references.metadata_path(self.entry[name]),
                "issue_url": Q.references.API + "/issues/437", "html_url": "https://github.com/" + I.REPOSITORY +
                    "/issues/437#issuecomment-" + str(identifier)})

    def metadata(self):
        return Q.public_metadata(self.originals, self.entry, self.declaration, self.authority_at)


def job_fixture(entry, source):
    job = {"id": 5001, "run_id": int(entry["runId"]), "run_attempt": int(entry["runAttempt"]),
        "name": "populate", "head_sha": source["commit"], "head_branch": S.SOURCE_REF.removeprefix("refs/heads/"),
        "status": "completed", "conclusion": "success", "started_at": F.utc(F.START), "completed_at": F.utc(F.DONE1),
        "url": Q.references.API + "/actions/jobs/5001", "run_url": Q.references.API + "/actions/runs/" + entry["runId"],
        "labels": ["ubuntu-latest"], "runner_id": 5002, "runner_name": "SYNTHETIC runner not a real host",
        "runner_group_id": 0, "runner_group_name": "GitHub Actions", "steps": [
            {"number": number, "name": name, "status": "completed", "conclusion": "success",
                "started_at": F.utc(F.START + number * 10), "completed_at": F.utc(F.START + number * 10 + 5)}
            for number, name in enumerate(Q.STEP_NAMES, 1)]}
    attempt = {"id": int(entry["runId"]), "run_attempt": int(entry["runAttempt"]), "head_sha": source["commit"],
        "head_branch": job["head_branch"], "path": S.bootstrap.WORKFLOW, "event": "workflow_dispatch",
        "status": "completed", "conclusion": "success", "pull_requests": [],
        "repository": {"full_name": I.REPOSITORY}, "head_repository": {"full_name": I.REPOSITORY}}
    return attempt, {"total_count": 1, "jobs": [job]}


class ConnectedFixture(MetadataFixture):
    """One complete synthetic H1 packet joined through the REAL maintained codec.

    Unlike individual helper fixtures, this supplies actual complete stored ZIP
    bytes with synthetic ciphertext payloads, canonical pending U/A bytes, the
    original public-policy/history model and the full job row. No predicate is
    replaced, source pin changed, cryptographic acceptance invented or test
    method reused. Everything remains supplied DATA, not a hosted qualification.
    """

    def __init__(self, selection="desktop-linux-x64"):
        super().__init__()
        profile, role, _system, _arch = S.bootstrap.selection(selection)
        self.delivery = d = DF.qualification_fixture(role, profile=profile)
        self.entry = next(row for row in self.declaration["qualifications"] if row["selection"] == selection)
        self.entry.update(runId=d["final"]["github"]["runId"], runAttempt=d["final"]["github"]["runAttempt"],
            completedAt=S.joint.timestamp(d["job"]["completed_at"]))
        self.authority_at, self.now = self.entry["completedAt"] + 100, self.entry["completedAt"] + 120
        prior = F.stage1()
        prior["expiresAt"] = DF.MODEL_EPOCH + 6000
        next(row for row in prior["bootstrap"] if row["selection"] == selection).update(
            runId=self.entry["runId"], runAttempt=self.entry["runAttempt"])
        original = F.comment(prior, 8001, F.START - 60)
        observed = F.observation1(prior, selection)
        observed["firstUseAt"] = d["proposal"]["firstUseAt"]
        original_raw, observed_raw = I.encoded(original), I.encoded(observed)
        matched = S.match_bootstrap(comment_raw=original_raw, comment_id=8001, body_sha256=F.body_hash(original),
            observation_raw=observed_raw, now=self.entry["completedAt"], **F.policy_inputs())
        history = self.history = S.BootstrapHistory(original_raw, observed_raw, b"",
            S.BASE["commit"].encode("ascii") + b"\n", F.ENTRY, F.POLICY, self.entry["completedAt"], matched)
        self.declaration["stage1"] = {"commentId": 8001, "bodySha256": F.body_hash(original), "reviewed": prior["reviewed"]}
        self.declaration["environment"] = prior["environment"]
        historical = I.parse(matched.record, S.LIMIT)
        policy, _public_armor = I._policy(F.POLICY, self.now)
        final = d["final"]
        final["initialRecipient"].update({name: historical[name] for name in
            ("authority", "environment", "originalBase", "reviewed", "firstUseAt", "notBefore", "expiresAt")})
        final["initialRecipient"]["matchSha256"] = Q.digest(matched.record)
        final["policy"] = {**historical["policy"], "fingerprint": policy["recipient"]["fingerprint"],
            "keySha256": policy["recipient"]["sha256"], "expiresAt": policy["expiresAt"], "retentionDays": 14}
        # Only public metadata is joined. Encryption subkey/ciphertext below
        # remain explicitly modeled, never a GPG recipient acceptance claim.
        final["recipient"].update(fingerprint=policy["recipient"]["fingerprint"],
            keySha256=policy["recipient"]["sha256"], expiresAt=policy["expiresAt"])
        final["productive"]["compatibilityInputsSha256"] = Q.source_compatibility.envelope_digest(
            Q.source_compatibility.envelope(final["source"], self.inputs))
        self.ciphertexts = (b"SYNTHETIC_FINAL_PACKET_BYTES_NOT_ENCRYPTED", b"SYNTHETIC_TAIL_PACKET_BYTES_NOT_ENCRYPTED")
        final["artifact"].update(size=len(self.ciphertexts[0]), sha256=Q.digest(self.ciphertexts[0]))
        final_raw = d["final_manifest_raw"] = I.encoded(final)
        d["deadline"]["manifestSha256"] = Q.digest(final_raw)
        predecessors = d["pending"]["predecessors"]
        predecessors["deadlineSha256"] = Q.digest(I.encoded(d["deadline"]))
        tail = DF.TD.public_inputs(DF.TD.manifest_inputs(final_raw, predecessors, d["tail"]["cut"]))
        tail.update(scope=DF.TD.SCOPE, recipient=copy.deepcopy(final["recipient"]),
            artifact={"name": "evidence.tar.gz.gpg", "size": len(self.ciphertexts[1]), "sha256": Q.digest(self.ciphertexts[1])},
            testAcceptance="NOT_PERFORMED", productiveAuthority=False, cacheAuthority=False,
            budgetAcceptance="NOT_ADMITTED", exportSaveAuthority=False)
        d["tail"], d["tail_manifest_raw"] = tail, I.encoded(tail)
        self.contents = (self.ciphertexts[0], final_raw, self.ciphertexts[1], d["tail_manifest_raw"])
        self.members = [{"name": name, "bytes": len(raw), "sha256": Q.digest(raw)}
            for name, raw in zip(Z.MEMBERS, self.contents)]
        self.zip = b"".join(Z.stored_zip(self.members, lambda index: iter((self.contents[index],))))
        self.packet = {"artifactId": int(d["upload"]["artifact"]["id"]), "bytes": len(self.zip), "sha256": Q.digest(self.zip)}
        self.entry["packet"] = self.packet
        pending = d["pending"]
        pending["originals"]["matchSha256"] = Q.digest(matched.record)
        pending.update(deadline=copy.deepcopy(d["deadline"]), predecessors=copy.deepcopy(predecessors), members=self.members,
            manifests={"finalSha256": Q.digest(final_raw), "tailSha256": Q.digest(d["tail_manifest_raw"])},
            totalBytes=sum(row["bytes"] for row in self.members), zipBytes=len(self.zip))
        pending_raw = d["pending_raw"] = DF.TD.encode_pending(pending)
        for value in (d["upload"], d["after"]):
            value.update(deadline=copy.deepcopy(d["deadline"]), originals=copy.deepcopy(pending["originals"]),
                members=copy.deepcopy(self.members), beforeSha256=Q.digest(pending_raw), policyNotBefore=policy["notBefore"],
                policyExpiresAt=policy["expiresAt"], authorityNotBefore=historical["notBefore"],
                authorityExpiresAt=historical["expiresAt"])
            value["artifact"].update(zipBytes=len(self.zip), zipSha256=Q.digest(self.zip))
        d["after"]["artifact"]["serviceDigest"] = "sha256:" + Q.digest(self.zip)
        d["upload_raw"] = DF.D.encoded(DF.D.pending_value(d["upload"], "finish"), DF.D.PENDING_LIMIT)
        d["after"]["uploadSha256"] = Q.digest(d["upload_raw"])
        d["after_raw"] = DF.D.encoded(DF.D.pending_value(d["after"], "after"), DF.D.PENDING_LIMIT)
        d["members"] = self.members
        self.final = final
        self.provider.update(key=Q.cache.cache_key(profile, role, self.inputs["seed"]["allowlistSha256"],
            self.inputs["seed"]["files"][Q.seed.INPUTS[1]]), literalPath=(
                "D:\\a\\_temp\\p2pkit-dependency-seed-" + profile + "-" + role +
                "\\restore-home\\caches\\modules-2\\files-2.1" if role == "windows-x64" else
                "/runner/temp/p2pkit-dependency-seed-" + profile + "-" + role +
                "/restore-home/caches/modules-2/files-2.1"),
            afterSaveSha256=final["productive"]["afterSaveSha256"], probeSha256=final["productive"]["probeSha256"])
        self.provider["cacheEntry"]["createdAt"] = self.entry["completedAt"] - 1
        self.provider.update(cacheVersion=version_fixture(self.provider["literalPath"], self.provider["compression"], role),
            nativeRecordSha256=final["copy"]["groups"][24]["map"]["sha256"],
            resolverRecordSha256=final["copy"]["groups"][26]["map"]["sha256"])
        self.documents["review"]["inspection"]["privateRecordSha256"] = final["copy"]["index"]["sha256"]
        self.documents["inventory"].update(members=self.members, history={name: encoded64(raw) for name, raw in (
            ("comment", history.comment_raw), ("observation", history.observation_raw),
            ("basePolicyEntry", history.base_policy_entry), ("ancestry", history.ancestry_raw),
            ("candidatePolicyEntry", history.candidate_policy_entry), ("candidatePolicy", history.candidate_policy_raw),
            ("match", history.expected.record))}, productiveEvidence={"finalManifestSha256": Q.digest(final_raw),
                "tailManifestSha256": Q.digest(d["tail_manifest_raw"]), "upload": encoded64(d["upload_raw"]),
                "after": encoded64(d["after_raw"])})
        for document in self.documents.values():
            document.update(source=prior["reviewed"], **{name: self.entry[name] for name in
                ("selection", "runId", "runAttempt", "completedAt", "packet")})
        self.reseal()
        self.attempt = {"id": int(self.entry["runId"]), "run_attempt": int(self.entry["runAttempt"]),
            "head_sha": final["source"]["commit"], "head_branch": d["job"]["head_branch"], "path": S.bootstrap.WORKFLOW,
            "event": "workflow_dispatch", "status": "completed", "conclusion": "success", "pull_requests": [],
            "repository": {"full_name": I.REPOSITORY}, "head_repository": {"full_name": I.REPOSITORY}}
        self.jobs = {"total_count": 1, "jobs": [copy.deepcopy(d["job"])]}
        artifact = d["after"]["artifact"]
        url = Q.references.API + "/actions/artifacts/" + str(self.packet["artifactId"])
        self.artifact = {"id": self.packet["artifactId"], "name": artifact["name"], "url": url,
            "archive_download_url": url + "/zip", "size_in_bytes": len(self.zip), "digest": artifact["serviceDigest"],
            "expired": False, "created_at": artifact["createdAt"], "expires_at": artifact["expiresAt"],
            "workflow_run": {"id": int(self.entry["runId"]), "head_sha": final["source"]["commit"],
                "head_branch": d["job"]["head_branch"]}}
        self.cache_row = {"id": self.provider["cacheEntry"]["id"], "key": self.provider["key"], "ref": S.SOURCE_REF,
            "version": self.provider["cacheVersion"], "size_in_bytes": self.provider["cacheEntry"]["bytes"],
            "created_at": F.utc(self.provider["cacheEntry"]["createdAt"])}

    def qualify(self, **changes):
        manifests = Q.read_stored_zip(io.BytesIO(self.zip), self.members, self.packet, lambda: None)
        arguments = {"originals": self.originals, "entry": self.entry, "declaration": self.declaration,
            "authority_created_at": self.authority_at, "attempt_raw": I.encoded(self.attempt),
            "jobs_raw": I.encoded(self.jobs), "job_raw": self.delivery["job_raw"],
            "job_date": self.delivery["service_date"], "artifact_raw": I.encoded(self.artifact),
            "inventory_pages": ((Q.references.inventory_path(self.entry["runId"], 1),
                I.encoded({"total_count": 1, "artifacts": [self.artifact]})),),
            "cache_pages": ((Q.cache_inventory_path(self.provider, 1),
                I.encoded({"total_count": 1, "actions_caches": [self.cache_row]})),),
            "manifests": manifests, "current_inputs": self.inputs, "now": self.now}
        return Q.qualify(**{**arguments, **changes})


class ProductiveDataControls(unittest.TestCase):
    def test_complete_fixed_zip_reads_all_members_and_only_returns_manifest_bytes(self):
        contents, members, raw, packet = zip_fixture()
        reader, checks = io.BytesIO(raw), []
        returned = Q.read_stored_zip(reader, members, packet, lambda: checks.append(True))
        self.assertEqual(returned, {Z.MEMBERS[1]: contents[1], Z.MEMBERS[3]: contents[3]})
        self.assertEqual(reader.tell(), len(raw))
        self.assertGreater(len(checks), 20)

    def test_partial_reads_are_completed_without_dropping_or_repeating_bytes(self):
        class Partial(io.BytesIO):
            def read(self, count):
                return super().read(min(count, 3))
        contents, members, raw, packet = zip_fixture()
        returned = Q.read_stored_zip(Partial(raw), members, packet, lambda: None)
        self.assertEqual(returned, {Z.MEMBERS[1]: contents[1], Z.MEMBERS[3]: contents[3]})

    def test_short_or_extra_zip_bytes_fail(self):
        _contents, members, raw, packet = zip_fixture()
        for value, code in ((raw[:-1], "TRUNCATED"), (raw + b"x", "TRAILING")):
            with self.subTest(code=code), self.assertRaisesRegex(I.AdmissionError, code):
                Q.read_stored_zip(io.BytesIO(value), members, packet, lambda: None)

    def test_bad_local_crc_central_and_end_framing_are_not_masked_by_rehash(self):
        _contents, members, raw, packet = zip_fixture()
        offsets = (0, 30 + len(Z.MEMBERS[0]) + members[0]["bytes"] + 4,
            sum(30 + len(row["name"]) + row["bytes"] + 16 for row in members), len(raw) - 2)
        for offset in offsets:
            changed = raw[:offset] + bytes((raw[offset] ^ 1,)) + raw[offset + 1:]
            with self.subTest(offset=offset), self.assertRaises(I.AdmissionError):
                Q.read_stored_zip(io.BytesIO(changed), members, {**packet, "sha256": Q.digest(changed)}, lambda: None)

    def test_whole_zip_and_member_hashes_are_independent(self):
        _contents, members, raw, packet = zip_fixture()
        with self.assertRaisesRegex(I.AdmissionError, "WHOLE_ZIP_DIGEST"):
            Q.read_stored_zip(io.BytesIO(raw), members, {**packet, "sha256": "0" * 64}, lambda: None)
        changed = copy.deepcopy(members)
        changed[0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(I.AdmissionError, "ZIP_MEMBER_DIGEST"):
            Q.read_stored_zip(io.BytesIO(raw), changed, packet, lambda: None)

    def test_member_order_whole_bound_and_typed_packet_are_checked_before_read(self):
        _contents, members, raw, packet = zip_fixture()
        for changed in (list(reversed(members)), [{**members[0], "bytes": Z.MAX_ZIP_BYTES}, *members[1:]]):
            with self.assertRaises(Z.ZipError):
                Q.read_stored_zip(io.BytesIO(raw), changed, packet, lambda: None)
        for bad in (True, 0, packet["bytes"] + 1):
            with self.assertRaises(I.AdmissionError):
                Q.read_stored_zip(io.BytesIO(raw), members, {**packet, "bytes": bad}, lambda: None)

    def test_reader_cancellation_and_no_progress_are_not_retried(self):
        _contents, members, raw, packet = zip_fixture()
        original = KeyboardInterrupt("SYNTHETIC_CANCEL")
        def cancelled(): raise original
        with self.assertRaises(KeyboardInterrupt) as caught:
            Q.read_stored_zip(io.BytesIO(raw), members, packet, cancelled)
        self.assertIs(caught.exception, original)
        class Empty:
            calls = 0
            def read(self, _count):
                self.calls += 1
                return b""
        reader = Empty()
        with self.assertRaisesRegex(I.AdmissionError, "TRUNCATED"):
            Q.read_stored_zip(reader, members, packet, lambda: None)
        self.assertEqual(reader.calls, 1)

    def test_exact_metadata_is_only_supplied_reference_data(self):
        f = MetadataFixture()
        inventory, compatible, review, bodies = f.metadata()
        self.assertEqual(inventory["packet"], f.packet)
        self.assertEqual(review["decision"], Q.REVIEW_DECISION)
        self.assertEqual(tuple(name for name, _raw in bodies), ("inventory", "compatibility", "review"))
        self.assertIs(type(compatible), dict)

    def test_rehashed_wrong_scope_source_merge_or_incomplete_inspection_fails(self):
        mutations = (("inventory", lambda value: value.update(scope="ENCRYPTED_PRIVATE_INITIAL_RECIPIENT_EVIDENCE")),
            ("compatibility", lambda value: value["source"].update(commit=F.H2)),
            ("review", lambda value: value["target"]["merge"].update(commit=F.H1)),
            ("review", lambda value: value.update(decision="APPROVE_SOURCE_ONLY")),
            ("review", lambda value: value["inspection"].update(provider="NOT_EXECUTED")))
        for name, mutate in mutations:
            f = MetadataFixture()
            f.documents[name] = copy.deepcopy(f.documents[name])
            mutate(f.documents[name]); f.reseal()
            with self.subTest(name=name), self.assertRaises(I.AdmissionError): f.metadata()

    def test_owner_metadata_cross_hashes_cannot_be_replaced(self):
        f = MetadataFixture()
        f.documents["review"]["inventoryBodySha256"] = "0" * 64
        raw = f.body("review")
        comment = I.parse(f.originals["review"], Q.references.COMMENT_LIMIT)
        comment["body"] = raw.decode("ascii")
        f.originals["review"] = I.encoded(comment)
        f.entry["review"].update(bytes=len(raw), sha256=Q.digest(raw))
        with self.assertRaisesRegex(I.AdmissionError, "REVIEW_INVENTORY"): f.metadata()

    def test_editing_owner_or_time_fails_even_with_exact_body_hash(self):
        for mutate in (lambda value: value["user"].update(login="SYNTHETIC_OTHER"),
            lambda value: value.update(updated_at=F.utc(F.DONE1 + 10)),
            lambda value: value.update(created_at=F.utc(F.START + 200), updated_at=F.utc(F.START + 200))):
            f = MetadataFixture()
            value = I.parse(f.originals["review"], Q.references.COMMENT_LIMIT)
            mutate(value); f.originals["review"] = I.encoded(value)
            with self.assertRaises(I.AdmissionError): f.metadata()

    def test_original_history_is_rechecked_at_h1_completion_not_current_authority_time(self):
        f = MetadataFixture()
        inventory, _compatible, _review, _bodies = f.metadata()
        result = Q.historical_originals(inventory, f.entry, f.declaration)
        self.assertEqual(result.expected.record, f.history.expected.record)
        self.assertGreater(F.NOW, F.stage1()["expiresAt"])
        self.assertLess(result.completed_at, F.stage1()["expiresAt"])

    def test_missing_noncanonical_or_changed_original_history_refuses(self):
        for changed in (lambda value: value.pop("ancestry"),
            lambda value: value.update(basePolicyEntry=encoded64(b"SYNTHETIC_POLICY_ALREADY_PRESENT")),
            lambda value: value.update(candidatePolicy=value["candidatePolicy"] + "\n")):
            f = MetadataFixture()
            inventory = copy.deepcopy(f.documents["inventory"])
            changed(inventory["history"])
            with self.assertRaises(I.AdmissionError): Q.historical_originals(inventory, f.entry, f.declaration)

    def test_completed_job_requires_real_completed_attempt_and_six_ordered_steps_data(self):
        f = MetadataFixture(); source = f.declaration["stage1"]["reviewed"]
        attempt, jobs = job_fixture(f.entry, source)
        self.assertEqual(Q.completed_job(I.encoded(attempt), I.encoded(jobs), f.entry, source), jobs["jobs"][0])

    def test_attempt_head_branch_event_and_partial_job_list_refuse(self):
        f = MetadataFixture(); source = f.declaration["stage1"]["reviewed"]
        for field, value in (("head_sha", F.H2), ("event", "pull_request"), ("status", "in_progress"),
                ("head_branch", "main"), ("run_attempt", True)):
            attempt, jobs = job_fixture(f.entry, source); attempt[field] = value
            with self.assertRaises(I.AdmissionError): Q.completed_job(I.encoded(attempt), I.encoded(jobs), f.entry, source)
        attempt, jobs = job_fixture(f.entry, source); jobs["total_count"] = 2
        with self.assertRaisesRegex(I.AdmissionError, "JOBS_COMPLETE"):
            Q.completed_job(I.encoded(attempt), I.encoded(jobs), f.entry, source)

    def test_failed_duplicate_or_nonadjacent_terminal_steps_cannot_qualify(self):
        f = MetadataFixture(); source = f.declaration["stage1"]["reviewed"]
        for mutate in (lambda steps: steps[-1].update(conclusion="failure"),
            lambda steps: steps.append(dict(steps[-1])), lambda steps: steps[-1].update(number=9),
            lambda steps: steps.pop(2), lambda steps: steps[-1].update(started_at=F.utc(F.DONE1 + 1))):
            attempt, jobs = job_fixture(f.entry, source); mutate(jobs["jobs"][0]["steps"])
            with self.assertRaises(I.AdmissionError): Q.completed_job(I.encoded(attempt), I.encoded(jobs), f.entry, source)

    def test_exact_source_inputs_and_original_provider_are_not_restore_acceptance(self):
        f = MetadataFixture()
        inventory, compatible, _review, _bodies = f.metadata()
        self.assertEqual(Q.compatibility(compatible, inventory, f.final, f.declaration, f.inputs), f.provider)

    def test_h1_digest_binds_the_full_original_envelope_and_its_required_lf(self):
        f = MetadataFixture()
        inventory, compatible, _review, _bodies = f.metadata()
        raw = Q.source_compatibility.encoded(Q.source_compatibility.envelope(f.final["source"], f.inputs))
        self.assertEqual(f.final["productive"]["compatibilityInputsSha256"], Q.digest(raw))
        for checksum in (Q.digest(raw[:-1]), "0" * 64):
            final = copy.deepcopy(f.final); final["productive"]["compatibilityInputsSha256"] = checksum
            with self.assertRaisesRegex(I.AdmissionError, "ORIGINAL_COMPATIBILITY_ENVELOPE"):
                Q.compatibility(compatible, inventory, final, f.declaration, f.inputs)

    def test_h2_merge_identity_cannot_relabel_the_original_h1_envelope(self):
        f = MetadataFixture()
        inventory, compatible, _review, _bodies = f.metadata()
        final = copy.deepcopy(f.final); final["source"] = f.declaration["firstPullRequest"]["merge"]
        final["productive"]["compatibilityInputsSha256"] = Q.source_compatibility.envelope_digest(
            Q.source_compatibility.envelope(final["source"], f.inputs))
        with self.assertRaisesRegex(I.AdmissionError, "COMPATIBILITY_H1_SOURCE"):
            Q.compatibility(compatible, inventory, final, f.declaration, f.inputs)

    def test_shared_closed135_inventory_refuses_old_subset_and_extra_path(self):
        f = MetadataFixture()
        self.assertIs(Q.PROVIDER_INPUTS, Q.source_compatibility.PROVIDER_INPUTS)
        self.assertEqual(len(Q.PROVIDER_INPUTS), 123)
        self.assertEqual(Q.PROVIDER_INPUTS[-1], "scripts/hosted_jvm_library_custody.py")
        for change in (lambda value: value["provider"].pop(Q.PROVIDER_INPUTS[-1]),
                lambda value: value["provider"].pop("scripts/run-hosted-recipient-routing.py"),
                lambda value: value["provider"].update({"scripts/extra.py": "a" * 64}),
                lambda value: value["seed"].update(components=2049)):
            value = copy.deepcopy(f.inputs); change(value)
            with self.assertRaises(I.AdmissionError): Q.checked_inputs(value)

    def test_same_key_cannot_replace_source_provider_ref_or_original_save(self):
        for mutate in (lambda value: value["inputs"]["provider"].update({Q.PROVIDER_INPUTS[0]: "a" * 64}),
            lambda value: value["provider"]["refs"].update(savedRef="refs/heads/main"),
            lambda value: value["provider"].update(afterSaveSha256="a" * 64),
            lambda value: value["provider"]["action"].update(enableCrossOsArchive=True),
            lambda value: value["provider"].update(compression="guessed-from-host")):
            f = MetadataFixture()
            inventory, compatible, _review, _bodies = f.metadata(); mutate(compatible)
            with self.assertRaises(I.AdmissionError):
                Q.compatibility(compatible, inventory, f.final, f.declaration, f.inputs)

    def test_native_provider_paths_are_literal_distinct_posix_and_windows_data(self):
        f = MetadataFixture()
        Q._path(f.provider["literalPath"], "desktop", "linux-x64")
        path = r"D:\a\_temp\p2pkit-dependency-seed-desktop-windows-x64\restore-home\caches\modules-2\files-2.1"
        self.assertEqual(Q._path(path, "desktop", "windows-x64"), path)
        for bad in (path.replace("_temp", "*"), path.replace("_temp", ".."), path.replace("_temp", "_temp."),
                    path.replace("D:", r"\\server\share")):
            with self.assertRaises(I.AdmissionError): Q._path(bad, "desktop", "windows-x64")

    def test_complete_cache_inventory_binds_original_id_version_size_and_ref(self):
        f = MetadataFixture()
        selected = {"id": 9001, "ref": S.SOURCE_REF, "key": f.provider["key"], "version": f.provider["cacheVersion"],
            "size_in_bytes": 2048, "created_at": F.utc(F.DONE1 - 1)}
        rows = [{**selected, "id": index, "version": "0" * 64} for index in range(1, 101)] + [selected]
        pages = ((Q.cache_inventory_path(f.provider, 1), I.encoded({"total_count": 101, "actions_caches": rows[:100]})),
            (Q.cache_inventory_path(f.provider, 2), I.encoded({"total_count": 101, "actions_caches": rows[100:]})))
        self.assertEqual(Q.cache_inventory(pages, f.provider), selected)
        with self.assertRaises(I.AdmissionError): Q.cache_inventory(pages[:1], f.provider)
        for field, bad in (("version", "0" * 64), ("ref", "refs/heads/main"), ("size_in_bytes", True),
                ("created_at", F.utc(F.DONE1))):
            changed = ((pages[0][0], pages[0][1]), (pages[1][0], I.encoded({"total_count": 101,
                "actions_caches": [{**selected, field: bad}]})))
            with self.assertRaises(I.AdmissionError): Q.cache_inventory(changed, f.provider)

    def test_only_attainable_compressions_bind_literal_path_and_windows_version(self):
        self.assertEqual(Q.COMPRESSIONS, ("gzip", "zstd-without-long"))
        for selection in ("desktop-linux-x64", "desktop-windows-x64"):
            f = ConnectedFixture(selection)
            role = S.bootstrap.selection(selection)[1]
            inventory, compatible, _review, _bodies = f.metadata()
            for compression in Q.COMPRESSIONS:
                value = copy.deepcopy(compatible)
                provider = value["provider"]
                provider.update(compression=compression,
                    cacheVersion=version_fixture(provider["literalPath"], compression, role))
                self.assertEqual(Q.compatibility(value, inventory, f.final, f.declaration, f.inputs), provider)
                for wrong in ("0" * 64, version_fixture(provider["literalPath"] + "/other", compression, role)):
                    provider["cacheVersion"] = wrong
                    with self.assertRaisesRegex(I.AdmissionError, "PROVIDER_CACHE_VERSION"):
                        Q.compatibility(value, inventory, f.final, f.declaration, f.inputs)
            value = copy.deepcopy(compatible); value["provider"]["compression"] = "zstd"
            with self.assertRaisesRegex(I.AdmissionError, "PROVIDER_COMPRESSION"):
                Q.compatibility(value, inventory, f.final, f.declaration, f.inputs)
            if role == "windows-x64":
                value = copy.deepcopy(compatible)
                value["provider"]["cacheVersion"] = version_fixture(value["provider"]["literalPath"],
                    value["provider"]["compression"], "linux-x64")
                with self.assertRaisesRegex(I.AdmissionError, "PROVIDER_CACHE_VERSION"):
                    Q.compatibility(value, inventory, f.final, f.declaration, f.inputs)

    def test_unique_service_tuple_precedes_original_id_even_across_pages(self):
        f = MetadataFixture()
        selected = {"id": f.provider["cacheEntry"]["id"], "key": f.provider["key"], "ref": S.SOURCE_REF,
            "version": f.provider["cacheVersion"], "size_in_bytes": f.provider["cacheEntry"]["bytes"],
            "created_at": F.utc(f.provider["cacheEntry"]["createdAt"])}
        rows = [{**selected, "id": index, "version": "0" * 64} for index in range(1, 100)] + [selected]
        pages = ((Q.cache_inventory_path(f.provider, 1), I.encoded({"total_count": 101, "actions_caches": rows})),
            (Q.cache_inventory_path(f.provider, 2), I.encoded({"total_count": 101,
                "actions_caches": [{**selected, "id": 9002}]})))
        with self.assertRaisesRegex(I.AdmissionError, "ORIGINAL_CACHE_ABSENT_OR_AMBIGUOUS"):
            Q.cache_inventory(pages, f.provider)
        one_wrong_id = ((pages[0][0], I.encoded({"total_count": 1,
            "actions_caches": [{**selected, "id": 9002}]})),)
        with self.assertRaisesRegex(I.AdmissionError, "ORIGINAL_CACHE_CHANGED"):
            Q.cache_inventory(one_wrong_id, f.provider)

    def test_cache_inventory_never_follows_supplied_paths_or_accepts_duplicate_ids(self):
        f = MetadataFixture()
        raw = I.encoded({"total_count": 2, "actions_caches": [{"id": 9001}, {"id": 9001}]})
        with self.assertRaisesRegex(I.AdmissionError, "DUPLICATE_CACHE_ENTRY"):
            Q.cache_inventory(((Q.cache_inventory_path(f.provider, 1), raw),), f.provider)
        with self.assertRaisesRegex(I.AdmissionError, "CACHE_PAGE_PATH"):
            Q.cache_inventory((("https://example.invalid/cache", raw),), f.provider)
        with self.assertRaisesRegex(I.AdmissionError, "CACHE_PAGE_ORIGINAL"):
            Q.cache_inventory(((Q.cache_inventory_path(f.provider, 1), bytearray(raw)),), f.provider)

    def test_noncanonical_base64_and_non_builtin_input_do_not_become_originals(self):
        for value in ("YQ==\n", "YQ", b"YQ==", "YQ===", "", "é"):
            with self.assertRaises(I.AdmissionError): Q.original_bytes(value, 100)
        self.assertEqual(Q.original_bytes("", 1, empty=True), b"")
        with self.assertRaises(I.AdmissionError): Q.canonical(bytearray(b"{}"))


class ConnectedProductiveControls(unittest.TestCase):
    def test_connected_fixture_keeps_policy_relative_calendar_and_original_budgets(self):
        epoch = DF.MODEL_EPOCH
        self.assertEqual(epoch, F.START + 51_200)
        f = ConnectedFixture()
        d = f.delivery
        self.assertIs(type(f.qualify()), Q.ProductiveQualification)
        self.assertEqual((d["proposal"]["firstUseAt"], f.entry["completedAt"], d["service_date"]),
            (epoch + 100, epoch + 5131, epoch + 5140))
        self.assertEqual((f.authority_at, f.now), (epoch + 5231, epoch + 5251))
        self.assertEqual((f.final["initialRecipient"]["notBefore"], f.final["initialRecipient"]["expiresAt"]),
            (F.START, epoch + 6000))
        policy, _public_armor = I._policy(F.POLICY, f.now)
        self.assertEqual((policy["notBefore"], policy["expiresAt"]), (F.START, F.END))
        self.assertEqual(f.final["policy"]["expiresAt"], F.END)
        for row in (d["upload"], d["after"]):
            self.assertEqual((row["policyNotBefore"], row["policyExpiresAt"]), (F.START, F.END))
        basis = d["proposal"]["serviceTimeBasis"]
        self.assertEqual(basis["service"]["jobStartedAt"], F.utc(epoch))
        self.assertEqual((basis["serviceAgeSeconds"], basis["chargedAgeNs"], basis["jobStartBasisNs"]),
            (100, 166 * DF.NS, 834 * DF.NS))
        self.assertEqual(d["proposal"]["proposedJobEndNs"] - basis["jobStartBasisNs"], 5400 * DF.NS)
        artifact = d["after"]["artifact"]
        self.assertEqual(artifact["requestedRetentionDays"], 14)
        self.assertEqual(S.joint.timestamp(artifact["expiresAt"]) - S.joint.timestamp(artifact["createdAt"]), 14 * 86400)

    def test_stale_pre_renewal_delivery_epoch_is_refused_without_policy_override(self):
        epoch = DF.MODEL_EPOCH
        try:
            DF.MODEL_EPOCH = 1790000000
            with self.assertRaisesRegex(I.AdmissionError, "RECIPIENT_POLICY_VALIDITY"):
                ConnectedFixture()
        finally:
            DF.MODEL_EPOCH = epoch
        self.assertEqual(DF.MODEL_EPOCH, F.START + 51_200)

    def test_complete_real_codec_join_for_each_required_stage2_cohort_is_still_data_only(self):
        for selection in ("desktop-linux-x64", "desktop-windows-x64", "desktop-macos-arm64", "full-macos-arm64"):
            with self.subTest(selection=selection):
                f = ConnectedFixture(selection)
                result = f.qualify()
                self.assertIs(type(result), Q.ProductiveQualification)
                self.assertNotIsInstance(result, I.Admission)
                record = I.parse(result.record, Q.references.COMMENT_LIMIT)
                self.assertEqual(record["scope"], Q.QUALIFIED_SCOPE)
                self.assertEqual(record["selection"], selection)
                self.assertEqual(record["jobSha256"], Q.digest(f.delivery["job_raw"]))
                self.assertEqual(record["nativeAuthority"], "NOT_ESTABLISHED_BY_SUPPLIED_DATA")
                for field in ("ordinaryAcceptance", "h2ProviderAcceptance", "cryptoAcceptance"):
                    self.assertEqual(record[field], "NOT_PERFORMED")
                self.assertEqual(f.delivery["upload"]["artifact"]["id"], str(f.packet["artifactId"]))
                expected = Q.source_compatibility.envelope_digest(Q.source_compatibility.envelope(
                    f.final["source"], f.inputs))
                self.assertEqual(f.final["productive"]["compatibilityInputsSha256"], expected)
                self.assertEqual(f.delivery["tail"]["productive"]["compatibilityInputsSha256"], expected)

    def test_original_job_detail_cannot_be_substituted_after_complete_job_list_binding(self):
        f = ConnectedFixture()
        self.assertIs(type(f.qualify()), Q.ProductiveQualification)
        changed = copy.deepcopy(f.delivery["job"])
        changed["runner_name"] = "SYNTHETIC_REPLACEMENT"
        with self.assertRaisesRegex(I.AdmissionError, "ORIGINAL_JOB_DETAIL_CHANGED"):
            f.qualify(job_raw=I.encoded(changed))
        with self.assertRaisesRegex(I.AdmissionError, "ORIGINAL_JOB_DATE"):
            f.qualify(job_date=True)

    def test_complete_manifest_cannot_turn_f_wrapper_into_original_upload_pending_bytes(self):
        f = ConnectedFixture()
        self.assertIs(type(f.qualify()), Q.ProductiveQualification)
        f.documents["inventory"]["productiveEvidence"]["upload"] = encoded64(I.encoded({"pending": f.delivery["upload"]}))
        f.reseal()
        with self.assertRaisesRegex(DF.D.DeliveryError, "FIELDS"):
            f.qualify()

    def test_rehashed_current_packet_selector_cannot_replace_original_upload_id(self):
        f = ConnectedFixture()
        self.assertIs(type(f.qualify()), Q.ProductiveQualification)
        f.packet["artifactId"] += 1
        url = Q.references.API + "/actions/artifacts/" + str(f.packet["artifactId"])
        f.artifact.update(id=f.packet["artifactId"], url=url, archive_download_url=url + "/zip")
        f.reseal()
        with self.assertRaisesRegex(I.AdmissionError, "ORIGINAL_UPLOAD_PACKET"):
            f.qualify()

    def test_current_artifact_must_match_original_after_service_creation_and_expiry(self):
        for field, difference in (("created_at", 1), ("expires_at", -1)):
            f = ConnectedFixture()
            self.assertIs(type(f.qualify()), Q.ProductiveQualification)
            f.artifact[field] = F.utc(S.joint.timestamp(f.artifact[field]) + difference)
            with self.subTest(field=field), self.assertRaisesRegex(I.AdmissionError, "ORIGINAL_AFTER_ARTIFACT"):
                f.qualify()

    def test_complete_packet_does_not_replace_original_cache_inventory_or_version(self):
        f = ConnectedFixture()
        self.assertIs(type(f.qualify()), Q.ProductiveQualification)
        absent = ((Q.cache_inventory_path(f.provider, 1), I.encoded({"total_count": 0, "actions_caches": []})),)
        with self.assertRaisesRegex(I.AdmissionError, "ORIGINAL_CACHE_ABSENT"):
            f.qualify(cache_pages=absent)
        f.cache_row["version"] = "0" * 64
        with self.assertRaisesRegex(I.AdmissionError, "ORIGINAL_CACHE_ABSENT_OR_AMBIGUOUS"):
            f.qualify()

    def test_owner_inspection_binds_actual_productive_configuration_maps_and_copy_index(self):
        for field, code in (("nativeRecordSha256", "OWNER_ORIGINAL_PRODUCTIVE_MAP"),
                ("resolverRecordSha256", "OWNER_ORIGINAL_CONFIGURATION_MAP"),
                ("privateRecordSha256", "OWNER_ORIGINAL_PRIVATE_INDEX")):
            f = ConnectedFixture()
            self.assertIs(type(f.qualify()), Q.ProductiveQualification)
            target = f.documents["review"]["inspection"] if field == "privateRecordSha256" else f.provider
            target[field] = "0" * 64
            f.reseal()  # Fully rehashed synthetic owner bodies still cannot replace the original map/index.
            with self.subTest(field=field), self.assertRaisesRegex(I.AdmissionError, code):
                f.qualify()

    def test_complete_productive_originals_do_not_authorize_changed_h2_provider_source(self):
        f = ConnectedFixture()
        self.assertIs(type(f.qualify()), Q.ProductiveQualification)
        changed = copy.deepcopy(f.inputs)
        changed["provider"][Q.PROVIDER_INPUTS[-1]] = "0" * 64
        with self.assertRaisesRegex(I.AdmissionError, "SOURCE_INPUT_BYTES_CHANGED"):
            f.qualify(current_inputs=changed)

    def test_reviewed_packet_still_requires_original_public_history_not_only_hashes(self):
        f = ConnectedFixture()
        self.assertIs(type(f.qualify()), Q.ProductiveQualification)
        f.documents["inventory"]["history"]["match"] = Q.digest(f.history.expected.record)
        f.reseal()
        with self.assertRaises(I.AdmissionError):
            f.qualify()


if __name__ == "__main__":
    unittest.main(verbosity=2, failfast=True)
