import P2pKitRpcExample
import SwiftUI

struct RpcPhysicalTestView: View {
    @ObservedObject var model: RpcPhoneModel
    @Environment(\.dismiss) private var dismiss
    @State private var selected = RpcPhysicalTestCatalog.shared.cases[0].id
    @State private var reference = ""
    @State private var notes = ""
    @State private var message = ""
    @State private var exportFile: URL?
    @State private var shareExport = false

    private var center: RpcPhysicalTestSession { model.applicationSession.deviceTests.physicalTests }
    private var test: RpcPhysicalTestCase {
        RpcPhysicalTestCatalog.shared.find(id: center.progress?.caseId ?? selected)
    }

    var body: some View {
        NavigationView {
            Form {
                Section {
                    Text("Run built-in tests or follow a physical procedure. External tools and hardware remain required where shown.")
                    Picker("Physical test", selection: $selected) {
                        ForEach(RpcPhysicalTestCatalog.shared.cases, id: \.id) { item in
                            Text(item.summary).tag(item.id)
                        }
                    }.disabled(center.progress != nil)
                    Text(test.equipment)
                    Text("Method: \(test.tool)")
                }
                Section(test.title) {
                    ForEach(Array(test.steps.enumerated()), id: \.offset) { index, step in
                        Toggle("\(index + 1). \(step)", isOn: Binding(
                            get: { center.progress?.observedSteps.contains { $0.intValue == index } == true },
                            set: { value in action { try center.observeStep(index: Int32(index), observed: value) } }
                        )).disabled(center.progress == nil)
                    }
                    Text("Save: \(test.evidence)")
                    TimelineView(.periodic(from: .now, by: 1)) { _ in
                        Text("Minimum \(test.minimumSeconds)s · observed \(center.elapsedMillis / 1_000)s")
                    }
                    if let phase = test.phase {
                        Button("Run on connected devices") { model.runDeviceTest(phase) }
                            .disabled(center.progress != nil || !model.canAct)
                    } else {
                        Button("Start guided observation") {
                            action { try center.start(caseId: test.id, source: model.compiledSource, platform: "iPhone") }
                        }.disabled(center.progress != nil)
                    }
                }
                if center.progress != nil {
                    Section("Private evidence") {
                        TextField("Evidence reference or saved run IDs", text: $reference)
                            .onChange(of: reference) { if $0.utf8.count > 1_024 { reference = String($0.prefix(256)) } }
                        TextField("What happened / missing setup", text: $notes)
                            .onChange(of: notes) { if $0.utf8.count > 4_096 { notes = String($0.prefix(1_024)) } }
                        Button("Save checkpoint") { action { try center.checkpoint(evidenceReference: reference, notes: notes) } }
                        Button("Save for review") { finish("AwaitingReview") }
                        Button("Record failure") { finish("Failed") }
                        Button("Record missing setup") { finish("Blocked") }
                        Button("End observation") { finish("Interrupted") }
                    }
                }
                Section("Monitor") {
                    Button("Share recent test evidence (up to 100 runs)") {
                        do {
                            try model.physicalTestAction {
                                exportFile = try RpcTestEvidenceExport.write(model.applicationSession.deviceTests)
                            }
                            shareExport = true
                        } catch { message = "Export incomplete; original archives remain retained." }
                    }.disabled(model.deviceTestRunning)
                    if let resources = model.liveTestResources {
                        Text(resources.title)
                        Text(resources.environmentTitle)
                    } else { Text("No live resource sample available.") }
                    Text(message)
                    if let issue = model.deviceTestStorageIssue { Text(issue) }
                    Text("Marked steps are operator observations. Only reviewed evidence establishes qualification.")
                }
            }
            .buttonStyle(.borderless)
            .navigationTitle("Test Center")
            .toolbar { Button("Done") { dismiss() } }
            .sheet(isPresented: $shareExport) { if let file = exportFile { RpcTestEvidenceShare(file: file) } }
        }
    }

    private func finish(_ outcome: String) {
        action { try center.finish(outcome: outcome, evidenceReference: reference, notes: notes) }
    }

    private func action(_ work: () throws -> Void) {
        do {
            try model.physicalTestAction(work)
            message = "Recorded locally. Inspect saved results and storage status."
        } catch { message = "Check steps, duration, evidence reference and storage status. Nothing was marked passed." }
    }
}
