package dev.p2pkit.sample.android.rpclab

import android.content.ClipData
import android.content.Context
import android.content.Intent
import android.system.Os
import android.system.OsConstants
import androidx.core.content.FileProvider
import dev.p2pkit.sample.rpc.RpcDeviceTestSession
import java.io.File
import java.io.FileOutputStream
import java.util.UUID

/** User-requested private sharing, without exporting identities, trust stores or deleting archived runs. */
internal fun exportRecentRpcEvidence(context: Context, session: RpcDeviceTestSession): Intent {
    val root = File(context.cacheDir, "test-evidence")
    check(root.isDirectory || root.mkdir())
    check(OsConstants.S_ISDIR(Os.lstat(root.path).st_mode))
    val directory = File(root, "rpc-" + UUID.randomUUID().toString())
    check(directory.mkdir())
    Os.chmod(directory.path, 0x1c0)
    val partial = File(directory, "recent-results.partial")
    check(partial.createNewFile())
    Os.chmod(partial.path, 0x180)
    FileOutputStream(partial).use { output ->
        session.writeRecentEvidence { line ->
            val bytes = (line + "\n").toByteArray(Charsets.UTF_8)
            try { output.write(bytes) } finally { bytes.fill(0) }
        }
        output.fd.sync()
    }
    val target = File(directory, "recent-results.jsonl")
    check(!target.exists() && partial.renameTo(target))
    val uri = FileProvider.getUriForFile(context, "${context.packageName}.test-evidence", target)
    return Intent(Intent.ACTION_SEND).apply {
        type = "application/x-ndjson"
        putExtra(Intent.EXTRA_STREAM, uri)
        clipData = ClipData.newRawUri("Private RPC test evidence", uri)
        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    }
}
