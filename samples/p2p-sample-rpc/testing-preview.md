# Testing the three RPC previews

These are interactive, English-only developer samples, not release-qualified
applications. Android's RPC activity, the separate iPhone **P2pKit RPC** app and
the opt-in JVM/Swing RPC window use the same manual-pairing contract. The ordinary
P2P sample screens and the capacity driver are different applications.
For the exact two-phone sequence and failure-reporting steps, see
[Manual Android ↔ iPhone RPC test](MANUAL-TESTING.md).

## Before starting

- Use an authorized private LAN with two permitted, non-self endpoints.
  Sharing Wi-Fi, connecting USB or installing an app does not prove RPC works.
- On Android/iPhone, tap **Use this Wi-Fi**, then choose exactly one role.
  If detection fails, read **Wi-Fi check details**; do not guess manual values.
- On JVM, select the actual interface and review the CIDR/port. The ARM64 Mac
  preview uses a [source-bound TCP adapter](../../library/p2p-transport-lan/src/nativeInterop/macosJvm/README.md)
  that verifies each socket's interface scope. Other active interfaces remain
  visible; they are not disabled or ignored. The portable Java transport retains
  its multi-interface restriction. Manual invitations do not require mDNS;
  this adapter does not fix or qualify multicast.
- Keep the phone apps visible while pairing. An ordinary idle host/client can
  survive an app switch of **up to 25 seconds** to transfer an invitation. Return
  promptly; iOS or Android may end the allowance early. The same approved network
  is rechecked before resuming, and no stopped role is automatically restarted.
  Stop, network loss, device lock, expired background time, or an in-flight/
  capacity operation or manual network setup still retires the role. Cleanup must finish before switching roles.

## Pair and exchange a real reply

1. Choose **Start host** on one endpoint and **Start client** (**Create client**
   on JVM) on the other. Starting roles is not a connection test.
2. On the host, create a new invitation. Phone apps offer **Copy invitation**
   without requiring Reveal while the foreground invitation is valid. Use
   Reveal only when you intentionally need to display the secret. Copying
   does not restart its two-minute lifetime or send it to the other device.
3. Transfer the exact text through a trusted private channel and paste it into
   the client's invitation field. Both phone apps allow a brief app switch:
   return within **25 seconds of leaving each app**. The invitation's original
   two-minute deadline is unchanged. iPhone copying is device-local, not Universal
   Clipboard. Android uses a bounded, non-sticky foreground service with a
   secret-free notification; no permanent background host is installed.
   Treat the invitation as a secret: do not publish it or include it in diagnostic
   logs/screenshots. Android cannot guarantee external clipboard sync ignores it.
4. Choose **Pair and connect** on the client. Pending requests and the host's
   **Clients / Pending / Completed / Queued** cards update automatically; no
   manual refresh is required. Compare the full client fingerprint with **Advanced → Local
   identity** on the phone client, or the JVM fingerprint field. Approve only
   that exact request. Seeing a pending request is not successful pairing.
5. Once connected, choose **Send test message (1 KiB echo)**, or **Call 1 KiB
   echo** on JVM. Require the actual expected reply count and no failure;
   a connected label alone is insufficient. Stop both roles after testing.

The iPhone can display an invitation QR code, but these previews do **not** yet
include an in-app camera scanner. Clipboard support is not a device-to-device
transfer mechanism. Test the reverse host/client direction separately.

Live dashboards observe existing in-memory state about every 500 ms, not a
network probe. They never approve a request, select a role or erase an action
failure. Phone observation pauses when backgrounded; stopping a role or closing
the Desktop window retires its observer. Unavailable counters must not be read
as proof of a connected peer or successful call.

## Prepare the ARM64 Mac preview

From clean committed source with JDK 17 and the existing Xcode toolchain:

```sh
./gradlew :p2p-sample-rpc:prepareRpcDesktopMac --offline --dependency-verification=strict
python3 -I -S -B "samples/p2p-sample-rpc/build/desktop-macos/$(git rev-parse HEAD)/run-desktop.py"
```

The create-only package verifies its source-bound JARs, native library and JDK
before opening an idle window. It never starts a role or approves a network for
you. A local Host/Stop check proves neither peer pairing nor multicast support.

## What prepared builds do not establish

Unit, simulator, build, signature and cleanup checks do not establish physical
Android hosting, cross-device pairing/echo, multicast, hostile-network behavior
or capacity. Record the compiled source shown by each app and the exact failed
step, without exporting invitations or private identities. Dependency advisory
remediation, full CLI/LAN qualification, Intel/ART and broader device campaigns
remain separate from this preview checklist.
