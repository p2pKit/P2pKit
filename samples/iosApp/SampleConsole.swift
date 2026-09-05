import CryptoKit
import Foundation

/// Data-minimized console fields, not a sanitizer for arbitrary text.
/// Use fixed labels, counts and SDK state names; keep user data in the UI.
/// These hashes support correlation, not unlinkability.
enum SampleConsole {
    static func identifier(_ value: String) -> String {
        let digest = SHA256.hash(data: Data(value.utf8)).map { String(format: "%02x", $0) }.joined()
        return "anon-" + String(digest.prefix(16))
    }

    static func received(peerId: String, isText: Bool, sizeBytes: Int64) -> String {
        "incoming from \(identifier(peerId)): <\(isText ? "text" : "binary") \(sizeBytes)B>"
    }

    static func sendingText(recipients: Int, sizeBytes: Int) -> String {
        "sending <text \(sizeBytes)B> to \(recipients) peer(s) (local send, not remote processing)"
    }

    /// NSError domains, userInfo, localized descriptions and underlying errors can contain user data.
    static func failure(_ error: Error) -> String {
        "errorCode=\((error as NSError).code) (details omitted)"
    }

    /// UI transfer labels may include arbitrary rejection/error text. Emit the fixed state only.
    static func transferState(_ label: String) -> String {
        let states = ["Offered", "Accepted", "Sending", "Completed", "Rejected", "Cancelled", "Failed"]
        return states.first { label == $0 || label.hasPrefix($0 + "(") || label.hasPrefix($0 + ":") || label.hasPrefix($0 + " ") }
            ?? "Unknown"
    }
}
