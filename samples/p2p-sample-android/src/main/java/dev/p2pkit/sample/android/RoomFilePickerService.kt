package dev.p2pkit.sample.android

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import androidx.core.content.ContextCompat
import java.util.UUID

internal fun interface RoomFilePickerExecution {
    fun start(onLost: () -> Unit): AutoCloseable?
}

/** Main-thread-only OS execution lease. The service never owns a session or a document. */
class RoomFilePickerService : Service() {
    private var owner: Request? = null
    private var ownerStartId = 0

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val request = pending?.takeIf { it.id == intent?.getStringExtra(EXTRA_ID) }
        if (request == null && owner != null) return START_NOT_STICKY
        try {
            // Even a request cancelled before onStartCommand must satisfy the foreground
            // start transaction before it can retire. It cannot restore a ViewModel or session.
            val builder = if (Build.VERSION.SDK_INT >= 26) {
                getSystemService(NotificationManager::class.java).createNotificationChannel(
                    NotificationChannel(CHANNEL, "File selection", NotificationManager.IMPORTANCE_LOW)
                )
                Notification.Builder(this, CHANNEL)
            } else {
                @Suppress("DEPRECATION")
                Notification.Builder(this)
            }
            val notification = builder
                .setSmallIcon(android.R.drawable.stat_notify_sync_noanim)
                .setContentTitle("P2pKit file selection")
                .setContentText("Keeping the connection open while you choose a file.")
                .setOngoing(true)
                .setVisibility(Notification.VISIBILITY_PRIVATE)
                .build()
            if (Build.VERSION.SDK_INT >= 34) {
                startForeground(NOTIFICATION, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_SHORT_SERVICE)
            } else {
                startForeground(NOTIFICATION, notification)
            }
            if (request == null) {
                stopSelfResult(startId)
            } else {
                owner = request
                ownerStartId = startId
                request.started = true
            }
        } catch (_: RuntimeException) {
            request?.let(::revoke)
            stopSelfResult(startId)
        }
        return START_NOT_STICKY
    }

    override fun onTimeout(startId: Int) { if (startId == ownerStartId) finish() }

    override fun onTimeout(startId: Int, fgsType: Int) { if (startId == ownerStartId) finish() }

    override fun onTaskRemoved(rootIntent: Intent?) {
        if (owner != null) finish()
        super.onTaskRemoved(rootIntent)
    }

    override fun onDestroy() {
        owner?.let(::revoke)
        owner = null
        super.onDestroy()
    }

    private fun finish() {
        owner?.let(::revoke)
        stopSelfResult(ownerStartId)
    }

    private class Request(val id: String, val onLost: () -> Unit, var started: Boolean = false)

    internal companion object {
        private const val EXTRA_ID = "file-picker-lease"
        private const val CHANNEL = "room-file-picker"
        private const val NOTIFICATION = 48125
        private var pending: Request? = null

        private fun revoke(request: Request) {
            if (pending !== request) return
            pending = null
            request.onLost()
        }

        fun execution(context: Context): RoomFilePickerExecution = RoomFilePickerExecution { onLost ->
            if (pending != null) return@RoomFilePickerExecution null
            val application = context.applicationContext
            val request = Request(UUID.randomUUID().toString(), onLost)
            val intent = Intent(application, RoomFilePickerService::class.java).putExtra(EXTRA_ID, request.id)
            pending = request
            try {
                ContextCompat.startForegroundService(application, intent)
                AutoCloseable {
                    if (pending === request) {
                        pending = null
                        if (request.started) application.stopService(intent)
                    }
                }
            } catch (_: RuntimeException) {
                pending = null
                null
            }
        }
    }
}
