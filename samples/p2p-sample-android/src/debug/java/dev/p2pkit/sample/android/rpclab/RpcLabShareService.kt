package dev.p2pkit.sample.android.rpclab

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import java.util.UUID

/** Debug-only OS execution support, not an RPC owner. A missing in-process lease can never restart a role. */
public class RpcLabShareService : Service() {
    private var owned: Request? = null
    private var ownedStart = 0

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val request = pending?.takeIf { it.id == intent?.getStringExtra(EXTRA_LEASE) }
        if (request == null) { stopSelfResult(startId); return START_NOT_STICKY }
        owned = request
        ownedStart = startId
        try {
            val notification = if (Build.VERSION.SDK_INT >= 26) {
                getSystemService(NotificationManager::class.java).createNotificationChannel(
                    NotificationChannel(CHANNEL, "RPC app-switch window", NotificationManager.IMPORTANCE_LOW),
                )
                Notification.Builder(this, CHANNEL)
            } else {
                @Suppress("DEPRECATION")
                Notification.Builder(this)
            }.setSmallIcon(android.R.drawable.stat_notify_sync_noanim)
                .setContentTitle("P2pKit RPC sharing window")
                .setContentText("Return to RPC within 25 seconds. The role stops automatically.")
                .setOngoing(true).setVisibility(Notification.VISIBILITY_PRIVATE).build()
            if (Build.VERSION.SDK_INT >= 34) {
                startForeground(NOTIFICATION, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_SHORT_SERVICE)
            } else startForeground(NOTIFICATION, notification)
        } catch (_: RuntimeException) {
            reject(request)
            stopSelfResult(startId)
        }
        return START_NOT_STICKY
    }

    override fun onTimeout(startId: Int) { if (ownedStart == startId) finishOwned() }
    override fun onTimeout(startId: Int, fgsType: Int) { if (ownedStart == startId) finishOwned() }
    override fun onTaskRemoved(rootIntent: Intent?) { finishOwned(); super.onTaskRemoved(rootIntent) }
    override fun onDestroy() { owned?.let(::reject); owned = null; super.onDestroy() }

    private fun finishOwned() { owned?.let(::reject); stopSelfResult(ownedStart) }

    private class Request(val id: String, val expired: () -> Unit)

    internal companion object {
        private const val EXTRA_LEASE = "rpc-app-switch-lease"
        private const val CHANNEL = "rpc-app-switch"
        private const val NOTIFICATION = 48124
        private var pending: Request? = null

        private fun reject(request: Request) {
            if (pending !== request) return
            pending = null
            request.expired()
        }

        /** All calls and Service callbacks are on the main thread; no role or invitation enters an Intent. */
        fun execution(context: Context): RpcLabAppSwitchWindow.Execution = object : RpcLabAppSwitchWindow.Execution {
            private val application = context.applicationContext
            private var request: Request? = null

            override fun begin(expired: () -> Unit): Boolean {
                if (pending != null || request != null) return false
                val next = Request(UUID.randomUUID().toString(), expired)
                request = next
                pending = next
                val intent = Intent(application, RpcLabShareService::class.java).putExtra(EXTRA_LEASE, next.id)
                return try {
                    if (Build.VERSION.SDK_INT >= 26) application.startForegroundService(intent)
                    else application.startService(intent)
                    true
                } catch (_: RuntimeException) {
                    if (pending === next) pending = null
                    request = null
                    false
                }
            }

            override fun end() {
                val previous = request ?: return
                request = null
                if (pending !== previous) return
                pending = null
                application.stopService(Intent(application, RpcLabShareService::class.java))
            }
        }
    }
}
