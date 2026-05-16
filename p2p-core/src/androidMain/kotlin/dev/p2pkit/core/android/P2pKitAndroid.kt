package dev.p2pkit.core.android

import android.content.Context

/**
 * Android-only init hook for P2pKit.
 *
 * Call [initialize] **once**, before constructing your first `P2pKit`,
 * typically from `Application.onCreate()`. The library retains only the
 * `applicationContext`, so passing an Activity is safe.
 *
 * What this enables:
 * - **Persistent `PeerId`.** Without this call, the Android default
 *   `PeerIdStorage` falls back to an in-memory implementation and the device
 *   appears to other peers with a new `PeerId` after every process restart.
 *
 * If you forget to call this on Android, the kit will emit a `P2pLogger.warn`
 * at construction and behave as in v0.1 (in-memory `PeerId`).
 */
public object P2pKitAndroid {

    @Volatile
    private var registeredContext: Context? = null

    public fun initialize(context: Context) {
        registeredContext = context.applicationContext
    }

    internal fun applicationContextOrNull(): Context? = registeredContext
}

/** Internal accessor used by `:p2p-core` androidMain factories. */
internal fun androidApplicationContextOrNull(): Context? = P2pKitAndroid.applicationContextOrNull()
