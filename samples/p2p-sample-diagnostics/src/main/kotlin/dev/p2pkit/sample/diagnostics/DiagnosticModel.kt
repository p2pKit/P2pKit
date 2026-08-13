package dev.p2pkit.sample.diagnostics

import dev.p2pkit.core.P2pLogger
import kotlinx.serialization.ExperimentalSerializationApi
import kotlinx.serialization.Serializable
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.io.File
import java.io.FileOutputStream
import java.net.InetAddress
import java.nio.charset.StandardCharsets
import java.nio.file.AtomicMoveNotSupportedException
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.security.MessageDigest
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.UUID
import java.util.zip.ZipEntry
import java.util.zip.ZipFile
import java.util.zip.ZipOutputStream

/**
 * Test-harness-only diagnostic event schema shared by the Android, JVM CLI,
 * and Desktop UI samples. The iOS sample mirrors this exact JSON schema in
 * Swift because its application target consumes the release XCFramework
 * rather than this JVM-only helper module.
 *
 * This module never participates in protocol decisions. Record/export
 * failures are contained and cannot fail a connection or transfer.
 */
@Serializable
public data class DiagnosticEvent(
    val schemaVersion: Int = SCHEMA_VERSION,
    val index: Long,
    val timestamp: String,
    val platform: String,
    val operatingSystem: String,
    val applicationVersion: String,
    val buildNumber: String,
    val gitCommitSha: String,
    val safeDeviceId: String,
    val testSessionId: String,
    val testId: String,
    val role: String,
    val peerId: String? = null,
    val connectionId: String? = null,
    val transferId: String? = null,
    val category: String,
    val eventName: String,
    val severity: DiagnosticSeverity,
    val currentState: String? = null,
    val previousState: String? = null,
    val protocolVersion: String? = null,
    val packetType: String? = null,
    val direction: DiagnosticDirection = DiagnosticDirection.LOCAL,
    val payloadSizeBytes: Long? = null,
    val sequenceNumber: Long? = null,
    val chunkNumber: Int? = null,
    val chunkCount: Int? = null,
    val retryNumber: Int? = null,
    val timeoutMillis: Long? = null,
    val retryDelayMillis: Long? = null,
    val durationMillis: Long? = null,
    val errorCode: String? = null,
    val errorDescription: String? = null,
    val outcome: DiagnosticOutcome? = null,
    val details: Map<String, String> = emptyMap(),
    val redactedFields: List<String> = emptyList()
) {
    public companion object {
        public const val SCHEMA_VERSION: Int = 1
    }
}

@Serializable
public enum class DiagnosticSeverity {
    DEBUG,
    INFO,
    WARNING,
    ERROR
}

@Serializable
public enum class DiagnosticDirection {
    SENT,
    RECEIVED,
    LOCAL
}

@Serializable
public enum class DiagnosticOutcome {
    SUCCESS,
    FAILURE,
    CANCELLATION,
    TIMEOUT,
    INTERRUPTION,
    RECOVERY,
    BLOCKED
}

@Serializable
public data class DiagnosticEnvironment(
    val platform: String,
    val operatingSystem: String,
    val applicationVersion: String,
    val buildNumber: String,
    val gitCommitSha: String,
    val safeDeviceId: String
) {
    init {
        require(platform.isNotBlank())
        require(operatingSystem.isNotBlank())
        require(applicationVersion.isNotBlank())
        require(buildNumber.isNotBlank())
        require(gitCommitSha.isNotBlank())
        require(safeDeviceId.matches(SAFE_ID)) {
            "safeDeviceId must contain only share-safe identifier characters"
        }
    }
}

@Serializable
public data class DiagnosticConfiguration(
    val protocolVersion: String = "secure-v2",
    val timeoutsMillis: Map<String, Long> = emptyMap(),
    val retryValues: Map<String, Long> = emptyMap(),
    val packetLimits: Map<String, Long> = emptyMap(),
    val faultInjection: Map<String, String> = emptyMap(),
    val values: Map<String, String> = emptyMap()
)

@Serializable
public data class DiagnosticTransferSummary(
    val transferId: String,
    val connectionIds: List<String>,
    val peerIds: List<String>,
    val senderFileSizeBytes: Long?,
    val receiverFileSizeBytes: Long?,
    val senderSha256: String?,
    val receiverSha256: String?,
    val integrityMatch: Boolean?
)

@Serializable
public data class DiagnosticSessionSummary(
    val schemaVersion: Int = DiagnosticEvent.SCHEMA_VERSION,
    val testId: String,
    val testSessionId: String,
    val role: String,
    val platform: String,
    val operatingSystem: String,
    val applicationVersion: String,
    val buildNumber: String,
    val gitCommitSha: String,
    val safeDeviceId: String,
    val startTimestamp: String?,
    val endTimestamp: String?,
    val protocolVersion: String,
    val connectionIds: List<String>,
    val transferIds: List<String>,
    val peerIds: List<String>,
    /**
     * Hash and integrity evidence grouped by the exact transfer identifier.
     * Top-level hash fields are populated only when [selectedTransferId]
     * identifies one unambiguous transfer.
     */
    val transferSummaries: List<DiagnosticTransferSummary>,
    val selectedTransferId: String?,
    val senderFileSizeBytes: Long?,
    val receiverFileSizeBytes: Long?,
    val senderSha256: String?,
    val receiverSha256: String?,
    val integrityMatch: Boolean?,
    val finalState: String?,
    val finalOutcome: DiagnosticOutcome?,
    val warningCount: Int,
    val errorCount: Int,
    val eventCount: Int,
    val droppedEventCount: Long,
    val configuration: DiagnosticConfiguration,
    val manualEvidenceStillRequired: List<String>
)

public data class DiagnosticFilter(
    val testId: String? = null,
    val sessionId: String? = null,
    val transferId: String? = null,
    val minimumSeverity: DiagnosticSeverity? = null,
    val search: String? = null
)

public data class DiagnosticRecord(
    val peerId: String? = null,
    val connectionId: String? = null,
    val transferId: String? = null,
    val category: String,
    val eventName: String,
    val severity: DiagnosticSeverity = DiagnosticSeverity.INFO,
    val currentState: String? = null,
    val previousState: String? = null,
    val protocolVersion: String? = null,
    val packetType: String? = null,
    val direction: DiagnosticDirection = DiagnosticDirection.LOCAL,
    val payloadSizeBytes: Long? = null,
    val sequenceNumber: Long? = null,
    val chunkNumber: Int? = null,
    val chunkCount: Int? = null,
    val retryNumber: Int? = null,
    val timeoutMillis: Long? = null,
    val retryDelayMillis: Long? = null,
    val durationMillis: Long? = null,
    val errorCode: String? = null,
    val errorDescription: String? = null,
    val outcome: DiagnosticOutcome? = null,
    val details: Map<String, String> = emptyMap()
)

/**
 * Thread-safe bounded recorder. It retains at most [maxEvents] and
 * [maxEncodedBytes] across at most [maxSessions] session identifiers.
 */
public class DiagnosticRecorder(
    public val environment: DiagnosticEnvironment,
    public val configuration: DiagnosticConfiguration = DiagnosticConfiguration(),
    private val maxEvents: Int = 5_000,
    private val maxEncodedBytes: Int = 5 * 1024 * 1024,
    private val maxSessions: Int = 8,
    private val timestamp: () -> String = ::isoTimestampNow,
    private val monotonicMillis: () -> Long = { System.nanoTime() / 1_000_000L },
    private val idFactory: () -> String = {
        "session-" + UUID.randomUUID().toString().replace("-", "").take(12)
    },
    private val eventSink: (String) -> Unit = {}
) {
    private val lock: Any = Any()
    private val entries: MutableList<StoredEvent> = mutableListOf()
    private val pendingSinkLines: ArrayDeque<PendingSinkLine> = ArrayDeque()
    private var pendingSinkBytes: Int = 0
    private var nextIndex: Long = 1L
    private var encodedBytes: Int = 0
    private var droppedEvents: Long = 0L
    private var sinkDraining: Boolean = false
    private var sessionContext: SessionContext = SessionContext(
        testId = "UNASSIGNED",
        sessionId = "session-unassigned",
        role = "unspecified",
        startElapsedMillis = monotonicMillis()
    )

    public val activeTestId: String
        get() = synchronized(lock) { sessionContext.testId }

    public val activeSessionId: String
        get() = synchronized(lock) { sessionContext.sessionId }

    public val activeRole: String
        get() = synchronized(lock) { sessionContext.role }

    @Volatile
    public var displayPaused: Boolean = false
        private set

    init {
        require(maxEvents > 0) { "maxEvents must be positive" }
        require(maxEncodedBytes > 0) { "maxEncodedBytes must be positive" }
        require(maxSessions > 0) { "maxSessions must be positive" }
    }

    public fun startSession(testId: String, role: String, requestedSessionId: String? = null): String {
        val normalizedTestId = normalizeTestId(testId)
        val sessionId = requestedSessionId?.trim()?.takeIf { it.isNotEmpty() } ?: idFactory()
        require(sessionId.matches(SAFE_ID) && sessionId.length <= 80) {
            "Session ID must use 1-80 letters, digits, '.', '_', or '-'"
        }
        require(role.trim().matches(SAFE_ROLE)) {
            "Role must use 1-24 letters, digits, '_', or '-'"
        }
        val newContext = SessionContext(
            testId = normalizedTestId,
            sessionId = sessionId,
            role = role.trim().lowercase(),
            startElapsedMillis = monotonicMillis()
        )
        val shouldDrain = synchronized(lock) {
            sessionContext = newContext
            appendSafelyLocked(
                DiagnosticRecord(
                    category = "test",
                    eventName = DiagnosticEventNames.TEST_SESSION_CREATED,
                    currentState = "active",
                    protocolVersion = configuration.protocolVersion,
                    details = mapOf("testMode" to "true")
                ),
                newContext
            )
        }
        drainSinkIfOwner(shouldDrain)
        return sessionId
    }

    public fun completeSession(outcome: DiagnosticOutcome, reason: String, finalState: String) {
        val severity = if (outcome == DiagnosticOutcome.SUCCESS || outcome == DiagnosticOutcome.RECOVERY) {
            DiagnosticSeverity.INFO
        } else {
            DiagnosticSeverity.ERROR
        }
        val shouldDrain = synchronized(lock) {
            val context = sessionContext
            appendSafelyLocked(
                DiagnosticRecord(
                    category = "test",
                    eventName = DiagnosticEventNames.TEST_SESSION_COMPLETED,
                    severity = severity,
                    currentState = finalState,
                    protocolVersion = configuration.protocolVersion,
                    durationMillis = (monotonicMillis() - context.startElapsedMillis).coerceAtLeast(0L),
                    errorCode = if (severity == DiagnosticSeverity.ERROR) "TEST_NOT_SUCCESSFUL" else null,
                    errorDescription = if (severity == DiagnosticSeverity.ERROR) reason else null,
                    outcome = outcome,
                    details = mapOf("reason" to reason)
                ),
                context
            )
        }
        drainSinkIfOwner(shouldDrain)
    }

    /**
     * Records an event without throwing. Invalid/unserializable diagnostic
     * input increments [droppedEventCount] instead of affecting the operation
     * being observed.
     */
    public fun record(record: DiagnosticRecord) {
        val shouldDrain = synchronized(lock) {
            appendSafelyLocked(record, sessionContext)
        }
        drainSinkIfOwner(shouldDrain)
    }

    public fun snapshot(filter: DiagnosticFilter = DiagnosticFilter()): List<DiagnosticEvent> =
        synchronized(lock) {
            entries.asSequence().map { it.event }.filter { it.matches(filter) }.toList()
        }

    public fun jsonLines(sessionId: String = activeSessionId): String =
        synchronized(lock) {
            val selected = entries.asSequence()
                .filter { it.event.testSessionId == sessionId }
                .map { it.json }
                .toList()
            selected.joinToString(
                separator = "\n",
                postfix = if (selected.isNotEmpty()) "\n" else ""
            )
        }

    public fun readableText(sessionId: String = activeSessionId): String =
        snapshot(DiagnosticFilter(sessionId = sessionId)).joinToString(
            separator = "\n",
            postfix = "\n"
        ) { event ->
            buildString {
                append(event.timestamp)
                append(' ')
                append(event.severity.name.padEnd(7))
                append(' ')
                append(event.eventName)
                append(" test=").append(event.testId)
                append(" session=").append(event.testSessionId)
                event.connectionId?.let { append(" connection=").append(it) }
                event.transferId?.let { append(" transfer=").append(it) }
                event.packetType?.let { append(" packet=").append(it) }
                event.currentState?.let { append(" state=").append(it) }
                event.errorCode?.let { append(" error=").append(it) }
                event.outcome?.let { append(" outcome=").append(it) }
            }
        }

    public fun summary(
        sessionId: String = activeSessionId,
        manualEvidence: List<String> = DEFAULT_MANUAL_EVIDENCE,
        selectedTransferId: String? = null
    ): DiagnosticSessionSummary {
        selectedTransferId?.let {
            require(it.matches(SAFE_ID)) { "Selected transfer ID is not share-safe" }
        }
        val captured = synchronized(lock) {
            SummaryCapture(
                events = entries.asSequence()
                    .map { it.event }
                    .filter { it.testSessionId == sessionId }
                    .toList(),
                activeContext = sessionContext,
                droppedEventCount = droppedEvents
            )
        }
        val events = captured.events
        val start = events.firstOrNull()
        val end = events.lastOrNull()
        val transferSummaries = events.asSequence()
            .mapNotNull { it.transferId }
            .distinct()
            .map { transferId -> transferSummary(transferId, events) }
            .toList()
        val selectedTransfer = when {
            selectedTransferId != null -> transferSummaries.singleOrNull {
                it.transferId == selectedTransferId
            }
            transferSummaries.size == 1 -> transferSummaries.single()
            else -> null
        }
        val terminal = events.lastOrNull {
            it.eventName == DiagnosticEventNames.TEST_SESSION_COMPLETED && it.outcome != null
        }
        val fallbackContext = captured.activeContext.takeIf { it.sessionId == sessionId }
        return DiagnosticSessionSummary(
            testId = start?.testId ?: fallbackContext?.testId ?: "UNASSIGNED",
            testSessionId = sessionId,
            role = start?.role ?: fallbackContext?.role ?: "unspecified",
            platform = environment.platform,
            operatingSystem = environment.operatingSystem,
            applicationVersion = environment.applicationVersion,
            buildNumber = environment.buildNumber,
            gitCommitSha = environment.gitCommitSha,
            safeDeviceId = environment.safeDeviceId,
            startTimestamp = start?.timestamp,
            endTimestamp = end?.timestamp,
            protocolVersion = terminal?.protocolVersion ?: configuration.protocolVersion,
            connectionIds = events.mapNotNull { it.connectionId }.distinct(),
            transferIds = events.mapNotNull { it.transferId }.distinct(),
            peerIds = events.mapNotNull { it.peerId }.distinct(),
            transferSummaries = transferSummaries,
            selectedTransferId = selectedTransfer?.transferId,
            senderFileSizeBytes = selectedTransfer?.senderFileSizeBytes,
            receiverFileSizeBytes = selectedTransfer?.receiverFileSizeBytes,
            senderSha256 = selectedTransfer?.senderSha256,
            receiverSha256 = selectedTransfer?.receiverSha256,
            integrityMatch = selectedTransfer?.integrityMatch,
            finalState = terminal?.currentState,
            finalOutcome = terminal?.outcome,
            warningCount = events.count { it.severity == DiagnosticSeverity.WARNING },
            errorCount = events.count { it.severity == DiagnosticSeverity.ERROR },
            eventCount = events.size,
            droppedEventCount = captured.droppedEventCount,
            configuration = configuration.copy(
                faultInjection = DiagnosticRedactor.redact(configuration.faultInjection).values,
                values = DiagnosticRedactor.redact(configuration.values).values
            ),
            manualEvidenceStillRequired = manualEvidence
        )
    }

    public fun pauseDisplay() {
        displayPaused = true
    }

    public fun resumeDisplay() {
        displayPaused = false
    }

    /** Clears only the active test session. Callers provide confirmation in their UI. */
    public fun clearCurrentSession(): Int = synchronized(lock) {
        val activeSessionId = sessionContext.sessionId
        val before = entries.size
        entries.removeAll { it.event.testSessionId == activeSessionId }
        encodedBytes = entries.sumOf { it.bytes }
        before - entries.size
    }

    public fun droppedEventCount(): Long = synchronized(lock) { droppedEvents }

    private fun appendSafelyLocked(record: DiagnosticRecord, context: SessionContext): Boolean {
        return try {
            val redacted = DiagnosticRedactor.redact(record.details)
            val event = DiagnosticEvent(
                index = nextIndex,
                timestamp = timestamp(),
                platform = environment.platform,
                operatingSystem = environment.operatingSystem,
                applicationVersion = environment.applicationVersion,
                buildNumber = environment.buildNumber,
                gitCommitSha = environment.gitCommitSha,
                safeDeviceId = environment.safeDeviceId,
                testSessionId = context.sessionId,
                testId = context.testId,
                role = context.role,
                peerId = record.peerId?.let(::anonymizeIdentifier),
                connectionId = record.connectionId?.takeIf { it.matches(SAFE_ID) },
                transferId = record.transferId?.takeIf { it.matches(SAFE_ID) },
                category = stableName(record.category),
                eventName = stableName(record.eventName),
                severity = record.severity,
                currentState = record.currentState?.let(DiagnosticRedactor::redactText),
                previousState = record.previousState?.let(DiagnosticRedactor::redactText),
                protocolVersion = record.protocolVersion ?: configuration.protocolVersion,
                packetType = record.packetType?.let(::stableName),
                direction = record.direction,
                payloadSizeBytes = record.payloadSizeBytes,
                sequenceNumber = record.sequenceNumber,
                chunkNumber = record.chunkNumber,
                chunkCount = record.chunkCount,
                retryNumber = record.retryNumber,
                timeoutMillis = record.timeoutMillis,
                retryDelayMillis = record.retryDelayMillis,
                durationMillis = record.durationMillis,
                errorCode = record.errorCode?.let(::stableName),
                errorDescription = record.errorDescription?.let(DiagnosticRedactor::redactText),
                outcome = record.outcome,
                details = redacted.values,
                redactedFields = redacted.redactedFields
            )
            val json = JSON.encodeToString(event)
            val stored = StoredEvent(
                event,
                json,
                json.toByteArray(StandardCharsets.UTF_8).size + 1
            )
            entries += stored
            nextIndex++
            encodedBytes += stored.bytes
            enforceBounds()
            if (pendingSinkLines.size >= maxEvents || pendingSinkBytes + stored.bytes > maxEncodedBytes) {
                droppedEvents++
                return false
            }
            pendingSinkLines.addLast(PendingSinkLine(json, stored.bytes))
            pendingSinkBytes += stored.bytes
            if (!sinkDraining) {
                sinkDraining = true
                true
            } else {
                false
            }
        } catch (_: Throwable) {
            droppedEvents++
            false
        }
    }

    /**
     * One caller drains the append-ordered queue. The external sink is never
     * invoked under [lock], so a slow or re-entrant sink cannot deadlock the
     * recorder or reorder persisted JSONL.
     */
    private fun drainSinkIfOwner(owner: Boolean) {
        if (!owner) return
        while (true) {
            val line = synchronized(lock) {
                if (pendingSinkLines.isEmpty()) {
                    sinkDraining = false
                    null
                } else {
                    pendingSinkLines.removeFirst().also { pendingSinkBytes -= it.bytes }
                }
            } ?: return
            try {
                eventSink(line.json)
            } catch (_: Throwable) {
                synchronized(lock) { droppedEvents++ }
            }
        }
    }

    private fun enforceBounds() {
        while (entries.size > maxEvents || encodedBytes > maxEncodedBytes) {
            val removed = entries.removeAt(0)
            encodedBytes -= removed.bytes
            droppedEvents++
        }
        val sessions = entries.map { it.event.testSessionId }.distinct()
        if (sessions.size > maxSessions) {
            val removable = sessions.take(sessions.size - maxSessions).toSet()
            entries.removeAll { it.event.testSessionId in removable }
            encodedBytes = entries.sumOf { it.bytes }
        }
    }

    private data class SessionContext(
        val testId: String,
        val sessionId: String,
        val role: String,
        val startElapsedMillis: Long
    )

    private data class SummaryCapture(
        val events: List<DiagnosticEvent>,
        val activeContext: SessionContext,
        val droppedEventCount: Long
    )

    private data class StoredEvent(val event: DiagnosticEvent, val json: String, val bytes: Int)
    private data class PendingSinkLine(val json: String, val bytes: Int)
}

private fun transferSummary(
    transferId: String,
    sessionEvents: List<DiagnosticEvent>
): DiagnosticTransferSummary {
    val events = sessionEvents.filter { it.transferId == transferId }
    val sender = events.lastOrNull { it.eventName == DiagnosticEventNames.FILE_SENDER_HASH }
    val receiver = events.lastOrNull { it.eventName == DiagnosticEventNames.FILE_RECEIVER_HASH }
    val integrity = events.lastOrNull { it.eventName == DiagnosticEventNames.FILE_INTEGRITY_CHECKED }
    return DiagnosticTransferSummary(
        transferId = transferId,
        connectionIds = events.mapNotNull { it.connectionId }.distinct(),
        peerIds = events.mapNotNull { it.peerId }.distinct(),
        senderFileSizeBytes = sender?.payloadSizeBytes,
        receiverFileSizeBytes = receiver?.payloadSizeBytes,
        senderSha256 = sender?.details?.get("sha256"),
        receiverSha256 = receiver?.details?.get("sha256"),
        integrityMatch = integrity?.details?.get("match")?.toBooleanStrictOrNull()
    )
}

public object DiagnosticEventNames {
    public const val APPLICATION_STARTED: String = "application.started"
    public const val APPLICATION_SHUTDOWN: String = "application.shutdown"
    public const val TEST_MODE_ACTIVATED: String = "test.mode.activated"
    public const val TEST_SESSION_CREATED: String = "test.session.created"
    public const val TEST_SESSION_COMPLETED: String = "test.session.completed"
    public const val PEER_INITIALIZED: String = "peer.local.initialized"
    public const val DISCOVERY_STARTED: String = "discovery.started"
    public const val PEER_DISCOVERED: String = "discovery.peer.discovered"
    public const val PEER_LOST: String = "discovery.peer.lost"
    public const val DISCOVERY_STOPPED: String = "discovery.stopped"
    public const val CONNECTION_ATTEMPTED: String = "connection.attempted"
    public const val CONNECTION_AUTHENTICATED: String = "connection.authentication.succeeded"
    public const val CONNECTION_AUTHENTICATION_FAILED: String = "connection.authentication.failed"
    public const val CONNECTION_STATE_CHANGED: String = "connection.state.changed"
    public const val CONNECTION_DISCONNECTED: String = "connection.disconnected"
    public const val PROTOCOL_NEGOTIATED: String = "protocol.secure_v2.negotiated"
    public const val PROTOCOL_PACKET_SENT: String = "protocol.packet.sent"
    public const val PROTOCOL_PACKET_RECEIVED: String = "protocol.packet.received"
    public const val PROTOCOL_PACKET_REJECTED: String = "protocol.packet.rejected"
    public const val METADATA_CREATED: String = "metadata.envelope.created"
    public const val METADATA_SENT: String = "metadata.envelope.sent"
    public const val METADATA_RECEIVED: String = "metadata.envelope.received"
    public const val METADATA_VALIDATED: String = "metadata.envelope.validated"
    public const val METADATA_REJECTED: String = "metadata.envelope.rejected"
    public const val FILE_SELECTED: String = "file.selected"
    public const val FILE_GENERATED: String = "file.generated"
    public const val FILE_SENDER_HASH: String = "file.sender.sha256"
    public const val FILE_RECEIVER_HASH: String = "file.receiver.sha256"
    public const val FILE_INTEGRITY_CHECKED: String = "file.integrity.checked"
    public const val TRANSFER_PREPARED: String = "transfer.prepared"
    public const val TRANSFER_OFFER_RECEIVED: String = "transfer.offer.received"
    public const val TRANSFER_OFFER_ACCEPTED: String = "transfer.offer.accepted"
    public const val TRANSFER_OFFER_REJECTED: String = "transfer.offer.rejected"
    public const val TRANSFER_STARTED: String = "transfer.started"
    public const val TRANSFER_PROGRESS: String = "transfer.progress.milestone"
    public const val TRANSFER_RETRY: String = "transfer.retry.attempted"
    public const val TRANSFER_ACK: String = "transfer.acknowledgment"
    public const val TRANSFER_INTERRUPTED: String = "transfer.interrupted"
    public const val TRANSFER_CANCELLED: String = "transfer.cancelled"
    public const val TRANSFER_RESUMED: String = "transfer.resumed"
    public const val TRANSFER_DURABLE_COMMITTED: String = "transfer.durable.committed"
    public const val TRANSFER_COMPLETED: String = "transfer.completed"
    public const val TRANSFER_FAILED: String = "transfer.failed"
    public const val TEMP_FILE_CREATED: String = "storage.temporary_file.created"
    public const val TEMP_FILE_CLEANED: String = "storage.temporary_file.cleaned"
    public const val NETWORK_PATH_CHANGED: String = "network.path.changed"
    public const val APPLICATION_BACKGROUNDED: String = "application.backgrounded"
    public const val APPLICATION_FOREGROUNDED: String = "application.foregrounded"
    public const val RECOVERY_STARTED: String = "recovery.started"
    public const val RECOVERY_COMPLETED: String = "recovery.completed"
    public const val TIMEOUT_EXPIRED: String = "timeout.expired"
    public const val FAULT_INJECTED: String = "fault.injected"
    public const val SDK_LOG: String = "sdk.log"
    public const val TRANSPORT_LOG: String = "transport.log"
    public const val EVIDENCE_EXPORTED: String = "evidence.exported"
    public const val DIAGNOSTIC_FAILURE: String = "diagnostics.failure"
}

/**
 * Converts the SDK's decoded frame trace into stable structured packet
 * events. The trace contains metadata only (type/length/chunk/id), never
 * payload bytes.
 */
public object StructuredFrameTrace {
    private val frame = Regex(
        """^(TX|RX) type=([A-Z_]+) len=(\d+)B(?: chunk=(\d+)/(\d+) id=([A-Za-z0-9]+)(?: LAST)?)?(?: xfer=([A-Za-z0-9]+))?.*$"""
    )

    public fun record(
        recorder: DiagnosticRecorder,
        line: String,
        connectionId: String? = null
    ) {
        val match = frame.matchEntire(line.trim())
        if (match == null) {
            recorder.record(
                DiagnosticRecord(
                    connectionId = connectionId,
                    category = "protocol",
                    eventName = DiagnosticEventNames.PROTOCOL_PACKET_REJECTED,
                    severity = DiagnosticSeverity.WARNING,
                    errorCode = "UNPARSEABLE_FRAME_TRACE",
                    errorDescription = "Frame trace did not match the diagnostic schema"
                )
            )
            return
        }
        val (wireDirection, packetType, size, chunk, chunks, messageId, transferId) = match.destructured
        val direction = if (wireDirection == "TX") DiagnosticDirection.SENT else DiagnosticDirection.RECEIVED
        val eventName = when (packetType) {
            "FILE_COMMIT" -> DiagnosticEventNames.TRANSFER_ACK
            else -> if (direction == DiagnosticDirection.SENT) {
                DiagnosticEventNames.PROTOCOL_PACKET_SENT
            } else {
                DiagnosticEventNames.PROTOCOL_PACKET_RECEIVED
            }
        }
        recorder.record(
            DiagnosticRecord(
                connectionId = connectionId,
                transferId = transferId.ifEmpty { null },
                category = if (packetType.startsWith("FILE_")) "transfer" else "protocol",
                eventName = eventName,
                protocolVersion = recorder.configuration.protocolVersion,
                packetType = packetType,
                direction = direction,
                payloadSizeBytes = size.toLongOrNull(),
                chunkNumber = chunk.toIntOrNull(),
                chunkCount = chunks.toIntOrNull(),
                details = buildMap {
                    if (messageId.isNotEmpty()) put("messageId", messageId)
                    put("authenticated", "true")
                }
            )
        )
    }
}

/**
 * SDK logger adapter that keeps the original sink while adding bounded,
 * redacted structured events. Known failure/retry lines receive stable event
 * names; all other SDK lines are retained as `sdk.log`.
 */
public class StructuredSdkLogger(
    private val recorder: DiagnosticRecorder,
    private val delegate: P2pLogger = P2pLogger.NoOp,
    private val context: () -> Triple<String?, String?, String?> = { Triple(null, null, null) }
) : P2pLogger {
    override fun debug(message: String) = emit(DiagnosticSeverity.DEBUG, message, null) {
        delegate.debug(message)
    }

    override fun info(message: String) = emit(DiagnosticSeverity.INFO, message, null) {
        delegate.info(message)
    }

    override fun warn(message: String, throwable: Throwable?) =
        emit(DiagnosticSeverity.WARNING, message, throwable) {
            delegate.warn(message, throwable)
        }

    override fun error(message: String, throwable: Throwable?) =
        emit(DiagnosticSeverity.ERROR, message, throwable) {
            delegate.error(message, throwable)
        }

    private fun emit(
        severity: DiagnosticSeverity,
        message: String,
        throwable: Throwable?,
        delegateCall: () -> Unit
    ) {
        try {
            delegateCall()
        } catch (_: Throwable) {
            // A diagnostic delegate must never affect the SDK operation.
        }
        val lower = message.lowercase()
        val eventName = when {
            "authenticated envelope identity mismatch" in lower ->
                DiagnosticEventNames.CONNECTION_AUTHENTICATION_FAILED
            "authenticated protocol violation" in lower || "malformed" in lower ->
                DiagnosticEventNames.PROTOCOL_PACKET_REJECTED
            "reconnect: attempt=" in lower && "succeeded" in lower ->
                DiagnosticEventNames.RECOVERY_COMPLETED
            "reconnect: attempt=" in lower ->
                DiagnosticEventNames.TRANSFER_RETRY
            "timed out" in lower || "timeout" in lower ->
                DiagnosticEventNames.TIMEOUT_EXPIRED
            else -> DiagnosticEventNames.SDK_LOG
        }
        val (peerId, connectionId, transferId) = context()
        recorder.record(
            DiagnosticRecord(
                peerId = peerId,
                connectionId = connectionId,
                transferId = transferId,
                category = "sdk",
                eventName = eventName,
                severity = severity,
                errorCode = throwable?.javaClass?.simpleName?.uppercase(),
                errorDescription = throwable?.message,
                details = mapOf("message" to message)
            )
        )
    }
}

public object DiagnosticRedactor {
    private val sensitiveKey = Regex(
        "(?i)(password|passphrase|credential|secret|token|private.?key|signing|authorization|" +
            "cookie|ssid|bssid|payload|content|file.?name|peer.?name|device.?name|display.?name|" +
            "host(?:name)?|ip(?:v[46])?.?address|address|(?:^|[_.-])name(?:$|[_.-]))"
    )
    private val credentialValue = Regex(
        """(?i)\b(bearer\s+[A-Za-z0-9._~+/=-]+|gh[pousr]_[A-Za-z0-9_]+|AKIA[A-Z0-9]{16})\b"""
    )
    private val sensitiveAssignment = Regex(
        """(?i)(password|passphrase|credential|secret|token|ssid|bssid|payload|content|body|data|""" +
            """text|message|bytes|raw|file.?name|peer.?name|device.?name|display.?name|name|""" +
            """peer|device|host(?:name)?|ip(?:v[46])?.?address|address)\s*=\s*(?:"[^"]*"|'[^']*'|\S+)"""
    )
    private val ipv4 = Regex("""(?<![A-Za-z0-9])(?:\d{1,3}\.){3}\d{1,3}(?![A-Za-z0-9])""")
    private val ipv6Candidate = Regex(
        """(?i)(?<![A-Za-z0-9])(?:\[[0-9a-f:.%_-]+]|[0-9a-f:.]*:[0-9a-f:.%_-]+)(?![A-Za-z0-9])"""
    )
    private val macAddress = Regex(
        """(?i)(?<![0-9a-f])(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}(?![0-9a-f])"""
    )
    private val control = Regex("""[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]""")

    public data class Result(val values: Map<String, String>, val redactedFields: List<String>)

    public fun redact(values: Map<String, String>): Result {
        val redacted = mutableListOf<String>()
        val safe = values.toSortedMap().mapValues { (key, value) ->
            if (sensitiveKey.containsMatchIn(key)) {
                redacted += key
                "<redacted>"
            } else {
                redactText(value)
            }
        }
        return Result(safe, redacted.sorted())
    }

    public fun redactText(value: String): String {
        val bounded = value.replace(control, "�").take(1_024)
        val credentialsRemoved = credentialValue.replace(bounded, "<redacted-credential>")
        val payloadsRemoved = sensitiveAssignment.replace(credentialsRemoved) {
            "${it.groupValues[1]}=<redacted>"
        }
        val macsRemoved = macAddress.replace(payloadsRemoved) {
            "<redacted-mac:${anonymizeIdentifier(it.value)}>"
        }
        val ipv6Removed = ipv6Candidate.replace(macsRemoved) {
            if (isIpv6Literal(it.value)) {
                "<redacted-ip:${anonymizeIdentifier(it.value)}>"
            } else {
                it.value
            }
        }
        return ipv4.replace(ipv6Removed) {
            "<redacted-ip:${anonymizeIdentifier(it.value)}>"
        }
    }

    private fun isIpv6Literal(candidate: String): Boolean {
        val unwrapped = candidate.removePrefix("[").removeSuffix("]")
        val address = unwrapped.substringBefore('%')
        if (':' !in address) return false
        return runCatching { InetAddress.getByName(address) }.isSuccess
    }
}

public object DiagnosticEvidenceExporter {
    private val safeEvidenceFilename = Regex("[A-Za-z0-9._-]{1,96}")
    private val reservedEvidenceFilenames: Set<String> = setOf(
        "events.jsonl",
        "events.txt",
        "summary.json",
        "manual-evidence-required.txt",
        "checksums.sha256"
    )
    private val filenameTimestamp = DateTimeFormatter
        .ofPattern("yyyy-MM-dd'T'HHmmss")
        .withZone(ZoneId.of("UTC"))

    public fun export(
        recorder: DiagnosticRecorder,
        directory: File,
        manualEvidence: List<String> = DEFAULT_MANUAL_EVIDENCE,
        additionalFiles: Map<String, ByteArray> = emptyMap()
    ): File {
        check(directory.isDirectory || directory.mkdirs()) {
            "Could not create evidence directory"
        }
        val summary = recorder.summary(manualEvidence = manualEvidence)
        val baseName = evidenceFilename(
            summary.testId,
            summary.platform,
            summary.startTimestamp ?: isoTimestampNow(),
            summary.testSessionId
        )
        val target = File(directory, baseName)
        val temporary = File(directory, ".$baseName.part")
        val files = linkedMapOf(
            "events.jsonl" to recorder.jsonLines(summary.testSessionId).toByteArray(StandardCharsets.UTF_8),
            "events.txt" to recorder.readableText(summary.testSessionId).toByteArray(StandardCharsets.UTF_8),
            "summary.json" to JSON.encodeToString(summary).toByteArray(StandardCharsets.UTF_8),
            "manual-evidence-required.txt" to (
                manualEvidence.joinToString(separator = "\n", postfix = "\n") { "- $it" }
            ).toByteArray(StandardCharsets.UTF_8)
        ).apply {
            additionalFiles.toSortedMap().forEach { (name, bytes) ->
                require(name.matches(safeEvidenceFilename)) {
                    "Additional evidence filename is not safe"
                }
                require(name !in reservedEvidenceFilenames) {
                    "Additional evidence filename is reserved: $name"
                }
                put(name, bytes)
            }
        }
        val checksums = files.entries.joinToString(separator = "\n", postfix = "\n") {
            "${sha256(it.value)}  ${it.key}"
        }.toByteArray(StandardCharsets.UTF_8)

        try {
            ZipOutputStream(FileOutputStream(temporary)).use { zip ->
                (files + ("checksums.sha256" to checksums)).toSortedMap().forEach { (name, bytes) ->
                    zip.putNextEntry(ZipEntry(name).apply { time = 0L })
                    zip.write(bytes)
                    zip.closeEntry()
                }
            }
            try {
                Files.move(
                    temporary.toPath(),
                    target.toPath(),
                    StandardCopyOption.ATOMIC_MOVE,
                    StandardCopyOption.REPLACE_EXISTING
                )
            } catch (_: AtomicMoveNotSupportedException) {
                Files.move(
                    temporary.toPath(),
                    target.toPath(),
                    StandardCopyOption.REPLACE_EXISTING
                )
            }
            recorder.record(
                DiagnosticRecord(
                    category = "evidence",
                    eventName = DiagnosticEventNames.EVIDENCE_EXPORTED,
                    details = mapOf(
                        "filename" to target.name,
                        "packageSha256" to sha256(target.readBytes())
                    )
                )
            )
            return target
        } catch (failure: Throwable) {
            temporary.delete()
            recorder.record(
                DiagnosticRecord(
                    category = "evidence",
                    eventName = DiagnosticEventNames.DIAGNOSTIC_FAILURE,
                    severity = DiagnosticSeverity.ERROR,
                    errorCode = "EVIDENCE_EXPORT_FAILED",
                    errorDescription = failure.message,
                    outcome = DiagnosticOutcome.FAILURE
                )
            )
            throw failure
        }
    }

    public fun evidenceFilename(
        testId: String,
        platform: String,
        timestamp: String,
        sessionId: String
    ): String {
        val instant = runCatching { Instant.parse(timestamp) }.getOrElse { Instant.EPOCH }
        return listOf(
            filenameComponent(testId),
            filenameComponent(platform.lowercase()),
            filenameTimestamp.format(instant),
            filenameComponent(sessionId)
        ).joinToString("_") + ".zip"
    }

    /** Verification helper used by tests and sample-evidence generation. */
    public fun verifyChecksums(zip: File): Boolean = ZipFile(zip).use { archive ->
        val entries = buildList {
            val enumeration = archive.entries()
            while (enumeration.hasMoreElements()) add(enumeration.nextElement())
        }
        if (entries.any { it.isDirectory || !it.name.matches(safeEvidenceFilename) }) return false
        if (entries.map { it.name }.distinct().size != entries.size) return false
        val checksumEntries = entries.filter { it.name == "checksums.sha256" }
        if (checksumEntries.size != 1) return false
        val dataEntries = entries.filterNot { it.name == "checksums.sha256" }.associateBy { it.name }
        val lines = archive.getInputStream(checksumEntries.single()).bufferedReader().readLines()
        val manifest = linkedMapOf<String, String>()
        for (line in lines.filter { it.isNotBlank() }) {
            val split = line.split("  ", limit = 2)
            if (split.size != 2 || !split[0].matches(Regex("[0-9a-f]{64}"))) return false
            val name = split[1]
            if (!name.matches(safeEvidenceFilename) || name == "checksums.sha256") return false
            if (manifest.put(name, split[0]) != null) return false
        }
        if (manifest.keys != dataEntries.keys) return false
        manifest.all { (name, expected) ->
            sha256(archive.getInputStream(dataEntries.getValue(name)).readBytes()) == expected
        }
    }
}

public fun diagnosticJson(event: DiagnosticEvent): String = JSON.encodeToString(event)

/**
 * Bounded process-restart trail for test builds. The sink rotates before a
 * file exceeds [maxBytes] and keeps at most [maxFiles]. It is intentionally
 * opt-in and stores already-redacted JSON only.
 */
public class RollingJsonlFileSink(
    private val directory: File,
    private val maxBytes: Long = 2L * 1024L * 1024L,
    private val maxFiles: Int = 4
) : (String) -> Unit {
    private val lock: Any = Any()

    init {
        require(maxBytes >= 4_096L)
        require(maxFiles in 1..32)
    }

    override fun invoke(line: String) {
        synchronized(lock) {
            check(directory.isDirectory || directory.mkdirs()) {
                "Could not create diagnostic log directory"
            }
            val active = File(directory, ACTIVE_FILE)
            val bytes = (line + "\n").toByteArray(StandardCharsets.UTF_8)
            if (active.length() + bytes.size > maxBytes) rotate()
            FileOutputStream(active, true).use { it.write(bytes) }
        }
    }

    /** Returns only persisted records belonging to the selected test session. */
    public fun evidenceFiles(sessionId: String): Map<String, ByteArray> = synchronized(lock) {
        require(sessionId.matches(SAFE_ID))
        if (!directory.isDirectory) return@synchronized emptyMap()
        directory.listFiles()
            .orEmpty()
            .filter { it.isFile && it.name.matches(ROTATED_NAME) }
            .sortedBy { it.name }
            .mapNotNull { file ->
                val selected = file.useLines { lines ->
                    lines.mapNotNull { line ->
                        runCatching { JSON.decodeFromString<DiagnosticEvent>(line) }
                            .getOrNull()
                            ?.takeIf { it.testSessionId == sessionId }
                            ?.let { line }
                    }.toList()
                }
                if (selected.isEmpty()) {
                    null
                } else {
                    "process-${file.name}" to
                        (selected.joinToString(separator = "\n", postfix = "\n"))
                            .toByteArray(StandardCharsets.UTF_8)
                }
            }
            .toMap()
    }

    public fun clear() {
        synchronized(lock) {
            directory.listFiles()
                .orEmpty()
                .filter { it.isFile && it.name.matches(ROTATED_NAME) }
                .forEach { it.delete() }
        }
    }

    /** Removes only records carrying the exact already-validated session ID. */
    public fun clearSession(sessionId: String) {
        require(sessionId.matches(SAFE_ID))
        val marker = "\"testSessionId\":\"$sessionId\""
        synchronized(lock) {
            directory.listFiles()
                .orEmpty()
                .filter { it.isFile && it.name.matches(ROTATED_NAME) }
                .forEach { file ->
                    val retained = file.useLines { lines ->
                        lines.filterNot { marker in it }.toList()
                    }
                    val temporary = File(file.parentFile, ".${file.name}.rewrite")
                    FileOutputStream(temporary, false).bufferedWriter().use { writer ->
                        retained.forEach {
                            writer.appendLine(it)
                        }
                    }
                    if (!file.delete() || !temporary.renameTo(file)) {
                        temporary.delete()
                        error("Could not clear diagnostic session")
                    }
                }
        }
    }

    private fun rotate() {
        File(directory, "$ACTIVE_FILE.${maxFiles - 1}").delete()
        for (index in (maxFiles - 2) downTo 0) {
            val source = if (index == 0) {
                File(directory, ACTIVE_FILE)
            } else {
                File(directory, "$ACTIVE_FILE.$index")
            }
            if (source.exists()) source.renameTo(File(directory, "$ACTIVE_FILE.${index + 1}"))
        }
    }

    private companion object {
        const val ACTIVE_FILE: String = "diagnostic-events.jsonl"
        val ROTATED_NAME: Regex = Regex("""diagnostic-events\.jsonl(?:\.\d+)?""")
    }
}

public fun anonymizeIdentifier(value: String): String =
    "anon-" + sha256(value.toByteArray(StandardCharsets.UTF_8)).take(16)

public fun correlationConnectionId(
    testSessionId: String,
    localPeerId: String,
    remotePeerId: String
): String {
    val peers = listOf(anonymizeIdentifier(localPeerId), anonymizeIdentifier(remotePeerId)).sorted()
    return "conn-" + sha256("$testSessionId|${peers[0]}|${peers[1]}".toByteArray()).take(20)
}

public fun isoTimestampNow(): String = DateTimeFormatter.ISO_INSTANT.format(Instant.now())

public fun sha256(bytes: ByteArray): String =
    MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }

private fun DiagnosticEvent.matches(filter: DiagnosticFilter): Boolean {
    if (filter.testId != null && testId != filter.testId) return false
    if (filter.sessionId != null && testSessionId != filter.sessionId) return false
    if (filter.transferId != null && transferId != filter.transferId) return false
    if (filter.minimumSeverity != null && severity.ordinal < filter.minimumSeverity.ordinal) return false
    val needle = filter.search?.trim()?.lowercase().orEmpty()
    if (needle.isNotEmpty()) {
        val haystack = listOfNotNull(eventName, errorCode, peerId, packetType, errorDescription)
            .joinToString(" ")
            .lowercase()
        if (needle !in haystack) return false
    }
    return true
}

private fun normalizeTestId(value: String): String {
    val normalized = value.trim().uppercase()
    require(normalized.matches(TEST_ID)) {
        "Test ID must use 2-64 uppercase letters, digits, '_', or '-'"
    }
    return normalized
}

private fun stableName(value: String): String {
    val normalized = value.trim().lowercase().replace(Regex("[^a-z0-9_.-]+"), "_")
    return normalized.ifEmpty { "unknown" }.take(96)
}

private fun filenameComponent(value: String): String =
    value.replace(Regex("[^A-Za-z0-9._-]+"), "-").trim('-').ifEmpty { "unknown" }.take(80)

private fun sha256(value: String): String = sha256(value.toByteArray(StandardCharsets.UTF_8))

private val SAFE_ID = Regex("[A-Za-z0-9._-]{1,80}")
private val SAFE_ROLE = Regex("[A-Za-z0-9_-]{1,24}")
private val TEST_ID = Regex("[A-Z0-9_-]{2,64}")

public val DEFAULT_MANUAL_EVIDENCE: List<String> = listOf(
    "UI observation notes with the visible final state",
    "Screenshots of identifiers, progress, hashes, and final status",
    "Screen recording for lifecycle, interruption, or race tests",
    "External packet capture when required by the validation-plan row",
    "OS/device metadata and external system logs when required by the validation-plan row"
)

@OptIn(ExperimentalSerializationApi::class)
internal val JSON: Json = Json {
    encodeDefaults = true
    explicitNulls = true
    prettyPrint = false
    // Imported/rejected JSON must not leak into shareable evidence errors.
    exceptionsWithDebugInfo = false
}
