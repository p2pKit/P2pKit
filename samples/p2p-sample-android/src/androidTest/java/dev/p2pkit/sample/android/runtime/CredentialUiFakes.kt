package dev.p2pkit.sample.android.runtime

import android.Manifest
import android.app.Application
import android.content.Context
import android.content.pm.PackageManager
import android.os.Looper
import android.os.SystemClock
import androidx.activity.result.ActivityResultRegistry
import androidx.activity.result.ActivityResultRegistryOwner
import androidx.activity.result.contract.ActivityResultContract
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.app.ActivityOptionsCompat
import dev.p2pkit.core.AppId
import dev.p2pkit.core.FeatureState
import dev.p2pkit.core.NetworkPathStatus
import dev.p2pkit.core.NetworkProvisioningError
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.P2pState
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.permission.NoOpP2pPermissionManager
import dev.p2pkit.core.provisioning.JoinNetworkResult
import dev.p2pkit.core.provisioning.LocalNetworkConfig
import dev.p2pkit.core.provisioning.LocalNetworkResult
import dev.p2pkit.core.provisioning.NetworkProvisioningEvent
import dev.p2pkit.core.provisioning.NetworkProvisioningManager
import dev.p2pkit.core.provisioning.NetworkProvisioningState
import dev.p2pkit.core.provisioning.NetworkState
import dev.p2pkit.core.provisioning.UnsupportedNetworkProvisioningManager
import dev.p2pkit.core.provisioning.WifiCredentials
import dev.p2pkit.core.provisioning.WifiSecurityType
import java.io.File
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import org.json.JSONArray
import org.json.JSONObject

/** Modeled permission inputs only. This never grants an Android permission or starts native provisioning. */
internal class CredentialApplication(
    private val actual: Application,
    directory: File,
    private val token: String
) : Application() {
    var nearbyGranted = true
    var nearbyChecks = 0
        private set
    private val noBackup = File(directory, "no-backup").also { check(it.mkdir()) }
    private val cache = File(directory, "cache").also { check(it.mkdir()) }

    init { attachBaseContext(actual) }

    // The production reporter calls applicationContext again: returning the real app would lose this model.
    override fun getApplicationContext(): Context = this
    override fun getNoBackupFilesDir(): File = noBackup
    override fun getCacheDir(): File = cache
    override fun getSharedPreferences(name: String, mode: Int) =
        actual.getSharedPreferences("ui324-$token-$name", mode)

    override fun checkSelfPermission(permission: String): Int = when (permission) {
        Manifest.permission.NEARBY_WIFI_DEVICES -> {
            check(Looper.myLooper() == Looper.getMainLooper())
            nearbyChecks++
            if (nearbyGranted) PackageManager.PERMISSION_GRANTED else PackageManager.PERMISSION_DENIED
        }
        "android.permission.ACCESS_LOCAL_NETWORK" -> PackageManager.PERMISSION_GRANTED
        else -> super.checkSelfPermission(permission)
    }
}

/** Genuine registry and remembered-launcher delivery; onLaunch models the OS result, not a system dialog. */
internal class CredentialPermissionRegistry : ActivityResultRegistry(), ActivityResultRegistryOwner {
    override val activityResultRegistry: ActivityResultRegistry get() = this
    val requests = mutableListOf<Int>()
    val trace = JSONArray()
    var pending: Int? = null
        private set

    override fun <I, O> onLaunch(
        requestCode: Int,
        contract: ActivityResultContract<I, O>,
        input: I,
        options: ActivityOptionsCompat?
    ) {
        check(Looper.myLooper() == Looper.getMainLooper())
        check(contract is ActivityResultContracts.RequestPermission)
        check(input == Manifest.permission.NEARBY_WIFI_DEVICES && options == null && pending == null)
        pending = requestCode
        requests += requestCode
        trace.put(JSONObject().put("kind", "fakegrant-request").put("requestCode", requestCode)
            .put("elapsedNanos", SystemClock.elapsedRealtimeNanos()))
    }

    fun answer(granted: Boolean) {
        val code = checkNotNull(pending)
        check(dispatchResult(code, granted)) { "The real remembered launcher no longer owns its pending result" }
        pending = null
        trace.put(JSONObject().put("kind", "fakegrant-result").put("requestCode", code).put("granted", granted)
            .put("elapsedNanos", SystemClock.elapsedRealtimeNanos()))
    }

    fun assertUnregistered() {
        check(pending == null)
        requests.distinct().forEach { code ->
            check(!dispatchResult(code, false)) { "A completed result registration survived card disposal" }
        }
    }
}

/** Emits the real manager event AND returns Joined, including a same-call success/release conflation fixture. */
internal class CredentialNetworkFixture(private val ssid: String, private val secret: String) :
    NetworkProvisioningManager by UnsupportedNetworkProvisioningManager() {
    enum class Outcome { JOINED, JOINED_THEN_FAILED, FAILED_ONLY }
    var outcome = Outcome.JOINED
    override val state = MutableStateFlow<NetworkProvisioningState>(NetworkProvisioningState.Idle)
    override val networkState = MutableStateFlow<NetworkState>(NetworkState.Unknown)
    override val events = MutableSharedFlow<NetworkProvisioningEvent>(extraBufferCapacity = 4)
    val calls = JSONArray()
    var closes = 0
        private set

    override suspend fun startLocalNetwork(config: LocalNetworkConfig): LocalNetworkResult =
        error("Hosting is outside the credential fixture")

    override suspend fun stopLocalNetwork() = Unit

    override suspend fun joinLocalNetwork(credentials: WifiCredentials): JoinNetworkResult {
        check(Looper.myLooper() == Looper.getMainLooper() && events.subscriptionCount.value > 0)
        val call = JSONObject().put("elapsedNanos", SystemClock.elapsedRealtimeNanos())
            .put("protected", credentials.securityType == WifiSecurityType.WPA2)
            .put("ssidMatches", credentials.ssid == ssid).put("secretMatches", credentials.password?.reveal() == secret)
            .put("mode", outcome.name)
        calls.put(call)
        check(credentials.ssid == ssid && credentials.password?.reveal() == secret)
        check(credentials.securityType == WifiSecurityType.WPA2) { "An empty credential replay became OPEN" }
        val signals = JSONArray()
        val joined = NetworkState.ConnectedToWifi(ssid, listOf("192.0.2.24"))
        if (outcome != Outcome.FAILED_ONLY) {
            networkState.value = joined
            state.value = NetworkProvisioningState.JoinedNetwork
            check(events.tryEmit(NetworkProvisioningEvent.NetworkJoined(joined)))
            signals.put("NetworkJoined")
        }
        val failure = NetworkProvisioningError.JoinFailed("synthetic UI324 release")
        if (outcome != Outcome.JOINED) {
            networkState.value = NetworkState.NoNetwork
            state.value = NetworkProvisioningState.Failed(failure)
            check(events.tryEmit(NetworkProvisioningEvent.Failed(failure)))
            signals.put("JoinFailed")
        }
        val result = if (outcome == Outcome.FAILED_ONLY) JoinNetworkResult.Failed(failure)
        else JoinNetworkResult.Joined(joined)
        call.put("signals", signals).put("returned", result.javaClass.simpleName)
            .put("returnElapsedNanos", SystemClock.elapsedRealtimeNanos())
        return result
    }

    override suspend fun close() {
        closes++
        state.value = NetworkProvisioningState.Closed
        networkState.value = NetworkState.NoNetwork
    }
}

/** No identity store, sockets, radios, native manager, cryptographic peer or real permission grant. */
internal class CredentialKit(override val networkProvisioning: CredentialNetworkFixture) : P2pKit {
    override val appId = AppId("ui324-synthetic")
    override val localDeviceName = "ui324"
    override val localPeerId = PeerId("ui324-fixture")
    override val localFingerprint: PeerFingerprint? = null
    override val localPairingQr: String? = null
    override fun parsePeerPairingQr(value: String): PeerFingerprint? = null
    override val state = MutableStateFlow<P2pState>(P2pState.Idle)
    override val advertisingState = MutableStateFlow<FeatureState>(FeatureState.Idle)
    override val discoveryState = MutableStateFlow<FeatureState>(FeatureState.Idle)
    override val peers = MutableStateFlow<List<Peer>>(emptyList())
    override val incomingSessions = MutableSharedFlow<P2pSession>()
    override val sessions = MutableStateFlow<List<P2pSession>>(emptyList())
    override val networkPathStatus = MutableStateFlow<NetworkPathStatus>(NetworkPathStatus.Unknown)
    override val permissions = NoOpP2pPermissionManager()
    var stops = 0
        private set

    override suspend fun start(): Unit = error("The sample starts through its feature boundaries")
    override suspend fun startAdvertising() { advertisingState.value = FeatureState.Active }
    override suspend fun stopAdvertising() { advertisingState.value = FeatureState.Idle }
    override suspend fun startDiscovery() { discoveryState.value = FeatureState.Active; state.value = P2pState.Running }
    override suspend fun stopDiscovery() { discoveryState.value = FeatureState.Idle }
    override suspend fun connect(peer: Peer): P2pSession = error("No protocol peer in a credential UI fixture")
    override suspend fun connect(peer: Peer, expectedFingerprint: PeerFingerprint): P2pSession = connect(peer)
    override fun lastSeen(peerId: PeerId): Long? = null
    override fun notifyAppForegrounded() = Unit
    override fun notifyAppBackgrounded() {
        advertisingState.value = FeatureState.Idle
        discoveryState.value = FeatureState.Idle
    }
    override suspend fun stop() {
        stops++
        networkProvisioning.close()
        advertisingState.value = FeatureState.Idle
        discoveryState.value = FeatureState.Idle
        state.value = P2pState.Stopped
    }

    fun subscriptions(): List<Int> = listOf(state, advertisingState, discoveryState, peers, sessions, networkPathStatus)
        .map { it.subscriptionCount.value } + listOf(incomingSessions.subscriptionCount.value,
            networkProvisioning.state.subscriptionCount.value, networkProvisioning.events.subscriptionCount.value,
            networkProvisioning.networkState.subscriptionCount.value)
}
