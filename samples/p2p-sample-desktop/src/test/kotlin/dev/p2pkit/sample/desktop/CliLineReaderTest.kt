package dev.p2pkit.sample.desktop

import java.io.Reader
import java.io.StringReader
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlinx.coroutines.runBlocking

class CliLineReaderTest {
    @Test
    fun handlesLfCrLfCrBlankAndFinalUnterminatedLines() {
        val reader = CliLineReader(StringReader("first\r\n\nsecond\rthird\nlast"))
        assertEquals(listOf("first", "", "second", "third", "last", null), List(6) { reader.readLine() })
    }

    @Test
    fun acceptsTheExactLimitIncludingUnterminatedFinalInput() {
        val line = "x".repeat(CLI_MAX_INPUT_CHARS)
        val reader = CliLineReader(StringReader("$line\r\n$line"))
        assertEquals(line, reader.readLine())
        assertEquals(line, reader.readLine())
        assertNull(reader.readLine())
    }

    @Test
    fun rejectsOneCharacterOverAndNeverExecutesItsCommandShapedTail() {
        for (ending in listOf("\n", "\r", "\r\n")) {
            val reader = CliLineReader(StringReader("x".repeat(CLI_MAX_INPUT_CHARS + 1) + "quit" + ending + "info\n"))
            val failure = assertFailsWith<CliInputTooLongException> { reader.readLine() }
            assertFalse(failure.message.orEmpty().contains("quit"))
            assertEquals("info", reader.readLine())
            assertNull(reader.readLine())
        }
    }

    @Test
    fun drainsManyTimesTheLimitFromAGeneratedStreamWithoutAllocatingThatLine() {
        var remaining = CLI_MAX_INPUT_CHARS * 128
        val reader = CliLineReader(object : Reader() {
            override fun read(): Int = if (remaining == 0) -1 else 'x'.code.also { remaining-- }

            override fun read(buffer: CharArray, offset: Int, length: Int): Int {
                if (remaining == 0) return -1
                val count = minOf(length, remaining)
                java.util.Arrays.fill(buffer, offset, offset + count, 'x')
                remaining -= count
                return count
            }

            override fun close() = Unit
        })
        assertFailsWith<CliInputTooLongException> { reader.readLine() }
        assertEquals(0, remaining)
        assertNull(reader.readLine())
    }

    @Test
    fun asynchronousConsoleRemainsUsableAfterRejectingALine() = runBlocking {
        val input = StringReader("x".repeat(CLI_MAX_INPUT_CHARS + 1) + "\nhelp\n").buffered()
        CliConsoleInput(input).use { console ->
            assertFailsWith<CliInputTooLongException> { console.readLine() }
            assertEquals("help", console.readLine())
            assertNull(console.readLine())
        }
    }
}
