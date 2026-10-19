package dev.p2pkit.rpc.windows.loader;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.Arrays;
import java.util.List;

/** Copied-data controls only; no IP Helper execution or installed network authority. */
public final class WindowsIpInterfaceTableTests {
    private static int controls;
    private WindowsIpInterfaceTableTests() {}

    public static void main(String[] args) {
        check(args.length == 0);
        byte[] ipv4 = row(2, 7, 100), ipv6 = row(23, 7, 100);
        var parsed = WindowsIpInterfaceTable.parse(join(ipv6, ipv4), 2);
        check(parsed.size() == 2 && parsed.get(0).family() == 2 && parsed.get(1).family() == 23);
        check(WindowsIpInterfaces.boundIndices(parsed).equals(java.util.Set.of(7)));
        byte[] other = row(2, 8, 200);
        check(WindowsIpInterfaces.boundIndices(WindowsIpInterfaceTable.parse(join(ipv4, other), 2)).size() == 2);
        // A second IP path remains visible; neither absence of addresses nor its display name removes it.
        reject(() -> WindowsIpInterfaceTable.parse(ipv4, 0));
        reject(() -> WindowsIpInterfaceTable.parse(ipv4, 4097));
        reject(() -> WindowsIpInterfaceTable.parse(Arrays.copyOf(ipv4, 167), 1));
        reject(() -> WindowsIpInterfaceTable.parse(join(ipv4, ipv4), 2));
        reject(() -> WindowsIpInterfaceTable.parse(join(ipv4, row(23, 7, 101)), 2));
        reject(() -> WindowsIpInterfaceTable.parse(row(0, 7, 100), 1));
        reject(() -> WindowsIpInterfaceTable.parse(row(2, 0, 100), 1));
        reject(() -> WindowsIpInterfaceTable.parse(row(2, -1, 100), 1));
        reject(() -> WindowsIpInterfaceTable.parse(row(2, 7, 0), 1));
        for (int offset : new int[] {41, 42, 43, 156}) {
            byte[] malformed = ipv4.clone(); malformed[offset] = 2;
            reject(() -> WindowsIpInterfaceTable.parse(malformed, 1));
        }
        for (int offset : new int[] {41, 42, 43}) {
            byte[] unsafe = ipv4.clone(); unsafe[offset] = 1;
            reject(() -> WindowsIpInterfaces.boundIndices(WindowsIpInterfaceTable.parse(unsafe, 1)));
        }
        check(!parsed.equals(WindowsIpInterfaceTable.parse(join(row(2, 7, 102), row(23, 7, 102)), 2)));
        // Input order cannot make a stable table seem changed; returned lists are immutable snapshots.
        check(parsed.equals(WindowsIpInterfaceTable.parse(join(ipv4, ipv6), 2)));
        reject(() -> parsed.add(parsed.get(0)));
        reject(() -> WindowsIpInterfaces.boundIndices(List.of()));
        System.out.println("WINDOWS_IP_TABLE_CONTROLS_PASS controls=" + controls +
            " scope=COPIED_DATA_NOT_NATIVE_NETWORK_QUALIFICATION");
    }

    private static byte[] row(int family, int index, long luid) {
        ByteBuffer bytes = ByteBuffer.allocate(168).order(ByteOrder.LITTLE_ENDIAN);
        bytes.putShort(0, (short) family); bytes.putLong(8, luid); bytes.putInt(16, index);
        bytes.putInt(148, 25); bytes.putInt(152, 1500); bytes.put(156, (byte) 1);
        return bytes.array();
    }
    private static byte[] join(byte[] first, byte[] second) {
        byte[] result = Arrays.copyOf(first, first.length + second.length);
        System.arraycopy(second, 0, result, first.length, second.length); return result;
    }
    private static void check(boolean value) { if (!value) throw new AssertionError(); controls++; }
    private static void reject(Runnable action) {
        try { action.run(); } catch (IllegalStateException | IllegalArgumentException | UnsupportedOperationException expected) {
            controls++; return;
        }
        throw new AssertionError("Expected rejection");
    }
}
