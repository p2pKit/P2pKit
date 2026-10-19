package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.FunctionDescriptor;
import java.lang.foreign.Linker;
import java.lang.foreign.MemoryLayout;
import java.lang.foreign.MemorySegment;
import java.lang.foreign.ValueLayout;
import java.lang.invoke.MethodHandle;

/** Fixed OS Program Files classification under original trusted startup, never environment/path authority. */
final class WindowsOriginalProgramFilesCandidate {
    private static final String EXPORT = "SHGetFolderPathW";
    private static final int PATH_CHARS = 260;
    static final class Failure extends RuntimeException {
        private static final long serialVersionUID = 1L;
        final transient WindowsOriginalProgramFilesCandidate retainedCandidate;
        Throwable operationFailure;
        final Throwable[] clearFailures = new Throwable[4];
        Throwable arenaCloseFailure;
        private Failure(WindowsOriginalProgramFilesCandidate candidate) {
            super("Original Program Files classification failed with ownership retained", null, false, false);
            retainedCandidate = candidate;
        }
        private boolean retirementFailed() {
            if (arenaCloseFailure != null) return true;
            for (Throwable caught : clearFailures) if (caught != null) return true;
            return false;
        }
    }

    private final Thread thread = Thread.currentThread();
    private final WindowsInstalledProfileCandidate owner;
    private final Failure failure = new Failure(this);
    // Captured resolver error, fixed ASCII export, physical-provider PIN output, caller-owned MAX_PATH.
    private final MemorySegment[] buffers = new MemorySegment[4];
    private WindowsOriginalSystemModulesCandidate systems;
    private WindowsOriginalSystemModuleCandidate shell;
    private WindowsOriginalSystemModuleCandidate provider;
    private MemorySegment shellModule;
    private MemorySegment resolveEntry;
    private MemorySegment pinEntry;
    private MemorySegment resolvedEntry;
    private MethodHandle resolveCall;
    private MethodHandle pinCall;
    private MethodHandle folderCall;
    private Arena frameArena;
    private long expectedTarget;
    private long rawEntry;
    private long rawProvider;
    private long errorOffset;
    private final int[] lastErrors = new int[2];
    private int pinStatus;
    private int folderStatus;
    private boolean attempted;
    private boolean callAttempted;
    private boolean nativeReturnUnconfirmed;
    private boolean frameRetired;
    private boolean succeeded;

    WindowsOriginalProgramFilesCandidate(WindowsInstalledProfileCandidate owner) { this.owner = owner; }

    void observe() {
        requireOriginal();
        if (attempted) throw new IllegalStateException("Program Files observation is already consumed");
        attempted = true;
        boolean accepted = false;
        try {
            systems = owner.originalSystems(this);
            shell = systems.module(3);
            WindowsSystemExportPlan.Target target = systems.resolve("shell32.dll", EXPORT);
            int slot = -1;
            for (int index = 0; index < systems.moduleCount(); index++) {
                if (WindowsOriginalSystemModulesCandidate.fixedName(index).equals(target.module())) slot = index;
            }
            if (slot < 0) throw new IllegalStateException("Known-folder export leaves the original fixed system cohort");
            provider = systems.module(slot);
            long base = provider.originalModuleBits();
            if (target.rva() <= 0 || target.rva() >= 256L * 1024 * 1024 || base > Long.MAX_VALUE - target.rva()) {
                throw new IllegalStateException("Known-folder export has an invalid original image bound");
            }
            expectedTarget = base + target.rva(); // Comparison only; never used to manufacture a callable view.
            shellModule = shell.originalProgramFilesModule(this);
            prepareFrame();
            resolveAndPin();
            callFolder();
            validatePath(buffers[3], folderStatus, owner.originalRoot());
            requireOriginal();
            accepted = true;
        } catch (Throwable caught) {
            failure.operationFailure = caught;
        } finally { retireFrame(); }
        succeeded = accepted && frameRetired && !nativeReturnUnconfirmed && !failure.retirementFailed();
        if (!succeeded) throw failure;
    }

    private void requireOriginal() {
        if (Thread.currentThread() != thread || owner == null) throw new IllegalStateException("Known-folder query lacks its original owner/thread");
        owner.requireOriginalKnownFolder(this);
    }

    void requireOriginalShellModule(WindowsOriginalSystemModuleCandidate candidate) {
        requireOriginal();
        if (systems == null || candidate == null || candidate != shell || candidate != systems.module(3)) {
            throw new IllegalStateException("Known-folder resolver lost the original shell32 owner");
        }
    }

    private void prepareFrame() {
        requireOriginal();
        Linker linker = owner.originalLinker();
        pinEntry = owner.resolverEntry(0);
        resolveEntry = owner.resolverEntry(1);
        Arena original = owner.originalArena();
        for (MemorySegment entry : new MemorySegment[] {pinEntry, resolveEntry}) {
            if (entry == null || !entry.isNative() || entry.byteSize() != 0 || entry.address() <= 65_535 ||
                !entry.scope().equals(original.scope()) || !entry.isAccessibleBy(thread) || !original.scope().isAlive()) {
                throw new IllegalStateException("Known-folder resolver lost its original scoped entry");
            }
        }
        MemoryLayout state = Linker.Option.captureStateLayout();
        MemoryLayout error = state.select(MemoryLayout.PathElement.groupElement("GetLastError"));
        errorOffset = state.byteOffset(MemoryLayout.PathElement.groupElement("GetLastError"));
        if (!(error instanceof ValueLayout.OfInt) || error.byteSize() != 4 || error.byteAlignment() != 4 ||
            state.byteSize() < 4 || state.byteSize() > 64 || errorOffset < 0 || errorOffset % 4 != 0 ||
            errorOffset > state.byteSize() - 4) throw new IllegalStateException("Unsupported known-folder resolver error layout");
        resolveCall = linker.downcallHandle(resolveEntry, FunctionDescriptor.of(ValueLayout.JAVA_LONG,
            ValueLayout.ADDRESS, ValueLayout.ADDRESS), Linker.Option.captureCallState("GetLastError"));
        pinCall = linker.downcallHandle(pinEntry, FunctionDescriptor.of(ValueLayout.JAVA_INT,
            ValueLayout.JAVA_INT, ValueLayout.ADDRESS, ValueLayout.ADDRESS), Linker.Option.captureCallState("GetLastError"));
        frameArena = Arena.ofConfined();
        buffers[0] = frameArena.allocate(state);
        buffers[1] = frameArena.allocate(EXPORT.length() + 1, 1);
        buffers[2] = frameArena.allocate(ValueLayout.JAVA_LONG);
        buffers[3] = frameArena.allocate(PATH_CHARS * 2L, 2);
        long[] sizes = {state.byteSize(), EXPORT.length() + 1L, 8, PATH_CHARS * 2L};
        int[] alignments = {4, 1, 8, 2};
        for (int index = 0; index < buffers.length; index++) {
            MemorySegment buffer = buffers[index];
            if (!buffer.isNative() || buffer.byteSize() != sizes[index] || buffer.address() <= 65_535 ||
                buffer.address() > Long.MAX_VALUE - sizes[index] || buffer.address() % alignments[index] != 0 ||
                !buffer.scope().equals(frameArena.scope()) || !buffer.isAccessibleBy(thread)) {
                throw new IllegalStateException("Invalid original known-folder private frame");
            }
            for (int prior = 0; prior < index; prior++) rejectAlias(buffers[prior].address(), buffers[prior].byteSize(), buffer);
            for (MemorySegment entry : new MemorySegment[] {pinEntry, resolveEntry, shellModule}) rejectAlias(entry.address(), 1, buffer);
            buffer.fill((byte) 0);
        }
        for (int index = 0; index < EXPORT.length(); index++) buffers[1].set(ValueLayout.JAVA_BYTE, index, (byte) EXPORT.charAt(index));
        buffers[3].fill((byte) 0x7f);
    }

    private void resolveAndPin() throws Throwable {
        requireOriginal();
        nativeReturnUnconfirmed = true;
        // Actual GPA return, not copied export RVA. Trusted OS startup covers possible forwarder processing.
        rawEntry = (long) resolveCall.invokeExact(buffers[0], shellModule, buffers[1]);
        nativeReturnUnconfirmed = false;
        lastErrors[0] = buffers[0].get(ValueLayout.JAVA_INT, errorOffset);
        if (rawEntry <= 65_535 || rawEntry != expectedTarget) throw new IllegalStateException("Actual known-folder export differs from its original cohort");
        for (MemorySegment buffer : buffers) rejectAlias(rawEntry, 1, buffer);
        resolvedEntry = MemorySegment.ofAddress(rawEntry).reinterpret(owner.originalArena(), null);
        requireOriginal();
        nativeReturnUnconfirmed = true;
        pinStatus = (int) pinCall.invokeExact(buffers[0], 5, resolvedEntry, buffers[2]); // PIN | FROM_ADDRESS.
        rawProvider = buffers[2].get(ValueLayout.JAVA_LONG, 0);
        nativeReturnUnconfirmed = false;
        lastErrors[1] = buffers[0].get(ValueLayout.JAVA_INT, errorOffset);
        if (pinStatus == 0 || rawProvider != provider.originalModuleBits()) throw new IllegalStateException("Known-folder physical provider differs");
        folderCall = owner.originalLinker().downcallHandle(resolvedEntry, FunctionDescriptor.of(ValueLayout.JAVA_INT,
            ValueLayout.ADDRESS, ValueLayout.JAVA_INT, ValueLayout.ADDRESS, ValueLayout.JAVA_INT, ValueLayout.ADDRESS));
    }

    private void callFolder() throws Throwable {
        requireOriginal();
        invokeFolder();
    }

    /** Exact fixed call, separately exercised with inert private frames; no production injection entry. */
    private void invokeFolder() throws Throwable {
        if (Thread.currentThread() != thread || !attempted) throw new IllegalStateException("Known-folder call lacks original thread/attempt");
        if (callAttempted || frameRetired || nativeReturnUnconfirmed || folderCall == null) throw new IllegalStateException("Known-folder call is outside its original lifecycle");
        callAttempted = true;
        nativeReturnUnconfirmed = true;
        folderStatus = (int) folderCall.invokeExact(MemorySegment.NULL, 0x26, MemorySegment.NULL, 0, buffers[3]);
        nativeReturnUnconfirmed = false; // HRESULT is the result; GetLastError does not classify this call.
    }

    private static void validatePath(MemorySegment buffer, int status, String root) {
        if (status != 0 || buffer == null || buffer.byteSize() != PATH_CHARS * 2L || root == null) throw new IllegalStateException("Program Files query did not succeed completely");
        StringBuilder path = new StringBuilder();
        for (int index = 0; index < PATH_CHARS; index++) {
            int value = Short.toUnsignedInt(buffer.getAtIndex(ValueLayout.JAVA_SHORT, index));
            if (value == 0) {
                if (path.isEmpty() || !root.equalsIgnoreCase(path + "\\P2pKit Sample")) throw new IllegalStateException("Original installation is not the OS Program Files application root");
                return; // Equality to the already canonical original root also rejects aliases/relative/dot paths.
            }
            if (value < 32 || value > 126) throw new IllegalStateException("Unsupported Program Files path representation");
            path.append((char) value);
        }
        throw new IllegalStateException("Unterminated Program Files path");
    }

    private void retireFrame() {
        if (Thread.currentThread() != thread) throw new IllegalStateException("Known-folder frame belongs to another thread");
        if (frameRetired || nativeReturnUnconfirmed) return;
        frameRetired = true;
        for (int index = 0; index < buffers.length; index++) {
            if (buffers[index] != null) {
                try { buffers[index].fill((byte) 0); }
                catch (Throwable caught) { failure.clearFailures[index] = caught; }
            }
        }
        if (frameArena != null) {
            try { frameArena.close(); }
            catch (Throwable caught) { failure.arenaCloseFailure = caught; }
        }
    }
    private static void rejectAlias(long address, long size, MemorySegment buffer) {
        if (address < buffer.address() + buffer.byteSize() && buffer.address() < address + size) throw new IllegalStateException("Known-folder frame aliases original input");
    }
    boolean completed() {
        requireOriginal();
        if (!succeeded || !frameRetired || nativeReturnUnconfirmed || failure.retirementFailed()) throw new IllegalStateException("Original Program Files classification is incomplete");
        return true;
    }
}
