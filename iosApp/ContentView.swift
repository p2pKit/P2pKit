import SwiftUI
import P2pKitShared

struct ContentView: View {
    @State private var status: String = "Not started"
    @State private var localPeerId: String = ""
    @State private var localDeviceName: String = "iPhone"
    @State private var peers: [String] = []
    @State private var kit: P2pKit?

    var body: some View {
        VStack(spacing: 16) {
            Text("P2pKit v0.3 Sample")
                .font(.title)
                .padding(.top, 32)

            Text("Status: \(status)")
                .foregroundColor(.secondary)

            if !localPeerId.isEmpty {
                Text("Local peer id:")
                    .font(.caption)
                Text(localPeerId)
                    .font(.system(.caption, design: .monospaced))
                    .padding(.horizontal)
                    .multilineTextAlignment(.center)
            }

            TextField("Device name", text: $localDeviceName)
                .textFieldStyle(.roundedBorder)
                .padding(.horizontal)
                .disabled(kit != nil)

            HStack(spacing: 12) {
                if kit == nil {
                    Button("Start") { Task { await start() } }
                        .buttonStyle(.borderedProminent)
                } else {
                    Button("Stop") { Task { await stop() } }
                        .buttonStyle(.borderedProminent)
                        .tint(.red)
                }
            }

            Text("Peers (\(peers.count))")
                .font(.headline)
                .padding(.top, 8)
            List(peers, id: \.self) { p in
                Text(p)
            }
            .frame(maxHeight: 240)

            Spacer()
        }
        .padding()
    }

    @MainActor
    private func start() async {
        status = "Starting…"

        // P2pKit.create { ... } in Kotlin → P2pKitCompanion.shared.create(block:)
        // in Swift. The block is `(P2pKitBuilder) -> Void` — no KotlinUnit
        // dance needed, Kotlin/Native bridges void blocks transparently.
        let built = P2pKitCompanion.shared.create { (builder: P2pKitBuilder) in
            // AppId / PeerId are Kotlin `value class`es wrapping String.
            // Kotlin/Native's ObjC bridge accepts the raw NSString and
            // re-wraps it internally; no AppId Swift type is exported.
            builder.appId = "p2pkit-desktop-sample"
            builder.deviceName = self.localDeviceName
            builder.transports { (tx: TransportsBuilder) in
                // `fun TransportsBuilder.lan()` extension → instance method
                // on TransportsBuilder in Swift.
                tx.lan()
            }
        }

        self.kit = built
        // `localPeerId` is a value class too; Kotlin/Native returns it as `id`
        // / Any?. Cast to NSString and read; failing that, render the
        // description.
        if let pidAny = built.localPeerId as Any?,
           let pidString = pidAny as? String {
            self.localPeerId = pidString
        } else {
            self.localPeerId = "\(built.localPeerId)"
        }

        do {
            try await built.startAdvertising()
            try await built.startDiscovery()
            status = "Running"
        } catch {
            status = "Start failed: \(error)"
            return
        }

        // Polling: full Flow → AsyncSequence bridging is a follow-up.
        Task { @MainActor in
            while self.kit != nil {
                let peerSet = built.peers.value
                if let set = peerSet as? Set<AnyHashable> {
                    let names = set.compactMap { ($0 as? Peer)?.name }.sorted()
                    self.peers = names
                }
                try? await Task.sleep(nanoseconds: 1_000_000_000)
            }
        }
    }

    @MainActor
    private func stop() async {
        guard let k = kit else { return }
        status = "Stopping…"
        try? await k.stop()
        kit = nil
        peers = []
        localPeerId = ""
        status = "Stopped"
    }
}
