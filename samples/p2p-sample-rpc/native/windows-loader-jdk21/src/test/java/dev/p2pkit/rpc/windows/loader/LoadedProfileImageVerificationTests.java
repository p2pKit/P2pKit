package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.MemorySegment;
import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.util.concurrent.atomic.AtomicReference;

/** Private inert ownership/name-order controls only: no native lookup, read, DLL or admitted bootstrap. */
public final class LoadedProfileImageVerificationTests {
    private static final String PREFIX = "Java_dev_p2pkit_sample_rpc_profile_WindowsProfileCustodyJni_";
    private static final String[] METHODS = {"abi", "capabilities", "openRoot", "child", "createChildDirectory",
        "identity", "fileIdentity", "exists", "names", "read", "lockExisting", "createProfileLock",
        "createVaultLock", "stageRecord", "prepareRecord", "writeRecord", "renameCandidate", "replaceCandidate",
        "syncDirectory", "discardStage", "requestExpectedFileDeletion", "deleteRecord", "close"};

    private LoadedProfileImageVerificationTests() {}

    public static void main(String[] args) throws Throwable {
        check(args.length == 1);
        String mode = args[0];
        switch (mode) {
            case "unattached", "once", "thread" -> ownership(mode);
            case "registration-before-verification", "registration-after-failure", "registration-thread" -> registration(mode);
            case "unprepared", "owned-required" -> {
                WindowsPackagedVerifier plan = plan();
                if (mode.equals("unprepared")) {
                    set(plan, "prepared", false);
                    expect(IllegalStateException.class, plan::requireDevelopmentImportComparison);
                } else {
                    plan.requireDevelopmentImportComparison(); // Inert copied data permits no native effect.
                    expect(IllegalStateException.class, () -> plan.requireOriginalImportBootstrap(null));
                    expect(IllegalStateException.class, () -> plan.requireOriginalLoadedFile(null));
                    expect(IllegalStateException.class, plan::originalSystemImportTargets);
                    check(get(plan, "originalBytes") == null && get(plan, "originalImportTargets") == null);
                }
            }
            case "order", "wrong-order", "substituted-view", "missing-name", "duplicate-name",
                 "closed-scope", "declaration" -> ordered(mode);
            default -> throw new AssertionError("Unknown loaded-image control");
        }
        System.out.println("WINDOWS_LOADED_IMAGE_VERIFICATION_PASS case=" + mode +
            " scope=INERT_BINDING_NOT_NATIVE_OR_AUTHORITY");
    }

    private static void ownership(String mode) throws Throwable {
        WindowsLoadedProfileImageVerification candidate = new WindowsLoadedProfileImageVerification(null, null, null, null);
        if (mode.equals("thread")) {
            AtomicReference<Throwable> caught = new AtomicReference<>();
            Thread other = new Thread(() -> {
                try { candidate.verify(); } catch (Throwable failure) { caught.set(failure); }
            });
            other.start(); other.join();
            check(caught.get() instanceof IllegalStateException && !((boolean) get(candidate, "attempted")));
            check(((WindowsLoadedProfileImageVerification.Failure) get(candidate, "failure")).operationFailure == null);
        }
        WindowsLoadedProfileImageVerification.Failure failure = (WindowsLoadedProfileImageVerification.Failure)
            expect(WindowsLoadedProfileImageVerification.Failure.class, candidate::verify);
        check(failure.retainedVerification == candidate && failure.operationFailure instanceof IllegalStateException &&
            failure.getCause() == null && get(candidate, "exports") == null && get(candidate, "reads") == null &&
            (int) get(candidate, "phase") == WindowsLoadedProfileImageVerification.PREPARE);
        Throwable original = failure.operationFailure;
        expect(IllegalStateException.class, candidate::verify);
        expect(IllegalStateException.class, candidate::jniEntries);
        expect(IllegalStateException.class, candidate::registrar);
        expect(IllegalStateException.class, candidate::declaringClass);
        expect(IllegalStateException.class, candidate::originalJvm);
        check(failure.operationFailure == original && !((boolean) get(candidate, "succeeded")));
    }

    private static void registration(String mode) throws Throwable {
        WindowsLoadedProfileImageVerification candidate = new WindowsLoadedProfileImageVerification(null, null, null, null);
        Throwable prior = null;
        if (mode.equals("registration-after-failure")) {
            WindowsLoadedProfileImageVerification.Failure failure = (WindowsLoadedProfileImageVerification.Failure)
                expect(WindowsLoadedProfileImageVerification.Failure.class, candidate::verify);
            prior = failure.operationFailure;
        }
        if (mode.equals("registration-thread")) {
            AtomicReference<Throwable> caught = new AtomicReference<>();
            Thread other = new Thread(() -> {
                try { candidate.registerOriginalJni(); } catch (Throwable failure) { caught.set(failure); }
            });
            other.start(); other.join();
            check(caught.get() instanceof IllegalStateException);
        } else expect(IllegalStateException.class, candidate::registerOriginalJni);
        check(!((boolean) get(candidate, "registrationAttempted")) && get(candidate, "registrationVm") == null &&
            get(candidate, "registrationRoots") == null && get(candidate, "registrationMethods") == null &&
            get(candidate, "registrationInvocation") == null && get(candidate, "registrationOwner") == null &&
            get(candidate, "registrationFailure") == null && WindowsJniRegistrationOwner.retainedProcessOwner() == null);
        check(((WindowsLoadedProfileImageVerification.Failure) get(candidate, "failure")).operationFailure == prior);
        expect(IllegalStateException.class, candidate::registerOriginalJni);
        check(get(candidate, "registrationInvocation") == null);
    }

    private static WindowsPackagedVerifier plan() throws Exception {
        Constructor<WindowsPackagedVerifier> constructor = WindowsPackagedVerifier.class
            .getDeclaredConstructor(WindowsOriginalProfileDllBytesCandidate.class);
        constructor.setAccessible(true);
        WindowsPackagedVerifier result = constructor.newInstance((Object) null);
        set(result, "prepared", true);
        set(result, "declaringClass", Object.class);
        return result;
    }

    private static void ordered(String mode) throws Throwable {
        WindowsPackagedVerifier plan = plan();
        WindowsLoadedProfileImageVerification candidate = new WindowsLoadedProfileImageVerification(null, null, plan, null);
        // Reflection invokes only private copied-data binding on explicitly inert native allocations.
        // It never creates an admitted bootstrap or calls public verify; successful getters still refuse.
        Arena arena = Arena.ofConfined();
        try {
            MemorySegment storage = arena.allocate(4096, 8);
            WindowsExportLookupInvocation.Result[] results = new WindowsExportLookupInvocation.Result[24];
            MemorySegment[] entries = new MemorySegment[24];
            String[] names = new String[24];
            long[] verified = new long[24];
            for (int index = 0; index < 24; index++) {
                int slot = 23 - index; // Reverse export enumeration: JNI result order must be name-derived.
                names[slot] = index == 23 ? "pwp_jni_register_once" : PREFIX + METHODS[index];
                entries[slot] = storage.asSlice(16L + index * 8, 0);
                verified[index] = entries[slot].address();
                Constructor<WindowsExportLookupInvocation> constructor = WindowsExportLookupInvocation.class
                    .getDeclaredConstructor(Object.class, Object.class, Object.class, MemorySegment.class,
                        Arena.class, MemorySegment.class, Arena.class, String.class, long.class, long.class);
                constructor.setAccessible(true);
                WindowsExportLookupInvocation export = constructor.newInstance(candidate, candidate, plan,
                    storage.asSlice(0, 0), arena, storage.asSlice(8, 0), arena, names[slot], 4096L, 16L + index * 8);
                set(export, "resolved", entries[slot]);
                set(export, "succeeded", true);
                results[slot] = (WindowsExportLookupInvocation.Result) get(export, "result");
            }
            set(candidate, "originalArena", arena);
            set(candidate, "declaration", Object.class);
            set(candidate, "names", names);
            set(candidate, "verified", verified);
            set(candidate, "exportResults", results);
            set(candidate, "exportEntries", entries);
            MemorySegment[] ordered = new MemorySegment[24];
            set(candidate, "orderedEntries", ordered);
            if (mode.equals("wrong-order")) {
                long first = verified[0]; verified[0] = verified[1]; verified[1] = first;
            }
            if (mode.equals("substituted-view")) {
                // Equal numeric bits and scope do not replace the exact view returned by the original result.
                entries[23] = entries[23].asReadOnly();
                check(entries[23] != results[23].entry() && entries[23].address() == results[23].entry().address());
            }
            if (mode.equals("missing-name")) names[23] = PREFIX + "missing";
            if (mode.equals("duplicate-name")) names[22] = names[23];
            if (mode.equals("declaration")) set(candidate, "declaration", String.class);
            if (mode.equals("closed-scope")) arena.close();
            if (mode.equals("order")) {
                invoke(candidate, "bindOriginalEntries");
                for (int index = 0; index < 24; index++) {
                    check(ordered[index] == entries[23 - index] && ordered[index].address() == verified[index]);
                }
                // Data-only private success cannot bypass the real original-owner/success guards.
                expect(IllegalStateException.class, candidate::jniEntries);
                expect(IllegalStateException.class, candidate::registrar);
            } else expect(IllegalStateException.class, () -> invoke(candidate, "bindOriginalEntries"));
            check(!((boolean) get(candidate, "attempted")) && !((boolean) get(candidate, "succeeded")) &&
                get(candidate, "reads") == null && get(candidate, "load") == null);
        } finally { if (arena.scope().isAlive()) arena.close(); }
    }

    private static Object get(Object owner, String name) throws Exception {
        Field field = owner.getClass().getDeclaredField(name); field.setAccessible(true); return field.get(owner);
    }
    private static void set(Object owner, String name, Object value) throws Exception {
        Field field = owner.getClass().getDeclaredField(name); field.setAccessible(true); field.set(owner, value);
    }
    private static void invoke(Object owner, String name) throws Throwable {
        Method method = owner.getClass().getDeclaredMethod(name); method.setAccessible(true);
        try { method.invoke(owner); } catch (InvocationTargetException wrapped) { throw wrapped.getCause(); }
    }
    private static Throwable expect(Class<? extends Throwable> type, Action action) throws Throwable {
        try { action.run(); } catch (Throwable caught) {
            if (type.isInstance(caught)) return caught;
            throw caught;
        }
        throw new AssertionError("Expected exact inert refusal");
    }
    private static void check(boolean value) { if (!value) throw new AssertionError("Loaded-image invariant failed"); }
    @FunctionalInterface private interface Action { void run() throws Throwable; }
}
