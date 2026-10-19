#!/usr/bin/env python3
"""Offline admission-evidence refusals; never launches an installed application."""
import copy
import importlib.util
from pathlib import Path
import sys
import types
import unittest

spec = importlib.util.spec_from_file_location("installed_admission", Path(__file__).resolve().parents[1] /
                                             "run-windows-installed-admission.py")
D = importlib.util.module_from_spec(spec)
spec.loader.exec_module(D)


class Clock:
    frequency = 1000
    def now(self):
        return 1000


class AdmissionEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.args = types.SimpleNamespace(expected_source="a" * 40, python=r"C:\admitted\python.exe", operation="admission")
        self.powershell = r"C:\Program Files\PowerShell\7\pwsh.exe"
        self.launcher = r"C:\Program Files\P2pKit Sample\P2pKit Sample.exe"
        self.hashes = {name: "b" * 64 for name in D.SOURCE_FILES}
        self.rows = [dict(pid=index + 1, creationFileTime=index + 100, imagePath=image,
                          firstSeenCounter=1100, exitObservedCounter=4400, exitCode=0, closed=False)
                     for index, image in enumerate((self.powershell, self.args.python, self.args.python, self.launcher))]
        self.retired = True
        self.witnesses = types.SimpleNamespace(evidence=lambda: self.rows, all_exited=lambda: self.retired)
        self.deadline = D.PreparationDeadline(Clock())
        self.observed = dict(schema=1, scope="EXTERNAL_PROCESS_EXIT_OBSERVER_NOT_PROFILE_QUALIFICATION",
            status="PASS", appSource=self.args.expected_source, operation="admission", control=None, stage="RECEIPT",
            phase="CANDIDATE_REQUIRES_OBSERVED_EXTERNAL_EXIT", finalizationCompleted=False,
            supervisorSource={name: self.hashes[name] for name in D.H.SOURCE_FILES},
            observerSource={name: self.hashes[name] for name in
                            ("windows_installed_observer.cs", "run-windows-installed-diagnostic.ps1")},
            startCounter=1000, counterFrequency=1000, deadlineCounter=31000, completedCounter=4000,
            budgetMilliseconds=30000, exitCode=0, processExitObserved=True, originalProcessHandleClosed=True,
            managedProcessClosed=True, capturesClosed=True, captureTasksRetired=True,
            outputExceeded=False, terminationAttempted=False, terminationReturned=False)

    def validate(self, observed=None, exit_counter=4500):
        return D.validate_observer(observed or self.observed, self.args, self.hashes, self.deadline,
                                   self.witnesses, (1, 100), exit_counter, self.powershell, self.launcher)

    def test_matching_original_exit_and_candidate_do_not_need_a_self_certifying_disk_record(self):
        self.assertEqual(self.validate(), 31000)
        self.assertEqual(self.deadline.end, 61000)

    def test_original_thirty_second_boundary_cannot_be_extended_by_preparation_ceiling(self):
        for counter in (31000, 31001, 60999):
            with self.subTest(counter=counter), self.assertRaises(ValueError):
                self.validate(exit_counter=counter)
        self.rows[-1]["exitObservedCounter"] = 31000
        with self.assertRaises(ValueError): self.validate()

    def test_missing_or_wrong_image_cannot_be_replaced_by_console_helper_counts(self):
        for index in range(4):
            with self.subTest(index=index):
                original = self.rows[index]["imagePath"]
                self.rows[index]["imagePath"] = r"C:\Windows\System32\conhost.exe"
                with self.assertRaises(ValueError): self.validate()
                self.rows[index]["imagePath"] = original
        self.rows[0]["creationFileTime"] += 1
        with self.assertRaises(ValueError): self.validate()

    def test_retirement_and_success_fields_require_actual_types_and_values(self):
        for field, invalid in (("schema", True), ("status", "FAIL"), ("appSource", "c" * 40),
            ("operation", "profile-create"), ("operation", None),
            ("counterFrequency", 1001), ("deadlineCounter", 61000), ("completedCounter", 4501),
            ("exitCode", True), ("exitCode", 125), ("processExitObserved", 1),
            ("originalProcessHandleClosed", False), ("managedProcessClosed", False),
            ("capturesClosed", False), ("captureTasksRetired", False), ("outputExceeded", True),
            ("terminationAttempted", True), ("terminationReturned", True), ("finalizationCompleted", True),
            ("phase", "RETURN_REQUIRES_OBSERVED_EXTERNAL_EXIT")):
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.validate({**self.observed, field: invalid})
        self.retired = False
        with self.assertRaises(ValueError): self.validate()

    def test_changed_source_bindings_refuse_admission(self):
        for field in ("supervisorSource", "observerSource"):
            value = copy.deepcopy(self.observed)
            value[field][next(iter(value[field]))] = "f" * 64
            with self.subTest(field=field), self.assertRaises(ValueError): self.validate(value)

    def test_driver_has_no_arbitrary_command_timeout_worker_or_fixture_switch(self):
        args = ["--expected-source", "a" * 40, "--private-parent", str(Path.cwd()), "--python", sys.executable]
        self.assertEqual(D.arguments(args).expected_source, "a" * 40)
        for option in ("--command", "--timeout", "--worker", "--case", "--start-counter", "--help"):
            with self.subTest(option=option), self.assertRaises(ValueError):
                D.arguments(args + [option, "anything"])

    def test_private_failure_detail_has_bounded_frames_and_no_exception_text(self):
        try:
            raise RuntimeError("SECRET_PRIVATE_DETAIL")
        except RuntimeError as error:
            detail = D.failure_detail("OBSERVATION", error)
        self.assertNotIn("SECRET", str(detail))
        self.assertLessEqual(len(detail["frames"]), 12)

    def test_fixed_operation_selection_and_observer_binding(self):
        argv = ["--expected-source", "a" * 40, "--private-parent", str(Path.cwd()), "--python", sys.executable]
        for operation in D.H.OPERATIONS:
            self.assertEqual(D.arguments(argv + ["--operation", operation]).operation, operation)
            self.args.operation = operation
            matching = {**self.observed, "operation": operation}
            self.assertEqual(self.validate(matching), 31000)
            for other in D.H.OPERATIONS.keys() - {operation}:
                with self.assertRaises(ValueError): self.validate({**matching, "operation": other})
        for invalid in ("profile-reset", "profile-create ", "ADMISSION"):
            with self.assertRaises(ValueError): D.arguments(argv + ["--operation", invalid])

    def test_native_selection_requires_its_separate_fixed_payload_binding(self):
        argv = ["--expected-source", "a" * 40, "--private-parent", str(Path.cwd()), "--python", sys.executable]
        extra = ["--native-directory", str(Path.cwd()), "--native-sha256", "b" * 64]
        for operation in D.H.N.OPERATIONS:
            with self.assertRaises(ValueError): D.arguments(argv + ["--operation", operation])
            accepted = D.arguments(argv + ["--operation", operation] + extra)
            self.assertEqual(accepted.native_sha256, "b" * 64)
            self.assertEqual(D.H.N.executable(accepted).name, D.H.N.FILE_NAME)
            accepted.start_counter, accepted.counter_frequency = 1000, 1000
            forwarded = D.H.worker_argv(accepted, Path.cwd() / "run")
            self.assertEqual(forwarded[-4:], extra)
        with self.assertRaises(ValueError): D.arguments(argv + extra)


if __name__ == "__main__":
    unittest.main(failfast=True)
