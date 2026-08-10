package dev.p2pkit.core.internal

import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.DelicateCoroutinesApi
import kotlinx.coroutines.newFixedThreadPoolContext

@OptIn(DelicateCoroutinesApi::class)
private val p2pBlockingIoDispatcher: CoroutineDispatcher =
    newFixedThreadPoolContext(2, "P2pKit-blocking-io")

@OptIn(DelicateCoroutinesApi::class)
private val p2pCleanupDispatcher: CoroutineDispatcher =
    newFixedThreadPoolContext(2, "P2pKit-resource-cleanup")

@OptIn(DelicateCoroutinesApi::class)
private val p2pApplicationCleanupDispatcher: CoroutineDispatcher =
    newFixedThreadPoolContext(2, "P2pKit-application-cleanup")

@OptIn(DelicateCoroutinesApi::class)
private val p2pFileReadDispatcher: CoroutineDispatcher =
    newFixedThreadPoolContext(2, "P2pKit-file-read")

@OptIn(DelicateCoroutinesApi::class)
private val p2pProtocolDispatcher: CoroutineDispatcher =
    newFixedThreadPoolContext(2, "P2pKit-protocol-control")

internal actual fun blockingIoDispatcher(): CoroutineDispatcher = p2pBlockingIoDispatcher

internal actual fun blockingCleanupDispatcher(): CoroutineDispatcher = p2pCleanupDispatcher

internal actual fun blockingApplicationCleanupDispatcher(): CoroutineDispatcher =
    p2pApplicationCleanupDispatcher

internal actual fun blockingFileReadDispatcher(): CoroutineDispatcher = p2pFileReadDispatcher

internal actual fun blockingProtocolDispatcher(): CoroutineDispatcher = p2pProtocolDispatcher
