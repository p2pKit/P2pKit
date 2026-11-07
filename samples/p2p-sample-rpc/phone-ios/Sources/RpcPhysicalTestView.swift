import P2pKitRpcExample
import SwiftUI

struct RpcPhysicalTestView: View {
    @ObservedObject var model: RpcPhoneModel
    let openWorkload: () -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var selected = RpcPhysicalTestCatalog.shared.cases[0].id
    @State private var reference = ""
    @State private var notes = ""
    @State private var message = ""
    @State private var exportFile: URL?
    @State private var shareExport = false
    @State private var archivePage: RpcTestArchivePage?
    @State private var archiveTask: Task<Void, Never>?
    @State private var archiveBusy = false
    @State private var choosingCase = false
    @State private var caseFilter = ""

    private var center: RpcPhysicalTestSession { model.applicationSession.deviceTests.physicalTests }
    private var test: RpcPhysicalTestCase {
        RpcPhysicalTestCatalog.shared.find(id: center.progress?.caseId ?? selected)
    }

    var body: some View {
        NavigationView {
            Form {
                Section {
                    Text("Run built-in tests or follow a physical procedure. External tools and hardware remain required where shown.")
                    Button("Physical test: " + test.summary) { choosingCase = true }
                        .disabled(center.progress != nil).accessibilityIdentifier("rpc.physicalCase")
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
                    if test.phase != nil {
                        Button("Open RPC test controls") { dismiss(); openWorkload() }
                            .disabled(center.progress != nil || model.deviceTestRunning)
                    } else {
                        Button("Start guided observation") {
                            action { try center.start(caseId: test.id, source: model.compiledSource, platform: "iPhone") }
                        }.disabled(center.progress != nil).accessibilityIdentifier("rpc.observationStart")
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
                        Button("End observation") { finish("Interrupted") }.accessibilityIdentifier("rpc.observationEnd")
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
                Section("Saved test archive") {
                    Button("Load newest saved results") { browseArchive() }
                        .disabled(archiveBusy || model.deviceTestRunning)
                    if let page = archivePage {
                        ForEach(page.reports, id: \.runId) { report in
                            DisclosureGroup(report.title) {
                                Text(report.detail).textSelection(.enabled)
                                Button("Share this output") { exportArchive(report.runId) }
                                    .disabled(archiveBusy || model.deviceTestRunning)
                            }
                        }
                        if page.reports.isEmpty { Text("No saved outputs.") }
                        if page.olderAvailable {
                            Button("Older results") { browseArchive(page.beforeMillis, page.beforeRunId) }
                                .disabled(archiveBusy || model.deviceTestRunning)
                        }
                    }
                    Button("Share all saved outputs") { exportArchive(nil) }
                        .disabled(archiveBusy || model.deviceTestRunning)
                    if archiveBusy { ProgressView("Reading saved outputs…") }
                }
            }
            .buttonStyle(.borderless)
            .navigationTitle("Test Center")
            .toolbar { Button("Done") { dismiss() } }
            .sheet(isPresented: $shareExport) { if let file = exportFile { RpcTestEvidenceShare(file: file) } }
            .sheet(isPresented: $choosingCase) {
                NavigationView {
                    List {
                        ForEach(RpcPhysicalTestCatalog.shared.cases.filter {
                            caseFilter.isEmpty || $0.summary.localizedCaseInsensitiveContains(caseFilter)
                                || $0.id.localizedCaseInsensitiveContains(caseFilter)
                        }, id: \.id) { item in
                            Button(item.summary) {
                                selected = item.id
                                reference = ""
                                notes = ""
                                choosingCase = false
                            }.accessibilityIdentifier("rpc.case." + item.id)
                        }
                    }
                    .searchable(text: $caseFilter, placement: .navigationBarDrawer(displayMode: .always), prompt: "Find a test")
                    .navigationTitle("Choose a test")
                    .toolbar { Button("Cancel") { choosingCase = false } }
                }
            }
            .onDisappear { archiveTask?.cancel() }
        }
    }

    private func finish(_ outcome: String) {
        action { try center.finish(outcome: outcome, evidenceReference: reference, notes: notes) }
    }

    private func browseArchive(_ beforeMillis: Int64 = Int64.max, _ beforeRunId: String = "") {
        guard !archiveBusy else { return }
        archiveBusy = true
        archiveTask = Task { @MainActor in
            defer { archiveBusy = false }
            do { archivePage = try await model.browseTestArchive(beforeMillis: beforeMillis, beforeRunId: beforeRunId) }
            catch { message = "Archive could not be read; original outputs remain retained." }
        }
    }

    private func exportArchive(_ runId: String?) {
        guard !archiveBusy else { return }
        archiveBusy = true
        archiveTask = Task { @MainActor in
            defer { archiveBusy = false }
            do {
                exportFile = try await model.exportTestArchive(runId: runId)
                shareExport = true
            } catch { message = "Export incomplete; original outputs remain retained." }
        }
    }

    private func action(_ work: () throws -> Void) {
        do {
            try model.physicalTestAction(work)
            message = "Recorded locally. Inspect saved results and storage status."
        } catch { message = "Check steps, duration, evidence reference and storage status. Nothing was marked passed." }
    }
}
