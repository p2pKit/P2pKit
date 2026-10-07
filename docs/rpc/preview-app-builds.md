# RPC preview app builds

The opt-in **RPC preview applications** workflow builds one exact feature commit into:

- Android debug APK (the RPC launcher exists in debug only).
- macOS ARM64 `.app` in a ZIP, with its source-pinned native TCP/Bonjour adapter and bundled Java runtime.
- Linux x64 application image in a `.tar.gz`, with its launcher and bundled Java runtime.
- **Windows x64 UI preview** in a ZIP with an `.exe` launcher and bundled Java runtime.

**Windows does not yet have protected persistent profile storage. Host/Client remain disabled with a
visible explanation; this package is not a working Windows RPC implementation.** Porting and validating
that storage boundary is separate engineering work, not physical-device testing. Linux retains the strict
ordinary-Java interface/topology restrictions. The Mac adapter is ARM64 only; no Intel runtime pass is inferred.

These are developer artifacts, not store installers or release/physical-network qualification. Desktop
images are not Developer-ID notarized or Authenticode signed. Respect OS warnings; do not disable security
protections. Android uses a CI debug certificate, which may differ from an already-installed local build.
Do not uninstall the existing app or erase trust to work around that mismatch; keep the matching local signer
for in-place updates. No keystore or signing secret is uploaded.

## Trigger and download

An owner-authorized push ending in `[rpc-ui-build]` on
`work/rpc-lan-20260927-054728-8b1b11da` starts the build without modifying `main`. Manual dispatch is also
available once GitHub registers the workflow. Ordinary feature pushes do not allocate these jobs.

Download the `rpc-<target>-<full SHA>-<attempt>` artifact from the matching successful Actions run. Each contains
a SHA-256 manifest, exact source/tree, scope and limitations. Extract the entire Desktop archive before opening
its launcher; retain the adjacent runtime and app files. Package creation alone does not prove discovery,
pairing, trust persistence or cross-device RPC. Test-result artifacts are separate from installable artifacts.

Dependency and wrapper caches are reused through the pinned Gradle setup action. Builds disable the task build
cache and enforce strict dependency verification. They do not update dependency versions or verification metadata.
New runners may need to download missing verified inputs; subsequent compatible jobs reuse cached downloads.

## UI scope

All three frontends now share a blue local-API workspace identity, clear Overview/Network/Requests/History
sections, prominent role controls and bounded live dashboards. Android adapts to light/dark mode and system/IME
insets; iOS uses native grouped sections, Dynamic Type and semantic role controls; Desktop retains responsive
scrolling and wrapped controls. Text remains an explicitly English developer preview. These presentation changes
do not change trust decisions, network admission, request limits, cancellation or background lifetime.
