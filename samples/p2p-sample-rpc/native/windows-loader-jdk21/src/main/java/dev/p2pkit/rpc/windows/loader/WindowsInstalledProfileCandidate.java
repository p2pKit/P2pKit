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
    private boolean attempted;
    private boolean profileAttempted;
    private boolean inputsReady;
    private boolean prepared;
    private boolean registrationAttempted;
    private boolean failed;

    WindowsInstalledProfileCandidate(WindowsOriginalInstallationCandidate installation) {
        this.installation = installation;
    }

    void prepare() {
        requireOriginal();
        if (attempted) throw new IllegalStateException("Installed preparation is already consumed");
        attempted = true;
        try {
            systems = originalBootstrap().inspectOriginalSystemModules();
            systems.requireOriginalExportGraph();
            programFiles = new WindowsOriginalProgramFilesCandidate(this);
            programFiles.observe();
            parentPin = WindowsInstalledParentPin.read(this);
            jvm = originalBootstrap().inspectOriginalJvm();
            jvmFile = jvm.inspectFile();
            jvmFile.requireInstalledPath(this);
            jvmSecurity = jvmFile.inspectSecurity();
            if (!jvmSecurity.descriptorPolicyAccepted()) throw new IllegalStateException("Original installed JVM leaf policy refused");
            jvmAncestors = jvmSecurity.inspectAncestors();
            requireJvmJoin();
            profileAttempted = true;
            originalBootstrap().inspectInstalledProfileDll(this);
            profileSecurity = profile.inspectSecurity();
            if (!profileSecurity.descriptorPolicyAccepted()) throw new IllegalStateException("Original installed profile leaf policy refused");
            profileAncestors = profileSecurity.inspectAncestors();
            profileAncestors.requireInstallationRoot(this);
            bytes = profile.inspectBytes();
            manifest = readManifest(Path.of(originalRoot()).resolve("app/resources/rpc-profile/windows-x64/component.manifest"));
            if (!HexFormat.of().formatHex(bytes.sha256()).equals(parentPin.dllSha256())) {
                throw new IllegalStateException("Original profile DLL differs from the trusted application parent pin");
            }
            packaged = bytes.inspectPackagedBytes(manifest, parentPin.manifestSha256(), parentPin.source(), parentPin.tree());
            packaged.prepareOriginalSystemImports();
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
            loadResult = load.invoke();
            imageVerification = loadResult.verifyImage(originalBootstrap(), packaged);
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
