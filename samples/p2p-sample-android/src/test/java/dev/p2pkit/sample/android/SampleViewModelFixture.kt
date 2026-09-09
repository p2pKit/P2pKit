package dev.p2pkit.sample.android

import android.app.Application
import android.content.Context
import android.content.ContextWrapper
import androidx.lifecycle.ViewModelStore
import androidx.lifecycle.viewModelScope
import dev.p2pkit.core.AppId
import dev.p2pkit.core.FeatureState
import dev.p2pkit.core.NetworkPathStatus
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.P2pState
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.permission.P2pPermission
import dev.p2pkit.core.permission.P2pPermissionManager
import dev.p2pkit.core.provisioning.UnsupportedNetworkProvisioningManager
import java.io.File
import java.nio.file.Files
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.Job
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.setMain
import org.robolectric.RuntimeEnvironment

@OptIn(ExperimentalCoroutinesApi::class)
internal suspend fun TestScope.withSampleViewModel(block: suspend SampleViewModelFixture.() -> Unit) {
    val dispatcher = StandardTestDispatcher(testScheduler)
    val application = RuntimeEnvironment.getApplication()
    val fixture = SampleViewModelFixture()
    val store = ViewModelStore()
    var directory: File? = null
    var vmJob: Job? = null
    var observer: Job? = null
    Dispatchers.setMain(dispatcher)
    try {
        val ownedDirectory = Files.createTempDirectory("sample-action-test-").toFile()
        directory = ownedDirectory
        val context = object : ContextWrapper(application) {
            override fun getApplicationContext(): Context = this
            override fun getNoBackupFilesDir(): File = File(ownedDirectory, "no-backup").apply { mkdirs() }
            override fun getCacheDir(): File = File(ownedDirectory, "cache").apply { mkdirs() }
            override fun getSharedPreferences(name: String, mode: Int) =
                application.getSharedPreferences(ownedDirectory.name, mode)
        }
        val host = object : Application() {
            override fun getApplicationContext(): Context = context
        }
        val vm = P2pKitViewModel(host, fixture, dispatcher)
        fixture.vm = vm
        fixture.clearViewModel = store::clear
        store.put("sample", vm)
        vmJob = requireNotNull(vm.viewModelScope.coroutineContext[Job])
        observer = backgroundScope.launch(dispatcher) {
            vm.runAdmission.collect { fixture.admission = it }
        }
        vm.notifyForegrounded()
        runCurrent()
        block(fixture)
    } finally {
        try {
            fixture.barriers.forEach { it.complete(Unit) }
            fixture.room.stopFailure = null
            fixture.smoke.stopFailure = null
            store.clear()
            runCurrent()
            observer?.cancelAndJoin()
            assertTrue(vmJob?.isCompleted != false, "ViewModel work must finish before retiring its test dispatcher")
            assertEquals(0, fixture.room.peers.subscriptionCount.value)
            assertEquals(0, fixture.smoke.peers.subscriptionCount.value)
        } finally {
            try {
                directory?.let {
                    application.deleteSharedPreferences(it.name)
                    assertTrue(it.deleteRecursively(), "fixture-owned diagnostic files must be removed")
                }
            } finally {
                Dispatchers.resetMain()
            }
        }
    }
}

internal class SampleViewModelFixture : SampleKitFactories {
    lateinit var vm: P2pKitViewModel
    lateinit var admission: SampleRunAdmission
    lateinit var clearViewModel: () -> Unit
    val room = SampleFakeKit("room")
    val smoke = SampleFakeKit("smoke")
    val barriers = mutableListOf<CompletableDeferred<Unit>>()
    var roomCreations = 0
    var smokeCreations = 0

    fun barrier(): CompletableDeferred<Unit> = CompletableDeferred<Unit>().also { barriers += it }

    override fun createRoomKit(): P2pKit {
        roomCreations++
        return room
    }

    override fun createSmokeKit(): P2pKit {
        smokeCreations++
        return smoke
    }
}

/** Inert boundary stand-in: no platform identity, sockets, cryptography or permission prompts. */
internal class SampleFakeKit(name: String) : P2pKit {
    override val appId = AppId("sample-action-fixture")
    override val localDeviceName = name
    override val localPeerId = PeerId("local-$name")
    override val localFingerprint: PeerFingerprint? = null
    override val localPairingQr: String? = null
    override fun parsePeerPairingQr(value: String): PeerFingerprint? = null
    override val state = MutableStateFlow<P2pState>(P2pState.Idle)
    override val advertisingState = MutableStateFlow<FeatureState>(FeatureState.Idle)
    override val discoveryState = MutableStateFlow<FeatureState>(FeatureState.Idle)
    override val peers = MutableStateFlow<List<Peer>>(emptyList())
    override val incomingSessions = MutableSharedFlow<P2pSession>()
    override val sessions = MutableStateFlow<List<P2pSession>>(emptyList())
    override val permissions = SampleFakePermissions()
    override val networkProvisioning = UnsupportedNetworkProvisioningManager()
    override val networkPathStatus = MutableStateFlow<NetworkPathStatus>(NetworkPathStatus.Unknown)
    var advertiseCalls = 0
    var discoveryCalls = 0
    var stopCalls = 0
    var stopAdvertisingCalls = 0
    var stopDiscoveryCalls = 0
    var connectCalls = 0
    var beforeAdvertising: suspend () -> Unit = {}
    var beforeDiscovery: suspend () -> Unit = {}
    var beforeStop: suspend () -> Unit = {}
    var advertisingFailure: Throwable? = null
    var stopFailure: Throwable? = null

    override suspend fun start() { error("sample uses feature startup") }
    override suspend fun startAdvertising() {
        advertiseCalls++
        beforeAdvertising()
        advertisingFailure?.let { throw it }
        advertisingState.value = FeatureState.Active
        state.value = P2pState.Running
    }
    override suspend fun stopAdvertising() {
        stopAdvertisingCalls++
        advertisingState.value = FeatureState.Idle
    }
    override suspend fun startDiscovery() {
        discoveryCalls++
        beforeDiscovery()
        discoveryState.value = FeatureState.Active
    }
    override suspend fun stopDiscovery() {
        stopDiscoveryCalls++
        discoveryState.value = FeatureState.Idle
    }
    override suspend fun connect(peer: Peer): P2pSession {
        connectCalls++
        error("synthetic dial boundary reached; fixture does not create a network session")
    }
    override suspend fun connect(peer: Peer, expectedFingerprint: PeerFingerprint): P2pSession = connect(peer)
    override fun lastSeen(peerId: PeerId): Long? = null
    override fun notifyAppBackgrounded() = Unit
    override fun notifyAppForegrounded() = Unit
    override suspend fun stop() {
        stopCalls++
        beforeStop()
        stopFailure?.let { throw it }
        advertisingState.value = FeatureState.Idle
        discoveryState.value = FeatureState.Idle
        state.value = P2pState.Stopped
    }
}

internal class SampleFakePermissions : P2pPermissionManager {
    var missing: List<P2pPermission> = emptyList()
    var checks = 0
    var beforeCheck: suspend () -> Unit = {}
    var failure: Throwable? = null
    override suspend fun requiredPermissions(): List<P2pPermission> = listOf(P2pPermission.LocalNetwork)
    override suspend fun missingPermissions(): List<P2pPermission> {
        checks++
        beforeCheck()
        failure?.let { throw it }
        return missing
    }
    override suspend fun hasRequiredPermissions(): Boolean = missingPermissions().isEmpty()
}
