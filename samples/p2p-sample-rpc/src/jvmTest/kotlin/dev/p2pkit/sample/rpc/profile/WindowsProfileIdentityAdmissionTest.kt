package dev.p2pkit.sample.rpc.profile

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFails
import kotlin.test.assertSame

/** Managed adapter controls, not Windows filesystem or native-runtime evidence. */
class WindowsProfileIdentityAdmissionTest {
    @Test fun decoderRejectsZeroVolumeForBothIdentityKinds() {
        for (directory in listOf(false, true)) {
            val raw = WindowsProfileIdentity(0, 0, 1, directory).encoded()
            assertFails { WindowsProfileIdentity.decode(raw, directory) }
        }
    }

    @Test fun decoderPreservesUnsignedVolumeAndFileIdBits() {
        for (directory in listOf(false, true)) {
            for (volume in listOf(1L, Long.MAX_VALUE, Long.MIN_VALUE, -1L)) {
                val identity = WindowsProfileIdentity(volume, Long.MIN_VALUE, -1, directory)
                assertEquals(identity, WindowsProfileIdentity.decode(identity.encoded(), directory))
            }
        }
    }

    @Test fun zeroVolumeRootIsRejectedAndItsOwnedHandleIsClosed() {
        val model = WindowsProfileModel()
        val native = object : WindowsProfileNativeApi by model {
            override fun directoryIdentity(handle: Long) = model.directoryIdentity(handle).also { it[1] = 0 }
        }
        var unexpected: WindowsProfileFiles? = null
        try {
            assertFails { unexpected = WindowsProfileFiles.openForValidation(native) }
        } finally { unexpected?.close() }
        assertEquals(listOf(1L), model.closeCalls)
        assertEquals(0, model.remaining)
    }

    @Test fun foreignVolumeChildIsRejectedButRetainedForExactOwnedCleanup() {
        val model = WindowsProfileModel()
        val native = object : WindowsProfileNativeApi by model {
            override fun directoryIdentity(handle: Long) = model.directoryIdentity(handle).also {
                if (handle != 1L) it[1] = 8
            }
        }
        val files = WindowsProfileFiles.openForValidation(native)
        try {
            assertFails { files.root.child("identity", create = true) }
            assertFails { files.root.exists("profile.header") }
            assertEquals(2, model.remaining)
        } finally { files.close() }
        assertEquals(listOf(2L, 1L), model.closeCalls)
        assertEquals(0, model.remaining)
    }

    @Test fun foreignVolumeFileObservationIsNotPublishedAndPoisonsAdmission() {
        val model = WindowsProfileModel()
        model.store.root.entries["profile.header"] = model.store.node(false, byteArrayOf(42))
        val native = object : WindowsProfileNativeApi by model {
            override fun fileIdentity(directory: Long, name: String) = model.fileIdentity(directory, name).also {
                it[1] = 8
            }
        }
        val files = WindowsProfileFiles.openForValidation(native)
        try {
            assertFails { files.root.fileIdentity("profile.header") }
            assertFails { files.root.exists("profile.header") }
        } finally { files.close() }
        assertEquals(0, model.remaining)
    }

    @Test fun callerSuppliedZeroFileIdNeverReachesNativeDeletion() {
        checkRejectedDeletion(WindowsProfileIdentity(7, 0, 0, false), foreignObservation = false)
    }

    @Test fun discoveredForeignVolumeFileIdNeverReachesNativeDeletion() {
        checkRejectedDeletion(expected = null, foreignObservation = true)
    }

    private fun checkRejectedDeletion(expected: WindowsProfileIdentity?, foreignObservation: Boolean) {
        val model = WindowsProfileModel()
        val original = model.store.node(false, byteArrayOf(42))
        model.store.root.entries["profile.header"] = original
        var deletes = 0
        val native = object : WindowsProfileNativeApi by model {
            override fun fileIdentity(directory: Long, name: String) = model.fileIdentity(directory, name).also {
                if (foreignObservation) it[1] = 8
            }
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
            assertFails { files.root.exists("profile.header") }
        } finally { files.close() }
        assertEquals(0, model.remaining)
    }
}
