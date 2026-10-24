// swift-tools-version: 5.9
import PackageDescription

// Pure metadata contracts, not a replacement XCTest UI target or readiness
// implementation. The application compiles this same small record source.
let package = Package(
    name: "KeyboardCauseProbeControls",
    targets: [
        .target(name: "KeyboardCauseProbeRecord"),
        .testTarget(name: "KeyboardCauseProbeRecordTests", dependencies: ["KeyboardCauseProbeRecord"])
    ]
)
