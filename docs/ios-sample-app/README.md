# (Deprecated) iOS sample template → use `iosApp/`

> **This directory is superseded.** The maintained, buildable iOS sample now
> lives at the repository root in **`iosApp/`** — a real XcodeGen project that
> demonstrates discovery, sessions, messaging, **file transfer**, the
> permission banner, and an in-app diagnostic log. Build it with:
>
> ```bash
> ./gradlew :p2p-transport-lan:assembleP2pKitSharedXCFramework
> cd iosApp && xcodegen generate && open *.xcodeproj
> # the iosApp pre-build script links the freshly-built framework
> ```
>
> For on-device LAN diagnostics (Issue #2 interface selection / Issue #3 AWDL),
> follow **`docs/LAN_DIAGNOSTICS_PROTOCOL.md`**.

## Why this folder is kept (for now)

The Swift files still here — `ContentView.swift`, `KitController.swift`,
`Info.plist`, `project.yml`, `P2pKitSampleApp.swift` — are an **early template
that no longer compiles** against the current exported API (it predates the
file-transfer API and never collected sessions/messages). They are retained only
for historical reference and are **not** wired into any build.

**Do not copy these files into a new project.** Use `iosApp/` instead. This
folder can be deleted once no external notes reference it.
