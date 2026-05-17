// KitController.swift — Swift facade over the P2pKit SDK.
//
// The Kotlin DSL uses lambdas (`P2pKit.create { ... }`). In Swift, those
// arrive as `(P2pKitBuilder) -> KotlinUnit` closures. Helpers here build the
// kit on a background queue and bridge the kit's reactive flows
// (StateFlow<Set<Peer>>, SharedFlow<P2pSession>) into `@Published`
// SwiftUI-friendly state.

import Foundation
import Combine
import SwiftUI

// `P2pKitShared` is the module name set in the framework's
// `binaries.framework { baseName = "P2pKitShared" }` block.
import P2pKitShared

@MainActor
final class KitController: ObservableObject {

    @Published var deviceName: String = "iPhone"
    @Published var appIdValue: String = "p2pkit-desktop-sample"

    @Published private(set) var isRunning: Bool = false
    @Published private(set) var peers: [Peer] = []
    @Published private(set) var sessions: [P2pSession] = []
    @Published private(set) var lastReceived: String = ""

    private var kit: P2pKit?
    private var peerCollector: Task<Void, Never>?
    private var sessionCollector: Task<Void, Never>?

    func start() async {
        guard kit == nil else { return }

        let appId = AppId(value: appIdValue)

        let builtKit = P2pKitCompanion.shared.create { builder -> KotlinUnit in
            builder.appId = appId
            builder.deviceName = self.deviceName
            // `transports { lan() }` — apply { ... } block of TransportsBuilder
            builder.transports { transportsBuilder -> KotlinUnit in
                // `lan()` is the extension declared in IosLanDsl.kt on iOS
                LanIosDslKt.lan(transportsBuilder)
                return KotlinUnit()
            }
            return KotlinUnit()
        }

        kit = builtKit
        isRunning = true

        try? await builtKit.startAdvertising()
        try? await builtKit.startDiscovery()

        // Bridge peers flow → @Published. FlowCollector requires a Kotlin
        // suspending lambda; the simplest path is the helper extension
        // FlowExtensions.watch (which you may have to add to commonMain if
        // not present — see the SDK's iosMain for the canonical pattern).
        // The skeleton below uses a periodic snapshot instead, which avoids
        // wrestling with Flow → AsyncSequence bridging on first build.
        peerCollector = Task { [weak self] in
            while !Task.isCancelled {
                guard let self, let k = await self.kit else { break }
                let snapshot = await k.peers.value as? Set<Peer>
                let asArray = (snapshot ?? []).sorted { $0.name < $1.name }
                await MainActor.run {
                    self.peers = asArray
                }
                try? await Task.sleep(nanoseconds: 1_000_000_000) // 1 s poll
            }
        }
    }

    func stop() async {
        peerCollector?.cancel()
        sessionCollector?.cancel()
        peerCollector = nil
        sessionCollector = nil

        try? await kit?.stop()
        kit = nil
        isRunning = false
        peers = []
        sessions = []
    }

    func connect(_ peer: Peer) async {
        guard let kit else { return }
        do {
            let session = try await kit.connect(peer: peer)
            // Push onto the active-sessions UI list.
            await MainActor.run {
                self.sessions.append(session)
            }
        } catch {
            await MainActor.run {
                self.lastReceived = "connect failed: \(error)"
            }
        }
    }

    func sendText(_ session: P2pSession, _ body: String) async {
        do {
            try await session.send(message: P2pMessageText(value: body))
        } catch {
            await MainActor.run {
                self.lastReceived = "send failed: \(error)"
            }
        }
    }
}
