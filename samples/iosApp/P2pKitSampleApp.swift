import SwiftUI

@main
struct P2pKitSampleApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
                .onAppear {
        #if DEBUG
        KeyboardCauseProbe.armIfRequested()
        #endif
        #if DEBUG && P2PKIT_KEYBOARD_QUERY_PROBE && targetEnvironment(simulator)
        KeyboardQueryGate.armIfRequested()
        #endif
                }
        }
    }
}
