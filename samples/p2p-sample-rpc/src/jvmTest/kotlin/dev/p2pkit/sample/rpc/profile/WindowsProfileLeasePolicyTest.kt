package dev.p2pkit.sample.rpc.profile

import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.rpc.RpcTrustPurpose
import dev.p2pkit.sample.rpc.RpcCapacityContract
import dev.p2pkit.sample.rpc.desktop.DesktopRpcProfile
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/** Explicit lease-policy call routing over inert storage; not Windows waiting/sharing or runtime evidence. */
class WindowsProfileLeasePolicyTest {
    private fun password() = "synthetic-no-wait-passphrase".toCharArray()

    private class RecordingNative(
        val model: WindowsProfileModel,
        private val requireNoWait: Boolean,
    ) : WindowsProfileNativeApi by model {
        val leases = mutableListOf<Pair<String, Boolean>>()
        override fun lock(directory: Long, name: String, nonBlocking: Boolean): Long {
            leases += name to nonBlocking
            if (requireNoWait) assertTrue(nonBlocking, "Windows caller must explicitly request a no-wait lease")
            return model.lock(directory, name, nonBlocking)
        }

        fun assertRetired() {
            assertEquals(0, model.remaining)
            assertTrue(model.store.locks.isEmpty())
            assertEquals(model.closeCalls.distinct(), model.closeCalls)
        }
    }

    @Test
    fun windowsProfileExplicitlyUsesNoWaitForProofIdentityTrustAndRevocationAcrossReopen() = runTest {
        val store = WindowsProfileModel.Store()
        val pin = PeerFingerprint.parse("p2f1-" + "a".repeat(52))
        val secret = byteArrayOf(17, 23, 42)
        repeat(3) { pass ->
            val native = RecordingNative(WindowsProfileModel(store), requireNoWait = true)
            val password = password()
            try {
                val profile = DesktopRpcProfile.open(WindowsProfileFiles.openForValidation(native), password)
                try {
                    if (pass == 0) {
                        assertContentEquals(secret, profile.vault.putIfAbsent("synthetic-identity", secret))
                        RpcTrustPurpose.entries.forEach {
                            profile.trust.replace(RpcCapacityContract.appId, it, setOf(pin))
                        }
                    } else {
                        assertContentEquals(secret, profile.vault.read("synthetic-identity"))
                        RpcTrustPurpose.entries.forEach {
                            val expected = if (pass == 1) setOf(pin) else emptySet()
                            assertEquals(expected, profile.trust.load(RpcCapacityContract.appId, it))
                            if (pass == 1) profile.trust.replace(RpcCapacityContract.appId, it, emptySet())
                        }
                    }
                    profile.vault.putIfAbsent("synthetic-delete", byteArrayOf(1))
                    assertTrue(profile.vault.delete("synthetic-delete"))
                } finally { profile.close() }
                profile.close()
                assertTrue(native.leases.any { it.first == "profile.lock" })
                assertTrue(native.leases.any { it.first == "vault.lock" })
                assertTrue(native.leases.all { it.second })
            } finally {
                assertTrue(password.all { it == '\u0000' })
                native.assertRetired()
            }
        }
    }

    @Test
    fun nonWindowsTransferredProviderRetainsTheExistingBlockingVaultPolicy() {
        val native = RecordingNative(WindowsProfileModel(), requireNoWait = false)
        val files = WindowsProfileFiles.openForValidation(native)
        // Inert non-Windows provider wrapper: exercise the default policy without changing any OS provider.
        val transferred = object : ProtectedProfileSession by files {}
        try {
            val profile = DesktopRpcProfile.open(transferred, password())
            try {
                profile.vault.putIfAbsent("synthetic-identity", byteArrayOf(1))
                assertContentEquals(byteArrayOf(1), profile.vault.read("synthetic-identity"))
            } finally { profile.close() }
            assertEquals(listOf("profile.lock" to true), native.leases.filter { it.first == "profile.lock" })
            val vaultLeases = native.leases.filter { it.first == "vault.lock" }
            assertTrue(vaultLeases.isNotEmpty())
            assertTrue(vaultLeases.none { it.second })
        } finally { files.close(); native.assertRetired() }
    }
}
