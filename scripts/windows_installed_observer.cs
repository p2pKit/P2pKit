// Fixed-purpose external observer. Canonical WindowsScope owns the worker tree.
// Retain Process.Start's original handle; never reopen a process by PID or name.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Security.AccessControl;
using System.Security.Cryptography;
using System.Security.Principal;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Win32.SafeHandles;

namespace P2pKit.WindowsQualification {
    public enum Control { Normal, Nonzero, OutputOverflow, BlockedWorker, BlockedOuter, ObserverOutputOverflow }
    public sealed class Observation {
        public string Status { get; internal set; }
        public string Capsule { get; internal set; }
        public Dictionary<string, object> Receipt { get; internal set; }
    }
    public static class InstalledObserver {
        const int OutputLimit = 65536, ReceiptLimit = 16384;
        static readonly UTF8Encoding Utf8 = new UTF8Encoding(false, true);
        static readonly string[] Sources = {
            "run-windows-installed-diagnostic.py", "ci_evidence.py", "audit_processes.py",
            "hosted_evidence.py", "hosted_evidence_primitives.py", "hosted_windows_files.py"
        };
        [StructLayout(LayoutKind.Sequential)]
        struct SecurityAttributes {
            public int Length;
            public IntPtr Descriptor;
            [MarshalAs(UnmanagedType.Bool)] public bool Inherit;
        }
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        static extern bool CreateDirectoryW(string path, ref SecurityAttributes security);
        [DllImport("kernel32.dll", SetLastError = true)]
        static extern uint WaitForSingleObject(SafeProcessHandle process, uint milliseconds);
        [DllImport("kernel32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        static extern bool GetExitCodeProcess(SafeProcessHandle process, out uint code);
        [DllImport("kernel32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        static extern bool TerminateProcess(SafeProcessHandle process, uint code);
        [DllImport("kernel32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        static extern bool CloseHandle(IntPtr handle);

        static void Require(bool value) {
            if (!value) throw new InvalidOperationException("WINDOWS_INSTALLED_OBSERVER_REFUSED");
        }
        static long Now() { return Stopwatch.GetTimestamp(); }
        static void Timely(long end) { Require(Now() < end); }
        static int Slice(long end, long frequency) {
            long remaining = end - Now(); Require(remaining > 0);
            return (int)Math.Min(25, Math.Max(1, Math.Floor(remaining * 1000.0 / frequency)));
        }
        static string Capsule(string parent) {
            Require(Path.IsPathFullyQualified(parent));
            var root = new DirectoryInfo(parent);
            Require(root.Exists && (root.Attributes & FileAttributes.ReparsePoint) == 0);
            byte[] bytes;
            using (var identity = WindowsIdentity.GetCurrent()) {
                Require(identity.User != null);
                var acl = new DirectorySecurity();
                acl.SetOwner(identity.User); acl.SetAccessRuleProtection(true, false);
                foreach (var sid in new[] { identity.User, new SecurityIdentifier("S-1-5-18") }) {
                    acl.AddAccessRule(new FileSystemAccessRule(sid, FileSystemRights.FullControl,
                        InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit,
                        PropagationFlags.None, AccessControlType.Allow));
                }
                bytes = acl.GetSecurityDescriptorBinaryForm();
            }
            string path = Path.Combine(root.FullName, "installed-" + Guid.NewGuid().ToString("N"));
            IntPtr descriptor = Marshal.AllocHGlobal(bytes.Length);
            try {
                Marshal.Copy(bytes, 0, descriptor, bytes.Length);
                var security = new SecurityAttributes {
                    Length = Marshal.SizeOf<SecurityAttributes>(), Descriptor = descriptor, Inherit = false
                };
                Require(CreateDirectoryW(path, ref security));
            } finally { Marshal.FreeHGlobal(descriptor); }
            return path;
        }
        sealed class Capture {
            public readonly Task Task;
            public volatile bool Overflow, Eof, Closed, Failed;
            public Capture(Stream original, string path) {
                Task = System.Threading.Tasks.Task.Run(async () => {
                    try {
                        using (var output = new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.Read)) {
                            byte[] buffer = new byte[4096]; int used = 0;
                            while (true) {
                                int count = await original.ReadAsync(buffer, 0, buffer.Length).ConfigureAwait(false);
                                if (count == 0) { Eof = true; break; }
                                int keep = Math.Min(count, OutputLimit - used);
                                if (keep != 0) await output.WriteAsync(buffer, 0, keep).ConfigureAwait(false);
                                used += keep;
                                if (count != keep) { Overflow = true; break; }
                            }
                            await output.FlushAsync().ConfigureAwait(false);
                        }
                    } catch { Failed = true; }
                    finally { try { original.Dispose(); Closed = true; } catch { Failed = true; } }
                });
            }
            public bool Complete {
                get { return Task.Status == TaskStatus.RanToCompletion && Eof && Closed && !Failed && !Overflow; }
            }
        }
        static byte[] ReadClosed(string path, int maximum, bool empty = false) {
            using (var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.None)) {
                Require((empty || stream.Length > 0) && stream.Length <= maximum);
                byte[] bytes = new byte[(int)stream.Length]; int used = 0;
                while (used < bytes.Length) {
                    int count = stream.Read(bytes, used, bytes.Length - used); Require(count > 0); used += count;
                }
                Require(stream.ReadByte() == -1); return bytes;
            }
        }
        static Dictionary<string, string> SourceHashes(string scripts, bool control) {
            var result = new Dictionary<string, string>(StringComparer.Ordinal);
            foreach (string name in Sources.Concat(control ? new[] { "tests/run-windows-installed-diagnostic-test.py" } : new string[0])) {
                byte[] bytes = ReadClosed(Path.Combine(scripts, name), 2 * 1024 * 1024);
                result.Add(name, Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant());
            }
            return result;
        }
        static Dictionary<string, string> ObserverHashes(string scripts, bool control) {
            var result = new Dictionary<string, string>(StringComparer.Ordinal);
            foreach (string name in new[] { "windows_installed_observer.cs", "run-windows-installed-diagnostic.ps1" }
                .Concat(control ? new[] { "tests/run-windows-installed-observer-control.ps1" } : new string[0])) {
                result.Add(name, Convert.ToHexString(SHA256.HashData(ReadClosed(Path.Combine(scripts, name), 262144))).ToLowerInvariant());
            }
            return result;
        }
        static void ObjectShape(JsonElement value, params string[] names) {
            Require(value.ValueKind == JsonValueKind.Object);
            var expected = new HashSet<string>(names, StringComparer.Ordinal);
            foreach (var property in value.EnumerateObject()) Require(expected.Remove(property.Name));
            Require(expected.Count == 0);
        }
        static void NoDuplicates(JsonElement value) {
            if (value.ValueKind == JsonValueKind.Object) {
                var names = new HashSet<string>(StringComparer.Ordinal);
                foreach (var item in value.EnumerateObject()) { Require(names.Add(item.Name)); NoDuplicates(item.Value); }
            } else if (value.ValueKind == JsonValueKind.Array) {
                foreach (var item in value.EnumerateArray()) NoDuplicates(item);
            }
        }
        static long Integer(JsonElement value) {
            Require(value.ValueKind == JsonValueKind.Number && Regex.IsMatch(value.GetRawText(), "^(0|[1-9][0-9]*)$"));
            Require(value.TryGetInt64(out long result)); return result;
        }
        static bool Text(JsonElement value, string expected) {
            return value.ValueKind == JsonValueKind.String && value.GetString() == expected;
        }
        static void CommandPass(JsonElement value) {
            ObjectShape(value, "exitCode", "timedOut", "cleanupKnown", "capturesClosed", "stage", "code",
                "nativeError", "cleanupReasons", "pendingContext", "elapsedSeconds");
            Require(Text(value.GetProperty("code"), "PASS") && Integer(value.GetProperty("exitCode")) == 0);
            Require(Text(value.GetProperty("stage"), "COMMAND"));
            Require(value.GetProperty("timedOut").ValueKind == JsonValueKind.False);
            Require(value.GetProperty("cleanupKnown").ValueKind == JsonValueKind.True);
            Require(value.GetProperty("capturesClosed").ValueKind == JsonValueKind.True);
            Require(value.GetProperty("nativeError").ValueKind == JsonValueKind.Null);
            Require(value.GetProperty("pendingContext").ValueKind == JsonValueKind.Null);
            var reasons = value.GetProperty("cleanupReasons");
            Require(reasons.ValueKind == JsonValueKind.Array && reasons.GetArrayLength() == 0);
            var elapsed = value.GetProperty("elapsedSeconds");
            Require(elapsed.ValueKind == JsonValueKind.Number && elapsed.TryGetDouble(out double seconds) &&
                !double.IsNaN(seconds) && !double.IsInfinity(seconds) && seconds >= 0 && seconds < 30);
        }
        // Evidence parser only; these values never authorize process creation or installation.
        public static void ValidateReceipt(byte[] bytes, string source, string scope, long start, long frequency,
            Dictionary<string, string> hashes) {
            Require(bytes != null && bytes.Length > 0 && bytes.Length <= ReceiptLimit);
            using (var document = JsonDocument.Parse(Utf8.GetString(bytes), new JsonDocumentOptions { MaxDepth = 16 })) {
                var root = document.RootElement; NoDuplicates(root);
                ObjectShape(root, "schema", "scope", "status", "appSource", "supervisorSource", "startCounter",
                    "counterFrequency", "deadlineCounter", "watchdogCounter", "completedCounter", "workerOutcome",
                    "outerCleanupKnown", "capturesClosed");
                long end = checked(start + frequency * 30);
                Require(Integer(root.GetProperty("schema")) == 1 && Text(root.GetProperty("scope"), scope));
                Require(Text(root.GetProperty("status"), "PASS") && Text(root.GetProperty("appSource"), source));
                Require(Integer(root.GetProperty("startCounter")) == start && Integer(root.GetProperty("counterFrequency")) == frequency);
                Require(Integer(root.GetProperty("deadlineCounter")) == end && Integer(root.GetProperty("watchdogCounter")) == end - frequency);
                long completed = Integer(root.GetProperty("completedCounter")); Require(completed >= start && completed < end);
                Require(root.GetProperty("outerCleanupKnown").ValueKind == JsonValueKind.True);
                Require(root.GetProperty("capturesClosed").ValueKind == JsonValueKind.True);
                var observed = root.GetProperty("supervisorSource"); ObjectShape(observed, hashes.Keys.ToArray());
                foreach (var pair in hashes) Require(Text(observed.GetProperty(pair.Key), pair.Value));
                var worker = root.GetProperty("workerOutcome"); ObjectShape(worker, "schema", "appSource", "outcome", "admissionMatched");
                Require(Integer(worker.GetProperty("schema")) == 1 && Text(worker.GetProperty("appSource"), source));
                Require(worker.GetProperty("admissionMatched").ValueKind == JsonValueKind.True);
                CommandPass(worker.GetProperty("outcome"));
            }
        }
        public static Observation RunInstalled(string scripts, string python, string parent, string source) {
            return Run(scripts, python, parent, source, null);
        }
        public static Observation RunControl(string scripts, string python, string parent, Control control) {
            Require(Enum.IsDefined(typeof(Control), control));
            string choice = new[] { "normal", "nonzero", "output-overflow", "blocked-worker", "blocked-outer", "observer-output-overflow" }[(int)control];
            return Run(scripts, python, parent, new string('0', 40), choice);
        }
        static Observation Run(string scripts, string python, string parent, string source, string control) {
            Require(OperatingSystem.IsWindows() && Environment.Is64BitProcess && Stopwatch.IsHighResolution);
            Require(Regex.IsMatch(source, "^[0-9a-f]{40}$") && Path.IsPathFullyQualified(python) && File.Exists(python));
            scripts = Path.GetFullPath(scripts); string capsule = Capsule(parent);
            var hashes = SourceHashes(scripts, control != null);
            var observerHashes = ObserverHashes(scripts, control != null);
            string stage = "START", status = "FAIL";
            long frequency = Stopwatch.Frequency, start = 0, end = 0, finished = 0;
            Require(frequency > 0 && frequency <= 1000000000000L);
            Process process = null; SafeProcessHandle handle = null;
            var captures = new List<Capture>();
            bool exited = false, originalClosed = false, managedClosed = false, terminated = false, terminationReturned = false;
            bool capturesClosed = false; uint? exitCode = null;
            try {
                var info = new ProcessStartInfo(python) {
                    UseShellExecute = false, CreateNoWindow = true, WorkingDirectory = scripts,
                    RedirectStandardOutput = true, RedirectStandardError = true
                };
                foreach (string arg in new[] { "-I", "-B", "-S", Path.Combine(scripts,
                    control == null ? "run-windows-installed-diagnostic.py" : "tests/run-windows-installed-diagnostic-test.py") })
                    info.ArgumentList.Add(arg);
                if (control != null) { info.ArgumentList.Add("--native"); info.ArgumentList.Add(control); }
                else { info.ArgumentList.Add("--expected-source"); info.ArgumentList.Add(source); }
                info.ArgumentList.Add("--private-parent"); info.ArgumentList.Add(capsule);
                start = Now(); end = checked(start + frequency * 30); Require(start > 0);
                info.ArgumentList.Add("--start-counter"); info.ArgumentList.Add(start.ToString(System.Globalization.CultureInfo.InvariantCulture));
                info.ArgumentList.Add("--counter-frequency"); info.ArgumentList.Add(frequency.ToString(System.Globalization.CultureInfo.InvariantCulture));
                process = Process.Start(info); Require(process != null);
                handle = process.SafeHandle; Require(!handle.IsInvalid && !handle.IsClosed);
                captures.Add(new Capture(process.StandardOutput.BaseStream, Path.Combine(capsule, "observer-stdout.log")));
                captures.Add(new Capture(process.StandardError.BaseStream, Path.Combine(capsule, "observer-stderr.log")));
                stage = "WAIT"; Timely(end);
                while (true) {
                    Require(captures.All(item => !item.Failed && !item.Overflow));
                    uint wait = WaitForSingleObject(handle, (uint)Slice(end, frequency));
                    Timely(end); Require(wait == 0 || wait == 258);
                    if (wait == 0) { exited = true; break; }
                }
                Require(GetExitCodeProcess(handle, out uint code)); exitCode = code; Require(code == 0);
                stage = "CAPTURES";
                while (captures.Any(item => !item.Task.IsCompleted)) Thread.Sleep(Slice(end, frequency));
                Require(captures.All(item => item.Complete)); Timely(end);
                Require(ReadClosed(Path.Combine(capsule, "observer-stderr.log"), OutputLimit, true).Length == 0);
                string output = Utf8.GetString(ReadClosed(Path.Combine(capsule, "observer-stdout.log"), OutputLimit));
                Require(output == "WINDOWS_INSTALLED_SUPERVISOR PASS\n" || output == "WINDOWS_INSTALLED_SUPERVISOR PASS\r\n");
                stage = "RECEIPT";
                ValidateReceipt(ReadClosed(Path.Combine(capsule, "run", "supervisor.json"), ReceiptLimit), source,
                    control == null ? "INSTALLED_ADMISSION_SUPERVISION_NOT_PROFILE_QUALIFICATION" : "SUPERVISOR_NATIVE_CONTROL_NOT_INSTALLED",
                    start, frequency, hashes);
                var after = SourceHashes(scripts, control != null);
                Require(hashes.All(pair => after.TryGetValue(pair.Key, out string value) && value == pair.Value));
                var observerAfter = ObserverHashes(scripts, control != null);
                Require(observerHashes.All(pair => observerAfter.TryGetValue(pair.Key, out string value) && value == pair.Value));
                Timely(end); status = "PASS";
            } catch { status = "FAIL"; }
            finally {
                // Any interval after end is failure-only retirement, never new acceptance time.
                long retirementEnd = checked(end + frequency * 2);
                if (handle != null && !handle.IsInvalid && !handle.IsClosed) {
                    try {
                        uint wait = WaitForSingleObject(handle, 0); Require(wait == 0 || wait == 258);
                        if (wait != 0) {
                            status = "FAIL"; terminated = true;
                            terminationReturned = TerminateProcess(handle, 125); Require(terminationReturned);
                            while (wait != 0 && Now() < retirementEnd)
                                wait = WaitForSingleObject(handle, (uint)Slice(retirementEnd, frequency));
                        }
                        exited = wait == 0; Require(exited);
                        Require(GetExitCodeProcess(handle, out uint code)); exitCode = code;
                    } catch { status = "FAIL"; }
                }
                try {
                    while (captures.Any(item => !item.Task.IsCompleted) && Now() < retirementEnd)
                        Thread.Sleep(Slice(retirementEnd, frequency));
                    capturesClosed = captures.Count == 2 && captures.All(item => item.Complete);
                    if (!capturesClosed) status = "FAIL";
                } catch { status = "FAIL"; }
                if (handle != null && !handle.IsInvalid && !handle.IsClosed) {
                    // Transfer this original once out of SafeHandle to observe CloseHandle's result.
                    // No concurrent observer uses it here; Process.Dispose cannot retry the handle.
                    IntPtr original = handle.DangerousGetHandle(); handle.SetHandleAsInvalid();
                    originalClosed = CloseHandle(original); if (!originalClosed) status = "FAIL";
                }
                try { if (process != null) { process.Dispose(); managedClosed = true; } }
                catch { status = "FAIL"; }
                finished = Now();
                if (!exited || !originalClosed || !managedClosed || terminated || finished >= end) status = "FAIL";
            }
            var record = new Dictionary<string, object> {
                ["schema"] = 1, ["scope"] = control == null ? "EXTERNAL_PROCESS_EXIT_OBSERVER_NOT_PROFILE_QUALIFICATION" : "EXTERNAL_NATIVE_CONTROL_NOT_INSTALLED",
                ["status"] = status, ["stage"] = stage, ["appSource"] = source, ["control"] = control,
                ["phase"] = "CANDIDATE_REQUIRES_OBSERVED_EXTERNAL_EXIT", ["finalizationCompleted"] = false,
                ["observerSource"] = observerHashes,
                ["supervisorSource"] = hashes, ["startCounter"] = start, ["counterFrequency"] = frequency,
                ["deadlineCounter"] = end, ["completedCounter"] = finished, ["budgetMilliseconds"] = 30000,
                ["elapsedMilliseconds"] = (finished - start) * 1000.0 / frequency,
                ["exitCode"] = exitCode, ["processExitObserved"] = exited, ["originalProcessHandleClosed"] = originalClosed,
                ["managedProcessClosed"] = managedClosed, ["capturesClosed"] = capturesClosed,
                ["captureTasksRetired"] = captures.Count == 2 && captures.All(item => item.Task.Status == TaskStatus.RanToCompletion && item.Closed),
                ["outputExceeded"] = captures.Any(item => item.Overflow),
                ["terminationAttempted"] = terminated, ["terminationReturned"] = terminationReturned
            };
            bool finalized = false;
            try {
                byte[] bytes = Utf8.GetBytes(JsonSerializer.Serialize(record) + "\n"); Require(bytes.Length <= ReceiptLimit);
                using (var stream = new FileStream(Path.Combine(capsule, "observer.json"), FileMode.CreateNew, FileAccess.Write, FileShare.None)) {
                    stream.Write(bytes, 0, bytes.Length); stream.Flush(true);
                }
                Timely(end); finalized = true;
            } catch { status = "FAIL"; }
            // The on-disk candidate cannot attest its own final write/close or this process's exit.
            // Callers must require the actual external exit in addition to the candidate. The returned
            // observation describes completed finalization and never retains a stale PASS after failure.
            record["status"] = status;
            record["phase"] = "RETURN_REQUIRES_OBSERVED_EXTERNAL_EXIT";
            record["finalizationCompleted"] = finalized;
            record["completedCounter"] = Now();
            record["elapsedMilliseconds"] = ((long)record["completedCounter"] - start) * 1000.0 / frequency;
            if ((long)record["completedCounter"] >= end) { status = "FAIL"; record["status"] = status; }
            return new Observation { Status = status, Capsule = capsule, Receipt = record };
        }
    }
}
