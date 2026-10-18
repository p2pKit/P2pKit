package dev.p2pkit.rpc.windows.loader;

import java.util.Arrays;

/** Inert self-relative descriptor controls, never native ACL readback or installation authority. */
public final class InstallationSecurityTests {
    private static final WindowsInstallationSecurity.Kind ROOT = WindowsInstallationSecurity.Kind.VOLUME_ROOT;
    private static final WindowsInstallationSecurity.Kind DIRECTORY = WindowsInstallationSecurity.Kind.DIRECTORY;
    private static final WindowsInstallationSecurity.Kind FILE = WindowsInstallationSecurity.Kind.FILE;
    private static final byte[] SYSTEM = sid(5, 18);
    private static final byte[] ADMIN = sid(5, 32, 544);
    private static final byte[] INSTALLER = sid(5, 80, 956008885L, 3418522649L, 1831038044L, 1853292631L, 2271478464L);
    private static final byte[] USERS = sid(5, 32, 545);
    private static int cases;

    private InstallationSecurityTests() {}

    private static byte[] sid(int authority, long... parts) {
        byte[] result = new byte[8 + parts.length * 4];
        result[0] = 1;
        result[1] = (byte) parts.length;
        result[7] = (byte) authority;
        for (int index = 0; index < parts.length; index++) put(result, 8 + index * 4, parts[index], 4);
        return result;
    }

    private static byte[] ace(int type, int flags, long mask, byte[] sid) {
        byte[] result = new byte[8 + sid.length];
        result[0] = (byte) type;
        result[1] = (byte) flags;
        put(result, 2, result.length, 2);
        put(result, 4, mask, 4);
        System.arraycopy(sid, 0, result, 8, sid.length);
        return result;
    }

    private static byte[] descriptor(byte[] owner, byte[]... entries) {
        int size = 28 + owner.length;
        for (byte[] entry : entries) size += entry.length;
        byte[] result = new byte[size];
        result[0] = 1;
        put(result, 2, 0x8004, 2);
        put(result, 4, 20, 4);
        int acl = 20 + owner.length;
        put(result, 16, acl, 4);
        System.arraycopy(owner, 0, result, 20, owner.length);
        result[acl] = 2;
        put(result, acl + 2, size - acl, 2);
        put(result, acl + 4, entries.length, 2);
        int cursor = acl + 8;
        for (byte[] entry : entries) {
            System.arraycopy(entry, 0, result, cursor, entry.length);
            cursor += entry.length;
        }
        return result;
    }

    private static void put(byte[] bytes, int offset, long value, int length) {
        for (int index = 0; index < length; index++) bytes[offset + index] = (byte) (value >>> (8 * index));
    }

    private static byte[] change(byte[] source, int offset, long value, int length) {
        byte[] result = source.clone();
        put(result, offset, value, length);
        return result;
    }

    private static void accept(byte[] bytes, WindowsInstallationSecurity.Kind kind) {
        WindowsInstallationSecurity.require(bytes, kind);
        cases++;
    }

    private static void reject(byte[] bytes, WindowsInstallationSecurity.Kind kind) {
        try {
            WindowsInstallationSecurity.require(bytes, kind);
            throw new AssertionError("Installation security accepted refused descriptor, case " + cases);
        } catch (IllegalArgumentException expected) {
            cases++;
        }
    }

    public static void main(String[] args) {
        if (args.length != 0) throw new AssertionError("Unexpected policy control arguments");
        byte[] rx = ace(0, 0x10, 0xa0000000L, USERS);
        byte[] safe = descriptor(SYSTEM, ace(0, 0, 0x10000000L, SYSTEM), rx,
            ace(0, 0x0b, 0x10000000L, sid(3, 0))); // CREATOR OWNER applies only to children.
        for (byte[] owner : new byte[][] { SYSTEM, ADMIN, INSTALLER }) {
            accept(descriptor(owner, rx), FILE);
            accept(descriptor(owner, ace(0, 0, 0x10000000L, owner)), DIRECTORY);
        }
        accept(safe, DIRECTORY);
        accept(change(safe, 2, 0x9404, 2), DIRECTORY); // Protected, auto-inherited DACL.
        accept(change(safe, 2, 0x8014, 2), FILE); // SACL unrequested, no MIC claim.
        accept(descriptor(SYSTEM), FILE); // Empty ACL is deny-all, not NULL ACL.
        accept(change(safe, 8, 20, 4), FILE); // Exact owner/group alias.
        accept(change(safe, 32, 4, 1), FILE); // ACL_REVISION_DS, still basic ACEs only.
        for (long mask : new long[] { 1, 8, 0x20, 0x80, 0x20000, 0x100000, 0x80000000L, 0x20000000L }) {
            accept(descriptor(SYSTEM, ace(0, 0, mask, USERS)), FILE);
        }
        for (long mask : new long[] { 2, 4, 6 }) {
            byte[] creation = descriptor(SYSTEM, ace(0, 0, mask, USERS));
            accept(creation, ROOT);
            reject(creation, FILE);
            reject(creation, DIRECTORY);
        }
        for (long mask : new long[] { 0x10, 0x40, 0x100, 0x10000, 0x40000, 0x80000, 0x40000000L, 0x10000000L }) {
            for (WindowsInstallationSecurity.Kind kind : WindowsInstallationSecurity.Kind.values()) {
                reject(descriptor(SYSTEM, ace(0, 0, mask, USERS)), kind);
            }
        }
        for (int flags : new int[] { 0, 1, 2, 3, 0x10, 0x13 }) {
            reject(descriptor(SYSTEM, ace(0, flags, 2, USERS)), DIRECTORY);
        }
        accept(descriptor(SYSTEM, ace(0, 0x08, 0x10000000L, USERS)), DIRECTORY);
        byte[] deny = ace(1, 0, 0x10000000L, USERS);
        byte[] write = ace(0, 0, 2, USERS);
        reject(descriptor(SYSTEM, deny, write), FILE);
        reject(descriptor(SYSTEM, write, deny), FILE);
        accept(descriptor(SYSTEM, deny, rx), FILE);
        for (byte[] owner : new byte[][] { USERS, sid(5, 18, 0), sid(4, 18), sid(5, 32, 544, 0),
            sid(5, 80, 956008885L, 3418522649L, 1831038044L, 1853292631L, 2271478465L), sid(0) }) {
            reject(descriptor(owner, rx), FILE);
        }
        for (int type : new int[] { 2, 3, 5, 6, 9, 10, 17, 255 }) {
            reject(descriptor(SYSTEM, ace(type, 0, 0, USERS)), FILE);
        }
        for (int flags : new int[] { 0x20, 0x40, 0x80, 0xff }) {
            reject(descriptor(SYSTEM, ace(0, flags, 0, USERS)), FILE);
            reject(descriptor(SYSTEM, ace(1, flags, 0, USERS)), FILE);
        }
        for (long mask : new long[] { 0x200, 0x200000, 0x1000000, 0x2000000, 0x8000000 }) {
            reject(descriptor(SYSTEM, ace(0, 8, mask, USERS)), FILE);
            reject(descriptor(SYSTEM, ace(1, 0, mask, SYSTEM)), FILE);
        }
        reject(null, FILE);
        reject(safe, null);
        reject(new byte[65_537], FILE);
        for (int size = 0; size < safe.length; size++) reject(Arrays.copyOf(safe, size), FILE);
        reject(change(safe, 0, 2, 1), FILE);
        reject(change(safe, 1, 1, 1), FILE);
        for (int control : new int[] { 0, 4, 0x8000, 0x8044, 0x8084, 0xc004 }) {
            reject(change(safe, 2, control, 2), FILE);
        }
        for (int at : new int[] { 4, 8, 16 }) {
            for (long offset : new long[] { 1, 16, 21, 0x80000000L, 0xffffffffL, safe.length }) {
                reject(change(safe, at, offset, 4), FILE);
            }
        }
        reject(change(safe, 4, 0, 4), FILE);
        reject(change(safe, 16, 0, 4), FILE);
        reject(change(safe, 12, 20, 4), FILE);
        reject(change(safe, 20, 2, 1), FILE);
        reject(change(safe, 21, 16, 1), FILE);
        // Partial SID overlap is refused, including an independently shaped valid group SID.
        byte[] overlap = change(safe, 8, 24, 4);
        overlap[24] = 1;
        reject(overlap, FILE);
        reject(change(safe, 8, 48, 4), FILE); // Valid SYSTEM ACE SID overlaps the DACL.
        reject(change(safe, 4, 48, 4), FILE); // Valid owner SID relocated into the DACL.
        for (int revision : new int[] { 0, 1, 3, 5 }) reject(change(safe, 32, revision, 1), FILE);
        reject(change(safe, 33, 1, 1), FILE);
        reject(change(safe, 38, 1, 2), FILE);
        for (int size : new int[] { 0, 4, 7, 9, 0xffff }) reject(change(safe, 34, size, 2), FILE);
        reject(change(safe, 36, 0xffff, 2), FILE);
        for (int size : new int[] { 0, 8, 15, 17, 16, 24, 0xffff }) reject(change(safe, 42, size, 2), FILE);
        reject(change(safe, 48, 2, 1), FILE); // ACE SID revision.
        reject(change(safe, 49, 16, 1), FILE);
        byte[] spare = Arrays.copyOf(safe, safe.length + 4);
        put(spare, 34, spare.length - 32, 2);
        accept(spare, FILE);
        spare[spare.length - 1] = 1;
        reject(spare, FILE);
        System.out.println("WINDOWS_INSTALLATION_SECURITY_PASS tests=" + cases +
            " scope=INERT_DESCRIPTOR_POLICY_NOT_NATIVE_READBACK_OR_AUTHORITY");
    }
}
