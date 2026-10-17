package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.Linker;
import java.lang.foreign.MemoryLayout;
import java.lang.foreign.MemorySegment;
import java.lang.foreign.ValueLayout;
import java.lang.invoke.MethodHandle;
import java.lang.invoke.MethodHandles;
import java.lang.invoke.MethodType;
import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.concurrent.atomic.AtomicReference;

/** Exact production stream lifecycle with test-owned memory/Java handles, never ReadFile or native custody. */
public final class OriginalFileBytesLeaseTests {
    static final int CHUNK = 65_536;
    static final String LOCATOR = "C:\\fixture\\p2pkit-windows-profile.dll";
    private static final LinkageError RETURN_FAILURE = new LinkageError("inert stream missing primitive return");
    private OriginalFileBytesLeaseTests() {}

    public static void main(String[] arguments) throws Throwable {
        check(arguments.length == 1);
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        String mode = arguments[0];
        switch (mode) {
            case "owner-refusal" -> ownerRefusal();
            case "substitution" -> substitution();
            case "bounds" -> bounds();
            case "thread" -> wrongThread();
            case "stream-512", "stream-chunk", "stream-multi", "stream-maximum", "short-first", "short-later",
                "eof-first", "extra-eof", "false", "pending", "overcount", "unsigned-count", "throw-after-return",
                "metadata-before", "metadata-after", "metadata-false", "metadata-throw", "copy-failure",
                "retirement-failure", "hash-same-copy", "immutability" -> stream(mode);
            default -> throw new AssertionError("Unknown original byte lease control");
        }
        System.out.println("WINDOWS_ORIGINAL_FILE_BYTES_PASS case=" + mode +
            " scope=INERT_FULL_STREAM_AND_FRAME_NOT_FILE_CUSTODY_OR_AUTHORITY");
    }

    static WindowsOriginalProfileDllBytesCandidate unattached(WindowsOriginalProfileDllFileCandidate file, long length) {
        return new WindowsOriginalProfileDllBytesCandidate(file, null, null, null, null, null, null,
            new long[] {17, 19, 23, length, length, 1, 32, 0});
    }

    private static void ownerRefusal() throws Throwable {
        WindowsOriginalProfileDllBytesCandidate owner = unattached(null, 512);
        WindowsOriginalFileBytesLease core = core(owner);
        check(value(core, "originalProfileDllOwner") == owner && value(core, "originalJvmOwner") == null);
        expect(IllegalStateException.class, owner::observe);
        expect(IllegalStateException.class, owner::completed);
        expect(IllegalStateException.class, owner::snapshot);
        expect(IllegalStateException.class, owner::sha256);
        expect(IllegalStateException.class, () -> invoke(core, "consumeStream"));
        check(!(boolean) value(core, "attempted") && !(boolean) value(core, "streamAttempted"));
        check(value(core, "frameArena") == null && value(core, "originalSnapshot") == null);
        check(((WindowsOriginalFileBytesLease.Failure) value(core, "failure")).retainedCandidate == core);
        check(((WindowsOriginalProfileDllBytesCandidate.Failure) value(owner, "failure")).retainedCandidate == owner);
    }

    private static void substitution() throws Throwable {
        try (Fixture fixture = new Fixture(512, true)) {
            WindowsOriginalProfileDllBytesCandidate other = unattached(fixture.file, 512);
            expect(IllegalStateException.class, other::observe);
            expect(IllegalStateException.class, () -> fixture.bytes.requireOriginalCore(core(other)));
            expect(IllegalStateException.class, () -> fixture.core.snapshot(other));
            expect(IllegalStateException.class, () -> fixture.core.snapshot(null));
            expect(IllegalStateException.class, () -> fixture.file.requireOriginalBytes(other));
            check(!(boolean) value(fixture.core, "attempted") && value(fixture.core, "frameArena") == null);
        }
    }

    private static void bounds() throws Throwable {
        for (long length : new long[] {Long.MIN_VALUE, -1, 0, 511, 32L * 1024 * 1024 + 1, Long.MAX_VALUE}) {
            WindowsOriginalFileBytesLease core = core(unattached(null, length));
            expect(IllegalStateException.class, () -> invoke(core, "prepareData"));
            check(value(core, "originalSnapshot") == null && value(core, "digest") == null);
        }
        for (long length : new long[] {1, 512L * 1024 * 1024}) {
            WindowsOriginalJvmBytesCandidate jvm = new WindowsOriginalJvmBytesCandidate(null, null, null,
                null, null, null, null, new long[] {17, 19, 23, length, length, 1, 32, 0});
            WindowsOriginalFileBytesLease core = (WindowsOriginalFileBytesLease) value(jvm, "core");
            invoke(core, "prepareData");
            check(value(core, "originalSnapshot") == null && value(core, "digest") != null);
            check((long) invoke(core, "maximumBytes") == 512L * 1024 * 1024);
            expect(IllegalStateException.class, jvm::completed);
        }
        WindowsOriginalJvmBytesCandidate tooLarge = new WindowsOriginalJvmBytesCandidate(null, null, null,
            null, null, null, null, new long[] {17, 19, 23, 0, 512L * 1024 * 1024 + 1, 1, 32, 0});
        expect(IllegalStateException.class, () -> invoke(value(tooLarge, "core"), "prepareData"));
    }

    private static void wrongThread() throws Throwable {
        try (Fixture fixture = new Fixture(512, true)) {
            fixture.prepare("thread");
            AtomicReference<Throwable> unexpected = new AtomicReference<>();
            Thread other = Thread.startVirtualThread(() -> {
                try {
                    expect(IllegalStateException.class, () -> invoke(fixture.core, "consumeStream"));
                    expect(IllegalStateException.class, () -> invoke(fixture.core, "retireFrame"));
                    expect(IllegalStateException.class, fixture.bytes::snapshot);
                } catch (Throwable caught) { unexpected.set(caught); }
            });
            other.join();
            check(unexpected.get() == null && fixture.reads == 0 && fixture.informationCalls == 0);
            check(!(boolean) value(fixture.core, "streamAttempted"));
            invoke(fixture.core, "consumeStream");
            check(fixture.bytes.completed() && fixture.reads == 2 && fixture.informationCalls == 6);
        }
    }

    private static void stream(String mode) throws Throwable {
        int length = mode.equals("stream-maximum") ? 32 * 1024 * 1024 : mode.equals("stream-512") ||
            mode.equals("immutability") ? 512 : mode.equals("stream-chunk") ? CHUNK : CHUNK + 1;
        boolean success = mode.startsWith("stream-") || mode.equals("immutability") || mode.equals("hash-same-copy");
        try (Fixture fixture = new Fixture(length, true)) {
            fixture.prepare(mode);
            Arena frame = (Arena) value(fixture.core, "frameArena");
            if (success) {
                invoke(fixture.core, "consumeStream");
                check(fixture.bytes.completed() && fixture.bytes.byteCount() == length);
                int expectedCalls = (length + CHUNK - 1) / CHUNK + 1;
                check(fixture.reads == expectedCalls && fixture.reads <= 513 && fixture.informationCalls == 6);
                check((int) value(fixture.core, "readCalls") == expectedCalls && !frame.scope().isAlive());
                byte[] snapshot = (byte[]) value(fixture.core, "originalSnapshot");
                check(snapshot.length == length);
                // Even at 32MiB there is one full snapshot only. Reference SHA uses one 64KiB scratch array.
                MessageDigest reference = MessageDigest.getInstance("SHA-256", "SUN");
                byte[] scratch = new byte[CHUNK];
                for (int offset = 0; offset < length; offset += CHUNK) {
                    int count = Math.min(CHUNK, length - offset);
                    for (int index = 0; index < count; index++) {
                        byte expected = pattern(offset + index);
                        scratch[index] = expected;
                        check(snapshot[offset + index] == expected);
                    }
                    reference.update(scratch, 0, count);
                }
                check(MessageDigest.isEqual(reference.digest(), fixture.bytes.sha256()));
                Arrays.fill(scratch, (byte) 0);
                if (mode.equals("hash-same-copy")) check(fixture.hashUpdates == 2);
                if (mode.equals("immutability")) {
                    byte[] copy = fixture.bytes.snapshot();
                    byte[] digest = fixture.bytes.sha256();
                    check(copy != snapshot && Arrays.equals(copy, snapshot));
                    copy[0] ^= 1;
                    digest[0] ^= 1;
                    check(snapshot[0] == pattern(0) && !MessageDigest.isEqual(digest, fixture.bytes.sha256()));
                    check(fixture.bytes.snapshot()[0] == pattern(0));
                }
            } else {
                WindowsOriginalFileBytesLease.Failure failure = (WindowsOriginalFileBytesLease.Failure) expect(
                    WindowsOriginalFileBytesLease.Failure.class, () -> invoke(fixture.core, "consumeStream"));
                check(failure.retainedCandidate == fixture.core && value(fixture.core, "failure") == failure);
                check(!(boolean) value(fixture.core, "succeeded") && value(fixture.core, "observedDigest") == null);
                boolean unknown = Arrays.asList("false", "pending", "overcount", "unsigned-count",
                    "throw-after-return", "metadata-throw").contains(mode);
                check(frame.scope().isAlive() == unknown && (boolean) value(fixture.core, "frameRetired") == !unknown);
                check((boolean) value(fixture.core, "nativeReturnUnconfirmed") ==
                    (mode.equals("throw-after-return") || mode.equals("metadata-throw")));
                check((boolean) value(fixture.core, "readCompletionUnconfirmed") == (unknown && !mode.equals("metadata-throw")));
                if (mode.equals("retirement-failure")) {
                    check(failure.operationFailure == null && failure.clearFailures[0] != null);
                    check(failure.arenaCloseFailure == null && fixture.informationCalls == 6);
                } else check(failure.operationFailure != null);
                if (mode.equals("throw-after-return") || mode.equals("metadata-throw")) check(failure.operationFailure == RETURN_FAILURE);
                if (mode.equals("metadata-before")) check(fixture.reads == 0 && fixture.informationCalls == 3);
                else if (mode.equals("metadata-after") || mode.equals("retirement-failure")) {
                    check(fixture.reads == 3 && fixture.informationCalls == 6);
                } else if (mode.equals("metadata-false") || mode.equals("metadata-throw")) {
                    check(fixture.reads == 3 && fixture.informationCalls == 4);
                } else {
                    check(fixture.informationCalls == 3);
                    check(fixture.reads == (mode.equals("short-first") || mode.equals("eof-first") ? 1 :
                        mode.equals("extra-eof") ? 3 : 2));
                }
                expect(IllegalStateException.class, fixture.bytes::completed);
                expect(IllegalStateException.class, fixture.bytes::byteCount);
                expect(IllegalStateException.class, fixture.bytes::sha256);
                expect(IllegalStateException.class, fixture.bytes::snapshot);
                invoke(fixture.core, "retireFrame");
                check(frame.scope().isAlive() == unknown && value(fixture.core, "failure") == failure);
            }
            int reads = fixture.reads, metadata = fixture.informationCalls;
            expect(IllegalStateException.class, () -> invoke(fixture.core, "consumeStream"));
            expect(IllegalStateException.class, fixture.core::observe);
            expect(IllegalStateException.class, fixture.file::inspectBytes);
            check(fixture.reads == reads && fixture.informationCalls == metadata);
            check(fixture.bootstrapScope.scope().isAlive() && fixture.handleScope.scope().isAlive());
            check(fixture.moduleScope.scope().isAlive() && fixture.ancestorScope.scope().isAlive());
            check(value(fixture.core, "fileHandle") == value(fixture.lease, "handle"));
            check(value(fixture.core, "fileArena") == fixture.handleScope && value(fixture.bootstrap, "originalJvm") == null);
        }
    }

    private static byte pattern(int offset) { return (byte) (offset * 31 + (offset >>> 16) + 7); }

    /** Inert identity graph. Allocated entries/HANDLE-shaped values are NEVER invoked as native addresses. */
    static final class Fixture implements AutoCloseable {
        final Arena bootstrapScope = Arena.ofConfined();
        final Arena handleScope = Arena.ofConfined();
        final Arena moduleScope = Arena.ofConfined();
        final Arena ancestorScope = Arena.ofConfined();
        final WindowsSystemBootstrapCandidate bootstrap;
        final WindowsOriginalProfileDllFileCandidate file;
        final WindowsOriginalFileLease lease;
        final WindowsOriginalProfileDllSecurityCandidate security;
        final WindowsOriginalFileSecurityQuery query;
        final WindowsOriginalProfileDllAncestorsCandidate ancestors;
        final long[] metadata;
        WindowsOriginalProfileDllBytesCandidate bytes;
        WindowsOriginalFileBytesLease core;
        String mode;
        int reads;
        int informationCalls;
        int position;
        int hashUpdates;

        Fixture(long length, boolean attachBytes) throws ReflectiveOperationException {
            metadata = new long[] {17, 19, 23, (length + 4095) & ~4095L, length, 1, 32, 0};
            Constructor<WindowsSystemBootstrapCandidate> constructor =
                WindowsSystemBootstrapCandidate.class.getDeclaredConstructor(Linker.class);
            constructor.setAccessible(true);
            bootstrap = constructor.newInstance((Object) null);
            field(bootstrap, "originalArena").set(bootstrap, bootstrapScope);
            field(bootstrap, "succeeded").setBoolean(bootstrap, true);
            field(bootstrap, "frameRetired").setBoolean(bootstrap, true);
            MemorySegment[] entries = (MemorySegment[]) value(bootstrap, "entries");
            for (int index = 1; index <= 13; index++) entries[index] = bootstrapScope.allocate(8).asSlice(0, 0);
            file = new WindowsOriginalProfileDllFileCandidate(bootstrap, LOCATOR);
            field(bootstrap, "profileDll").set(bootstrap, file);
            field(bootstrap, "profileDllAttempted").setBoolean(bootstrap, true);
            field(file, "attempted").setBoolean(file, true);
            field(file, "originalPath").set(file, (LOCATOR + '\0').toCharArray());
            lease = WindowsOriginalFileLease.forProfileDll(file);
            field(file, "lease").set(file, lease);
            field(file, "succeeded").setBoolean(file, true);
            field(lease, "succeeded").setBoolean(lease, true);
            field(lease, "frameRetired").setBoolean(lease, true);
            MemorySegment handle = handleScope.allocate(8).asSlice(0, 0);
            field(lease, "handle").set(lease, handle);
            field(lease, "rawHandle").setLong(lease, handle.address());
            field(lease, "handleArena").set(lease, handleScope);
            System.arraycopy(metadata, 0, (long[]) value(lease, "first"), 0, metadata.length);
            security = lease.newProfileDllSecurity(file);
            field(file, "security").set(file, security);
            field(file, "securityAttempted").setBoolean(file, true);
            query = (WindowsOriginalFileSecurityQuery) value(security, "query");
            field(query, "succeeded").setBoolean(query, true);
            field(query, "frameRetired").setBoolean(query, true);
            field(query, "ntReturned").setBoolean(query, true);
            field(query, "policyEvaluated").setBoolean(query, true);
            field(query, "policyAccepted").setBoolean(query, true);
            field(query, "exactDescriptor").set(query, new byte[20]);
            field(query, "moduleArena").set(query, moduleScope);
            field(query, "module").set(query, moduleScope.allocate(8).asSlice(0, 0));
            field(query, "entry").set(query, moduleScope.allocate(8).asSlice(0, 0));
            field(security, "ancestorsAttempted").setBoolean(security, true);
            ancestors = query.newProfileDllAncestors(security);
            field(security, "ancestors").set(security, ancestors);
            Object ancestorCore = value(ancestors, "core");
            field(ancestorCore, "succeeded").setBoolean(ancestorCore, true);
            field(ancestorCore, "frameRetired").setBoolean(ancestorCore, true);
            field(ancestorCore, "componentCount").setInt(ancestorCore, 2);
            field(ancestorCore, "directoryCount").setInt(ancestorCore, 2);
            field(ancestorCore, "openedCount").setInt(ancestorCore, 3);
            field(ancestorCore, "leaseArena").set(ancestorCore, ancestorScope);
            if (attachBytes) {
                bytes = lease.newProfileDllBytes(file);
                core = core(bytes);
                field(file, "bytes").set(file, bytes);
                field(file, "bytesAttempted").setBoolean(file, true);
            }
        }

        void prepare(String mode) throws Throwable {
            this.mode = mode;
            invoke(core, "prepareData");
            invoke(core, "prepareFrame", new Class<?>[] {MemoryLayout.class}, MemoryLayout.structLayout(ValueLayout.JAVA_INT));
            MethodHandle read = MethodHandles.lookup().findVirtual(Fixture.class, "read",
                MethodType.methodType(int.class, MemorySegment.class, MemorySegment.class, MemorySegment.class,
                    int.class, MemorySegment.class, MemorySegment.class)).bindTo(this);
            MethodHandle returned = MethodHandles.lookup().findVirtual(Fixture.class, "returned",
                MethodType.methodType(int.class, int.class)).bindTo(this);
            field(core, "readCall").set(core, MethodHandles.filterReturnValue(read, returned));
            field(core, "informationCall").set(core, MethodHandles.lookup().findVirtual(Fixture.class, "information",
                MethodType.methodType(int.class, MemorySegment.class, MemorySegment.class, int.class,
                    MemorySegment.class, int.class)).bindTo(this));
            field(core, "attempted").setBoolean(core, true);
            if (mode.equals("copy-failure")) field(core, "originalSnapshot").set(core, new byte[CHUNK]);
            if (mode.equals("hash-same-copy")) field(core, "digest").set(core, new CopiedDigest(this));
        }

        private int read(MemorySegment error, MemorySegment handle, MemorySegment output, int wanted,
            MemorySegment count, MemorySegment overlapped) throws Throwable {
            reads++;
            if (reads == 1) {
                expect(IllegalStateException.class, () -> invoke(core, "consumeStream"));
                expect(IllegalStateException.class, core::observe);
                expect(IllegalStateException.class, file::inspectBytes);
                check(reads == 1 && informationCalls == 3); // Reentrant entry performs no second operation.
            }
            check(handle == value(lease, "handle") && overlapped.address() == 0);
            check(count.get(ValueLayout.JAVA_INT, 0) == -1 && wanted >= 1 && wanted <= CHUNK);
            check(informationCalls == 3 && reads <= 513 && Thread.currentThread() == value(core, "thread"));
            check(wanted == (position < metadata[4] ? Math.min(CHUNK, metadata[4] - position) : 1));
            for (int index = 0; index < CHUNK; index++) check(output.getAtIndex(ValueLayout.JAVA_BYTE, index) == 0);
            boolean failingRead = reads == 2;
            int amount = position < metadata[4] ? wanted : 0;
            if (mode.equals("short-first") && reads == 1 || mode.equals("short-later") && failingRead) amount = wanted - 1;
            if (mode.equals("eof-first") && reads == 1) amount = 0;
            if (mode.equals("extra-eof") && position == metadata[4]) amount = 1;
            if ((mode.equals("false") || mode.equals("pending")) && failingRead) amount = wanted / 2;
            for (int index = 0; index < amount; index++) output.setAtIndex(ValueLayout.JAVA_BYTE, index, pattern(position + index));
            int returned = mode.equals("overcount") && failingRead ? wanted + 1 :
                mode.equals("unsigned-count") && failingRead ? -1 : amount;
            count.set(ValueLayout.JAVA_INT, 0, returned);
            error.set(ValueLayout.JAVA_INT, 0, mode.equals("pending") ? 997 : 126); // Stale TRUE error is harmless.
            position += amount;
            return (mode.equals("false") || mode.equals("pending")) && failingRead ? 0 : 1;
        }

        private int returned(int status) {
            if (mode.equals("throw-after-return") && reads == 2) throw RETURN_FAILURE;
            return status;
        }

        private int information(MemorySegment error, MemorySegment handle, int kind, MemorySegment output, int size)
            throws Throwable {
            informationCalls++;
            check(handle == value(lease, "handle") && Thread.currentThread() == value(core, "thread"));
            int phase = (informationCalls - 1) % 3;
            check(kind == new int[] {18, 9, 1}[phase] && size == new int[] {24, 8, 24}[phase]);
            check(informationCalls <= 3 ? reads == 0 : position == metadata[4] && reads == (metadata[4] + CHUNK - 1) / CHUNK + 1);
            if (mode.equals("metadata-throw") && informationCalls == 4) throw RETURN_FAILURE;
            if (mode.equals("metadata-false") && informationCalls == 4) return 0;
            output.fill((byte) 0);
            if (kind == 18) {
                for (int index = 0; index < 3; index++) output.set(ValueLayout.JAVA_LONG, index * 8L, metadata[index]);
            } else if (kind == 9) {
                output.set(ValueLayout.JAVA_INT, 0, (int) metadata[6]);
                output.set(ValueLayout.JAVA_INT, 4, (int) metadata[7]);
            } else {
                output.set(ValueLayout.JAVA_LONG, 0, metadata[3]);
                long length = metadata[4] + (mode.equals("metadata-before") && informationCalls == 3 ||
                    mode.equals("metadata-after") && informationCalls == 6 ? 1 : 0);
                output.set(ValueLayout.JAVA_LONG, 8, length);
                output.set(ValueLayout.JAVA_INT, 16, (int) metadata[5]);
            }
            error.set(ValueLayout.JAVA_INT, 0, 126);
            if (mode.equals("retirement-failure") && informationCalls == 6) {
                MemorySegment[] buffers = (MemorySegment[]) value(core, "buffers");
                buffers[0] = buffers[0].asReadOnly();
            }
            return 1;
        }

        @Override public void close() throws ReflectiveOperationException {
            if (core != null) {
                Arena frame = (Arena) value(core, "frameArena");
                // Inert Java handles only: no pending native request can reference this test-owned frame.
                if (frame != null && frame.scope().isAlive()) frame.close();
            }
            ancestorScope.close(); moduleScope.close(); handleScope.close(); bootstrapScope.close();
        }
    }

    /** Test-only probe: proves DLL digest updates use the owned copy, even after native-buffer mutation. */
    private static final class CopiedDigest extends MessageDigest {
        private final Fixture fixture;
        private final MessageDigest delegate;
        CopiedDigest(Fixture fixture) throws Exception {
            super("SHA-256");
            this.fixture = fixture;
            delegate = MessageDigest.getInstance("SHA-256", "SUN");
        }
        @Override protected void engineUpdate(byte input) { throw new AssertionError("Unexpected one-byte digest update"); }
        @Override protected void engineUpdate(byte[] input, int offset, int length) {
            try {
                check(input == value(fixture.core, "originalSnapshot") && offset == fixture.hashUpdates * CHUNK);
                ((MemorySegment[]) value(fixture.core, "buffers"))[1].fill((byte) 0x6c);
                fixture.hashUpdates++;
                delegate.update(input, offset, length);
            } catch (ReflectiveOperationException failure) { throw new AssertionError(failure); }
        }
        @Override protected byte[] engineDigest() { return delegate.digest(); }
        @Override protected void engineReset() { delegate.reset(); }
    }

    static WindowsOriginalFileBytesLease core(WindowsOriginalProfileDllBytesCandidate bytes)
        throws ReflectiveOperationException { return (WindowsOriginalFileBytesLease) value(bytes, "core"); }
    static Field field(Object owner, String name) throws ReflectiveOperationException {
        Field field = owner.getClass().getDeclaredField(name);
        field.setAccessible(true);
        return field;
    }
    static Object value(Object owner, String name) throws ReflectiveOperationException { return field(owner, name).get(owner); }
    static Object invoke(Object owner, String name) throws Throwable { return invoke(owner, name, new Class<?>[0]); }
    static Object invoke(Object owner, String name, Class<?>[] types, Object... arguments) throws Throwable {
        Method method = owner.getClass().getDeclaredMethod(name, types);
        method.setAccessible(true);
        try { return method.invoke(owner, arguments); }
        catch (InvocationTargetException failure) { throw failure.getCause(); }
    }
    interface Action { void run() throws Throwable; }
    static Throwable expect(Class<? extends Throwable> type, Action action) {
        try { action.run(); }
        catch (Throwable caught) {
            if (type.isInstance(caught)) return caught;
            throw new AssertionError("Unexpected original byte control failure", caught);
        }
        throw new AssertionError("Expected original byte refusal");
    }
    static void check(boolean condition) {
        if (!condition) throw new AssertionError("Original byte lease control failed");
    }
}
