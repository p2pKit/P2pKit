package dev.p2pkit.sample.rpc.desktop

import dev.p2pkit.sample.rpc.RpcPhoneBuildStamp
import dev.p2pkit.sample.rpc.lab.LabFiles
import java.nio.file.Files
import java.nio.file.LinkOption.NOFOLLOW_LINKS
import java.nio.file.Path
import java.nio.file.attribute.BasicFileAttributes
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout

internal fun parseDesktopAdvertisingReadinessArguments(args: Array<String>): Path {
    require(args.size == 2 && args[0] == "--approved-local-advertising") {
        "Explicit local host advertising authorization and an empty private parent are required"
    }
    return Path.of(args[1]).also { require(it.isAbsolute && it.normalize() == it) }
}

/**
 * One real local Host/advertise/Stop check. No client, approval, fixture discovery or existing profile.
 * This cannot prove multicast delivery, peer discovery, application RPC or cross-device interoperability.
 * OrganizationLan rejects self destinations: two identities on the same Mac cannot qualify those gates.
 */
fun main(args: Array<String>) = runBlocking {
    val parent = parseDesktopAdvertisingReadinessArguments(args)
    check(RpcPhoneBuildStamp.SOURCE_CLEAN)
    check(!System.getProperty("dev.p2pkit.lan.macos.nativeDir").isNullOrBlank())
    LabFiles.privateDirectory(parent)
    check(parent.toRealPath() == parent)
    val key = Files.readAttributes(parent, BasicFileAttributes::class.java, NOFOLLOW_LINKS).fileKey()
    check(key != null)
    Files.list(parent).use { check(it.findAny().isEmpty) }
    // Exercise the real transport's fresh policy check, not the UI's advisory discovery preflight.
    val settings = desktopRpcAutomaticSettings(desktopRpcNetworks())
    val host = DesktopRpcRuntime.create(parent)
    var primary: Throwable? = null
    fun event(value: String) {
        println("{\"phase\":\"$value\",\"source\":\"${RpcPhoneBuildStamp.SOURCE_COMMIT}\"," +
            "\"scope\":\"LOCAL_HOST_ADVERTISING_ONLY_NOT_MULTICAST_DELIVERY_OR_RPC_QUALIFICATION\"}")
    }
    try {
        withTimeout(30_000) { host.start(true, settings) }
        check(host.state == "Running" && host.status(true).networkActivity == "Active")
        check(host.connectedClients == 0 && host.pending().isEmpty())
        event("HOST_RUNNING_AND_ADVERTISING")
        delay(5_000) // Fixed independent process/socket observation window; not an RPC deadline.
        check(host.state == "Running" && host.status(true).networkActivity == "Active")
        check(host.connectedClients == 0 && host.pending().isEmpty())
    } catch (failure: Throwable) {
        primary = failure
        event("FAILED_LOCAL_HOST_ADVERTISING")
        throw failure
    } finally {
        try {
            withContext(NonCancellable) { host.close() }
            check(Files.readAttributes(parent, BasicFileAttributes::class.java, NOFOLLOW_LINKS).fileKey() == key)
            Files.list(parent).use { check(it.findAny().isEmpty) }
            event("OWNED_HOST_AND_EPHEMERAL_STORE_CLOSED")
        } catch (cleanup: Throwable) {
            event("CLEANUP_FAILED")
            primary?.addSuppressed(cleanup) ?: throw cleanup
        }
    }
    event("PASS_LOCAL_HOST_ADVERTISING_ONLY")
}
