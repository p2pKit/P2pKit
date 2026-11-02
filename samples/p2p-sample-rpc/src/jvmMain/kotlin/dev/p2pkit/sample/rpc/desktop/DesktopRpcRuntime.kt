package dev.p2pkit.sample.rpc.desktop

import dev.p2pkit.rpc.RpcPlatform
import dev.p2pkit.rpc.RpcTrustStore
import dev.p2pkit.rpc.jvm
import dev.p2pkit.sample.rpc.RpcDeviceTestPhase
import dev.p2pkit.sample.rpc.RpcApplicationExample
import dev.p2pkit.sample.rpc.RpcApplicationInput
import dev.p2pkit.sample.rpc.RpcApplicationSession
import dev.p2pkit.sample.rpc.RpcPhoneCallResult
import dev.p2pkit.sample.rpc.RpcPhoneLab
import dev.p2pkit.sample.rpc.RpcPhonePairing
import dev.p2pkit.sample.rpc.RpcPhoneSettings
import dev.p2pkit.sample.rpc.lab.LabFiles
import dev.p2pkit.sample.rpc.lab.LabTrustStore
import dev.p2pkit.sample.rpc.lab.LabVault
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.withContext
import java.nio.file.Files
import java.nio.file.LinkOption
import java.nio.file.Path
import java.nio.file.attribute.BasicFileAttributes
import java.nio.file.attribute.PosixFilePermissions

/** Explicitly separate automatic application networking from the older non-advertising Host/Stop probe. */
internal fun desktopRpcApplicationFactory(
    host: Boolean, nearby: Boolean,
): suspend (RpcPlatform, RpcPhoneSettings, RpcTrustStore, RpcApplicationSession) -> RpcPhoneLab = when {
    nearby && host -> RpcPhoneLab.Companion::createNearbyApplicationHost
    nearby -> RpcPhoneLab.Companion::createNearbyApplicationClient
    host -> RpcPhoneLab.Companion::createApplicationHost
    else -> RpcPhoneLab.Companion::createApplicationClient
}

/** Public RPC facade, protected persistent or owned ephemeral identity, no capacity import or permissive transport. */
internal class DesktopRpcRuntime private constructor(
    private val parent: Path, private val application: RpcApplicationSession,
    private val profile: DesktopRpcProfile? = null,
) {
    private var directory: Path? = null
    private var directoryKey: Any? = null
    private var identityDirectory: Path? = null
    private var identityDirectoryKey: Any? = null
    private var vault: LabVault? = null
    private var lab: RpcPhoneLab? = null
    private var savedTests = ""
    private var creationCleanupFailure: Throwable? = null

    // The owner receives this runtime BEFORE any file/socket allocation, including partial initialization.
    internal fun prepareStore() {
        check(directory == null && vault == null)
        if (profile != null) { vault = profile.vault; return }
        val root = Files.createTempDirectory(parent.toRealPath(), "p2pkit-rpc-desktop-",
            PosixFilePermissions.asFileAttribute(PosixFilePermissions.fromString("rwx------")))
        directory = root
        directoryKey = directoryIdentity(root)
        val identity = LabFiles.newDirectory(root, "identity")
        identityDirectory = identity
        identityDirectoryKey = directoryIdentity(identity)
        vault = LabVault(identity)
    }

    suspend fun start(host: Boolean, settings: RpcPhoneSettings, nearby: Boolean = true) {
        application.deviceTests.configureDeviceName(when {
            System.getProperty("os.name").startsWith("Mac") -> "Mac (JVM)"
            System.getProperty("os.name").startsWith("Windows") -> "Windows (JVM)"
            else -> "Linux (JVM)"
        })
        prepareStore()
        val store = checkNotNull(vault)
        if (application.deviceTests.reports.isEmpty()) {
            store.read("device-test-results-v1")?.let { application.deviceTests.restoreJson(it.decodeToString()) }
        }
        savedTests = application.deviceTests.exportJson()
        val platform = RpcPlatform.jvm(store)
        val trust = LabTrustStore(store)
        try {
            lab = desktopRpcApplicationFactory(host, nearby)(platform, settings, trust, application)
        } catch (failure: Throwable) {
            // The facade closes failed creation on Exception, retaining failed close as suppressed evidence.
            // Do not destroy its store when cleanup is unproven or a fatal error bypassed that contract.
            if (failure !is Exception || failure.suppressed.isNotEmpty()) creationCleanupFailure = failure
            throw failure
        }
    }

    val fingerprint: String get() = checkNotNull(lab).fingerprint
    val state: String get() = checkNotNull(lab).state
    val connectedClients: Int get() = checkNotNull(lab).connectedClients
    fun pending(): List<RpcPhonePairing> = checkNotNull(lab).pending()

    /** Passive facade values only; the run owner reads these off the EDT and joins the reader before close. */
    fun status(host: Boolean): DesktopRpcStatus {
        val current = checkNotNull(lab)
        val diagnostics = current.diagnostics
        val process = java.lang.management.ManagementFactory.getOperatingSystemMXBean()
            as com.sun.management.OperatingSystemMXBean
        application.deviceTests.observeResources(process.processCpuTime,
            java.lang.management.ManagementFactory.getMemoryMXBean().heapMemoryUsage.used.coerceAtLeast(1),
            "JVM_HEAP_BYTES", java.lang.management.ManagementFactory.getThreadMXBean().threadCount,
            "JVM_THREADS", null)
        saveTests()
        return DesktopRpcStatus(
            role = if (host) DesktopRpcRole.Host else DesktopRpcRole.Client,
            state = current.state,
            fingerprint = current.fingerprint,
            clients = current.connectedClients,
            completed = diagnostics.completedCalls,
            queued = diagnostics.queuedCalls,
            pending = if (host) current.pending().map { DesktopRpcPending(it.requestId, it.fingerprint, it.origin) }
                else emptyList(),
            historyRevision = application.history.revision,
            nearby = current.nearbyHosts(), trusted = current.trustedDevices(),
            connection = current.discoveryConnection, networkActivity = current.networkActivity,
            metrics = current.requestMetrics, tests = application.deviceTests.progress,
        )
    }

    private fun saveTests() = synchronized(application.deviceTests) {
        if (vault == null) return@synchronized
        val tests = application.deviceTests
        val archive = DesktopRpcTestArchive(checkNotNull(vault))
        tests.unarchivedReports.forEach { archive.retain(tests, it) }
        val text = application.deviceTests.exportJson()
        if (text != savedTests) {
            checkNotNull(vault).replace("device-test-results-v1", text.toByteArray())
            savedTests = text
        }
    }

    fun allowTests(enabled: Boolean) { checkNotNull(lab).allowDeviceTestsFromHost(enabled) }
    fun cancelTest() { lab?.cancelDeviceTest() }
    suspend fun test(phase: RpcDeviceTestPhase, peer: String?): String? = awaitDesktopRpcCompletion { completed ->
        val operation = checkNotNull(lab).beginDeviceTest(phase, peer, completed)
        val cancel: () -> Unit = { operation.cancel() }
        cancel
    }
    suspend fun multiTest(phase: RpcDeviceTestPhase, peers: List<String>): String? =
        awaitDesktopRpcCompletion { completed ->
            val operation = checkNotNull(lab).beginMultiDeviceTests(phase, peers, completed)
            val cancel: () -> Unit = { operation.cancel() }
            cancel
        }

    suspend fun deleteTest(runId: String) {
        val tests = application.deviceTests
        val report = checkNotNull(tests.reports.firstOrNull { it.runId == runId })
        check(tests.beginResultDeletion(runId)) { "Stop or finish active tests before deleting outputs" }
        var deleted = false
        try {
            DesktopRpcTestArchive(checkNotNull(vault)).delete(tests, report)
            deleted = true
        } finally { tests.finishResultDeletion(runId, deleted) }
        saveTests()
    }

    suspend fun invitation(): String = checkNotNull(lab).invitation()
    suspend fun approve(selected: DesktopRpcPending) {
        val current = checkNotNull(lab)
        check(current.pending().any { it.requestId == selected.requestId && it.fingerprint == selected.fingerprint }) {
            "The explicitly confirmed pending request is no longer current"
        }
        current.approve(selected.requestId)
    }
    suspend fun reject(selected: DesktopRpcPending) {
        val current = checkNotNull(lab)
        check(current.pending().any { it.requestId == selected.requestId && it.fingerprint == selected.fingerprint })
        current.reject(selected.requestId)
    }

    suspend fun select(fingerprint: String): String? = awaitDesktopRpcCompletion { completed ->
        val operation = checkNotNull(lab).beginSelectNearby(fingerprint, true, completed)
        val cancel: () -> Unit = { operation.cancel() }
        cancel
    }

    suspend fun forget(fingerprint: String) {
        val current = checkNotNull(lab)
        check(current.trustedDevices().any { it.fingerprint == fingerprint })
        current.revoke(fingerprint)
    }

    suspend fun pairAndConnect(invitation: String) = checkNotNull(lab).pairAndConnect(invitation)

    suspend fun echo(): RpcPhoneCallResult = awaitDesktopRpcCompletion { completed ->
        val operation = checkNotNull(lab).echo(large = false, onComplete = completed)
        val cancel: () -> Unit = { operation.cancel() }
        cancel
    }

    suspend fun example(example: RpcApplicationExample): String? = awaitDesktopRpcCompletion { completed ->
        val operation = checkNotNull(lab).beginExample(example, completed)
        val cancel: () -> Unit = { operation.cancel() }
        cancel
    }

    suspend fun request(input: RpcApplicationInput): String? = awaitDesktopRpcCompletion { completed ->
        val operation = checkNotNull(lab).beginRequest(input, completed)
        val cancel: () -> Unit = { operation.cancel() }
        cancel
    }

    suspend fun close() = withContext(NonCancellable) {
        // Physical runtime closure precedes any identity destruction, including failed initialization.
        check(creationCleanupFailure == null) { "Failed factory cleanup requires owner review" }
        lab?.close()
        directory?.let { root ->
            check(directoryKey != null && directoryIdentity(root) == directoryKey)
            identityDirectory?.let { identity ->
                check(identityDirectoryKey != null && directoryIdentity(identity) == identityDirectoryKey)
            }
        }
        saveTests()
        directory?.let { root ->
            check(directoryKey != null && directoryIdentity(root) == directoryKey)
            identityDirectory?.let { identity ->
                check(identityDirectoryKey != null && directoryIdentity(identity) == identityDirectoryKey)
                val store = vault
                if (store == null) Files.delete(identity) else store.destroy()
            }
            // Delete only the inode-matched EMPTY owned directory; foreign content makes close fail.
            check(directoryIdentity(root) == directoryKey)
            Files.delete(root)
        }
    }

    companion object {
        fun create(
            parent: Path = Path.of(System.getProperty("java.io.tmpdir")),
            application: RpcApplicationSession = RpcApplicationSession(),
            profile: DesktopRpcProfile? = null,
        ): DesktopRpcRuntime = DesktopRpcRuntime(parent, application, profile)

        private fun directoryIdentity(path: Path): Any {
            LabFiles.privateDirectory(path)
            return checkNotNull(Files.readAttributes(path, BasicFileAttributes::class.java,
                LinkOption.NOFOLLOW_LINKS).fileKey())
        }
    }
}

/** Keep the foreground slot until the facade's actual terminal callback, even after caller cancellation. */
internal suspend fun <T> awaitDesktopRpcCompletion(start: ((T) -> Unit) -> (() -> Unit)): T {
    val completion = CompletableDeferred<T>()
    val cancel = start { completion.complete(it) }
    return try { completion.await() }
    catch (cancelled: CancellationException) {
        withContext(NonCancellable) { cancel(); completion.await() }
        throw cancelled
    }
}
