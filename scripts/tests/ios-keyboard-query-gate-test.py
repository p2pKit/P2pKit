#!/usr/bin/env python3
"""Source tripwires for an opt-in UIKit diagnostic, not native causal evidence.

These tests inspect committed-style Swift source only. They do not compile
UIKit, deliver a notification/tap, measure native query latency, or establish
that a gate was shown, restored, or observed by accessibility on a simulator.
"""
from __future__ import annotations

from pathlib import Path
import re
import sys
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "samples/iosApp/KeyboardQueryGate.swift"
APP = ROOT / "samples/iosApp/P2pKitSampleApp.swift"
COMPILE_GUARD = "#if DEBUG && P2PKIT_KEYBOARD_QUERY_PROBE && targetEnvironment(simulator)"


def without_comments(source: str) -> str:
    # This fixture has no raw/multiline strings or slash-containing literals.
    # Deliberately narrow: these are source tripwires, not a Swift interpreter.
    return re.sub(r"/\*.*?\*/|//[^\n]*", "", source, flags=re.S)


def method(source: str, name: str) -> str:
    # Pin the ordinary four-space method structure; do not match a call site.
    match = re.search(
        rf"^    (?:private )?(?:static )?func {re.escape(name)}\b.*?^    \}}",
        source, flags=re.M | re.S,
    )
    if match is None:
        raise AssertionError(f"Missing source-controlled method: {name}")
    return match.group(0)


class KeyboardQueryGateSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = GATE.read_text(encoding="utf-8")
        cls.code = without_comments(cls.source)
        cls.app = APP.read_text(encoding="utf-8")

    def body(self, name):
        return method(self.code, name)

    def assert_before(self, source, first, second):
        self.assertIn(first, source)
        self.assertIn(second, source)
        self.assertLess(source.index(first), source.index(second))

    def test_entire_gate_and_call_site_require_debug_probe_and_simulator(self):
        self.assertTrue(self.source.startswith(COMPILE_GUARD + "\n"))
        self.assertTrue(self.source.rstrip().endswith("#endif"))
        self.assertEqual(1, self.source.count("#if"))
        self.assertRegex(self.app, re.escape(COMPILE_GUARD) +
                         r"\s+KeyboardQueryGate\.armIfRequested\(\)\s+#endif")
        self.assertEqual(1, self.app.count("KeyboardQueryGate.armIfRequested()"))

    def test_arming_requires_opt_in_uuid_and_closed_delay_set(self):
        arm = self.body("armIfRequested")
        for fragment in (
            "installed == nil",
            'process.arguments.contains("--p2pkit-ui-test-keyboard-query-gate")',
            'process.environment["P2PKIT_KEYBOARD_QUERY_NONCE"]',
            "UUID(uuidString: rawNonce)",
            'process.environment["P2PKIT_KEYBOARD_QUERY_DELAY_MS"]',
            '["0", "100", "2000", "3500", "never", "6000"].contains(rawDelay)',
            "else { return }",
        ):
            self.assert_before(arm, fragment, "let gate = KeyboardQueryGate(")
        self.assertIn("nonce: nonce.uuidString, delay: Int(rawDelay)", arm)

    def test_singleton_owns_c_callback_context_before_observation(self):
        self.assertIn("private static var installed: KeyboardQueryGate?", self.code)
        arm = self.body("armIfRequested")
        self.assert_before(arm, "installed = gate", "gate.observe()")
        self.assertNotIn("installed = nil", self.code)
        observe = self.body("observe")
        self.assertIn("Unmanaged.passUnretained(self).toOpaque()", observe)
        self.assertIn(".fromOpaque(context).takeUnretainedValue()", observe)
        self.assertIn("DispatchQueue.main.async { gate.receive(command) }", observe)
        self.assertRegex(self.code, r"@MainActor\s+final class KeyboardQueryGate")

    def test_nonce_scopes_only_two_exact_install_and_wait_commands(self):
        self.assertIn(r'dev.p2pkit.sample.keyboard-query-gate.\(nonce).\(suffix)',
                      self.body("name"))
        self.assertIn('for suffix in ["install", "wait"]', self.body("observe"))
        receive = self.body("receive")
        self.assertIn('if command == (name("install").rawValue as String) { installGate() }', receive)
        self.assertIn('else if command == (name("wait").rawValue as String) { startRelease() }', receive)
        self.assertNotIn("switch command", receive)
        self.assertNotIn("hasSuffix", receive)
        self.assertNotIn("contains(", receive)

    def test_install_selects_one_foreground_key_window(self):
        install = self.body("installGate")
        for fragment in ("UIApplication.shared.connectedScenes",
                         "$0 as? UIWindowScene", ".foregroundActive", ".isKeyWindow",
                         "windows.count == 1", "let selectedWindow = windows.first"):
            self.assert_before(install, fragment, "selectedField.inputView = gate")
        self.assertNotIn("UIApplication.shared.windows", install)

    def test_hierarchy_walk_is_bounded_and_does_not_pick_first_duplicate(self):
        install = self.body("installGate")
        self.assertIn("guard examined <= 4096", install)
        self.assertIn("pending.append(contentsOf: view.subviews)", install)
        self.assertIn("matches.append(textField)", install)
        self.assertIn("matches.count == 1, let selectedField = matches.first", install)
        self.assert_before(install, "guard examined <= 4096", "matches.append(textField)")
        self.assertNotIn("first(where:", install)

    def test_install_keeps_original_nonfocused_nil_input_view_host(self):
        install = self.body("installGate")
        self.assertIn('textField.placeholder == "Host (e.g. 192.168.1.42)"', install)
        for fragment in ("selectedField.window === selectedWindow",
                         "!selectedField.isFirstResponder", "selectedField.inputView == nil"):
            self.assert_before(install, fragment, "selectedField.inputView = gate")
        self.assertIn("private weak var field: UITextField?", self.code)
        self.assertIn("private weak var window: UIWindow?", self.code)
        self.assertNotIn("textDidBeginEditingNotification", self.code)

    def test_zero_cell_installs_no_gate_and_real_gate_has_no_subcontrols(self):
        install = self.body("installGate")
        self.assert_before(install, "if delay != 0 {", "let gate = UIInputView(")
        self.assertIn("gate.isAccessibilityElement = false", install)
        self.assertIn("gate.accessibilityElementsHidden = true", install)
        self.assertEqual(1, self.code.count("UIInputView(frame:"))
        for constructor in ("UITextField(", "UIButton(", "UILabel(", "addSubview("):
            self.assertNotIn(constructor, self.code)

    def test_install_ack_follows_exact_retained_gate_and_phase_transition(self):
        install = self.body("installGate")
        self.assert_before(install, "guard phase == .armed", "selectedField.inputView = gate")
        self.assert_before(install, "selectedField.inputView = gate",
                           "guard selectedField.inputView === gate")
        self.assert_before(install, "guard selectedField.inputView === gate", "phase = .installed")
        self.assert_before(install, "phase = .installed", 'send("installed")')

    def test_wait_requires_installed_owned_focused_field_before_scheduling(self):
        wait = self.body("startRelease")
        for fragment in ("guard phase == .installed", "guard ownsFocusedField()"):
            self.assert_before(wait, fragment, "phase = .waiting")
        self.assert_before(wait, "phase = .waiting", 'send("received")')
        self.assert_before(wait, 'send("received")', "DispatchQueue.main.asyncAfter(")

    def test_never_has_no_timer_and_other_cells_schedule_once_weakly(self):
        wait = self.body("startRelease")
        self.assert_before(wait, "guard let delay else { return }", "DispatchQueue.main.asyncAfter(")
        self.assertEqual(1, self.code.count("DispatchQueue.main.asyncAfter("))
        self.assertIn(".now() + .milliseconds(delay)", wait)
        self.assertIn("{ [weak self] in", wait)
        self.assertEqual(1, self.code.count("self?.releaseGate()"))
        self.assertNotIn("Timer", self.code)
        self.assertNotIn("CADisplayLink", self.code)

    def test_ownership_means_same_active_window_first_responder_and_exact_gate(self):
        owns = self.body("ownsFocusedField")
        for fragment in ("field.window === window", "window.isKeyWindow",
                         "window.windowScene?.activationState == .foregroundActive",
                         "field.isFirstResponder",
                         "if delay == 0 { return field.inputView == nil }",
                         "inputGate != nil && field.inputView === inputGate"):
            self.assertIn(fragment, owns)

    def test_release_rechecks_ownership_before_its_only_restore(self):
        release = self.body("releaseGate")
        self.assert_before(release, "guard phase == .waiting, ownsFocusedField(), let field",
                           "field.inputView = nil")
        self.assert_before(release, "field.inputView = nil", "field.reloadInputViews()")
        self.assertEqual(1, release.count("field.inputView = nil"))
        self.assertEqual(1, release.count("field.reloadInputViews()"))

    def test_release_ack_requires_focus_and_nil_input_view_after_reload_returns(self):
        release = self.body("releaseGate")
        after_reload = release.split("field.reloadInputViews()", 1)[1]
        for fragment in ("field.window === window", "window.isKeyWindow",
                         "window.windowScene?.activationState == .foregroundActive",
                         "field.isFirstResponder", "field.inputView == nil",
                         'refuse("release_focus_not_preserved")'):
            self.assert_before(after_reload, fragment, "phase = .released")
        self.assert_before(after_reload, "phase = .released", 'send("released")')
        self.assert_before(after_reload, 'send("released")', "retireObservers()")
        self.assertIn("NOT proof of actual key visibility", method(self.source, "releaseGate"))

    def test_refusal_is_terminal_and_restores_only_the_owned_view(self):
        refuse = self.body("refuse")
        self.assert_before(refuse, "guard phase != .refused", "phase = .refused")
        self.assert_before(refuse, "phase = .refused", 'send("refused")')
        self.assert_before(refuse, "retireObservers()", "field.inputView = nil")
        self.assert_before(refuse, "field.inputView === inputGate", "field.inputView = nil")
        self.assertIn("if field.isFirstResponder { field.reloadInputViews() }", refuse)
        self.assertNotIn("installGate()", refuse)
        self.assertNotIn("UIApplication", refuse)

    def test_retirement_removes_every_registered_name_and_clears_owned_list(self):
        observe = self.body("observe")
        retire = self.body("retireObservers")
        self.assertIn("names.append(notification)", observe)
        self.assertIn("for notification in names", retire)
        self.assertIn("CFNotificationCenterRemoveObserver", retire)
        self.assertIn("Unmanaged.passUnretained(self).toOpaque(), notification, nil", retire)
        self.assertIn("names.removeAll()", retire)
        self.assertIn("retireObservers()", self.body("startRelease"))

    def test_telemetry_is_bounded_same_subsystem_and_no_field_values_or_addresses(self):
        self.assertIn('Logger(subsystem: "dev.p2pkit.sample.keyboard-cause-probe"', self.code)
        record = self.body("record")
        self.assert_before(record, "guard sequence < 16", "sequence += 1")
        self.assertIn("ProcessInfo.processInfo.systemUptime", record)
        for forbidden in (".text", ".placeholder", ".description", ".debugDescription",
                          "String(describing:", "ObjectIdentifier", "toOpaque", "UIDevice"):
            self.assertNotIn(forbidden, record)
        bodies = "\n".join(self.body(name) for name in
                           ("observe", "installGate", "startRelease", "releaseGate", "refuse"))
        for argument in re.findall(r"\brecord\(([^)\n]*)\)", bodies):
            self.assertTrue(argument == "reason" or re.fullmatch(r'"[a-z_]+"', argument), argument)
        for argument in re.findall(r"\brefuse\(([^)\n]*)\)", bodies):
            if argument.startswith("_ reason:"):
                continue  # Method declaration, not a call.
            self.assertRegex(argument, r'^"[a-z_]+"$')

    def test_gate_has_no_focus_input_preference_ax_or_private_uikit_fallback(self):
        for forbidden in ("becomeFirstResponder", "resignFirstResponder", "endEditing(",
                          ".typeText(", ".tap(", ".text =", "insertText(", "deleteBackward(",
                          "keyboardType =", "inputMode =", "UIPasteboard", "UserDefaults",
                          "XCUIApplication", "XCUIElement", "NSClassFromString", "UIKeyboard",
                          "method_exchangeImplementations", "setValue(", "layoutIfNeeded("):
            self.assertNotIn(forbidden, self.code)
        self.assertEqual(3, len(re.findall(r"\b(?:selectedField|field)\.inputView\s*=(?!=)", self.code)))
        self.assertEqual(2, self.code.count("field.reloadInputViews()"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
