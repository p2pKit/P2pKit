package dev.p2pkit.sample.rpc.profile

import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.rpc.RpcTrustPurpose
import dev.p2pkit.sample.rpc.RpcCapacityContract
import dev.p2pkit.sample.rpc.desktop.DesktopRpcProfile
import dev.p2pkit.sample.rpc.lab.LabFiles
import java.io.IOException
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference
import kotlinx.coroutines.test.runTest
import kotlin.concurrent.thread
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFails
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertSame
import kotlin.test.assertTrue

/** Inert startup call-order/failure controls; not NTFS persistence, Windows execution or crash-recovery evidence. */
class WindowsProfileStartupSyncTest {
    private fun password() = "synthetic-startup-sync-passphrase".toCharArray()
    private fun await(latch: CountDownLatch) = assertTrue(latch.await(5, TimeUnit.SECONDS))
    private fun recordName(namespace: String) = LabFiles.sha256(namespace.toByteArray(Charsets.UTF_8)) + ".aesgcm"
    private fun trustNamespace(purpose: RpcTrustPurpose) =
        "rpc-trust:${RpcCapacityContract.appId.value}:${purpose.name}"

    private data class Saved(val id: Long, val directory: Boolean, val bytes: List<Byte>)
    private fun snapshot(store: WindowsProfileModel.Store): Map<String, Saved> = buildMap {
        fun visit(path: String, node: WindowsProfileModel.Node) {
            put(path, Saved(node.id, node.directory, node.bytes.toList()))
            node.entries.forEach { (name, child) -> visit("$path/$name", child) }
        }
        visit("", store.root)
    }

    private fun assertRetired(model: WindowsProfileModel) {
        assertEquals(0, model.remaining)
        assertTrue(model.store.locks.isEmpty())
        assertEquals(model.closeCalls.distinct(), model.closeCalls)
    }

    private fun populated(): WindowsProfileModel.Store {
        val model = WindowsProfileModel()
        val profile = DesktopRpcProfile.open(WindowsProfileFiles.openForValidation(model), password())
        try { profile.vault.putIfAbsent("synthetic-identity", byteArrayOf(17, 23)) }
        finally { profile.close() }
        assertRetired(model)
        return model.store
    }

    private data class Lease(val directory: Long, val name: String, val nonBlocking: Boolean, val token: Long)

    /** Records original token ownership; sync itself remains the existing inert model's no-op. */
    private class StartupNative(
        val model: WindowsProfileModel,
        private val requireStartupSync: Boolean = true,
    ) : WindowsProfileNativeApi by model {
        var root = 0L
            private set
        var identity = 0L
            private set
        var beforeSync: () -> Unit = {}
        var failVerificationAfterSync: String? = null
        val verificationFailure = IOException("synthetic post-sync identity verification failure")
        var vaultCloseFailure: IOException? = null
        val opened = mutableListOf<Long>()
        val leases = mutableListOf<Lease>()
        val activeLeases = mutableSetOf<Long>()
        val syncCalls = mutableListOf<Long>()
        val dataReads = mutableListOf<String>()
        val mutations = mutableListOf<String>()
        val closeAttempts = mutableListOf<Long>()
        val events = mutableListOf<String>()
        val verifiedAfterSync = mutableSetOf<Long>()
        var syncReturned = false
            private set

        override fun openRoot(): Long = model.openRoot().also { root = it; opened += it }

        override fun child(directory: Long, name: String, create: Boolean): Long {
            if (create) mutations += "create:$name"
            assertEquals(root, directory)
            assertEquals("identity", name)
            assertEquals(0L, identity)
            return model.child(directory, name, create).also { identity = it; opened += it }
        }

        override fun directoryIdentity(handle: Long): LongArray {
            val value = model.directoryIdentity(handle)
            if (syncReturned) {
                val name = if (handle == identity) "identity" else "profile"
                events += "verify:$name"
                if (failVerificationAfterSync == name) throw verificationFailure
                verifiedAfterSync += handle
            }
            return value
        }

        override fun lock(directory: Long, name: String, nonBlocking: Boolean): Long {
            assertTrue(nonBlocking, "Windows admission must explicitly request a single nonblocking lease attempt")
            return model.lock(directory, name, nonBlocking).also {
                leases += Lease(directory, name, nonBlocking, it)
                opened += it
                assertTrue(activeLeases.add(it))
            }
        }

        override fun read(directory: Long, name: String, maximum: Int): ByteArray {
            if (!name.endsWith(".lock")) {
                dataReads += name
                events += "read:$name"
                if (requireStartupSync) {
                    assertTrue(syncReturned, "Header/key/ciphertext admission cannot precede actual sync return")
                    assertEquals(setOf(root, identity), verifiedAfterSync)
                }
            }
            return model.read(directory, name, maximum)
        }

        override fun write(directory: Long, name: String, bytes: ByteArray, replace: Boolean) {
            mutations += "write:$name"
            model.write(directory, name, bytes, replace)
        }

        override fun delete(directory: Long, name: String, expected: LongArray): Boolean {
            mutations += "delete:$name"
            return model.delete(directory, name, expected)
        }

        override fun deleteIfEmpty(directory: Long) {
            mutations += "delete-directory"
            model.deleteIfEmpty(directory)
        }

        override fun sync(directory: Long) {
            syncCalls += directory
            assertTrue(identity > 0 && root > 0 && identity != root)
            assertEquals(identity, directory, "Sync the original identity handle, not the root or a reopened directory")
            val profileLease = leases.first { it.name == "profile.lock" }
            val vaultLease = leases.first { it.name == "vault.lock" }
            assertEquals(root, profileLease.directory)
            assertEquals(identity, vaultLease.directory)
            assertEquals(setOf(profileLease.token, vaultLease.token), activeLeases)
            val store = model.store
            assertEquals(setOf(store.root.id to "profile.lock",
                store.root.entries.getValue("identity").id to "vault.lock"), store.locks)
            assertTrue(dataReads.isEmpty())
            assertTrue(mutations.isEmpty())
            events += "sync:enter"
            beforeSync()
            model.sync(directory)
            syncReturned = true
            events += "sync:return"
        }

        override fun close(handle: Long) {
            closeAttempts += handle
            events += "close:$handle"
            val inspection = leases.firstOrNull { it.name == "vault.lock" }
            if (handle == inspection?.token) vaultCloseFailure?.let { throw it }
            model.close(handle)
            activeLeases.remove(handle)
        }

        fun assertStartupSync() {
            assertEquals(listOf(identity), syncCalls)
            assertTrue(syncReturned)
            assertEquals(setOf(root, identity), verifiedAfterSync)
            assertEquals(1, leases.count { it.name == "profile.lock" })
            assertTrue(leases.all { it.nonBlocking })
            assertTrue(dataReads.isNotEmpty())
            assertTrue(events.indexOf("sync:return") < events.indexOfFirst { it.startsWith("read:") })
            assertTrue(mutations.isEmpty())
        }

        fun assertRetired() {
            assertEquals(0, model.remaining)
            assertTrue(model.store.locks.isEmpty())
            assertTrue(activeLeases.isEmpty())
            assertEquals(opened.toSet(), closeAttempts.toSet())
            assertEquals(closeAttempts.distinct(), closeAttempts)
            assertEquals(closeAttempts, model.closeCalls)
        }
    }

    @Test
    fun existingCanonicalInventorySyncsItsOriginalIdentityUnderBothLeasesBeforeDataAdmission() {
        val store = populated()
        val before = snapshot(store)
        val native = StartupNative(WindowsProfileModel(store))
        val pass = password()
        val profile = DesktopRpcProfile.open(WindowsProfileFiles.openForValidation(native), pass)
        try { assertContentEquals(byteArrayOf(17, 23), profile.vault.read("synthetic-identity")) }
        finally { profile.close() }
        native.assertStartupSync()
        native.assertRetired()
        assertTrue(pass.all { it == '\u0000' })
        assertEquals(before, snapshot(store))
    }

    @Test
    fun lostModeledProofWriteAcknowledgmentStillRequiresCurrentNamespaceSyncWithoutPendingNames() {
        val model = WindowsProfileModel()
        val failure = IOException("synthetic proof acknowledgment lost after visible model write")
        var attempts = 0
        val interrupted = object : WindowsProfileNativeApi by model {
            override fun write(directory: Long, name: String, bytes: ByteArray, replace: Boolean) {
                model.write(directory, name, bytes, replace)
                if (name.endsWith(".aesgcm")) { attempts++; throw failure }
            }
        }
        val originalPass = password()
        assertSame(failure, assertFails {
            DesktopRpcProfile.open(WindowsProfileFiles.openForValidation(interrupted), originalPass)
        })
        assertEquals(1, attempts)
        assertTrue(originalPass.all { it == '\u0000' })
        assertTrue(checkNotNull(model.writtenInput).all { it == 0.toByte() })
        assertRetired(model)
        val identity = model.store.root.entries.getValue("identity")
        assertEquals(setOf("vault.lock", recordName("desktop-profile-key-check-v1")), identity.entries.keys)
        val before = snapshot(model.store)
        val native = StartupNative(WindowsProfileModel(model.store))
        val pass = password()
        DesktopRpcProfile.open(WindowsProfileFiles.openForValidation(native), pass).close()
        native.assertStartupSync()
        native.assertRetired()
        assertTrue(pass.all { it == '\u0000' })
        assertEquals(before, snapshot(model.store))
        // This authenticates today's visible proof, not the success of the earlier unacknowledged write.
        assertTrue(failure.suppressed.isEmpty())
    }

    private suspend fun trustedStore(pin: PeerFingerprint): WindowsProfileModel.Store {
        val store = populated()
        val model = WindowsProfileModel(store)
        val profile = DesktopRpcProfile.open(WindowsProfileFiles.openForValidation(model), password())
        try { RpcTrustPurpose.entries.forEach { profile.trust.replace(RpcCapacityContract.appId, it, setOf(pin)) } }
        finally { profile.close() }
        assertRetired(model)
        return store
    }

    private suspend fun loseTrustAcknowledgment(
        store: WindowsProfileModel.Store,
        purpose: RpcTrustPurpose,
        delete: Boolean,
    ) {
        val model = WindowsProfileModel(store)
        val failure = IOException("synthetic trust acknowledgment lost after visible model effect")
        val target = recordName(trustNamespace(purpose))
        var armed = false
        var attempts = 0
        val native = object : WindowsProfileNativeApi by model {
            override fun write(directory: Long, name: String, bytes: ByteArray, replace: Boolean) {
                model.write(directory, name, bytes, replace)
                if (armed && !delete && name == target) { attempts++; throw failure }
            }
            override fun delete(directory: Long, name: String, expected: LongArray): Boolean {
                val removed = model.delete(directory, name, expected)
                if (armed && delete && name == target) { assertTrue(removed); attempts++; throw failure }
                return removed
            }
        }
        val pass = password()
        val profile = DesktopRpcProfile.open(WindowsProfileFiles.openForValidation(native), pass)
        armed = true
        try {
            assertSame(failure, assertFails {
                if (delete) profile.vault.delete(trustNamespace(purpose))
                else profile.trust.replace(RpcCapacityContract.appId, purpose, emptySet())
            })
            assertFails { profile.trust.load(RpcCapacityContract.appId, purpose) }
        } finally { profile.close() }
        assertEquals(1, attempts)
        assertTrue(pass.all { it == '\u0000' })
        if (!delete) assertTrue(checkNotNull(model.writtenInput).all { it == 0.toByte() })
        assertRetired(model)
        assertTrue(store.root.entries.getValue("identity").entries.keys.all {
            it == "vault.lock" || Regex("[0-9a-f]{64}\\.aesgcm").matches(it)
        })
        assertTrue(failure.suppressed.isEmpty())
    }

    private suspend fun assertTrustReopen(
        store: WindowsProfileModel.Store,
        expected: Map<RpcTrustPurpose, Set<PeerFingerprint>>,
    ) {
        val before = snapshot(store)
        val native = StartupNative(WindowsProfileModel(store))
        val pass = password()
        val profile = DesktopRpcProfile.open(WindowsProfileFiles.openForValidation(native), pass)
        try {
            assertContentEquals(byteArrayOf(17, 23), profile.vault.read("synthetic-identity"))
            expected.forEach { (purpose, pins) ->
                assertEquals(pins, profile.trust.load(RpcCapacityContract.appId, purpose))
            }
        } finally { profile.close() }
        native.assertStartupSync()
        native.assertRetired()
        assertTrue(pass.all { it == '\u0000' })
        assertEquals(before, snapshot(store))
    }

    @Test
    fun unacknowledgedCanonicalTrustReplacementSyncsBeforeReopeningEveryPurpose() = runTest {
        val pin = PeerFingerprint.parse("p2f1-" + "a".repeat(52))
        val store = trustedStore(pin)
        val expected = RpcTrustPurpose.entries.associateWith { setOf(pin) }.toMutableMap()
        for (purpose in RpcTrustPurpose.entries) {
            val before = snapshot(store)
            loseTrustAcknowledgment(store, purpose, delete = false)
            val after = snapshot(store)
            val path = "/identity/${recordName(trustNamespace(purpose))}"
            assertEquals(before.keys, after.keys)
            assertEquals(before - path, after - path)
            assertTrue(before.getValue(path).id != after.getValue(path).id)
            expected[purpose] = emptySet()
            assertTrustReopen(store, expected)
        }
    }

    @Test
    fun unacknowledgedCanonicalTrustDeletionSyncsBeforeReadingCurrentAbsenceForEveryPurpose() = runTest {
        val pin = PeerFingerprint.parse("p2f1-" + "a".repeat(52))
        val store = trustedStore(pin)
        val expected = RpcTrustPurpose.entries.associateWith { setOf(pin) }.toMutableMap()
        for (purpose in RpcTrustPurpose.entries) {
            val before = snapshot(store)
            loseTrustAcknowledgment(store, purpose, delete = true)
            assertEquals(before - "/identity/${recordName(trustNamespace(purpose))}", snapshot(store))
            expected[purpose] = emptySet()
            assertTrustReopen(store, expected)
        }
    }

    @Test
    fun startupCannotConsumeHeaderOrPublishAProfileWhileTheOriginalSyncIsBlocked() {
        val store = populated()
        val before = snapshot(store)
        val native = StartupNative(WindowsProfileModel(store))
        val entered = CountDownLatch(1)
        val release = CountDownLatch(1)
        native.beforeSync = { entered.countDown(); await(release) }
        val files = WindowsProfileFiles.openForValidation(native)
        val pass = password()
        val outcome = AtomicReference<Result<DesktopRpcProfile>?>(null)
        val worker = thread(name = "synthetic-startup-sync") {
            outcome.set(runCatching { DesktopRpcProfile.open(files, pass) })
        }
        try {
            await(entered)
            assertFalse(native.syncReturned)
            assertNull(outcome.get())
            assertTrue(native.dataReads.isEmpty())
            assertEquals(4, files.retainedHandleCount)
            assertEquals(2, native.activeLeases.size)
            assertEquals(before, snapshot(store))
        } finally {
            release.countDown()
            worker.join(5_000)
            assertFalse(worker.isAlive)
            outcome.get()?.getOrNull()?.close()
        }
        assertTrue(assertNotNull(outcome.get()).isSuccess)
        assertTrue(pass.all { it == '\u0000' })
        native.assertStartupSync()
        native.assertRetired()
        assertEquals(before, snapshot(store))
    }

    @Test
    fun syncFailureKeepsItsOriginalErrorClearsPasswordAndRetiresOwnersWithoutReadingOrMutatingRecords() {
        val store = populated()
        val before = snapshot(store)
        val native = StartupNative(WindowsProfileModel(store))
        val failure = IOException("synthetic current namespace sync failure")
        native.beforeSync = { throw failure }
        val files = WindowsProfileFiles.openForValidation(native)
        val pass = password()
        assertSame(failure, assertFails { DesktopRpcProfile.open(files, pass) })
        assertTrue(failure.suppressed.isEmpty())
        assertEquals(listOf(native.identity), native.syncCalls)
        assertFalse(native.syncReturned)
        assertTrue(native.dataReads.isEmpty())
        assertTrue(native.mutations.isEmpty())
        assertTrue(pass.all { it == '\u0000' })
        native.assertRetired()
        val closes = native.closeAttempts.toList()
        files.close()
        assertEquals(closes, native.closeAttempts)
        assertEquals(before, snapshot(store))
    }

    @Test
    fun syncAndLeaseCloseFailuresRetainPrimaryAndCleanupUncertaintyWithoutRetryingTheOriginalOwner() {
        val store = populated()
        val before = snapshot(store)
        val native = StartupNative(WindowsProfileModel(store))
        val failure = IOException("synthetic current namespace sync failure")
        val cleanup = IOException("synthetic original inspection lease close uncertainty")
        native.beforeSync = { throw failure }
        native.vaultCloseFailure = cleanup
        val files = WindowsProfileFiles.openForValidation(native)
        val pass = password()
        val attempt = DesktopRpcProfile.openAttempt(files, pass)
        assertSame(failure, attempt.result.exceptionOrNull())
        assertSame(cleanup, attempt.cleanupFailure)
        assertTrue(failure.suppressed.isNotEmpty() && failure.suppressed.all { it === cleanup })
        assertEquals(listOf(native.identity), native.syncCalls)
        assertFalse(native.syncReturned)
        assertTrue(native.dataReads.isEmpty())
        assertTrue(native.mutations.isEmpty())
        assertTrue(pass.all { it == '\u0000' })
        val inspection = native.leases.first { it.name == "vault.lock" }.token
        assertEquals(setOf(inspection), native.activeLeases)
        assertEquals(1, native.closeAttempts.count { it == inspection })
        assertEquals(native.closeAttempts.distinct(), native.closeAttempts)
        assertEquals(native.opened.toSet(), native.closeAttempts.toSet())
        assertEquals(1, native.model.remaining) // Inert uncertain owner remains explicitly unproven, not retired.
        assertEquals(1, files.retainedHandleCount)
        assertEquals(setOf(store.root.entries.getValue("identity").id to "vault.lock"), store.locks)
        val closes = native.closeAttempts.toList()
        assertSame(cleanup, assertFails { files.close() })
        assertEquals(closes, native.closeAttempts)
        assertEquals(before, snapshot(store))
    }

    @Test
    fun bothOriginalDirectoriesMustRevalidateAfterSyncBeforeHeaderOrCiphertextConsumption() {
        val store = populated()
        val before = snapshot(store)
        for (target in listOf("identity", "profile")) {
            val native = StartupNative(WindowsProfileModel(store))
            native.failVerificationAfterSync = target
            val pass = password()
            assertSame(native.verificationFailure, assertFails {
                DesktopRpcProfile.open(WindowsProfileFiles.openForValidation(native), pass)
            })
            assertEquals(listOf(native.identity), native.syncCalls)
            assertTrue(native.syncReturned)
            assertTrue(native.dataReads.isEmpty())
            assertTrue(native.mutations.isEmpty())
            assertTrue(pass.all { it == '\u0000' })
            native.assertRetired()
            assertEquals(before, snapshot(store))
        }
    }

    private fun assertInventoryRefusedBeforeSync(store: WindowsProfileModel.Store) {
        val before = snapshot(store)
        val native = StartupNative(WindowsProfileModel(store))
        val pass = password()
        assertFails { DesktopRpcProfile.open(WindowsProfileFiles.openForValidation(native), pass) }
        assertTrue(native.syncCalls.isEmpty())
        assertTrue(native.dataReads.isEmpty())
        assertTrue(native.mutations.isEmpty())
        assertTrue(pass.all { it == '\u0000' })
        native.assertRetired()
        assertEquals(before, snapshot(store))
    }

    @Test
    fun pendingUnknownNamesAndWrongMemberTypesRefuseBeforeAnyNamespaceSync() {
        val store = populated()
        val root = store.root
        val identity = root.entries.getValue("identity")
        for (directory in listOf(root, identity)) {
            for (name in listOf("pwp-pending-" + "0".repeat(32), "pwp-stage-" + "1".repeat(32), "unknown")) {
                directory.entries[name] = store.node(false, byteArrayOf(99))
                try { assertInventoryRefusedBeforeSync(store) }
                finally { directory.entries.remove(name) } // Only this inert fixture member; never runtime recovery.
            }
        }
        val typeChanges = listOf(root to "profile.header", root to "identity", identity to "vault.lock",
            identity to recordName("desktop-profile-key-check-v1"))
        for ((parent, name) in typeChanges) {
            val original = parent.entries.getValue(name)
            parent.entries[name] = store.node(!original.directory)
            try { assertInventoryRefusedBeforeSync(store) }
            finally { parent.entries[name] = original }
        }
        val lock = identity.entries.remove("vault.lock")!!
        try { assertInventoryRefusedBeforeSync(store) }
        finally { identity.entries["vault.lock"] = lock }
    }

    @Test
    fun currentNamespaceAcknowledgmentDoesNotBypassCiphertextAuthentication() {
        val store = populated()
        val proof = store.root.entries.getValue("identity").entries.getValue(recordName("desktop-profile-key-check-v1"))
        proof.bytes[proof.bytes.lastIndex] = (proof.bytes.last().toInt() xor 1).toByte()
        val before = snapshot(store)
        val native = StartupNative(WindowsProfileModel(store))
        val pass = password()
        assertFails { DesktopRpcProfile.open(WindowsProfileFiles.openForValidation(native), pass) }
        native.assertStartupSync()
        native.assertRetired()
        assertTrue(pass.all { it == '\u0000' })
        assertEquals(before, snapshot(store))
    }

    @Test
    fun freshProfileDoesNotInventAnExistingIdentitySyncBeforeCreation() {
        val native = StartupNative(WindowsProfileModel(), requireStartupSync = false)
        val pass = password()
        DesktopRpcProfile.open(WindowsProfileFiles.openForValidation(native), pass).close()
        assertTrue(native.syncCalls.isEmpty())
        assertEquals(setOf("profile.lock", "profile.header", "identity"), native.model.store.root.entries.keys)
        assertTrue(native.mutations.contains("create:identity"))
        assertTrue(pass.all { it == '\u0000' })
        native.assertRetired()
    }
}
