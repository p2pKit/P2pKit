package dev.p2pkit.sample.rpc.profile

import java.io.IOException
import java.lang.reflect.Modifier
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertNull
import kotlin.test.assertSame
import kotlin.test.assertTrue

/** JVM exception/constructor contract only; no native loading or Windows filesystem qualification. */
class WindowsProfileCustodyExceptionTest {
    private val known = linkedMapOf(
        1 to WindowsProfileCustodyFailure.Argument,
        2 to WindowsProfileCustodyFailure.Policy,
        3 to WindowsProfileCustodyFailure.OperatingSystem,
        4 to WindowsProfileCustodyFailure.Busy,
        5 to WindowsProfileCustodyFailure.Closed,
        6 to WindowsProfileCustodyFailure.Limit,
        7 to WindowsProfileCustodyFailure.NotFound,
        8 to WindowsProfileCustodyFailure.CleanupUnknown,
        9 to WindowsProfileCustodyFailure.Unimplemented,
    )
    private val unknown = listOf(Int.MIN_VALUE, -65_536, -1, 0, 10, 31, 255, 65_536, Int.MAX_VALUE)

    @Test
    fun eachNativeFailureCodeHasItsExactExplicitMeaning() {
        assertEquals((1..9).toList(), known.keys.toList())
        assertEquals(
            known.values.toSet() + WindowsProfileCustodyFailure.Unknown,
            WindowsProfileCustodyFailure.entries.toSet(),
        )
        known.forEach { (code, expected) ->
            val exception = WindowsProfileCustodyException(code)
            assertSame(expected, WindowsProfileCustodyFailure.fromNativeCode(code))
            assertSame(expected, exception.failure)
            assertEquals(code, exception.nativeCode)
        }
    }

    @Test
    fun zeroNegativeAndUnrecognizedCodesRemainUnknownWithoutLosingTheirRawValue() {
        unknown.forEach { code ->
            val exception = WindowsProfileCustodyException(code)
            assertSame(WindowsProfileCustodyFailure.Unknown, WindowsProfileCustodyFailure.fromNativeCode(code))
            assertSame(WindowsProfileCustodyFailure.Unknown, exception.failure)
            assertEquals(code, exception.nativeCode)
        }
    }

    @Test
    fun exactJniClassNameAndPrimitiveIntConstructorInstantiateTheTypedException() {
        val type = Class.forName("dev.p2pkit.sample.rpc.profile.WindowsProfileCustodyException")
        assertSame(WindowsProfileCustodyException::class.java, type)
        val intType = checkNotNull(Int::class.javaPrimitiveType)
        val constructor = type.getDeclaredConstructor(intType)
        assertEquals(1, type.declaredConstructors.size)
        assertEquals(listOf(intType), constructor.parameterTypes.toList())
        assertTrue(Modifier.isPublic(constructor.modifiers))
        assertFalse(constructor.isSynthetic)
        assertFailsWith<NoSuchMethodException> { type.getDeclaredConstructor() }
        assertFailsWith<NoSuchMethodException> { type.getDeclaredConstructor(String::class.java) }
        (known.keys + unknown).forEach { code ->
            val exception = assertIs<WindowsProfileCustodyException>(constructor.newInstance(code))
            assertEquals(code, exception.nativeCode)
            assertSame(known[code] ?: WindowsProfileCustodyFailure.Unknown, exception.failure)
            assertIs<IOException>(exception)
        }
    }

    @Test
    fun messageContainsOnlyFixedTextAndTheBoundedNumericCode() {
        (known.keys + unknown).forEach { code ->
            val exception = WindowsProfileCustodyException(code)
            val message = checkNotNull(exception.message)
            assertEquals("Windows profile custody rejected (code $code)", message)
            assertTrue(message.length <= 51)
            assertTrue(message.all { it.code in 32..126 })
            assertNull(exception.cause)
            assertTrue(exception.suppressed.isEmpty())
        }
    }

    @Test
    fun existingIoExceptionCatchesRetainTheSameTypedFailure() {
        val exception = WindowsProfileCustodyException(8)
        val caught = assertFailsWith<IOException> { throw exception }
        assertSame(exception, caught)
        assertSame(
            WindowsProfileCustodyFailure.CleanupUnknown,
            assertIs<WindowsProfileCustodyException>(caught).failure,
        )
    }
}
