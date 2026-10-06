package dev.p2pkit.sample.rpc.desktop

import dev.p2pkit.sample.rpc.RpcPhoneBuildStamp
import dev.p2pkit.sample.rpc.RpcPhoneSettings
import dev.p2pkit.sample.rpc.lab.LabFiles
import java.nio.file.Files
import java.nio.file.LinkOption.NOFOLLOW_LINKS
import java.nio.file.Path
import java.nio.file.attribute.BasicFileAttributes
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking

internal data class DesktopLocalReadinessArguments(val settings: RpcPhoneSettings, val ownedParent: Path)

internal fun parseDesktopLocalReadinessArguments(args: Array<String>): DesktopLocalReadinessArguments {
    require(args.size == 6 && args[0] == "--approved-local-host") {
        "Explicit approved local Host, interface, numeric IPv4, private CIDRs, port and empty private parent required"
    }
    val settings = desktopRpcSettings(args[3], args[1], args[2], args[4])
    require(settings.localAddress.split('.').size == 4) { "This probe covers IPv4 only" }
    val parent = Path.of(args[5])
    require(parent.isAbsolute && parent.normalize() == parent)
    return DesktopLocalReadinessArguments(settings, parent)
}

/** Explicit local Host/Stop only. Never mints an invitation, sends discovery, approves or connects a peer. */
fun main(args: Array<String>) = runBlocking {
    val selected = parseDesktopLocalReadinessArguments(args)
    check(RpcPhoneBuildStamp.SOURCE_CLEAN)
    check(!System.getProperty("dev.p2pkit.lan.macos.nativeDir").isNullOrBlank()) {
        "Explicit verified native stage required; there is no portable diagnostic fallback"
    }
    LabFiles.privateDirectory(selected.ownedParent)
    check(selected.ownedParent.toRealPath() == selected.ownedParent)
    val parentKey = checkNotNull(Files.readAttributes(selected.ownedParent,
        BasicFileAttributes::class.java, NOFOLLOW_LINKS).fileKey())
    Files.list(selected.ownedParent).use { check(it.findAny().isEmpty) }
    val runtime = DesktopRpcRuntime.create(selected.ownedParent)
    try {
        runtime.start(host = true, selected.settings)
        check(runtime.state == "Running" && runtime.connectedClients == 0 && runtime.pending().isEmpty())
        println("{\"phase\":\"HOST_RUNNING\",\"source\":\"${RpcPhoneBuildStamp.SOURCE_COMMIT}\"," +
            "\"pid\":${ProcessHandle.current().pid()}}")
        // A fixed, bounded observation window for an independent owner-specific lsof readback, not an RPC deadline.
        delay(5_000)
    } finally {
        runtime.close() // Retains partial/failing cleanup; never destroys identity after an unproven native close.
    }
    check(Files.readAttributes(selected.ownedParent,
        BasicFileAttributes::class.java, NOFOLLOW_LINKS).fileKey() == parentKey)
    Files.list(selected.ownedParent).use { check(it.findAny().isEmpty) }
    println("{\"phase\":\"OWNED_HOST_AND_VAULT_CLEANUP_VERIFIED\",\"source\":\"${RpcPhoneBuildStamp.SOURCE_COMMIT}\"}")
}
