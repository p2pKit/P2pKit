package dev.p2pkit.sample.android.runtime;

import android.app.Activity;
import android.app.Instrumentation;
import android.os.Bundle;
import android.system.ErrnoException;
import android.system.Os;
import android.system.OsConstants;
import android.system.StructStat;
import dev.p2pkit.transport.lan.AndroidOsSocketOps;
import java.io.File;
import java.io.FileDescriptor;
import java.io.FileInputStream;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Actual kernel/JNI controls only. Never opens a profile, reads trust, or approves a LAN peer. */
public final class LanSocketRuntimeInstrumentation extends Instrumentation {
    private final AndroidOsSocketOps ops = AndroidOsSocketOps.INSTANCE;
    private long deadline;
    private String stage = "OPEN";

    @Override public void onCreate(Bundle arguments) { super.onCreate(arguments); start(); }

    @Override public void onStart() {
        Bundle result = new Bundle();
        try {
            deadline = System.nanoTime() + 10_000_000_000L;
            exercise();
            result.putString("stream", "P2PKIT_ANDROID_SOCKET_RUNTIME PASS controls=8\n");
            finish(Activity.RESULT_OK, result);
        } catch (Throwable failure) {
            // Fixed result only: no addresses, device identifiers, payloads or exception messages.
            result.putString("stream", "P2PKIT_ANDROID_SOCKET_RUNTIME FAIL stage=" + stage + "\n");
            finish(Activity.RESULT_CANCELED, result);
        }
    }

    private void exercise() throws Exception {
        FileDescriptor listener = ops.open(false);
        FileDescriptor accepted = null;
        try (Socket client = new Socket()) {
            stage = "LISTENER_FLAGS";
            verifyKernelFlags(listener);
            stage = "ACCEPT";
            ops.bind(listener, new InetSocketAddress(InetAddress.getByName("127.0.0.1"), 0));
            ops.listen(listener, 1);
            require(ops.accept(listener) == null); // The real listening socket is nonblocking.
            client.connect(ops.local(listener), 2_000);
            client.setSoTimeout(2_000);
            while (accepted == null) {
                withinDeadline();
                accepted = ops.accept(listener);
                if (accepted == null) ops.poll(listener, false, 100);
            }
            ops.configureAccepted(accepted);
            stage = "ACCEPTED_FLAGS";
            verifyKernelFlags(accepted); // Independent /proc view, not the JNI implementation's assertion.
            stage = "ROUND_TRIP";
            byte[] one = new byte[1];
            require(ops.read(accepted, one, 0, 1) == null);
            client.getOutputStream().write(65);
            Integer received = null;
            while (received == null) {
                withinDeadline();
                received = ops.read(accepted, one, 0, 1);
                if (received == null) ops.poll(accepted, false, 100);
            }
            require(received == 1 && one[0] == 65);
            require(Integer.valueOf(1).equals(ops.write(accepted, one, 0, 1)));
            require(client.getInputStream().read() == 65);
            // A non-reading peer must produce EAGAIN, not hold the descriptor lease indefinitely.
            byte[] block = new byte[65536];
            int written = 0;
            stage = "WRITE_BACKPRESSURE";
            while (true) {
                withinDeadline();
                Integer count = ops.write(accepted, block, 0, block.length);
                if (count == null) break;
                require(count > 0);
                written += count;
                require(written <= 16 * 1024 * 1024);
            }
            stage = "EOF";
            client.shutdownOutput();
            Integer eof = null;
            while (eof == null) {
                withinDeadline();
                eof = ops.read(accepted, one, 0, 1);
                if (eof == null) ops.poll(accepted, false, 100);
            }
            require(eof == 0);
        } finally {
            try { if (accepted != null) { ops.close(accepted); verifyClosed(accepted); } }
            finally { ops.close(listener); verifyClosed(listener); }
        }
    }

    private void verifyKernelFlags(FileDescriptor descriptor) throws Exception {
        StructStat original = Os.fstat(descriptor);
        File[] entries = new File("/proc/self/fd").listFiles();
        require(entries != null && entries.length <= 4096);
        int matches = 0;
        for (File entry : entries) {
            withinDeadline();
            StructStat candidate;
            try { candidate = Os.stat(entry.getPath()); }
            catch (ErrnoException missing) {
                if (missing.errno != OsConstants.ENOENT) throw missing;
                continue;
            }
            if (candidate.st_dev != original.st_dev || candidate.st_ino != original.st_ino) continue;
            matches++;
            byte[] info = new byte[4097];
            int size = 0;
            try (var input = new FileInputStream(new File("/proc/self/fdinfo", entry.getName()))) {
                while (size < info.length) {
                    int count = input.read(info, size, info.length - size);
                    if (count < 0) break;
                    size += count;
                }
            }
            require(size <= 4096);
            Matcher flags = Pattern.compile("(?m)^flags:\\s+([0-7]+)$")
                .matcher(new String(info, 0, size, StandardCharsets.US_ASCII));
            require(flags.find());
            long bits = Long.parseLong(flags.group(1), 8);
            require(!flags.find());
            require((bits & 0x80000L) != 0 && (bits & 0x800L) != 0); // Linux O_CLOEXEC and O_NONBLOCK.
        }
        require(matches == 1);
    }

    private void verifyClosed(FileDescriptor descriptor) throws Exception {
        require(!descriptor.valid());
        try { Os.fstat(descriptor); throw new AssertionError(); }
        catch (ErrnoException closed) { require(closed.errno == OsConstants.EBADF); }
    }

    private void withinDeadline() { require(System.nanoTime() < deadline); }
    private static void require(boolean value) { if (!value) throw new AssertionError(); }
}
