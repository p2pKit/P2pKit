// P2pKitSampleApp.swift — app entry point
// Drop into a new SwiftUI iOS app target; the framework module is `P2pKitShared`.

import SwiftUI

@main
struct P2pKitSampleApp: App {
    @StateObject private var controller = KitController()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(controller)
        }
    }
}
