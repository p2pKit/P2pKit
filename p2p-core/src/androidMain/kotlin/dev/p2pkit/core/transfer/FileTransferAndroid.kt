package dev.p2pkit.core.transfer

import android.content.ContentResolver
import android.content.Context
import android.content.res.AssetFileDescriptor
import android.net.Uri
import android.provider.OpenableColumns
import dev.p2pkit.core.P2pSession
import kotlinx.io.Buffer
import kotlinx.io.RawSource
import kotlinx.io.asSource

/**
 * Send a file identified by a content [Uri] (typically from the Storage Access
 * Framework or a system file picker) to the peer.
 *
 * The transfer's metadata is resolved via [Context.getContentResolver]:
 *  - `name` ← [OpenableColumns.DISPLAY_NAME] (falls back to the URI's last path
 *    segment, or `"file"` if neither is available)
 *  - `sizeBytes` ← [OpenableColumns.SIZE]
 *  - `mimeType` ← [ContentResolver.getType]
 *
 * The underlying `InputStream` opened from the URI is closed automatically
 * when the returned [P2pFileTransfer] reaches any terminal state.
 *
 * @throws IllegalArgumentException if the URI cannot be opened or its size
 *   cannot be determined (Android Storage Access Framework occasionally
 *   returns `null` for documents the host app cannot stat — for those, save
 *   to a temp file first and use the JVM `sendFile(File)` overload).
 */
public suspend fun P2pSession.sendFile(context: Context, uri: Uri): P2pFileTransfer {
    val cr = context.contentResolver
    val descriptor = cr.openAssetFileDescriptor(uri, "r")
        ?: throw IllegalArgumentException("Cannot open URI for reading: $uri")
    val (displayName, queriedSize, mimeType) = try {
        queryUriMetadata(cr, uri)
    } catch (e: Throwable) {
        runCatching { descriptor.close() }
        throw e
    }
    val resolvedSize = try {
        resolveStableSize(uri, queriedSize, descriptor.length)
    } catch (e: Throwable) {
        runCatching { descriptor.close() }
        throw e
    }
    val source = try {
        AssetFileRawSource(descriptor, descriptor.createInputStream().asSource())
    } catch (e: Throwable) {
        runCatching { descriptor.close() }
        throw e
    }
    return try {
        sendFile(
            name = displayName,
            sizeBytes = resolvedSize,
            mimeType = mimeType,
            source = source
        )
    } catch (e: Throwable) {
        runCatching { source.close() }
        throw e
    }
}

internal fun resolveStableSize(uri: Uri, queriedSize: Long?, descriptorSize: Long): Long {
    require(queriedSize == null || queriedSize >= 0L) {
        "ContentResolver returned a negative SIZE for $uri: $queriedSize"
    }
    val openedSize = descriptorSize.takeIf { it >= 0L }
    if (queriedSize != null && openedSize != null && queriedSize != openedSize) {
        throw IllegalArgumentException(
            "Document size changed while opening $uri: metadata=$queriedSize descriptor=$openedSize"
        )
    }
    return openedSize ?: queriedSize ?: throw IllegalArgumentException(
        "Cannot determine size for $uri from either the opened descriptor or SIZE metadata. " +
            "Save the document to a temporary File first."
    )
}

private class AssetFileRawSource(
    private val descriptor: AssetFileDescriptor,
    private val delegate: RawSource
) : RawSource {
    override fun readAtMostTo(sink: Buffer, byteCount: Long): Long =
        delegate.readAtMostTo(sink, byteCount)

    override fun close() {
        try {
            delegate.close()
        } finally {
            descriptor.close()
        }
    }
}

private data class UriMetadata(val displayName: String, val sizeBytes: Long?, val mimeType: String?)

private fun queryUriMetadata(cr: ContentResolver, uri: Uri): UriMetadata {
    val fallbackName = uri.lastPathSegment?.substringAfterLast('/')?.takeIf { it.isNotBlank() } ?: "file"
    val mimeType: String? = cr.getType(uri)
    var displayName = fallbackName
    var sizeBytes: Long? = null
    cr.query(
        uri,
        arrayOf(OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE),
        null,
        null,
        null
    )?.use { cursor ->
        if (cursor.moveToFirst()) {
            val nameIdx = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
            if (nameIdx >= 0 && !cursor.isNull(nameIdx)) {
                cursor.getString(nameIdx)?.let { if (it.isNotBlank()) displayName = it }
            }
            val sizeIdx = cursor.getColumnIndex(OpenableColumns.SIZE)
            if (sizeIdx >= 0 && !cursor.isNull(sizeIdx)) {
                sizeBytes = cursor.getLong(sizeIdx)
            }
        }
    }
    return UriMetadata(displayName, sizeBytes, mimeType)
}
