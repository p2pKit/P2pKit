package dev.p2pkit.sample.rpc.profile

import java.io.IOException

/**
 * Code-only failure from the incomplete custody component, not a retry or recovery authorization.
 * JNI resolves this exact class and its sole non-default primitive-int constructor: `<init>(I)V`.
 * Keep paths, handles, identities and application data out of this exception's message and fields.
 */
internal class WindowsProfileCustodyException(val nativeCode: Int) :
    IOException("Windows profile custody rejected (code $nativeCode)") {
    val failure: WindowsProfileCustodyFailure = WindowsProfileCustodyFailure.fromNativeCode(nativeCode)
}

/** Explicit native result mapping; enum order is not an ABI, and unknown codes never imply success. */
internal enum class WindowsProfileCustodyFailure {
    Argument,
    Policy,
    OperatingSystem,
    Busy,
    Closed,
    Limit,
    NotFound,
    CleanupUnknown,
    Unimplemented,
    Unknown;

    companion object {
        fun fromNativeCode(code: Int): WindowsProfileCustodyFailure = when (code) {
            1 -> Argument
            2 -> Policy
            3 -> OperatingSystem
            4 -> Busy
            5 -> Closed
            6 -> Limit
            7 -> NotFound
            8 -> CleanupUnknown
            9 -> Unimplemented
            else -> Unknown
        }
    }
}
