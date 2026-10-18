package dev.p2pkit.rpc.windows.loader;

/**
 * Bounded installed-object owner/DACL policy, not a native observation or installation authority.
 * The caller must obtain OWNER|DACL from the original held handle through the admitted OS interface.
 * No SACL/MIC, effective-token membership or AccessCheck emulation is claimed. Denies cannot rescue an
 * untrusted mutating allow. Only inheritance-only entries are excluded from the current object's grants.
 * VOLUME_ROOT requires independent actual volume-root admission; a path prefix is insufficient.
 */
final class WindowsInstallationSecurity {
    enum Kind { VOLUME_ROOT, DIRECTORY, FILE }

    private static final int MAXIMUM_BYTES = 65_536;
    private static final long SPECIFIC_RIGHTS = 0x001f01ffL;
    private static final long GENERIC_RIGHTS = 0xf0000000L;
    private static final long MUTATION = 0x000d0156L; // DELETE/DAC/OWNER, WRITE_DATA/APPEND/EA/CHILD/ATTR.
    private static final long GENERIC_READ = 0x00120089L;
    private static final long GENERIC_EXECUTE = 0x001200a0L;
    private static final long GENERIC_WRITE = 0x00120116L;
    private static final long[] SYSTEM = { 18 };
    private static final long[] ADMINISTRATORS = { 32, 544 };
    private static final long[] TRUSTED_INSTALLER = {
        80, 956008885L, 3418522649L, 1831038044L, 1853292631L, 2271478464L
    };

    private WindowsInstallationSecurity() {}

    static void require(byte[] descriptor, Kind kind) {
        if (descriptor == null || descriptor.length < 20 || descriptor.length > MAXIMUM_BYTES || kind == null) {
            refuse();
        }
        // Stable bounded private input prevents later caller mutation between framing and policy reads.
        // Copying is not proof of atomic native acquisition or the authority of the supplied bytes.
        descriptor = descriptor.clone();
        int control = word(descriptor, 2);
        // Require SELF_RELATIVE/DACL_PRESENT; reject untrusted/server-security/resource-manager flags.
        // Owner/group/DACL/SACL defaulting, inheritance and protection flags do not bypass ACE policy.
        if (unsigned(descriptor[0]) != 1 || descriptor[1] != 0 || (control & 0x8004) != 0x8004 ||
            (control & ~0xbf3f) != 0 || dword(descriptor, 12) != 0) {
            refuse();
        }
        // A SACL-present flag with no requested SACL bytes is not a SACL/MIC observation.
        int owner = offset(descriptor, 4);
        int ownerLength = sidLength(descriptor, owner, descriptor.length);
        if (!trusted(descriptor, owner)) refuse();
        int group = optionalOffset(descriptor, 8);
        int groupLength = group == 0 ? 0 : sidLength(descriptor, group, descriptor.length);
        if (group != 0 && overlap(owner, ownerLength, group, groupLength) &&
            (owner != group || ownerLength != groupLength)) {
            refuse();
        }
        int acl = offset(descriptor, 16); // Null/absent DACL is not an empty deny-all ACL.
        span(descriptor, acl, 8);
        if ((unsigned(descriptor[acl]) != 2 && unsigned(descriptor[acl]) != 4) || descriptor[acl + 1] != 0 ||
            word(descriptor, acl + 6) != 0) {
            refuse();
        }
        int aclLength = word(descriptor, acl + 2);
        int count = word(descriptor, acl + 4);
        if (aclLength < 8 || aclLength % 4 != 0 || count > (aclLength - 8) / 16) refuse();
        span(descriptor, acl, aclLength);
        if (overlap(owner, ownerLength, acl, aclLength) ||
            (group != 0 && overlap(group, groupLength, acl, aclLength))) {
            refuse();
        }
        int end = acl + aclLength;
        int cursor = acl + 8;
        for (int index = 0; index < count; index++) {
            if (cursor > end - 8) refuse();
            int type = unsigned(descriptor[cursor]);
            int flags = unsigned(descriptor[cursor + 1]);
            int length = word(descriptor, cursor + 2);
            if ((type != 0 && type != 1) || (flags & ~0x1f) != 0 || length < 16 ||
                length % 4 != 0 || length > end - cursor) {
                refuse();
            }
            long mask = dword(descriptor, cursor + 4);
            if ((mask & ~(SPECIFIC_RIGHTS | GENERIC_RIGHTS)) != 0) refuse();
            int sid = cursor + 8;
            int sidBytes = sidLength(descriptor, sid, cursor + length);
            if (sidBytes != length - 8) refuse();
            if (type == 0 && (flags & 8) == 0 && !trusted(descriptor, sid)) {
                long grants = expand(mask);
                long forbidden = kind == Kind.VOLUME_ROOT ? MUTATION & ~6L : MUTATION;
                if ((grants & forbidden) != 0) refuse();
            }
            cursor += length;
        }
        // Windows ACLs may reserve unused trailing capacity; require it zero rather than treating hidden
        // additional ACE bytes as harmless padding. Valid deny-all ACLs therefore remain representable.
        while (cursor < end) if (descriptor[cursor++] != 0) refuse();
    }

    private static long expand(long mask) {
        long rights = mask & SPECIFIC_RIGHTS;
        if ((mask & 0x80000000L) != 0) rights |= GENERIC_READ;
        if ((mask & 0x40000000L) != 0) rights |= GENERIC_WRITE;
        if ((mask & 0x20000000L) != 0) rights |= GENERIC_EXECUTE;
        if ((mask & 0x10000000L) != 0) rights |= SPECIFIC_RIGHTS;
        return rights;
    }

    private static int offset(byte[] bytes, int at) {
        int result = optionalOffset(bytes, at);
        if (result == 0) refuse();
        return result;
    }

    private static int optionalOffset(byte[] bytes, int at) {
        long result = dword(bytes, at);
        if (result == 0) return 0;
        if (result < 20 || result > bytes.length - 8 || result % 4 != 0) refuse();
        return (int) result;
    }

    private static int sidLength(byte[] bytes, int start, int end) {
        if (start < 20 || start > end - 8 || end > bytes.length || start % 4 != 0 ||
            unsigned(bytes[start]) != 1) {
            refuse();
        }
        int count = unsigned(bytes[start + 1]);
        int length = 8 + count * 4;
        if (count > 15 || length > end - start) refuse();
        return length;
    }

    private static boolean trusted(byte[] bytes, int sid) {
        // Binary SECURITY_NT_AUTHORITY, not display names, string prefixes or caller-selected authorities.
        for (int index = 2; index < 7; index++) if (bytes[sid + index] != 0) return false;
        return bytes[sid + 7] == 5 &&
            (matches(bytes, sid, SYSTEM) || matches(bytes, sid, ADMINISTRATORS) ||
                matches(bytes, sid, TRUSTED_INSTALLER));
    }

    private static boolean matches(byte[] bytes, int sid, long[] expected) {
        if (unsigned(bytes[sid + 1]) != expected.length) return false;
        for (int index = 0; index < expected.length; index++) {
            if (dword(bytes, sid + 8 + index * 4) != expected[index]) return false;
        }
        return true;
    }

    private static void span(byte[] bytes, int start, int length) {
        if (start < 20 || length < 0 || start > bytes.length || length > bytes.length - start) refuse();
    }

    private static boolean overlap(int first, int length, int second, int size) {
        return first < second + size && second < first + length;
    }

    private static int unsigned(byte value) { return Byte.toUnsignedInt(value); }
    private static int word(byte[] bytes, int at) {
        return unsigned(bytes[at]) | unsigned(bytes[at + 1]) << 8;
    }
    private static long dword(byte[] bytes, int at) {
        return Integer.toUnsignedLong(word(bytes, at) | word(bytes, at + 2) << 16);
    }
    private static void refuse() { throw new IllegalArgumentException("Installed Windows security policy refused"); }
}
