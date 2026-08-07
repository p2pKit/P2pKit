package dev.p2pkit.core.internal

/**
 * V0.4-PROVENANCE (L2): emit the SDK build identity directly to the
 * platform's native log channel (Android `Logcat`, iOS Xcode console
 * via stdout). This is separate from the user-supplied `P2pLogger` so
 * the identity line ALWAYS appears in hardware-test logs, even when
 * the host app uses the default `P2pLogger.NoOp`.
 *
 * The format is fixed (`p2pkit: [buildInfo] <describe>`) so log scans
 * can rely on it as a stable signature without prior knowledge of the
 * host's logger wiring.
 */
internal expect fun nativeBuildInfoLog(line: String)
