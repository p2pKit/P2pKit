package dev.p2pkit.core.internal

internal actual fun nativeBuildInfoLog(line: String) {
    // println on iOS goes to stdout, which Xcode mirrors as the device's
    // attached console. Visible regardless of the host app's P2pLogger
    // wiring — matches the format IosLanDebug.log uses elsewhere.
    println("p2pkit: [buildInfo] $line")
}
