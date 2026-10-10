package dev.p2pkit.sample.rpc.desktop

/** The containing application may remove the RPC section only after [DesktopRpcCloseResult.Closed]. */
public enum class DesktopRpcCloseResult { Closed, Busy, Failed }

/** EDT-confined, one physical close attempt; no queued navigation and no retry of a failed vault close. */
internal class DesktopRpcPanelCloseOwner {
    private enum class State { Open, Closing, Closed, Failed }
    private var state = State.Open

    fun request(
        unlocking: Boolean,
        completed: (DesktopRpcCloseResult) -> Unit,
        begin: ((DesktopRpcCloseResult) -> Unit) -> Unit,
    ) {
        when {
            state == State.Closed -> completed(DesktopRpcCloseResult.Closed)
            state == State.Failed -> completed(DesktopRpcCloseResult.Failed)
            unlocking || state == State.Closing -> completed(DesktopRpcCloseResult.Busy)
            else -> {
                state = State.Closing
                try {
                    begin { result ->
                        if (state != State.Closing) return@begin
                        check(result != DesktopRpcCloseResult.Busy) { "Physical close must have a terminal result" }
                        state = if (result == DesktopRpcCloseResult.Closed) State.Closed else State.Failed
                        completed(result)
                    }
                } catch (failure: Exception) {
                    // Retain ownership even if close could not be scheduled. Never retry a partial physical close.
                    if (state != State.Closing) throw failure
                    state = State.Failed
                    completed(DesktopRpcCloseResult.Failed)
                }
            }
        }
    }
}
