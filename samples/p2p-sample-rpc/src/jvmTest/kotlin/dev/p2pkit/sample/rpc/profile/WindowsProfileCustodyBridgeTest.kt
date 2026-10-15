package dev.p2pkit.sample.rpc.profile

import java.io.IOException
import java.security.SecureRandom
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFails
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertSame
import kotlin.test.assertTrue

/** Actual managed mapping with inert JNI calls. No DLL loading, Win32 execution or full-provider qualification. */
class WindowsProfileCustodyBridgeTest {
    private val record = "a".repeat(64) + ".aesgcm"
    private val expected = longArrayOf(1, 19, Long.MIN_VALUE, 23, 0x2ff, 1)

    @Test
    fun constructionDoesNotInvokeNativeCallsOrGenerateAPendingName() {
        val calls = Calls()
        val random = RandomBytes()
        WindowsProfileCustodyBridge(calls, random)
        assertTrue(calls.queries.isEmpty())
        assertTrue(calls.operations.isEmpty())
        assertTrue(random.buffers.isEmpty())
        // The default also constructs without loading or entering JNI; no DLL is loaded in this test JVM.
        WindowsProfileCustodyBridge()
    }

    @Test
    fun actualPartialContractIsReportedAndTheCompleteAdapterRefusesItBeforeRootOpen() {
        val calls = Calls()
        val bridge = WindowsProfileCustodyBridge(calls)
        assertEquals(13, bridge.abi())
        assertEquals(0x43L, bridge.capabilities())
        assertFails { WindowsProfileFiles.openForValidation(bridge) }
        assertTrue(calls.operations.isEmpty())
        assertFalse(WindowsProfileAvailability.IMPLEMENTED)
        assertFalse(WindowsProfileAvailability.QUALIFIED)
    }

    @Test
    fun metadataReadsAndDirectoryOperationsForwardExactArgumentsAndResults() {
        val calls = Calls()
        val bridge = WindowsProfileCustodyBridge(calls)
        assertEquals(41L, bridge.openRoot())
        assertSame(calls.directoryWords, bridge.directoryIdentity(41))
        assertSame(calls.fileWords, bridge.fileIdentity(47, record))
        assertSame(calls.members, bridge.names(47))
        assertSame(calls.bytes, bridge.read(47, record, 262_144))
        assertSame(calls.bytes, bridge.read(47, "vault.lock", 0))
        assertTrue(bridge.exists(47, record))
        calls.present = false
        assertFalse(bridge.exists(47, record))
        assertEquals(43L, bridge.child(41, "identity", false))
        assertEquals(43L, bridge.child(41, "identity", true))
        bridge.sync(47)
        assertEquals(listOf(
            Invocation("openRoot"),
            Invocation("identity", 41L),
            Invocation("fileIdentity", 47L, record),
            Invocation("names", 47L),
            Invocation("read", 47L, record, 262_144),
            Invocation("read", 47L, "vault.lock", 0),
            Invocation("exists", 47L, record),
            Invocation("exists", 47L, record),
            Invocation("child", 41L, "identity"),
            Invocation("createChildDirectory", 41L, "identity"),
            Invocation("syncDirectory", 47L),
        ), calls.operations)
        assertEquals(List(11) { listOf("abi", "capabilities") }.flatten(), calls.queries)
    }

    @Test
    fun nativeObservationFailuresPropagateWithoutFallbackOrCleanup() {
        val operations = listOf<Pair<String, (WindowsProfileCustodyBridge) -> Unit>>(
            "openRoot" to { it.openRoot() },
            "identity" to { it.directoryIdentity(41) },
            "fileIdentity" to { it.fileIdentity(41, record) },
            "exists" to { it.exists(41, record) },
            "names" to { it.names(41) },
            "read" to { it.read(41, record, 262_144) },
            "syncDirectory" to { it.sync(41) },
        )
        for ((name, operation) in operations) {
            val calls = Calls().also { it.failAt = name }
            assertSame(calls.failure, assertFails { operation(WindowsProfileCustodyBridge(calls)) })
            assertEquals(listOf(name), calls.operations.map { it.method })
        }
    }

    @Test
    fun childSelectionDoesNotProbeOrFallBackAfterOpenOrCreateFailure() {
        for (create in listOf(false, true)) {
            val name = if (create) "createChildDirectory" else "child"
            val calls = Calls().also { it.failAt = name }
            assertSame(calls.failure, assertFails {
                WindowsProfileCustodyBridge(calls).child(41, "identity", create)
            })
            assertEquals(listOf(Invocation(name, 41L, "identity")), calls.operations)
        }
    }

    @Test
    fun existingFixedLocksUseOneStrictObservationAndOneExistingAdmission() {
        for (name in listOf("profile.lock", "vault.lock")) {
            val calls = Calls()
            assertEquals(53L, WindowsProfileCustodyBridge(calls).lock(47, name, true))
            assertEquals(listOf(Invocation("exists", 47L, name), Invocation("lockExisting", 47L, name)),
                calls.operations)
            assertEquals(listOf("abi", "capabilities", "abi", "capabilities"), calls.queries)
        }
    }

    @Test
    fun absentFixedLocksDispatchToExactlyTheirRoleSpecificCreate() {
        for ((name, create) in listOf("profile.lock" to "createProfileLock", "vault.lock" to "createVaultLock")) {
            val calls = Calls().also { it.present = false }
            assertEquals(53L, WindowsProfileCustodyBridge(calls).lock(47, name, true))
            assertEquals(listOf(Invocation("exists", 47L, name), Invocation(create, 47L)), calls.operations)
        }
    }

    @Test
    fun blockingLockRequestsAreRejectedWithoutAnyNativeCall() {
        for (name in listOf("profile.lock", "vault.lock")) {
            val calls = Calls()
            assertFailsWith<IllegalArgumentException> { WindowsProfileCustodyBridge(calls).lock(47, name, false) }
            assertTrue(calls.queries.isEmpty())
            assertTrue(calls.operations.isEmpty())
        }
    }

    @Test
    fun arbitraryOrAliasedLockNamesAreRejectedBeforeExistenceObservation() {
        for (name in listOf("", "other.lock", "PROFILE.LOCK", "vault.lock.", "../vault.lock", "vault.lock:ads")) {
            val calls = Calls()
            assertFailsWith<IllegalArgumentException> { WindowsProfileCustodyBridge(calls).lock(47, name, true) }
            assertTrue(calls.queries.isEmpty())
            assertTrue(calls.operations.isEmpty())
        }
    }

    @Test
    fun noObservationErrorIsReinterpretedAsAnAbsentLock() {
        for (code in (1..9) + listOf(-1, Int.MAX_VALUE)) {
            val calls = Calls().also { it.failAt = "exists"; it.failure = WindowsProfileCustodyException(code) }
            assertSame(calls.failure, assertFails {
                WindowsProfileCustodyBridge(calls).lock(47, "vault.lock", true)
            })
            assertEquals(listOf(Invocation("exists", 47L, "vault.lock")), calls.operations)
        }
    }

    @Test
    fun selectedLockFailureNeverOpensAfterCreateOrCreatesAfterOpen() {
        for (present in listOf(false, true)) {
            for ((name, create) in listOf("profile.lock" to "createProfileLock", "vault.lock" to "createVaultLock")) {
                val selected = if (present) "lockExisting" else create
                val calls = Calls().also { it.present = present; it.failAt = selected }
                assertSame(calls.failure, assertFails {
                    WindowsProfileCustodyBridge(calls).lock(47, name, true)
                })
                assertEquals(listOf("exists", selected), calls.operations.map { it.method })
            }
        }
    }

    @Test
    fun everyStorageEntryRejectsTheOlderSameExportAbiBeforeSideEffects() {
        val operations = listOf<(WindowsProfileCustodyBridge) -> Unit>(
            { it.openRoot() }, { it.directoryIdentity(41) }, { it.fileIdentity(41, record) },
            { it.exists(41, record) }, { it.names(41) }, { it.child(41, "identity", false) },
            { it.child(41, "identity", true) }, { it.read(41, record, 1) },
            { it.write(41, record, byteArrayOf(1), true) }, { it.lock(41, "profile.lock", true) },
            { it.lock(41, "vault.lock", true) }, { it.delete(41, record, expected) }, { it.sync(41) },
        )
        for (operation in operations) {
            val calls = Calls().also { it.version = 12 }
            val random = RandomBytes()
            val bridge = WindowsProfileCustodyBridge(calls, random)
            assertFailsWith<IllegalStateException> { operation(bridge) }
            assertTrue(calls.operations.isEmpty())
            assertTrue(random.buffers.isEmpty())
            assertFailsWith<IllegalStateException> { bridge.close(41) }
            assertTrue(calls.operations.isEmpty())
        }
    }

    @Test
    fun wrongUnknownOrPretendFullContractsNeverAdmitStorage() {
        val policies = listOf(-1 to 0x43L, 0 to 0x43L, 1 to 0x7fL, 12 to 0x43L, 14 to 0x43L,
            13 to -1L, 13 to 0L, 13 to 0x3fL, 13 to 0x7fL, 13 to 0x143L)
        for ((version, capabilities) in policies) {
            val calls = Calls().also { it.version = version; it.flags = capabilities }
            val bridge = WindowsProfileCustodyBridge(calls)
            assertEquals(version, bridge.abi())
            assertEquals(capabilities, bridge.capabilities())
            assertFailsWith<IllegalStateException> { bridge.openRoot() }
            assertTrue(calls.operations.isEmpty())
        }
    }

    @Test
    fun initialIntrospectionFailuresDoNotAuthorizeCleanupOrLaterReadmission() {
        for (query in listOf("abi", "capabilities")) {
            val calls = Calls().also { it.failAt = query }
            val bridge = WindowsProfileCustodyBridge(calls)
            assertSame(calls.failure, assertFails { bridge.openRoot() })
            calls.failAt = null
            assertFailsWith<IllegalStateException> { bridge.openRoot() }
            assertFailsWith<IllegalStateException> { bridge.close(41) }
            assertTrue(calls.operations.isEmpty())
        }
    }

    @Test
    fun observingRawCompatibleVersionValuesAloneDoesNotAuthorizeNativeClose() {
        val calls = Calls()
        val bridge = WindowsProfileCustodyBridge(calls)
        assertFailsWith<IllegalStateException> { bridge.close(41) }
        assertTrue(calls.queries.isEmpty())
        bridge.abi()
        bridge.capabilities()
        assertFailsWith<IllegalStateException> { bridge.close(41) }
        assertTrue(calls.operations.isEmpty())
    }

    @Test
    fun changedPinsSealNewStoragePermanentlyButPreserveOriginalClose() {
        val changes = listOf<(Calls) -> Unit>(
            { it.version = 12 }, { it.flags = 0x7fL }, { it.failAt = "abi" }, { it.failAt = "capabilities" },
        )
        for (change in changes) {
            val calls = Calls()
            val bridge = WindowsProfileCustodyBridge(calls)
            assertEquals(41L, bridge.openRoot())
            change(calls)
            val firstFailure = assertFails { bridge.names(41) }
            if (calls.failAt != null) assertSame(calls.failure, firstFailure)
            assertEquals(listOf(Invocation("openRoot")), calls.operations)
            calls.version = 13
            calls.flags = 0x43L
            calls.failAt = null
            assertFailsWith<IllegalStateException> { bridge.names(41) }
            calls.failAt = "abi"
            val queries = calls.queries.toList()
            bridge.close(41)
            assertEquals(queries, calls.queries)
            assertEquals(listOf(Invocation("openRoot"), Invocation("close", 41L)), calls.operations)
        }
    }

    @Test
    fun closingAnAdmittedOwnerDoesNotQueryIntrospectionOrRetryAFailedClose() {
        val calls = Calls()
        val bridge = WindowsProfileCustodyBridge(calls)
        val root = bridge.openRoot()
        calls.failAt = "close"
        val queries = calls.queries.toList()
        assertSame(calls.failure, assertFails { bridge.close(root) })
        assertEquals(queries, calls.queries)
        assertEquals(listOf(Invocation("openRoot"), Invocation("close", root)), calls.operations)
    }

    @Test
    fun lockSelectionRechecksThePinAfterTheExactExistenceObservation() {
        for (present in listOf(false, true)) {
            val calls = Calls().also { it.present = present }
            val bridge = WindowsProfileCustodyBridge(calls)
            bridge.openRoot()
            calls.afterEntry = { if (it == "exists") calls.version = 12 }
            assertFailsWith<IllegalStateException> { bridge.lock(41, "profile.lock", true) }
            bridge.close(41)
            assertEquals(listOf("openRoot", "exists", "close"), calls.operations.map { it.method })
        }
    }

    @Test
    fun writeUsesAll128RandomBitsExactlyOnceWithoutCopyingCallerCiphertext() {
        val calls = Calls()
        val random = RandomBytes()
        val bytes = byteArrayOf(1, 7, 23)
        WindowsProfileCustodyBridge(calls, random).write(47, record, bytes, true)
        val invocation = calls.operations.single()
        assertEquals("writeRecord", invocation.method)
        assertEquals(47L, invocation.arguments[0])
        assertEquals("pwp-pending-00112233445566778899aabbccddeeff", invocation.arguments[1])
        assertEquals(record, invocation.arguments[2])
        assertSame(bytes, invocation.arguments[3])
        assertEquals(true, invocation.arguments[4])
        assertContentEquals(byteArrayOf(1, 7, 23), bytes)
        assertEquals(1, random.buffers.size)
        assertEquals(16, random.buffers.single().size)
        assertTrue(random.buffers.single().all { it == 0.toByte() })
        assertEquals(listOf("abi", "capabilities", "abi", "capabilities"), calls.queries)
    }

    @Test
    fun eachWriteGeneratesANewPendingInputAndPreservesCreateOrReplaceMode() {
        val calls = Calls()
        val random = RandomBytes()
        val bridge = WindowsProfileCustodyBridge(calls, random)
        bridge.write(41, "profile.header", byteArrayOf(), false)
        random.source.fill(0x7f)
        bridge.write(47, record, byteArrayOf(1), false)
        random.source.fill(0x80.toByte())
        bridge.write(47, record, ByteArray(262_144), true)
        assertEquals(listOf("writeRecord", "writeRecord", "writeRecord"), calls.operations.map { it.method })
        assertEquals(listOf(false, false, true), calls.operations.map { it.arguments[4] })
        assertEquals(listOf(
            "pwp-pending-00112233445566778899aabbccddeeff",
            "pwp-pending-" + "7f".repeat(16),
            "pwp-pending-" + "80".repeat(16),
        ), calls.operations.map { it.arguments[1] })
        assertEquals(3, random.buffers.size)
        assertTrue(random.buffers.all { bytes -> bytes.size == 16 && bytes.all { it == 0.toByte() } })
        assertTrue(random.buffers.zipWithNext().all { (first, second) -> first !== second })
    }

    @Test
    fun invalidWriteTargetsAndOversizedDataAreRejectedBeforeEntropyOrNativeEntry() {
        val targets = listOf("profile.header" to true, "PROFILE.HEADER" to false, "vault.lock" to false,
            "" to false, "../profile.header" to false, "b".repeat(63) + ".aesgcm" to false,
            "B".repeat(64) + ".aesgcm" to false, record + ":ads" to true, record + "\n" to false)
        for ((name, replace) in targets) {
            val calls = Calls()
            val random = RandomBytes()
            assertFailsWith<IllegalArgumentException> {
                WindowsProfileCustodyBridge(calls, random).write(47, name, byteArrayOf(1), replace)
            }
            assertTrue(calls.queries.isEmpty())
            assertTrue(calls.operations.isEmpty())
            assertTrue(random.buffers.isEmpty())
        }
        val calls = Calls()
        val random = RandomBytes()
        assertFailsWith<IllegalArgumentException> {
            WindowsProfileCustodyBridge(calls, random).write(47, record, ByteArray(262_145), true)
        }
        assertTrue(calls.queries.isEmpty())
        assertTrue(calls.operations.isEmpty())
        assertTrue(random.buffers.isEmpty())
    }

    @Test
    fun entropyFailureClearsThePartialInputWithoutWritingOrRetrying() {
        val calls = Calls()
        val failure = IOException("Synthetic entropy failure")
        val random = RandomBytes().also { it.failure = failure }
        val bytes = byteArrayOf(1, 7)
        assertSame(failure, assertFails { WindowsProfileCustodyBridge(calls, random).write(47, record, bytes, true) })
        assertTrue(calls.operations.isEmpty())
        assertEquals(1, random.buffers.size)
        assertTrue(random.buffers.single().all { it == 0.toByte() })
        assertContentEquals(byteArrayOf(1, 7), bytes)
    }

    @Test
    fun theWritePinIsRecheckedAfterGeneratingItsName() {
        val calls = Calls()
        val random = RandomBytes().also { it.afterFill = { calls.flags = 0x7f } }
        val bridge = WindowsProfileCustodyBridge(calls, random)
        assertFailsWith<IllegalStateException> { bridge.write(47, record, byteArrayOf(1), true) }
        assertTrue(calls.operations.isEmpty())
        assertEquals(1, random.buffers.size)
        assertTrue(random.buffers.single().all { it == 0.toByte() })
        calls.flags = 0x43
        assertFailsWith<IllegalStateException> { bridge.write(47, record, byteArrayOf(1), true) }
        assertEquals(1, random.buffers.size)
        assertTrue(calls.operations.isEmpty())
    }

    @Test
    fun writeFailureDoesNotGenerateAnotherNamePublishAgainOrDeleteLeftovers() {
        for (code in listOf(2, 3, 7, 8, 9)) {
            val calls = Calls().also { it.failAt = "writeRecord"; it.failure = WindowsProfileCustodyException(code) }
            val random = RandomBytes()
            val bytes = byteArrayOf(1, 7)
            assertSame(calls.failure, assertFails {
                WindowsProfileCustodyBridge(calls, random).write(47, record, bytes, true)
            })
            assertEquals(listOf("writeRecord"), calls.operations.map { it.method })
            assertEquals(1, random.buffers.size)
            assertTrue(random.buffers.single().all { it == 0.toByte() })
            assertContentEquals(byteArrayOf(1, 7), bytes)
        }
    }

    @Test
    fun deletionReportsTrueOnlyAfterTheComposedNativeCallReturns() {
        val calls = Calls()
        val bridge = WindowsProfileCustodyBridge(calls)
        assertTrue(bridge.delete(47, record, expected))
        val invocation = calls.operations.single()
        assertEquals("deleteRecord", invocation.method)
        assertEquals(47L, invocation.arguments[0])
        assertEquals(record, invocation.arguments[1])
        assertSame(expected, invocation.arguments[2])
        assertContentEquals(longArrayOf(1, 19, Long.MIN_VALUE, 23, 0x2ff, 1), expected)
    }

    @Test
    fun initialMissingAndEveryOtherNativeDeleteFailureRemainErrors() {
        for (code in (1..9) + listOf(-1, Int.MAX_VALUE)) {
            val calls = Calls().also { it.failAt = "deleteRecord"; it.failure = WindowsProfileCustodyException(code) }
            assertSame(calls.failure, assertFails {
                WindowsProfileCustodyBridge(calls).delete(47, record, expected)
            })
            assertEquals(listOf("deleteRecord"), calls.operations.map { it.method })
            assertSame(expected, calls.operations.single().arguments[2])
        }
    }

    @Test
    fun fixtureDirectoryDeletionIsExplicitlyUnsupportedEvenAfterAdmission() {
        val calls = Calls()
        val bridge = WindowsProfileCustodyBridge(calls)
        assertFailsWith<UnsupportedOperationException> { bridge.deleteIfEmpty(47) }
        assertTrue(calls.queries.isEmpty())
        assertTrue(calls.operations.isEmpty())
        bridge.openRoot()
        val queries = calls.queries.toList()
        assertFailsWith<UnsupportedOperationException> { bridge.deleteIfEmpty(47) }
        assertEquals(queries, calls.queries)
        assertEquals(listOf(Invocation("openRoot")), calls.operations)
    }

    private data class Invocation(val method: String, val arguments: List<Any>) {
        constructor(method: String, vararg arguments: Any) : this(method, arguments.toList())
    }

    private class Calls : WindowsProfileCustodyCalls {
        var version = 13
        var flags = 0x43L
        var present = true
        var failAt: String? = null
        var failure: Throwable = IOException("Synthetic native failure")
        var afterEntry: ((String) -> Unit)? = null
        val queries = mutableListOf<String>()
        val operations = mutableListOf<Invocation>()
        val directoryWords = longArrayOf(1, 19, 1, 23, 0x1ff, 1)
        val fileWords = longArrayOf(1, 19, Long.MIN_VALUE, 23, 0x2ff, 1)
        val members = arrayOf("profile.lock", "identity")
        val bytes = byteArrayOf(1, 7)

        private fun enter(name: String, vararg arguments: Any) {
            if (name == "abi" || name == "capabilities") queries += name
            else operations += Invocation(name, arguments.toList())
            afterEntry?.invoke(name)
            if (failAt == name) throw failure
        }

        override fun abi(): Int { enter("abi"); return version }
        override fun capabilities(): Long { enter("capabilities"); return flags }
        override fun openRoot(): Long { enter("openRoot"); return 41 }
        override fun child(directory: Long, name: String): Long { enter("child", directory, name); return 43 }
        override fun createChildDirectory(directory: Long, name: String): Long {
            enter("createChildDirectory", directory, name)
            return 43
        }
        override fun identity(handle: Long): LongArray { enter("identity", handle); return directoryWords }
        override fun fileIdentity(directory: Long, name: String): LongArray {
            enter("fileIdentity", directory, name)
            return fileWords
        }
        override fun exists(directory: Long, name: String): Boolean { enter("exists", directory, name); return present }
        override fun names(directory: Long): Array<String> { enter("names", directory); return members }
        override fun read(directory: Long, name: String, maximum: Int): ByteArray {
            enter("read", directory, name, maximum)
            return bytes
        }
        override fun lockExisting(directory: Long, name: String): Long {
            enter("lockExisting", directory, name)
            return 53
        }
        override fun createProfileLock(root: Long): Long { enter("createProfileLock", root); return 53 }
        override fun createVaultLock(identityDirectory: Long): Long {
            enter("createVaultLock", identityDirectory)
            return 53
        }
        override fun writeRecord(
            directory: Long, pendingName: String, target: String, ciphertext: ByteArray, replace: Boolean,
        ) = enter("writeRecord", directory, pendingName, target, ciphertext, replace)
        override fun deleteRecord(directory: Long, name: String, expected: LongArray) =
            enter("deleteRecord", directory, name, expected)
        override fun syncDirectory(directory: Long) = enter("syncDirectory", directory)
        override fun close(handle: Long) = enter("close", handle)
    }

    private class RandomBytes : SecureRandom() {
        val source = ByteArray(16) { (it * 17).toByte() }
        val buffers = mutableListOf<ByteArray>()
        var failure: Throwable? = null
        var afterFill: (() -> Unit)? = null

        override fun nextBytes(bytes: ByteArray) {
            buffers += bytes
            assertEquals(16, bytes.size)
            source.copyInto(bytes)
            afterFill?.invoke()
            failure?.let { throw it }
        }
    }
}
