#if DEBUG && P2PKIT_KEYBOARD_REFLOW_PROBE && targetEnvironment(simulator)
import CoreFoundation
import Foundation
import os
import UIKit

// Synthetic header-mechanism fixture, not a reproduction of historical #520.
// No input-view, focus, keyboard preference, AX, or forced-layout intervention.
// A receipt attests only cached native facts; needsNativeLogReview=true because
// the deferred sample must also precede the separately logged XCTest verdict.
@MainActor
final class KeyboardReflowProbe: NSObject {
    struct State {
        let activeRun: Bool
        let hintPresent: Bool
        let otherBannerPresent: Bool
        let browserReady: Bool
    }

    private enum Mode: String { case beforeTarget, duringEditing }
    private enum Phase: String { case armed, scheduled, published, realized, inapplicable }
    private enum Receipt: String { case accepted, inapplicable }
    private enum Event: String {
        case armed, conflict, receipt
        case editingBegan = "editing_began", editingEnded = "editing_ended"
        case mutationScheduled = "mutation_scheduled", mutationWillPublish = "mutation_will_publish"
        case mutationPublished = "mutation_published", mutationDeferred = "mutation_deferred"
        case bannerChanged = "banner_changed", limitReached = "limit_reached"
        case keyboardWillShow = "keyboard_will_show", keyboardDidShow = "keyboard_did_show"
        case keyboardWillHide = "keyboard_will_hide", keyboardDidHide = "keyboard_did_hide"
        case keyboardWillChangeFrame = "keyboard_will_change_frame"
        case keyboardDidChangeFrame = "keyboard_did_change_frame"
    }
    private enum Reason: String {
        case inactiveRun = "inactive_run", unrelatedBanner = "unrelated_banner"
        case hintAlreadyPresent = "hint_already_present", hintRetracted = "hint_retracted"
        case windowNotUnique = "window_not_unique", viewTreeBound = "view_tree_bound"
        case hostNotUnique = "host_not_unique", scrollMissing = "scroll_missing"
        case hostIdentityChanged = "host_identity_changed", hostAlreadyEditing = "host_already_editing"
        case hostNotEditing = "host_not_editing", customInputView = "custom_input_view"
        case invalidGeometry = "invalid_geometry", setterRefused = "setter_refused"
        case beforeTargetSampleLate = "before_target_sample_late"
        case beforeTargetNotRealized = "before_target_not_realized"
        case noContentReflow = "no_content_reflow", eventLimit = "event_limit"
    }
    private enum Selection {
        case host(UITextField, UIWindow, UIScrollView)
        case refused(Reason)
    }
    // Value-only snapshots: never extend a native field/window/scroll lifetime.
    private struct Geometry {
        let uptime: Double
        let contentFrame: CGRect?
        let originalIdentity: Bool
        let firstResponder: Bool
        let line: String
    }

    private static var installed: KeyboardReflowProbe?
    private let logger = Logger(subsystem: "dev.p2pkit.sample.keyboard-cause-probe", category: "reflow")
    private let nonce: String
    private let mode: Mode
    private let readState: @MainActor () -> State
    private let publishHint: @MainActor () -> Bool
    private var lastState: State
    private weak var field: UITextField?
    private weak var window: UIWindow?
    private weak var scroll: UIScrollView?
    private var phase = Phase.armed
    private var reason: Reason?
    private var sequence = 0
    private var logLimitReached = false
    private var receiptSent = false
    private var mutationAttempted = false
    private var didPublish = false
    private var deferredReflow = false
    private var acceptedCached = false
    private var editingCount = 0
    private var firstEditingUptime: Double?
    private var mutationUptime: Double?
    private var deferredUptime: Double?
    private var armContentFrame: CGRect?
    private var beforeContentFrame: CGRect?
    private var deferredContentFrame: CGRect?
    private var lastGeometry: Geometry?

    private init(nonce: String, mode: Mode, state: @escaping @MainActor () -> State,
                 publishHint: @escaping @MainActor () -> Bool) {
        self.nonce = nonce
        self.mode = mode
        self.readState = state
        self.publishHint = publishHint
        self.lastState = state()
        super.init()
    }

    static func armIfRequested(state: @escaping @MainActor () -> State,
                               publishHint: @escaping @MainActor () -> Bool) {
        let process = ProcessInfo.processInfo
        guard installed == nil,
              process.arguments.contains("--p2pkit-ui-test-keyboard-reflow-probe"),
              let rawNonce = process.environment["P2PKIT_KEYBOARD_REFLOW_NONCE"],
              let nonce = UUID(uuidString: rawNonce),
              let rawMode = process.environment["P2PKIT_KEYBOARD_REFLOW_MODE"],
              let mode = Mode(rawValue: rawMode) else { return }
        let probe = KeyboardReflowProbe(nonce: nonce.uuidString, mode: mode,
                                        state: state, publishHint: publishHint)
        installed = probe // Own the unretained C context for the app lifetime.
        probe.install()
    }

    static func bannerChangedIfInstalled() {
        guard let probe = installed else { return }
        probe.updateState()
        probe.record(.bannerChanged)
    }

    private func install() {
        installReceiptObserver()
        let center = NotificationCenter.default
        for name in [UITextField.textDidBeginEditingNotification, UITextField.textDidEndEditingNotification] {
            center.addObserver(self, selector: #selector(editingChanged(_:)), name: name, object: nil)
        }
        for name in [UIResponder.keyboardWillShowNotification, UIResponder.keyboardDidShowNotification,
                     UIResponder.keyboardWillHideNotification, UIResponder.keyboardDidHideNotification,
                     UIResponder.keyboardWillChangeFrameNotification, UIResponder.keyboardDidChangeFrameNotification] {
            center.addObserver(self, selector: #selector(keyboardChanged(_:)), name: name, object: nil)
        }
        switch findHost() {
        case .host(let selectedField, let selectedWindow, let selectedScroll):
            field = selectedField
            window = selectedWindow
            scroll = selectedScroll
        case .refused(let failure):
            record(.armed)
            refuse(failure)
            return
        }
        let geometry = snapshot()
        armContentFrame = geometry.contentFrame
        record(.armed, geometry: geometry)
        updateState()
        guard reason == nil else { return }
        guard field?.isFirstResponder == false else { refuse(.hostAlreadyEditing); return }
        guard field?.inputView == nil else { refuse(.customInputView); return }
        // This call is synchronous inside installRunObservers, before that
        // callback returns and the published port can render for the UI test.
        if mode == .beforeTarget { applyHint() }
    }

    private func findHost() -> Selection {
        let windows = UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }
            .filter { $0.activationState == .foregroundActive }.flatMap(\.windows).filter(\.isKeyWindow)
        guard windows.count == 1, let selectedWindow = windows.first else { return .refused(.windowNotUnique) }
        var pending: [UIView] = [selectedWindow]
        var matches: [UITextField] = []
        var examined = 0
        while let view = pending.popLast() {
            examined += 1
            guard examined <= 4096 else { return .refused(.viewTreeBound) }
            if let textField = view as? UITextField,
               textField.placeholder == "Host (e.g. 192.168.1.42)" { matches.append(textField) }
            pending.append(contentsOf: view.subviews)
        }
        guard matches.count == 1, let selectedField = matches.first,
              selectedField.window === selectedWindow else { return .refused(.hostNotUnique) }
        guard let selectedScroll = nearestScroll(to: selectedField) else { return .refused(.scrollMissing) }
        return .host(selectedField, selectedWindow, selectedScroll)
    }

    private func nearestScroll(to view: UIView) -> UIScrollView? {
        var ancestor = view.superview
        for _ in 0..<128 {
            guard let current = ancestor else { return nil }
            if let found = current as? UIScrollView { return found }
            ancestor = current.superview
        }
        return nil
    }

    private func validateOriginalHost(requireEditing: Bool) -> Bool {
        switch findHost() {
        case .refused(let failure): refuse(failure); return false
        case .host(let selectedField, let selectedWindow, let selectedScroll):
            guard selectedField === field, selectedWindow === window, selectedScroll === scroll else {
                refuse(.hostIdentityChanged); return false
            }
            guard selectedField.inputView == nil else { refuse(.customInputView); return false }
            if requireEditing && !selectedField.isFirstResponder { refuse(.hostNotEditing); return false }
            return true
        }
    }

    @objc private func editingChanged(_ notification: Notification) {
        guard let observed = notification.object as? UITextField,
              observed === field || observed.placeholder == "Host (e.g. 192.168.1.42)" else { return }
        updateState()
        if notification.name == UITextField.textDidEndEditingNotification {
            // Loss of focus after publication is a possible outcome, not a
            // reason to condition the mechanism experiment on preserved focus.
            record(.editingEnded, observed: observed)
            return
        }
        guard notification.name == UITextField.textDidBeginEditingNotification else { return }
        editingCount += 1
        let firstEditing = firstEditingUptime == nil
        if firstEditing { firstEditingUptime = ProcessInfo.processInfo.systemUptime }
        record(.editingBegan, observed: observed)
        guard firstEditing, reason == nil else { return }
        guard observed === field else { refuse(.hostIdentityChanged); return }
        guard validateOriginalHost(requireEditing: true) else { return }
        if mode == .beforeTarget {
            guard deferredReflow else { refuse(.beforeTargetNotRealized); return }
            updateAcceptance()
        } else {
            phase = .scheduled
            record(.mutationScheduled, observed: observed)
            // Exactly one attempt, on the next main turn after actual native
            // Host editing; no timer, tap acknowledgement, or receipt trigger.
            DispatchQueue.main.async { [weak self] in self?.applyHint() }
        }
    }

    private func applyHint() {
        guard !mutationAttempted else { return }
        mutationAttempted = true
        updateState()
        guard reason == nil, validateOriginalHost(requireEditing: mode == .duringEditing) else { return }
        if mode == .beforeTarget && field?.isFirstResponder != false { refuse(.hostAlreadyEditing); return }
        let geometry = snapshot()
        guard geometry.originalIdentity, valid(geometry.contentFrame) else { refuse(.invalidGeometry); return }
        beforeContentFrame = geometry.contentFrame
        record(.mutationWillPublish, geometry: geometry)
        guard publishHint() else { refuse(.setterRefused); return }
        mutationUptime = ProcessInfo.processInfo.systemUptime
        didPublish = true
        phase = .published
        updateState()
        record(.mutationPublished)
        guard reason == nil else { return }
        // This is only a sample, NOT a promise that SwiftUI laid out on this
        // turn. No layoutIfNeeded, animation, polling, or retry repairs a miss.
        DispatchQueue.main.async { [weak self] in self?.measureDeferredReflow() }
    }

    private func measureDeferredReflow() {
        guard didPublish, deferredUptime == nil else { return }
        updateState()
        let ownsOriginal = validateOriginalHost(requireEditing: false)
        let geometry = snapshot()
        deferredUptime = geometry.uptime
        deferredContentFrame = geometry.contentFrame
        if reason == nil {
            if mode == .beforeTarget && firstEditingUptime != nil {
                refuse(.beforeTargetSampleLate)
            } else if !ownsOriginal || !geometry.originalIdentity || !valid(geometry.contentFrame) {
                refuse(.invalidGeometry)
            } else if let before = beforeContentFrame, let after = geometry.contentFrame,
                      after.minY - before.minY >= 1 {
                deferredReflow = true
                phase = .realized
            } else {
                refuse(.noContentReflow)
            }
        }
        updateAcceptance()
        record(.mutationDeferred, geometry: geometry)
    }

    @objc private func keyboardChanged(_ notification: Notification) {
        let event: Event
        switch notification.name {
        case UIResponder.keyboardWillShowNotification: event = .keyboardWillShow
        case UIResponder.keyboardDidShowNotification: event = .keyboardDidShow
        case UIResponder.keyboardWillHideNotification: event = .keyboardWillHide
        case UIResponder.keyboardDidHideNotification: event = .keyboardDidHide
        case UIResponder.keyboardWillChangeFrameNotification: event = .keyboardWillChangeFrame
        case UIResponder.keyboardDidChangeFrameNotification: event = .keyboardDidChangeFrame
        default: return
        }
        updateState()
        record(event,
               keyboardFrame: (notification.userInfo?[UIResponder.keyboardFrameEndUserInfoKey] as? NSValue)?.cgRectValue,
               keyboardLocal: (notification.userInfo?[UIResponder.keyboardIsLocalUserInfoKey] as? NSNumber)?.boolValue,
               keyboardDuration: (notification.userInfo?[UIResponder.keyboardAnimationDurationUserInfoKey] as? NSNumber)?.doubleValue)
    }

    private func updateState() {
        lastState = readState()
        if !lastState.activeRun { refuse(.inactiveRun) }
        else if lastState.otherBannerPresent { refuse(.unrelatedBanner) }
        else if didPublish && !lastState.hintPresent { refuse(.hintRetracted) }
        else if !didPublish && lastState.hintPresent { refuse(.hintAlreadyPresent) }
        // browserReady is intentionally observed, never cleared or suppressed.
        // The real later-ready handler may retract the synthetic hint normally.
        updateAcceptance()
    }

    private func updateAcceptance() {
        acceptedCached = reason == nil && didPublish && deferredReflow && firstEditingUptime != nil &&
            lastState.activeRun && lastState.hintPresent && !lastState.otherBannerPresent
    }

    private func refuse(_ failure: Reason) {
        guard reason == nil else { return }
        reason = failure
        phase = .inapplicable
        acceptedCached = false
        record(.conflict)
    }

    private func name(_ suffix: String) -> CFNotificationName {
        CFNotificationName("dev.p2pkit.sample.keyboard-reflow-probe.\(nonce).\(suffix)" as CFString)
    }

    private func installReceiptObserver() {
        CFNotificationCenterAddObserver(CFNotificationCenterGetDarwinNotifyCenter(),
            Unmanaged.passUnretained(self).toOpaque(), { _, context, notification, _, _ in
                guard let context, let notification else { return }
                let probe = Unmanaged<KeyboardReflowProbe>.fromOpaque(context).takeUnretainedValue()
                let command = notification.rawValue as String
                DispatchQueue.main.async { probe.receive(command) }
            }, name("receipt").rawValue, nil, .deliverImmediately)
    }

    private func receive(_ command: String) {
        guard command == (name("receipt").rawValue as String), !receiptSent else { return }
        receiptSent = true
        let receipt: Receipt = acceptedCached ? .accepted : .inapplicable
        // Read-only, cached evidence only. In particular no readState(),
        // snapshot(), applyHint(), focus/layout, or delayed acceptance repair.
        sequence += 1 // One reserved receipt after at most 96 native events.
        emit(.receipt, geometry: lastGeometry, receipt: receipt)
        CFNotificationCenterPostNotification(CFNotificationCenterGetDarwinNotifyCenter(),
                                            name(receipt.rawValue), nil, nil, true)
        CFNotificationCenterRemoveObserver(CFNotificationCenterGetDarwinNotifyCenter(),
            Unmanaged.passUnretained(self).toOpaque(), name("receipt"), nil)
    }

    private func snapshot(observed: UITextField? = nil) -> Geometry {
        let uptime = ProcessInfo.processInfo.systemUptime
        let current = observed ?? field
        let currentWindow = current?.window
        let currentScroll = current.flatMap { nearestScroll(to: $0) }
        let sameField = current != nil && current === field
        let sameWindow = currentWindow != nil && currentWindow === window
        let sameScroll = currentScroll != nil && currentScroll === scroll
        let nativeInput = current != nil && current?.inputView == nil
        var windowFrame: CGRect?
        var contentFrame: CGRect?
        var scrollWindowFrame: CGRect?
        if let current, let currentWindow { windowFrame = current.convert(current.bounds, to: currentWindow) }
        if let current, let currentScroll { contentFrame = current.convert(current.bounds, to: currentScroll) }
        if let currentScroll, let currentWindow {
            scrollWindowFrame = currentScroll.convert(currentScroll.bounds, to: currentWindow)
        }
        let line = "originalAlive=\(field != nil) originalAttached=\(field?.window != nil) " +
            "sameField=\(sameField) sameWindow=\(sameWindow) sameScroll=\(sameScroll) " +
            "attached=\(currentWindow != nil) firstResponder=\(current?.isFirstResponder ?? false) " +
            "nativeInput=\(nativeInput) keyWindow=\(currentWindow?.isKeyWindow ?? false) " +
            "foreground=\(currentWindow?.windowScene?.activationState == .foregroundActive) " +
            "fieldWindowFrame=\(rect(windowFrame)) fieldContentFrame=\(rect(contentFrame)) " +
            "windowBounds=\(rect(currentWindow?.bounds)) scrollBounds=\(rect(currentScroll?.bounds)) " +
            "scrollWindowFrame=\(rect(scrollWindowFrame)) scrollOffset=\(point(currentScroll?.contentOffset)) " +
            "scrollContentSize=\(size(currentScroll?.contentSize)) scrollInset=\(insets(currentScroll?.contentInset)) " +
            "scrollAdjustedInset=\(insets(currentScroll?.adjustedContentInset)) " +
            "scrollDragging=\(currentScroll?.isDragging ?? false) scrollDecelerating=\(currentScroll?.isDecelerating ?? false)"
        return Geometry(uptime: uptime, contentFrame: contentFrame,
                        originalIdentity: sameField && sameWindow && sameScroll && nativeInput,
                        firstResponder: current?.isFirstResponder ?? false, line: line)
    }

    private func record(_ event: Event, geometry: Geometry? = nil, observed: UITextField? = nil,
                        keyboardFrame: CGRect? = nil, keyboardLocal: Bool? = nil, keyboardDuration: Double? = nil) {
        guard !logLimitReached else { return }
        let measured = geometry ?? snapshot(observed: observed)
        lastGeometry = measured
        sequence += 1
        let admitted = sequence >= 96 ? Event.limitReached : event
        if admitted == .limitReached {
            logLimitReached = true
            reason = reason ?? .eventLimit
            phase = .inapplicable
            acceptedCached = false
            NotificationCenter.default.removeObserver(self)
        }
        emit(admitted, geometry: measured, keyboardFrame: keyboardFrame,
             keyboardLocal: keyboardLocal, keyboardDuration: keyboardDuration)
    }

    private func emit(_ event: Event, geometry: Geometry?, keyboardFrame: CGRect? = nil,
                      keyboardLocal: Bool? = nil, keyboardDuration: Double? = nil, receipt: Receipt? = nil) {
        let delta = geometry?.contentFrame.flatMap { after in beforeContentFrame.map { Double(after.minY - $0.minY) } }
        let line = "P2PKIT_KEYBOARD_REFLOW_V1 nonce=\(nonce) mode=\(mode.rawValue) sequence=\(sequence) " +
            "event=\(event.rawValue) phase=\(phase.rawValue) reason=\(reason?.rawValue ?? "none") " +
            "uptimeSeconds=\(ProcessInfo.processInfo.systemUptime) geometryUptimeSeconds=\(number(geometry?.uptime)) " +
            "firstEditingUptimeSeconds=\(number(firstEditingUptime)) mutationUptimeSeconds=\(number(mutationUptime)) " +
            "deferredUptimeSeconds=\(number(deferredUptime)) editingCount=\(editingCount) " +
            "activeRun=\(lastState.activeRun) hintPresent=\(lastState.hintPresent) " +
            "otherBannerPresent=\(lastState.otherBannerPresent) browserReady=\(lastState.browserReady) " +
            "acceptedCached=\(acceptedCached) needsNativeLogReview=true receiptStatus=\(receipt?.rawValue ?? "none") " +
            "armContentFrame=\(rect(armContentFrame)) mutationBeforeContentFrame=\(rect(beforeContentFrame)) " +
            "deferredContentFrame=\(rect(deferredContentFrame)) deltaContentY=\(number(delta)) " +
            "keyboardFrame=\(rect(keyboardFrame)) keyboardLocal=\(keyboardLocal.map { String($0) } ?? "none") " +
            "keyboardDurationSeconds=\(number(keyboardDuration)) \(geometry?.line ?? "geometry=none")"
        logger.notice("\(line, privacy: .public)")
    }

    private func valid(_ value: CGRect?) -> Bool {
        guard let value, !value.isNull, !value.isInfinite, !value.isEmpty else { return false }
        return [value.minX, value.minY, value.width, value.height].allSatisfy { $0.isFinite }
    }

    private func number(_ value: Double?) -> String {
        guard let value else { return "none" }
        return value.isFinite ? String(value) : "invalid"
    }

    private func rect(_ value: CGRect?) -> String {
        guard let value else { return "none" }
        return [value.minX, value.minY, value.width, value.height].map { number(Double($0)) }.joined(separator: ",")
    }

    private func point(_ value: CGPoint?) -> String {
        guard let value else { return "none" }
        return [value.x, value.y].map { number(Double($0)) }.joined(separator: ",")
    }

    private func size(_ value: CGSize?) -> String {
        guard let value else { return "none" }
        return [value.width, value.height].map { number(Double($0)) }.joined(separator: ",")
    }

    private func insets(_ value: UIEdgeInsets?) -> String {
        guard let value else { return "none" }
        return [value.top, value.left, value.bottom, value.right].map { number(Double($0)) }.joined(separator: ",")
    }
}
#endif
