package dev.p2pkit.sample.rpc

/** Operator instructions, not a capability claim or authority to inject faults. */
public data class RpcPhysicalTestCase(
    public val id: String,
    public val title: String,
    public val category: String,
    public val issues: List<Int>,
    public val equipment: String,
    public val steps: List<String>,
    public val evidence: String,
    public val minimumSeconds: Int = 0,
    public val phase: RpcDeviceTestPhase? = null,
    public val tool: String = "Guided observation",
) {
    public val summary: String get() = "$category · $title"
    public val instructions: String get() = buildString {
        appendLine(equipment)
        appendLine("Method: $tool")
        if (minimumSeconds > 0) appendLine("Minimum observation: ${minimumSeconds / 60} minutes")
        steps.forEachIndexed { index, step -> appendLine("${index + 1}. $step") }
        appendLine("Save: $evidence")
        appendLine("Issues: ${issues.joinToString { "#$it" }}")
    }
}

/** Stable case IDs bind saved records to this catalog revision. */
public object RpcPhysicalTestCatalog {
    public const val revision: Int = 1
    public val cases: List<RpcPhysicalTestCase> = buildList {
        for (phase in RpcDeviceTestPhase.entries.filter { it != RpcDeviceTestPhase.Observation }) {
            add(RpcPhysicalTestCase("rpc-${phase.name.lowercase()}", phase.title, "RPC buttons", listOf(525),
                "Two connected, trusted devices on the private Wi-Fi. Use Multi-device tests for overlap.",
                listOf("Choose Host and Client; select the discovered Host and compare fingerprints.",
                    "Use Run on connected devices. For Host start, enable the selected Host's test permission.",
                    "Wait for both sides' saved result. Repeat in all six Android/iPhone/Mac directions."),
                "Both run IDs, source, direction, measured results and available resources.",
                phase = phase, tool = "Built-in RPC workload"))
        }
        fun case(id: String, title: String, category: String, issues: List<Int>, equipment: String,
            seconds: Int = 0, tool: String = "Guided observation", evidence: String, vararg steps: String) {
            add(RpcPhysicalTestCase(id, title, category, issues, equipment, steps.toList(), evidence, seconds,
                tool = tool))
        }
        case("lan-idle", "Discovery and removal", "LAN", listOf(21, 43),
            "Ordinary sample screens; Android and a second peer; OS logs and packet capture.", 1_800,
            evidence = "Both diagnostic ZIPs; serviceRemoved hasInfo/hasPeerId/leaseActive, withdrawal, Lost and TTL.",
            steps = arrayOf("Enable Advertise and Discover with Auto-mesh off; leave unconnected for 30 minutes.",
                "Stop/restart the advertiser, then force-stop it. Repeat with the observer backgrounded.",
                "Live peers stay visible; departed peers disappear. #43 needs a real metadata-free callback."))
        case("lan-soak", "Six-hour discovery soak", "LAN", listOf(21, 39),
            "Two physical Androids and one JVM peer; dedicated LAN and resource/packet recording.", 21_600,
            evidence = "30-minute/hourly snapshots; endpoints, PSS, threads, sockets, both-side transfers and PCAP.",
            steps = arrayOf("Keep peers unconnected for the first two hours; twelve total hours is preferred.",
                "Restart JVM at hours 2 and 4. Restart one Android at hours 3 and 5; do 20 discovery cycles.",
                "Final hour: messages and 5 MiB each direction for every pair, graceful removal, ten quiet minutes.",
                "No stale endpoint or growth trend; sockets within baseline +16 and PSS within +max(20 MiB,50%)."))
        case("jvm-path", "Desktop interface changes", "LAN", listOf(25, 31),
            "Mac/Linux and a real peer; two Wi-Fi networks and Ethernet.",
            evidence = "Routes, explicit JmDNS binding, endpoint changes and packet capture.",
            steps = arrayOf("While running: switch Wi-Fi A to B, Wi-Fi to Ethernet, remove/re-add the interface.",
                "Discovery and TCP must follow the selected LAN without restarting the application."))
        case("android-route", "Android hotspot and VPN routing", "Android", listOf(26, 28, 33),
            "Physical OEM devices; ordinary sample; Wi-Fi/hotspot/VPN/cellular and capture tooling.",
            evidence = "Interface/network address, mDNS, TCP SYN and return route, dumpsys and PCAP.",
            steps = arrayOf("Run on normal Wi-Fi and Android hotspot; repeat with VPN and cellular active.",
                "Cover IPv4, dual stack and supported scoped IPv6; actual selected LAN must carry every socket.",
                "No safe LAN must refuse before SYN. Hotspot network=none still needs explicit AP-address binding."))
        case("android-rebind", "Android rapid rebind", "Android", listOf(29, 30, 35),
            "Physical Android, hotspot/AP; reviewed callback/bind-failure fixture for controlled races.",
            tool = "Radio actions plus external callback fixture",
            evidence = "50 toggles, callback/generation timeline, native close/recreate and retry outcomes.",
            steps = arrayOf("Toggle Wi-Fi/hotspot 50 times, including bursts around the unchanged 800 ms debounce.",
                "Exercise slow AP readiness, failed bind/retry, superseding callback and Stop during replacement.",
                "Exactly one settled generation; bounded retry or typed failure; no listener leak or app restart."))
        case("android-background", "Android background recovery", "Android", listOf(36),
            "Physical Android ordinary sample; default OEM background policy recorded.", 600,
            evidence = "Enabled/disabled intent, settled stop/restore events, OS logs and partial-file cleanup.",
            steps = arrayOf("During discovery/handshake/transfer: rotate, background 30 s then 10–15 min; lock/unlock.",
                "Change Wi-Fi/hotspot; force-stop/relaunch. Repeat kit Stop/Start 20 times.",
                "Only previously enabled features resume; no pre-crash transfer becomes successful."))
        case("apple-recovery", "iPhone path and interruption recovery", "Apple", listOf(23, 27, 37, 38),
            "Physical Apple peer; two APs/subnets; ordinary sample and lifecycle/path diagnostics.",
            evidence = "Ordered lifecycle and browser/listener generations, current endpoint and old-port release.",
            steps = arrayOf("During discovery/handshake/idle/transfer: peer restart/new port 20 times; hotspot off/on.",
                "Switch Wi-Fi A/B and infrastructure/AWDL; return from Settings, Control Center, dialogs or call.",
                "Background 30 s/5 min, lock 30 s, swipe-kill/relaunch; iPad split-view where supported.",
                "One rebind per inactive episode; late old dial cannot remove a fresh endpoint."))
        case("apple-awdl", "Apple peer-to-peer without a router", "Apple", listOf(32, 34),
            "Two physical Apple mobile devices, preferably iPhone + iPad; native Apple sample on both.",
            evidence = "Actual peer-to-peer path, cellular prohibited, browser/listener/outbound flags and hashes.",
            steps = arrayOf("Leave Wi-Fi enabled but disconnect both devices from the AP.",
                "Discover, authenticate and transfer in both directions; repeat hotspot host/client where supported.",
                "Prove the actual path. Mac JVM and successful connection alone cannot establish AWDL."))
        case("tcp-timing", "TCP and Apple write-ready timing", "Network faults", listOf(40, 41),
            "Controlled router/bridge and instrumented native timestamps; LAN, hotspot and AWDL.",
            tool = "External packet/native timing fixture",
            evidence = "Repeated connect distributions; reset/drop capture; Closed and exactly one native cancel.",
            steps = arrayOf("Compare successful connect, TCP reset, silent drop, stale endpoint and path interruption.",
                "Preserve JVM/Android 5 s total and 1.5 s alternate slices; Apple 10 s connect/write-ready.",
                "After write-ready timeout, connection is Closed; later write rejects immediately."))
        case("link-local", "Direct Ethernet without DHCP", "LAN", listOf(44),
            "Two Mac/Linux machines, direct Ethernet/USB-Ethernet; supported Android Ethernet as another cell.",
            evidence = "Actual 169.254/16 and IPv6 zones, direct-interface PCAP, sizes/hashes and three cycles.",
            steps = arrayOf("Disable DHCP and alternate routes; wait for actual link-local addresses.",
                "Three bidirectional discovery/authentication cycles, transferring 200 KiB and 5 MiB each way.",
                "Unscoped IPv6 must not dial. Restore normal network configuration afterward."))
        case("core-files", "Files, consent and cleanup", "Core sample", emptyList(),
            "Ordinary sample on both devices; synthetic fixtures and diagnostic sessions with one shared ID.",
            evidence = "Both diagnostic ZIPs, consent/outcomes, independent source/destination hashes and cleanup.",
            steps = arrayOf("Send 0, 1 byte, 200 KiB, 5 MiB and 49 MiB both ways; text, binary, image and hostile names.",
                "Accept/reject/expire; cancel Offered/Accepted/mid-transfer; rotate with picker/offer; Stop while live.",
                "Durable commit precedes acknowledgement. Lost acknowledgement may leave a valid receiver file."))
        case("core-storage", "Storage and export failures", "Core sample", emptyList(),
            "Reviewed bounded file/sink fixture; never fill the owner's phone or modify personal files.",
            tool = "External storage fault fixture",
            evidence = "Collision reservations, limits, failure events, file listings/hashes and original logs.",
            steps = arrayOf("Same-name concurrent offers, repeated/over-50 MiB offers, quota/unwritable sink/export failure.",
                "Mutate source or inject digest mismatch; interrupt receiver at each commit stage.",
                "No path escape, overwritten existing file or partial success; preserve committed output."))
        case("android-provisioning", "Android permissions and hotspot ownership", "Android", emptyList(),
            "Physical OS bands 24–25/29–32/33–34/35+; two OEMs; secure LOHS handoff and on-device fixture.",
            tool = "External provisioning fixture (PS-T01/02)",
            evidence = "Device/target SDK, consent, callback generations, shared-process manager/binding and cleanup.",
            steps = arrayOf("Deny/permanent deny/grant/revoke/cancel/timeout/success; Nearby Wi-Fi versus legacy Location.",
                "Invalid WPA2/WPA3/OPEN inputs refuse before native registration; valid retry succeeds.",
                "API/feature capability, radio-off and Ethernet-only cases; actual secure hotspot enrollment.",
                "Same-process A owns join; B onAvailable refuses without unbinding A. Both close orders and late callbacks.",
                "Concurrent close shares one pending attempt/failure; delayed N1 lost preserves N2; one terminal winner."))
        case("apple-manual-info", "Apple native ownership", "Apple", emptyList(),
            "Signed on-device manual-info/cancellation fixture and same-moment interface capture.",
            tool = "External native lifecycle fixture",
            evidence = "Real owner/caller cancellation, ManagerClosed, interface/identity/port and terminal close.",
            steps = arrayOf("Race Stop with manual-info; cancel caller separately, then stop owner and call again.",
                "No detached work; later calls return ManagerClosed and repeated close is safe.",
                "Addresses match active LAN/AWDL; preserve IPv6 zone and exclude cellular/VPN/wildcard/down paths."))
        case("network-impairments", "Delay, loss and hostile packets", "Network faults", emptyList(),
            "Two real machines, isolated managed network, two router models and reviewed fault generator.",
            tool = "External network fixture (LAN-T08 / ENV-02)",
            evidence = "Three repeats/profile, seed/settings, both peer exports, mandatory PCAP and resource bounds.",
            steps = arrayOf("Baseline then 250 ms delay; 100±75 ms jitter/10% reorder; loss 1/5/20%; 64 kbit/s/1 Mbit/s.",
                "2% duplicate; combined 150±50 ms, 5% loss, 2% reorder, 1% duplicate.",
                "Disconnect during discovery/handshake/idle/49 MiB transfer; restart same/new identity; change subnet.",
                "Block mDNS/data separately, asymmetric return, isolation, TCP reset/silent drop.",
                "Malformed App ID/version/TXT/security records, duplicate identity, bounded flood/admission+1.",
                "No fallback/corruption/unbounded growth; restore only test-owned rules."))
        case("desktop-lifecycle", "Desktop UI and CLI lifecycle", "Desktop", emptyList(),
            "Headful Mac/Linux/Windows, distinct peer, reviewed UI/process-fault fixture.",
            tool = "Application controls plus external fault fixture",
            evidence = "Three repeats, video/transcript, baseline/mid/end resources and full owned-process retirement.",
            steps = arrayOf("CLI valid/invalid options, ambiguous peer, EOF, terminal close, signals/crash/blocked network.",
                "Window start/stop/toggles, chooser/consent/cancel/sink failure and close during live work.",
                "At least 1000 terminal messages/transfers or explicitly agreed byte/time budget; bounded history."))
        case("platform-matrix", "Platform and consumer matrix", "Core sample", emptyList(),
            "Required Android/Apple OS bands and hardware; Intel x86_64 Apple runtime for that separate cell.",
            evidence = "Exact consumer dependencies/artifacts, architectures, three repeats per role/OS/topology.",
            steps = arrayOf("All Android/Apple/JVM pairs in both directions, plus three-peer concurrent traffic.",
                "Run KMP consumer smoke with Android initialization and physical Swift/XCFramework, then 200 KiB transfer.",
                "Prove iOS 14 library floor with compatible consumer; Intel framework load and Start/Stop separately."))
        case("ios-backup", "Actual iOS backup exclusion", "External evidence", listOf(291),
            "iCloud Backup-enabled real device and supported backup-set inspection; spare device if restore needed.",
            tool = "OS backup and external inspection",
            evidence = "Unique inbox/evidence fixtures, actual backup time/scope and demonstrable absence from backup.",
            steps = arrayOf("Receive unique synthetic file into P2pKitInbox; export to P2pKitEvidence; record hashes.",
                "Complete actual backup, inspect its set using supported tools; do not reset the daily phone.",
                "Flags/container download/storage totals do not prove absence; label Finder versus iCloud accurately."))
        case("independent-peer", "Independent secure-v2 implementation", "External evidence", listOf(133),
            "Authoritative frozen independent peer and six-source coordinator; qualified original execution context.",
            tool = "External independent implementation",
            evidence = "Source/input hashes, known answers, both transcripts, PCAP and retained C2 exit-70 failure.",
            steps = arrayOf("Recover original inputs and compiled-schema checks; retain bounded execution envelope.",
                "Three repeats/role on JVM OSes, two Android OS bands and native Apple Wi-Fi/AWDL where supported.",
                "Pin accept/refuse, text/binary/metadata, 5 MiB, cancel/reconnect/close and malformed/replay negatives."))
        for (platform in listOf("Android", "iPhone")) for (count in listOf(128, 256)) {
            case("capacity-${platform.lowercase()}-$count", "$platform Host · $count Clients", "Mac campaign",
                listOf(525), "Native ARM Mac; matching APK/signed app/framework/driver; prepared private campaign.",
                1_800, "Source-matched Mac campaign runner",
                "Source/tree/product bindings, correct throughput, p95/p99, misses, phone and generator resources.",
                "Run large/correctness/churn/steady independently through the maintained campaign runner.",
                "Large: 20 exact 1 MiB, concurrency 2 on one client. Correctness: full authenticated cohort.",
                "Churn: five rounds, original identities, reconnect batches ≤2. Steady: 1800 s, 1 KiB, 10 calls/s/client.",
                "Separate initialization/idle/faults; retain 65-second drain and exact Stop. Never substitute UI Clients.")
        }
        case("mixed-capacity", "One phone plus 255 Mac Clients", "Mac campaign", listOf(525),
            "Both physical phones; native Mac generator and reviewed mixed physical-pin/outcome extension.",
            tool = "Mixed-cohort runner extension required",
            evidence = "Simultaneous full roster, physical phone outcomes, per-client results and cleanup.",
            steps = arrayOf("Android Host: iPhone +255 independent Mac Clients simultaneously; then reverse phones.",
                "Separate phone smoke or 256 Mac Clients cannot certify this topology."))
        case("socket-faults", "Socket backpressure, fairness and mixed faults", "Mac campaign", listOf(525),
            "Reviewed authenticated socket slow-reader and coordinated fault/connection generator.",
            tool = "Socket and coordinated-fault runner extensions required",
            evidence = "Actual socket read pressure, bounded queues/memory, per-peer progress, schedule and drain.",
            steps = arrayOf("Slow/stop a peer reading socket bytes while other authenticated Clients progress.",
                "Coordinate reconnect, deadlines/cancellation, revocation and competing Clients over a declared long run.",
                "Delayed handler is not socket backpressure. Keep admission/authentication/encryption intact."))
        case("rpc-revocation", "RPC identity approval and revocation", "RPC controls", listOf(525),
            "Trusted Host and two Clients on private Wi-Fi; exact source and both peer diagnostic recordings.",
            evidence = "Reject/approve/revoke times, typed outcomes, unrelated Client progress and cleanup.",
            steps = arrayOf("Reject unknown fingerprint, then compare and approve the intended Client.",
                "Revoke/forget during use; stale approvals cannot restore access; explicit reapproval required.",
                "Other Clients remain usable; reconnect uses the saved identity; no automatic request replay."))
        case("battery-discharge", "Unplugged battery and thermal recording", "Resources", listOf(525),
            "Reviewed unplugged recorder or supported wireless control; owner physically removes charger.",
            tool = "Reviewed discharge recorder required",
            evidence = "Actual charging state, start/end battery, measured duration/workload, available current/thermal.",
            steps = arrayOf("Record powered baseline, then unplug both USB and external charging as applicable.",
                "Run the declared workload/recorder; stop on serious/critical thermal state or safety threshold.",
                "Charging is not discharge; battery temperature is not CPU temperature; iOS categories are coarse.",
                "Reconnect charging after completion; preserve original failure and verified Stop."))
        case("windows-installed", "Windows installed qualification W01–W11", "Windows", listOf(462),
            "Native AMD64 Windows/VM, disposable ordinary-user interactive login, protected MSI and fixed NTFS.",
            tool = "Canonical Windows installed supervisor",
            evidence = "Installed source/runtime/DLL hashes, token/load/native results, both peers and all retirement.",
            steps = arrayOf("W01–03: user/root admission, hostile first-load inputs, loaded module and every JNI method.",
                "W04–07: native filesystem cases; 0/1/262144 bytes/over-limit, locks, encrypted reopen and fault/cancel.",
                "W08–09: main app/RPC/Back, Host/Client, Reject/Approve, typed calls, persisted pin/revoke/stale observer.",
                "W10: first retained ui-host-cycle then ≥20 accepted cycles, interruption and all process/resource closure.",
                "W11: installed readback and independent review. Preserve 10/15/5/30 s budgets; never reset failures."))
    }

    public fun find(id: String): RpcPhysicalTestCase = cases.first { it.id == id }
}
