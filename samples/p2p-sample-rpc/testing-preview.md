# Testing the three RPC previews

These are interactive, English-only developer samples, not release-qualified
applications. Android's RPC activity, the separate iPhone **P2pKit RPC** app and
the opt-in JVM/Swing RPC window use the same manual-pairing contract. The ordinary
P2P sample screens and the capacity driver are different applications.

## Before starting

- Use an authorized private LAN with two permitted, non-self endpoints.
  Sharing Wi-Fi, connecting USB or installing an app does not prove RPC works.
- On Android/iPhone, tap **Use this Wi-Fi**, then choose exactly one role.
  If detection fails, read **Wi-Fi check details**; do not guess manual values.
- On JVM, select the actual interface and review the CIDR/port. Additional UP,
  non-loopback interfaces currently block the strict JVM transport. A supported
  per-socket adapter is still needed for that topology; do not alter protections.
- Keep the phone apps visible while pairing. An ordinary idle host/client can
  survive an app switch of **up to 25 seconds** to transfer an invitation. Return
  promptly; iOS or Android may end the allowance early. The same approved network
  is rechecked before resuming, and no stopped role is automatically restarted.
  Stop, network loss, device lock, expired background time, or an in-flight/
  capacity operation or manual network setup still retires the role. Cleanup must finish before switching roles.

## Pair and exchange a real reply

1. Choose **Start host** on one endpoint and **Start client** (**Create client**
   on JVM) on the other. Starting roles is not a connection test.
2. On the host, create a new invitation and explicitly reveal it. Phone apps
   offer **Copy invitation** while the foreground invitation is valid. Copying
   does not restart its two-minute lifetime or send it to the other device.
3. Transfer the exact text through a trusted private channel and paste it into
   the client's invitation field. Both phone apps allow a brief app switch:
   return within **25 seconds of leaving each app**. The invitation's original
   two-minute deadline is unchanged. iPhone copying is device-local, not Universal
   Clipboard. Android uses a bounded, non-sticky foreground service with a
   secret-free notification; no permanent background host is installed.
   Treat the invitation as a secret: do not publish it or include it in diagnostic
   logs/screenshots. Android cannot guarantee external clipboard sync ignores it.
4. Choose **Pair and connect** on the client. On the host, refresh pending
   requests. Compare the full client fingerprint with **Advanced → Local
   identity** on the phone client, or the JVM fingerprint field. Approve only
   that exact request. Seeing a pending request is not successful pairing.
5. Once connected, choose **Send test message (1 KiB echo)**, or **Call 1 KiB
   echo** on JVM. Require the actual expected reply count and no failure;
   a connected label alone is insufficient. Stop both roles after testing.

The iPhone can display an invitation QR code, but these previews do **not** yet
include an in-app camera scanner. Clipboard support is not a device-to-device
transfer mechanism. Test the reverse host/client direction separately.

## What prepared builds do not establish

Unit, simulator, build, signature and cleanup checks do not establish physical
Android hosting, cross-device pairing/echo, multicast, hostile-network behavior
or capacity. Record the compiled source shown by each app and the exact failed
step, without exporting invitations or private identities. Dependency advisory
remediation, full CLI/LAN qualification, Intel/ART and broader device campaigns
remain separate from this preview checklist.
