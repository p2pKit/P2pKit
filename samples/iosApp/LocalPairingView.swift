import SwiftUI

/// Explicit operator UI only. The QR is public identity, but is identifying and must not enter diagnostics.
struct LocalPairingView: View {
    let qr: String
    @State private var isRevealed = false

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Button(isRevealed ? "Hide local pairing information" : "Show local pairing information") {
                isRevealed.toggle()
            }
            .accessibilityIdentifier("show-local-pairing")
            if isRevealed {
                Text("Share with the intended peer through a trusted channel. Do not include in diagnostic exports.")
                    .font(.caption)
                Text("Local pairing QR text")
                    .font(.caption.bold())
                Text(qr)
                    .font(.system(.caption, design: .monospaced))
                    .environment(\.layoutDirection, .leftToRight)
                    .fixedSize(horizontal: false, vertical: true)
                    .textSelection(.enabled)
                    .accessibilityIdentifier("local-pairing-qr")
                Text("This sample still accepts incoming same-AppId peers; exchanging a QR does not change that policy.")
                    .font(.caption)
            }
        }
    }
}
