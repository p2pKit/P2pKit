#if DEBUG && P2PKIT_KEYBOARD_QUERY_PROBE && targetEnvironment(simulator)
import CoreFoundation
import Foundation
import os
import UIKit

// Investigative fixture only, not readiness or a production input path. Keep
// the actual Host field and its single user tap; delay only UIKit's standard
// input view so native query strategies can be compared against the same event.
@MainActor
final class KeyboardQueryGate {
    private enum Phase: String { case armed, installed, waiting, released, refused }
    private static var installed: KeyboardQueryGate?
    private let logger = Logger(subsystem: "dev.p2pkit.sample.keyboard-cause-probe", category: "query-gate")
    private let nonce: String
    private let delay: Int?
    private var phase = Phase.armed
    private var sequence = 0
    private weak var field: UITextField?
    private weak var window: UIWindow?
    private var inputGate: UIInputView?
    private var names: [CFNotificationName] = []

    private init(nonce: String, delay: Int?) {
        self.nonce = nonce
        self.delay = delay
    }

    static func armIfRequested() {
        let process = ProcessInfo.processInfo
        guard installed == nil, process.arguments.contains("--p2pkit-ui-test-keyboard-query-gate"),
              let rawNonce = process.environment["P2PKIT_KEYBOARD_QUERY_NONCE"],
              let nonce = UUID(uuidString: rawNonce),
              let rawDelay = process.environment["P2PKIT_KEYBOARD_QUERY_DELAY_MS"],
              ["0", "100", "2000", "3500", "never", "6000"].contains(rawDelay) else { return }
        let gate = KeyboardQueryGate(nonce: nonce.uuidString, delay: Int(rawDelay))
        installed = gate // Own the C callback context for the entire app lifetime.
        gate.observe()
    }

    private func name(_ suffix: String) -> CFNotificationName {
        CFNotificationName("dev.p2pkit.sample.keyboard-query-gate.\(nonce).\(suffix)" as CFString)
    }

    private func observe() {
        let center = CFNotificationCenterGetDarwinNotifyCenter()
        for suffix in ["install", "wait"] {
            let notification = name(suffix)
            names.append(notification)
            CFNotificationCenterAddObserver(center, Unmanaged.passUnretained(self).toOpaque(),
                { _, context, name, _, _ in
                    guard let context, let name else { return }
                    let gate = Unmanaged<KeyboardQueryGate>.fromOpaque(context).takeUnretainedValue()
                    let command = name.rawValue as String
                    DispatchQueue.main.async { gate.receive(command) }
                }, notification.rawValue, nil, .deliverImmediately)
        }
        record("armed")
    }

    private func retireObservers() {
        for notification in names {
            CFNotificationCenterRemoveObserver(CFNotificationCenterGetDarwinNotifyCenter(),
                Unmanaged.passUnretained(self).toOpaque(), notification, nil)
        }
        names.removeAll()
    }

    private func send(_ suffix: String) {
        CFNotificationCenterPostNotification(CFNotificationCenterGetDarwinNotifyCenter(), name(suffix), nil, nil, true)
    }

    private func receive(_ command: String) {
        // In a switch pattern, `as String` is a type-cast pattern, not this
        // CFString bridge. Compare explicit String expressions instead.
        if command == (name("install").rawValue as String) { installGate() }
        else if command == (name("wait").rawValue as String) { startRelease() }
    }

    private func installGate() {
        guard phase == .armed else { refuse("duplicate_install"); return }
        let windows = UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }
            .filter { $0.activationState == .foregroundActive }.flatMap(\.windows).filter(\.isKeyWindow)
        guard windows.count == 1, let selectedWindow = windows.first else { refuse("window_not_unique"); return }
        var pending: [UIView] = [selectedWindow]
        var matches: [UITextField] = []
        var examined = 0
        while let view = pending.popLast() {
            examined += 1
            guard examined <= 4096 else { refuse("view_tree_bound"); return }
            if let textField = view as? UITextField,
               textField.placeholder == "Host (e.g. 192.168.1.42)" { matches.append(textField) }
            pending.append(contentsOf: view.subviews)
        }
        guard matches.count == 1, let selectedField = matches.first,
              selectedField.window === selectedWindow, !selectedField.isFirstResponder,
              selectedField.inputView == nil else { refuse("host_not_admissible"); return }
        field = selectedField
        window = selectedWindow
        if delay != 0 {
            let gate = UIInputView(frame: CGRect(x: 0, y: 0, width: selectedWindow.bounds.width, height: 260),
                                   inputViewStyle: .keyboard)
            gate.isAccessibilityElement = false
            gate.accessibilityElementsHidden = true
            inputGate = gate
            selectedField.inputView = gate
            guard selectedField.inputView === gate else { refuse("install_not_retained"); return }
        }
        phase = .installed
        record("installed")
        send("installed")
    }

    private func startRelease() {
        guard phase == .installed else { refuse("duplicate_wait"); return }
        guard ownsFocusedField() else { refuse("wait_ownership_lost"); return }
        phase = .waiting
        record("received")
        send("received")
        guard let delay else { return } // Never cell: no delayed mutation is scheduled.
        if delay == 0 {
            phase = .released
            record("no_gate")
            send("released")
            retireObservers()
        } else {
            DispatchQueue.main.asyncAfter(deadline: .now() + .milliseconds(delay)) { [weak self] in
                self?.releaseGate()
            }
        }
    }

    private func ownsFocusedField() -> Bool {
        guard let field, let window, field.window === window, window.isKeyWindow,
              window.windowScene?.activationState == .foregroundActive, field.isFirstResponder else { return false }
        if delay == 0 { return field.inputView == nil }
        return inputGate != nil && field.inputView === inputGate
    }

    private func releaseGate() {
        guard phase == .waiting, ownsFocusedField(), let field else { refuse("release_ownership_lost"); return }
        // The original was nil. Never install a successor field, force focus,
        // synthesize input or use a value/tap retry to satisfy an observation.
        field.inputView = nil
        field.reloadInputViews()
        guard let window, field.window === window, window.isKeyWindow,
              window.windowScene?.activationState == .foregroundActive,
              field.isFirstResponder, field.inputView == nil else { refuse("release_focus_not_preserved"); return }
        phase = .released
        record("released")
        send("released") // Setter/reload return, NOT proof of actual key visibility.
        retireObservers()
    }

    private func refuse(_ reason: String) {
        guard phase != .refused else { return }
        phase = .refused
        record(reason)
        send("refused")
        retireObservers()
        // Do not overwrite a replacement input view or retarget a successor.
        if let field, let inputGate, field.inputView === inputGate {
            field.inputView = nil
            if field.isFirstResponder { field.reloadInputViews() }
        }
    }

    private func record(_ event: String) {
        // Closed source-owned events plus a generated UUID and booleans/numbers.
        // No text-field contents, device identifiers or arbitrary error strings.
        guard sequence < 16 else { return }
        sequence += 1
        let line = "KEYBOARD_QUERY_GATE_EVENT nonce=\(nonce) sequence=\(sequence) event=\(event) " +
            "phase=\(phase.rawValue) uptimeSeconds=\(ProcessInfo.processInfo.systemUptime) " +
            "delayMillis=\(delay.map(String.init) ?? "never") " +
            "attached=\(field?.window != nil) firstResponder=\(field?.isFirstResponder ?? false) " +
            "ownsGate=\(inputGate != nil && field?.inputView === inputGate)"
        logger.notice("\(line, privacy: .public)")
    }
}
#endif
