package dev.p2pkit.sample.android

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation

/** Ephemeral UI state for the hotspot secret. Deliberately has no Saver. */
internal class JoinCredentialInputState {
    var passphrase: String by mutableStateOf("")
        private set

    var isRevealed: Boolean by mutableStateOf(false)
        private set

    fun updatePassphrase(value: String) {
        passphrase = value
        if (value.isEmpty()) isRevealed = false
    }

    fun toggleReveal() {
        if (passphrase.isNotEmpty()) isRevealed = !isRevealed
    }

    fun conceal() {
        isRevealed = false
    }

    /** Clears the credential when the containing Activity is no longer visible. */
    fun onHostStopped() {
        clear()
    }

    /** Clears the credential once Android reports a successful network join. */
    fun onJoinSucceeded() {
        clear()
    }

    /**
     * Permission results never resume a join automatically: a lifecycle stop may
     * already have cleared the credential while the system dialog was visible.
     */
    fun onPermissionResult() {
        clear()
    }

    fun clear() {
        passphrase = ""
        isRevealed = false
    }
}

internal fun joinPassphraseVisualTransformation(isRevealed: Boolean): VisualTransformation =
    if (isRevealed) VisualTransformation.None else PasswordVisualTransformation()

internal const val PASSPHRASE_REVEAL_MILLIS: Long = 15_000L
