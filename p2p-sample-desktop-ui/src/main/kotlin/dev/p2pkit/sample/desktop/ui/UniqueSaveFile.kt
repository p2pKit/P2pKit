package dev.p2pkit.sample.desktop.ui

import java.io.File

/**
 * 2026-07 (SMP-1, P1-32): pick a destination no other transfer is writing to.
 * `createNewFile()` atomically claims the name, so a repeated offer with the
 * same name lands in `"<base> (n)<ext>"` instead of truncating the previous
 * copy, and two concurrent same-named offers can never open two streams onto
 * the same path.
 *
 * Extracted as the samples' shared uniquification helper: the algorithm is
 * duplicated verbatim from the CLI sample's AUDIT-2026-06
 * (A-G9-samples-desktop-ios-19) fix (`p2p-sample-desktop` `Main.kt`
 * `uniqueSaveFile`; the Android sample's `uniqueDestination` is the same
 * shape) — the desktop-ui sample had shipped WITHOUT it, silently
 * overwriting on same-named offers. Keep the copies in sync;
 * `UniqueSaveFileTest` in this module is the de-facto contract (the same
 * jvm-pins-the-shared-shape convention as `HostSelectorTest` in
 * `:p2p-transport-lan`).
 */
internal fun uniqueSaveFile(dir: File, sanitizedName: String): File {
    val dot = sanitizedName.lastIndexOf('.')
    val base = if (dot > 0) sanitizedName.substring(0, dot) else sanitizedName
    val ext = if (dot > 0) sanitizedName.substring(dot) else ""
    var n = 0
    while (true) {
        val candidate = if (n == 0) File(dir, sanitizedName) else File(dir, "$base ($n)$ext")
        val claimed = try {
            candidate.createNewFile() // atomic: false when the name is already taken
        } catch (_: Exception) {
            // Unopenable name or unwritable dir — return the candidate and let
            // the accept path's open-failure guard reject the offer with the
            // real error instead of looping here.
            return candidate
        }
        if (claimed) return candidate
        n++
    }
}
