package dev.p2pkit.sample.android

import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertSame
import kotlin.test.assertTrue

class JoinCredentialInputStateTest {
    @Test
    fun secretDefaultsEmptyAndObscured() {
        val state = JoinCredentialInputState()

        assertEquals("", state.passphrase)
        assertFalse(state.isRevealed)
        assertIs<PasswordVisualTransformation>(
            joinPassphraseVisualTransformation(state.isRevealed)
        )
    }

    @Test
    fun revealIsExplicitAndClearRemovesTheSecret() {
        val state = JoinCredentialInputState()
        state.updatePassphrase("distinct-secret")

        assertFalse(state.isRevealed)
        state.toggleReveal()
        assertTrue(state.isRevealed)
        assertSame(
            VisualTransformation.None,
            joinPassphraseVisualTransformation(state.isRevealed)
        )
        state.conceal()
        assertFalse(state.isRevealed)

        state.toggleReveal()
        assertTrue(state.isRevealed)

        state.clear()
        assertEquals("", state.passphrase)
        assertFalse(state.isRevealed)
    }

    @Test
    fun aRecreatedEphemeralStateDoesNotRestoreThePriorSecret() {
        val original = JoinCredentialInputState()
        original.updatePassphrase("must-not-be-restored")
        original.toggleReveal()

        val recreated = JoinCredentialInputState()

        assertEquals("", recreated.passphrase)
        assertFalse(recreated.isRevealed)
    }

    @Test
    fun lifecycleStopClearsTheSecretAndRevealState() {
        val state = revealedCredential()

        state.onHostStopped()

        assertCleared(state)
    }

    @Test
    fun successfulJoinClearsTheSecretAndRevealState() {
        val state = revealedCredential()

        state.onJoinSucceeded()

        assertCleared(state)
    }

    @Test
    fun permissionResultClearsInsteadOfReusingASecret() {
        val state = revealedCredential()

        state.onPermissionResult()

        assertCleared(state)
    }

    @Test
    fun joinUiWiresEphemeralObscuredAndLifecycleAwareCredentialState() {
        val source = mainActivitySource()

        assertTrue(source.contains("val credentialInput = remember { JoinCredentialInputState() }"))
        assertFalse(source.contains("passInput by rememberSaveable"))
        assertTrue(source.contains("LifecycleEventEffect(Lifecycle.Event.ON_STOP)"))
        assertTrue(source.contains("credentialInput.onHostStopped()"))
        assertTrue(source.contains("credentialInput.onJoinSucceeded()"))
        assertTrue(source.contains("visualTransformation = joinPassphraseVisualTransformation"))
        assertTrue(source.contains("credentialInput.onPermissionResult()"))
        assertFalse(source.contains("if (granted) vm.joinHotspot"))
    }

    private fun revealedCredential(): JoinCredentialInputState =
        JoinCredentialInputState().apply {
            updatePassphrase("must-be-cleared")
            toggleReveal()
        }

    private fun assertCleared(state: JoinCredentialInputState) {
        assertEquals("", state.passphrase)
        assertFalse(state.isRevealed)
    }

    private fun mainActivitySource(): String {
        val relativePath = "src/main/java/dev/p2pkit/sample/android/MainActivity.kt"
        val repositoryPath = "samples/p2p-sample-android/$relativePath"
        val workingDirectory = requireNotNull(System.getProperty("user.dir"))
        var directory: File? = File(workingDirectory).absoluteFile
        while (directory != null) {
            listOf(File(directory, relativePath), File(directory, repositoryPath))
                .firstOrNull(File::isFile)
                ?.let { return it.readText() }
            directory = directory.parentFile
        }
        error("Could not locate $relativePath from $workingDirectory")
    }
}
