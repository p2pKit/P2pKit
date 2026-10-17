#!/usr/bin/env python3
"""Run only the protected publisher's fixed, complete remote-consumer tail.

No signing, upload, retry, version override or publication authority. Private
captures stay on the ephemeral worker; successful execution returns only a
source-bound public summary. The original job clock includes earlier stages.
"""
import importlib.util
import os
from pathlib import Path
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("publisher_consumer_recovery", ROOT / "scripts/maven_recovery.py")
R = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(R)
P, F = R.P, R.F
JOB_SECONDS = 150 * 60


def publication_context(api, environment):
    context = F.hosted_context(environment, "revalidate")
    P.need(environment.get("RUNNER_OS") == "macOS" and environment.get("RUNNER_ARCH") == "X64",
           "Published consumers require the reviewed Intel macOS job")
    invocation = P.maven_invocation(api, context["source"], context["id"], context["attempt"], completed=False)
    P.need(invocation["tag"] == context["tag"], "Publisher consumer tag differs")
    commit = api.json("/git/commits/" + context["source"])
    tree = commit.get("tree", {}).get("sha", "")
    P.need(commit.get("sha") == context["source"] and P.SHA.fullmatch(tree), "Publisher source tree differs")
    R.verify_checkout(ROOT, context["source"], tree)
    version = P.VERSION.from_properties(R.D.read(ROOT / "gradle.properties", 65536).decode())["canonicalVersion"]
    P.need(version == invocation["version"], "Publisher consumer version differs")
    rows = api.pages(f"/actions/runs/{context['id']}/attempts/{context['attempt']}/jobs", "jobs")
    selected = [row for row in rows if row.get("name") == "publish-release"]
    P.need(len(selected) == 1, "Missing or ambiguous publisher job")
    job = selected[0]
    now, monotonic_now = time.time(), time.monotonic()
    start = P.timestamp(job.get("started_at"))
    P.need(job.get("run_id") == context["id"] and job.get("run_attempt") == context["attempt"] and
           job.get("head_sha") == context["source"] and job.get("status") == "in_progress" and
           job.get("conclusion") is None and job.get("completed_at") is None and
           start <= now < start + JOB_SECONDS - 60,
           "Publisher consumer job is stale or outside its original deadline")
    return invocation, {"commit": context["source"], "tree": tree}, monotonic_now + start + JOB_SECONDS - 60 - now


def execute(api, environment):
    invocation, source, deadline = publication_context(api, environment)
    parent = Path(environment["RUNNER_TEMP"])
    P.PACK.physical_directory(parent)
    directory = Path(tempfile.mkdtemp(prefix="p2pkit-published-consumers-", dir=parent))
    env = R.execution_environment(environment, directory, "consumers")
    script_hash = P.PACK.file_hash(ROOT / R.CONSUMER_SCRIPT, P.JSON_LIMIT)
    outcome = R.terminal_consumers(ROOT, source, env, directory, deadline)
    P.need(outcome.get("code") == "PASS" and type(outcome.get("exitCode")) is int and outcome["exitCode"] == 0 and
           outcome.get("cleanupKnown") is True and outcome.get("capturesClosed") is True and
           outcome.get("timedOut") is False, "Published consumer command or cleanup failed")
    P.need(time.monotonic() <= deadline, "Published consumers exceeded the original job deadline")
    R.verify_checkout(ROOT, source["commit"], source["tree"])
    P.need(P.PACK.file_hash(ROOT / R.CONSUMER_SCRIPT, P.JSON_LIMIT) == script_hash, "Original consumer script changed")
    result = {"result": "COMPLETE_REMOTE_CONSUMERS_VERIFIED_NOT_PUBLISHED", "source": source,
              "maven": invocation, "script": script_hash,
              "log": P.PACK.file_hash(directory / "command.log", R.LOG_LIMIT),
              "exitCode": 0, "cleanupKnown": True, "capturesClosed": True}
    R.write_record(directory, "result.json", result)
    return result


def main():
    os.umask(0o077)
    try:
        result = execute(R.ReadOnlyApi(os.environ.get("GH_TOKEN", "")), os.environ)
        print(result["result"])
        return 0
    except (ValueError, KeyError, TypeError, OSError, RuntimeError):
        # No private exception args, credential/path values or consumer output.
        print("PUBLISHED_CONSUMERS_FAILED: retained private originals; publication is not repeated")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
