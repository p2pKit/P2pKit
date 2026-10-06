# Manual Android ↔ iPhone RPC test

Use the **P2pKit RPC** screen, not the ordinary P2P sample or a capacity session.
This is a two-phone pairing/echo smoke test, not full LAN or release qualification.
Both devices must use the same authorized private Wi-Fi. USB and a Wi-Fi icon
alone do not prove that they can connect.

## First direction: Android hosts, iPhone connects

1. On **both phones**, tap **Stop** if a role is active. Wait for the message
   confirming owned cleanup completed. Then tap **Use this Wi-Fi** if needed.
2. On **Android only**, tap **Start host**. Check **Active role: Host**.
   The host can say `Running` with zero clients while it waits; that is normal.
3. On Android, tap **Create one-use, two-minute invitation**, then
   **Copy invitation**. Copy does not require displaying the secret with Reveal.
   Copying does **not** send it to the iPhone or restart the two-minute clock.
4. Transfer the exact invitation through an already available trusted private
   channel. Return to each RPC app within **25 seconds** if you switch apps
   while a role is active; the OS can end this allowance sooner. If the role
   stops or the invitation expires, finish cleanup and create a fresh invitation.
   iPhone copies are device-local, not Universal Clipboard. Do not post codes
   publicly, put them in logs, use cloud chat/clipboard sync, or send screenshots
   containing them.
5. On the **iPhone**, return to P2pKit RPC, confirm Wi-Fi if necessary, and tap
   **Start client**. Check **Active role: Client**, paste into **Invitation
   obtained through a trusted local channel**, and tap **Pair and connect** once.
   Keep **both RPC apps in the foreground** from this point until the call ends.
6. On the **Android host**, watch the live **Pending** card and the request under
   **Local administrator approval**; no Refresh click is needed. Compare its full
   fingerprint with the iPhone's **Advanced → Local identity**. Tap
   **Approve this exact client** only if they match. If no request appears,
   inspect the client status/log; do not approve an unrelated device.
7. Wait for the iPhone to report connected/`Ready`. On the **iPhone client**,
   tap **Send test message (1 KiB echo)**. Success requires **1/1 replies** and
   no failure. There is no separate incoming chat/message popup: the sample
   calls an echo procedure and displays its result on the client.
8. Watch the host's live client/call cards. Then **Stop both** and
   verify cleanup completed.

## Reverse direction

Repeat the same steps with **iPhone = Host** and **Android = Client**. Create
the invitation on iPhone, paste it on Android, approve the Android fingerprint
on iPhone, and send the echo from Android. Never select Host on both phones.

## Read the result correctly

- Starting a role is not a connection. `Running` describes a host, not a
  connected client. A client needs connected/`Ready` before sending an echo.
- Pending requests update automatically on the **host**, not on the client.
  A fresh valid attempt can reuse existing durable trust; do not erase trust
  merely to force a new approval request.
- Zero completed calls is expected until the client sends an echo. The
  client does not have a meaningful “connected clients” counter.
- Pairing and in-flight calls cannot be continued while switching apps.
  Transfer the invitation **before** pressing Pair; do not extend deadlines.

## Live dashboard

The active ordinary session reads cached status about twice per second. Host
cards show **Clients**, **Pending**, **Completed** and **Queued**; pending-client
rows update automatically. Client cards show connection information and call
counts rather than a host-only client count. Waiting/unavailable values are not
successful zero-count observations. Approval is always an explicit action.

Phone observation pauses in the background and retires with the role. It does
not keep a session alive, start traffic, approve a client or extend any deadline.
Periodic observations do not overwrite action results or earlier errors.
Manual Refresh remains an optional immediate check, not a pairing requirement.

## If a step fails

Open **Diagnostic log → Copy diagnostics** on each phone. Share those two
diagnostic texts, the direction tested, and the last numbered step reached.
The bounded log retains earlier errors across Refresh and Stop, but only in
memory; copy it before closing/restarting the app. It contains source, fixed
events, known states, counts and safe failure codes—not invitations, pins,
addresses, payloads or raw exception messages.

Do not repeatedly press Pair, reset trust, change router/firewall/privacy
settings, or assume a timeout proves a network cause. Preserve the first
failure, stop both roles, and diagnose that evidence before retrying.
