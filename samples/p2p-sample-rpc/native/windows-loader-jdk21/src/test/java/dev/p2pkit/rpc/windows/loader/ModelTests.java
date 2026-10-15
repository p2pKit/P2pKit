package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.MemoryLayout;
import java.lang.foreign.MemorySegment;
import java.lang.foreign.ValueLayout;
import java.nio.ByteOrder;
import java.util.concurrent.atomic.AtomicReference;

/** Portable FFM memory/Java-policy tests only. No Windows OS calls, profile, DLL or installed-app claim. */
public final class ModelTests {
    private ModelTests() {}

    public static void main(String[] arguments) throws InterruptedException {
        check(arguments.length == 0);
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        runtimeAndMetadataPolicy();
        providerAlwaysRefuses();
        invalidComponents();
        boundedComponents();
        unicodeLayout();
        littleEndianEncoding();
        zeroedOutputAndPadding();
        clearingOwnedBuffers();
        closeInvalidatesAllViews();
        wrongThreadNeverAcquiresOrRetires();
        independentOwners();
        boundsFailurePreservesOwnedFrame();
        borrowedInputViewsCannotRewriteDescriptorOrComponent();
        retirementFailuresKeepBothExactOutcomesAndNeverRetry();
        System.out.println("WINDOWS_LOADER_JDK21_MODELS_PASS tests=14 " +
            "scope=PORTABLE_FFM_DATA_NOT_WINDOWS_NATIVE_OR_PROFILE");
    }

    private static void runtimeAndMetadataPolicy() {
        String json = Probe.readback();
        check(json.length() < 2048 && json.contains("\"productionAvailable\":false") &&
            json.contains("\"javaFeature\":21") && json.contains("\"unnamedNativeAccess\":false"));
        check(WindowsLoaderRuntime.quotedMetadata("Vendor").equals("\"Vendor\""));
        check(WindowsLoaderRuntime.quotedMetadata("\"").equals("\"\\\"\""));
        check(WindowsLoaderRuntime.quotedMetadata("\\").equals("\"\\\\\""));
        for (String invalid : new String[] {null, "", "\n", "\u001f", "\u007f", "\u0080", "a".repeat(129)}) {
            expect(IllegalStateException.class, () -> WindowsLoaderRuntime.quotedMetadata(invalid));
        }
        check(WindowsLoaderRuntime.quotedMetadata("a".repeat(128)).length() == 130);
    }

    private static void providerAlwaysRefuses() {
        Throwable failure = expect(UnsupportedOperationException.class, WindowsLoader::openInstalledProvider);
        check(WindowsLoader.REFUSAL.equals(failure.getMessage()));
    }

    private static void invalidComponents() {
        for (String invalid : new String[] {null, "", ".", "..", "/tmp", "a/b", "a\\b", "a:b", "a\0b",
            "a.", "a ", " a", "CON", "con.dll", "PRN", "AUX", "NUL", "COM1", "lpt9.sys", "a\n", "é", "\ud800"}) {
            expect(IllegalArgumentException.class, () -> WindowsX64Frame.openComponent(invalid));
        }
    }

    private static void boundedComponents() {
        expect(IllegalArgumentException.class, () -> WindowsX64Frame.openComponent("a".repeat(256)));
        try (WindowsX64Frame frame = WindowsX64Frame.openComponent("a".repeat(255))) {
            check(frame.componentBytes().byteSize() == 512);
            check(Short.toUnsignedInt(frame.unicodeString().get(WindowsX64Frame.USHORT, 0)) == 510);
            check(Short.toUnsignedInt(frame.unicodeString().get(WindowsX64Frame.USHORT, 2)) == 512);
        }
    }

    private static void unicodeLayout() {
        check(WindowsX64Frame.UNICODE_STRING.byteSize() == 16 &&
            WindowsX64Frame.UNICODE_STRING.byteAlignment() == 8 &&
            WindowsX64Frame.IO_STATUS_BLOCK.byteSize() == 16);
        check(WindowsX64Frame.UNICODE_STRING.byteOffset(MemoryLayout.PathElement.groupElement("Buffer")) == 8);
        try (WindowsX64Frame frame = WindowsX64Frame.openComponent("P2pKit Sample")) {
            MemorySegment address = frame.unicodeString()
                .get(ValueLayout.ADDRESS.withOrder(ByteOrder.LITTLE_ENDIAN), 8);
            check(address.address() == frame.componentBytes().address());
            check(address.byteSize() == 0); // No reinterpretation/dereference of an unbounded pointer.
        }
    }

    private static void littleEndianEncoding() {
        try (WindowsX64Frame frame = WindowsX64Frame.openComponent("Az-9.dll")) {
            byte[] bytes = frame.componentBytes().toArray(ValueLayout.JAVA_BYTE);
            check(bytes[0] == 'A' && bytes[1] == 0 && bytes[2] == 'z' && bytes[3] == 0);
            check(bytes[bytes.length - 1] == 0 && bytes[bytes.length - 2] == 0);
            check(frame.unicodeString().get(ValueLayout.JAVA_BYTE, 0) == 16);
            check(frame.unicodeString().get(ValueLayout.JAVA_BYTE, 1) == 0);
        }
    }

    private static void zeroedOutputAndPadding() {
        try (WindowsX64Frame frame = WindowsX64Frame.openComponent("a")) {
            check(zero(frame.ioStatusBlock()));
            for (int i = 4; i < 8; i++) check(frame.unicodeString().get(ValueLayout.JAVA_BYTE, i) == 0);
        }
    }

    private static void clearingOwnedBuffers() {
        try (WindowsX64Frame frame = WindowsX64Frame.openComponent("p2pkit-windows-profile.dll")) {
            frame.ioStatusBlock().fill((byte) 7);
            frame.clear();
            check(zero(frame.componentBytes()) && zero(frame.unicodeString()) && zero(frame.ioStatusBlock()));
            frame.clear();
            check(zero(frame.componentBytes()));
        }
    }

    private static void closeInvalidatesAllViews() {
        WindowsX64Frame frame = WindowsX64Frame.openComponent("a");
        MemorySegment[] segments = {frame.componentBytes(), frame.unicodeString(), frame.ioStatusBlock()};
        frame.close();
        frame.close();
        expect(IllegalStateException.class, frame::componentBytes);
        expect(IllegalStateException.class, frame::unicodeString);
        expect(IllegalStateException.class, frame::ioStatusBlock);
        expect(IllegalStateException.class, frame::clear);
        for (MemorySegment segment : segments) {
            check(!segment.scope().isAlive());
            expect(IllegalStateException.class, () -> segment.get(ValueLayout.JAVA_BYTE, 0));
        }
    }

    private static void wrongThreadNeverAcquiresOrRetires() throws InterruptedException {
        try (WindowsX64Frame frame = WindowsX64Frame.openComponent("a")) {
            MemorySegment borrowed = frame.componentBytes();
            AtomicReference<Throwable> failure = new AtomicReference<>();
            Thread thread = new Thread(() -> {
                try {
                    expect(IllegalStateException.class, frame::unicodeString);
                    expect(IllegalStateException.class, frame::clear);
                    expect(IllegalStateException.class, frame::close);
                    expect(WrongThreadException.class, () -> borrowed.get(ValueLayout.JAVA_BYTE, 0));
                } catch (Throwable caught) { failure.set(caught); }
            }, "portable-windows-frame-wrong-thread");
            thread.start();
            thread.join(5000);
            check(!thread.isAlive());
            if (failure.get() != null) throw new AssertionError("Wrong-thread control failed", failure.get());
            check(frame.componentBytes().get(ValueLayout.JAVA_BYTE, 0) == 'a');
        }
    }

    private static void independentOwners() {
        try (WindowsX64Frame first = WindowsX64Frame.openComponent("first");
             WindowsX64Frame second = WindowsX64Frame.openComponent("second")) {
            check(first.componentBytes().address() != second.componentBytes().address());
            first.clear();
            check(second.componentBytes().get(ValueLayout.JAVA_BYTE, 0) == 's');
        }
    }

    private static void boundsFailurePreservesOwnedFrame() {
        try (WindowsX64Frame frame = WindowsX64Frame.openComponent("a")) {
            expect(IndexOutOfBoundsException.class, () ->
                frame.ioStatusBlock().set(ValueLayout.JAVA_BYTE, 16, (byte) 1));
            expect(IndexOutOfBoundsException.class, () ->
                frame.componentBytes().get(ValueLayout.JAVA_BYTE, -1));
            check(zero(frame.ioStatusBlock()));
            check(frame.componentBytes().get(ValueLayout.JAVA_BYTE, 0) == 'a');
        }
    }

    private static void borrowedInputViewsCannotRewriteDescriptorOrComponent() {
        try (WindowsX64Frame frame = WindowsX64Frame.openComponent("fixed.dll")) {
            check(frame.componentBytes().isReadOnly() && frame.unicodeString().isReadOnly());
            expect(UnsupportedOperationException.class, () ->
                frame.componentBytes().set(ValueLayout.JAVA_BYTE, 0, (byte) 'x'));
            expect(UnsupportedOperationException.class, () -> frame.unicodeString().fill((byte) 0));
            check(frame.componentBytes().get(ValueLayout.JAVA_BYTE, 0) == 'f');
            check(!frame.ioStatusBlock().isReadOnly());
            frame.ioStatusBlock().set(ValueLayout.JAVA_BYTE, 0, (byte) 7);
            check(frame.ioStatusBlock().get(ValueLayout.JAVA_BYTE, 0) == 7);
        }
    }

    private static void retirementFailuresKeepBothExactOutcomesAndNeverRetry() {
        Throwable[] failures = {null, new IllegalStateException("synthetic retirement error"),
            new OutOfMemoryError("synthetic retirement reporting failure")};
        for (Throwable clear : failures) for (Throwable release : failures) {
            if (clear == null && release == null) continue;
            int[] calls = {0, 0};
            WindowsX64Frame frame = WindowsX64Frame.openForValidation("fixed.dll",
                new WindowsX64Frame.CleanupObservation() {
                    @Override public void afterClear() { calls[0]++; throwIfPresent(clear); }
                    @Override public void afterArenaClose() { calls[1]++; throwIfPresent(release); }
                });
            MemorySegment original = frame.ioStatusBlock();
            WindowsX64Frame.CloseFailure carrier = (WindowsX64Frame.CloseFailure)
                expect(WindowsX64Frame.CloseFailure.class, frame::close);
            check(carrier.retainedFrame == frame && carrier.clearFailure == clear &&
                carrier.arenaCloseFailure == release && carrier.getCause() == (clear != null ? clear : release));
            check(carrier.getSuppressed().length == 0 && !original.scope().isAlive());
            if (clear != null) check(clear.getSuppressed().length == 0);
            if (release != null) check(release.getSuppressed().length == 0);
            check(expect(WindowsX64Frame.CloseFailure.class, frame::close) == carrier);
            check(expect(WindowsX64Frame.CloseFailure.class, frame::close) == carrier);
            check(calls[0] == 1 && calls[1] == 1);
            expect(IllegalStateException.class, frame::componentBytes);
        }
    }

    private static void throwIfPresent(Throwable failure) {
        if (failure instanceof Error error) throw error;
        if (failure instanceof RuntimeException exception) throw exception;
    }

    private static boolean zero(MemorySegment segment) {
        for (byte value : segment.toArray(ValueLayout.JAVA_BYTE)) if (value != 0) return false;
        return true;
    }

    private static Throwable expect(Class<? extends Throwable> type, Runnable action) {
        try { action.run(); } catch (Throwable failure) {
            if (type.isInstance(failure)) return failure;
            throw new AssertionError("Unexpected failure class", failure);
        }
        throw new AssertionError("Expected " + type.getSimpleName());
    }

    private static void check(boolean condition) {
        if (!condition) throw new AssertionError("Portable Windows frame contract failed");
    }
}
