package dev.p2pkit.sample.android

import java.io.ByteArrayInputStream
import java.io.IOException
import java.io.InputStream
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.runBlocking
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNull
import kotlin.test.assertSame
import kotlin.test.assertTrue

class TestFileDigestsTest {
    @Test
    fun hashesKnownVector() {
        assertEquals(
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
            TestFileDigests.sha256(ByteArrayInputStream("abc".encodeToByteArray()))
        )
    }

    @Test
    fun providerOpenFailuresAreReturnedForTheViewModelFailureBranch() = runBlocking {
        for (failure in listOf(IOException(PRIVATE_URI), SecurityException(PRIVATE_URI))) {
            val result = TestFileDigests.readSourceHash { throw failure }
            assertSame(failure, result.exceptionOrNull())
        }
    }

    @Test
    fun providerReadFailureClosesTheStreamAndRemainsAnOrdinaryFailure() = runBlocking {
        var closed = false
        val failure = IOException(PRIVATE_URI)
        val result = TestFileDigests.readSourceHash {
            object : InputStream() {
                override fun read(): Int = throw failure
                override fun close() { closed = true }
            }
        }
        assertSame(failure, result.exceptionOrNull())
        assertTrue(closed)
    }

    @Test
    fun providerCloseFailureIsNotReportedAsASuccessfulDigest() = runBlocking {
        val failure = IOException(PRIVATE_URI)
        val result = TestFileDigests.readSourceHash {
            object : ByteArrayInputStream("fixture".toByteArray()) {
                override fun close(): Unit = throw failure
            }
        }
        assertSame(failure, result.exceptionOrNull())
    }

    @Test
    fun providerCancellationClosesItsStreamAndStillPropagates() = runBlocking {
        var closed = false
        assertFailsWith<CancellationException> {
            TestFileDigests.readSourceHash {
                object : InputStream() {
                    override fun read(): Int = throw CancellationException("synthetic cancelled provider")
                    override fun close() { closed = true }
                }
            }
        }
        assertTrue(closed)
    }

    @Test
    fun providerFatalErrorsAreNotConvertedIntoFileFailures() = runBlocking {
        val error = LinkageError("synthetic fatal provider")
        val thrown = assertFailsWith<LinkageError> { TestFileDigests.readSourceHash { throw error } }
        // Coroutine debug stack recovery may copy a thrown error and retain the original as its cause.
        assertSame(error, thrown.cause ?: thrown)
    }

    @Test
    fun successfulAndAbsentProviderStreamsRemainDistinctFromFailures() = runBlocking {
        assertEquals(
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
            TestFileDigests.readSourceHash { ByteArrayInputStream("abc".toByteArray()) }.getOrThrow()
        )
        assertNull(TestFileDigests.readSourceHash { null }.getOrThrow())
    }
}

private const val PRIVATE_URI = "content://synthetic-provider/private-document.txt"
