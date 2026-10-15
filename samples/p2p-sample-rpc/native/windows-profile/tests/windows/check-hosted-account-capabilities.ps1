# Read-only process-token observation in the already authorized test-only hosted job.
# No account/profile changes, privilege adjustment, child launch, payload loading or smoke authorization.
# Environment guards are scope checks, not substitutes for the owner's workflow authorization.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
try {
    if ($PSVersionTable.PSVersion.Major -lt 7 -or -not $IsWindows -or
        $env:GITHUB_ACTIONS -cne 'true' -or $env:GITHUB_EVENT_NAME -cne 'workflow_dispatch' -or
        $env:GITHUB_REPOSITORY -cne 'p2pKit/P2pKit' -or
        $env:GITHUB_REF -cne 'refs/heads/work/rpc-windows-validation-20261012' -or
        $env:GITHUB_JOB -cne 'rpc-windows' -or $env:RUNNER_ENVIRONMENT -cne 'github-hosted' -or
        $env:RUNNER_OS -cne 'Windows' -or $env:RUNNER_ARCH -cne 'X64' -or $env:ImageOS -cne 'win22' -or
        $env:GITHUB_SHA -cnotmatch '\A[0-9a-f]{40}\z') {
        throw 'Wrong hosted test scope'
    }
    if ('P2pKit.ReadOnlyHostedAccountCapabilities' -as [type]) { throw 'Unexpected existing probe type' }

    # PowerShell 7 compiles this fixed definition in-process. No compiler process/output assembly is requested.
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;

namespace P2pKit
{
    public static class ReadOnlyHostedAccountCapabilities
    {
        [StructLayout(LayoutKind.Sequential)]
        private struct Luid { public uint Low; public int High; }

        [DllImport("kernel32.dll", ExactSpelling = true)]
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)]
        private static extern IntPtr GetCurrentProcess();

        [DllImport("kernel32.dll", ExactSpelling = true, SetLastError = true)]
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool IsWow64Process2(IntPtr process, out ushort processMachine, out ushort nativeMachine);

        [DllImport("advapi32.dll", ExactSpelling = true, SetLastError = true)]
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool OpenProcessToken(IntPtr process, uint access, out IntPtr token);

        [DllImport("advapi32.dll", ExactSpelling = true, SetLastError = true)]
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool GetTokenInformation(IntPtr token, int informationClass,
            [Out] byte[] information, uint size, out uint returnedSize);

        [DllImport("advapi32.dll", ExactSpelling = true, CharSet = CharSet.Unicode, SetLastError = true)]
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool LookupPrivilegeValueW(string system, string name, out Luid value);

        [DllImport("kernel32.dll", ExactSpelling = true, SetLastError = true)]
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool CloseHandle(IntPtr handle);

        public static bool[] Read()
        {
            ushort processMachine, nativeMachine;
            if (!IsWow64Process2(GetCurrentProcess(), out processMachine, out nativeMachine) ||
                processMachine != 0 || nativeMachine != 0x8664 || IntPtr.Size != 8)
                throw new InvalidOperationException("Native Windows AMD64 required");

            IntPtr token = IntPtr.Zero;
            if (!OpenProcessToken(GetCurrentProcess(), 0x0008, out token)) // TOKEN_QUERY only.
                throw new InvalidOperationException("Process token query unavailable");
            try
            {
                byte[] bytes = new byte[16384]; // Fixed, bounded TOKEN_PRIVILEGES query; no identity query.
                uint used;
                if (!GetTokenInformation(token, 3, bytes, (uint)bytes.Length, out used) ||
                    used < 4 || used > bytes.Length)
                    throw new InvalidOperationException("Privilege query unavailable");
                uint count = BitConverter.ToUInt32(bytes, 0);
                if (count > (used - 4) / 12 || used != 4 + 12 * count)
                    throw new InvalidOperationException("Invalid privilege query shape");

                string[] names = { "SeAssignPrimaryTokenPrivilege", "SeIncreaseQuotaPrivilege", "SeImpersonatePrivilege" };
                bool[] result = new bool[6]; // Each fixed name has presence/enabled booleans, in that order.
                for (int selected = 0; selected < names.Length; selected++)
                {
                    Luid wanted;
                    if (!LookupPrivilegeValueW(null, names[selected], out wanted))
                        throw new InvalidOperationException("Fixed privilege lookup unavailable");
                    for (uint index = 0; index < count; index++)
                    {
                        int offset = checked(4 + 12 * (int)index);
                        if (BitConverter.ToUInt32(bytes, offset) != wanted.Low ||
                            BitConverter.ToInt32(bytes, offset + 4) != wanted.High) continue;
                        if (result[2 * selected]) throw new InvalidOperationException("Duplicate privilege entry");
                        result[2 * selected] = true;
                        result[2 * selected + 1] = (BitConverter.ToUInt32(bytes, offset + 8) & 2) != 0;
                    }
                }
                return result;
            }
            finally
            {
                IntPtr original = token;
                token = IntPtr.Zero; // Detach before the one physical close; never retry a raw handle.
                if (!CloseHandle(original)) throw new InvalidOperationException("Token cleanup uncertain");
            }
        }
    }
}
'@ -ErrorAction Stop

    $observed = [P2pKit.ReadOnlyHostedAccountCapabilities]::Read()
    $names = @('SeAssignPrimaryTokenPrivilege', 'SeIncreaseQuotaPrivilege', 'SeImpersonatePrivilege')
    $privileges = [ordered]@{}
    for ($index = 0; $index -lt $names.Count; $index++) {
        $privileges[$names[$index]] = [ordered]@{
            present = [bool]$observed[2 * $index]
            enabled = [bool]$observed[2 * $index + 1]
        }
    }
    [ordered]@{
        scope = 'READ_ONLY_HOST_PROCESS_TOKEN_NOT_STANDARD_ACCOUNT_OR_SMOKE_PROOF'
        source = $env:GITHUB_SHA
        nativeWindowsX64 = $true
        privileges = $privileges
    } | ConvertTo-Json -Depth 4 -Compress
    exit 0
} catch {
    # Never forward exception text, native identities, environment contents or incidental local paths.
    [Console]::Error.WriteLine('REFUSED hosted-account-capability-probe; no smoke or account action was performed')
    exit 1
}
