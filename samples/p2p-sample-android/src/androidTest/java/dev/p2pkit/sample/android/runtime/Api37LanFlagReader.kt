package dev.p2pkit.sample.android.runtime

import android.annotation.TargetApi
import android.os.flagging.AconfigPackage
import android.os.flagging.AconfigStorageReadException

/** Entered lazily, only by the separately admitted API37 profile collector. No hidden delegate or reflection. */
@TargetApi(37)
internal object Api37LanFlagReader {
    // Erased signatures keep the public flagged types out of the old instrumentation entry's loading path.
    fun load(packageName: String): Any = AconfigPackage.load(packageName)

    fun read(reader: Any, flagName: String, defaultValue: Boolean): Boolean =
        (reader as AconfigPackage).getBooleanFlagValue(flagName, defaultValue)

    fun errorCode(error: Throwable): Int = (error as AconfigStorageReadException).errorCode
}
