package dev.p2pkit.sample.android

import android.app.Application
import dev.p2pkit.sample.kmp.initP2pKitAndroid

/**
 * Registers application context before kit creation. The default authenticated
 * identity uses Android Keystore wrapping and `noBackupFilesDir`; missing
 * initialization is a configuration failure, not an in-memory identity fallback.
 */
class P2pKitSampleApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        initP2pKitAndroid(this)
    }
}
