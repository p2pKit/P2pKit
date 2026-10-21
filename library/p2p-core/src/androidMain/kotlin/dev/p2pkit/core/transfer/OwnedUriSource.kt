package dev.p2pkit.core.transfer

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.io.RawSource

/** Ownership starts before dispatch: cancelled entry or return must still close the acquired source. */
internal suspend fun <T> prepareOwnedUriSource(source: RawSource, prepare: (RawSource) -> T): T =
    source.use { owned ->
        withContext(Dispatchers.IO) { prepare(owned) }
    }
