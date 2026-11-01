package dev.p2pkit.sample.android.rpclab;

import android.os.ParcelFileDescriptor;
import android.system.ErrnoException;
import android.system.Os;
import android.system.OsConstants;
import android.system.StructStat;

import java.io.FileDescriptor;
import java.util.Arrays;

/**
 * Debug-only descriptor metadata and sealed control-record primitive.
 * The CLI uses one fixed app-data root and fixed output names. No identity key,
 * normal application payload, or production RPC/transport entry point is exposed.
 * API24's stat has no dereference option; reads use public Android descriptor APIs.
 */
public final class RpcLabFdStat {
    private RpcLabFdStat() { }

    public static void main(String[] arguments) {
        try {
            if (arguments.length == 3 && "read".equals(arguments[0])) {
                byte[] record = readRecord(arguments[1], arguments[2]);
                System.out.write(record);
                System.out.flush();
                return;
            }
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
        } catch (RecordMissing failure) {
            System.exit(44);
        } catch (RecordChanged failure) {
            System.exit(45);
        } catch (Exception failure) {
            // No descriptor values, paths, exception messages, or payloads.
            System.err.println("RPC descriptor metadata refused");
            System.exit(1);
        }
    }

    /** One ART launch for the complete sealed read, with all descriptors closed before publication. */
    public static byte[] readRecord(String runLabel, String name) throws Exception {
        return readRecordAt(".", runLabel, name);
    }

    // Package-private real-ART test seam. The CLI still has only one fixed application-data root.
    static byte[] readRecordAt(String appData, String runLabel, String name) throws Exception {
        if (!runLabel.matches("[a-z0-9-]{1,64}") || !Arrays.asList(
                "ready.txt", "failed.txt", "telemetry.txt", "closed.txt").contains(name)) {
            throw new IllegalArgumentException("Unknown owned record");
        }
        directory(appData, false);
        String base = appData + "/no_backup/rpc-capacity";
        String run = base + "/" + runLabel;
        directory(appData + "/no_backup", false);
        directory(base, true);
        directory(run, true);
        FileDescriptor seal = null;
        FileDescriptor data = null;
        try {
            StructStat sealBefore = null;
            if (!"telemetry.txt".equals(name)) {
                String path = run + "/.complete-" + name;
                sealBefore = metadata(path, true, true);
                seal = open(path);
                unchanged(sealBefore, Os.fstat(seal));
            }
            String path = run + "/" + name;
            StructStat before = metadata(path, false, "telemetry.txt".equals(name));
            data = open(path);
            unchanged(before, Os.fstat(data));
            byte[] bytes = new byte[16385];
            int size = 0;
            int read;
            while (size < bytes.length && (read = Os.read(data, bytes, size, bytes.length - size)) > 0) {
                size += read;
            }
            if (size != before.st_size || size == 0 || size > 16384) {
                throw new RecordChanged();
            }
            unchanged(before, Os.fstat(data));
            if (seal != null) {
                unchanged(sealBefore, Os.fstat(seal));
                unchanged(sealBefore, metadata(run + "/.complete-" + name, true, false));
            }
            return Arrays.copyOf(bytes, size);
        } finally {
            try { if (data != null) Os.close(data); }
            finally { if (seal != null) Os.close(seal); }
        }
    }

    private static FileDescriptor open(String path) throws ErrnoException {
        return Os.open(path, OsConstants.O_RDONLY | OsConstants.O_NOFOLLOW
                | OsConstants.O_NONBLOCK | OsConstants.O_CLOEXEC, 0);
    }

    private static void directory(String path, boolean privateMode) throws ErrnoException {
        StructStat value = Os.lstat(path);
        if (!OsConstants.S_ISDIR(value.st_mode) || value.st_uid != Os.getuid()
                || (privateMode && (value.st_mode & 07777) != 0700)) {
            throw new IllegalArgumentException("Owned directory required");
        }
    }

    private static StructStat metadata(String path, boolean seal, boolean optional) throws Exception {
        StructStat value;
        try { value = Os.lstat(path); }
        catch (ErrnoException failure) {
            if (optional && failure.errno == OsConstants.ENOENT) throw new RecordMissing();
            throw failure;
        }
        if (!OsConstants.S_ISREG(value.st_mode) || value.st_uid != Os.getuid()
                || (value.st_mode & 07777) != 0600 || value.st_nlink != 1
                || (seal ? value.st_size != 0 : value.st_size <= 0 || value.st_size > 16384)) {
            throw new IllegalArgumentException("Owned bounded regular record required");
        }
        return value;
    }

    private static void unchanged(StructStat before, StructStat after) throws RecordChanged {
        if (before.st_dev != after.st_dev || before.st_ino != after.st_ino || before.st_size != after.st_size
                || before.st_mtime != after.st_mtime || before.st_mode != after.st_mode
                || before.st_uid != after.st_uid || before.st_nlink != after.st_nlink) {
            throw new RecordChanged();
        }
    }

    private static final class RecordMissing extends Exception { }
    private static final class RecordChanged extends Exception { }

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
