package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.Linker;
import java.lang.foreign.MemorySegment;
import java.nio.file.LinkOption;
import java.nio.file.Files;
import java.nio.file.Path;
import java.io.InputStream;
import java.util.HexFormat;

/**
 * Closed installation -> original JVM/file -> pinned profile bytes -> typed pre-load preparation.
 * Conditional on trusted OS/JVM/application startup and independently qualified installed package bytes.
 * The closed original registration continuation accepts no supplied path/pin/token or replacement owner.
 * No public installed-provider availability or qualification follows from these dormant methods.
 */
final class WindowsInstalledProfileCandidate {
    static final class Failure extends RuntimeException {
        private static final long serialVersionUID = 1L;
        final transient WindowsInstalledProfileCandidate retainedCandidate;
        Throwable operationFailure;
        private Failure(WindowsInstalledProfileCandidate candidate) {
            super("Installed profile preparation failed with original ownership retained", null, false, false);
            retainedCandidate = candidate;
        }
    }

    private final Thread thread = Thread.currentThread();
    private final WindowsOriginalInstallationCandidate installation;
    private final Failure failure = new Failure(this);
    private WindowsOriginalSystemModulesCandidate systems;
    private WindowsOriginalProgramFilesCandidate programFiles;
    private WindowsOriginalJvmCandidate jvm;
    private WindowsOriginalJvmFileCandidate jvmFile;
    private WindowsOriginalJvmSecurityCandidate jvmSecurity;
    private WindowsOriginalJvmAncestorsCandidate jvmAncestors;
    private WindowsOriginalProfileDllFileCandidate profile;
    private WindowsOriginalProfileDllSecurityCandidate profileSecurity;
    private WindowsOriginalProfileDllAncestorsCandidate profileAncestors;
    private WindowsOriginalProfileDllBytesCandidate bytes;
    private WindowsInstalledParentPin parentPin;
    private byte[] manifest;
    private WindowsPackagedVerifier packaged;
    private WindowsLibraryLoadInvocation load;
    private WindowsLibraryLoadInvocation.Result loadResult;
    private WindowsLoadedProfileImageVerification imageVerification;
    private WindowsJniRegistrationOwner registrationOwner;
    private WindowsOriginalIpInterfaces ipInterfaces;
    private boolean attempted;
    private boolean profileAttempted;
    private boolean inputsReady;
    private boolean prepared;
    private boolean registrationAttempted;
    private boolean failed;
    private int diagnosticPhase; // Does not confer authority or change any admission/cleanup transition.

    WindowsInstalledProfileCandidate(WindowsOriginalInstallationCandidate installation) {
        this.installation = installation;
    }

    void prepare() {
        requireOriginal();
        if (attempted) throw new IllegalStateException("Installed preparation is already consumed");
        attempted = true;
        try {
            diagnosticPhase = 1;
            systems = originalBootstrap().inspectOriginalSystemModules();
            systems.requireOriginalExportGraph();
            diagnosticPhase = 2;
            programFiles = new WindowsOriginalProgramFilesCandidate(this);
            programFiles.observe();
            diagnosticPhase = 3;
            parentPin = WindowsInstalledParentPin.read(this);
            diagnosticPhase = 4;
            jvm = originalBootstrap().inspectOriginalJvm();
            diagnosticPhase = 5;
            jvmFile = jvm.inspectFile();
            jvmFile.requireInstalledPath(this);
            diagnosticPhase = 6;
            jvmSecurity = jvmFile.inspectSecurity();
            if (!jvmSecurity.descriptorPolicyAccepted()) throw new IllegalStateException("Original installed JVM leaf policy refused");
            diagnosticPhase = 7;
            jvmAncestors = jvmSecurity.inspectAncestors();
            requireJvmJoin();
            diagnosticPhase = 8;
            profileAttempted = true;
            originalBootstrap().inspectInstalledProfileDll(this);
            diagnosticPhase = 9;
            profileSecurity = profile.inspectSecurity();
            if (!profileSecurity.descriptorPolicyAccepted()) throw new IllegalStateException("Original installed profile leaf policy refused");
            diagnosticPhase = 10;
            profileAncestors = profileSecurity.inspectAncestors();
            profileAncestors.requireInstallationRoot(this);
            diagnosticPhase = 11;
            bytes = profile.inspectBytes();
            diagnosticPhase = 12;
            manifest = readManifest(Path.of(originalRoot()).resolve("app/resources/rpc-profile/windows-x64/component.manifest"));
            if (!HexFormat.of().formatHex(bytes.sha256()).equals(parentPin.dllSha256())) {
                throw new IllegalStateException("Original profile DLL differs from the trusted application parent pin");
            }
            diagnosticPhase = 13;
            packaged = bytes.inspectPackagedBytes(manifest, parentPin.manifestSha256(), parentPin.source(), parentPin.tree());
            diagnosticPhase = 19;
            systems.prepareApiSetNamespace();
            diagnosticPhase = 14;
            packaged.prepareOriginalSystemImports();
            diagnosticPhase = 20;
            systems.finishApiSetRoutes();
            diagnosticPhase = 15;
            inputsReady = true;
            WindowsLibraryLoadInvocation.prepareInstalled(this); // Attaches load before its private frame effects.
            prepared = true;
        } catch (Throwable caught) {
            failure.operationFailure = caught;
            failed = true;
            throw failure;
        }
    }

    /** Complete only this retained original chain; registration is not complete provider qualification. */
    WindowsJniRegistrationOwner registerOriginalProfile() {
        requireOriginal();
        if (registrationAttempted) throw new IllegalStateException("Installed profile registration is already consumed");
        prepared();
        registrationAttempted = true;
        try {
            // Each existing process-rooted parent attaches its child before the child's native effects.
            // Never recreate a module view, choose another import plan, or enter the development overload.
            diagnosticPhase = 16;
            loadResult = load.invoke();
            diagnosticPhase = 17;
            imageVerification = loadResult.verifyImage(originalBootstrap(), packaged);
            diagnosticPhase = 18;
            registrationOwner = imageVerification.registerOriginalJni();
            if (registrationOwner.state() != WindowsJniRegistrationOwner.State.Registered) {
                throw new IllegalStateException("Original installed registration did not complete");
            }
            return registrationOwner;
        } catch (Throwable caught) {
            failure.operationFailure = caught;
            failed = true;
            // Deeper failure carriers and permanent load/image/JNI roots retain partial original owners.
            // No speculative frame retirement, unload, retry or conversion to no-effects Unavailable.
            throw failure;
        }
    }

    /** Read stored stage only; failed confined/native owners are never dereferenced by this diagnostic. */
    String failureOperation() {
        return switch (diagnosticPhase) {
            case 1 -> systemFailureOperation();
            case 2 -> "PROFILE_KNOWN_FOLDER";
            case 3 -> "PROFILE_PARENT_PIN";
            case 4 -> "PROFILE_JVM_IMAGE";
            case 5 -> "PROFILE_JVM_FILE";
            case 6 -> "PROFILE_JVM_SECURITY";
            case 7 -> "PROFILE_JVM_ANCESTORS";
            case 8 -> "PROFILE_FILE";
            case 9 -> "PROFILE_SECURITY";
            case 10 -> "PROFILE_ANCESTORS";
            case 11 -> "PROFILE_BYTES";
            case 12 -> "PROFILE_MANIFEST";
            case 13 -> "PROFILE_PACKAGE";
            case 14 -> systems == null ? "PROFILE_IMPORTS" : systems.importFailureOperation();
            case 15 -> "PROFILE_PREPARE_LOAD";
            case 16 -> "PROFILE_LOAD_IMAGE";
            case 17 -> "PROFILE_VERIFY_IMAGE";
            case 18 -> "PROFILE_REGISTER_JNI";
            case 19, 20 -> systems == null ? "API_SET_PRECONDITION" : systems.apiSetFailureOperation();
            default -> "PROFILE_PRECONDITION";
        };
    }

    private String systemFailureOperation() {
        // inspectOriginalSystemModules() can throw before assigning systems. Its exact typed carrier
        // already retains the original collection; never re-enter the bootstrap to find or retry it.
        if (failure.operationFailure instanceof WindowsOriginalSystemModulesCandidate.Failure original) {
            return original.retainedCandidate.failureOperation();
        }
        return systems == null ? "PROFILE_SYSTEM_MODULES" : systems.failureOperation();
    }

    private static byte[] readManifest(Path path) throws Exception {
        // Untrusted bounded comparison data only; the independent application parent pin authenticates it.
        if (!Files.isRegularFile(path, LinkOption.NOFOLLOW_LINKS)) throw new IllegalStateException("Missing ordinary component manifest");
        try (InputStream stream = Files.newInputStream(path, LinkOption.NOFOLLOW_LINKS)) {
            byte[] data = stream.readNBytes(4097);
            if (data.length == 0 || data.length > 4096) throw new IllegalStateException("Unbounded component manifest");
            return data;
        }
    }

    private void requireOriginal() {
        if (Thread.currentThread() != thread || installation == null) throw new IllegalStateException("Installed preparation lacks its original thread/installation");
        installation.requireOriginalProfile(this);
        if (failed) throw failure;
    }

    String originalRoot() { requireOriginal(); return installation.originalRoot(this); }
    String fixedJvmPath() { return originalRoot() + "\\runtime\\bin\\server\\jvm.dll"; }
    String fixedProfilePath() { requireReadyForProfile(); return originalRoot() + "\\app\\resources\\rpc-profile\\windows-x64\\p2pkit-windows-profile.dll"; }
    WindowsSystemBootstrapCandidate originalBootstrap() { requireOriginal(); return installation.originalBootstrap(this); }
    Linker originalLinker() { requireOriginal(); return installation.originalLinker(); }
    Arena originalArena() { requireOriginal(); return installation.originalBootstrapArena(); }
    MemorySegment resolverEntry(int index) { requireOriginal(); return originalBootstrap().originalInstalledResolverEntry(this, index); }

    void requireOriginalKnownFolder(WindowsOriginalProgramFilesCandidate candidate) {
        requireOriginal();
        if (!attempted || candidate == null || candidate != programFiles || systems == null) throw new IllegalStateException("Known-folder query is not the original retained child");
        systems.requireOriginalBootstrap(originalBootstrap());
        systems.requireOriginalExportGraph();
    }
    WindowsOriginalSystemModulesCandidate originalSystems(WindowsOriginalProgramFilesCandidate candidate) {
        requireOriginalKnownFolder(candidate); return systems;
    }
    WindowsOriginalIpInterfaces prepareIpInterfaces() {
        requireOriginal();
        if (ipInterfaces != null || registrationOwner == null ||
            registrationOwner.state() != WindowsJniRegistrationOwner.State.Registered) {
            throw new IllegalStateException("IP observation requires original installed registration");
        }
        ipInterfaces = new WindowsOriginalIpInterfaces(this);
        ipInterfaces.prepare();
        return ipInterfaces;
    }
    void requireOriginalIpInterfaces(WindowsOriginalIpInterfaces candidate) {
        requireOriginal();
        if (candidate == null || candidate != ipInterfaces || systems == null) {
            throw new IllegalStateException("IP observation lacks its original installation parent");
        }
        systems.requireOriginalExportGraph();
    }
    WindowsOriginalSystemModulesCandidate originalIpSystems(WindowsOriginalIpInterfaces candidate) {
        requireOriginalIpInterfaces(candidate); return systems;
    }
    void requireOriginalJvmFile(WindowsOriginalJvmFileCandidate candidate) {
        requireOriginal();
        if (jvm == null || candidate == null || candidate != jvmFile) throw new IllegalStateException("Installed JVM file attachment differs");
        originalBootstrap().requireOriginalJvm(jvm);
        jvm.requireOriginalFile(candidate);
    }
    void requireOriginalJvmAncestors(WindowsOriginalJvmAncestorsCandidate candidate) {
        requireOriginalJvmFile(jvmFile);
        if (candidate == null || candidate != jvmAncestors || jvmSecurity == null || !jvmSecurity.descriptorPolicyAccepted()) {
            throw new IllegalStateException("Installed JVM ancestors lack the original accepted leaf");
        }
        jvmFile.requireOriginalSecurity(jvmSecurity);
        jvmSecurity.requireOriginalAncestors(candidate);
    }
    private void requireJvmJoin() {
        requireOriginalJvmFile(jvmFile);
        jvmFile.requireInstalledPath(this);
        requireOriginalJvmAncestors(jvmAncestors);
        jvmAncestors.requireInstallationRoot(this);
    }
    void requireReadyForProfile() {
        requireOriginal();
        if (!attempted || programFiles == null || !programFiles.completed() || parentPin == null) throw new IllegalStateException("Installed profile lacks original Program Files classification/parent pin");
        requireJvmJoin();
    }
    void attachOriginalProfile(WindowsOriginalProfileDllFileCandidate candidate) {
        requireReadyForProfile();
        if (!profileAttempted || profile != null || candidate == null) throw new IllegalStateException("Installed profile attachment is consumed");
        profile = candidate;
    }
    void requireOriginalProfileFile(WindowsOriginalProfileDllFileCandidate candidate) {
        requireReadyForProfile();
        if (!profileAttempted || candidate == null || candidate != profile) throw new IllegalStateException("Profile file is not the original installed attachment");
    }
    void requireOriginalProfileAncestors(WindowsOriginalProfileDllAncestorsCandidate candidate) {
        requireOriginalProfileFile(profile);
        if (candidate == null || candidate != profileAncestors || profileSecurity == null || !profileSecurity.descriptorPolicyAccepted()) {
            throw new IllegalStateException("Installed profile ancestors lack the original accepted leaf");
        }
        profile.requireOriginalSecurity(profileSecurity);
        profileSecurity.requireOriginalAncestors(candidate);
    }
    void joinRoot(WindowsOriginalFileAncestorsLease member) { requireOriginal(); installation.requireRootJoin(this, member); }

    void requirePreparedInputs() {
        requireReadyForProfile();
        if (!inputsReady || bytes == null || !bytes.completed() || packaged == null || manifest == null) throw new IllegalStateException("Installed pre-load inputs are incomplete");
        profile.requireInstalledOwner(this);
        profile.requireOriginalBytes(bytes);
        profileAncestors.requireInstallationRoot(this);
        packaged.requireInstalledPreparation(bytes);
        systems.requireSealedApiSetRoutes();
    }
    void requireOriginalPackagedPlan(WindowsPackagedVerifier candidate) {
        requirePreparedInputs();
        if (candidate == null || candidate != packaged) throw new IllegalStateException("Installed image verification substituted its original byte plan");
    }
    WindowsOriginalInstallationCandidate originalInstallation() { requirePreparedInputs(); return installation; }
    WindowsOriginalJvmCandidate originalJvm() { requirePreparedInputs(); return jvm; }
    WindowsOriginalProfileDllFileCandidate originalProfile() { requirePreparedInputs(); return profile; }
    void attachOriginalLoad(WindowsLibraryLoadInvocation candidate) {
        requirePreparedInputs();
        if (load != null || candidate == null) throw new IllegalStateException("Installed load preparation is already attached");
        load = candidate;
    }
    void requireOriginalLoad(WindowsLibraryLoadInvocation candidate) {
        requirePreparedInputs();
        if (candidate == null || candidate != load || candidate.installationOwner != installation ||
            candidate.runtimeOwner != jvm || candidate.fileOwner != profile) throw new IllegalStateException("Load is not the original installed input chain");
    }
    boolean prepared() { requirePreparedInputs(); if (!prepared || load == null) throw new IllegalStateException("Installed load is not prepared"); return true; }
}
