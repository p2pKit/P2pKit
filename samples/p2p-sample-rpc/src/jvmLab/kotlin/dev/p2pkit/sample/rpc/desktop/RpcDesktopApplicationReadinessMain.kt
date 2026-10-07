package dev.p2pkit.sample.rpc.desktop

import dev.p2pkit.rpc.RpcExecutionEvidence
import dev.p2pkit.sample.rpc.RpcApplicationExample
import dev.p2pkit.sample.rpc.RpcApplicationSession
import dev.p2pkit.sample.rpc.RpcDiscoveryConnectionState
import dev.p2pkit.sample.rpc.RpcPhoneBuildStamp
import dev.p2pkit.sample.rpc.RpcRequestOutcome
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

internal fun parseDesktopApplicationReadinessArguments(args: Array<String>): Path {
    require(args.size == 2 && args[0] == "--approved-local-application") {
        "Explicit local advertising/discovery, synthetic approval and RPC authorization plus private parent required"
    }
    return Path.of(args[1]).also { require(it.isAbsolute && it.normalize() == it) }
}

/**
 * Explicit two-identity, same-Mac application check. Uses real discovery and adapters, never endpoint fallback.
 * It is NOT another-device, AP multicast, capacity, UI, or persistent-profile qualification.
 * Only the newly created synthetic client's exact authenticated pin may be approved. No existing profile is opened.
 */
fun main(args: Array<String>) = runBlocking {
    val parent = parseDesktopApplicationReadinessArguments(args)
    check(RpcPhoneBuildStamp.SOURCE_CLEAN)
    check(!System.getProperty("dev.p2pkit.lan.macos.nativeDir").isNullOrBlank())
    LabFiles.privateDirectory(parent)
    check(parent.toRealPath() == parent)
    val key = Files.readAttributes(parent, BasicFileAttributes::class.java, NOFOLLOW_LINKS).fileKey()
    check(key != null)
    Files.list(parent).use { check(it.findAny().isEmpty) }
    val settings = desktopRpcAutomaticSettings(desktopRpcNetworks()) // No forced interface, port or route.
    val hostApp = RpcApplicationSession()
    val clientApp = RpcApplicationSession()
    val host = DesktopRpcRuntime.create(parent, hostApp)
    val client = DesktopRpcRuntime.create(parent, clientApp)
    var phase = "start-host"
    var passed = false
    var primary: Throwable? = null
    fun event(value: String) {
        println("{\"phase\":\"$value\",\"source\":\"${RpcPhoneBuildStamp.SOURCE_COMMIT}\"," +
            "\"scope\":\"SAME_MAC_APPLICATION_NOT_DEVICE_OR_RELEASE_QUALIFICATION\"}")
    }
    suspend fun awaitState(check: () -> Boolean) = withTimeout(15_000) {
        while (!check()) delay(100)
    }
    suspend fun approveOnlyOwnedClient() {
        awaitState { host.pending().any { it.fingerprint == client.fingerprint } }
        val requests = host.pending()
        check(requests.all { it.fingerprint == client.fingerprint }) { "Unexpected external approval request" }
        val request = requests.single()
        check(request.origin == "Nearby")
        host.approve(DesktopRpcPending(request.requestId, request.fingerprint, request.origin))
        awaitState { client.status(false).connection?.state == RpcDiscoveryConnectionState.Ready }
        check(host.status(true).trusted.any { it.fingerprint == client.fingerprint })
        check(client.status(false).trusted.any { it.fingerprint == host.fingerprint })
    }
    try {
        withTimeout(30_000) { host.start(true, settings) }
        check(host.state == "Running")
        event("HOST_RUNNING")
        phase = "discover"
        withTimeout(30_000) { client.start(false, settings) }
        check(host.fingerprint != client.fingerprint)
        awaitState { client.status(false).nearby.count { it.fingerprint == host.fingerprint } == 1 }
        check(host.pending().isEmpty())
        check(client.status(false).trusted.isEmpty() && host.status(true).trusted.isEmpty())
        check(client.status(false).connection?.selectedFingerprint == null)
        event("DISCOVERED_WITHOUT_IMPLICIT_TRUST")
        phase = "first-approval"
        check(client.select(host.fingerprint) == null)
        approveOnlyOwnedClient()
        event("EXPLICIT_APPROVAL_AND_PINNED_CONNECTION")
        phase = "typed-requests"
        for (example in RpcApplicationExample.entries) {
            check(client.example(example) == null)
            val result = clientApp.history.entries().last()
            val expected = if (example in setOf(RpcApplicationExample.BusinessError,
                    RpcApplicationExample.ValidationError)) RpcRequestOutcome.BusinessError
                else RpcRequestOutcome.Succeeded
            check(result.outcome == expected && result.responsePreview.isNotEmpty())
            check(result.requestId != null && result.peerFingerprint == host.fingerprint)
            check(result.executionEvidence == RpcExecutionEvidence.HandlerFinished)
            awaitState {
                host.status(true) // Existing passive history projection; not a fixture response.
                hostApp.history.entries().any {
                    it.requestId == result.requestId && it.peerFingerprint == client.fingerprint &&
                        it.outcome == expected
                }
            }
        }
        check(clientApp.history.entries().size == 5 && hostApp.history.entries().size == 5)
        event("FIVE_TYPED_REQUESTS_AND_MATCHED_HOST_HISTORY")
        phase = "host-revocation"
        host.forget(client.fingerprint)
        awaitState { client.status(false).connection?.state == RpcDiscoveryConnectionState.RequiresApproval }
        check(host.pending().isEmpty())
        check(host.status(true).trusted.none { it.fingerprint == client.fingerprint })
        check(client.status(false).trusted.any { it.fingerprint == host.fingerprint })
        event("REVOCATION_REQUIRES_APPROVAL_WITHOUT_POPUP_RETRY")
        phase = "explicit-renewal"
        check(client.select(host.fingerprint) == null)
        approveOnlyOwnedClient()
        check(client.example(RpcApplicationExample.GetUser) == null)
        check(clientApp.history.entries().last().outcome == RpcRequestOutcome.Succeeded)
        event("EXPLICIT_REAPPROVAL_AND_TYPED_REPLY")
        passed = true
    } catch (failure: Throwable) {
        primary = failure
        event("FAILED_$phase") // Fixed phase only; no nested errors, network identity or application payload.
        throw failure
    } finally {
        var cleanup: Throwable? = null
        withContext(NonCancellable) {
            for (runtime in listOf(client, host)) {
                try { runtime.close() } catch (failure: Throwable) {
                    if (cleanup == null) cleanup = failure else cleanup.addSuppressed(failure)
                }
            }
        }
        if (cleanup == null) {
            try {
                check(Files.readAttributes(parent, BasicFileAttributes::class.java, NOFOLLOW_LINKS).fileKey() == key)
                Files.list(parent).use { check(it.findAny().isEmpty) }
                event("OWNED_RUNTIMES_AND_EPHEMERAL_STORES_CLOSED")
            } catch (failure: Throwable) { cleanup = failure }
        }
        cleanup?.let { failure ->
            event("CLEANUP_FAILED")
            primary?.addSuppressed(failure) ?: throw failure
        }
    }
    check(passed)
    event("PASS_SAME_MAC_APPLICATION_CHECK")
}
