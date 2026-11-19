package dev.p2pkit.sample.rpc

import dev.p2pkit.core.AppId
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.rpc.RpcClient
import dev.p2pkit.rpc.RpcEndpoint
import dev.p2pkit.rpc.RpcHostConfiguration
import dev.p2pkit.rpc.RpcProcedure
import dev.p2pkit.rpc.RpcReply
import dev.p2pkit.rpc.RpcSelectedHost
import dev.p2pkit.rpc.RpcTrustPurpose
import dev.p2pkit.rpc.RpcTrustStore
import kotlinx.coroutines.delay
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withTimeout
import kotlinx.serialization.builtins.serializer

/** Private, explicitly imported companion plan. Parsing never grants trust. */
public class RpcMixedClientPlan private constructor(internal val fields: Map<String, String>) {
    public val runLabel: String get() = fields.getValue("runLabel")
    public val hostFingerprint: String get() = fields.getValue("hostPin")
    internal val physicalPin: PeerFingerprint get() = PeerFingerprint.parse(fields.getValue("physicalClientPin"))
    internal val nonce: String get() = fields.getValue("runNonce")
    internal val artifact: String get() = fields.getValue("physicalClientArtifactSha256")
    internal val selectedHost: RpcSelectedHost get() = RpcSelectedHost(PeerFingerprint.parse(hostFingerprint),
        RpcEndpoint(fields.getValue("hostAddress"), fields.getValue("hostPort").toInt()))

    internal fun verify(platform: String, installedSha256: String) {
        require(RpcPhoneBuildStamp.SOURCE_CLEAN && fields.getValue("hostSourceSha") == RpcPhoneLab.compiledSource)
        require(fields.getValue("physicalClientPlatform") == platform && artifact == installedSha256)
    }

    public companion object {
        @Throws(Exception::class)
        public fun parse(text: String): RpcMixedClientPlan {
            val fields = parseMobileRecord(text)
            require(fields.keys == setOf("schema", "scope", "runLabel", "runNonce", "hostSourceSha",
                "hostArtifactSha256", "hostPlatform", "hostPin", "hostAddress", "hostPort",
                "physicalClientPin", "physicalClientPlatform", "physicalClientArtifactSha256"))
            require(fields.getValue("schema") == "1" && fields.getValue("scope") == "physical-mixed-rpc-client")
            require(fields.getValue("runLabel").matches(Regex("[a-z0-9-]{1,48}")))
            require(fields.getValue("runNonce").matches(Regex("[a-f0-9]{64}")))
            require(fields.getValue("hostSourceSha").matches(Regex("[a-f0-9]{40}")))
            require(listOf("hostArtifactSha256", "physicalClientArtifactSha256").all {
                fields.getValue(it).matches(Regex("[a-f0-9]{64}"))
            })
            require(setOf(fields.getValue("hostPlatform"), fields.getValue("physicalClientPlatform")) ==
                setOf("Android", "Ios"))
            require(fields.getValue("hostAddress").matches(Regex("[0-9.]{7,15}")))
            require(fields.getValue("hostPort").matches(Regex("[1-9][0-9]{3,4}")) &&
                fields.getValue("hostPort").toInt() in 1024..65535)
            return RpcMixedClientPlan(fields).also { require(it.selectedHost.fingerprint != it.physicalPin) }
        }
    }
}

internal object MixedCapacityWire {
    const val GENERATED = 255
    const val PHONE_REPLIES = 20
    val control = procedure("qualification.mixed-control")
    val probe = procedure("qualification.mixed-probe")

    private fun procedure(key: String) = RpcProcedure(
        key, 1, String.serializer(), String.serializer(), String.serializer(),
        requestLimitBytes = 256, responseLimitBytes = 256, errorLimitBytes = 128,
    )
}

/** The live pin set comes from the actual authenticated Host, never from a caller declaration. */
internal class MixedCapacityHost(
    private val roster: Set<PeerFingerprint>,
    private val physical: PeerFingerprint,
    private val anchor: PeerFingerprint,
    private val nonce: String,
    private val artifact: String,
) {
    private val lock = Mutex()
    private val generators = hashSetOf<PeerFingerprint>()
    private var joined = false
    private var open = false
    private var verified = false
    private var released = false
    private var phoneReplies = 0
    private var connections: Map<PeerFingerprint, Long>? = null

    init { require(roster.size == 256 && physical in roster && anchor in roster && anchor != physical) }

    fun register(config: RpcHostConfiguration, live: () -> Map<PeerFingerprint, Long>) = with(config) {
        register(MixedCapacityWire.control, authorize = { it.fingerprint == physical || it.fingerprint == anchor }) {
                context, body -> control(checkNotNull(context.peer.fingerprint), body, live)
        }
        register(MixedCapacityWire.probe, authorize = { it.fingerprint in roster }) { context, body ->
            probe(checkNotNull(context.peer.fingerprint), body, live)
        }
    }

    suspend fun control(
        pin: PeerFingerprint, body: String, live: () -> Map<PeerFingerprint, Long>,
    ): RpcReply<String, String> =
        lock.withLock {
            val prefix = "$nonce/"
            if (!body.startsWith(prefix)) return@withLock reject()
            when (val action = body.removePrefix(prefix)) {
                "join/$artifact" -> if (pin == physical && !joined) {
                    joined = true
                    RpcReply.Success("joined")
                } else reject()
                "open" -> {
                    val cohort = live()
                    if (pin == anchor && joined && !open && cohort.keys == roster) {
                        connections = cohort.toMap()
                        open = true
                        RpcReply.Success("open")
                    } else reject()
                }
                "status" -> if (pin == physical && joined) {
                    RpcReply.Success(if (released) "released" else if (open) "open" else "waiting")
                } else reject()
                "confirmed" -> if (pin == physical && open && !verified && !released &&
                    phoneReplies == MixedCapacityWire.PHONE_REPLIES && live() == connections
                ) {
                    verified = true // The companion verified every decoded response before sending this.
                    RpcReply.Success("confirmed")
                } else reject()
                "inspect", "release" -> if (pin == anchor && open && !released && live() == connections) {
                    val complete = verified && generators.size == MixedCapacityWire.GENERATED
                    if (action == "release" && !complete) return@withLock reject()
                    if (action == "release") released = true
                    RpcReply.Success("${generators.size},$phoneReplies,$verified")
                } else reject()
                else -> reject()
            }
        }

    suspend fun probe(
        pin: PeerFingerprint, body: String, live: () -> Map<PeerFingerprint, Long>,
    ): RpcReply<String, String> =
        lock.withLock {
            if (!open || released || pin !in roster || live() != connections) return@withLock reject()
            if (pin == physical) {
                if (phoneReplies >= MixedCapacityWire.PHONE_REPLIES || body != "$nonce/phone/$phoneReplies") {
                    return@withLock reject()
                }
                phoneReplies++
            } else if (body != "$nonce/generator" || !generators.add(pin)) return@withLock reject()
            RpcReply.Success(body)
        }

    private fun reject(): RpcReply<String, String> = RpcReply.ApplicationError("unexpected-mixed-client-state")
}

/** The platform supplies an isolated protected store. This adaptor restricts it to one purpose and pin. */
internal class MixedClientTrust(private val store: RpcTrustStore, private val pin: PeerFingerprint) : RpcTrustStore {
    override suspend fun load(appId: AppId, purpose: RpcTrustPurpose): Set<PeerFingerprint> {
        require(appId == RpcCapacityContract.appId && purpose == RpcTrustPurpose.SelectedHosts)
        return store.load(appId, purpose)
    }

    override suspend fun replace(appId: AppId, purpose: RpcTrustPurpose, fingerprints: Set<PeerFingerprint>) {
        require(appId == RpcCapacityContract.appId && purpose == RpcTrustPurpose.SelectedHosts)
        require(fingerprints.isEmpty() || fingerprints == setOf(pin))
        store.replace(appId, purpose, fingerprints)
    }

    suspend fun retire() {
        val appId = RpcCapacityContract.appId
        val purpose = RpcTrustPurpose.SelectedHosts
        val current = load(appId, purpose)
        check(current.isEmpty() || current == setOf(pin))
        if (current.isNotEmpty()) replace(appId, purpose, emptySet())
        check(load(appId, purpose).isEmpty())
    }
}

internal class MixedCapacityClientRun(
    val plan: RpcMixedClientPlan, val trust: MixedClientTrust,
) {
    var replies = 0
        private set
    var released = false
        private set
    var closed = false

    suspend fun execute(client: RpcClient) = withTimeout(180_000) {
        check(!closed && replies == 0 && !released)
        client.connect(plan.selectedHost)
        suspend fun control(action: String): String {
            val reply = client.call(MixedCapacityWire.control, "${plan.nonce}/$action")
            check(reply is RpcReply.Success)
            return reply.value
        }
        check(control("join/${plan.artifact}") == "joined")
        while (true) {
            val status = control("status")
            if (status == "open") break
            check(status == "waiting")
            delay(500)
        }
        repeat(MixedCapacityWire.PHONE_REPLIES) {
            val payload = "${plan.nonce}/phone/$it"
            check(client.call(MixedCapacityWire.probe, payload) == RpcReply.Success(payload))
            replies++
        }
        check(control("confirmed") == "confirmed")
        while (true) {
            val status = control("status")
            if (status == "released") break
            check(status == "open")
            delay(500)
        }
        released = true
    }

    fun record(): String {
        check(closed)
        return encodeMobileRecord(plan.fields + mapOf("verifiedReplies" to replies.toString(),
            "released" to released.toString(), "runtimeClosed" to "true", "temporaryTrustRemoved" to "true"))
    }
}
