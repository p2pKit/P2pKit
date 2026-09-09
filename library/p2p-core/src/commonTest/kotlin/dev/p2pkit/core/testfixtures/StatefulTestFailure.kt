package dev.p2pkit.core.testfixtures

/**
 * Controlled fault with per-instance state for tests that require the logged cause's exact identity.
 * Coroutine stack-trace recovery may reflectively copy standard exceptions across a channel/suspension.
 * It cannot recreate this instance's token, so those tests observe the original injected fault instead
 * of weakening their cause assertions or disabling recovery for production exceptions.
 */
internal class StatefulTestFailure(
    message: String,
    val identityToken: Any = Any()
) : IllegalStateException(message)
