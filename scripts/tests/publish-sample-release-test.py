#!/usr/bin/env python3
"""Pure policy/state-machine fixtures; NO real GitHub, build or app evidence."""

import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import urllib.parse
import zipfile


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("releases", ROOT / "scripts/publish-sample-release.py")
R = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(R)
SOURCE, TREE, HEAD = "1" * 40, "2" * 40, "3" * 40


def run(identifier, path, sha, event="push"):
    return {"id": identifier, "run_attempt": 1, "path": path, "head_sha": sha, "event": event,
            "repository": {"full_name": R.REPO}, "head_repository": {"full_name": R.REPO},
            "head_branch": "main", "status": "completed", "conclusion": "success", "workflow_id": 77,
            "pull_requests": [{"number": 99, "head": {"sha": HEAD}}]}


class FakeApi:
    """Original Python orchestration with in-memory HTTP and synthetic ZIPs."""
    def __init__(self):
        self.data, self.collections, self.files, self.mutations = {}, {}, {}, []
        self.release, self.ref, self.assets, self.fail_upload_after = None, None, [], None
        self.release_history, self.release_list_queries = [], []
        self.data["/rules/branches/main"] = [{"type": "pull_request"}, {"type": "required_status_checks",
            "parameters": {"required_status_checks": [{"context": x} for x in sorted(R.REQUIRED)]}}]
        self.data["/commits/" + SOURCE] = {"sha": SOURCE, "commit": {"tree": {"sha": TREE}},
                                        "parents": [{"sha": "4" * 40}, {"sha": HEAD}]}
        self.data["/git/ref/heads/main"] = {"object": {"sha": SOURCE}}
        self.data[f"/compare/{SOURCE}...{SOURCE}"] = {"status": "identical", "merge_base_commit": {"sha": SOURCE}}
        pull = {"number": 99, "merged_at": "2026-09-15T10:00:00Z", "merged": True, "merge_commit_sha": SOURCE,
                "base": {"ref": "main", "repo": {"full_name": R.REPO}},
                "head": {"sha": HEAD, "repo": {"full_name": R.REPO}}, "user": {"login": "implementer"}}
        self.collections[f"/commits/{SOURCE}/pulls"] = [pull]
        self.data["/pulls/99"] = pull
        self.collections["/pulls/99/reviews"] = [{"id": 1, "state": "APPROVED", "commit_id": HEAD,
            "submitted_at": "2026-09-15T09:00:00Z", "author_association": "MEMBER",
            "user": {"login": "independent-reviewer", "type": "User"}}]
        for sha, contexts, event in ((HEAD, R.REQUIRED, "pull_request"), (SOURCE, R.REQUIRED - {"review"}, "push")):
            rows = []
            for i, name in enumerate(sorted(contexts), start=100 if sha == HEAD else 200):
                rows.append({"id": i, "name": name, "head_sha": sha, "status": "completed", "conclusion": "success",
                    "completed_at": "2026-09-15T09:00:00Z", "app": {"slug": "github-code-scanning" if name == "osv-scanner" else "github-actions"},
                    "details_url": f"https://github.com/{R.REPO}/actions/runs/{i}/job/{i}"})
                if name != "osv-scanner":
                    self.data[f"/actions/runs/{i}"] = run(i, R.CHECK_WORKFLOWS[name], sha, event)
            self.collections[f"/commits/{sha}/check-runs?filter=all"] = rows
        producer = run(300, R.PRODUCER, SOURCE)
        self.data["/actions/runs/300"] = producer
        self.collections[f"/actions/workflows/desktop-cross-host.yml/runs?event=push&branch=main&head_sha={SOURCE}"] = [producer]
        self.data["/actions/workflows/desktop-cross-host.yml"] = {"id": 77, "path": R.PRODUCER}
        self.collections["/actions/runs/300/attempts/1/jobs"] = [
            {"id": 10 + i, "name": host, "status": "completed", "conclusion": "success", "run_id": 300, "run_attempt": 1}
            for i, host in enumerate(("ubuntu-latest", "windows-latest", "macos-15"))]
        self.collections["/actions/runs/300/artifacts"] = []

    def json(self, path, *, method="GET", value=None, missing=False, upload=None):
        if upload is not None:
            if self.fail_upload_after is not None and len(self.assets) == self.fail_upload_after:
                raise R.Hold("Synthetic upload failure")
            self.mutations.append(("UPLOAD", path))
            self.assets.append({"id": len(self.assets) + 1, "name": upload.name, "state": "uploaded",
                "size": upload.stat().st_size, "digest": "sha256:" + hashlib.sha256(upload.read_bytes()).hexdigest()})
            return copy.deepcopy(self.assets[-1])
        if method == "POST":
            assert path == "/releases"
            self.mutations.append((method, path))
            self.release = {**value, "id": 500, "html_url": "https://github.com/" + R.REPO + "/releases/tag/" + value["tag_name"]}
            return copy.deepcopy(self.release)
        if method == "PATCH":
            assert path == "/releases/500"
            self.mutations.append((method, path))
            self.release.update(value)
            self.ref = {"object": {"type": "commit", "sha": SOURCE, "url": R.API + R.PREFIX + "/git/commits/" + SOURCE}}
            return copy.deepcopy(self.release)
        if path.startswith("/releases/tags/"):
            # This endpoint promises published releases, not draft discovery.
            return copy.deepcopy(self.release) if self.release and not self.release["draft"] else None
        if path.startswith("/releases?"):
            self.release_list_queries.append(path)
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(path).query)
            assert query["per_page"] == ["100"]
            start = (int(query["page"][0]) - 1) * 100
            rows = self.release_history + ([self.release] if self.release is not None else [])
            return copy.deepcopy(rows[start:start + 100])
        if path == "/releases/500":
            return copy.deepcopy(self.release)
        if path.startswith("/git/ref/tags/"):
            return copy.deepcopy(self.ref)
        return copy.deepcopy(self.data[path])

    def pages(self, path, key=None):
        if path == "/releases":
            return R.Api.pages(self, path, key)
        if path == "/releases/500/assets":
            return copy.deepcopy(self.assets)
        return copy.deepcopy(self.collections[path])

    def download(self, artifact, destination):
        destination.write_bytes(self.files[artifact["id"]])


class ReleaseTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="sample-release-synthetic-")
        self.base = Path(self.temp.name).resolve()
        self.api = FakeApi()
        for i, (platform, runner, arch) in enumerate((("android", "Linux", "x64"), ("linux", "Linux", "x64"),
                                                     ("windows", "Windows", "x64"), ("macos", "macOS", "arm64"))):
            prefix = "sample-android" if platform == "android" else "sample-desktop-" + runner + "-" + arch.upper()
            # RUNNER_ARCH uses X64, not X64 inferred from a runner label.
            artifact = {"id": i + 1, "name": prefix + f"-{SOURCE}-300-1", "expired": False,
                        "workflow_run": {"id": 300, "head_sha": SOURCE, "head_branch": "main"}}
            raw = self.bundle(platform, arch)
            artifact.update(size_in_bytes=len(raw), digest="sha256:" + hashlib.sha256(raw).hexdigest())
            self.api.files[i + 1] = raw
            self.api.collections["/actions/runs/300/artifacts"].append(artifact)

    def tearDown(self):
        self.temp.cleanup()  # Source-defined synthetic bytes only.

    def bundle(self, platform, arch, extra=None, context_change=None):
        payload = {"sample-debug.apk": b"synthetic APK, not executable"} if platform == "android" else {
            f"{kind}-{platform}-{arch}-{SOURCE[:12]}" + (".zip" if platform == "windows" else ".tar.gz"):
            b"synthetic archive, not an application" for kind in ("desktop-ui", "desktop-cli")}
        if platform != "android":
            payload[f"desktop-installer-{platform}-{arch}-{SOURCE[:12]}.{R.PACK.INSTALLER_FORMATS[platform]}"] = b"synthetic installer, not executable"
        artifacts = [{"file": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()} for name, raw in payload.items()]
        context = {"repository": R.REPO, "commit": SOURCE, "tree": TREE, "event_name": "push", "ref": "refs/heads/main",
            "run_id": "300", "run_attempt": "1", "job": "verify", "workflow_ref": R.REPO + "/" + R.PRODUCER + "@refs/heads/main",
            "workflow_sha": SOURCE, "platform": "linux" if platform == "android" else platform, "architecture": arch}
        context.update(context_change or {})
        manifest = {"schema": 2, "sourceAndRun": context, "scope": R.PACK.SCOPE}
        if platform == "android":
            manifest.update(artifact=artifacts[0], agpMetadata={"applicationId": "dev.p2pkit.sample.android", "variant": "debug",
                "versionCode": 1, "versionName": "0.1.0"})
        else:
            manifest["artifacts"] = artifacts
        payload["manifest.json"] = R.encoded(manifest)
        payload.update({"licenses/" + name: b"synthetic public license" for name in R.PACK.LICENSES})
        if extra:
            payload.update(extra)
        payload["checksums.sha256"] = "".join(hashlib.sha256(raw).hexdigest() + "  " + name + "\n" for name, raw in payload.items()).encode()
        path = self.base / "fixture.zip"
        with zipfile.ZipFile(path, "w") as archive:
            for name, raw in payload.items():
                archive.writestr(name, raw)
        return path.read_bytes()

    def plan(self):
        # Actual argparse/workflow inputs are strings, not test-only integers.
        return R.admit(self.api, SOURCE, "300", "1")

    def output(self, label="output"):
        path = self.base / label
        path.mkdir()
        return path

    def test_complete_metadata_admits_exact_four_outputs_without_mutation(self):
        plan = self.plan()
        self.assertEqual(4, len(plan["artifacts"]))
        self.assertEqual("samples-" + SOURCE, plan["tag"])
        self.assertEqual([], self.api.mutations)

    def test_cli_string_producer_identity_is_normalized_once(self):
        plan = self.plan()
        self.assertIs(type(plan["producer"]["id"]), int)
        self.assertEqual(300, plan["producer"]["id"])
        self.assertEqual(plan, R.admit(self.api, SOURCE, 300, 1))
        self.assertEqual(plan, R.admit(self.api, SOURCE))
        for value in ("0300", "300.0", "0", "-300", True):
            with self.subTest(value=value), self.assertRaises(R.Hold):
                R.admit(self.api, SOURCE, value, "1")

    def newer_check(self, name, event, sha=SOURCE, change=None):
        path = f"/commits/{sha}/check-runs?filter=all"
        previous = next(x for x in self.api.collections[path] if x["name"] == name)
        row = {**previous, "id": 900, "details_url": f"https://github.com/{R.REPO}/actions/runs/900/job/900"}
        row.update(change or {})
        self.api.collections[path].append(row)
        self.api.data["/actions/runs/900"] = run(900, R.CHECK_WORKFLOWS[name], sha, event)

    def test_latest_successful_main_schedule_and_manual_checks_are_reused(self):
        original = copy.deepcopy(self.api.collections)
        for name in ("complete-gate", "scan / osv-scan"):
            for event in ("schedule", "workflow_dispatch"):
                self.api.collections = copy.deepcopy(original)
                self.newer_check(name, event)
                with self.subTest(name=name, event=event):
                    plan = self.plan()
                    self.assertEqual(900, next(x["id"] for x in plan["mainChecks"] if x["name"] == name))
        self.assertEqual([], self.api.mutations)

    def test_newest_main_failure_or_incomplete_check_is_not_hidden_by_old_success(self):
        original = copy.deepcopy(self.api.collections)
        for name in ("complete-gate", "scan / osv-scan"):
            for event in ("push", "schedule", "workflow_dispatch"):
                for change in ({"conclusion": "failure"}, {"conclusion": "skipped"}, {"status": "in_progress"}):
                    self.api.collections = copy.deepcopy(original)
                    self.newer_check(name, event, change=change)
                    with self.subTest(name=name, event=event, change=change), self.assertRaises(R.Hold):
                        self.plan()

    def test_main_scheduled_manual_checks_still_require_exact_main_workflow_source_and_repo(self):
        original = copy.deepcopy(self.api.collections)
        for event in ("schedule", "workflow_dispatch"):
            for change in ({"head_branch": "topic"}, {"head_sha": HEAD},
                           {"head_repository": {"full_name": "fork/P2pKit"}},
                           {"path": R.PRODUCER}, {"event": "pull_request"}):
                self.api.collections = copy.deepcopy(original)
                self.newer_check("complete-gate", event)
                self.api.data["/actions/runs/900"].update(change)
                with self.subTest(event=event, change=change), self.assertRaises(R.Hold):
                    self.plan()

    def test_pr_checks_do_not_admit_main_schedule_or_manual_events(self):
        original = copy.deepcopy(self.api.collections)
        for event in ("schedule", "workflow_dispatch"):
            self.api.collections = copy.deepcopy(original)
            self.newer_check("complete-gate", event, sha=HEAD)
            with self.subTest(event=event), self.assertRaises(R.Hold):
                self.plan()

    def test_trigger_event_set_is_explicit_for_each_maintained_workflow(self):
        for name, path in R.TRIGGERS.items():
            event_payload = {"name": name, "id": 900, "head_sha": SOURCE}
            for event in ("push", "schedule", "workflow_dispatch", "pull_request", "pull_request_target"):
                self.api.data["/actions/runs/900"] = run(900, path, SOURCE, event)
                with self.subTest(name=name, event=event):
                    if event == "push" or (name in ("CI", "OSV Advisory Scan") and event in ("schedule", "workflow_dispatch")):
                        self.assertEqual(SOURCE, R.trigger_source(self.api, event_payload))
                    else:
                        with self.assertRaises(R.Hold):
                            R.trigger_source(self.api, event_payload)
        with self.assertRaises(R.Hold):
            R.trigger_source(self.api, {"name": "Untrusted workflow", "id": 900, "head_sha": SOURCE})

    def test_wrong_producer_event_repo_workflow_commit_and_status_reject(self):
        path = "/actions/runs/300"
        original = copy.deepcopy(self.api.data[path])
        for key, value in (("event", "pull_request"), ("head_sha", HEAD), ("head_branch", "topic"),
                           ("path", ".github/workflows/attacker.yml"), ("workflow_id", 1),
                           ("head_repository", {"full_name": "fork/P2pKit"}), ("conclusion", "failure")):
            self.api.data[path] = {**original, key: value}
            with self.subTest(key=key), self.assertRaises(R.Hold):
                self.plan()
        self.assertEqual([], self.api.mutations)

    def test_missing_failed_skipped_and_forged_required_checks_reject(self):
        path = f"/commits/{SOURCE}/check-runs?filter=all"
        original = copy.deepcopy(self.api.collections[path])
        for key, value in (("conclusion", "failure"), ("conclusion", "skipped"), ("head_sha", HEAD),
                           ("app", {"slug": "unknown"}), ("details_url", "https://attacker.invalid")):
            self.api.collections[path] = copy.deepcopy(original)
            self.api.collections[path][0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(R.Hold):
                self.plan()
        self.api.collections[path] = []
        with self.assertRaises(R.Hold):
            self.plan()

    def test_changed_required_policy_is_not_silently_waived(self):
        self.api.data["/rules/branches/main"][1]["parameters"]["required_status_checks"].append({"context": "new-required-check"})
        with self.assertRaises(R.Hold):
            self.plan()

    def test_formal_approval_must_be_independent_current_premerge_and_not_dismissed(self):
        original = copy.deepcopy(self.api.collections["/pulls/99/reviews"][0])
        for change in ({"user": {"login": "implementer", "type": "User"}}, {"commit_id": SOURCE},
                       {"submitted_at": "2026-09-16T09:00:00Z"}, {"state": "DISMISSED"}, {"state": "CHANGES_REQUESTED"},
                       {"user": {"login": "robot", "type": "Bot"}}):
            self.api.collections["/pulls/99/reviews"] = [{**original, **change}]
            with self.subTest(change=change), self.assertRaises(R.Hold):
                self.plan()

    def test_unmerged_or_non_preserving_candidate_rejects(self):
        self.api.data["/pulls/99"]["merged"] = False
        with self.assertRaises(R.Hold):
            self.plan()
        self.api.data["/pulls/99"]["merged"] = True
        self.api.data["/commits/" + SOURCE]["parents"] = [{"sha": HEAD}]
        with self.assertRaises(R.Hold):
            self.plan()

    def test_missing_host_and_mixed_attempt_cannot_publish_partial_platform_set(self):
        self.api.collections["/actions/runs/300/attempts/1/jobs"][0]["run_attempt"] = 2
        with self.assertRaises(R.Hold):
            self.plan()
        self.api.collections["/actions/runs/300/attempts/1/jobs"].pop()
        with self.assertRaises(R.Hold):
            self.plan()

    def test_expired_missing_digest_duplicate_and_wrong_artifact_source_reject(self):
        path = "/actions/runs/300/artifacts"
        original = copy.deepcopy(self.api.collections[path])
        for change in ({"expired": True}, {"digest": ""}, {"size_in_bytes": R.ARCHIVE_LIMIT + 1},
                       {"workflow_run": {"id": 300, "head_sha": HEAD, "head_branch": "main"}}):
            self.api.collections[path] = copy.deepcopy(original)
            self.api.collections[path][0].update(change)
            with self.subTest(change=change), self.assertRaises(R.Hold):
                self.plan()
        self.api.collections[path] = original + [original[0]]
        with self.assertRaises(R.Hold):
            self.plan()

    def test_verify_inspects_all_original_bundles_and_never_mutates(self):
        result = R.publish(self.api, self.plan(), self.output(), False)
        self.assertEqual("VERIFIED_NOT_PUBLISHED", result["result"])
        self.assertEqual(7, len(result["assets"]))
        self.assertEqual([".apk", ".deb", ".msi", ".dmg"], [Path(x["file"]).suffix for x in result["assets"][:4]])
        self.assertEqual([], self.api.mutations)

    def test_direct_installers_and_notices_preserve_the_original_producer_members(self):
        plan, destination = self.plan(), self.output()
        result = R.publish(self.api, plan, destination, False)
        for asset in result["assets"][:4]:
            with zipfile.ZipFile(io.BytesIO(self.api.files[asset["artifactId"]])) as source:
                self.assertEqual(source.read(asset["member"]), (destination / asset["file"]).read_bytes())
            self.assertEqual(asset["sha256"], hashlib.sha256((destination / asset["file"]).read_bytes()).hexdigest())
        with zipfile.ZipFile(destination / "sample-notices.zip") as notices:
            self.assertEqual(sorted(R.PACK.LICENSES), sorted(notices.namelist()))
            self.assertTrue(all(notices.read(name) == b"synthetic public license" for name in R.PACK.LICENSES))
        manifest = json.loads((destination / "sample-release.json").read_bytes())
        self.assertEqual(result["assets"][:5], manifest["releaseAssets"])

    def test_differing_cross_platform_notices_prevent_publication(self):
        raw = self.bundle("linux", "x64", extra={"licenses/P2pKit-LICENSE": b"different public notice"})
        self.api.files[2] = raw
        self.api.collections["/actions/runs/300/artifacts"][1].update(
            size_in_bytes=len(raw), digest="sha256:" + hashlib.sha256(raw).hexdigest())
        with self.assertRaisesRegex(R.Hold, "notices differ"):
            R.publish(self.api, self.plan(), self.output(), True)
        self.assertEqual([], self.api.mutations)

    def test_unsafe_path_private_extra_and_wrong_manifest_source_reject(self):
        for i, changes in enumerate(({"extra": {"../escape": b"bad"}}, {"extra": {"private-child.log": b"bad"}},
                                     {"context_change": {"commit": HEAD}}, {"context_change": {"run_attempt": "2"}})):
            raw = self.bundle("android", "x64", **changes)
            artifact = self.plan()["artifacts"][0]
            artifact.update(size_in_bytes=len(raw), digest="sha256:" + hashlib.sha256(raw).hexdigest())
            path = self.base / f"bad-{i}.zip"
            path.write_bytes(raw)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                R.inspect_bundle(path, artifact, self.plan())

    def test_tampered_bundle_prevents_all_mutation(self):
        plan = self.plan()
        self.api.files[1] += b"tampered"
        with self.assertRaises(ValueError):
            R.publish(self.api, plan, self.output(), True)
        self.assertEqual([], self.api.mutations)

    def test_first_publish_is_draft_then_exact_uploads_then_prerelease_readback(self):
        result = R.publish(self.api, self.plan(), self.output(), True)
        self.assertEqual("PUBLISHED_DEVELOPMENT_PRERELEASE", result["result"])
        self.assertEqual(("POST", "/releases"), self.api.mutations[0])
        self.assertEqual(("PATCH", "/releases/500"), self.api.mutations[-1])
        self.assertEqual(7, len(self.api.assets))
        self.assertFalse(self.api.release["draft"])
        self.assertTrue(self.api.release["prerelease"])
        self.assertEqual("false", self.api.release["make_latest"])
        self.assertFalse(self.api.release["tag_name"].startswith("v"))

    def test_published_rerun_checks_same_bytes_and_does_not_mutate(self):
        plan = self.plan()
        R.publish(self.api, plan, self.output(), True)
        self.api.mutations.clear()
        R.publish(self.api, plan, self.output("rerun"), True)
        self.assertEqual([], self.api.mutations)

    def test_partial_draft_resumes_only_missing_assets(self):
        plan = self.plan()
        self.api.fail_upload_after = 2
        with self.assertRaises(R.Hold):
            R.publish(self.api, plan, self.output(), True)
        self.assertTrue(self.api.release["draft"])
        self.assertIsNone(self.api.json("/releases/tags/" + plan["tag"], missing=True))
        self.api.fail_upload_after = None
        self.api.mutations.clear()
        R.publish(self.api, plan, self.output("resume"), True)
        self.assertEqual(5, sum(x[0] == "UPLOAD" for x in self.api.mutations))
        self.assertEqual(0, sum(x[0] == "POST" for x in self.api.mutations))
        self.assertEqual(("PATCH", "/releases/500"), self.api.mutations[-1])

    def test_existing_draft_on_later_release_page_is_resumed_without_second_post(self):
        plan = self.plan()
        self.api.fail_upload_after = 2
        with self.assertRaises(R.Hold):
            R.publish(self.api, plan, self.output(), True)
        self.api.release_history = [{"id": 1000 + i, "tag_name": "unrelated-" + str(i)} for i in range(100)]
        self.api.fail_upload_after = None
        self.api.mutations.clear()
        self.api.release_list_queries.clear()
        R.publish(self.api, plan, self.output("resume"), True)
        self.assertEqual(["/releases?per_page=100&page=1", "/releases?per_page=100&page=2"], self.api.release_list_queries)
        self.assertFalse(any(x[0] == "POST" for x in self.api.mutations))
        self.assertEqual(5, sum(x[0] == "UPLOAD" for x in self.api.mutations))

    def test_ambiguous_same_tag_drafts_prevent_all_mutation(self):
        plan = self.plan()
        self.api.fail_upload_after = 2
        with self.assertRaises(R.Hold):
            R.publish(self.api, plan, self.output(), True)
        self.api.release_history = [{**self.api.release, "id": 501}]
        self.api.fail_upload_after = None
        self.api.mutations.clear()
        with self.assertRaises(R.Hold):
            R.publish(self.api, plan, self.output("ambiguous"), True)
        self.assertEqual([], self.api.mutations)

    def test_changed_draft_body_target_or_scope_is_never_adopted(self):
        plan = self.plan()
        self.api.fail_upload_after = 2
        with self.assertRaises(R.Hold):
            R.publish(self.api, plan, self.output(), True)
        original = copy.deepcopy(self.api.release)
        self.api.fail_upload_after = None
        self.api.mutations.clear()
        for i, change in enumerate(({"body": "changed"}, {"target_commitish": HEAD}, {"prerelease": False}, {"name": "changed"})):
            self.api.release = {**original, **change}
            with self.subTest(change=change), self.assertRaises(R.Hold):
                R.publish(self.api, plan, self.output("changed" + str(i)), True)
            self.assertEqual([], self.api.mutations)

    def test_collision_unknown_asset_or_missing_digest_never_overwrites(self):
        plan = self.plan()
        R.publish(self.api, plan, self.output(), True)
        original = copy.deepcopy(self.api.assets)
        for i, change in enumerate(({"digest": None}, {"name": "unexpected.log"}, {"state": "starter"})):
            self.api.assets = copy.deepcopy(original)
            self.api.assets[0].update(change)
            self.api.mutations.clear()
            with self.subTest(change=change), self.assertRaises(R.Hold):
                R.publish(self.api, plan, self.output("collision" + str(i)), True)
            self.assertEqual([], self.api.mutations)

    def test_wrong_tag_and_orphan_tag_are_not_adopted(self):
        for i, sha in enumerate((HEAD, SOURCE)):
            self.api.ref = {"object": {"type": "commit", "sha": sha, "url": R.API + R.PREFIX + "/git/commits/" + sha}}
            with self.subTest(sha=sha), self.assertRaises(R.Hold):
                R.publish(self.api, self.plan(), self.output("tag" + str(i)), True)
            self.assertEqual([], self.api.mutations)

    def test_preexisting_workspace_is_not_written(self):
        path = self.output()
        sentinel = path / "important.zip"
        sentinel.write_bytes(b"keep")
        with self.assertRaises(R.Hold):
            R.publish(self.api, self.plan(), path, True)
        self.assertEqual(b"keep", sentinel.read_bytes())

    def test_context_rejects_local_fork_branch_and_wrong_publisher_source(self):
        env = {"GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted", "GITHUB_REPOSITORY": R.REPO,
               "GITHUB_REF": "refs/heads/main", "GITHUB_SERVER_URL": "https://github.com", "GITHUB_API_URL": R.API,
               "GITHUB_WORKFLOW_REF": R.REPO + "/" + R.WORKFLOW + "@refs/heads/main", "GITHUB_WORKFLOW_SHA": SOURCE,
               "GITHUB_SHA": SOURCE, "GITHUB_RUN_ID": "1", "GITHUB_RUN_ATTEMPT": "1", "GITHUB_EVENT_NAME": "workflow_dispatch"}
        self.assertEqual(SOURCE, R.hosted_context(env)["source"])
        for key, value in (("GITHUB_ACTIONS", "false"), ("GITHUB_REPOSITORY", "fork/P2pKit"),
                           ("GITHUB_REF", "refs/heads/topic"), ("GITHUB_SHA", HEAD), ("GITHUB_EVENT_NAME", "pull_request_target")):
            with self.subTest(key=key), self.assertRaises(R.Hold):
                R.hosted_context({**env, key: value})


if __name__ == "__main__":
    unittest.main()
