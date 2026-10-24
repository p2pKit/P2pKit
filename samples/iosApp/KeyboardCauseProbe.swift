#if DEBUG
import Foundation
import os
import UIKit

// Explicitly armed only by the opt-in investigative test build. UIKit's
// notifications record the app-side focus/keyboard timeline without an AX
// query, keyboard input, preference mutation, or extra readiness allowance.
@MainActor
final class KeyboardCauseProbe: NSObject {
    private static var installed: KeyboardCauseProbe?
    private let logger = Logger(subsystem: "dev.p2pkit.sample.keyboard-cause-probe", category: "events")
    private var budget = KeyboardCauseProbeBudget()
    private weak var field: UITextField?

    static func armIfRequested() {
        guard installed == nil,
              ProcessInfo.processInfo.arguments.contains("--p2pkit-ui-test-keyboard-cause-probe") else { return }
        let probe = KeyboardCauseProbe()
        installed = probe
        probe.install()
    }

    private func install() {
        let center = NotificationCenter.default
        for name in [UITextField.textDidBeginEditingNotification, UITextField.textDidEndEditingNotification] {
            center.addObserver(self, selector: #selector(editingChanged(_:)), name: name, object: nil)
        }
        for name in [UIResponder.keyboardWillShowNotification, UIResponder.keyboardDidShowNotification,
                     UIResponder.keyboardWillHideNotification, UIResponder.keyboardDidHideNotification,
                     UIResponder.keyboardWillChangeFrameNotification, UIResponder.keyboardDidChangeFrameNotification] {
            center.addObserver(self, selector: #selector(keyboardChanged(_:)), name: name, object: nil)
        }
        record(.armed)
    }

    @objc private func editingChanged(_ notification: Notification) {
        guard let textField = notification.object as? UITextField else { return }
        field = textField
        record(notification.name == UITextField.textDidBeginEditingNotification ? .editingBegan : .editingEnded)
    }

    @objc private func keyboardChanged(_ notification: Notification) {
        let event: KeyboardCauseProbeEvent
        switch notification.name {
        case UIResponder.keyboardWillShowNotification: event = .keyboardWillShow
        case UIResponder.keyboardDidShowNotification: event = .keyboardDidShow
        case UIResponder.keyboardWillHideNotification: event = .keyboardWillHide
        case UIResponder.keyboardDidHideNotification: event = .keyboardDidHide
        case UIResponder.keyboardWillChangeFrameNotification: event = .keyboardWillChangeFrame
        case UIResponder.keyboardDidChangeFrameNotification: event = .keyboardDidChangeFrame
        default: return
        }
        record(event,
               keyboardFrame: (notification.userInfo?[UIResponder.keyboardFrameEndUserInfoKey] as? NSValue)?.cgRectValue,
               keyboardIsLocal: (notification.userInfo?[UIResponder.keyboardIsLocalUserInfoKey] as? NSNumber)?.boolValue)
    }

    private func record(
        _ event: KeyboardCauseProbeEvent,
        keyboardFrame: CGRect? = nil,
        keyboardIsLocal: Bool? = nil
    ) {
        guard let (sequence, admittedEvent) = budget.admit(event) else { return }
        let record = KeyboardCauseProbeRecord(
            sequence: sequence, event: admittedEvent, uptime: ProcessInfo.processInfo.systemUptime,
            field: field.map { KeyboardCauseProbeField(placeholder: $0.placeholder) } ?? .none,
            firstResponder: field?.isFirstResponder, keyboardIsLocal: keyboardIsLocal,
            keyboardFrame: keyboardFrame, windowBounds: field?.window?.bounds
        )
        logger.notice("\(record.line, privacy: .public)")
        if admittedEvent == .limitReached {
            NotificationCenter.default.removeObserver(self)
        }
    }
}
#endif
