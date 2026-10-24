import Foundation

// Investigative metadata only. No field value, arbitrary notification payload,
// device identifier, or keyboard candidate can enter the log vocabulary.
enum KeyboardCauseProbeField: String {
    case none, host, port, pairing, other

    init(placeholder: String?) {
        switch placeholder {
        case "Host (e.g. 192.168.1.42)": self = .host
        case "Port": self = .port
        case "Peer pairing QR text (p2pkit:v2:…)": self = .pairing
        default: self = .other
        }
    }
}

enum KeyboardCauseProbeEvent: String {
    case armed
    case editingBegan, editingEnded
    case keyboardWillShow, keyboardDidShow
    case keyboardWillHide, keyboardDidHide
    case keyboardWillChangeFrame, keyboardDidChangeFrame
    case limitReached
}

struct KeyboardCauseProbeBudget {
    static let maximumEvents = 64
    private(set) var emitted = 0

    mutating func admit(_ event: KeyboardCauseProbeEvent) -> (Int, KeyboardCauseProbeEvent)? {
        guard emitted <= Self.maximumEvents else { return nil }
        emitted += 1
        return (emitted, emitted > Self.maximumEvents ? .limitReached : event)
    }
}

struct KeyboardCauseProbeRecord {
    let sequence: Int
    let event: KeyboardCauseProbeEvent
    let uptime: TimeInterval
    let field: KeyboardCauseProbeField
    let firstResponder: Bool?
    let keyboardIsLocal: Bool?
    let keyboardFrame: CGRect?
    let windowBounds: CGRect?

    var line: String {
        // All strings are closed enums or finite numeric/boolean encodings.
        "KEYBOARD_CAUSE_EVENT sequence=\(sequence) event=\(event.rawValue) " +
            "uptimeSeconds=\(Self.number(uptime)) field=\(field.rawValue) " +
            "firstResponder=\(Self.boolean(firstResponder)) " +
            "keyboardIsLocal=\(Self.boolean(keyboardIsLocal)) " +
            "keyboardFrame=\(Self.rectangle(keyboardFrame)) " +
            "windowBounds=\(Self.rectangle(windowBounds))"
    }

    private static func boolean(_ value: Bool?) -> String {
        value.map { $0 ? "true" : "false" } ?? "UNAVAILABLE"
    }

    private static func number(_ value: Double) -> String {
        value.isFinite && value >= 0 ? String(value) : "UNAVAILABLE"
    }

    private static func rectangle(_ value: CGRect?) -> String {
        guard let value else { return "UNAVAILABLE" }
        let coordinates = [value.origin.x, value.origin.y, value.size.width, value.size.height, value.maxX, value.maxY]
        guard !value.isNull, !value.isInfinite, coordinates.allSatisfy(\.isFinite),
              value.size.width >= 0, value.size.height >= 0 else { return "INVALID" }
        return "\(value.origin.x),\(value.origin.y),\(value.size.width),\(value.size.height)"
    }
}
