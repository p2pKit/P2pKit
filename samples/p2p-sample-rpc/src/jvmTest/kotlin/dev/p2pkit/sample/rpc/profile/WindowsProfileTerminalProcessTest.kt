package dev.p2pkit.sample.rpc.profile

import dev.p2pkit.sample.rpc.desktop.DesktopRpcTerminalExit
import java.io.File
import java.nio.file.Files
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/** Real JVM subprocesses on the executing host; never presented as a Windows kernel/packaged-app test. */
class WindowsProfileTerminalProcessTest {
    private fun probe(mode: String, expectedExit: Int, expectedMarker: String, deadlineSeconds: Long = 10) {
        val output = Files.createTempFile("rpc-terminal-control-", ".log")
        var process: Process? = null
        try {
            // Only these classes and the Kotlin runtime are required; no Gradle worker or foreign code lookup.
            val classes = listOf(WindowsProfileTerminalProcessProbe::class.java,
                WindowsProfileTerminalClose::class.java, Unit::class.java)
            val classpath = classes.map { File(it.protectionDomain.codeSource.location.toURI()).absolutePath }
                .distinct().joinToString(File.pathSeparator)
            val java = File(System.getProperty("java.home"), "bin/java")
            process = ProcessBuilder(java.absolutePath, "-cp", classpath,
                WindowsProfileTerminalProcessProbe::class.java.name, mode)
                .redirectErrorStream(true).redirectOutput(output.toFile()).start()
            assertTrue(process.waitFor(deadlineSeconds, TimeUnit.SECONDS),
                "Owned terminal probe exceeded ${deadlineSeconds}s")
            assertFalse(process.isAlive)
            assertTrue(Files.size(output) <= 8192, "Unexpected subprocess output bound")
            val text = Files.readString(output)
            println("TERMINAL_JVM_PROBE mode=$mode exit=${process.exitValue()} output=${text.trim()}")
            assertEquals(expectedExit, process.exitValue(), text)
            assertTrue(expectedMarker in text, text)
            if (expectedExit == 125) assertFalse("RETIRED" in text, text)
        } finally {
            process?.let {
                if (it.isAlive) { it.destroyForcibly(); assertTrue(it.waitFor(5, TimeUnit.SECONDS)) }
                assertFalse(it.isAlive)
            }
            Files.deleteIfExists(output)
        }
    }

    @Test fun blockedNativeOwnerCannotExitNaturallyWhenMainReturns() = probe("owner", 125, "OWNER_ENTERED")
    @Test fun blockedConcealmentCannotPreventActualDeadlineTermination() = probe("conceal", 125, "CONCEAL_ENTERED")
    @Test fun blockedCompletionCannotDisarmActualDeadlineTermination() = probe("completion", 125, "COMPLETION_ENTERED")
    @Test fun returnedOwnerAndCompletionRetireTheNonDaemonDeadline() = probe("success", 0, "RETIRED")
    @Test fun applicationFacadeExitsOnlyAfterActualOwnerRetirement() =
        probe("application-success", 0, "APPLICATION_OWNERS_RETURNED")
    @Test fun applicationShutdownHooksStayWithinTheExplicitThirtySecondProductionDeadline() =
        // This control executes the selected 30s application policy, not a longer timeout for an old test.
        probe("application-hook", 125, "SHUTDOWN_HOOK_ENTERED", deadlineSeconds = 40)
}

internal object WindowsProfileTerminalProcessProbe {
    @JvmStatic fun main(args: Array<String>) {
        require(args.size == 1 && args[0] in setOf("owner", "conceal", "completion", "success",
            "application-success", "application-hook"))
        val mode = args[0]
        val blocked = CountDownLatch(1)
        fun stall(name: String) { println(name); System.out.flush(); blocked.await() }
        if (mode.startsWith("application-")) {
            check(WindowsProfileTerminalClose.APPLICATION_DEADLINE_MILLIS == 30_000L)
            if (mode == "application-hook") {
                Runtime.getRuntime().addShutdownHook(Thread { stall("SHUTDOWN_HOOK_ENTERED") })
            }
            val application = DesktopRpcTerminalExit(conceal = {}, retireAllOwners = {
                println("APPLICATION_OWNERS_RETURNED")
                System.out.flush()
            })
            check(application.requestApplicationExit())
            return
        }
        val owner = WindowsProfileTerminalClose.forValidation(500,
            conceal = { if (mode == "conceal") stall("CONCEAL_ENTERED") },
            retireAllOwners = { if (mode == "owner") stall("OWNER_ENTERED") },
            retired = {
                if (mode == "completion") stall("COMPLETION_ENTERED")
                println("RETIRED")
                System.out.flush()
            })
        check(owner.requestApplicationExit())
        // In the owner/completion cases the application thread ends; the owned non-daemon deadline must keep
        // the JVM alive until cleanup finishes or Runtime.halt(125) fires. No synthetic parent keepalive.
    }
}
