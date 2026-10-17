package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.MemorySegment;
import java.util.Arrays;

/**
 * Once-owned post-load comparison, NOT initial loading/installation authority or provider admission.
 * The original load retains this entire attachment before its first lookup. It composes existing fixed
 * export/readback/PE comparisons without admitting a caller's callable segments or expected addresses.
 * Prior bootstrap, actual system-file/mapping custody and productive first load still require review;
 * matching snapshots cannot exclude intervening mapping changes. Its optional fixed JNI continuation
 * retains the same original VM and verified entries; registration is not provider publication. No unload exists.
 */
final class WindowsLoadedProfileImageVerification {
    static final int PREPARE = 0;
    static final int EXPORT = 1;
    static final int READ = 2;
    static final int COMPARE = 3;
    static final int COMPLETE = 4;
    private static final String PREFIX = "Java_dev_p2pkit_sample_rpc_profile_WindowsProfileCustodyJni_";
    private static final String[] METHODS = {"abi", "capabilities", "openRoot", "child", "createChildDirectory",
        "identity", "fileIdentity", "exists", "names", "read", "lockExisting", "createProfileLock",
        "createVaultLock", "stageRecord", "prepareRecord", "writeRecord", "renameCandidate", "replaceCandidate",
        "syncDirectory", "discardStage", "requestExpectedFileDeletion", "deleteRecord", "close"};

    static final class Failure extends RuntimeException {
        private static final long serialVersionUID = 1L;
        final transient WindowsLoadedProfileImageVerification retainedVerification;
        Throwable operationFailure;

        private Failure(WindowsLoadedProfileImageVerification verification) {
            super("Loaded profile image comparison failed with original ownership retained", null, false, false);
            retainedVerification = verification;
        }
    }

    private final Thread thread = Thread.currentThread();
    private final WindowsLibraryLoadInvocation.Result load;
    private final WindowsSystemBootstrapCandidate bootstrap;
    private final WindowsPackagedVerifier plan;
    private final WindowsSystemImportResolution imports;
    private final Failure failure = new Failure(this);
    private boolean attempted;
    private boolean succeeded;
    private int phase;
    private Arena originalArena;
    private MemorySegment module;
    private WindowsOriginalJvmCandidate originalJvm;
    private Class<?> declaration;
    private long[] layout;
    private String[] names;
    private long[] rvas;
    private long[] importTargets;
    private long[] exportTargets;
    private WindowsExportLookupInvocation[] exports;
    private WindowsExportLookupInvocation.Result[] exportResults;
    private MemorySegment[] exportEntries;
    private long[] requested;
    private WindowsImageReadInvocation[] reads;
    private WindowsImageReadInvocation.Result[] readResults;
    private byte[][] pages;
    private long[] verified;
    private MemorySegment[] orderedEntries;
    private boolean registrationAttempted;
    private WindowsJvmAcquisitionInvocation.Result registrationVm;
    private WindowsJniRegistrationOwner.Retention registrationRoots;
    private long[] registrationMethods;
    private WindowsJniRegistrationInvocation registrationInvocation;
    private WindowsJniRegistrationOwner registrationOwner;
    private Throwable registrationFailure;


    WindowsLoadedProfileImageVerification(WindowsLibraryLoadInvocation.Result load,
                                         WindowsSystemBootstrapCandidate bootstrap,
                                         WindowsPackagedVerifier plan, WindowsSystemImportResolution imports) {
        // No allocation of native resources/effects or caller callbacks during attachment construction.
        this.load = load;
        this.bootstrap = bootstrap;
        this.plan = plan;
        this.imports = imports;
    }

    void verify() {
        requireThread();
        if (attempted) throw new IllegalStateException("Loaded image comparison was already attempted");
        attempted = true;
        try {
            requireOriginal();
            originalArena = bootstrap.originalLoadedImageArena(load);
            module = load.module();
            originalJvm = bootstrap.originalLoadedImageJvm(load);
            declaration = plan.declaringClass();
            layout = plan.imageLayout();
            names = plan.exportNames();
            rvas = plan.exportRvas();
            importTargets = imports == null ? plan.originalSystemImportTargets() : imports.addresses();
            if (names.length != 24 || rvas.length != 24 || layout.length != 3 ||
                importTargets.length != plan.importNames().length / 2) {
                throw new IllegalStateException("Original comparison inventory differs");
            }
            exportTargets = new long[24];
            exports = new WindowsExportLookupInvocation[24];
            exportResults = new WindowsExportLookupInvocation.Result[24];
            exportEntries = new MemorySegment[24];
            orderedEntries = new MemorySegment[24];
            phase = EXPORT;
            for (int index = 0; index < 24; index++) {
                requireOriginal();
                exports[index] = WindowsExportLookupInvocation.prepare(bootstrap, load, plan,
                    bootstrap.originalLoadedImageEntry(load, 4), originalArena, module, originalArena,
                    names[index], layout[0], layout[1], layout[2], rvas[index]);
                exportResults[index] = exports[index].invoke();
                exportEntries[index] = exportResults[index].entry();
                exportTargets[index] = exportEntries[index].address();
            }
            phase = READ;
            requested = plan.regions(module.address());
            reads = new WindowsImageReadInvocation[requested.length / 3];
            readResults = new WindowsImageReadInvocation.Result[reads.length];
            pages = new byte[reads.length][];
            for (int index = 0; index < reads.length; index++) {
                requireOriginal();
                int kind = Math.toIntExact(requested[index * 3 + 2]);
                WindowsImageReadInvocation.Kind policy = switch (kind) {
                    case 0 -> WindowsImageReadInvocation.Kind.READ_ONLY;
                    case 1 -> WindowsImageReadInvocation.Kind.EXECUTABLE;
                    case 2 -> WindowsImageReadInvocation.Kind.DATA;
                    default -> throw new IllegalStateException("Unknown original image read policy");
                };
                reads[index] = WindowsImageReadInvocation.prepare(bootstrap, load, plan,
                    bootstrap.originalLoadedImageEntry(load, 6), bootstrap.originalLoadedImageEntry(load, 7),
                    originalArena, module, originalArena, layout[0], requested[index * 3] - module.address(),
                    Math.toIntExact(requested[index * 3 + 1]), policy);
                readResults[index] = reads[index].invoke();
                pages[index] = readResults[index].bytes();
            }
            phase = COMPARE;
            requireOriginal();
            verified = plan.verify(module.address(), exportTargets, importTargets, pages);
            bindOriginalEntries();
            requireOriginal();
            phase = COMPLETE;
            succeeded = true;
        } catch (Throwable caught) {
            failure.operationFailure = caught;
            // Child failures themselves retain original scopes, raw results and uncertain private frames.
            // The original process load permanently retains this complete/partial graph; never retry/unload.
            throw failure;
        }
    }

    private void bindOriginalEntries() {
        if (verified.length != 24 || declaration != plan.declaringClass()) {
            throw new IllegalStateException("Original JNI comparison result differs");
        }
        for (int index = 0; index < 24; index++) {
            String expected = index == 23 ? "pwp_jni_register_once" : PREFIX + METHODS[index];
            int slot = -1;
            for (int candidate = 0; candidate < 24; candidate++) {
                if (names[candidate].equals(expected)) {
                    if (slot >= 0) throw new IllegalStateException("Original JNI export name is duplicated");
                    slot = candidate;
                }
            }
            if (slot < 0 || exportResults[slot].entry() != exportEntries[slot] ||
                exportEntries[slot].address() != verified[index] ||
                !exportEntries[slot].scope().equals(originalArena.scope())) {
                throw new IllegalStateException("JNI comparison does not identify an original scoped export");
            }
            orderedEntries[index] = exportEntries[slot]; // Preserve original views; never recreate from numeric results.
        }
    }

    private void requireThread() {
        if (Thread.currentThread() != thread || thread.isVirtual()) {
            throw new IllegalStateException("Loaded image comparison requires its original platform thread");
        }
    }

    private void requireOriginal() {
        requireThread();
        if (load == null || bootstrap == null || plan == null) {
            throw new IllegalStateException("Missing original loaded image chain");
        }
        load.requireOriginalVerification(this);
        bootstrap.requireOriginalLoadedImage(load);
        if (imports == null) {
            plan.requireOriginalImportBootstrap(bootstrap);
            plan.requireOriginalLoadedFile(load);
        }
        else {
            plan.requireDevelopmentImportComparison();
            imports.requireOriginalBinding(bootstrap, plan);
        }
    }

    private void requireSucceeded() {
        requireOriginal();
        if (!succeeded || failure.operationFailure != null || phase != COMPLETE) {
            throw new IllegalStateException("Loaded profile image is not completely verified");
        }
    }

    /** Exact original VM/class/23 views/registrar only; no caller-selected address or replacement owner. */
    WindowsJniRegistrationOwner registerOriginalJni() {
        requireSucceeded();
        if (registrationAttempted) throw new IllegalStateException("Original image JNI registration was already attempted");
        registrationAttempted = true; // Reserve under the permanent load/image root before any acquisition/allocation.
        try {
            registrationVm = originalJvm.originalVirtualMachineFor(this);
            registrationRoots = new WindowsJniRegistrationOwner.Retention(this, originalJvm, load, declaration, plan);
            registrationMethods = new long[23];
            for (int index = 0; index < registrationMethods.length; index++) {
                MemorySegment entry = orderedEntries[index];
                if (!entry.scope().isAlive() || !entry.scope().equals(originalArena.scope()) ||
                    !entry.isAccessibleBy(thread)) {
                    throw new IllegalStateException("Original JNI entry scope is no longer live");
                }
                registrationMethods[index] = entry.address();
            }
            requireSucceeded();
            registrationInvocation = WindowsJniRegistrationInvocation.prepare(registrationRoots, orderedEntries[23],
                registrationVm.virtualMachine(), registrationMethods);
            registrationOwner = WindowsJniRegistrationOwner.registerOnce(registrationRoots, registrationInvocation);
            if (registrationOwner.state() != WindowsJniRegistrationOwner.State.Registered ||
                registrationOwner.retention != registrationRoots || !registrationOwner.ownsInvocation(registrationInvocation)) {
                throw new IllegalStateException("Original JNI owner did not complete its exact registration");
            }
            requireSucceeded();
            return registrationOwner;
        } catch (Throwable caught) {
            registrationFailure = caught;
            if (caught instanceof WindowsJniRegistrationOwner.Failure nativeFailure) {
                registrationOwner = nativeFailure.retainedOwner;
            }
            failure.operationFailure = caught; // Seal every image getter and all future registration attempts.
            // No speculative retirement on an ambiguous controller return. The retained native owner's
            // own known-return policy governs its frame; pre-controller failures retain this prepared frame.
            throw failure;
        }
    }

    Class<?> declaringClass() { requireSucceeded(); return declaration; }
    WindowsOriginalJvmCandidate originalJvm() { requireSucceeded(); return originalJvm; }
    MemorySegment[] jniEntries() { requireSucceeded(); return Arrays.copyOf(orderedEntries, 23); }
    MemorySegment registrar() { requireSucceeded(); return orderedEntries[23]; }
}
