package dev.p2pkit.sample.rpc.desktop

import dev.p2pkit.sample.rpc.lab.LabFiles
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import java.nio.file.Files
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

class DesktopRpcCampaignMailboxTest {
    @Test fun cancellationTargetsOneOriginalRequestAndDoesNotReplayOrInventCleanup() = fixture { directory ->
        val mailbox = DesktopRpcCampaignMailbox(directory, "a".repeat(40))
        val id = mailbox.start(mailbox.profiles.single(), "large")
        val request = Json.parseToJsonElement(LabFiles.read(directory.resolve("requests/$id.json")).decodeToString()).jsonObject
        assertEquals("128", request.getValue("clients").jsonPrimitive.content)
        assertFailsWith<IllegalStateException> { mailbox.start(mailbox.profiles.single(), "steady") }
        mailbox.cancel(); mailbox.cancel()
        assertNotNull(mailbox.activeId)
        assertTrue(Files.exists(directory.resolve("cancel/$id.json")))
        assertTrue(Files.exists(directory.resolve("ready/$id.json")))
        assertTrue(Files.exists(directory.resolve("cancel-ready/$id.json")))
        LabFiles.write(directory.resolve("results/$id.json"),
            """{"schema":1,"sourceSha":"${"a".repeat(40)}","id":"$id","state":"RecoveryRequired","cleanupVerified":false}""".toByteArray())
        mailbox.poll()
        assertEquals(null, mailbox.activeId)
        assertFailsWith<IllegalStateException> { runBlocking { mailbox.retire() } }
        assertTrue(Files.exists(directory.resolve("requests/$id.json")))
    }

    @Test fun sourceMismatchAndStaleWorkerRefuseBeforeCreatingARequest() = fixture { directory ->
        assertFailsWith<IllegalArgumentException> { DesktopRpcCampaignMailbox(directory, "f".repeat(40)) }
        val mailbox = DesktopRpcCampaignMailbox(directory, "a".repeat(40))
        LabFiles.write(directory.resolve("status.json"),
            """{"schema":1,"sourceSha":"${"a".repeat(40)}","state":"Idle","updatedAtEpochMillis":1}""".toByteArray(), replace = true)
        assertFailsWith<IllegalStateException> { mailbox.start(mailbox.profiles.single(), "large") }
        Files.list(directory.resolve("requests")).use { assertFalse(it.findAny().isPresent) }
    }

    private fun fixture(test: (java.nio.file.Path) -> Unit) {
        val root = Files.createTempDirectory("rpc-campaign-mailbox-").toRealPath()
        try {
            root.toFile().setReadable(false, false); root.toFile().setWritable(false, false); root.toFile().setExecutable(false, false)
            root.toFile().setReadable(true, true); root.toFile().setWritable(true, true); root.toFile().setExecutable(true, true)
            listOf("requests", "results", "cancel", "ready", "cancel-ready").forEach {
                LabFiles.newDirectory(root, it)
            }
            LabFiles.write(root.resolve("context.json"),
                """{"schema":1,"sourceSha":"${"a".repeat(40)}","profiles":[{"platform":"android","clients":128}]}""".toByteArray())
            LabFiles.write(root.resolve("status.json"),
                """{"schema":1,"sourceSha":"${"a".repeat(40)}","state":"Idle","updatedAtEpochMillis":${System.currentTimeMillis()}}""".toByteArray())
            test(root)
        } finally { root.toFile().deleteRecursively() }
    }
}
