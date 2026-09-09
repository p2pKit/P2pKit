package dev.p2pkit.core.android

import android.content.Context

/**
 * Android-only init hook for P2pKit.
 *
 * Call [initialize] **once**, before constructing your first `P2pKit` with
 * default authenticated identity storage, typically from `Application.onCreate()`.
 * The library retains only the `applicationContext`, so passing an Activity is safe.
 *
 * What this enables:
 * - **Persistent secure identity.** The default Android store wraps the identity
 *   with an Android Keystore key and keeps its record in `noBackupFilesDir`.
 * - **Network-path recovery.** The default `NetworkPathObserver` uses this
 *   context to watch Wi-Fi/Ethernet availability. Hosts can supply their own
 *   observer, but that does not replace the identity-store initialization requirement.
 *
 * For default authenticated identity storage, missing initialization is a
 * configuration failure during kit creation: `P2pError.LocalIdentityUnavailable`
 * with `LocalIdentityFailureKind.STORE_NOT_CONFIGURED` and
 * `LocalIdentityRecovery.CONFIGURE_STORE`. There is no in-memory identity
 * fallback or automatic downgrade to legacy mode.
 *
 * Initialization only registers context; storage and key availability are checked
 * when the kit loads or creates its secure identity.
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
