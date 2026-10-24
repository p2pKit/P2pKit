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
                }
        }
    }
}
