package dev.p2pkit.sample.rpc.profile

import dev.p2pkit.sample.rpc.desktop.DesktopRpcProfile
import java.io.IOException
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFails
import kotlin.test.assertFalse
import kotlin.test.assertSame
import kotlin.test.assertTrue

/** Startup policy/model checks, not NTFS, native recovery, power-loss or installed-app evidence. */
class WindowsProfileRecoveryAdmissionTest {
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
