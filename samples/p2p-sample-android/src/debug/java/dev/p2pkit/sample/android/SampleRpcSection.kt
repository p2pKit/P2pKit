package dev.p2pkit.sample.android

import android.content.Context
import android.content.ContextWrapper
import androidx.activity.ComponentActivity
import androidx.compose.runtime.Composable
import androidx.compose.ui.platform.LocalContext
import dev.p2pkit.sample.android.rpclab.RpcLabContent
import dev.p2pkit.sample.android.rpclab.RpcLabProcessRuntime
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.map

/** Foundation distributes assembleDebug: RPC is a section of this APK's existing MainActivity. */
internal const val sampleRpcAvailable = true

@Composable
internal fun SampleRpcSection(entry: SampleRpcSectionToken, onExit: () -> Unit) {
    val context = LocalContext.current
    val activity = generateSequence(context) { current: Context -> (current as? ContextWrapper)?.baseContext }
        .filterIsInstance<ComponentActivity>().first()
    RpcLabContent(activity, entry, onExit)
}

/** The runtime owner outlives Activity/VM destruction until its existing retained cleanup really succeeds. */
internal fun sampleRpcRuntimeOccupied(): Boolean = RpcLabProcessRuntime.owner.occupied

internal fun sampleRpcRuntimeOccupancy(): Flow<Boolean> =
    RpcLabProcessRuntime.owner.state.map { it != null }.distinctUntilChanged()
