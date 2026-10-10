package dev.p2pkit.sample.rpc.desktop

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertSame

class RpcDesktopNativeReadbackTest {
    private val source = "a".repeat(40)
    private fun run(
        clean: Boolean = true, os: String = "Mac OS X", arch: String = "arm64",
        directory: String? = null, policy: String? = "development-adhoc-v1", load: () -> String,
    ): String = checkedNativeReadback(source, clean, os, arch, directory, policy, load)

    @Test fun onlyExactInstalledModeMayInvokeTheNativeBoundary() {
        for (arch in listOf("arm64", "aarch64")) {
            var calls = 0
            assertEquals("PACKAGED_NATIVE_SOURCE_AND_ABI_PASS_NO_NETWORK $source", run(arch = arch) {
                calls++; "$source:${"b".repeat(40)}"
            })
            assertEquals(1, calls)
        }
        val forbidden = { throw AssertionError("Native boundary must not execute") }
        assertFailsWith<IllegalStateException> { run(clean = false, load = forbidden) }
        assertFailsWith<IllegalStateException> { run(os = "Linux", load = forbidden) }
        assertFailsWith<IllegalStateException> { run(arch = "x86_64", load = forbidden) }
        for (policy in listOf(null, "", "unknown")) {
            assertFailsWith<IllegalStateException> { run(policy = policy, load = forbidden) }
        }
        for (directory in listOf("", "/private/native")) {
            assertFailsWith<IllegalStateException> { run(directory = directory, load = forbidden) }
        }
    }

    @Test fun malformedOrMismatchedNativeSourceAndFailuresCannotBecomeAPass() {
        for (actual in listOf(source, "$source:", "${"c".repeat(40)}:${"b".repeat(40)}",
            "$source:${"b".repeat(40)}\n")) {
            assertFailsWith<IllegalStateException> { run { actual } }
        }
        val failure = IllegalStateException("synthetic admission or cleanup failure")
        assertSame(failure, assertFailsWith<IllegalStateException> { run { throw failure } })
    }
}
