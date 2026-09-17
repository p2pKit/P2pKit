package dev.p2pkit.sample.android.runtime

import java.io.IOException
import java.security.MessageDigest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertSame
import kotlin.test.assertTrue

/** The actual recorder with synthetic ports; these are not Android API or enforcement tests. */
class LanReadbackCollectorTest {
    private val references = LanReadbackCollector.References(
        "a".repeat(32), "b".repeat(40), "c".repeat(40), "d".repeat(64),
        "e".repeat(64), "f".repeat(64), "1".repeat(32),
    )
    private val identity = LanReadbackCollector.Identity(
        references.sourceCommit, false, LanReadbackCollector.PACKAGE, 0, 10123, 10123, 456,
        10, 100, 37, 37, "REL", 0,
    )
    private val readerId = "2".repeat(32)

    private inner class FakePort : LanReadbackCollector.Port {
        val reader = Any()
        val loadedPackages = mutableListOf<String>()
        val reads = mutableListOf<Triple<Any, String, Boolean>>()
        var values = listOf(true, true)
        var currentIdentity = identity
        var currentStamp = LanReadbackCollector.Stamp(1000, 100)
        var identityCalls = 0
        var stampCalls = 0
        var beforeIdentity: (Int) -> Unit = {}
        var beforeStamp: (Int) -> Unit = {}
        var loadFailure: Throwable? = null
        var readFailure: Throwable? = null
        var failRead = 1
        var errorDetails: LanReadbackCollector.ErrorDetails? = null
        var describeFailure: Throwable? = null

        override fun identity(): LanReadbackCollector.Identity {
            beforeIdentity(++identityCalls)
            return currentIdentity
        }

        override fun stamp(): LanReadbackCollector.Stamp {
            beforeStamp(++stampCalls)
            return currentStamp
        }

        override fun load(packageName: String): Any {
            loadedPackages += packageName
            loadFailure?.let { throw it }
            return reader
        }

        override fun read(reader: Any, flagName: String, defaultValue: Boolean): Boolean {
            reads += Triple(reader, flagName, defaultValue)
            if (reads.size == failRead) readFailure?.let { throw it }
            return values[reads.size - 1]
        }

        override fun errorDetails(error: Throwable): LanReadbackCollector.ErrorDetails {
            describeFailure?.let { throw it }
            return errorDetails ?: LanReadbackCollector.ErrorDetails(error.javaClass.name, null)
        }
    }

    private fun collect(
        port: FakePort,
        references: LanReadbackCollector.References = this.references,
        retain: (ByteArray) -> Unit = {},
    ): LanReadbackCollector.Result = LanReadbackCollector.collect(references, port, readerId, retain)

    @Test
    fun exactlyOneLoadAndTheSameObjectReceiveFalseThenTrueDefaults() {
        val port = FakePort()
        val result = collect(port)
        assertTrue(result.complete && result.retained)
        assertEquals(listOf("android.permission.flags"), port.loadedPackages)
        assertEquals(listOf(false, true), port.reads.map { it.third })
        port.reads.forEach {
            assertSame(port.reader, it.first)
            assertEquals("access_local_network_permission_enabled", it.second)
        }
        assertEquals(listOf("load", "read", "read"), result.events.map { it.phase })
        assertEquals(listOf(null, false, true), result.events.map { it.defaultValue })
        assertTrue(result.events.all { it.readerId == readerId && it.identity == identity })
        assertEquals(9, port.identityCalls) // Initial + before/after each API and retention boundary.
        assertNull(result.failure)
    }

    @Test
    fun allFourPairsAreRecordedWithoutInterpretingEnforcementOrChangingDefaults() {
        for (pair in listOf(listOf(true, true), listOf(false, false), listOf(false, true), listOf(true, false))) {
            val port = FakePort().also { it.values = pair }
            val result = collect(port)
            assertTrue(result.complete)
            assertEquals(pair, result.events.drop(1).map { it.value })
            assertEquals(listOf(false, true), port.reads.map { it.third })
        }
    }

    @Test
    fun encodedBytesMatchTheExistingClosedReadbackContract() {
        var bytes: ByteArray? = null
        val result = collect(FakePort()) { bytes = it }
        val binding = "{\"token\":\"${references.token}\",\"sourceCommit\":\"${references.sourceCommit}\"," +
            "\"sourceTree\":\"${references.sourceTree}\",\"appApkSha256\":\"${references.appApkSha256}\"," +
            "\"testApkSha256\":\"${references.testApkSha256}\",\"profileSha256\":\"${references.profileSha256}\"," +
            "\"installId\":\"${references.installId}\",\"packageName\":\"dev.p2pkit.sample.android\"," +
            "\"user\":0,\"uid\":10123,\"pid\":456,\"processStartElapsedMillis\":10,\"installEpochMillis\":100," +
            "\"sdkInt\":37,\"targetSdk\":37,\"codename\":\"REL\",\"previewSdkInt\":0,\"buildDirty\":false}"
        val stamp = "{\"epochMillis\":1000,\"elapsedMillis\":100}"
        val events = (0..2).joinToString(",") { index ->
            val phase = if (index == 0) "load" else "read"
            val default = if (index == 0) "" else ",\"default\":${index == 2}"
            val outcome = if (index == 0) "{\"kind\":\"LOADED\"}" else "{\"kind\":\"RETURNED\",\"value\":true}"
            "{\"phase\":\"$phase\",\"binding\":$binding,\"readerId\":\"$readerId\"$default," +
                "\"start\":$stamp,\"end\":$stamp,\"outcome\":$outcome}"
        }
        val expected = "{\"schema\":\"p2pkit-android-lan-readback/1\",\"mode\":\"profile-readback\"," +
            "\"binding\":$binding,\"readerClass\":\"android.os.flagging.AconfigPackage\"," +
            "\"flagPackage\":\"android.permission.flags\",\"flagName\":\"access_local_network_permission_enabled\"," +
            "\"events\":[$events]}\n"
        assertEquals(expected, assertNotNull(bytes).toString(Charsets.UTF_8))
        assertEquals(expected.length, result.byteCount)
        val hash = MessageDigest.getInstance("SHA-256").digest(assertNotNull(bytes))
            .joinToString("") { "%02x".format(it.toInt() and 0xff) }
        assertEquals(hash, result.sha256)
    }

    @Test
    fun loadAndEachReadErrorEndTheSequenceAndKeepTheOriginal() {
        for (index in 0..2) {
            val failure = IOException("not public: synthetic private message")
            val port = FakePort().apply {
                if (index == 0) {
                    loadFailure = failure
                } else {
                    readFailure = failure
                    failRead = index
                }
            }
            var retained: String? = null
            val result = collect(port) { retained = it.toString(Charsets.UTF_8) }
            assertFalse(result.complete)
            assertTrue(result.retained)
            assertSame(failure, result.failure)
            assertEquals(index, port.reads.size)
            assertEquals(1, port.loadedPackages.size)
            assertEquals(index + 1, result.events.size)
            assertEquals("ERROR", result.events.last().kind)
            assertEquals("java.io.IOException", result.events.last().error?.type)
            assertNull(result.events.last().error?.code)
            assertEquals(if (index == 0) null else readerId, result.events.last().readerId)
            assertFalse(assertNotNull(retained).contains("synthetic private message"))
            assertFalse(result.toString().contains("synthetic private message"))
        }
    }

    @Test
    fun unavailablePublicClassIsARecordedLoadErrorNotAHiddenFallback() {
        val failure = NoClassDefFoundError("private loader detail")
        val port = FakePort().also { it.loadFailure = failure }
        val result = collect(port)
        assertFalse(result.complete)
        assertSame(failure, result.failure)
        assertEquals("java.lang.NoClassDefFoundError", result.events.single().error?.type)
        assertEquals(0, port.reads.size)
    }

    @Test
    fun publicStorageErrorDescriptorKeepsAllCodesWithoutTurningAbsenceIntoFalse() {
        // Descriptor injection only; the Android adapter's public exception cast is not exercised here.
        for (code in 0..4) {
            val port = FakePort().apply {
                loadFailure = IOException("synthetic public-error stand-in")
                errorDetails = LanReadbackCollector.ErrorDetails(LanReadbackCollector.STORAGE_ERROR, code)
            }
            val result = collect(port)
            assertFalse(result.complete)
            assertEquals(code, result.events.single().error?.code)
            assertNull(result.events.single().value)
            assertEquals(0, port.reads.size)
        }
    }

    @Test
    fun errorDescriptorFailureDoesNotReplaceOrRetryTheOriginalCall() {
        val first = IOException("first")
        val port = FakePort().apply {
            loadFailure = first
            describeFailure = NoClassDefFoundError("error accessor unavailable")
        }
        val result = collect(port)
        assertFalse(result.complete)
        assertFalse(result.retained) // Missing descriptor makes serialization incomplete; never invent a code.
        assertSame(first, result.failure)
        assertEquals("load", result.failureStage)
        assertEquals(1, port.loadedPackages.size)
        assertTrue(port.reads.isEmpty())
    }

    @Test
    fun identityDriftAtEveryPrePostBoundaryIsStickyFailure() {
        for (boundary in 2..9) {
            val port = FakePort().apply {
                beforeIdentity = { if (it == boundary) currentIdentity = identity.copy(pid = identity.pid + 1) }
            }
            val result = collect(port)
            assertFalse(result.complete, "boundary=$boundary")
            assertNotNull(result.failure)
            assertEquals(boundary, port.identityCalls)
        }
    }

    @Test
    fun uidUserInstallSourceAndRuntimeDriftAfterTheFirstReadStopsFurtherReads() {
        val mutations: List<(LanReadbackCollector.Identity) -> LanReadbackCollector.Identity> = listOf(
            { it.copy(uid = 10124, applicationUid = 10124) }, { it.copy(user = 1) },
            { it.copy(applicationUid = 10124) }, { it.copy(processStartElapsedMillis = 11) },
            { it.copy(installEpochMillis = 101) }, { it.copy(sourceCommit = "9".repeat(40)) },
            { it.copy(buildDirty = true) }, { it.copy(packageName = "other.app") },
            { it.copy(sdkInt = 36) }, { it.copy(targetSdk = 36) },
            { it.copy(codename = "Preview") }, { it.copy(previewSdkInt = 1) },
        )
        for (mutate in mutations) {
            val port = FakePort().apply {
                beforeIdentity = { if (it == 5) currentIdentity = mutate(identity) }
            }
            val result = collect(port)
            assertFalse(result.complete)
            assertEquals(1, port.reads.size)
            assertNull(result.events.last().end)
        }
    }

    @Test
    fun invalidInitialIdentityNeverLoadsTheReader() {
        val invalidIdentities = listOf(
            identity.copy(uid = 0), identity.copy(uid = 20000), identity.copy(targetSdk = 36),
            identity.copy(buildDirty = true), identity.copy(pid = 0), identity.copy(installEpochMillis = 0),
        )
        for (invalid in invalidIdentities) {
            val port = FakePort().also { it.currentIdentity = invalid }
            val result = collect(port)
            assertFalse(result.complete)
            assertTrue(port.loadedPackages.isEmpty())
            assertTrue(result.events.isEmpty())
        }
    }

    @Test
    fun backwardEpochOrElapsedAtEveryClockBoundaryFailsWithoutRenewal() {
        for (boundary in 2..17) {
            for (epoch in listOf(false, true)) {
                val port = FakePort().apply {
                    beforeStamp = {
                        if (it == boundary) currentStamp = if (epoch) {
                            currentStamp.copy(epochMillis = 999)
                        } else currentStamp.copy(elapsedMillis = 99)
                    }
                }
                assertFalse(collect(port).complete, "boundary=$boundary, epoch=$epoch")
                assertEquals(boundary, port.stampCalls)
            }
        }
    }

    @Test
    fun expiredOriginalWindowAtEveryClockBoundaryNeverStartsANewInterval() {
        for (boundary in 2..17) {
            val port = FakePort().apply {
                beforeStamp = {
                    if (it == boundary) currentStamp = currentStamp.copy(
                        elapsedMillis = 100 + LanReadbackCollector.OBSERVATION_MILLIS,
                    )
                }
            }
            assertFalse(collect(port).complete, "boundary=$boundary")
            assertEquals(boundary, port.stampCalls)
        }
    }

    @Test
    fun clockMustFollowActualInstallAndProcessStartInItsOwnDomain() {
        for (stamp in listOf(LanReadbackCollector.Stamp(99, 100), LanReadbackCollector.Stamp(1000, 9))) {
            val port = FakePort().also { it.currentStamp = stamp }
            assertFalse(collect(port).complete)
            assertTrue(port.loadedPackages.isEmpty())
        }
    }

    @Test
    fun elapsedDeadlineOverflowAndInvalidReferencesAreRejectedBeforeLoad() {
        val port = FakePort().also { it.currentStamp = LanReadbackCollector.Stamp(1000, Long.MAX_VALUE) }
        assertFalse(collect(port).complete)
        assertTrue(port.loadedPackages.isEmpty())
        val invalidReferences = listOf(
            references.copy(token = "../bad"), references.copy(sourceTree = "main"),
            references.copy(testApkSha256 = "f".repeat(63)), references.copy(installId = "A".repeat(32)),
        )
        for (invalid in invalidReferences) {
            val candidate = FakePort()
            assertFalse(collect(candidate, invalid).complete)
            assertTrue(candidate.loadedPackages.isEmpty())
        }
    }

    @Test
    fun writeFailureNeverReturnsASuccessfulTerminalAndIsNotRetried() {
        val failure = IOException("synthetic retention failure")
        var writes = 0
        val result = collect(FakePort()) {
            writes++
            throw failure
        }
        assertFalse(result.complete || result.retained)
        assertSame(failure, result.failure)
        assertEquals("retention", result.failureStage)
        assertEquals(1, writes)
    }

    @Test
    fun retentionClockExpiryAndIdentityDriftCannotPublishCompletedData() {
        for (clock in listOf(true, false)) {
            val port = FakePort()
            val result = collect(port) {
                if (clock) port.currentStamp = port.currentStamp.copy(elapsedMillis = 30100)
                else port.currentIdentity = identity.copy(installEpochMillis = 101)
            }
            assertFalse(result.complete)
            assertTrue(result.retained) // Bytes exist, but the terminal is failed and cannot qualify them.
            assertEquals("retention", result.failureStage)
        }
    }

    @Test
    fun secondaryIdentityAndRetentionFailuresPreserveTheOriginalReadException() {
        val failure = IOException("original read failure")
        val port = FakePort().apply {
            readFailure = failure
            beforeIdentity = { if (it == 5) throw IllegalStateException("later identity failure") }
        }
        val result = collect(port) { throw IOException("later write failure") }
        assertSame(failure, result.failure)
        assertEquals("read-false", result.failureStage)
        assertFalse(result.complete || result.retained)
        assertEquals(1, port.reads.size)
    }

    @Test
    fun interruptedReadRemainsFailedAndStopsTheSequence() {
        val interrupted = InterruptedException("synthetic cancellation")
        val port = FakePort().also { it.readFailure = interrupted }
        val result = collect(port)
        assertSame(interrupted, result.failure)
        assertFalse(result.complete)
        assertEquals(1, port.reads.size)
    }

    @Test
    fun oversizedErrorTypeCannotReachPrivateRetentionOrComplete() {
        val port = FakePort().apply {
            loadFailure = IOException("first")
            errorDetails = LanReadbackCollector.ErrorDetails("example." + "a".repeat(17000), null)
        }
        var writes = 0
        val result = collect(port) { writes++ }
        assertFalse(result.complete || result.retained)
        assertNull(result.byteCount)
        assertEquals(0, writes)
        assertSame(port.loadFailure, result.failure)
    }

    @Test
    fun retainedPayloadIsBoundedAndDoesNotShareTheReturnedDigestBuffer() {
        var count = 0
        var original: ByteArray? = null
        val result = collect(FakePort()) {
            count++
            assertTrue(it.size in 1..LanReadbackCollector.MAX_RECORD_BYTES)
            original = it.copyOf()
            it.fill(0) // The retainer cannot mutate the collector's original checksum input.
        }
        assertEquals(1, count)
        val hash = MessageDigest.getInstance("SHA-256").digest(assertNotNull(original))
            .joinToString("") { "%02x".format(it.toInt() and 0xff) }
        assertEquals(hash, result.sha256)
    }
}
