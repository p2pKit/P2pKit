package dev.p2pkit.sample.rpc.desktop

import dev.p2pkit.sample.rpc.RpcPhoneBuildStamp
import dev.p2pkit.sample.rpc.profile.WindowsProfileCustodyException
import dev.p2pkit.sample.rpc.profile.WindowsProfileFiles
import java.security.MessageDigest
import javax.crypto.AEADBadTagException

/** Fixed synthetic existing-profile control. Never creates, resets or repairs a fixture. */
public object RpcDesktopWindowsPasswordControl {
    private const val PASSWORD = "P2pKit installed synthetic control v1"
    private const val WRONG_PASSWORD = "P2pKit invalid synthetic control v1"
    private const val MARKER = "windows-installed-profile-control-v1"
    private val marker = "P2pKit synthetic installed restart control v1".toByteArray(Charsets.US_ASCII)
    private val owners = arrayOf(Owner(), Owner(), Owner())
    private var started = false
    private var stage = "NOT_STARTED"
    private var retainedFailure: Throwable? = null

    private class Owner {
        var files: WindowsProfileFiles? = null
        var transferred = false
        var attempt: DesktopRpcProfileOpenAttempt? = null
        var profile: DesktopRpcProfile? = null
        var closeStarted = false
    }

    @Synchronized
    public fun run(): String {
        check(!started) { "An installed password control already owns this process" }
        started = true
        try {
            stage = "RUNTIME_PRECHECK"
            RpcDesktopWindowsRuntimeReadback.run()
            WindowsDesktopRuntimePreparation.prepare()
            stage = "BEFORE_VALID_OPEN"
            val before = valid(owners[0])
            stage = "WRONG_PASSWORD_OPEN"
            val owner = owners[1]
            val attempt = acquire(owner, WRONG_PASSWORD)
            check(attempt.result.exceptionOrNull() is AEADBadTagException) {
                "Expected authenticated ciphertext refusal was not observed"
            }
            check(attempt.cleanupFailure == null && attempt.retainedSession == null)
            check(checkNotNull(owner.files).retainedHandleCount == 0)
            // Failed open already performed its owned cleanup; do not repeat any physical close.
            owner.closeStarted = true
            stage = "AFTER_VALID_OPEN"
            check(valid(owners[2]) == before) { "Password refusal changed the existing encrypted profile" }
            stage = "COMPLETE"
            return "{\"source\":\"${RpcPhoneBuildStamp.SOURCE_COMMIT}\",\"password\":{\"schema\":1," +
                "\"scope\":\"INSTALLED_PASSWORD_REFUSAL_NOT_TAMPER_OR_FULL_QUALIFICATION\"," +
                "\"existingMarker\":\"VERIFIED\",\"wrongPassword\":\"AUTHENTICATION_REFUSED\"," +
                "\"encryptedContents\":\"UNCHANGED\",\"validReopen\":\"VERIFIED\"," +
                "\"close\":\"ACKNOWLEDGED\",\"network\":\"NOT_ENTERED\"}}"
        } catch (original: Throwable) {
            retainedFailure = original
            for (owner in owners) retire(owner, original)
            val native = (original as? WindowsProfileCustodyException)?.failure?.name ?: "NOT_CLASSIFIED"
            System.err.println("WINDOWS_INSTALLED_PASSWORD_FAILED stage=$stage native=$native")
            throw original
        }
    }

    private fun acquire(owner: Owner, passwordText: String): DesktopRpcProfileOpenAttempt {
        val password = passwordText.toCharArray()
        try {
            val files = WindowsProfileFiles.openInstalled()
            owner.files = files
            checkProfileControlInventory(files.root.names(), create = false)
            owner.transferred = true
            val attempt = DesktopRpcProfile.openAttempt(files, password)
            owner.attempt = attempt
            owner.profile = attempt.result.getOrNull() // Retain even an unexpectedly accepted wrong password.
            check(password.all { it == '\u0000' })
            return attempt
        } finally { password.fill('\u0000') }
    }

    private fun valid(owner: Owner): Map<String, List<Byte>> {
        val attempt = acquire(owner, PASSWORD)
        val profile = attempt.result.getOrThrow()
        check(attempt.cleanupFailure == null && attempt.retainedSession == null)
        val files = checkNotNull(owner.files)
        val actual = checkNotNull(profile.vault.read(MARKER))
        try { check(MessageDigest.isEqual(actual, marker)) } finally { actual.fill(0) }
        files.requireSettledProfileInventory()
        val root = files.root
        checkProfileControlInventory(root.names(), create = false)
        val identity = root.child("identity")
        val names = identity.names()
        check(names.size in 3..128) // Bounded original protected namespace, including its own vault lease.
        val contents = buildMap {
            // The original profile lease remains exclusive; never reopen its locked file for hashing.
            for (name in listOf("profile.header")) {
                val bytes = root.read(name)
                try { put(name, MessageDigest.getInstance("SHA-256").digest(bytes).toList()) }
                finally { bytes.fill(0) }
            }
            for (name in (names - "vault.lock").sorted()) {
                val bytes = identity.read(name)
                try { put("identity/$name", MessageDigest.getInstance("SHA-256").digest(bytes).toList()) }
                finally { bytes.fill(0) }
            }
        }
        owner.closeStarted = true
        profile.close()
        check(files.retainedHandleCount == 0)
        return contents
    }

    private fun retire(owner: Owner, original: Throwable) {
        if (owner.closeStarted) return
        owner.closeStarted = true
        try {
            if (owner.profile != null) owner.profile?.close()
            else if (!owner.transferred) owner.files?.close()
            // A failed transferred attempt owns its cleanup and any uncertainty until process exit.
        } catch (cleanup: Throwable) {
            if (cleanup !== original) original.addSuppressed(cleanup)
        }
    }
}
