package dev.p2pkit.sample.rpc.profile

import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.rpc.RpcTrustPurpose
import dev.p2pkit.sample.rpc.RpcCapacityContract
import dev.p2pkit.sample.rpc.desktop.DesktopRpcProfile
import dev.p2pkit.sample.rpc.lab.LabVault
import java.io.IOException
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.concurrent.thread
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFails
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertSame
import kotlin.test.assertTrue
import kotlinx.coroutines.test.runTest

/** Managed contract/model tests only; no DLL is loaded and no native Windows protection is asserted. */
class WindowsProfileFilesTest {
    private fun password() = "synthetic-profile-passphrase".toCharArray()
    private fun await(latch: CountDownLatch) = assertTrue(latch.await(5, TimeUnit.SECONDS))
    private fun join(worker: Thread) { worker.join(5_000); assertFalse(worker.isAlive) }
    private fun awaitRetiring(files: WindowsProfileFiles) {
        val end = System.nanoTime() + TimeUnit.SECONDS.toNanos(5)
        while (!files.retirementStarted && System.nanoTime() < end) Thread.yield()
        assertTrue(files.retirementStarted)
    }

    @Test fun productionWindowsGateRemainsClosedIndependentOfModels() {
        assertFalse(WindowsProfileAvailability.IMPLEMENTED)
        assertFalse(WindowsProfileAvailability.QUALIFIED)
        assertFails { WindowsProfileAvailability.requirePosixProductionHost("Windows 11") }
        assertFails { WindowsProfileAvailability.requirePosixProductionHost("windows Server") }
        WindowsProfileAvailability.requirePosixProductionHost("Mac OS X")
    }

    @Test fun wrongAbiAndIncompleteCapabilitiesNeverOpenNativeStorage() {
        for (wrongAbi in listOf(true, false)) {
            val native = WindowsProfileModel()
            if (wrongAbi) native.declaredAbi = 2 else native.declaredCapabilities = 0x7e
            assertFails { WindowsProfileFiles.openForValidation(native) }
            assertEquals(0, native.opens)
            assertTrue(native.closeCalls.isEmpty())
        }
    }

    @Test fun metadataDecoderRequiresExactFlagsKindVersionLinksAndBoundedShape() {
        val valid = WindowsProfileIdentity(7, 0, 1, true).encoded()
        for (index in listOf(0, 4, 5)) {
            val modified = valid.copyOf().also { it[index] = 0 }
            assertFails { WindowsProfileIdentity.decode(modified, true) }
        }
        assertFails { WindowsProfileIdentity.decode(valid + 0, true) }
        assertFails { WindowsProfileIdentity.decode(valid, false) }
        assertFails { WindowsProfileIdentity.decode(valid.copyOf().also { it[3] = 0 }, true) }
        assertEquals(WindowsProfileIdentity(7, 0, 1, true), WindowsProfileIdentity.decode(valid, true))
    }

    @Test fun rejectedRootStillClosesItsAlreadyAllocatedHandle() {
        val native = WindowsProfileModel().also { it.invalidMetadata = true }
        assertFails { WindowsProfileFiles.openForValidation(native) }
        assertEquals(listOf(1L), native.closeCalls)
        assertEquals(0, native.remaining)
    }

    @Test fun componentParserRejectsTraversalAdsAliasesReservedNamesAndExcessLength() {
        for (name in listOf("", ".", "..", "../a", "a/b", "a\\b", "C:drive", "name:stream", "CON",
                "nul.txt", "COM1", "lpt9", "name.", "name ", "a".repeat(97), "\u0000")) {
            assertFails("must reject component") { profileComponent(name) }
        }
        for (name in listOf("identity", "profile.lock", "a".repeat(64) + ".aesgcm")) {
            assertEquals(name, profileComponent(name))
        }
    }

    @Test fun writeCopiesAreClearedOnSuccessAndFailureWithoutChangingCallerBytes() {
        for (fail in listOf(false, true)) {
            val native = WindowsProfileModel()
            val files = WindowsProfileFiles.openForValidation(native)
            val input = byteArrayOf(1, 2, 3)
            if (fail) native.writeFailure = IOException("synthetic write failure")
            try {
                if (fail) assertFails { files.root.write("profile.header", input) }
                else files.root.write("profile.header", input)
                assertContentEquals(byteArrayOf(1, 2, 3), input)
                assertTrue(assertNotNull(native.writtenInput).all { it == 0.toByte() })
            } finally { files.close() }
            assertEquals(0, native.remaining)
        }
    }

    @Test fun oversizedNativeReadIsClearedAndPoisonsFurtherWorkButStillAllowsCleanup() {
        val native = WindowsProfileModel().also { it.readOversize = true }
        val files = WindowsProfileFiles.openForValidation(native)
        assertFails { files.root.read("profile.header", 3) }
        assertTrue(assertNotNull(native.oversizedOutput).all { it == 0.toByte() })
        assertFails { files.root.exists("profile.header") }
        files.close()
        assertEquals(0, native.remaining)
    }

    @Test fun actualProfileAndVaultPreserveCryptoTrustAndWrongPasswordWithoutReset() = runTest {
        val store = WindowsProfileModel.Store()
        val firstNative = WindowsProfileModel(store)
        val pass = password()
        val first = DesktopRpcProfile.open(WindowsProfileFiles.openForValidation(firstNative), pass)
        assertTrue(pass.all { it == '\u0000' })
        val secret = ByteArray(64) { 42 }
        val pin = PeerFingerprint.parse("p2f1-" + "a".repeat(52))
        first.vault.putIfAbsent("identity", secret)
        for (purpose in RpcTrustPurpose.entries) first.trust.replace(RpcCapacityContract.appId, purpose, setOf(pin))
        val competing = WindowsProfileModel(store)
        assertFails { DesktopRpcProfile.open(WindowsProfileFiles.openForValidation(competing), password()) }
        assertEquals(0, competing.remaining)
        first.close()
        first.close()
        assertEquals(0, firstNative.remaining)
        val before = store.root.entries.getValue("identity").entries.mapValues { it.value.bytes.copyOf() }
        assertTrue(before.values.none { it.toString(Charsets.UTF_8).contains(pin.value) })
        val wrongNative = WindowsProfileModel(store)
        assertFails { DesktopRpcProfile.open(WindowsProfileFiles.openForValidation(wrongNative),
            "wrong-synthetic-passphrase".toCharArray()) }
        assertEquals(0, wrongNative.remaining)
        before.forEach { (name, bytes) ->
            assertContentEquals(bytes, store.root.entries.getValue("identity").entries.getValue(name).bytes)
        }
        val reopenedNative = WindowsProfileModel(store)
        val reopened = DesktopRpcProfile.open(WindowsProfileFiles.openForValidation(reopenedNative), password())
        assertContentEquals(secret, reopened.vault.read("identity"))
        for (purpose in RpcTrustPurpose.entries) {
            assertEquals(setOf(pin), reopened.trust.load(RpcCapacityContract.appId, purpose))
            reopened.trust.replace(RpcCapacityContract.appId, purpose, emptySet())
        }
        reopened.close()
        assertEquals(0, reopenedNative.remaining)
    }

    @Test fun profileOpenFailureClosesSessionWithoutRepairingMissingMetadata() {
        val native = WindowsProfileModel()
        native.store.root.entries["foreign"] = native.store.node(false, byteArrayOf(42))
        val pass = password()
        assertFails { DesktopRpcProfile.open(WindowsProfileFiles.openForValidation(native), pass) }
        assertTrue(pass.all { it == '\u0000' })
        assertContentEquals(byteArrayOf(42), native.store.root.entries.getValue("foreign").bytes)
        assertFalse("profile.header" in native.store.root.entries)
        assertEquals(0, native.remaining)
    }

    @Test fun actualVaultDestructionRetainsRecordedIdentityAcrossLateFileReplacement() {
        val native = WindowsProfileModel()
        val files = WindowsProfileFiles.openForValidation(native)
        val root = files.root
        val foreign = native.store.node(false, byteArrayOf(99))
        var replacedName: String? = null
        val custody = object : ProtectedProfileDirectory by root {
            override fun delete(name: String, expectedIdentity: Any?): Boolean {
                if (name.endsWith(".aesgcm")) {
                    assertNotNull(expectedIdentity)
                    native.store.root.entries[name] = foreign // After destroy's complete ownership preflight.
                    replacedName = name
                }
                return root.delete(name, expectedIdentity)
            }
        }
        val key = LabVault.randomKey()
        val vault = try { LabVault(custody, key) } finally { key.fill(0) }
        try {
            vault.putIfAbsent("synthetic", byteArrayOf(42))
            assertFails { vault.destroy() }
            assertSame(foreign, native.store.root.entries[assertNotNull(replacedName)])
            assertContentEquals(byteArrayOf(99), foreign.bytes)
            assertFails { vault.read("synthetic") }
        } finally { vault.close(); files.close() }
        assertEquals(0, native.remaining)
    }

    @Test fun suppliedDeleteCustodyRejectsForeignTypesDirectoriesAndOtherVolumesBeforeNativeDeletion() {
        for (expected in listOf("not-a-file-id", WindowsProfileIdentity(7, 0, 1, true),
                WindowsProfileIdentity(8, 0, 2, false))) {
            val model = WindowsProfileModel()
            val original = model.store.node(false, byteArrayOf(42))
            model.store.root.entries["profile.header"] = original
            var deletes = 0
            val native = object : WindowsProfileNativeApi by model {
                override fun delete(directory: Long, name: String, expected: LongArray): Boolean {
                    deletes++
                    return model.delete(directory, name, expected)
                }
            }
            val files = WindowsProfileFiles.openForValidation(native)
            try {
                assertFails { files.root.delete("profile.header", expected) }
                assertEquals(0, deletes)
                assertSame(original, model.store.root.entries["profile.header"])
            } finally { files.close() }
            assertEquals(0, model.remaining)
        }
    }

    @Test fun profileCloseRetiresDirectoryHandlesOnlyAfterVaultUsersAreClosed() {
        val native = WindowsProfileModel()
        val profile = DesktopRpcProfile.open(WindowsProfileFiles.openForValidation(native), password())
        native.beforeClose = { assertFails { profile.vault.read("identity") } }
        profile.close()
        assertEquals(0, native.remaining)
        assertEquals(native.closeCalls.distinct(), native.closeCalls)
    }

    @Test fun failedNativeCloseIsRetainedNeverRetriedAndNeverReportedClosed() {
        val native = WindowsProfileModel()
        val files = WindowsProfileFiles.openForValidation(native)
        files.root.child("identity", create = true)
        val failure = IOException("synthetic unknown close")
        native.closeFailure = failure
        assertSame(failure, assertFailsWith<IOException> { files.close() })
        assertEquals(2, files.retainedHandleCount)
        val calls = native.closeCalls.toList()
        assertSame(failure, assertFailsWith<IOException> { files.close() })
        assertEquals(calls, native.closeCalls)
        assertFails { files.root }
    }

    @Test fun uncertainLeaseClosePoisonsOrdinaryAdmissionButRetainsIndependentCleanup() {
        val native = FailingLeaseNative()
        val files = WindowsProfileFiles.openForValidation(native)
        val root = files.root
        root.write("profile.header", byteArrayOf(42))
        val lease = root.lock("profile.lock")
        try {
            assertSame(native.failure, assertFailsWith<IOException> { lease.close() })
            assertSame(native.failure, assertFailsWith<IOException> { lease.close() })
            root.verifyIdentity() // Explicit custody readback remains available to cleanup.
            val calls = native.ordinaryCalls
            val attempts: List<() -> Any?> = listOf(
                { root.read("profile.header") }, { root.write("other", byteArrayOf(99)) },
                { root.child("identity", create = true) }, { root.sync() }, { root.exists("profile.header") },
                { root.names() }, { root.fileIdentity("profile.header") }, { root.delete("profile.header") },
                { root.lock("another.lock") }, { root.deleteIfEmpty() },
            )
            attempts.forEach { assertFails { it() } }
            assertEquals(calls, native.ordinaryCalls)
        } finally { assertSame(native.failure, assertFailsWith<IOException> { files.close() }) }
        assertEquals(listOf(2L, 1L), native.closeAttempts)
        assertEquals(1, files.retainedHandleCount)
        assertEquals(1, native.model.remaining) // The uncertain lock still exists in this model.
        assertSame(native.failure, assertFailsWith<IOException> { files.close() })
        assertEquals(listOf(2L, 1L), native.closeAttempts)
    }

    @Test fun actualVaultRefusesWorkAfterUncertainLeaseCloseEvenIfNativeLockWasReleased() {
        val native = FailingLeaseNative(releaseBeforeFailure = true)
        val files = WindowsProfileFiles.openForValidation(native)
        val key = LabVault.randomKey()
        val vault = try { LabVault(files.root, key) } finally { key.fill(0) }
        try {
            assertSame(native.failure, assertFailsWith<IOException> {
                vault.putIfAbsent("synthetic", byteArrayOf(42))
            })
            val saved = native.model.store.root.entries.mapValues { it.value.bytes.copyOf() }
            val calls = native.ordinaryCalls
            assertFails { vault.replace("synthetic", byteArrayOf(99)) }
            assertFails { vault.read("synthetic") }
            assertEquals(calls, native.ordinaryCalls)
            assertEquals(saved.keys, native.model.store.root.entries.keys)
            saved.forEach { (name, bytes) ->
                assertContentEquals(bytes, native.model.store.root.entries.getValue(name).bytes)
            }
        } finally {
            vault.close()
            assertSame(native.failure, assertFailsWith<IOException> { files.close() })
        }
        assertEquals(listOf(2L, 1L), native.closeAttempts)
        assertEquals(0, native.model.remaining) // Managed code must not infer this from a failed native close.
        assertEquals(1, files.retainedHandleCount)
        assertSame(native.failure, assertFailsWith<IOException> { files.close() })
        assertEquals(listOf(2L, 1L), native.closeAttempts)
    }

    @Test fun actualProfileCloseFailureAttemptsIndependentHandlesButRetainsOneTerminalFailure() {
        val native = WindowsProfileModel()
        val files = WindowsProfileFiles.openForValidation(native)
        val profile = DesktopRpcProfile.open(files, password())
        val alreadyClosed = native.closeCalls.toSet()
        val failure = IOException("synthetic uncertain lock release")
        native.closeFailure = failure
        assertSame(failure, assertFailsWith<IOException> { profile.close() })
        val attempts = native.closeCalls.filterNot { it in alreadyClosed }
        assertEquals(3, attempts.size) // Profile lock, identity directory, root: every independent handle once.
        assertEquals(3, files.retainedHandleCount)
        assertEquals(attempts.distinct(), attempts)
        assertFails { profile.vault.read("identity") }
        val previous = native.closeCalls.toList()
        assertSame(failure, assertFailsWith<IOException> { profile.close() })
        assertEquals(previous, native.closeCalls)
        assertTrue(native.store.locks.any { it.second == "profile.lock" })
    }

    @Test fun directoryHandleAdmissionIsBoundedBeforeAnotherNativeAllocation() {
        val native = WindowsProfileModel()
        val files = WindowsProfileFiles.openForValidation(native)
        val root = files.root
        repeat(31) { root.child("identity-$it", create = true) }
        assertEquals(32, files.retainedHandleCount)
        assertFails { root.child("identity-overflow", create = true) }
        assertFalse("identity-overflow" in native.store.root.entries)
        files.close()
        assertEquals(32, native.closeCalls.size)
        assertEquals(0, files.retainedHandleCount)
    }

    @Test fun closeWaitsForLateChildRegistrationThenRetiresEveryOwnedHandleExactlyOnce() {
        val native = WindowsProfileModel()
        val files = WindowsProfileFiles.openForValidation(native)
        val root = files.root
        val entered = CountDownLatch(1)
        val release = CountDownLatch(1)
        native.beforeChild = { entered.countDown(); await(release) }
        val childFailure = AtomicReference<Throwable?>()
        val closeFailure = AtomicReference<Throwable?>()
        val child = thread {
            try { root.child("identity", create = true) } catch (t: Throwable) { childFailure.set(t) }
        }
        await(entered)
        val closer = thread { try { files.close() } catch (t: Throwable) { closeFailure.set(t) } }
        try {
            awaitRetiring(files)
            assertTrue(native.closeCalls.isEmpty())
            assertFails { root.exists("profile.header") }
        } finally { release.countDown(); join(child); join(closer) }
        assertNotNull(childFailure.get())
        assertEquals(null, closeFailure.get())
        assertEquals(listOf(2L, 1L), native.closeCalls)
        assertEquals(0, files.retainedHandleCount)
    }

    @Test fun concurrentOperationIsRejectedNotQueuedAndReadCloseDoesNotFreeAnActiveHandle() {
        val native = WindowsProfileModel()
        native.store.root.entries["profile.header"] = native.store.node(false, byteArrayOf(42))
        val files = WindowsProfileFiles.openForValidation(native)
        val root = files.root
        val entered = CountDownLatch(1)
        val release = CountDownLatch(1)
        native.beforeRead = { entered.countDown(); await(release) }
        val readFailure = AtomicReference<Throwable?>()
        val reader = thread { try { root.read("profile.header") } catch (t: Throwable) { readFailure.set(t) } }
        await(entered)
        assertFails { root.exists("profile.header") }
        val closeFailure = AtomicReference<Throwable?>()
        val closer = thread { try { files.close() } catch (t: Throwable) { closeFailure.set(t) } }
        try {
            awaitRetiring(files)
            assertTrue(native.closeCalls.isEmpty())
        } finally { release.countDown(); join(reader); join(closer) }
        assertNotNull(readFailure.get())
        assertEquals(null, closeFailure.get())
        assertEquals(listOf(1L), native.closeCalls)
    }

    @Test fun interruptedCloseStillJoinsLateNativeReturnAndRetiresHandlesWithoutReportingSuccess() {
        val native = WindowsProfileModel()
        val files = WindowsProfileFiles.openForValidation(native)
        val root = files.root
        val entered = CountDownLatch(1)
        val release = CountDownLatch(1)
        native.beforeChild = { entered.countDown(); await(release) }
        val childFailure = AtomicReference<Throwable?>()
        val closeFailure = AtomicReference<Throwable?>()
        val interruptRestored = AtomicBoolean()
        val child = thread {
            try { root.child("identity", create = true) } catch (t: Throwable) { childFailure.set(t) }
        }
        await(entered)
        val closer = thread {
            try { files.close() } catch (t: Throwable) { closeFailure.set(t) }
            finally { interruptRestored.set(Thread.currentThread().isInterrupted) }
        }
        try {
            awaitRetiring(files)
            closer.interrupt()
            assertTrue(native.closeCalls.isEmpty())
        } finally { release.countDown(); join(child); join(closer) }
        assertNotNull(childFailure.get())
        assertTrue(closeFailure.get() is InterruptedException)
        assertTrue(interruptRestored.get())
        assertEquals(listOf(2L, 1L), native.closeCalls)
        assertEquals(0, files.retainedHandleCount)
        val original = closeFailure.get()
        assertSame(original, assertFailsWith<InterruptedException> { files.close() })
        assertEquals(listOf(2L, 1L), native.closeCalls)
    }

    @Test fun preInterruptedIdleCloseStillRetiresButCachesNonSuccess() {
        val native = WindowsProfileModel()
        val files = WindowsProfileFiles.openForValidation(native)
        val failure = AtomicReference<Throwable?>()
        val restored = AtomicBoolean()
        val closer = thread {
            Thread.currentThread().interrupt()
            try { files.close() } catch (caught: Throwable) { failure.set(caught) }
            finally { restored.set(Thread.currentThread().isInterrupted) }
        }
        join(closer)
        assertTrue(failure.get() is InterruptedException)
        assertTrue(restored.get())
        assertEquals(listOf(1L), native.closeCalls)
        assertEquals(0, files.retainedHandleCount)
        assertSame(failure.get(), assertFailsWith<InterruptedException> { files.close() })
        assertEquals(listOf(1L), native.closeCalls)
    }

    @Test fun interruptFlagSetDuringNativeCloseCannotReportSuccessfulRetirement() {
        val native = WindowsProfileModel()
        val files = WindowsProfileFiles.openForValidation(native)
        native.beforeClose = { Thread.currentThread().interrupt() }
        val failure = AtomicReference<Throwable?>()
        val restored = AtomicBoolean()
        val closer = thread {
            try { files.close() } catch (caught: Throwable) { failure.set(caught) }
            finally { restored.set(Thread.currentThread().isInterrupted) }
        }
        join(closer)
        assertTrue(failure.get() is InterruptedException)
        assertTrue(restored.get())
        assertEquals(listOf(1L), native.closeCalls)
        assertEquals(0, files.retainedHandleCount)
        assertSame(failure.get(), assertFailsWith<InterruptedException> { files.close() })
        assertEquals(listOf(1L), native.closeCalls)
    }

    @Test fun nativeCloseFailureStaysPrimaryWhenAnInterruptFlagAlsoArrives() {
        val native = WindowsProfileModel()
        val files = WindowsProfileFiles.openForValidation(native)
        val original = IOException("synthetic native close failure")
        var attempts = 0
        native.beforeClose = { attempts++; Thread.currentThread().interrupt(); throw original }
        val failure = AtomicReference<Throwable?>()
        val restored = AtomicBoolean()
        val closer = thread {
            try { files.close() } catch (caught: Throwable) { failure.set(caught) }
            finally { restored.set(Thread.currentThread().isInterrupted) }
        }
        join(closer)
        assertSame(original, failure.get())
        assertTrue(restored.get())
        assertEquals(1, original.suppressed.size)
        assertTrue(original.suppressed.single() is InterruptedException)
        assertEquals(1, files.retainedHandleCount)
        assertSame(original, assertFailsWith<IOException> { files.close() })
        assertEquals(1, attempts)
        assertEquals(1, original.suppressed.size)
    }

    @Test fun repeatedInterruptFlagsRetainOnlyTheFirstInterruptionDiagnostic() {
        val native = WindowsProfileModel()
        val files = WindowsProfileFiles.openForValidation(native)
        files.root.child("identity", create = true)
        native.beforeClose = { Thread.currentThread().interrupt() }
        val failure = AtomicReference<Throwable?>()
        val restored = AtomicBoolean()
        val closer = thread {
            try { files.close() } catch (caught: Throwable) { failure.set(caught) }
            finally { restored.set(Thread.currentThread().isInterrupted) }
        }
        join(closer)
        assertTrue(failure.get() is InterruptedException)
        assertTrue(restored.get())
        assertEquals(listOf(2L, 1L), native.closeCalls)
        assertEquals(0, files.retainedHandleCount)
        val original = assertNotNull(failure.get())
        assertTrue(original.suppressed.isEmpty())
        assertSame(original, assertFailsWith<InterruptedException> { files.close() })
        assertTrue(original.suppressed.isEmpty())
        assertEquals(listOf(2L, 1L), native.closeCalls)
    }

    @Test fun nativeInterruptedExceptionWithClearedFlagStillRestoresCallerAndRetainsOwnership() {
        val native = WindowsProfileModel()
        val files = WindowsProfileFiles.openForValidation(native)
        val original = InterruptedException("synthetic native interruption")
        var attempts = 0
        native.beforeClose = { attempts++; throw original }
        val failure = AtomicReference<Throwable?>()
        val restored = AtomicBoolean()
        val closer = thread {
            try { files.close() } catch (caught: Throwable) { failure.set(caught) }
            finally { restored.set(Thread.currentThread().isInterrupted) }
        }
        join(closer)
        assertSame(original, failure.get())
        assertTrue(restored.get())
        assertEquals(1, files.retainedHandleCount)
        assertSame(original, assertFailsWith<InterruptedException> { files.close() })
        assertTrue(original.suppressed.isEmpty())
        assertEquals(1, attempts)
    }

    /** Selective uncertain release, with both possible physical outcomes; never a native Windows fixture. */
    private class FailingLeaseNative(
        val model: WindowsProfileModel = WindowsProfileModel(),
        private val releaseBeforeFailure: Boolean = false,
    ) : WindowsProfileNativeApi by model {
        val failure = IOException("synthetic uncertain lease close")
        val closeAttempts = mutableListOf<Long>()
        var ordinaryCalls = 0
        private var uncertainLease: Long? = null
        private fun <T> ordinary(action: () -> T): T { ordinaryCalls++; return action() }
        override fun fileIdentity(directory: Long, name: String) = ordinary { model.fileIdentity(directory, name) }
        override fun exists(directory: Long, name: String) = ordinary { model.exists(directory, name) }
        override fun names(directory: Long) = ordinary { model.names(directory) }
        override fun child(directory: Long, name: String, create: Boolean) = ordinary {
            model.child(directory, name, create)
        }
        override fun read(directory: Long, name: String, maximum: Int) = ordinary {
            model.read(directory, name, maximum)
        }
        override fun write(directory: Long, name: String, bytes: ByteArray, replace: Boolean) = ordinary {
            model.write(directory, name, bytes, replace)
        }
        override fun lock(directory: Long, name: String, nonBlocking: Boolean) = ordinary {
            model.lock(directory, name, nonBlocking).also { if (uncertainLease == null) uncertainLease = it }
        }
        override fun delete(directory: Long, name: String, expected: LongArray) = ordinary {
            model.delete(directory, name, expected)
        }
        override fun sync(directory: Long) = ordinary { model.sync(directory) }
        override fun deleteIfEmpty(directory: Long) = ordinary { model.deleteIfEmpty(directory) }
        override fun close(handle: Long) {
            closeAttempts += handle
            if (handle == uncertainLease) {
                if (releaseBeforeFailure) model.close(handle)
                throw failure
            }
            model.close(handle)
        }
    }
}
