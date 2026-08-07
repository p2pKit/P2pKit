package dev.p2pkit.core.internal

/**
 * JVM actual: NO-OP.
 *
 * JVM consumers always wire `P2pLogger` to their own log infrastructure
 * (Logback, java.util.logging, slf4j, etc.); the `logger.info` call
 * issued alongside this fallback already routes the identity to the
 * host's chosen sink. Emitting an additional `println` here breaks
 * timing-sensitive JVM tests — Gradle's test runner captures
 * `System.out` through a synchronized channel that introduces enough
 * latency to push `NetworkPathRecoveryTest.pathSatisfiedWakesParked
 * ReconnectHandlerBeforeDelayExpires` past its 2-second budget.
 *
 * The Android and iOS actuals do emit, because:
 *   - Android: even when the sample wires `P2pLogger`, the platform
 *     `Logcat` emission is a useful belt-and-suspenders signal in a
 *     known channel.
 *   - iOS: the iOS sample uses the default `P2pLogger.NoOp`, so this
 *     `println` (mirrored to Xcode console) is the ONLY way the
 *     identity reaches the operator.
 */
internal actual fun nativeBuildInfoLog(line: String) {
    // Intentionally empty. See kdoc.
}
