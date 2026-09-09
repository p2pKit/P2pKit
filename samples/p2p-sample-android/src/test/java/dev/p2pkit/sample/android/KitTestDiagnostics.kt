package dev.p2pkit.sample.android

import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pLogger
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.withContext

/** Module-local test adapter: core's commonTest fixtures are intentionally not published. */
internal class KitTestDiagnostics {
    private class Owned(
        val recording: Recording,
        val verify: (Recording) -> Unit,
        var kit: P2pKit? = null
    )

    // Creation/teardown is test-thread-owned; logging below can arrive from platform workers.
    private val owned = mutableListOf<Owned>()

    fun create(
        recording: Recording = Recording(),
        verifyDiagnostics: (Recording) -> Unit = { it.assertQuiet() },
        build: (Recording) -> P2pKit
    ): P2pKit {
        val owner = Owned(recording, verifyDiagnostics)
        owned += owner // Observe construction diagnostics even when no kit is returned.
        return build(recording).also { owner.kit = it }
    }

    /** Stop every returned kit before checking logs; optional settings/files cleanup always runs. */
    suspend fun finish(primaryFailure: Throwable? = null, afterStop: () -> Unit = {}) {
        val failures = mutableListOf<Throwable>()
        for (owner in owned) {
            try {
                withContext(NonCancellable) { owner.kit?.stop() }
            } catch (failure: Throwable) {
                failures += failure
            }
        }
        try {
            afterStop()
        } catch (failure: Throwable) {
            failures += failure
        }
        for (owner in owned) {
            try {
                owner.verify(owner.recording)
            } catch (failure: Throwable) {
                failures += failure
            }
        }
        owned.clear()
        val primary = primaryFailure ?: failures.firstOrNull()
        if (primary != null) {
            failures.filter { it !== primary }.forEach(primary::addSuppressed)
            if (primaryFailure == null) throw primary
        }
    }

    class Recording(private val delegate: P2pLogger = P2pLogger.NoOp) : P2pLogger by delegate {
        enum class Level { WARN, ERROR }
        data class Entry(val level: Level, val message: String, val throwable: Throwable?)
        private val recorded = MutableStateFlow<List<Entry>>(emptyList())
        val entries: List<Entry> get() = recorded.value
        fun warnings(): List<String> = entries.filter { it.level == Level.WARN }.map { it.message }
        fun errors(): List<String> = entries.filter { it.level == Level.ERROR }.map { it.message }

        override fun warn(message: String, throwable: Throwable?) {
            recorded.update { it + Entry(Level.WARN, message, throwable) }
            delegate.warn(message, throwable) // Record BEFORE a deliberate throwing/gating delegate.
        }

        override fun error(message: String, throwable: Throwable?) {
            recorded.update { it + Entry(Level.ERROR, message, throwable) }
            delegate.error(message, throwable)
        }

        fun assertQuiet() {
            if (entries.isNotEmpty()) {
                throw AssertionError("Unexpected WARN/ERROR after kit shutdown: ${entries.joinToString()}")
            }
        }
    }
}
