package dev.p2pkit.sample.rpc.profile

import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.rpc.RpcTrustPurpose
import dev.p2pkit.sample.rpc.RpcCapacityContract
import dev.p2pkit.sample.rpc.desktop.DesktopRpcProfile
import dev.p2pkit.sample.rpc.lab.LabFiles
import java.io.IOException
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFails
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertSame
import kotlin.test.assertTrue

/** Startup policy/model checks, not NTFS, native recovery, power-loss or installed-app evidence. */
class WindowsProfileRecoveryAdmissionTest {
    private val proofNamespace = "desktop-profile-key-check-v1"
    private fun password() = "synthetic-recovery-passphrase".toCharArray()
    private fun populated(): WindowsProfileModel.Store {
        val model = WindowsProfileModel()
        val profile = DesktopRpcProfile.open(WindowsProfileFiles.openForValidation(model), password())
        try { profile.vault.putIfAbsent("synthetic-identity", byteArrayOf(17, 23)) }
        finally { profile.close() }
        assertEquals(0, model.remaining)
        return model.store
    }

    private data class Saved(val id: Long, val directory: Boolean, val bytes: ByteArray)
    private fun snapshot(store: WindowsProfileModel.Store): Map<String, Saved> = buildMap {
        fun visit(path: String, node: WindowsProfileModel.Node) {
            put(path, Saved(node.id, node.directory, node.bytes.copyOf()))
            node.entries.forEach { (name, child) -> visit("$path/$name", child) }
        }
        visit("", store.root)
    }

    private fun unchanged(before: Map<String, Saved>, store: WindowsProfileModel.Store) {
        val after = snapshot(store)
        assertEquals(before.keys, after.keys)
        preserved(before, store)
    }

    private fun preserved(before: Map<String, Saved>, store: WindowsProfileModel.Store) {
        val after = snapshot(store)
        before.forEach { (name, saved) ->
            val actual = after.getValue(name)
            assertEquals(saved.id, actual.id)
            assertEquals(saved.directory, actual.directory)
            assertContentEquals(saved.bytes, actual.bytes)
        }
    }

    private fun refusesUnchanged(store: WindowsProfileModel.Store) {
        val before = snapshot(store)
        val model = WindowsProfileModel(store)
        val pass = password()
        assertFails { DesktopRpcProfile.open(WindowsProfileFiles.openForValidation(model), pass) }
        assertTrue(pass.all { it == '\u0000' })
        unchanged(before, store)
        assertEquals(0, model.remaining)
        assertTrue(store.locks.isEmpty())
        assertEquals(model.closeCalls.distinct(), model.closeCalls)
    }

    private fun refusesWithoutRecoveryWrites(store: WindowsProfileModel.Store, pass: CharArray): Throwable {
        val before = snapshot(store)
        val model = WindowsProfileModel(store)
        val mutations = mutableListOf<String>()
        val native = object : WindowsProfileNativeApi by model {
            override fun write(directory: Long, name: String, bytes: ByteArray, replace: Boolean) {
                mutations += "write:$name"
                model.write(directory, name, bytes, replace)
            }

            override fun child(directory: Long, name: String, create: Boolean): Long {
                if (create) mutations += "directory:$name"
                return model.child(directory, name, create)
            }

            override fun lock(directory: Long, name: String, nonBlocking: Boolean): Long {
                if (!model.exists(directory, name)) mutations += "lock:$name"
                return model.lock(directory, name, nonBlocking)
            }

            override fun delete(directory: Long, name: String, expected: LongArray): Boolean {
                mutations += "delete:$name"
                return model.delete(directory, name, expected)
            }

            override fun deleteIfEmpty(directory: Long) {
                mutations += "deleteDirectory"
                model.deleteIfEmpty(directory)
            }
        }
        val files = WindowsProfileFiles.openForValidation(native)
        val attempt = DesktopRpcProfile.openAttempt(files, pass)
        try {
            assertTrue(attempt.result.isFailure, "An established profile must not be reinitialized")
            assertNull(attempt.cleanupFailure)
        } finally {
            // A regressed successful admission must still retire its real model owners before the test fails.
            attempt.result.getOrNull()?.close()
        }
        assertTrue(mutations.isEmpty(), "Refusal must not attempt record or namespace repair: $mutations")
        assertTrue(pass.all { it == '\u0000' })
        unchanged(before, store)
        assertEquals(0, files.retainedHandleCount)
        assertEquals(0, model.remaining)
        assertTrue(store.locks.isEmpty())
        assertEquals(model.closeCalls.distinct(), model.closeCalls)
        val closed = model.closeCalls.toList()
        files.close()
        assertEquals(closed, model.closeCalls)
        return checkNotNull(attempt.result.exceptionOrNull())
    }

    private enum class Mutation { ProfileLease, HeaderWrite, IdentityCreate, VaultLease, RecordWrite, RecordDelete }
    private enum class Timing { Before, After }

    /**
     * Effects below exist only in the inert model. They do not simulate NTFS flush ordering or crashes.
     * A failed allocating native call owns its unpublished token: retire it here, not in the managed caller.
     * The created namespace entry deliberately survives that retirement; no rollback cleanup is modeled.
     */
    private class MutationFailure(
        val model: WindowsProfileModel,
        private val mutation: Mutation,
        private val timing: Timing,
        private val pendingName: String? = null,
    ) : WindowsProfileNativeApi by model {
        val failure = IOException("synthetic ${mutation.name} ${timing.name} effect failure")
        var enabled = true
        var attempts = 0
            private set
        val writeCopies = mutableListOf<ByteArray>()
        val unpublishedRetirements = mutableListOf<Long>()

        private fun matches(candidate: Mutation) = enabled && mutation == candidate
        private fun failAllocation(allocate: () -> Long): Long {
            attempts++
            if (timing == Timing.After) {
                val unpublished = allocate()
                model.close(unpublished)
                unpublishedRetirements += unpublished
            }
            throw failure
        }

        override fun lock(directory: Long, name: String, nonBlocking: Boolean): Long {
            val target = when (name) {
                "profile.lock" -> Mutation.ProfileLease
                "vault.lock" -> Mutation.VaultLease
                else -> error("Unexpected modeled lease")
            }
            return if (matches(target)) failAllocation { model.lock(directory, name, nonBlocking) }
                else model.lock(directory, name, nonBlocking)
        }

        override fun child(directory: Long, name: String, create: Boolean): Long =
            if (create && name == "identity" && matches(Mutation.IdentityCreate)) {
                failAllocation { model.child(directory, name, create) }
            } else model.child(directory, name, create)

        override fun write(directory: Long, name: String, bytes: ByteArray, replace: Boolean) {
            writeCopies += bytes
            val selected = (name == "profile.header" && matches(Mutation.HeaderWrite)) ||
                (name.endsWith(".aesgcm") && matches(Mutation.RecordWrite))
            if (!selected) return model.write(directory, name, bytes, replace)
            attempts++
            if (timing == Timing.After) model.write(directory, name, bytes, replace)
            pendingName?.let {
                // Explicit unresolved inventory, not a claim about which residues any native failure leaves.
                val identity = model.store.root.entries.getValue("identity")
                check(it !in identity.entries)
                identity.entries[it] = model.store.node(false, bytes.copyOf())
            }
            throw failure
        }

        override fun delete(directory: Long, name: String, expected: LongArray): Boolean {
            if (!name.endsWith(".aesgcm") || !matches(Mutation.RecordDelete)) {
                return model.delete(directory, name, expected)
            }
            attempts++
            if (timing == Timing.After) assertTrue(model.delete(directory, name, expected))
            throw failure
        }

        fun assertRetired(files: WindowsProfileFiles, pass: CharArray) {
            assertEquals(1, attempts)
            assertTrue(pass.all { it == '\u0000' })
            writeCopies.forEach { assertTrue(it.all { byte -> byte == 0.toByte() }) }
            assertEquals(0, files.retainedHandleCount)
            assertEquals(0, model.remaining)
            assertTrue(model.store.locks.isEmpty())
            assertEquals(model.closeCalls.distinct(), model.closeCalls)
            unpublishedRetirements.forEach { token -> assertEquals(1, model.closeCalls.count { it == token }) }
            val completed = model.closeCalls.toList()
            files.close()
            assertEquals(completed, model.closeCalls)
        }
    }

    private fun interruptedInitialization(mutation: Mutation, timing: Timing): WindowsProfileModel.Store {
        val native = MutationFailure(WindowsProfileModel(), mutation, timing)
        val files = WindowsProfileFiles.openForValidation(native)
        val pass = password()
        assertSame(native.failure, assertFails { DesktopRpcProfile.open(files, pass) })
        assertTrue(native.failure.suppressed.isEmpty())
        native.assertRetired(files, pass)
        val allocates = mutation in setOf(Mutation.ProfileLease, Mutation.IdentityCreate, Mutation.VaultLease)
        assertEquals(if (allocates && timing == Timing.After) 1 else 0, native.unpublishedRetirements.size)
        return native.model.store
    }

    private fun reopensUnchanged(store: WindowsProfileModel.Store, fresh: Boolean = false) {
        val before = snapshot(store)
        if (fresh) {
            assertFalse("profile.header" in store.root.entries)
            assertFalse("identity" in store.root.entries)
        }
        val model = WindowsProfileModel(store)
        val pass = password()
        DesktopRpcProfile.open(WindowsProfileFiles.openForValidation(model), pass).close()
        assertTrue(pass.all { it == '\u0000' })
        assertEquals(0, model.remaining)
        assertTrue(store.locks.isEmpty())
        assertEquals(model.closeCalls.distinct(), model.closeCalls)
        if (fresh) preserved(before, store) else unchanged(before, store)
        assertEquals(setOf("profile.lock", "profile.header", "identity"), store.root.entries.keys)
    }

    @Test
    fun modeledProfileLeaseFailureRetiresUnpublishedOwnerAndAllowsOnlyFreshInitialization() {
        for (timing in Timing.entries) {
            val store = interruptedInitialization(Mutation.ProfileLease, timing)
            assertEquals(if (timing == Timing.After) setOf("profile.lock") else emptySet(), store.root.entries.keys)
            reopensUnchanged(store, fresh = true)
        }
    }

    @Test
    fun modeledHeaderWriteFailureDistinguishesAbsentHeaderFromUnfinishedProfile() {
        for (timing in Timing.entries) {
            val store = interruptedInitialization(Mutation.HeaderWrite, timing)
            if (timing == Timing.Before) {
                assertEquals(setOf("profile.lock"), store.root.entries.keys)
                reopensUnchanged(store, fresh = true)
            } else {
                assertEquals(setOf("profile.lock", "profile.header"), store.root.entries.keys)
                refusesUnchanged(store)
            }
        }
    }

    @Test
    fun modeledIdentityCreateFailurePreservesPartialInitializationAndRefusesFreshAdmission() {
        for (timing in Timing.entries) {
            val store = interruptedInitialization(Mutation.IdentityCreate, timing)
            val expected = setOf("profile.lock", "profile.header") +
                if (timing == Timing.After) setOf("identity") else emptySet()
            assertEquals(expected, store.root.entries.keys)
            store.root.entries["identity"]?.let { assertTrue(it.entries.isEmpty()) }
            refusesUnchanged(store)
        }
    }

    @Test
    fun modeledVaultLeaseCreateFailurePreservesPartialInitializationAndRefusesFreshAdmission() {
        for (timing in Timing.entries) {
            val store = interruptedInitialization(Mutation.VaultLease, timing)
            assertEquals(setOf("profile.lock", "profile.header", "identity"), store.root.entries.keys)
            assertEquals(if (timing == Timing.After) setOf("vault.lock") else emptySet(),
                store.root.entries.getValue("identity").entries.keys)
            refusesUnchanged(store)
        }
    }

    @Test
    fun modeledProofWriteFailureRefusesMissingProofButAuthenticatesCompletedModelEffect() {
        for (timing in Timing.entries) {
            val store = interruptedInitialization(Mutation.RecordWrite, timing)
            val records = store.root.entries.getValue("identity").entries.keys
            if (timing == Timing.Before) {
                assertEquals(setOf("vault.lock"), records)
                refusesUnchanged(store)
            } else {
                assertEquals(2, records.size)
                assertEquals(1, records.count { it.endsWith(".aesgcm") })
                reopensUnchanged(store)
            }
        }
    }

    private suspend fun trustedStore(pin: PeerFingerprint): WindowsProfileModel.Store {
        val store = populated()
        val model = WindowsProfileModel(store)
        val profile = DesktopRpcProfile.open(WindowsProfileFiles.openForValidation(model), password())
        try {
            for (purpose in RpcTrustPurpose.entries) {
                profile.trust.replace(RpcCapacityContract.appId, purpose, setOf(pin))
            }
        } finally { profile.close() }
        assertEquals(0, model.remaining)
        assertTrue(store.locks.isEmpty())
        return store
    }

    private suspend fun failTrustMutation(
        store: WindowsProfileModel.Store,
        purpose: RpcTrustPurpose,
        timing: Timing,
        mutation: Mutation = Mutation.RecordWrite,
        pendingName: String? = null,
    ) {
        check(mutation == Mutation.RecordWrite || mutation == Mutation.RecordDelete)
        val native = MutationFailure(WindowsProfileModel(store), mutation, timing, pendingName)
            .also { it.enabled = false }
        val files = WindowsProfileFiles.openForValidation(native)
        val pass = password()
        val profile = DesktopRpcProfile.open(files, pass)
        native.enabled = true
        try {
            assertSame(native.failure, assertFails {
                if (mutation == Mutation.RecordWrite) {
                    profile.trust.replace(RpcCapacityContract.appId, purpose, emptySet())
                } else profile.vault.delete(trustNamespace(purpose))
            })
            // An uncertain mutation poisons this session; neither a retry nor an application-data read is admitted.
            assertFails { profile.trust.load(RpcCapacityContract.appId, purpose) }
            assertEquals(1, native.attempts)
            assertEquals(if (mutation == Mutation.RecordWrite) 1 else 0, native.writeCopies.size)
        } finally { profile.close() }
        assertTrue(native.failure.suppressed.isEmpty())
        native.assertRetired(files, pass)
    }

    private fun trustNamespace(purpose: RpcTrustPurpose) =
        "rpc-trust:${RpcCapacityContract.appId.value}:${purpose.name}"

    private fun trustPath(purpose: RpcTrustPurpose): String =
        "/identity/${LabFiles.sha256(trustNamespace(purpose).toByteArray(Charsets.UTF_8))}.aesgcm"

    private suspend fun reopensTrustUnchanged(
        store: WindowsProfileModel.Store,
        expected: Map<RpcTrustPurpose, Set<PeerFingerprint>>,
    ) {
        val written = snapshot(store)
        val model = WindowsProfileModel(store)
        val pass = password()
        val profile = DesktopRpcProfile.open(WindowsProfileFiles.openForValidation(model), pass)
        try {
            assertContentEquals(byteArrayOf(17, 23), profile.vault.read("synthetic-identity"))
            for ((purpose, pins) in expected) {
                assertEquals(pins, profile.trust.load(RpcCapacityContract.appId, purpose))
            }
        } finally { profile.close() }
        assertTrue(pass.all { it == '\u0000' })
        assertEquals(0, model.remaining)
        assertTrue(store.locks.isEmpty())
        assertEquals(model.closeCalls.distinct(), model.closeCalls)
        unchanged(written, store)
    }

    @Test
    fun modeledTrustReplacementFailureReopensOnlyAuthenticatedOldOrNewStateForEveryPurpose() = runTest {
        val pin = PeerFingerprint.parse("p2f1-" + "a".repeat(52))
        val store = trustedStore(pin)
        val expected = RpcTrustPurpose.entries.associateWith { setOf(pin) }.toMutableMap()
        for (purpose in RpcTrustPurpose.entries) {
            for (timing in Timing.entries) {
                val before = snapshot(store)
                failTrustMutation(store, purpose, timing)
                if (timing == Timing.Before) unchanged(before, store) else {
                    expected[purpose] = emptySet()
                    val after = snapshot(store)
                    val path = trustPath(purpose)
                    assertEquals(before.keys, after.keys)
                    preserved(before - path, store)
                    assertTrue(before.getValue(path).id != after.getValue(path).id)
                }
                reopensTrustUnchanged(store, expected)
            }
        }
    }

    @Test
    fun modeledTrustRecordDeletionFailureNeverReportsSuccessOrDeletesOtherNamespaces() = runTest {
        val pin = PeerFingerprint.parse("p2f1-" + "a".repeat(52))
        val store = trustedStore(pin)
        val expected = RpcTrustPurpose.entries.associateWith { setOf(pin) }.toMutableMap()
        for (purpose in RpcTrustPurpose.entries) {
            for (timing in Timing.entries) {
                val before = snapshot(store)
                failTrustMutation(store, purpose, timing, mutation = Mutation.RecordDelete)
                if (timing == Timing.Before) unchanged(before, store) else {
                    expected[purpose] = emptySet()
                    // Only the explicitly modeled record was removed. No successful return or sync is implied.
                    unchanged(before - trustPath(purpose), store)
                }
                reopensTrustUnchanged(store, expected)
            }
        }
    }

    @Test
    fun modeledPendingTrustWriteRefusesFreshAdmissionEvenWithAnAuthenticatedOldOrNewRecord() = runTest {
        val pin = PeerFingerprint.parse("p2f1-" + "a".repeat(52))
        for (timing in Timing.entries) {
            val store = trustedStore(pin)
            val before = snapshot(store)
            val pending = "pwp-pending-" + "2".repeat(32)
            failTrustMutation(store, RpcTrustPurpose.HostClients, timing, pendingName = pending)
            val after = snapshot(store)
            val target = trustPath(RpcTrustPurpose.HostClients)
            val pendingPath = "/identity/$pending"
            assertEquals(before.keys + pendingPath, after.keys)
            preserved(if (timing == Timing.Before) before else before - target, store)
            assertTrue(after.getValue(pendingPath).bytes.isNotEmpty())
            if (timing == Timing.After) {
                assertTrue(before.getValue(target).id != after.getValue(target).id)
                assertContentEquals(after.getValue(target).bytes, after.getValue(pendingPath).bytes)
            }
            refusesUnchanged(store)
        }
    }

    @Test
    fun establishedProfileMissingProofNeverReinitializesItsRetainedIdentityOrTrust() = runTest {
        val pin = PeerFingerprint.parse("p2f1-" + "a".repeat(52))
        val store = trustedStore(pin)
        val before = snapshot(store)
        val proofName = LabFiles.sha256(proofNamespace.toByteArray(Charsets.UTF_8)) + ".aesgcm"
        val identity = store.root.entries.getValue("identity")
        // Model lost metadata after actual successful profile use, not an interrupted first initialization.
        val removed = checkNotNull(identity.entries.remove(proofName))
        assertTrue(removed.bytes.isNotEmpty())
        for (pass in listOf(password(), "synthetic-wrong-passphrase".toCharArray())) {
            refusesWithoutRecoveryWrites(store, pass)
            assertFalse(proofName in identity.entries)
            unchanged(before - "/identity/$proofName", store)
        }
    }

    @Test
    fun authenticatedButIncorrectProofNeverBecomesInitializationAuthority() = runTest {
        val pin = PeerFingerprint.parse("p2f1-" + "a".repeat(52))
        val store = trustedStore(pin)
        val before = snapshot(store)
        val model = WindowsProfileModel(store)
        val profile = DesktopRpcProfile.open(WindowsProfileFiles.openForValidation(model), password())
        val incorrectProof = "synthetic authenticated but incorrect proof".toByteArray(Charsets.US_ASCII)
        try {
            // Use the actual AES-GCM writer and reader: valid authentication is not the expected proof value.
            profile.vault.replace(proofNamespace, incorrectProof)
            assertContentEquals(incorrectProof, profile.vault.read(proofNamespace))
        } finally { profile.close() }
        assertEquals(0, model.remaining)
        assertTrue(store.locks.isEmpty())
        val proofPath = "/identity/${LabFiles.sha256(proofNamespace.toByteArray(Charsets.UTF_8))}.aesgcm"
        preserved(before - proofPath, store)
        val failure = refusesWithoutRecoveryWrites(store, password())
        assertEquals("Profile key check failed", failure.message)
        refusesWithoutRecoveryWrites(store, "synthetic-wrong-passphrase".toCharArray())
    }

    @Test
    fun cleanExistingInventoryPreservesIdentityAndDoesNotRewriteRecords() {
        val store = populated()
        val before = snapshot(store)
        val model = WindowsProfileModel(store)
        val pass = password()
        val profile = DesktopRpcProfile.open(WindowsProfileFiles.openForValidation(model), pass)
        try { assertContentEquals(byteArrayOf(17, 23), profile.vault.read("synthetic-identity")) }
        finally { profile.close() }
        assertTrue(pass.all { it == '\u0000' })
        unchanged(before, store)
        assertEquals(0, model.remaining)
        assertTrue(store.locks.isEmpty())
    }

    @Test
    fun inspectionDoesNotReopenTheShareNoneVaultLeaseForData() {
        val store = populated()
        val before = snapshot(store)
        val model = WindowsProfileModel(store)
        var vaultLease = 0L
        var emptyReads = 0
        val native = object : WindowsProfileNativeApi by model {
            override fun lock(directory: Long, name: String, nonBlocking: Boolean): Long =
                model.lock(directory, name, nonBlocking).also { if (name == "vault.lock") vaultLease = it }

            override fun read(directory: Long, name: String, maximum: Int): ByteArray {
                if (name == "vault.lock") {
                    check(vaultLease == 0L) { "Synthetic native share-none lock cannot be reopened" }
                    emptyReads++
                    assertEquals(0, maximum)
                }
                return model.read(directory, name, maximum)
            }

            override fun close(handle: Long) {
                model.close(handle)
                if (handle == vaultLease) vaultLease = 0
            }
        }
        val profile = DesktopRpcProfile.open(WindowsProfileFiles.openForValidation(native), password())
        try { assertContentEquals(byteArrayOf(17, 23), profile.vault.read("synthetic-identity")) }
        finally { profile.close() }
        assertEquals(1, emptyReads)
        assertEquals(0L, vaultLease)
        assertEquals(0, model.remaining)
        assertTrue(store.locks.isEmpty())
        unchanged(before, store)
    }

    @Test
    fun sharedModelRefusesLockDataReopenButStillObservesOriginalMetadata() {
        for (name in listOf("profile.lock", "vault.lock")) {
            val model = WindowsProfileModel()
            val root = model.openRoot()
            val lease = model.lock(root, name, nonBlocking = true)
            try {
                val expected = model.fileIdentity(root, name)
                assertFails { model.read(root, name, 0) }
                assertContentEquals(expected, model.fileIdentity(root, name))
            } finally { model.close(lease) }
            try { assertContentEquals(byteArrayOf(), model.read(root, name, 0)) }
            finally { model.close(root) }
            assertEquals(0, model.remaining)
            assertTrue(model.store.locks.isEmpty())
        }
    }

    @Test
    fun oldValidRecordsDoNotSettlePendingStagedOrUnknownRootInventory() {
        val store = populated()
        for (name in listOf("pwp-pending-" + "0".repeat(32), "pwp-stage-" + "0".repeat(32), "unknown")) {
            store.root.entries[name] = store.node(false, byteArrayOf(99))
            try { refusesUnchanged(store) }
            finally { store.root.entries.remove(name) } // Exact inert fixture member, never production recovery.
        }
    }

    @Test
    fun identityInventoryRejectsPendingStageMalformedAndUnknownNamesWithoutAdoption() {
        val store = populated()
        val identity = store.root.entries.getValue("identity")
        for (name in listOf("pwp-pending-" + "0".repeat(32), "pwp-pending-invalid",
                "pwp-stage-" + "1".repeat(32), "unknown", "A".repeat(64) + ".aesgcm", "short.aesgcm")) {
            identity.entries[name] = store.node(false, byteArrayOf(99))
            try { refusesUnchanged(store) }
            finally { identity.entries.remove(name) }
        }
    }

    @Test
    fun allowedNamesCannotConcealWrongObjectKinds() {
        val store = populated()
        val root = store.root
        val identity = root.entries.getValue("identity")
        val changes = listOf(root to "profile.header", root to "identity", identity to "vault.lock",
            identity to identity.entries.keys.first { it.endsWith(".aesgcm") })
        for ((parent, name) in changes) {
            val original = parent.entries.getValue(name)
            parent.entries[name] = store.node(!original.directory)
            try { refusesUnchanged(store) }
            finally { parent.entries[name] = original }
        }
    }

    @Test
    fun missingIdentityLockAndMissingHeaderAreNotRecreated() {
        val store = populated()
        val identity = store.root.entries.getValue("identity")
        val lock = identity.entries.remove("vault.lock")!!
        refusesUnchanged(store)
        assertFalse("vault.lock" in identity.entries)
        identity.entries["vault.lock"] = lock
        store.root.entries.remove("profile.header")
        refusesUnchanged(store)
        assertFalse("profile.header" in store.root.entries)
    }

    @Test
    fun inventoryFailureRetiresOwnersWithoutReadingApplicationCiphertext() {
        val store = populated()
        val before = snapshot(store)
        val model = WindowsProfileModel(store)
        val failure = IOException("synthetic inventory failure")
        var calls = 0
        var recordReads = 0
        val native = object : WindowsProfileNativeApi by model {
            override fun names(directory: Long): Array<String> {
                calls++
                if (calls == 2) throw failure
                return model.names(directory)
            }
            override fun read(directory: Long, name: String, maximum: Int): ByteArray {
                if (!name.endsWith(".lock")) recordReads++
                return model.read(directory, name, maximum)
            }
        }
        val pass = password()
        assertSame(failure, assertFails {
            DesktopRpcProfile.open(WindowsProfileFiles.openForValidation(native), pass)
        })
        assertEquals(2, calls)
        assertEquals(0, recordReads)
        assertTrue(pass.all { it == '\u0000' })
        assertEquals(0, model.remaining)
        assertTrue(store.locks.isEmpty())
        assertEquals(model.closeCalls.distinct(), model.closeCalls)
        unchanged(before, store)
    }

    @Test
    fun uncertainInspectionLeaseCloseIsNotRetriedOrReportedAsAdmitted() {
        val store = populated()
        val before = snapshot(store)
        val model = WindowsProfileModel(store)
        val failure = IOException("synthetic inspection close uncertainty")
        var vaultLease = 0L
        val attempts = mutableListOf<Long>()
        val native = object : WindowsProfileNativeApi by model {
            override fun lock(directory: Long, name: String, nonBlocking: Boolean): Long =
                model.lock(directory, name, nonBlocking).also { if (name == "vault.lock") vaultLease = it }

            override fun close(handle: Long) {
                attempts += handle
                if (handle == vaultLease) throw failure
                model.close(handle)
            }
        }
        val files = WindowsProfileFiles.openForValidation(native)
        val pass = password()
        assertSame(failure, assertFails { DesktopRpcProfile.open(files, pass) })
        assertTrue(pass.all { it == '\u0000' })
        assertTrue(vaultLease > 0)
        assertEquals(1, attempts.count { it == vaultLease })
        assertEquals(attempts.distinct(), attempts)
        val completedAttempts = attempts.toList()
        assertSame(failure, assertFails { files.close() })
        assertEquals(completedAttempts, attempts)
        assertEquals(1, model.remaining) // Synthetic uncertain owner retained, not successful native cleanup.
        assertEquals(1, files.retainedHandleCount)
        unchanged(before, store)
    }
}
