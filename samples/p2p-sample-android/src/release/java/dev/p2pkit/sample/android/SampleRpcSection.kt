package dev.p2pkit.sample.android

import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flowOf

/** Preserve the existing release variant; it has no RPC debug implementation or runtime dependency. */
internal const val sampleRpcAvailable = false

@Composable
internal fun SampleRpcSection(entry: SampleRpcSectionToken, onExit: () -> Unit) {
    // Defensive fallback; MainActivity never exposes this entry for the existing release variant.
    check(entry.lane == SampleProcessOwner.Lane.RpcSection)
    Text("RPC is not included in this build variant.")
    TextButton(onExit) { Text("Back to Room") }
}

internal fun sampleRpcRuntimeOccupied(): Boolean = false
internal fun sampleRpcRuntimeOccupancy(): Flow<Boolean> = flowOf(false)
