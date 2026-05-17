// ContentView.swift — minimal UI surface for the device test checklist.
//
// Lists discovered peers, lets you connect to one, sends a text message.
// Enough to walk through T1.1–T1.5 on a physical iPhone.

import SwiftUI
import P2pKitShared

struct ContentView: View {
    @EnvironmentObject var controller: KitController
    @State private var messageBody: String = "hi from iPhone"

    var body: some View {
        NavigationView {
            VStack(alignment: .leading, spacing: 16) {
                Group {
                    TextField("Device name", text: $controller.deviceName)
                        .textFieldStyle(.roundedBorder)
                        .disabled(controller.isRunning)
                    TextField("App id", text: $controller.appIdValue)
                        .textFieldStyle(.roundedBorder)
                        .autocapitalization(.none)
                        .disabled(controller.isRunning)
                }

                if controller.isRunning {
                    Button("Stop") {
                        Task { await controller.stop() }
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(.red)
                } else {
                    Button("Start") {
                        Task { await controller.start() }
                    }
                    .buttonStyle(.borderedProminent)
                }

                Text("Peers (\(controller.peers.count))")
                    .font(.headline)
                List(controller.peers, id: \.id.value) { peer in
                    HStack {
                        VStack(alignment: .leading) {
                            Text(peer.name).bold()
                            Text(peer.id.value.prefix(8))
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                        Spacer()
                        Button("Connect") {
                            Task { await controller.connect(peer) }
                        }
                        .buttonStyle(.bordered)
                    }
                }
                .frame(maxHeight: 240)

                Text("Active sessions (\(controller.sessions.count))")
                    .font(.headline)
                ForEach(controller.sessions, id: \.id) { session in
                    HStack {
                        Text(session.peer.name).bold()
                        Spacer()
                        TextField("body", text: $messageBody)
                            .textFieldStyle(.roundedBorder)
                            .frame(width: 160)
                        Button("Send") {
                            Task { await controller.sendText(session, messageBody) }
                        }
                        .buttonStyle(.bordered)
                    }
                }

                if !controller.lastReceived.isEmpty {
                    Text("Last: \(controller.lastReceived)")
                        .font(.caption)
                        .foregroundColor(.orange)
                }

                Spacer()
            }
            .padding()
            .navigationTitle("P2pKit Sample")
        }
    }
}
