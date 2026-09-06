package dev.p2pkit.sample.diagnostics;

import java.io.RandomAccessFile;
import java.nio.channels.FileLock;

/** Separate real JVM process: verifies that contention has not released the first owner's OS lock. */
public final class DiagnosticDirectoryLockProbe {
    private DiagnosticDirectoryLockProbe() {}

    public static void main(String[] args) throws Exception {
        try (RandomAccessFile file = new RandomAccessFile(args[0], "rw")) {
            FileLock claim = file.getChannel().tryLock();
            if (claim == null) {
                System.out.println("BUSY");
            } else {
                try {
                    System.out.println("ACQUIRED");
                } finally {
                    claim.release();
                }
            }
        }
    }
}
