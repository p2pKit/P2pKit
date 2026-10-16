package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.FunctionDescriptor;
import java.lang.foreign.Linker;
import java.lang.foreign.MemoryLayout;
import java.lang.foreign.MemorySegment;
import java.lang.foreign.ValueLayout;
import java.lang.invoke.MethodHandle;
import java.nio.ByteOrder;

/**
 * Dormant named, NONFORWARDED GetProcAddress mechanics; never initial OS lookup or loading authority.
 * A reviewed caller must transfer exclusive original bootstrap/module owners and bind all export fields
 * to the same independently verified original PE plan. Numbers, references and scopes prove none of that.
 * In particular this cannot resolve system-library forwarders to establish its own bootstrap authority.
 */
final class WindowsExportLookupInvocation {
    static final int MAXIMUM_NAME_BYTES = 256;
    static final MemoryLayout NAME = MemoryLayout.sequenceLayout(MAXIMUM_NAME_BYTES, ValueLayout.JAVA_BYTE);
    static final FunctionDescriptor DESCRIPTOR = FunctionDescriptor.of(ValueLayout.ADDRESS,
        ValueLayout.ADDRESS, ValueLayout.ADDRESS.withTargetLayout(NAME));

    static final class Result {
        final WindowsExportLookupInvocation retainedInvocation;

        private Result(WindowsExportLookupInvocation invocation) { retainedInvocation = invocation; }

        MemorySegment entry() {
            retainedInvocation.requireThread();
            if (!retainedInvocation.succeeded) throw new IllegalStateException("Named export lookup is not successful");
            retainedInvocation.requireOriginalScopes();
            return retainedInvocation.resolved;
        }
    }

    static final class Failure extends RuntimeException {
        private static final long serialVersionUID = 1L;
        final transient WindowsExportLookupInvocation retainedInvocation;
        Throwable preparationFailure;
        Throwable invocationFailure;
        Throwable readbackFailure;
        Throwable nameClearFailure;
        Throwable arenaCloseFailure;

        Failure(WindowsExportLookupInvocation invocation) {
            super("Named export lookup failed with original ownership retained", null, false, false);
            retainedInvocation = invocation;
        }

        boolean retirementFailed() { return nameClearFailure != null || arenaCloseFailure != null; }
    }

    private final Thread thread = Thread.currentThread();
    final Object bootstrapOwner;
    final Object moduleOwner;
    final Object originalExportPlan;
    private final MemorySegment systemEntry;
    private final Arena bootstrapArena;
    private final MemorySegment module;
    private final Arena moduleArena;
    private final String name;
    private final long imageBytes;
    private final long functionRva;
    private final Failure failure = new Failure(this);
    private final Result result = new Result(this);
    private Arena frameArena;
    private MemorySegment nameBuffer;
    private MemorySegment nameView;
    private MethodHandle call;
    private MemorySegment resolved;
    private boolean attempted;
    private boolean active;
    private boolean retired;
    private boolean succeeded;

    private WindowsExportLookupInvocation(Object bootstrapOwner, Object moduleOwner, Object originalExportPlan,
                                         MemorySegment systemEntry, Arena bootstrapArena,
                                         MemorySegment module, Arena moduleArena, String name,
                                         long imageBytes, long functionRva) {
        this.bootstrapOwner = bootstrapOwner;
        this.moduleOwner = moduleOwner;
        this.originalExportPlan = originalExportPlan;
        this.systemEntry = systemEntry;
        this.bootstrapArena = bootstrapArena;
        this.module = module;
        this.moduleArena = moduleArena;
        this.name = name;
        this.imageBytes = imageBytes;
        this.functionRva = functionRva;
    }

    /** Export directory and function fields must come from the retained original, nonforwarded PE plan. */
    static WindowsExportLookupInvocation prepare(Object bootstrapOwner, Object moduleOwner, Object originalExportPlan,
                                                 MemorySegment systemEntry, Arena bootstrapArena,
                                                 MemorySegment module, Arena moduleArena, String name,
                                                 long imageBytes, long exportDirectoryRva,
                                                 long exportDirectoryBytes, long functionRva) {
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        if (WindowsExportLookupInvocation.class.getModule() != WindowsLoaderRuntime.class.getModule() ||
            Thread.currentThread().isVirtual()) {
            throw new IllegalStateException("Named export lookup requires its original boot module/platform thread");
        }
        if (bootstrapOwner == null || moduleOwner == null || originalExportPlan == null ||
            !originalSegment(systemEntry, bootstrapArena) || !originalSegment(module, moduleArena) ||
            name == null || name.isEmpty() || name.length() >= MAXIMUM_NAME_BYTES ||
            !name.matches("[A-Za-z_][A-Za-z0-9_]*") || imageBytes < 4096 || imageBytes > 128L * 1024 * 1024 ||
            (module.address() & 65_535) != 0 || module.address() > Long.MAX_VALUE - imageBytes ||
            exportDirectoryRva <= 0 || exportDirectoryBytes < 40 || exportDirectoryRva >= imageBytes ||
            exportDirectoryBytes > imageBytes - exportDirectoryRva || functionRva <= 0 || functionRva >= imageBytes ||
            (functionRva >= exportDirectoryRva && functionRva < exportDirectoryRva + exportDirectoryBytes)) {
            throw new IllegalArgumentException("Invalid original nonforwarded export binding");
        }
        Linker linker = Linker.nativeLinker();
        if (linker.getClass().getModule() != Object.class.getModule() || linker.getClass().getClassLoader() != null ||
            !linker.getClass().getName().equals("jdk.internal.foreign.abi.x64.windows.Windowsx64Linker") ||
            ValueLayout.ADDRESS.byteSize() != 8 || ByteOrder.nativeOrder() != ByteOrder.LITTLE_ENDIAN) {
            throw new IllegalStateException("Named export lookup requires the actual Windows x64 linker");
        }
        WindowsExportLookupInvocation invocation = new WindowsExportLookupInvocation(bootstrapOwner, moduleOwner,
            originalExportPlan, systemEntry, bootstrapArena, module, moduleArena, name, imageBytes, functionRva);
        try {
            invocation.prepareFrame(linker.downcallHandle(systemEntry, DESCRIPTOR));
            return invocation;
        } catch (Throwable caught) {
            invocation.failure.preparationFailure = caught;
            try { invocation.retireFrame(); } catch (Failure ignored) { /* Preserve independent failures. */ }
            throw invocation.failure;
        }
    }

    private static boolean originalSegment(MemorySegment segment, Arena arena) {
        return segment != null && arena != null && segment.isNative() && segment.address() > 0 &&
            arena.scope().isAlive() && !arena.scope().equals(Arena.global().scope()) &&
            segment.scope().equals(arena.scope()) && segment.isAccessibleBy(Thread.currentThread());
    }

    /** No production validation bypass; off-host tests reflect only this private inert frame preparation. */
    private void prepareFrame(MethodHandle handle) {
        call = handle;
        frameArena = Arena.ofConfined();
        nameBuffer = frameArena.allocate(NAME);
        validateNameBuffer();
        for (int index = 0; index < name.length(); index++) {
            nameBuffer.set(ValueLayout.JAVA_BYTE, index, (byte) name.charAt(index));
        }
        nameView = nameBuffer.asReadOnly(); // The exact terminator and unused tail stay zero initialized.
    }

    private void validateNameBuffer() {
        long first = nameBuffer.address();
        long base = module.address();
        if (!nameBuffer.isNative() || nameBuffer.byteSize() != MAXIMUM_NAME_BYTES || first <= 65_535 ||
            first > Long.MAX_VALUE - MAXIMUM_NAME_BYTES || !nameBuffer.scope().equals(frameArena.scope()) ||
            !nameBuffer.scope().isAlive() || !nameBuffer.isAccessibleBy(thread) ||
            (first < base + imageBytes && base < first + MAXIMUM_NAME_BYTES) ||
            (systemEntry.address() >= first && systemEntry.address() < first + MAXIMUM_NAME_BYTES)) {
            // Low-word-only values select ordinals, not names; any overlap with the admitted image is invalid.
            throw new IllegalStateException("Invalid original named-export call buffer");
        }
    }

    private void requireThread() {
        if (Thread.currentThread() != thread) {
            throw new IllegalStateException("Named export lookup accessed outside its owning platform thread");
        }
    }

    private void requireOriginalScopes() {
        if (!originalSegment(systemEntry, bootstrapArena) || !originalSegment(module, moduleArena)) {
            throw new IllegalStateException("Original named-export scopes are unavailable");
        }
    }

    Result invoke() {
        requireThread();
        if (attempted || retired) throw new IllegalStateException("Named export lookup is already consumed");
        attempted = true;
        boolean accepted = false;
        try {
            try {
                requireOriginalScopes();
                validateNameBuffer();
                active = true;
                try { resolved = (MemorySegment) call.invokeExact(module, nameView); }
                finally { active = false; }
            } catch (Throwable caught) {
                failure.invocationFailure = caught;
                throw failure;
            }
            try {
                requireOriginalScopes();
                // Keep the original raw return before validation/view creation. In-image alone is insufficient.
                if (resolved.address() != module.address() + functionRva ||
                    (resolved.address() >= nameBuffer.address() &&
                        resolved.address() < nameBuffer.address() + MAXIMUM_NAME_BYTES)) {
                    throw new IllegalStateException("Resolved named export differs from its exact original RVA");
                }
                resolved = resolved.reinterpret(moduleArena, null);
                accepted = true;
            } catch (Throwable caught) {
                failure.readbackFailure = caught;
                throw failure;
            }
        } finally {
            try { retireFrame(); }
            finally { succeeded = accepted && !failure.retirementFailed(); }
        }
        return result;
    }

    /** Retire only private ASCII storage; neither original scope nor loaded module is closed or unloaded. */
    void retireFrame() {
        requireThread();
        if (active) throw new IllegalStateException("Named export lookup is still active");
        if (retired) {
            if (failure.retirementFailed()) throw failure;
            return;
        }
        retired = true;
        try { if (nameBuffer != null) nameBuffer.fill((byte) 0); }
        catch (Throwable caught) { failure.nameClearFailure = caught; }
        try { if (frameArena != null) frameArena.close(); }
        catch (Throwable caught) { failure.arenaCloseFailure = caught; }
        if (failure.retirementFailed()) throw failure;
    }
}
