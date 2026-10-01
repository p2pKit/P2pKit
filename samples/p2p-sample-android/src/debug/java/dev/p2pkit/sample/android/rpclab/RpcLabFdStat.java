package dev.p2pkit.sample.android.rpclab;

import android.os.ParcelFileDescriptor;
import android.system.ErrnoException;
import android.system.Os;
import android.system.OsConstants;
import android.system.StructStat;

import java.io.FileDescriptor;

/**
 * Debug-only run-as metadata primitive. API24's stat has no dereference option.
 * Uses public Android APIs on one explicitly inherited descriptor, never a path,
 * payload, key, authorization decision, or production RPC/transport entry point.
 */
public final class RpcLabFdStat {
    private RpcLabFdStat() { }

    public static void main(String[] arguments) {
        try {
            if (arguments.length != 1) {
                throw new IllegalArgumentException("One fixed metadata format is required");
            }
            // Dup, inspect, and close only this command's explicitly inherited
            // descriptor. The parent keeps its original open file description.
            String value;
            try (ParcelFileDescriptor descriptor = ParcelFileDescriptor.fromFd(5)) {
                value = format(descriptor.getFileDescriptor(), arguments[0]);
            }
            System.out.println(value); // Never publish metadata before duplicate closure succeeds.
        } catch (Exception failure) {
            // No descriptor values, paths, exception messages, or payloads.
            System.err.println("RPC descriptor metadata refused");
            System.exit(1);
        }
    }

    public static String format(FileDescriptor descriptor, String format) throws ErrnoException {
        if (!"identity".equals(format) && !"record".equals(format)) {
            throw new IllegalArgumentException("Unknown metadata format");
        }
        StructStat metadata = Os.fstat(descriptor);
        if (!OsConstants.S_ISREG(metadata.st_mode)) {
            throw new IllegalArgumentException("Regular descriptor required");
        }
        String identity = metadata.st_dev + ":" + metadata.st_ino;
        if ("identity".equals(format)) {
            return identity;
        }
        // Exactly stat's %d:%i:%s:%Y:%a:%u:%h, including special mode bits.
        return identity + ":" + metadata.st_size + ":" + metadata.st_mtime + ":"
            + Integer.toOctalString(metadata.st_mode & 07777) + ":" + metadata.st_uid + ":" + metadata.st_nlink;
    }
}
