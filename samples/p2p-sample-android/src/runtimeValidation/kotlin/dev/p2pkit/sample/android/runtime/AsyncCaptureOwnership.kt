package dev.p2pkit.sample.android.runtime

/** A timed-out observer cannot dispose a bitmap that the asynchronous producer still owns. */
internal class AsyncCaptureOwnership(private val dispose: () -> Unit) {
    private var started = false
    private var completed = false
    private var released = false
    private var disposed = false

    @Synchronized
    fun start(): Boolean {
        check(!started)
        if (released) return false
        started = true
        return true
    }

    @Synchronized
    fun complete() {
        check(started && !completed)
        completed = true
        disposeIfRetired()
    }

    @Synchronized
    fun release() {
        released = true
        disposeIfRetired()
    }

    @Synchronized
    fun retired(): Boolean = disposed

    private fun disposeIfRetired() {
        if (released && (!started || completed) && !disposed) {
            dispose()
            disposed = true
        }
    }
}
