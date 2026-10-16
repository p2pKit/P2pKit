package dev.p2pkit.sample.rpc.profile

import dev.p2pkit.sample.rpc.desktop.DesktopRpcProfile
import java.lang.reflect.Modifier
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertNull
import kotlin.test.assertTrue

/**
 * Fixed factory refusals and the actual private managed composition over inert custody calls only.
 * Test-only reflection never registers a production owner or calls the installed factory successfully.
 * This is not DLL, NTFS, protected-profile, installed-runtime or durability qualification.
 */
class WindowsProfileInstalledProviderTest {
    @Test fun absentBootModuleRefusesTheActualZeroArgumentProductionFactory() {
        assertFalse(ModuleLayer.boot().findModule("dev.p2pkit.rpc.windows.loader").isPresent)
        repeat(2) {
            val failure = assertFailsWith<WindowsProfileInstalledProvider.Unavailable> {
                WindowsProfileFiles.openInstalled()
            }
            assertNull(failure.cause) // Exact absence, before reflection, JNI initialization or acquisition.
        }
        assertFalse(WindowsProfileAvailability.IMPLEMENTED)
        assertFalse(WindowsProfileAvailability.QUALIFIED)
    }

    @Test fun productionEntryAcceptsNoBackendOrPermissionArguments() {
        val factory = WindowsProfileFiles.Companion::class.java.getDeclaredMethod("openInstalled")
        assertEquals(0, factory.parameterCount)
        assertEquals(WindowsProfileFiles::class.java, factory.returnType)
        assertEquals(0, WindowsProfileInstalledProvider::class.java.getDeclaredMethod("acquireNative").parameterCount)
        val composed = adapterClass()
        assertTrue(Modifier.isPrivate(composed.modifiers))
        assertTrue(Modifier.isFinal(composed.modifiers))
    }

    @Test fun composedContractIsDistinctFromTheUnchangedRawContractAndAcquiresNothing() {
        val calls = Calls()
        val native = composed(calls)
        assertEquals(1, native.abi())
        assertEquals(0x7fL, native.capabilities())
        assertEquals(13, calls.abi())
        assertEquals(0x43L, calls.capabilities())
        assertEquals(0, calls.model.opens)
        assertEquals(0, calls.model.remaining)
        assertTrue(calls.model.closeCalls.isEmpty())
    }

    @Test fun wrongRawContractCannotBecomeACompleteProviderBeforeRootOpen() {
        for ((abi, capabilities) in listOf(12 to 0x43L, 1 to 0x7fL, 13 to 0x7fL, 13 to 0x03L)) {
            val calls = Calls().also { it.rawAbi = abi; it.rawCapabilities = capabilities }
            assertFailsWith<IllegalStateException> { WindowsProfileFiles.openForValidation(composed(calls)) }
            assertEquals(0, calls.model.opens)
            assertEquals(0, calls.model.remaining)
            assertTrue(calls.model.closeCalls.isEmpty())
        }
    }

    @Test fun rawPinDriftSealsStorageButRetiresTheOriginalAdmittedOwner() {
        val calls = Calls()
        val files = WindowsProfileFiles.openForValidation(composed(calls))
        val directory = files.root
        calls.rawAbi = 12
        assertFailsWith<IllegalStateException> { directory.names() }
        calls.rawAbi = 13
        assertFailsWith<IllegalStateException> { directory.names() }
        files.close()
        assertEquals(0, calls.model.remaining)
        assertEquals(1, calls.model.closeCalls.size)
        files.close()
        assertEquals(1, calls.model.closeCalls.size)
    }

    @Test fun composedProviderPreservesEncryptedProfileAcrossRetirementAndReopen() {
        val calls = Calls()
        val password = "synthetic-composed-profile".toCharArray()
        val profile = DesktopRpcProfile.open(WindowsProfileFiles.openForValidation(composed(calls)), password)
        assertTrue(password.all { it == '\u0000' })
        val original = byteArrayOf(1, 2, 3)
        val replacement = byteArrayOf(5, 6, 7)
        val stored = profile.vault.putIfAbsent("synthetic-composed-record", original)
        try { assertContentEquals(original, stored) } finally { stored.fill(0) }
        profile.vault.replace("synthetic-composed-record", replacement)
        profile.close()
        assertEquals(0, calls.model.remaining)
        assertTrue(calls.model.store.locks.isEmpty())
        assertTrue(calls.pending.all { it.matches(Regex("pwp-pending-[0-9a-f]{32}")) })
        assertTrue(calls.model.store.root.entries.keys.containsAll(
            listOf("profile.header", "identity", "profile.lock"),
        ))

        val reopenedCalls = Calls(WindowsProfileModel(calls.model.store))
        val reopened = DesktopRpcProfile.open(WindowsProfileFiles.openForValidation(composed(reopenedCalls)),
            "synthetic-composed-profile".toCharArray())
        val read = reopened.vault.read("synthetic-composed-record")
        try { assertContentEquals(replacement, read) } finally { read?.fill(0) }
        assertTrue(reopened.vault.delete("synthetic-composed-record"))
        assertNull(reopened.vault.read("synthetic-composed-record"))
        reopened.close()
        assertEquals(0, reopenedCalls.model.remaining)
        assertTrue(reopenedCalls.model.store.locks.isEmpty())
    }

    @Test fun fixtureDirectoryDeletionIsNotMadeIntoAProductionCleanupOperation() {
        val calls = Calls()
        val files = WindowsProfileFiles.openForValidation(composed(calls))
        assertFailsWith<UnsupportedOperationException> { files.root.deleteIfEmpty() }
        files.close()
        assertEquals(0, calls.model.remaining)
    }

    private fun adapterClass(): Class<*> = WindowsProfileInstalledProvider::class.java.declaredClasses.single {
        it.simpleName == "CompleteAdapter"
    }

    private fun composed(calls: Calls): WindowsProfileNativeApi {
        val constructor = adapterClass().getDeclaredConstructor(WindowsProfileCustodyBridge::class.java)
        assertTrue(Modifier.isPrivate(constructor.modifiers))
        assertTrue(constructor.trySetAccessible())
        return assertIs<WindowsProfileNativeApi>(constructor.newInstance(WindowsProfileCustodyBridge(calls)))
    }

    /** The existing in-memory filesystem model, presented under the raw custody method names. */
    private class Calls(val model: WindowsProfileModel = WindowsProfileModel()) : WindowsProfileCustodyCalls {
        var rawAbi = 13
        var rawCapabilities = 0x43L
        val pending = mutableListOf<String>()
        override fun abi(): Int = rawAbi
        override fun capabilities(): Long = rawCapabilities
        override fun openRoot(): Long = model.openRoot()
        override fun child(directory: Long, name: String): Long = model.child(directory, name, false)
        override fun createChildDirectory(directory: Long, name: String): Long = model.child(directory, name, true)
        override fun identity(handle: Long): LongArray = model.directoryIdentity(handle)
        override fun fileIdentity(directory: Long, name: String): LongArray = model.fileIdentity(directory, name)
        override fun exists(directory: Long, name: String): Boolean = model.exists(directory, name)
        override fun names(directory: Long): Array<String> = model.names(directory)
        override fun read(directory: Long, name: String, maximum: Int): ByteArray = model.read(directory, name, maximum)
        override fun lockExisting(directory: Long, name: String): Long = model.lock(directory, name, true)
        override fun createProfileLock(root: Long): Long = model.lock(root, "profile.lock", true)
        override fun createVaultLock(identityDirectory: Long): Long = model.lock(identityDirectory, "vault.lock", true)
        override fun writeRecord(
            directory: Long, pendingName: String, target: String, ciphertext: ByteArray, replace: Boolean,
        ) {
            pending += pendingName
            model.write(directory, target, ciphertext, replace)
        }
        override fun deleteRecord(directory: Long, name: String, expected: LongArray) {
            check(model.delete(directory, name, expected))
        }
        override fun syncDirectory(directory: Long) = model.sync(directory)
        override fun close(handle: Long) = model.close(handle)
    }
}
