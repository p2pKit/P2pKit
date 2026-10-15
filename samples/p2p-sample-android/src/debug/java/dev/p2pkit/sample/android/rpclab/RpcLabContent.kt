package dev.p2pkit.sample.android.rpclab

import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import dev.p2pkit.sample.android.SampleRpcSectionToken

/** The maintained app section owns one lifecycle and leave policy; shortcuts route through MainActivity. */
@Composable
internal fun RpcLabContent(activity: ComponentActivity, entry: SampleRpcSectionToken, onExit: () -> Unit) {
    val currentExit by rememberUpdatedState(onExit)
    var controller by remember(activity, entry) { mutableStateOf<RpcLabController?>(null) }
    DisposableEffect(activity, entry) {
        val owned = RpcLabController(activity, entry) { currentExit() }
        controller = owned
        // LifecycleRegistry immediately delivers current start/resume; no synthetic foreground episode.
        activity.lifecycle.addObserver(owned)
        onDispose {
            activity.lifecycle.removeObserver(owned)
            owned.detach()
            if (controller === owned) controller = null
        }
    }
    // Always consume while this entry is visible, including initialization and cleanup. Predictive Back
    // must not reveal the Room/Activity behind an unretired RPC owner.
    BackHandler { controller?.requestLeave() }
    RpcLabTheme { controller?.Content() }
}
