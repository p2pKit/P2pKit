# Android accepted sockets

The organization-LAN listener must bind its descriptor to the selected Android
`Network` before `bind`/`listen`. `Os.fcntlInt` is public only from API 30, and
`Os.accept` does not preserve the listening descriptor's nonblocking or
close-on-exec flags. The native helper creates sockets and accepts children with
both flags atomically, using NDK APIs available at the existing API 24 minimum.
It does not change process routing or access profiles, keys or peer approval.

`AndroidSocketHandle` continues to gate every syscall and close. The exact
`FileDescriptor` owns a strongly retained `ParcelFileDescriptor`; close goes
through that owner, including Android's descriptor ownership checks. JNI only
receives integers borrowed under that lease, never private Java fields. The
library stays loaded for the Android class loader's lifetime.

Install NDK `29.0.14206865` into the existing Android SDK with
`sdkmanager "ndk;29.0.14206865"`. The `buildAndroidLanSockets` Gradle task uses
that compiler for all four Android ABIs and registers its generated libraries
with AGP's JNI source API, for both application consumers and the published
AAR. ELF segments support 16 KiB pages. No generated binaries are checked in.

Run the complete `:p2p-transport-lan:testAndroidHostTest` suite for descriptor
ownership, cancellation, races and failed-cleanup controls. Build the maintained
sample and test APK with `:p2p-sample-android:assembleDebug` and
`:p2p-sample-android:assembleDebugAndroidTest`.

On an approved device, after stopping the application, run:

```text
adb shell am instrument -r -w dev.p2pkit.sample.android.test/dev.p2pkit.sample.android.runtime.LanSocketRuntimeInstrumentation
```

Use an outer deadline and retain the final result. This supplemental runner has
a ten-second control budget and bounds all traffic to a synthetic local socket.
It checks listener/accepted flags independently through `/proc/self/fdinfo`,
nonblocking accept/read, a byte round trip, write backpressure, EOF and close.
It neither resets app data nor qualifies real LAN discovery, encrypted pairing,
RPC, revocation or application lifecycle. Run those separately with explicit
fingerprint approval; hosted tests do not establish physical-device coverage.
