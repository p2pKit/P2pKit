package dev.p2pkit.sample.android.rpclab

import dev.p2pkit.sample.rpc.RpcMobileCapacityConfig
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CopyableThrowable
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.Job
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import java.security.MessageDigest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertSame
import kotlin.test.assertTrue

@OptIn(ExperimentalCoroutinesApi::class)
class RpcLabUsbDeveloperCommandTest {
    private class CloseFailure : IllegalStateException(), CopyableThrowable<CloseFailure> {
        override fun createCopy(): CloseFailure? = null
    }
    private val source = "2".repeat(40)
    private val artifact = "3".repeat(64)

    private fun inbox(count: Int = 256): String {
        val alphabet = "abcdefghijklmnopqrstuvwxyz234567"
        val pins = List(count) { "p2f1-${alphabet[it / 32]}${alphabet[it % 32]}" + "a".repeat(50) }
        return "schema=2\nscope=mobile-usb-capacity\nrunLabel=synthetic-mobile\nclientCount=$count\n" +
            "runNonce=${"1".repeat(64)}\nhostSourceSha=$source\nhostPlatform=Android\n" +
            "hostArtifactSha256=$artifact\nsubnets=192.168.14.0/24\nhostInterface=wlan0\n" +
            "hostAddress=192.168.14.2\nhostPort=48123\nclientPins=${pins.joinToString(",")}\n"
    }

    private fun extras(text: String = inbox()): MutableMap<String, String> = linkedMapOf(
        "rpcUsbRunLabel" to "synthetic-mobile", "rpcUsbSourceSha" to source, "rpcUsbArtifactSha256" to artifact,
        "rpcUsbInboxSha256" to MessageDigest.getInstance("SHA-256").digest(text.toByteArray(Charsets.US_ASCII))
            .joinToString("") { "%02x".format(it) },
    )

    @Test
    fun exactPrivate256InputCanBeVerifiedWithoutProvisioningOrImportingAnything() {
        val text = inbox()
        val command = RpcLabUsbDeveloperCommand.parse(extras(text))
        val config = RpcMobileCapacityConfig.parse(text)
        command.verify(config, text, source, artifact)
        assertEquals("synthetic-mobile", command.runLabel)
        assertEquals(256, config.clientCount)
        assertTrue(text.length <= 16_384)
    }

    @Test
    fun wrongSourceArtifactInboxRunAndCapacitySelectionCannotAuthorizeStart() {
        val text = inbox()
        val config = RpcMobileCapacityConfig.parse(text)
        val command = RpcLabUsbDeveloperCommand.parse(extras(text))
        for (fields in listOf(extras(text).apply { put("rpcUsbRunLabel", "another-run") },
            extras(text).apply { put("rpcUsbSourceSha", "4".repeat(40)) },
            extras(text).apply { put("rpcUsbArtifactSha256", "4".repeat(64)) },
            extras(text).apply { put("rpcUsbInboxSha256", "4".repeat(64)) })) {
            assertFailsWith<IllegalArgumentException> {
                RpcLabUsbDeveloperCommand.parse(fields).verify(config, text, source, artifact)
            }
        }
        assertFailsWith<IllegalArgumentException> { command.verify(config, text, "4".repeat(40), artifact) }
        assertFailsWith<IllegalArgumentException> { command.verify(config, text, source, "4".repeat(64)) }
        val differentCount = inbox(128)
        assertFailsWith<IllegalArgumentException> {
            command.verify(RpcMobileCapacityConfig.parse(differentCount), differentCount, source, artifact)
        }
    }

    @Test
    fun incompleteMalformedOrUnscopedArgumentsCannotBecomeACommand() {
        for (fields in listOf(extras().apply { remove("rpcUsbInboxSha256") },
            extras().apply { put("pins", "arbitrary-input") },
            extras().apply { put("rpcUsbRunLabel", "../unowned") },
            extras().apply { put("rpcUsbRunLabel", "synthetic-mobile\n") },
            extras().apply { put("rpcUsbSourceSha", "main") },
            extras().apply { put("rpcUsbArtifactSha256", "assumed-install") },
            extras().apply { put("rpcUsbInboxSha256", "4".repeat(65)) })) {
            assertFailsWith<IllegalArgumentException> { RpcLabUsbDeveloperCommand.parse(fields) }
        }
    }

    @Test
    fun shortcutQueueIsCreateOnlyAndConsumesOneCommandExactlyOnce() {
        val queue = RpcLabUsbCommandQueue()
        val first = RpcLabUsbDeveloperCommand.parse(extras())
        val second = RpcLabUsbDeveloperCommand.parse(extras().apply { put("rpcUsbRunLabel", "another-run") })
        assertNull(queue.take())
        assertTrue(queue.offer(first))
        assertFalse(queue.offer(second))
        assertSame(first, queue.take())
        assertNull(queue.take())
        assertTrue(queue.offer(second))
        assertSame(second, queue.take())
    }

    private fun hold(owner: RpcLabRuntimeOwner<Any>, runtime: Any): RpcLabRuntimeOwner.Token {
        val creator = Job()
        val token = owner.beginCreation(creator)
        owner.retain(token, runtime)
        owner.finishCreation(token)
        creator.complete()
        return token
    }

    @Test
    fun nextCommandWaitsForActualOwnerRetirementAfterTheClosedReceiptWasPublished() = runTest {
        val owner = RpcLabRuntimeOwner<Any>()
        val token = hold(owner, Any())
        val closed = CompletableDeferred<Unit>()
        val finishRetirement = CompletableDeferred<Unit>()
        val cleanup = backgroundScope.launch {
            owner.retire(token) {
                closed.complete(Unit)
                finishRetirement.await()
            }
        }
        runCurrent()
        assertTrue(closed.isCompleted)
        assertTrue(owner.occupied)
        var admitted = false
        val deferred = backgroundScope.deferRpcLabUsbCommand(cleanup) {
            assertFalse(owner.occupied)
            admitted = true
        }
        runCurrent()
        assertFalse(admitted)
        finishRetirement.complete(Unit)
        runCurrent()
        deferred.join()
        assertTrue(admitted)
        assertFalse(owner.occupied)
    }

    @Test
    fun failedCleanupCompletesItsTaskButRetainsTheExactOwnerAndRefusesANextCommand() = runTest {
        val owner = RpcLabRuntimeOwner<Any>()
        val runtime = Any()
        val token = hold(owner, runtime)
        val closeFailure = CloseFailure()
        val finish = CompletableDeferred<Unit>()
        val cleanup = backgroundScope.launch {
            try { owner.retire(token) { finish.await(); throw closeFailure } }
            catch (_: CloseFailure) { /* The controller likewise records failure without losing its owner. */ }
        }
        var admitted = false
        val deferred = backgroundScope.deferRpcLabUsbCommand(cleanup) {
            if (!owner.occupied && owner.failure == null) admitted = true
        }
        runCurrent()
        finish.complete(Unit)
        runCurrent()
        deferred.join()
        assertTrue(cleanup.isCompleted)
        assertFalse(admitted)
        assertTrue(owner.occupied)
        assertSame(runtime, owner.current(token))
        assertSame(closeFailure, owner.failure?.cause)
        owner.retire(token) { } // Retire only this synthetic fixture before the test returns.
    }

    @Test
    fun cancellingAQueuedCommandDoesNotCancelTheIndependentOwnedCleanupOrStartALaterRun() = runTest {
        val owner = RpcLabRuntimeOwner<Any>()
        val token = hold(owner, Any())
        val finish = CompletableDeferred<Unit>()
        val cleanup = backgroundScope.launch { owner.retire(token) { finish.await() } }
        var admitted = false
        val deferred = backgroundScope.deferRpcLabUsbCommand(cleanup) { admitted = true }
        runCurrent()
        deferred.cancelAndJoin()
        assertTrue(owner.occupied)
        assertFalse(cleanup.isCancelled)
        finish.complete(Unit)
        runCurrent()
        cleanup.join()
        assertFalse(owner.occupied)
        assertFalse(admitted)
    }
}
