#!/usr/bin/env python3
"""Four pure/mocked diagnostic controls, not Darwin/libproc or simulator acceptance."""
import ast
import copy
import ctypes
import importlib.util
import json
import os
from pathlib import Path
import queue
import sys
import unittest
from unittest import mock

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("runtime_metadata_diagnostic",
    ROOT / "scripts/diagnostics/intel-simctl/runtime-list.py")
D = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(D)

# Supplied numeric fixtures only; no native identity, hosted source or clock claim.
EPOCH = 100000000
CONTROLLER = {"pid": 10, "uid": 501, "parentPid": 9, "parentUniqueId": 90, "parentPidVersion": 1,
              "group": 10, "uniqueId": 100, "pidVersion": 3,
              "startSeconds": 90, "startMicroseconds": 0, "status": 2}
CHILD = {"pid": 20, "uid": 501, "parentPid": 10, "parentUniqueId": 100, "parentPidVersion": 3,
         "group": 20, "uniqueId": 200, "pidVersion": 1,
         "startSeconds": 100, "startMicroseconds": 1000, "status": 3}


class SuppliedNative:
    def __init__(self, image="simctl", change=None):
        self.image, self.change, self.child_reads = image, change, 0

    def census(self, _deadline):
        return [copy.deepcopy(CHILD)]

    def identity(self, pid, permitted=None):
        if pid == CONTROLLER["pid"]:
            return copy.deepcopy(CONTROLLER), "UNKNOWN"
        row = copy.deepcopy(CHILD)
        self.child_reads += 1
        if self.change is not None and self.child_reads == 2:
            row.update(self.change)
        name = self.image.encode()
        image = D.closed_image(name, name) if permitted is not None and permitted(row) else "UNKNOWN"
        return row, image


def observation(frame):
    return {"schema": 1, "scope": D.SCOPE, "qualification": False, "armedEpochMicroseconds": EPOCH,
            "observerStarted": True, "observerFinished": True,
            "baseline": {"reason": "NONE", "errno": 0, "controller": copy.deepcopy(CONTROLLER), "children": []},
            "frames": [copy.deepcopy(frame), *(D.unknown_frame(i, "STOPPED") for i in range(1, 4))]}


class RuntimeMetadataControls(unittest.TestCase):
    def test_fresh_child_filter_rejects_nonowned_stale_and_ambiguous_candidates(self):
        self.assertEqual((CHILD, "NONE", 1), D.choose_child([CHILD], CONTROLLER, EPOCH, [], None))
        for mutation in ({"uid": 502}, {"parentPid": 11}, {"parentUniqueId": 101},
                         {"parentPidVersion": 4}, {"group": 21}, {"startSeconds": 99}, {"status": 5}):
            with self.subTest(mutation=mutation):
                self.assertEqual((None, "NO_CANDIDATE", 0),
                    D.choose_child([{**CHILD, **mutation}], CONTROLLER, EPOCH, [], None))
        self.assertEqual((None, "NO_CANDIDATE", 0),
            D.choose_child([CHILD], CONTROLLER, EPOCH, [D.lifetime(CHILD)], None))
        other = {**CHILD, "pid": 21, "group": 21, "uniqueId": 201}
        self.assertEqual((None, "AMBIGUOUS", 2), D.choose_child([CHILD, other], CONTROLLER, EPOCH, [], None))
        self.assertEqual((None, "REPLACED", 1),
            D.choose_child([other], CONTROLLER, EPOCH, [], D.lifetime(CHILD)))

        # Supplied libproc inventory includes kernel PID0, as the maintained census allows.
        native = D.ReadOnlyProcesses.__new__(D.ReadOnlyProcesses)
        native.types = D.GATE.audit_processes
        native.proc = mock.Mock()
        calls = []
        def supplied_list(buffer, size):
            calls.append((buffer is None, size))
            if buffer is None:
                return 2
            buffer[0], buffer[1] = 0, CHILD["pid"]
            return 2
        native.proc.proc_listallpids.side_effect = supplied_list
        native.identity = mock.Mock(return_value=(copy.deepcopy(CHILD), "UNKNOWN"))
        with mock.patch.object(D.time, "monotonic", return_value=0.0):
            self.assertEqual([CHILD], native.census(1.0))
        self.assertEqual(2, len(calls))
        native.identity.assert_called_once_with(CHILD["pid"])
        native.identity.side_effect = D.ObservationFailure("IDENTITY_DENIED", 1)
        with mock.patch.object(D.time, "monotonic", return_value=0.0), self.assertRaises(D.ObservationFailure) as caught:
            native.census(1.0)
        self.assertEqual("IDENTITY_DENIED", caught.exception.reason)

    def test_identity_recheck_and_closed_projection(self):
        observer = D.Observer()
        for name, expected in (("xcrun", "XCRUN"), ("simctl", "SIMCTL"), ("private-unexpected-name", "OTHER")):
            with self.subTest(image=expected), mock.patch.object(D.time, "monotonic", return_value=5.101):
                frame, latched = observer._frame(SuppliedNative(name), CONTROLLER, [], EPOCH, 5.0, 0, None)
            self.assertEqual(expected, frame["image"])
            self.assertEqual(D.lifetime(CHILD), latched)
            safe = D.encoded(D.project_observations(observation(frame)))
            for forbidden in (b"private-unexpected-name", b"parentPid", b"uniqueId", b"501", b"identity"):
                self.assertNotIn(forbidden, safe)
            malformed = observation(frame)
            malformed["frames"][0]["recheck"]["uniqueId"] += 1
            with self.assertRaisesRegex(ValueError, "OWNED_RECHECK"):
                D.validate_observations(malformed)
            malformed = observation(frame)
            malformed["frames"][0]["rawName"] = "must-not-escape"
            with self.assertRaisesRegex(ValueError, "KEYS"):
                D.project_observations(malformed)
        for mutation, reason in (({"pidVersion": 2}, "EXEC_CHANGED"), ({"uniqueId": 201}, "REPLACED"),
                                 ({"uid": 502}, "REPLACED")):
            with self.subTest(mutation=mutation), mock.patch.object(D.time, "monotonic", return_value=5.101):
                frame, latched = observer._frame(SuppliedNative(change=mutation), CONTROLLER, [], EPOCH, 5.0, 0, None)
            self.assertEqual(("UNKNOWN", reason), (frame["outcome"], frame["reason"]))
            self.assertEqual(D.lifetime(CHILD), latched)
        for reason in ("ABI_INVALID", "IDENTITY_DENIED"):
            native = SuppliedNative()
            native.census = mock.Mock(side_effect=D.ObservationFailure(reason, 1))
            with mock.patch.object(D.time, "monotonic", return_value=5.101):
                frame, _ = observer._frame(native, CONTROLLER, [], EPOCH, 5.0, 0, None)
            self.assertEqual(reason, frame["reason"])
            D.validate_observations(observation(frame))

    def test_four_frame_schedule_stops_without_retrying_command(self):
        clock, reached = [0.0], []
        class SuppliedStop:
            def __init__(self, stop_after=None):
                self.stop_after, self.stopped = stop_after, False
            def wait(self, seconds):
                if self.stop_after is not None and len(reached) == self.stop_after:
                    self.stopped = True
                    return True
                clock[0] += seconds
                return False
            def is_set(self):
                return self.stopped
        for stop_after, expected in ((None, list(D.TARGET_MILLISECONDS)), (1, [100])):
            clock[0], reached[:] = 0.0, []
            observer = D.Observer()
            observer.stop = SuppliedStop(stop_after)
            observer.armed.set()
            observer.arm_data = (EPOCH, 0.0, True)
            native = SuppliedNative()
            native.census = mock.Mock(return_value=[])
            def supplied_frame(_native, _controller, _baseline, _epoch, _began, index, latched):
                reached.append(round(clock[0] * 1000))
                return D.unknown_frame(index, "NO_CANDIDATE", round(clock[0] * 1000)), latched
            with mock.patch.object(D, "ReadOnlyProcesses", return_value=native), \
                 mock.patch.object(D.os, "getpid", return_value=CONTROLLER["pid"]), \
                 mock.patch.object(D.time, "monotonic", side_effect=lambda: clock[0]), \
                 mock.patch.object(observer, "_frame", side_effect=supplied_frame):
                observer._work()
            self.assertEqual(expected, reached)
            native.census.assert_called_once()  # One baseline; frames are the supplied pure hook.
            self.assertEqual(len(expected), observer.frames.qsize())
        fake = D.Observer()
        fake.arm_data = (EPOCH, 0.0, False)
        fake.start_and_arm = mock.Mock()
        publications = []
        with mock.patch.object(D, "Observer", return_value=fake), \
             mock.patch.object(D.GATE, "_intel_capture_phase", return_value={"supplied": True}) as capture:
            self.assertEqual({"supplied": True}, D.capture_runtime(Path("/synthetic"), publications))
        capture.assert_called_once_with(Path("/synthetic"), "simulator-runtimes",
                                       ["/usr/bin/xcrun", "simctl", "list", "--json", "runtimes"])
        self.assertEqual(1, len(publications))

        workflow = (ROOT / ".github/workflows/ios-x64-tests.yml").read_text()
        for required in ("type: choice", "required: true", "default: runtime-metadata",
                         "runtime-metadata|owned-txt) ;;", "P2PKIT_DIAGNOSTIC_SELECTION_INVALID'; exit 1",
                         "if: ${{ inputs.diagnostic == 'runtime-metadata' }}",
                         "if: ${{ inputs.diagnostic == 'owned-txt' }}",
                         "if: ${{ always() && inputs.diagnostic == 'runtime-metadata' }}",
                         "if: ${{ always() && inputs.diagnostic == 'owned-txt' }}"):
            self.assertIn(required, workflow)
        self.assertEqual(1, workflow.count("scripts/diagnostics/intel-simctl/runtime-list.py"))
        self.assertEqual(1, workflow.count("scripts/diagnostics/intel-lan-host/run.py"))
        self.assertIn("timeout-minutes: 40", workflow)
        self.assertNotIn("cancel-in-progress: true", workflow)
        source = (ROOT / "scripts/diagnostics/intel-simctl/runtime-list.py").read_text()
        tree = ast.parse(source)
        observer_tree = next(item for item in tree.body if isinstance(item, ast.ClassDef) and item.name == "Observer")
        forbidden = {"Popen", "kill", "killpg", "signal", "getenv", "_environment", "_acquire", "DarwinScope"}
        self.assertFalse({node.attr for node in ast.walk(observer_tree) if isinstance(node, ast.Attribute)} & forbidden)

    def test_capture_failure_is_preserved_and_observer_stopped(self):
        for primary in (ValueError("supplied-primary"), KeyboardInterrupt()):
            observer = D.Observer()
            observer.arm_data = (EPOCH, 0.0, False)
            observer.start_and_arm = mock.Mock()
            publications = []
            with mock.patch.object(D, "Observer", return_value=observer), \
                 mock.patch.object(D.GATE, "_intel_capture_phase", side_effect=primary) as capture:
                with self.assertRaises(type(primary)) as caught:
                    D.capture_runtime(Path("/synthetic"), publications)
            self.assertIs(primary, caught.exception)
            self.assertTrue(observer.stop.is_set())
            capture.assert_called_once()
            D.validate_observations(json.loads(publications[0]))

        observer = D.Observer()
        observer.arm_data = (EPOCH, 0.0, False)
        observer.start_and_arm = mock.Mock()
        observer.finish = mock.Mock(side_effect=KeyboardInterrupt())
        primary = ValueError("supplied-primary")
        with mock.patch.object(D, "Observer", return_value=observer), \
             mock.patch.object(D.GATE, "_intel_capture_phase", side_effect=primary):
            with self.assertRaises(ValueError) as caught:
                D.capture_runtime(Path("/synthetic"), [])
        self.assertIs(primary, caught.exception)
        self.assertTrue(observer.stop.is_set())

        # Construction or arming failure must not suppress a primary command.
        for construction in (True, False):
            observer = D.Observer()
            observer.start_and_arm = mock.Mock(side_effect=ValueError("supplied-observer"))
            publications = []
            with mock.patch.object(D, "Observer", side_effect=ValueError("constructor") if construction else None,
                                   return_value=observer), \
                 mock.patch.object(D.GATE, "_intel_capture_phase", return_value={"timedOut": True, "exitCode": -15}) as capture:
                row = D.capture_runtime(Path("/synthetic"), publications)
            self.assertEqual({"timedOut": True, "exitCode": -15}, row)
            capture.assert_called_once()
            self.assertIsNone(json.loads(publications[0])["armedEpochMicroseconds"])

        # Interruption during arming is different: no new command, unconditional stop.
        observer = D.Observer()
        interruption = KeyboardInterrupt()
        observer.start_and_arm = mock.Mock(side_effect=interruption)
        publications = []
        with mock.patch.object(D, "Observer", return_value=observer), \
             mock.patch.object(D.GATE, "_intel_capture_phase") as capture:
            with self.assertRaises(KeyboardInterrupt) as caught:
                D.capture_runtime(Path("/synthetic"), publications)
        self.assertIs(interruption, caught.exception)
        capture.assert_not_called()
        self.assertTrue(observer.stop.is_set())

        # A noninterruptible native read is not claimed stopped or allowed to mutate a publication.
        observer = D.Observer()
        observer.started = True
        observer.arm_data = (EPOCH, 0.0, False)
        observer.thread = mock.Mock()
        observer.thread.is_alive.return_value = True
        result = observer.finish()
        observer.thread.join.assert_called_once_with(D.JOIN_SECONDS)
        self.assertFalse(result["observerFinished"])
        frozen = D.encoded(result)
        observer.frames.put_nowait(D.encoded(D.unknown_frame(0, "NO_CANDIDATE", 100)))
        self.assertEqual(frozen, D.encoded(result))
        D.validate_observations(result)


if __name__ == "__main__":
    unittest.main(verbosity=2, failfast=True)
