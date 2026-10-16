#!/usr/bin/env python3
"""Seven Python/Node DATA contract controls; never hosted or native authority.

One fixed, credential-free Node peer receives only this small synthetic model.
Neither endpoint imports an earlier test suite or launches a native helper.
"""
from __future__ import annotations

import _strptime
import base64
import ctypes
import os
from pathlib import Path
import selectors
import shutil
import stat
import subprocess
import sys
import time
import unittest


sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(SCRIPTS), str(SCRIPTS / "tests")]
NODE = shutil.which("node")
PEER = SCRIPTS / "tests" / "hosted-initial-artifact-finite-contract-peer.cjs"
ARGV = [NODE, "--max-old-space-size=256", str(PEER)]
CHILD_ENV = {"PATH": os.defpath, "LANG": "C", "LC_ALL": "C", "TZ": "UTC"}
BOUND = 512 * 1024
SCOPE = "OFFLINE_FINITE_PYTHON_NODE_MODEL_NOT_AUTHORITY_V1"
GUARDED = False
SPAWNS = 0
PIPE_SETUP = False
PIPE_WRAPS = []


def offline(event, args):
    global SPAWNS
    if event == "open" and GUARDED:
        # Popen wraps these three parent pipe FDs before its child audit event.
        # Permit no pathname, file, fourth wrapper, duplicate FD or later reopen.
        if not PIPE_SETUP or SPAWNS or len(PIPE_WRAPS) >= 3:
            raise AssertionError("FINITE_CONTRACT_UNEXPECTED_OPEN")
        descriptor, mode, flags = args
        position = len(PIPE_WRAPS)
        expected = (os.O_WRONLY, os.O_RDONLY, os.O_RDONLY)[position]
        if type(descriptor) is not int or descriptor <= 2 or descriptor in [row[0] for row in PIPE_WRAPS] or \
                mode not in (("w", "wb") if position == 0 else ("r", "rb")) or flags & os.O_ACCMODE != expected:
            raise AssertionError("FINITE_CONTRACT_PIPE_WRAPPER")
        metadata = os.fstat(descriptor)
        if not stat.S_ISFIFO(metadata.st_mode):
            raise AssertionError("FINITE_CONTRACT_NOT_PIPE")
        PIPE_WRAPS.append((descriptor, metadata.st_dev, metadata.st_ino, expected))
    elif event == "subprocess.Popen":
        if not GUARDED or not PIPE_SETUP or len(PIPE_WRAPS) != 3 or SPAWNS or \
                args != (NODE, ARGV, str(SCRIPTS.parent), CHILD_ENV):
            raise AssertionError("FINITE_CONTRACT_UNEXPECTED_CHILD")
        SPAWNS += 1
    elif event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen",
            "os.putenv", "os.unsetenv") or GUARDED and event in ("open", "os.listdir", "os.scandir"):
        raise AssertionError("FINITE_CONTRACT_SIDE_EFFECT")


sys.addaudithook(offline)
import hosted_initial_artifact_delivery as D
import hosted_initial_artifact_finite_fixtures as F


def b64(raw):
    return base64.b64encode(raw).decode("ascii")


def exchange(raw):
    """Bound both pipe accumulation and the one original child, not just JSON."""
    global PIPE_SETUP
    if NODE is None or not 0 < len(raw) <= BOUND or PIPE_SETUP or PIPE_WRAPS or SPAWNS:
        raise AssertionError("FINITE_CONTRACT_PEER_OR_INPUT")
    PIPE_SETUP = True
    try:
        child = subprocess.Popen(ARGV, cwd=str(SCRIPTS.parent), env=CHILD_ENV, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
    finally:
        PIPE_SETUP = False
    deadline = time.monotonic() + 20
    output, errors, offset = bytearray(), bytearray(), 0
    try:
        actual = []
        for pipe, access in ((child.stdin, os.O_WRONLY), (child.stdout, os.O_RDONLY), (child.stderr, os.O_RDONLY)):
            metadata = os.fstat(pipe.fileno())
            actual.append((pipe.fileno(), metadata.st_dev, metadata.st_ino, access))
        if actual != PIPE_WRAPS or len({row[1:3] for row in actual}) != 3:
            raise AssertionError("FINITE_CONTRACT_ORIGINAL_PIPE_WRAPPERS")
        with selectors.DefaultSelector() as selector:
            for pipe, events in ((child.stdin, selectors.EVENT_WRITE), (child.stdout, selectors.EVENT_READ),
                    (child.stderr, selectors.EVENT_READ)):
                os.set_blocking(pipe.fileno(), False)
                selector.register(pipe, events)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise AssertionError("FINITE_CONTRACT_PEER_TIMEOUT")
                for key, _events in selector.select(remaining):
                    pipe = key.fileobj
                    if pipe is child.stdin:
                        written = os.write(pipe.fileno(), raw[offset:offset + 32768])
                        if written <= 0:
                            raise AssertionError("FINITE_CONTRACT_PEER_SHORT_WRITE")
                        offset += written
                        if offset == len(raw):
                            selector.unregister(pipe)
                            pipe.close()
                    else:
                        target, limit = (output, BOUND) if pipe is child.stdout else (errors, 4096)
                        part = os.read(pipe.fileno(), min(32768, limit + 1 - len(target)))
                        if not part:
                            selector.unregister(pipe)
                            pipe.close()
                        else:
                            target.extend(part)
                            if len(target) > limit:
                                raise AssertionError("FINITE_CONTRACT_PEER_OUTPUT_BOUND")
        remaining = deadline - time.monotonic()
        if remaining <= 0 or child.wait(timeout=remaining) != 0 or errors or offset != len(raw):
            raise AssertionError("FINITE_CONTRACT_PEER_FAILED")
        return bytes(output)
    except Exception:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)
        raise AssertionError("FINITE_CONTRACT_PEER_REFUSED_OR_TIMED_OUT") from None
    finally:
        for pipe in (child.stdin, child.stdout, child.stderr):
            pipe.close()


def preimages(mode):
    return {name: F.wire({"model": mode + "_" + name.upper() + "_NOT_NATIVE_AUTHORITY"}) for name in
        ("directory_identity_raw", "file_metadata_raw", "file_owner_close_raw")}


def environment(model, after_model):
    ready = model["ready"]
    return {"GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted", "GITHUB_REPOSITORY": D.I.REPOSITORY,
        "GITHUB_SHA": ready["source"]["commit"], "GITHUB_REF": D.S.SOURCE_REF, "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_JOB": "populate", "GITHUB_RUN_ID": "9001", "GITHUB_RUN_ATTEMPT": "2",
        "GITHUB_WORKFLOW_SHA": ready["source"]["commit"], "GITHUB_WORKFLOW_REF": D.I.REPOSITORY +
            "/.github/workflows/dependency-cache-bootstrap.yml@" + D.S.SOURCE_REF,
        "GITHUB_SERVER_URL": "https://github.com", "GITHUB_API_URL": "https://api.github.com",
        "RUNNER_OS": "Linux", "RUNNER_ARCH": "X64", "RUNNER_NAME": "MODEL_RUNNER_NOT_AUTHORITY",
        "P2PKIT_INITIAL_SEAL_SHA256": F.seed()["initialSealSha256"], "P2PKIT_INITIAL_SEAL_END_NS": str(346 * F.NS),
        "P2PKIT_INITIAL_SEAL_CLOCK_ROLE": "linux-x64", "P2PKIT_INITIAL_SEAL_CLOCK_DOMAIN":
            F.seed()["initialSealClockDomain"], "P2PKIT_INITIAL_SEAL_CLOCK_TICKS_PER_SECOND": str(F.NS),
        "P2PKIT_INITIAL_SEAL_BOOT_SHA256": "a" * 64, "P2PKIT_INITIAL_SEAL_OUTCOME": "success",
        "P2PKIT_INITIAL_BEFORE_SHA256": ready["beforeSha256"], "P2PKIT_INITIAL_BEFORE_OUTCOME": "success",
        "P2PKIT_INITIAL_UPLOAD_OUTCOME": "success", "P2PKIT_INITIAL_UPLOAD_SHA256": F.sha(after_model["upload_raw"]),
        "P2PKIT_INITIAL_UPLOAD_DIRECTORY_SHA256": after_model["carrier"]["directoryIdentitySha256"],
        "P2PKIT_INITIAL_UPLOAD_FILE_METADATA_SHA256": after_model["carrier"]["fileMetadataSha256"],
        "P2PKIT_INITIAL_UPLOAD_OWNER_CLOSE_SHA256": after_model["carrier"]["fileOwnerCloseSha256"]}


class FiniteContractControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global GUARDED
        GUARDED = True
        cls.model = F.fixture(D)
        cls.after_model = F.after(D, cls.model)
        cls.finish_input = F.wire(cls.model["control"])
        cls.after_input = F.wire(cls.after_model["control"])
        cls.upload = cls.after_model["upload_raw"]
        cls.finish_preimages, cls.after_preimages = preimages("FINISH"), preimages("AFTER")
        cls.finish_result = D.finite_result("finish", cls.upload, ready_raw=cls.model["ready_raw"],
            input_raw=cls.finish_input, closed_ns=347 * F.NS, **cls.finish_preimages)
        finish = D.canonical(cls.finish_result)
        # A must bind this test's actual U output preimages, not independent fake hashes.
        cls.after_model["carrier"] = {name: finish[name] for name in D.CARRIER_FIELDS}
        cls.delivery = F.delivery(D, cls.model, cls.after_model)
        cls.after_result = D.finite_result("after", cls.delivery, ready_raw=cls.after_model["ready_raw"],
            input_raw=cls.after_input, closed_ns=408 * F.NS, **cls.after_preimages)
        cls.codec = F.wire({"uint64": (1 << 64) - 1, "largeId": (1 << 63) - 1, "safeBoundary": (1 << 53) + 1,
            "unicode": "\u00e9\U0001f680\u007f\b\t\r\n\"\\", "\ue000": 1, "\U00010000": 2})
        cls.invalid = [b'{"n":1.0}\n', b'{"n":1e0}\n', b'{"n":-0}\n']
        request = {"schema": 1, "scope": SCOPE, "nowMs": F.NOW * 1000, "environment": environment(cls.model, cls.after_model),
            "readyBase64": b64(cls.model["ready_raw"]), "finalBase64": b64(cls.model["final_raw"]),
            "finishInputBase64": b64(cls.finish_input), "afterReadyBase64": b64(cls.after_model["ready_raw"]),
            "afterInputBase64": b64(cls.after_input), "finishResultBase64": b64(cls.finish_result),
            "afterResultBase64": b64(cls.after_result), "codecBase64": b64(cls.codec),
            "invalidCanonicalBase64": [b64(raw) for raw in cls.invalid]}
        cls.response = D.canonical(exchange(F.wire(request)), BOUND)
        D.fields(cls.response, {"schema", "scope", "readyBase64", "afterReadyBase64", "finishInputBase64", "afterInputBase64",
            "finishResultBase64", "afterResultBase64", "uploadOutputs", "afterOutputs", "changedFinishInputBase64",
            "changedAfterInputBase64", "originalInputRefused", "reboundInputRefused", "codecBase64", "invalidRefused"})
        if cls.response["schema"] != 1 or cls.response["scope"] != SCOPE or SPAWNS != 1:
            raise AssertionError("FINITE_CONTRACT_EXACT_RESPONSE")

    def same(self, actual, expected):
        self.assertTrue(actual == expected, "FINITE_CONTRACT_EXACT_BYTES_OR_VALUE")

    def returned(self, name):
        return D._base64(self.response[name], BOUND)

    def pending_from(self, raw, mode):
        model = self.model
        control = D.control_input(raw, mode)
        if mode == "finish":
            return D.upload_pending(model["pending"], model["context"], policy=model["policy"], match=model["match"],
                control=control, observed=D.finish_observations(control, now=F.NOW), finish_first=345 * F.NS,
                prepared=346 * F.NS, now=F.NOW)
        return D.delivery_pending(model["pending"], model["context"], self.upload, self.after_model["ready_raw"],
            policy=model["policy"], match=model["match"], control=control, carrier=self.after_model["carrier"],
            prepared=407 * F.NS, now=F.NOW)

    def result_and_outputs(self, mode):
        upload = mode == "finish"
        original = self.finish_result if upload else self.after_result
        raw = self.returned("finishResultBase64" if upload else "afterResultBase64")
        self.same(raw, original)
        value = D.canonical(raw)
        D.fields(value, D.FINITE_FIELDS)
        pending_raw = D.encoded(D.pending_value(value["pending"], mode))
        self.same(pending_raw, self.upload if upload else self.delivery)
        reconstructed = D.finite_result(mode, pending_raw,
            ready_raw=self.model["ready_raw"] if upload else self.after_model["ready_raw"],
            input_raw=self.finish_input if upload else self.after_input,
            closed_ns=(347 if upload else 408) * F.NS,
            **(self.finish_preimages if upload else self.after_preimages))
        self.same(raw, reconstructed)
        outputs = {"artifact-id": value["artifactId"], "receipt-base64": b64(pending_raw),
            "receipt-sha256": F.sha(pending_raw), "directory-identity-sha256": value["directoryIdentitySha256"],
            "file-metadata-sha256": value["fileMetadataSha256"], "file-owner-close-sha256": value["fileOwnerCloseSha256"]}
        self.same(self.response["uploadOutputs" if upload else "afterOutputs"], outputs)
        return value

    def test_01_python_ready_and_after_ready_are_accepted_losslessly(self):
        self.same(self.returned("readyBase64"), self.model["ready_raw"])
        self.same(D.stream_ready(self.returned("readyBase64")), self.model["ready"])
        self.same(self.returned("afterReadyBase64"), self.after_model["ready_raw"])

    def test_02_node_finish_input_reproduces_python_pending(self):
        raw = self.returned("finishInputBase64")
        self.same(raw, self.finish_input)
        self.same(self.pending_from(raw, "finish"), self.upload)

    def test_03_node_after_input_retains_both_complete_original_bodies(self):
        raw = self.returned("afterInputBase64")
        self.same(raw, self.after_input)
        control = D.control_input(raw, "after")
        self.same(len(control[1]), 2)
        for index, row in enumerate(control[1]):
            self.same(row["body"], D._base64(self.after_model["control"]["afterOriginals"][index]["bodyBase64"], D.HTTP_LIMIT))
        self.same(self.pending_from(raw, "after"), self.delivery)

    def test_04_python_finish_result_passes_node_full_predicate_and_six_outputs(self):
        self.result_and_outputs("finish")

    def test_05_python_after_result_binds_original_u_carrier_and_shortened_retention(self):
        value = self.result_and_outputs("after")
        self.same(value["pending"]["uploadCarrier"], self.after_model["carrier"])
        artifact = value["pending"]["artifact"]
        self.same(artifact["requestedRetentionDays"], 14)
        self.same(artifact["expiresAt"], "2026-10-09T00:00:30Z")
        self.same(artifact["requestedExpiresAt"], "2026-10-10T00:00:30.000Z")

    def test_06_changed_original_i_is_not_substituted_even_with_rebound_outer_hash(self):
        self.same(self.response["originalInputRefused"], {"finish": True, "after": True})
        self.same(self.response["reboundInputRefused"], {"finish": True, "after": True})
        for mode, name, original, pending in (("finish", "changedFinishInputBase64", self.finish_input, self.upload),
                ("after", "changedAfterInputBase64", self.after_input, self.delivery)):
            changed = self.returned(name)
            self.assertTrue(changed != original, "FINITE_CONTRACT_NEGATIVE_MUST_CHANGE_BYTES")
            self.assertTrue(self.pending_from(changed, mode) != pending, "FINITE_CONTRACT_MUST_RETAIN_ACTUAL_ORIGINALS")

    def test_07_exact_large_integers_unicode_and_lexical_float_boundaries(self):
        raw = self.returned("codecBase64")
        self.same(raw, self.codec)
        parsed = D.canonical(raw)
        self.same(D.integer(parsed["uint64"]), (1 << 64) - 1)
        self.same(D.integer(parsed["largeId"]), (1 << 63) - 1)
        self.same(D.integer(parsed["safeBoundary"]), (1 << 53) + 1)
        self.same(self.response["invalidRefused"], [True, True, True])
        # Python's generic parser preserves a float; its typed integer gate must reject it.
        for invalid in self.invalid[:2]:
            value = D.I.parse(invalid, BOUND)
            self.same(type(value["n"]), float)
            with self.assertRaises(ValueError):
                D.integer(value["n"])
        with self.assertRaises(ValueError):
            D.canonical(self.invalid[2])


if __name__ == "__main__":
    unittest.main(failfast=True)
