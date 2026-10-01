package dev.p2pkit.sample.android.rpclab

import android.app.Activity
import android.app.Instrumentation
import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.os.Process
import android.system.ErrnoException
import android.system.Os
import android.system.OsConstants
import android.view.WindowManager
import dalvik.system.BaseDexClassLoader
import dev.p2pkit.core.AppId
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.rpc.RpcFailure
import dev.p2pkit.rpc.RpcFailureKind
import dev.p2pkit.rpc.RpcPlatform
import dev.p2pkit.rpc.RpcTrustPurpose
import dev.p2pkit.rpc.android
import dev.p2pkit.sample.rpc.RpcCapacityContract
import dev.p2pkit.sample.rpc.RpcPhoneCallResult
import dev.p2pkit.sample.rpc.RpcPhoneLab
import dev.p2pkit.sample.rpc.RpcPhoneSettings
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import java.io.File
import java.io.FileOutputStream
import java.security.KeyStore

/**
 * Real API24 ART controls, not Robolectric, API37 permission, LAN traffic, or capacity qualification.
 * Run only on an owned fresh emulator/app install. No fixture pin, payload, key or exception message is exported.
 */
class RpcLabRuntimeInstrumentation : Instrumentation() {
    private lateinit var arguments: Bundle
    private val result = Bundle()
    private var stage = "admission"
    private var completed = 0
    private var activity: Activity? = null
    private var lab: RpcPhoneLab? = null
    private var fixtureRoot: File? = null
    private var fixtureAlias: String? = null
    private var capacityFixture: File? = null

    override fun onCreate(arguments: Bundle?) {
        super.onCreate(arguments)
        this.arguments = Bundle(arguments ?: Bundle())
        start()
    }

    override fun onStart() {
        super.onStart()
        var failure: Throwable? = null
        runBlocking {
            try {
                withTimeout(90_000) { exercise() }
            } catch (error: Throwable) {
                failure = error
                result.putString("rpcFailureStage", stage)
                result.putString("rpcFailureClass", error.javaClass.simpleName)
                retainFailureSite(error)
            } finally {
                try {
                    withContext(NonCancellable) {
                        lab?.close()
                        activity?.let { owned ->
                            runOnMainSync { owned.finish() }
                            withTimeout(10_000) { while (!owned.isDestroyed) delay(50) }
                        }
                        cleanupFixture()
                    }
                    result.putString("rpcCleanup", "PASS")
                } catch (cleanup: Throwable) {
                    if (failure == null) failure = cleanup
                    result.putString("rpcCleanup", "FAIL")
                    result.putString("rpcCleanupFailureClass", cleanup.javaClass.simpleName)
                }
            }
        }
        result.putString("rpcCompleted", completed.toString())
        result.putString("rpcOutcome", if (failure == null && completed == CONTROL_COUNT) "PASS" else "FAIL")
        val code = if (failure == null && completed == CONTROL_COUNT) Activity.RESULT_OK else Activity.RESULT_CANCELED
        finish(code, result)
    }

    private fun passed(name: String) {
        completed++
        result.putString("rpcControl$completed", name)
    }

    private fun retainFailureSite(error: Throwable) {
        // Only checked-in sample source coordinates: never exception text,
        // payloads, filesystem paths, fixture tokens or platform stack frames.
        val names = setOf("RpcLabRuntimeInstrumentation.kt", "AndroidRpcCapacityFiles.kt",
            "AndroidRpcLabTrustStore.kt", "RpcLabActivity.kt")
        error.stackTrace.firstOrNull {
            it.className.startsWith("dev.p2pkit.sample.android.rpclab.") &&
                it.fileName in names && it.lineNumber > 0
        }?.let {
            result.putString("rpcFailureFile", it.fileName)
            result.putString("rpcFailureLine", it.lineNumber.toString())
        }
        if (error is ErrnoException) result.putString("rpcFailureErrno", error.errno.toString())
    }

    private suspend fun exercise() {
        val token = checkNotNull(arguments.getString("token")).also { check(it.matches(Regex("[a-f0-9]{32}"))) }
        check(arguments.getString("scope") == "supplemental-api24-rpc-controls")
        check(Build.VERSION.SDK_INT == 24 && "Dalvik" == System.getProperty("java.vm.name"))
        check(targetContext.packageName == "dev.p2pkit.sample.android")
        check(Process.myUid() == targetContext.applicationInfo.uid && targetContext.classLoader is BaseDexClassLoader)
        result.putString("rpcToken", token)
        result.putString("rpcApi", Build.VERSION.SDK_INT.toString())
        result.putString("rpcAbi", Build.SUPPORTED_ABIS.first())
        result.putString("rpcVm", System.getProperty("java.vm.name"))
        result.putString("rpcScope", "SUPPLEMENTAL_CONTROLS_NO_NETWORK_OR_CAPACITY_CLAIM")

        val root = File(targetContext.noBackupFilesDir.canonicalFile, "rpc-phone-lab-trust-$token")
        val alias = "dev.p2pkit.rpc.phone-lab.trust.v1-$token"
        val keys = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        check(!root.exists() && !keys.containsAlias(alias))
        fixtureRoot = root
        fixtureAlias = alias
        val store = AndroidRpcLabTrustStore(targetContext, token)
        val appId = RpcCapacityContract.appId
        val pinA = PeerFingerprint.parse("p2f1-" + "a".repeat(52))
        val pinB = PeerFingerprint.parse("p2f1-b" + "a".repeat(51))
        val hostPurpose = RpcTrustPurpose.HostClients
        val clientPurpose = RpcTrustPurpose.SelectedHosts

        stage = "keystore-round-trip"
        check(store.load(appId, hostPurpose).isEmpty())
        store.replace(appId, hostPurpose, setOf(pinA))
        check(AndroidRpcLabTrustStore(targetContext, token).load(appId, hostPurpose) == setOf(pinA))
        check(keys.getKey(alias, null).encoded == null) // The real Android Keystore key is not exportable.
        // API24 must establish the actual atomic close-on-exec property, not merely compile its flag.
        val descriptor = openRpcLabDescriptor(root.path, OsConstants.O_RDONLY or OsConstants.O_NOFOLLOW, 0)
        try { verifyOwnDirectoryCloseOnExec(root) }
        finally { Os.close(descriptor) }
        fsyncRpcLabDirectory(root)
        // The compatible public-API directory barrier must never accept a regular-file substitution.
        val approvalFile = File(root, "${hostPurpose.name}.aesgcm")
        val originalApproval = approvalFile.readBytes()
        check(runCatching { fsyncRpcLabDirectory(approvalFile) }.isFailure)
        check(approvalFile.readBytes().contentEquals(originalApproval))
        passed("keystore-round-trip-nonexportable")

        stage = "namespace-and-approval-validation"
        store.replace(appId, clientPurpose, setOf(pinB))
        check(store.load(appId, hostPurpose) == setOf(pinA) && store.load(appId, clientPurpose) == setOf(pinB))
        check(runCatching { store.load(AppId("not.the.synthetic.app"), hostPurpose) }.isFailure)
        val alphabet = "abcdefghijklmnopqrstuvwxyz234567"
        val tooMany = (0..128).map {
            PeerFingerprint.parse("p2f1-${alphabet[it / 32]}${alphabet[it % 32]}" + "a".repeat(50))
        }.toSet()
        check(runCatching { store.replace(appId, hostPurpose, tooMany) }.isFailure)
        check(store.load(appId, hostPurpose) == setOf(pinA))
        passed("namespaces-and-128-pin-bound")

        stage = "tampered-ciphertext"
        val hostFile = File(root, "${hostPurpose.name}.aesgcm")
        val clientFile = File(root, "${clientPurpose.name}.aesgcm")
        val originalHost = hostFile.readBytes()
        val originalClient = clientFile.readBytes()
        check(!originalHost.toString(Charsets.ISO_8859_1).contains(pinA.value))
        val damaged = originalHost.copyOf()
        damaged[damaged.lastIndex] = (damaged.last().toInt() xor 1).toByte()
        writeFixture(hostFile, damaged)
        try {
            check(runCatching { store.load(appId, hostPurpose) }.isFailure)
            check(runCatching { store.replace(appId, hostPurpose, emptySet()) }.isFailure)
        } finally { writeFixture(hostFile, originalHost) }
        check(store.load(appId, hostPurpose) == setOf(pinA))
        passed("tamper-fails-closed-without-erasing-approval")

        stage = "purpose-substitution"
        writeFixture(clientFile, originalHost)
        try { check(runCatching { store.load(appId, clientPurpose) }.isFailure) }
        finally { writeFixture(clientFile, originalClient) }
        check(store.load(appId, clientPurpose) == setOf(pinB))
        passed("authenticated-purpose-isolation")

        stage = "client-runtime"
        val settings = RpcPhoneSettings("10.0.2.0/24", "eth0", "10.0.2.15", 48123)
        val platform = RpcPlatform.android(targetContext)
        lab = RpcPhoneLab.createClient(platform, settings, store)
        val first = checkNotNull(lab)
        val fingerprint = first.fingerprint
        check(first.connectedClients == 0 && first.state != "Ready")
        val outcome = CompletableDeferred<RpcPhoneCallResult>()
        val operation = first.echo(large = false) { outcome.complete(it) }
        val reply = withTimeout(5_000) { outcome.await() }
        check(reply.completed == 0 && reply.failureKind == "NotConnected" && reply.executionEvidence == "NotSent")
        withTimeout(5_000) { while (operation.active) delay(10) }
        val rejected = runCatching { first.connect(pinA.value, "10.0.2.2", 48123) }.exceptionOrNull()
        check(rejected is RpcFailure && rejected.kind == RpcFailureKind.Unauthorized)
        first.close()
        first.close() // Public retained-close reobservation must be safe on real ART.
        lab = null
        lab = RpcPhoneLab.createClient(platform, settings, store)
        check(checkNotNull(lab).fingerprint == fingerprint)
        checkNotNull(lab).close()
        lab = null
        passed("real-rpc-client-identity-persistence-not-sent-and-close")

        stage = "invalid-phone-policy"
        check(runCatching { RpcPhoneLab.parseCapacityPins(pinA.value) }.isFailure)
        check(runCatching {
            RpcPhoneLab.createClient(platform, RpcPhoneSettings("0.0.0.0/0", "eth0", "10.0.2.15", 48123), store)
        }.isFailure)
        passed("phone-input-fails-closed")

        stage = "actual-debug-activity"
        val created = startActivitySync(Intent(targetContext, RpcLabActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        activity = created
        waitForIdleSync()
        check(created is RpcLabActivity && !created.isFinishing)
        check(created.window.attributes.flags and WindowManager.LayoutParams.FLAG_SECURE != 0)
        runOnMainSync { created.finish() }
        withTimeout(10_000) { while (!created.isDestroyed) delay(50) }
        activity = null
        passed("actual-foreground-debug-activity-and-destruction")

        stage = "mobile-private-control-files"
        val capacityHome = AndroidRpcCapacityFiles.prepareHome(targetContext)
        val capacityRoot = File(capacityHome, "control-$token")
        check(capacityRoot.mkdir())
        capacityFixture = capacityRoot
        Os.chmod(capacityRoot.path, 0x1c0)
        val files = AndroidRpcCapacityFiles(targetContext, capacityRoot.name)
        val input = File(capacityRoot, "inbox.txt")
        FileOutputStream(input).use { it.write("schema=1\n".toByteArray()); it.fd.sync() }
        Os.chmod(input.path, 0x180)
        check(files.read("inbox.txt") == "schema=1\n" && files.read("stop.txt", optional = true) == null)
        files.publish("ready.txt", "ready=true\n")
        check(checkNotNull(capacityRoot.listFiles()).none { it.name.startsWith(".capacity-") })
        check(runCatching { files.publish("ready.txt", "ready=false\n") }.isFailure)
        check(files.read("ready.txt") == "ready=true\n")
        check(checkNotNull(capacityRoot.listFiles()).none { it.name.startsWith(".capacity-") })
        files.publish("telemetry.txt", "sequence=1\n")
        files.publish("telemetry.txt", "sequence=2\n")
        check(files.read("telemetry.txt") == "sequence=2\n")
        check(checkNotNull(capacityRoot.listFiles()).none { it.name.startsWith(".capacity-") })
        check(runCatching { files.read("../unowned") }.isFailure)
        check(runCatching { files.publish("failed.txt", "x=" + "a".repeat(16_384)) }.isFailure)
        val link = File(capacityRoot, "linked.txt")
        Os.link(input.path, link.path)
        try { check(runCatching { files.read("inbox.txt") }.isFailure) }
        finally { Os.remove(link.path) }
        check(files.read("inbox.txt") == "schema=1\n")
        Os.chmod(input.path, 0x1b6) //0666 is never an admitted developer-imported input.
        try { check(runCatching { files.read("inbox.txt") }.isFailure) }
        finally { Os.chmod(input.path, 0x180) }
        Os.remove(input.path)
        Os.symlink(File(capacityRoot, "ready.txt").path, input.path)
        try { check(runCatching { files.read("inbox.txt") }.isFailure) }
        finally { Os.remove(input.path) }
        check(files.read("ready.txt") == "ready=true\n" && files.read("inbox.txt", optional = true) == null)
        passed("mobile-private-files-atomic-publication-and-negative-admission")

        stage = "mobile-self-process-resources"
        val installed = androidRpcInstalledArtifact(targetContext)
        check(installed.matches(Regex("[a-f0-9]{64}")) && androidRpcInstalledArtifact(targetContext) == installed)
        var previousCpu = 0L
        repeat(32) {
            val resources = androidRpcPhoneProcessStats()
            check(resources.cpuNanos >= previousCpu && resources.residentBytes > 0 && resources.nativeThreads > 0)
            check(resources.cpuNanos % 1_000_000 == 0L) // Actual Android API precision, not a claimed nanosecond timer.
            previousCpu = resources.cpuNanos
        }
        passed("mobile-actual-self-process-cpu-rss-and-thread-counters")

        stage = "missing-keystore-key"
        keys.deleteEntry(alias) // Only the new, nonce-scoped synthetic fixture key, never a real UI identity.
        check(runCatching { store.load(appId, hostPurpose) }.isFailure)
        check(runCatching { store.replace(appId, hostPurpose, emptySet()) }.isFailure)
        check(hostFile.readBytes().contentEquals(originalHost) && !keys.containsAlias(alias))
        passed("missing-key-never-recreates-or-clears-existing-trust")
    }

    private fun writeFixture(file: File, bytes: ByteArray) {
        check(file.parentFile == fixtureRoot)
        FileOutputStream(file).use { it.write(bytes); it.fd.sync() }
    }

    private fun verifyOwnDirectoryCloseOnExec(directory: File) {
        // Os.fcntlInt itself is public only since API30. Read the kernel's flags
        // for our one nonce-scoped directory descriptor instead: no hidden API,
        // no descriptor guessing, and no opening keys or another process's files.
        val entries = checkNotNull(File("/proc/self/fd").listFiles()).also { check(it.size <= 4096) }
        val matching = entries.filter { entry ->
            check(entry.name.matches(Regex("[0-9]+")))
            try { Os.readlink(entry.path) == directory.canonicalPath }
            catch (missing: ErrnoException) {
                if (missing.errno != OsConstants.ENOENT) throw missing
                false // listFiles' own directory descriptor may already have closed.
            }
        }
        check(matching.size == 1)
        val info = File("/proc/self/fdinfo", matching.single().name).readText().also { check(it.length <= 4096) }
        val flags = Regex("(?m)^flags:\\s+([0-7]+)$").findAll(info).toList()
        check(flags.size == 1 && flags.single().groupValues[1].toLong(8) and 0x80000L != 0L)
    }

    private fun cleanupFixture() {
        capacityFixture?.let { root ->
            val known = setOf("inbox.txt", "ready.txt", "telemetry.txt", "linked.txt")
            for (file in checkNotNull(root.listFiles())) {
                val info = Os.lstat(file.path)
                check(file.name in known && info.st_uid == Process.myUid() &&
                    (OsConstants.S_ISREG(info.st_mode) || OsConstants.S_ISLNK(info.st_mode)))
                Os.remove(file.path)
            }
            check(root.delete())
        }
        fixtureAlias?.let { alias ->
            KeyStore.getInstance("AndroidKeyStore").apply { load(null); deleteEntry(alias) }
        }
        fixtureRoot?.let { root ->
            val known = RpcTrustPurpose.entries.map { "${it.name}.aesgcm" }.toSet() + "trust.lock"
            for (file in checkNotNull(root.listFiles())) {
                val metadata = Os.lstat(file.path)
                check(file.name in known && OsConstants.S_ISREG(metadata.st_mode) && metadata.st_uid == Process.myUid())
                check(file.delete())
            }
            check(root.delete())
        }
    }

    private companion object { const val CONTROL_COUNT = 10 }
}
