package dev.p2pkit.sample.android

import android.app.Application
import dev.p2pkit.core.android.P2pKitAndroid

/**
 * Wires P2pKit's Android-only init hook so that `PeerId` persistence uses
 * the app's `filesDir`. Without this call, the kit logs a warning and falls
 * back to in-memory storage (PeerId regenerates every process).
 */
class P2pKitSampleApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        P2pKitAndroid.initialize(this)
    }
}
