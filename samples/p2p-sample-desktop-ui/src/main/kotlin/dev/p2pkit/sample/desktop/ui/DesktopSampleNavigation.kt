package dev.p2pkit.sample.desktop.ui

/** One section/exit owner for toolbar Back, Escape and window close; callbacks are UI-thread confined. */
internal class DesktopSampleNavigation(private val changed: () -> Unit = {}) {
    enum class Section { Samples, Diagnostics, Rpc }

    var section = Section.Samples
        private set
    var leaving = false
        private set
    var cleanupFailed = false
        private set
    private var attempt: Any? = null
    private var exited = false

    fun open(target: Section, ordinaryIdle: Boolean = true): Boolean {
        if (exited || leaving || section != Section.Samples || target == Section.Samples) return false
        if (target == Section.Rpc && !ordinaryIdle) return false
        section = target
        cleanupFailed = false
        changed()
        return true
    }

    /** Root Escape is deliberately unhandled; it never silently exits the application. */
    fun back(closeRpc: ((Boolean) -> Unit) -> Unit): Boolean {
        if (exited || leaving) return true
        return when (section) {
            Section.Samples -> false
            Section.Diagnostics -> { section = Section.Samples; changed(); true }
            Section.Rpc -> { leave(false, closeRpc) {}; true }
        }
    }

    fun exit(close: ((Boolean) -> Unit) -> Unit, completed: (Boolean) -> Unit) = leave(true, close, completed)

    private fun leave(exit: Boolean, close: ((Boolean) -> Unit) -> Unit, completed: (Boolean) -> Unit) {
        if (exited) return
        if (leaving) { completed(false); return } // No queued exit; the host may accept a new explicit request.
        val token = Any()
        attempt = token
        leaving = true
        cleanupFailed = false
        changed()
        close { success ->
            if (attempt !== token) return@close
            attempt = null
            leaving = false
            cleanupFailed = !success
            if (success) {
                if (exit) exited = true else section = Section.Samples
            }
            changed()
            completed(success)
        }
    }
}
