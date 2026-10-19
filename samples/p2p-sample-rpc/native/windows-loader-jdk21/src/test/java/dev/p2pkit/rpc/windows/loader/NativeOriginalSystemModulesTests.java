package dev.p2pkit.rpc.windows.loader;

import java.lang.foreign.Arena;
import java.lang.foreign.MemorySegment;
import java.util.Arrays;
import java.util.Set;

import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.expect;
import static dev.p2pkit.rpc.windows.loader.OriginalFileBytesLeaseTests.value;

/**
 * Actual read-only fixed cohort diagnostic. No caller module/path, DLL loading, grant or filesystem change.
 * A negative observation is never a successful graph/OS admission. The original bootstrap remains a
 * development prerequisite; PIN plus later disk custody does not establish original mapped-file identity.
 */
public final class NativeOriginalSystemModulesTests {
    private static final String[] NAMES = {"kernel32.dll", "advapi32.dll", "ntdll.dll", "shell32.dll",
        "ole32.dll", "kernelbase.dll", "sechost.dll", "combase.dll", "iphlpapi.dll"};
    private static WindowsSystemBootstrapCandidate bootstrap;
    private static WindowsOriginalSystemModulesCandidate collection;
    private NativeOriginalSystemModulesTests() {}

    public static void main(String[] arguments) throws Throwable {
        check(arguments.length == 1 && arguments[0].equals("actual") && bootstrap == null);
        WindowsLoaderRuntime.requireDiagnosticRuntime();
        loaderRefuses();
        bootstrap = WindowsSystemBootstrapCandidate.inspect();
        check(bootstrap.completed());
        collection = bootstrap.inspectOriginalSystemModules();
        check(collection.completed() && collection.moduleCount() == NAMES.length);
        check(value(bootstrap, "systemModules") == collection && value(collection, "bootstrap") == bootstrap);
        check(value(bootstrap, "originalJvm") == null && value(bootstrap, "profileDll") == null);
        check((boolean) value(collection, "frameRetired") && !(boolean) value(collection, "nativeReturnUnconfirmed"));
        Arena moduleArena = (Arena) value(collection, "moduleArena");
        check(moduleArena != null && moduleArena.scope().isAlive());
        String outcome = collection.outcome();
        int stopped = collection.stoppedSlot();
        check(Set.of("MODULE_ABSENT", "LEAF_POLICY_REFUSED", "ANCESTOR_POLICY_REFUSED", "COMPLETE").contains(outcome));
        int pinned = 0, files = 0, security = 0, ancestors = 0, bytes = 0, graphQueries = 0;
        for (int slot = 0; slot < NAMES.length; slot++) {
            WindowsOriginalSystemModuleCandidate module = collection.module(slot);
            check(module.name().equals(NAMES[slot]) && value(module, "collection") == collection);
            if (module.pinned()) {
                pinned++;
                long raw = (long) value(module, "rawModule");
                check(raw > 0 && (raw & 65_535) == 0 && ((long[]) value(collection, "rawModules"))[slot] == raw);
                MemorySegment view = (MemorySegment) value(module, "module");
                check(view.address() == raw && view.scope().equals(moduleArena.scope()));
            }
            if (module.fileObserved()) {
                files++;
                WindowsOriginalFileLease file = (WindowsOriginalFileLease) value(module, "file");
                check(file.completed() && value(file, "originalSystemOwner") == module);
                check(value(file, "originalOwner") == null && value(file, "originalProfileDllOwner") == null);
                check(module.byteCount() >= 512 && module.byteCount() <= 32L * 1024 * 1024);
                check(module.linkCount() > 0 && module.linkCount() <= 0xffff_ffffL);
                check(Arrays.equals((long[]) value(file, "first"), (long[]) value(file, "second")));
                check(((long[]) value(file, "first"))[4] == module.byteCount());
                MemorySegment handle = (MemorySegment) value(file, "handle");
                Arena fileArena = (Arena) value(file, "handleArena");
                check(fileArena.scope().isAlive() && handle.scope().equals(fileArena.scope()));
                if (module.securityObserved()) {
                    security++;
                    WindowsOriginalFileSecurityQuery query = (WindowsOriginalFileSecurityQuery) value(module, "security");
                    check(query.completed() && value(query, "originalSystemOwner") == module);
                    check(value(query, "fileHandle") == handle && value(query, "fileArena") == fileArena);
                    check((long) value(query, "rawModule") == (long) value(collection.module(2), "rawModule"));
                }
                if (module.ancestorsObserved()) {
                    ancestors++;
                    WindowsOriginalFileAncestorsLease chain = (WindowsOriginalFileAncestorsLease) value(module, "ancestors");
                    check(module.descriptorPolicyAccepted() && chain.completed() && chain.ancestorCount() >= 2);
                    check(value(chain, "originalSystemOwner") == module && value(chain, "originalFileHandle") == handle);
                    check(value(chain, "originalFileArena") == fileArena);
                    check(Arrays.equals((long[]) value(chain, "originalFile"), (long[]) value(file, "first")));
                }
                if (module.bytesObserved()) {
                    bytes++;
                    WindowsOriginalFileBytesLease stream = (WindowsOriginalFileBytesLease) value(module, "bytes");
                    check(module.descriptorPolicyAccepted() && module.descriptorPoliciesAccepted() && stream.completed());
                    check(value(stream, "originalSystemOwner") == module && value(stream, "fileHandle") == handle);
                    check(value(stream, "fileArena") == fileArena && stream.byteCount() == module.byteCount());
                    check((int) value(stream, "readCalls") == (module.byteCount() + 65_535) / 65_536 + 1);
                    check((int) value(stream, "readCalls") <= 513 && module.sha256().length == 32);
                    check(Arrays.equals(stream.sha256(), module.sha256()));
                    check((boolean) value(stream, "frameRetired") && !(boolean) value(stream, "nativeReturnUnconfirmed") &&
                        !(boolean) value(stream, "readCompletionUnconfirmed"));
                }
            } else check(!module.securityObserved() && !module.ancestorsObserved() && !module.bytesObserved());
        }
        if (outcome.equals("COMPLETE")) {
            check(stopped == -1 && pinned == 9 && files == 9 && security == 9 && ancestors == 9 && bytes == 9);
            String[] exports = {"GetCurrentProcessId", "RegCloseKey", "NtQuerySecurityObject", "SHGetKnownFolderPath", "CoTaskMemFree"};
            Set<String> originalNames = Set.of(NAMES);
            for (int slot = 0; slot < exports.length; slot++) {
                WindowsSystemExportPlan.Target target = collection.resolve(NAMES[slot], exports[slot]);
                check(originalNames.contains(target.module()) && target.rva() > 0 && target.rva() <= 0xffff_ffffL && target.ordinal() > 0);
                graphQueries++;
            }
        } else {
            check(stopped >= 0 && stopped < 9 && bytes == 0 && value(collection, "graph") == null && value(collection, "inputs") == null);
            if (outcome.equals("MODULE_ABSENT")) check(pinned == stopped && files == 0 && security == 0 && ancestors == 0);
            else {
                check(pinned == 9 && files == stopped + 1 && security == stopped + 1);
                WindowsOriginalSystemModuleCandidate refused = collection.module(stopped);
                if (outcome.equals("LEAF_POLICY_REFUSED")) {
                    check(!refused.descriptorPolicyAccepted() && ancestors == stopped);
                    check(value(refused, "ancestors") == null && !(boolean) value(refused, "ancestorsAttempted"));
                    expect(IllegalStateException.class, refused::observeAncestors);
                } else check(refused.descriptorPolicyAccepted() && !refused.descriptorPoliciesAccepted() && ancestors == stopped + 1);
            }
            expect(IllegalStateException.class, () -> collection.resolve("kernel32.dll", "GetCurrentProcessId"));
        }
        // All completed outcomes, even COMPLETE data, seal further native input/stage factories.
        for (int slot = 0; slot < NAMES.length; slot++) {
            WindowsOriginalSystemModuleCandidate module = collection.module(slot);
            expect(IllegalStateException.class, module::observeBytes);
            expect(IllegalStateException.class, module::originalLinker);
        }
        expect(IllegalStateException.class, bootstrap::inspectOriginalSystemModules);
        loaderRefuses();
        check(moduleArena.scope().isAlive());
        System.out.println("WINDOWS_NATIVE_ORIGINAL_SYSTEM_MODULES_PASS case=actual" +
            " scope=DEVELOPMENT_SYSTEM_MODULE_DISK_GRAPH_NOT_MAPPED_IDENTITY_OR_OS_AUTHORITY outcome=" + outcome +
            " stoppedSlot=" + stopped + " pinned=" + pinned + " files=" + files + " bytes=" + bytes + " graphQueries=" + graphQueries);
    }

    private static void loaderRefuses() {
        Throwable refusal = expect(WindowsLoader.Unavailable.class, WindowsLoader::openInstalledProvider);
        check(WindowsLoader.REFUSAL.equals(refusal.getMessage()));
    }
    private static void check(boolean condition) { if (!condition) throw new AssertionError("Original native system-module diagnostic failed"); }
}
