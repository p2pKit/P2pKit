#!/usr/bin/env python3
"""Portable source tripwires, not native reflow or historical causal evidence.

These checks do not compile UIKit, render a banner, deliver an editing event,
prove a deferred sample occurred before XCTest's verdict, or qualify a device.
The opt-in native run and its retained timestamped evidence remain necessary.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
import sys
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
PROBE = ROOT / "samples/iosApp/KeyboardReflowProbe.swift"
CONTENT = ROOT / "samples/iosApp/ContentView.swift"
GUARD = "#if DEBUG && P2PKIT_KEYBOARD_REFLOW_PROBE && targetEnvironment(simulator)"
BASELINE_CONTENT_SHA256 = "c8129ea4bc1aafae91f6706ed9d63f69b1d32eb5d35539396f72d3bc0705c35d"


def without_comments(source: str) -> str:
    # Deliberately limited to these ordinary source-controlled Swift strings.
    # This is not a Swift parser and cannot replace the real-SDK typecheck.
    return re.sub(r"/\*.*?\*/|//[^\n]*", "", source, flags=re.S)


def method(source: str, name: str) -> str:
    match = re.search(
        rf"^    (?:(?:private|static|@objc) )*func {re.escape(name)}\b.*?^    \}}",
        source, flags=re.M | re.S,
    )
    if match is None:
        raise AssertionError(f"Missing source-controlled method: {name}")
    return match.group(0)


def hook(source: str, kind: str) -> str:
    match = re.search(
        rf"^ +// KEYBOARD_REFLOW_PROBE_{kind}_HOOK_BEGIN\n.*?"
        rf"^ +// KEYBOARD_REFLOW_PROBE_{kind}_HOOK_END\n",
        source, flags=re.M | re.S,
    )
    if match is None:
        raise AssertionError(f"Missing bounded hook: {kind}")
    return match.group(0)


class KeyboardReflowProbeSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = PROBE.read_text(encoding="utf-8")
        cls.code = without_comments(cls.source)
        cls.content = CONTENT.read_text(encoding="utf-8")

    def body(self, name):
        return method(self.code, name)

    def assert_before(self, source, first, second):
        self.assertIn(first, source)
        self.assertIn(second, source)
        self.assertLess(source.index(first), source.index(second))

    def test_helper_and_both_hooks_are_debug_opt_in_simulator_only(self):
        self.assertTrue(self.source.startswith(GUARD + "\n"))
        self.assertTrue(self.source.rstrip().endswith("#endif"))
        self.assertEqual(1, self.source.count("#if"))
        for kind in ("RUN", "VIEW"):
            bounded = hook(self.content, kind)
            self.assertEqual(1, bounded.count(GUARD))
            self.assertEqual(1, bounded.count("#endif"))
        self.assertEqual(1, self.content.count("KeyboardReflowProbe.armIfRequested("))
        self.assertEqual(1, self.content.count("KeyboardReflowProbe.bannerChangedIfInstalled()"))

    def test_outside_two_marked_hooks_content_is_exact_69fd925d_baseline(self):
        normalized = self.content
        for kind in ("RUN", "VIEW"):
            normalized = normalized.replace(hook(normalized, kind), "", 1)
        self.assertEqual(BASELINE_CONTENT_SHA256, hashlib.sha256(normalized.encode()).hexdigest())

    def test_launch_requires_argument_uuid_and_exact_two_mode_enum(self):
        arm = self.body("armIfRequested")
        for fragment in (
            "installed == nil",
            'process.arguments.contains("--p2pkit-ui-test-keyboard-reflow-probe")',
            'process.environment["P2PKIT_KEYBOARD_REFLOW_NONCE"]',
            "UUID(uuidString: rawNonce)",
            'process.environment["P2PKIT_KEYBOARD_REFLOW_MODE"]',
            "Mode(rawValue: rawMode)",
        ):
            self.assert_before(arm, fragment, "let probe = KeyboardReflowProbe(")
        self.assertIn("private enum Mode: String { case beforeTarget, duringEditing }", self.code)
        self.assertIn("nonce: nonce.uuidString, mode: mode", arm)
        self.assertRegex(self.code, r"@MainActor\s+final class KeyboardReflowProbe: NSObject")

    def test_run_hook_is_first_and_setter_independently_fences_empty_banner(self):
        run = hook(self.content, "RUN")
        for fragment in ("activeRun: self.runLifecycle.acceptsWork(run)",
                         "hintPresent: self.errorBanner == Self.localNetworkHint",
                         "otherBannerPresent: self.errorBanner != nil && self.errorBanner != Self.localNetworkHint",
                         "browserReady: self.browserEverReady"):
            self.assertIn(fragment, run)
        setter = run.split("publishHint: {", 1)[1]
        self.assert_before(setter, "guard self.runLifecycle.acceptsWork(run), self.errorBanner == nil",
                           "self.errorBanner = Self.localNetworkHint")
        self.assertEqual(1, setter.count("self.errorBanner = Self.localNetworkHint"))
        self.assertNotIn("browserEverReady =", run)
        observers = self.content.split("private func installRunObservers(", 1)[1]
        self.assertRegex(observers, r"runLifecycle\.withActiveRun\(run\) \{\s*"
                         r"// KEYBOARD_REFLOW_PROBE_RUN_HOOK_BEGIN")
        self.assert_before(observers, "KeyboardReflowProbe.armIfRequested(", "let incoming = OwnedFlowCollection")

    def test_before_target_publication_is_synchronous_inside_install(self):
        install = self.body("install")
        self.assertIn("if mode == .beforeTarget { applyHint() }", install)
        for forbidden in ("Task", "async", "sleep", "Timer", "receiptSent"):
            self.assertNotIn(forbidden, install)
        self.assert_before(install, "updateState()", "if mode == .beforeTarget { applyHint() }")
        self.assert_before(install, "field?.isFirstResponder == false", "applyHint()")

    def test_actual_unique_host_editing_alone_schedules_dynamic_mutation_once(self):
        editing = self.body("editingChanged")
        self.assertIn("notification.object as? UITextField", editing)
        self.assertIn("UITextField.textDidBeginEditingNotification", editing)
        self.assertIn("UITextField.textDidEndEditingNotification", editing)
        for fragment in ("let firstEditing = firstEditingUptime == nil",
                         "guard firstEditing, reason == nil",
                         "guard observed === field",
                         "guard validateOriginalHost(requireEditing: true)"):
            self.assert_before(editing, fragment, "self?.applyHint()")
        self.assertIn("DispatchQueue.main.async { [weak self] in self?.applyHint() }", editing)
        self.assertEqual(1, self.code.count("self?.applyHint()"))
        self.assertIn("guard deferredReflow else { refuse(.beforeTargetNotRealized); return }", editing)

    def test_only_publication_attempt_rechecks_state_scope_and_native_geometry(self):
        apply = self.body("applyHint")
        for fragment in ("guard !mutationAttempted", "mutationAttempted = true", "updateState()",
                         "guard reason == nil, validateOriginalHost(requireEditing: mode == .duringEditing)",
                         "guard geometry.originalIdentity, valid(geometry.contentFrame)"):
            self.assert_before(apply, fragment, "guard publishHint()")
        self.assertEqual(1, self.code.count("guard publishHint()"))
        self.assert_before(apply, "guard publishHint()", "didPublish = true")
        self.assert_before(apply, "didPublish = true", "self?.measureDeferredReflow()")
        self.assertIn("DispatchQueue.main.async { [weak self] in self?.measureDeferredReflow() }", apply)
        self.assertEqual(1, self.code.count("self?.measureDeferredReflow()"))

    def test_native_selection_requires_single_foreground_key_window_unique_host(self):
        lookup = self.body("findHost")
        for fragment in ("UIApplication.shared.connectedScenes", "$0 as? UIWindowScene",
                         ".foregroundActive", ".isKeyWindow", "windows.count == 1",
                         "guard examined <= 4096", "pending.append(contentsOf: view.subviews)",
                         'textField.placeholder == "Host (e.g. 192.168.1.42)"',
                         "matches.count == 1", "selectedField.window === selectedWindow"):
            self.assertIn(fragment, lookup)
        self.assertNotIn("first(where:", lookup)
        self.assertIn("for _ in 0..<128", self.body("nearestScroll"))
        validate = self.body("validateOriginalHost")
        for fragment in ("selectedField === field", "selectedWindow === window", "selectedScroll === scroll",
                         "selectedField.inputView == nil", "requireEditing && !selectedField.isFirstResponder"):
            self.assertIn(fragment, validate)

    def test_native_objects_are_weak_and_snapshots_do_not_retain_them(self):
        for declaration in ("private weak var field: UITextField?", "private weak var window: UIWindow?",
                            "private weak var scroll: UIScrollView?"):
            self.assertIn(declaration, self.code)
        geometry = self.code.split("private struct Geometry {", 1)[1].split("\n    }", 1)[0]
        for native in ("UITextField", "UIWindow", "UIScrollView", "UIView"):
            self.assertNotIn(native, geometry)
        self.assertIn("private static var installed: KeyboardReflowProbe?", self.code)
        self.assert_before(self.body("armIfRequested"), "installed = probe", "probe.install()")
        self.assertNotIn("installed = nil", self.code)

    def test_geometry_reports_window_content_coordinates_and_scroll_offsets(self):
        snapshot = self.body("snapshot")
        for fragment in ("current.convert(current.bounds, to: currentWindow)",
                         "current.convert(current.bounds, to: currentScroll)",
                         "currentScroll.convert(currentScroll.bounds, to: currentWindow)",
                         "currentScroll?.contentOffset", "currentScroll?.bounds", "currentScroll?.contentSize",
                         "currentScroll?.contentInset", "currentScroll?.adjustedContentInset"):
            self.assertIn(fragment, snapshot)
        for key in ("sameField=", "sameWindow=", "sameScroll=", "firstResponder=", "originalAlive=",
                    "originalAttached=", "fieldWindowFrame=", "fieldContentFrame=", "scrollOffset=",
                    "scrollBounds=", "scrollWindowFrame=", "scrollContentSize=", "scrollAdjustedInset="):
            self.assertIn(key, snapshot)
        emit = self.body("emit")
        for key in ("armContentFrame=", "mutationBeforeContentFrame=", "deferredContentFrame=", "deltaContentY="):
            self.assertIn(key, emit)

    def test_one_deferred_sample_requires_real_downward_content_reflow(self):
        deferred = self.body("measureDeferredReflow")
        self.assertIn("guard didPublish, deferredUptime == nil", deferred)
        self.assertIn("validateOriginalHost(requireEditing: false)", deferred)
        self.assertIn("mode == .beforeTarget && firstEditingUptime != nil", deferred)
        self.assertIn("refuse(.beforeTargetSampleLate)", deferred)
        self.assertIn("!ownsOriginal || !geometry.originalIdentity || !valid(geometry.contentFrame)", deferred)
        self.assert_before(deferred, "after.minY - before.minY >= 1", "deferredReflow = true")
        self.assertIn("refuse(.noContentReflow)", deferred)
        self.assertIn("!value.isNull, !value.isInfinite, !value.isEmpty", self.body("valid"))
        self.assertIn(".allSatisfy { $0.isFinite }", self.body("valid"))
        self.assertNotIn("geometry.firstResponder", deferred)
        self.assertNotIn("DispatchQueue", deferred)

    def test_inactive_run_unrelated_banner_existing_hint_and_retraction_refuse(self):
        update = self.body("updateState")
        for fragment in ("lastState = readState()", "!lastState.activeRun", "refuse(.inactiveRun)",
                         "lastState.otherBannerPresent", "refuse(.unrelatedBanner)",
                         "didPublish && !lastState.hintPresent", "refuse(.hintRetracted)",
                         "!didPublish && lastState.hintPresent", "refuse(.hintAlreadyPresent)"):
            self.assertIn(fragment, update)
        self.assertNotIn("browserReady", update)
        refuse = self.body("refuse")
        self.assert_before(refuse, "guard reason == nil", "reason = failure")
        self.assertIn("acceptedCached = false", refuse)
        self.assertNotIn("publishHint", refuse)

    def test_acceptance_requires_cached_publication_reflow_and_actual_editing(self):
        acceptance = self.body("updateAcceptance")
        for fragment in ("reason == nil", "didPublish", "deferredReflow", "firstEditingUptime != nil",
                         "lastState.activeRun", "lastState.hintPresent", "!lastState.otherBannerPresent"):
            self.assertIn(fragment, acceptance)
        self.assertNotIn("firstResponder", acceptance)
        self.assertIn("needsNativeLogReview=true", self.body("emit"))
        self.assertIn("separately logged XCTest verdict", self.source)
        for key in ("geometryUptimeSeconds=", "firstEditingUptimeSeconds=", "mutationUptimeSeconds=",
                    "deferredUptimeSeconds=", "uptimeSeconds="):
            self.assertIn(key, self.body("emit"))

    def test_receipt_is_nonce_scoped_single_read_only_cached_reply(self):
        self.assertIn(r'dev.p2pkit.sample.keyboard-reflow-probe.\(nonce).\(suffix)', self.body("name"))
        self.assertIn('name("receipt").rawValue, nil, .deliverImmediately', self.body("installReceiptObserver"))
        self.assertIn("private enum Receipt: String { case accepted, inapplicable }", self.code)
        receive = self.body("receive")
        self.assertIn('guard command == (name("receipt").rawValue as String), !receiptSent', receive)
        self.assertIn("let receipt: Receipt = acceptedCached ? .accepted : .inapplicable", receive)
        self.assertIn("emit(.receipt, geometry: lastGeometry, receipt: receipt)", receive)
        self.assertIn("CFNotificationCenterRemoveObserver", receive)
        for forbidden in ("readState()", "updateState()", "snapshot(", "applyHint(", "measureDeferredReflow(",
                          "validateOriginalHost(", "findHost(", "Task", "async", "Timer", "sleep"):
            self.assertNotIn(forbidden, receive)
        observer = self.body("installReceiptObserver")
        self.assertIn("Unmanaged.passUnretained(self).toOpaque()", observer)
        self.assertIn(".fromOpaque(context).takeUnretainedValue()", observer)
        self.assertIn("DispatchQueue.main.async { probe.receive(command) }", observer)
        self.assertNotIn("switch command", receive)

    def test_keyboard_and_banner_observation_does_not_schedule_actions(self):
        keyboard = self.body("keyboardChanged")
        for event in ("keyboardWillShowNotification", "keyboardDidShowNotification", "keyboardWillHideNotification",
                      "keyboardDidHideNotification", "keyboardWillChangeFrameNotification", "keyboardDidChangeFrameNotification",
                      "keyboardFrameEndUserInfoKey", "keyboardIsLocalUserInfoKey", "keyboardAnimationDurationUserInfoKey"):
            self.assertIn(event, keyboard)
        for body in (keyboard, self.body("bannerChangedIfInstalled")):
            for forbidden in ("applyHint(", "DispatchQueue", "Task", "publishHint("):
                self.assertNotIn(forbidden, body)
        view = hook(self.content, "VIEW")
        self.assertIn(".onChange(of: errorBanner)", view)
        self.assertIn("KeyboardReflowProbe.bannerChangedIfInstalled()", view)

    def test_events_are_closed_bounded_and_use_existing_public_numeric_subsystem(self):
        record = self.body("record")
        self.assert_before(record, "guard !logLimitReached", "snapshot(observed: observed)")
        self.assertIn("sequence >= 96 ? Event.limitReached : event", record)
        self.assertIn("acceptedCached = false", record)
        self.assertIn("NotificationCenter.default.removeObserver(self)", record)
        self.assertIn('Logger(subsystem: "dev.p2pkit.sample.keyboard-cause-probe"', self.code)
        self.assertIn("_ event: Event", record)
        self.assertIn("_ failure: Reason", self.body("refuse"))
        self.assertIn('P2PKIT_KEYBOARD_REFLOW_V1 nonce=', self.body("emit"))
        for body in (self.body("snapshot"), self.body("emit")):
            for forbidden in (".text", ".placeholder", ".description", ".debugDescription", "ObjectIdentifier",
                              "String(describing:", "toOpaque", "UIDevice"):
                self.assertNotIn(forbidden, body)

    def test_no_input_focus_preference_ax_forced_layout_animation_or_retry_intervention(self):
        for forbidden in ("becomeFirstResponder", "resignFirstResponder", "endEditing(", "reloadInputViews",
                          "UIInputView(", ".typeText(", ".tap(", "insertText(", "deleteBackward(",
                          "UIPasteboard", "UserDefaults", "XCUIApplication", "XCUIElement", "NSClassFromString",
                          "method_exchangeImplementations", "setValue(", "layoutIfNeeded(", "setNeedsLayout(",
                          "withAnimation", "UIView.animate", "asyncAfter", "Task.sleep", "Timer", "CADisplayLink"):
            self.assertNotIn(forbidden, self.code)
        self.assertIsNone(re.search(r"\.(?:inputView|text|keyboardType|inputMode|contentOffset)\s*=(?!=)", self.code))


if __name__ == "__main__":
    unittest.main(verbosity=2)
