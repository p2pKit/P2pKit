package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.FunctionDescriptor;
import java.lang.foreign.Linker;
import java.lang.foreign.MemoryLayout;
import java.lang.foreign.MemorySegment;
import java.lang.foreign.ValueLayout;
import java.lang.invoke.MethodHandle;
import java.util.Arrays;
import java.util.Locale;

/**
 * Dormant read-only original process-launcher/ancestor custody candidate under trusted OS/JVM startup.
 * GetModuleFileNameW(NULL) supplies a locator, NOT mapped-section identity or historical immutability.
 * Recognized package layout and retained owner/DACL observations do not prove Program Files, MSI identity,
 * installed bytes, pre-JVM safety or effective standard-user protection. No file bytes, DLL/profile load,
 * JNI registration, arbitrary path factory or productive provider continuation is exposed here.
 */
final class WindowsOriginalInstallationCandidate {
    private static final int PATH_CHARS = 1024;
    private static final String PACKAGE = "P2pKit Sample";
    private static final String LAUNCHER = PACKAGE + ".exe";
    private static final MemoryLayout PATH = MemoryLayout.sequenceLayout(PATH_CHARS, ValueLayout.JAVA_SHORT);

    static final class Failure extends RuntimeException {
        private static final long serialVersionUID = 1L;
        final transient WindowsOriginalInstallationCandidate retainedCandidate;
        Throwable operationFailure;
        final Throwable[] clearFailures = new Throwable[2];
        Throwable arenaCloseFailure;

        private Failure(WindowsOriginalInstallationCandidate candidate) {
            super("Original installation custody failed with ownership retained", null, false, false);
            retainedCandidate = candidate;
        }

        private boolean retirementFailed() {
            if (arenaCloseFailure != null) return true;
            for (Throwable caught : clearFailures) if (caught != null) return true;
            return false;
        }
    }

    private final Thread thread = Thread.currentThread();
    private final WindowsSystemBootstrapCandidate bootstrap;
    private final Failure failure = new Failure(this);
    private final MemorySegment[] buffers = new MemorySegment[2]; // Original executable path and captured error.
    private Arena frameArena;
    private MethodHandle pathCall;
    private long errorOffset;
    private int pathReturn;
    private int lastError;
    private boolean errorObserved;
    private boolean nativeReturnUnconfirmed;
    private boolean frameRetired;
    private boolean pathCallAttempted;
    private boolean attempted;
    private boolean failed;
    private boolean observationCompleted;
    private char[] originalPath;
    private char[] originalRoot;
    private boolean fileAttempted;
    private boolean fileObserved;
    private boolean securityAttempted;
    private boolean securityObserved;
    private boolean ancestorsAttempted;
    private boolean ancestorsObserved;
    private boolean leafPolicyRefused;
    private boolean ancestorPolicyRefused;
    private WindowsOriginalFileLease file;
    private WindowsOriginalFileSecurityQuery security;
    private WindowsOriginalFileAncestorsLease ancestors;

    WindowsOriginalInstallationCandidate(WindowsSystemBootstrapCandidate bootstrap) { this.bootstrap = bootstrap; }

    void observe() {
        requireOriginalBootstrap();
        if (attempted) throw new IllegalStateException("Original installation observation is already consumed");
        attempted = true;
        try {
            observePath();
            fileAttempted = true;
            file = WindowsOriginalFileLease.forInstallation(this);
            // The exact shared core/failure is attached before CreateFileW and every following stage.
            file.observe();
            file.completed();
            fileObserved = true;
            securityAttempted = true;
            security = file.newInstallationSecurity(this);
            security.observe();
            leafPolicyRefused = !security.descriptorPolicyAccepted();
            securityObserved = true;
            if (!leafPolicyRefused) {
                ancestorsAttempted = true;
                ancestors = security.newInstallationAncestors(this);
                ancestors.observe();
                ancestorPolicyRefused = !ancestors.descriptorPoliciesAccepted();
                ancestorsObserved = true;
            }
            // A negative policy is a completed diagnostic, never accepted custody or native authority.
            observationCompleted = true;
        } catch (Throwable caught) {
            failure.operationFailure = caught;
            failed = true;
            throw failure;
        }
    }

    private void observePath() throws Throwable {
        requireOriginalNativeInputs();
        try {
            prepareFrame();
            callOriginalPath();
            lastError = buffers[1].get(ValueLayout.JAVA_INT, errorOffset);
            errorObserved = true; // Successful GetModuleFileNameW may leave stale last-error state.
            originalPath = validatePath(buffers[0], pathReturn);
            originalRoot = Arrays.copyOf(originalPath, originalPath.length - LAUNCHER.length() - 1);
            originalRoot[originalRoot.length - 1] = 0; // Replace the original separator with NUL.
        } finally {
            retireFrame();
        }
        if (!frameRetired || nativeReturnUnconfirmed || failure.retirementFailed()) {
            throw new IllegalStateException("Original launcher path frame did not retire completely");
        }
    }

    private void prepareFrame() {
        requireOriginalNativeInputs();
        Linker linker = bootstrap.originalInstallationLinker(this);
        Arena originalArena = bootstrap.originalInstallationArena(this);
        MemorySegment entry = bootstrap.originalInstallationPathEntry(this);
        if (entry == null || !entry.isNative() || entry.byteSize() != 0 || entry.address() <= 65_535 ||
            entry.address() > Long.MAX_VALUE - 1 || !entry.scope().equals(originalArena.scope()) ||
            !entry.isAccessibleBy(thread)) {
            throw new IllegalStateException("Original launcher path lost its fixed system entry");
        }
        MemoryLayout state = Linker.Option.captureStateLayout();
        MemoryLayout error = state.select(MemoryLayout.PathElement.groupElement("GetLastError"));
        errorOffset = state.byteOffset(MemoryLayout.PathElement.groupElement("GetLastError"));
        if (!(error instanceof ValueLayout.OfInt) || error.byteSize() != 4 || error.byteAlignment() != 4 ||
            state.byteSize() < 4 || state.byteSize() > 64 || errorOffset < 0 || errorOffset % 4 != 0 ||
            errorOffset > state.byteSize() - 4) {
            throw new IllegalStateException("Unsupported original launcher captured-error layout");
        }
        FunctionDescriptor descriptor = FunctionDescriptor.of(ValueLayout.JAVA_INT, ValueLayout.ADDRESS,
            ValueLayout.ADDRESS.withTargetLayout(PATH), ValueLayout.JAVA_INT);
        pathCall = linker.downcallHandle(entry, descriptor, Linker.Option.captureCallState("GetLastError"));
        frameArena = Arena.ofConfined();
        buffers[0] = frameArena.allocate(PATH);
        buffers[1] = frameArena.allocate(state);
        for (int index = 0; index < buffers.length; index++) {
            MemorySegment buffer = buffers[index];
            long size = index == 0 ? PATH.byteSize() : state.byteSize();
            int alignment = index == 0 ? 2 : 4;
            if (!buffer.isNative() || buffer.byteSize() != size || buffer.address() <= 65_535 ||
                buffer.address() > Long.MAX_VALUE - size || buffer.address() % alignment != 0 ||
                !buffer.scope().equals(frameArena.scope()) || !buffer.isAccessibleBy(thread) ||
                overlap(entry.address(), 1, buffer.address(), size)) {
                throw new IllegalStateException("Invalid private launcher path frame");
            }
        }
        if (overlap(buffers[0].address(), buffers[0].byteSize(), buffers[1].address(), buffers[1].byteSize())) {
            throw new IllegalStateException("Original launcher observation frames overlap");
        }
        buffers[0].fill((byte) 0x7f);
    }

    private void callOriginalPath() throws Throwable {
        requireOriginalNativeInputs();
        if (!attempted || frameArena == null || frameRetired || nativeReturnUnconfirmed || pathCallAttempted) {
            throw new IllegalStateException("Original launcher path call is unavailable or consumed");
        }
        pathCallAttempted = true;
        nativeReturnUnconfirmed = true;
        // NULL selects this process's original executable; never a caller-selected HMODULE/path.
        pathReturn = (int) pathCall.invokeExact(buffers[1], MemorySegment.NULL, buffers[0], PATH_CHARS);
        nativeReturnUnconfirmed = false;
    }

    private static char[] validatePath(MemorySegment buffer, int returned) {
        long count = Integer.toUnsignedLong(returned);
        if (count == 0 || count >= PATH_CHARS || buffer == null || buffer.byteSize() != PATH.byteSize() ||
            Short.toUnsignedInt(buffer.getAtIndex(ValueLayout.JAVA_SHORT, count)) != 0) {
            throw new IllegalStateException("Original launcher path is incomplete");
        }
        char[] path = new char[(int) count + 1];
        for (int index = 0; index < count; index++) {
            char value = (char) Short.toUnsignedInt(buffer.getAtIndex(ValueLayout.JAVA_SHORT, index));
            if (value < 32 || value > 126) throw new IllegalStateException("Unsupported launcher path representation");
            path[index] = value;
        }
        String text = new String(path, 0, (int) count);
        if (!text.matches("[A-Za-z]:\\\\[A-Za-z0-9 ._\\\\-]+") ||
            !text.endsWith("\\" + PACKAGE + "\\" + LAUNCHER)) {
            throw new IllegalStateException("Not the maintained original launcher layout");
        }
        String[] components = text.substring(3).split("\\\\", -1);
        if (components.length < 2 || components.length >= 64) {
            throw new IllegalStateException("Original launcher path component count is unsupported");
        }
        for (String component : components) {
            if (component.isEmpty() || component.length() > 255 ||
                !component.matches("[A-Za-z0-9][A-Za-z0-9 ._-]*") || component.endsWith(".") ||
                component.endsWith(" ")) {
                throw new IllegalStateException("Original launcher component is noncanonical");
            }
            String stem = component.split("\\.", 2)[0].stripTrailing().toUpperCase(Locale.ROOT);
            if (stem.equals("CON") || stem.equals("PRN") || stem.equals("AUX") || stem.equals("NUL") ||
                stem.matches("(?:COM|LPT)[1-9]")) {
                throw new IllegalStateException("Original launcher component is reserved");
            }
        }
        return path;
    }

    private static boolean overlap(long first, long count, long second, long size) {
        return first < second + size && second < first + count;
    }

    private void retireFrame() {
        if (Thread.currentThread() != thread) throw new IllegalStateException("Wrong launcher frame owner thread");
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

    private void requireOriginalBootstrap() {
        if (Thread.currentThread() != thread || bootstrap == null) {
            throw new IllegalStateException("Original installation requires its original platform thread/bootstrap");
        }
        bootstrap.requireOriginalInstallation(this);
        if (failed) throw failure;
    }

    void requireOriginalNativeInputs() {
        requireOriginalBootstrap();
        if (leafPolicyRefused || ancestorPolicyRefused || nativeReturnUnconfirmed) {
            throw new IllegalStateException("Original installation observation refused further native inputs");
        }
    }

    private void requirePathObserved() {
        requireOriginalBootstrap();
        if (!attempted || !pathCallAttempted || !errorObserved || !frameRetired || nativeReturnUnconfirmed ||
            failure.retirementFailed() || originalPath == null || originalRoot == null) {
            throw new IllegalStateException("Original launcher path has no complete retained observation");
        }
    }

    void requireOriginalFileLease(WindowsOriginalFileLease candidate) {
        requirePathObserved();
        if (!fileAttempted || candidate == null || candidate != file) {
            throw new IllegalStateException("Installation file core is not its original retained attachment");
        }
    }

    private void requireFileCompleted() {
        requirePathObserved();
        if (!fileObserved || file == null) throw new IllegalStateException("Original installation file is incomplete");
        file.completed();
    }

    void requireOriginalQuery(WindowsOriginalFileSecurityQuery candidate) {
        requireFileCompleted();
        if (!securityAttempted || candidate == null || candidate != security) {
            throw new IllegalStateException("Installation query core is not its original retained attachment");
        }
    }

    void requireOriginalAncestorInputs() {
        requireFileCompleted();
        requireOriginalNativeInputs();
        if (!securityObserved || security == null || !security.descriptorPolicyAccepted()) {
            throw new IllegalStateException("Installation ancestors require original accepted leaf policy");
        }
    }

    WindowsOriginalFileAncestorsLease newOriginalAncestors(WindowsOriginalFileSecurityQuery candidate,
        Arena moduleArena, MemorySegment module, MemorySegment queryEntry, MemorySegment pinEntry,
        MemorySegment resolveEntry) {
        requireOriginalQuery(candidate);
        requireOriginalAncestorInputs();
        return file.newInstallationAncestors(this, candidate, moduleArena, module, queryEntry, pinEntry, resolveEntry);
    }

    void requireOriginalAncestors(WindowsOriginalFileAncestorsLease candidate) {
        requireFileCompleted();
        if (!ancestorsAttempted || candidate == null || candidate != ancestors || !securityObserved || security == null) {
            throw new IllegalStateException("Installation ancestor core is not its original retained attachment");
        }
        security.completed(); // Prior stage only; negative ancestor observations remain readable.
    }

    Linker originalLinker() { requireOriginalNativeInputs(); return bootstrap.originalInstallationLinker(this); }
    Arena originalBootstrapArena() { requireOriginalNativeInputs(); return bootstrap.originalInstallationArena(this); }
    MemorySegment originalFileEntry(int index) {
        requireOriginalNativeInputs(); return bootstrap.originalInstallationFileEntry(this, index);
    }
    char[] originalPathSnapshot() {
        requirePathObserved(); requireOriginalNativeInputs(); return originalPath.clone();
    }
    MemorySegment originalSecurityEntry(WindowsOriginalFileLease candidate, int index) {
        requireOriginalFileLease(candidate); requireOriginalNativeInputs();
        return bootstrap.originalInstallationSecurityEntry(this, index);
    }
    MemorySegment originalAncestorsEntry(WindowsOriginalFileLease candidate, int index) {
        requireOriginalFileLease(candidate); requireOriginalAncestorInputs();
        return bootstrap.originalInstallationAncestorsEntry(this, index);
    }

    boolean completed() {
        requireFileCompleted();
        if (!observationCompleted || !securityObserved || security == null ||
            !leafPolicyRefused && (!ancestorsObserved || ancestors == null)) {
            throw new IllegalStateException("Original installation diagnostic is incomplete");
        }
        security.completed();
        if (ancestorsObserved) ancestors.completed();
        return true;
    }

    boolean custodyAccepted() {
        completed();
        return !leafPolicyRefused && !ancestorPolicyRefused && ancestorsObserved;
    }

    int retainedDirectoryCount() {
        completed();
        return ancestorsObserved ? ancestors.ancestorCount() : 0;
    }
}
