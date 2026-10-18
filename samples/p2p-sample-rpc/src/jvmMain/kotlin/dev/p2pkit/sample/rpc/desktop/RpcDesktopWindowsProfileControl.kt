package dev.p2pkit.sample.rpc.desktop

import dev.p2pkit.sample.rpc.RpcPhoneBuildStamp
import dev.p2pkit.sample.rpc.profile.WindowsProfileCustodyException
import dev.p2pkit.sample.rpc.profile.WindowsProfileFiles
import java.security.MessageDigest

/**
 * Explicit synthetic controls for the installed application, never a normal profile credential or fallback.
 * The operator must admit a disposable application context and the maintained outer supervisor first.
 * Creation refuses existing contents. Restart requires the encrypted marker and never repairs missing state.
 * All original sessions, attempts and failures remain reachable until process exit, including failed cleanup.
 */
public object RpcDesktopWindowsProfileControl {
    private const val MARKER = "windows-installed-profile-control-v1"
    private const val SCRATCH = "windows-installed-profile-control-scratch-v1"
    private val marker = "P2pKit synthetic installed restart control v1".toByteArray(Charsets.US_ASCII)
    private val scratch = "P2pKit synthetic replacement control v1".toByteArray(Charsets.US_ASCII)
    private var started = false
    private var stage = "NOT_STARTED"
    private var retainedFailure: Throwable? = null
    private val owners = arrayOf(Owner(), Owner())

    private class Owner {
        var files: WindowsProfileFiles? = null
        var transferred = false
        var attempt: DesktopRpcProfileOpenAttempt? = null
        var profile: DesktopRpcProfile? = null
        var closeStarted = false
    }

    public fun create(): String = run(create = true)
    public fun reopen(): String = run(create = false)

    @Synchronized
    private fun run(create: Boolean): String {
        check(!started) { "An installed profile control already owns this process" }
        started = true
        try {
            stage = "RUNTIME_PRECHECK"
            RpcDesktopWindowsRuntimeReadback.run()
            stage = "DESKTOP_RUNTIME_PREPARATION"
            WindowsDesktopRuntimePreparation.prepare()
            visit(owners[0], create)
            // A second genuine provider/session acquisition exercises reuse without unloading registered JNI.
            visit(owners[1], create = false)
            stage = "COMPLETE"
            val operation = if (create) "profile-create" else "profile-reopen"
            return "{\"source\":\"${RpcPhoneBuildStamp.SOURCE_COMMIT}\",\"profile\":{\"schema\":1," +
                "\"scope\":\"INSTALLED_PRODUCTIVE_PROFILE_CONTROL_NOT_HOST_CLIENT_QUALIFICATION\"," +
                "\"operation\":\"$operation\",\"publicProvider\":\"ADMITTED\",\"encryptedRecord\":\"VERIFIED\"," +
                "\"readReplaceDelete\":\"VERIFIED\",\"reopen\":\"VERIFIED\",\"close\":\"ACKNOWLEDGED\"," +
                "\"network\":\"NOT_ENTERED\"}}"
        } catch (original: Throwable) {
            retainedFailure = original
            val native = (original as? WindowsProfileCustodyException)?.failure?.name ?: "NOT_CLASSIFIED"
            System.err.println("WINDOWS_INSTALLED_PROFILE_FAILED stage=$stage native=$native")
            throw original
        }
    }

    private fun visit(owner: Owner, create: Boolean) {
        // Public synthetic fixture password only. No caller secret, environment override or argv credential.
        val password = "P2pKit installed synthetic control v1".toCharArray()
        try {
            stage = "PUBLIC_PROVIDER"
            val files = WindowsProfileFiles.openInstalled()
            owner.files = files
            stage = "INITIAL_INVENTORY"
            checkProfileControlInventory(files.root.names(), create)
            stage = "PROFILE_OPEN"
            owner.transferred = true
            val attempt = DesktopRpcProfile.openAttempt(files, password)
            owner.attempt = attempt
            val profile = attempt.result.getOrThrow()
            owner.profile = profile
            check(attempt.cleanupFailure == null && attempt.retainedSession == null)
            val vault = profile.vault
            stage = "ENCRYPTED_MARKER"
            if (create) equalAndClear(vault.putIfAbsent(MARKER, marker), marker)
            equalAndClear(checkNotNull(vault.read(MARKER)), marker)
            // Inspect ciphertext through the same admitted native directory, not a pathname reopen.
            val recordName = MessageDigest.getInstance("SHA-256").digest(MARKER.toByteArray(Charsets.UTF_8))
                .joinToString("") { "%02x".format(it) } + ".aesgcm"
            val encrypted = files.root.child("identity").read(recordName)
            check(encrypted.size == marker.size + 29 && encrypted[0] == 1.toByte())
            check(encrypted.asList().windowed(marker.size).none { it == marker.asList() })
            stage = "READ_REPLACE_DELETE"
            check(vault.read(SCRATCH) == null) // Preserve an interrupted scratch record; never silently reset it.
            equalAndClear(vault.putIfAbsent(SCRATCH, marker), marker)
            vault.replace(SCRATCH, scratch)
            equalAndClear(checkNotNull(vault.read(SCRATCH)), scratch)
            check(vault.delete(SCRATCH))
            check(vault.read(SCRATCH) == null && !vault.delete(SCRATCH))
            files.requireSettledProfileInventory()
            stage = "PROFILE_CLOSE"
            owner.closeStarted = true
            profile.close()
            // Successful native acknowledgments plus an empty managed ledger; process retirement is external.
            check(files.retainedHandleCount == 0)
        } catch (original: Throwable) {
            retainedFailure = original // Retain before any cleanup or diagnostic allocation.
            if (!owner.closeStarted) {
                owner.closeStarted = true
                try {
                    if (owner.profile != null) owner.profile?.close()
                    else if (!owner.transferred) owner.files?.close()
                    // A transferred failed attempt already owns retirement; never retry unknown native cleanup.
                } catch (cleanup: Throwable) {
                    if (cleanup !== original) original.addSuppressed(cleanup)
                }
            }
            throw original
        } finally { password.fill('\u0000') }
    }

    private fun equalAndClear(actual: ByteArray, expected: ByteArray) {
        try { check(MessageDigest.isEqual(actual, expected)) }
        finally { actual.fill(0) }
    }
}

/** Refusal before profile writes: no reset, legacy-profile adoption or incomplete-state repair. */
internal fun checkProfileControlInventory(names: Set<String>, create: Boolean) {
    check(if (create) names.isEmpty() else names == setOf("profile.lock", "profile.header", "identity")) {
        "Unexpected disposable profile inventory; preserve it for owner review"
    }
}
