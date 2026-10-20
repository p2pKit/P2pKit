/* Test-only TCP option measurement; not P2pKit protocol or security qualification. */
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.util.Arrays;
import java.util.concurrent.atomic.AtomicReference;

public final class TcpNoDelayLatency {
    private static final int MAGIC = 0x5032504c;
    private static final int WARMUP = 8;
    private static final int SAMPLES = 32;
    private static final int SOCKET_MILLIS = 2000;
    private static final int BLOCKS = 8;
    private static final boolean[] OPTIONS = {false, true, true, false};

    private static void require(boolean value, String message) throws IOException {
        if (!value) throw new IOException(message);
    }

    private static byte[] frame(int sequence, boolean pong) {
        byte[] bytes = new byte[40];
        bytes[0] = 'P'; bytes[1] = 'I'; bytes[2] = 'N'; bytes[3] = (byte) (pong ? 'O' : 'G');
        for (int n = 0; n < 4; n++) bytes[4 + n] = (byte) (sequence >>> (24 - 8 * n));
        for (int n = 8; n < bytes.length; n++) bytes[n] = (byte) n;
        return bytes;
    }

    private static void serve(ServerSocket listener) throws Exception {
        listener.setSoTimeout(15_000);
        for (int block = 0; block < BLOCKS; block++) {
            try (Socket socket = listener.accept()) {
                socket.setSoTimeout(SOCKET_MILLIS);
                DataInputStream input = new DataInputStream(socket.getInputStream());
                DataOutputStream output = new DataOutputStream(socket.getOutputStream());
                require(input.readInt() == MAGIC && input.readInt() == block, "Wrong measurement binding");
                boolean noDelay = OPTIONS[block % 4];
                require(input.readUnsignedByte() == (noDelay ? 1 : 0), "Wrong option order");
                socket.setTcpNoDelay(noDelay);
                require(socket.getTcpNoDelay() == noDelay, "Accepted option readback differs");
                output.writeByte(socket.getTcpNoDelay() ? 1 : 0);
                output.flush();
                for (int sequence = 0; sequence < WARMUP + SAMPLES; sequence++) {
                    byte[] bytes = new byte[40];
                    input.readFully(bytes);
                    require(Arrays.equals(bytes, frame(sequence, false)), "PING bytes differ");
                    output.write(frame(sequence, true));
                    output.flush();
                }
                // Actual half-close and EOF are separate from all measured exchanges.
                require(input.read() == -1, "Unexpected trailing input");
                socket.shutdownOutput();
            }
        }
    }

    private static String measure(String host, int port) throws Exception {
        StringBuilder results = new StringBuilder("[");
        for (int block = 0; block < BLOCKS; block++) {
            boolean noDelay = OPTIONS[block % 4];
            boolean split = block >= 4;
            try (Socket socket = new Socket()) {
                socket.setSoTimeout(SOCKET_MILLIS);
                socket.connect(new InetSocketAddress(host, port), SOCKET_MILLIS);
                socket.setTcpNoDelay(noDelay);
                require(socket.getTcpNoDelay() == noDelay, "Dialed option readback differs");
                DataInputStream input = new DataInputStream(socket.getInputStream());
                DataOutputStream output = new DataOutputStream(socket.getOutputStream());
                output.writeInt(MAGIC); output.writeInt(block); output.writeByte(noDelay ? 1 : 0); output.flush();
                int acceptedOption = input.readUnsignedByte();
                require(acceptedOption == (noDelay ? 1 : 0), "Remote accepted option readback differs");
                if (block > 0) results.append(',');
                results.append("{\"block\":").append(block).append(",\"noDelay\":").append(noDelay)
                    .append(",\"acceptedNoDelay\":").append(acceptedOption == 1)
                    .append(",\"writeShape\":\"").append(split ? "split-4-36" : "coalesced-40")
                    .append("\",\"nanoseconds\":[");
                for (int sequence = 0; sequence < WARMUP + SAMPLES; sequence++) {
                    byte[] ping = frame(sequence, false);
                    byte[] pong = new byte[40];
                    long began = System.nanoTime();
                    if (split) {
                        output.write(ping, 0, 4); output.flush();
                        output.write(ping, 4, ping.length - 4); output.flush();
                    } else {
                        output.write(ping); output.flush();
                    }
                    input.readFully(pong);
                    long elapsed = System.nanoTime() - began;
                    require(elapsed > 0 && Arrays.equals(pong, frame(sequence, true)), "PONG or clock differs");
                    if (sequence >= WARMUP) {
                        if (sequence > WARMUP) results.append(',');
                        results.append(elapsed);
                    }
                }
                socket.shutdownOutput();
                require(input.read() == -1, "Responder did not half-close naturally");
                results.append("]}");
            }
        }
        return results.append(']').toString();
    }

    public static void main(String[] args) throws Exception {
        require(Runtime.version().feature() == 17, "Measurement requires JDK17");
        require((args.length == 1 && args[0].equals("loopback"))
            || (args.length == 3 && (args[0].equals("serve") || args[0].equals("measure"))), "Invalid command");
        if (args[0].equals("loopback")) {
            AtomicReference<Throwable> failure = new AtomicReference<>();
            try (ServerSocket listener = new ServerSocket(0, 1, InetAddress.getByName("127.0.0.1"))) {
                Thread worker = new Thread(() -> {
                    try { serve(listener); } catch (Throwable error) { failure.set(error); }
                }, "nodelay-measurement-responder");
                worker.start();
                String rows;
                try { rows = measure("127.0.0.1", listener.getLocalPort()); }
                finally {
                    listener.close();
                    worker.join(5000);
                    require(!worker.isAlive(), "Responder retirement unknown");
                }
                if (failure.get() != null) throw new IOException("Responder failed", failure.get());
                System.out.println("{\"schema\":1,\"scope\":\"loopback-transport-only\",\"warmup\":" + WARMUP
                    + ",\"samplesPerBlock\":" + SAMPLES + ",\"blocks\":" + rows + "}");
            }
        } else if (args[0].equals("serve")) {
            int port = Integer.parseInt(args[2]);
            require(port > 1023 && port <= 65535, "Explicit unprivileged server port required");
            try (ServerSocket listener = new ServerSocket(port, 1, InetAddress.getByName(args[1]))) {
                System.out.println("READY"); System.out.flush();
                serve(listener);
            }
            System.out.println("COMPLETE");
        } else if (args[0].equals("measure")) {
            int port = Integer.parseInt(args[2]);
            require(port > 1023 && port <= 65535, "Explicit unprivileged server port required");
            String rows = measure(args[1], port);
            System.out.println("{\"schema\":1,\"scope\":\"explicit-peer-transport-only\",\"warmup\":" + WARMUP
                + ",\"samplesPerBlock\":" + SAMPLES + ",\"blocks\":" + rows + "}");
        } else throw new IOException("Unknown mode");
    }
}
