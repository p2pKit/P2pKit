package dev.p2pkit.core.internal

import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers

internal actual fun blockingIoDispatcher(): CoroutineDispatcher = Dispatchers.IO

internal actual fun blockingCleanupDispatcher(): CoroutineDispatcher = Dispatchers.IO

internal actual fun blockingApplicationCleanupDispatcher(): CoroutineDispatcher = Dispatchers.IO

internal actual fun blockingFileReadDispatcher(): CoroutineDispatcher = Dispatchers.IO

internal actual fun blockingProtocolDispatcher(): CoroutineDispatcher = Dispatchers.IO
