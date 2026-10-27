package dev.p2pkit.sample.android.rpclab

import dev.p2pkit.sample.rpc.RpcMobileCapacityConfig
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.launch
import java.security.MessageDigest
import java.util.concurrent.atomic.AtomicReference

/** Debug-APK developer command. It names existing private input, never supplies pins or a network policy. */
internal class RpcLabUsbDeveloperCommand private constructor(
    val runLabel: String,
    private val sourceSha: String,
    private val artifactSha256: String,
    private val inboxSha256: String,
) {
    fun verify(config: RpcMobileCapacityConfig, inbox: String, compiledSource: String, installedArtifact: String) {
        require(config.hostPlatform == "Android" && config.runLabel == runLabel &&
            sourceSha == compiledSource && config.hostSourceSha == sourceSha &&
            artifactSha256 == installedArtifact && config.hostArtifactSha256 == artifactSha256)
        val digest = MessageDigest.getInstance("SHA-256").digest(inbox.toByteArray(Charsets.US_ASCII))
            .joinToString("") { "%02x".format(it) }
        require(digest == inboxSha256)
    }

    companion object {
        val EXTRA_NAMES = setOf("rpcUsbRunLabel", "rpcUsbSourceSha", "rpcUsbArtifactSha256", "rpcUsbInboxSha256")

        fun parse(extras: Map<String, String>): RpcLabUsbDeveloperCommand {
            require(extras.keys == EXTRA_NAMES)
            require(extras.getValue("rpcUsbRunLabel").matches(Regex("[a-z0-9-]{1,64}")))
            require(extras.getValue("rpcUsbSourceSha").matches(Regex("[a-f0-9]{40}")))
            for (name in setOf("rpcUsbArtifactSha256", "rpcUsbInboxSha256")) {
                require(extras.getValue(name).matches(Regex("[a-f0-9]{64}")))
            }
            return RpcLabUsbDeveloperCommand(extras.getValue("rpcUsbRunLabel"), extras.getValue("rpcUsbSourceSha"),
                extras.getValue("rpcUsbArtifactSha256"), extras.getValue("rpcUsbInboxSha256"))
        }
    }
}

/** The shortcut hands one exact command to the maintained RPC section; an occupied command is never replaced. */
internal class RpcLabUsbCommandQueue {
    private val pending = AtomicReference<RpcLabUsbDeveloperCommand?>()
    fun offer(command: RpcLabUsbDeveloperCommand): Boolean = pending.compareAndSet(null, command)
    fun take(): RpcLabUsbDeveloperCommand? = pending.getAndSet(null)
}

internal object RpcLabUsbDeveloperCommands {
    val queue = RpcLabUsbCommandQueue()
}

/** A closed receipt can precede the controller's final retirement; await only its already-owned cleanup task. */
internal fun CoroutineScope.deferRpcLabUsbCommand(cleanup: Job, afterRetirement: () -> Unit): Job = launch {
    cleanup.join()
    currentCoroutineContext().ensureActive()
    afterRetirement()
}
