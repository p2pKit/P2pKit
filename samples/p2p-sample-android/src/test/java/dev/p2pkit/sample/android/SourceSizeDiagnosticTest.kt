package dev.p2pkit.sample.android

import java.io.ByteArrayInputStream
import java.io.Closeable
import java.io.IOException
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.asCoroutineDispatcher
import kotlinx.coroutines.async
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertSame
import kotlin.test.assertTrue

class SourceSizeDiagnosticTest {
    @Test
    fun afterSuccessfulHashAllProviderOperationsRunOffTheUiCaller() = runBlocking {
        Executors.newSingleThreadExecutor { Thread(it, "synthetic-ui") }.asCoroutineDispatcher().use { ui ->
            withContext(ui) {
                val caller = Thread.currentThread()
                assertNotNull(TestFileDigests.readSourceHash { ByteArrayInputStream(byteArrayOf(1)) }.getOrThrow())
                assertSame(caller, Thread.currentThread())
                val operations = mutableListOf<String>()
                val size = TestFileDigests.readSourceSize {
                    assertFalse(Thread.currentThread() === caller)
                    operations += "open"
                    Closeable { operations += "close"; assertFalse(Thread.currentThread() === caller) }.use {
                        operations += "length"
                        assertFalse(Thread.currentThread() === caller)
                        12L
                    }
                }
                assertEquals(12L, size.getOrThrow())
                assertEquals(listOf("open", "length", "close"), operations)
                assertSame(caller, Thread.currentThread())
            }
        }
    }

    @Test
    fun absentUnknownAndFailedMetadataNeverBecomeFabricatedSizes() = runBlocking {
        assertNull(TestFileDigests.readSourceSize { null }.getOrThrow())
        assertNull(TestFileDigests.readSourceSize { -1L }.getOrThrow())
        assertEquals(0L, TestFileDigests.readSourceSize { 0L }.getOrThrow())
        val failure = IOException("synthetic provider failure")
        assertSame(failure, TestFileDigests.readSourceSize { throw failure }.exceptionOrNull())
    }

    @Test
    fun readOrCloseFailureIsNotSuccessfulMetadataAndAlwaysCloses() = runBlocking {
        for (failOnClose in listOf(false, true)) {
            var closes = 0
            val failure = IOException("synthetic read or close failure")
            val result = TestFileDigests.readSourceSize {
                Closeable { closes++; if (failOnClose) throw failure }.use {
                    if (!failOnClose) throw failure
                    8L
                }
            }
            assertSame(failure, result.exceptionOrNull())
            assertEquals(1, closes)
        }
    }

    @Test
    fun slowProviderLeavesUiRunnableAndCancelledReturnDoesNotPublishMetadata() = runBlocking {
        Executors.newSingleThreadExecutor { Thread(it, "synthetic-ui") }.asCoroutineDispatcher().use { ui ->
            val entered = CountDownLatch(1)
            val release = CountDownLatch(1)
            var closes = 0
            var published = false
            val task = async(ui) {
                TestFileDigests.readSourceSize {
                    Closeable { closes++ }.use {
                        entered.countDown()
                        check(release.await(5, TimeUnit.SECONDS)) { "fixture release missing" }
                        9L
                    }
                }
                published = true
            }
            try {
                withContext(Dispatchers.IO) { assertTrue(entered.await(5, TimeUnit.SECONDS)) }
                assertEquals("ui-runnable", withContext(ui) { "ui-runnable" })
                task.cancel()
            } finally {
                release.countDown()
            }
            task.join()
            assertTrue(task.isCancelled)
            assertFalse(published)
            assertEquals(1, closes)
        }
    }

    @Test
    fun providerCancellationIsRethrownAfterClose() = runBlocking {
        var closes = 0
        val failure = CancellationException("synthetic provider cancelled")
        val thrown = try {
            TestFileDigests.readSourceSize {
                Closeable { closes++ }.use { throw failure }
            }
            null
        } catch (error: CancellationException) { error }
        assertSame(failure, thrown?.cause ?: thrown)
        assertEquals(1, closes)
    }
}
