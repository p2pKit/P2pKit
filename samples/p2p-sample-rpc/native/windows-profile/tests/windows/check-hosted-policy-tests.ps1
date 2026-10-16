# Actual MSVC execution of fixed, memory-only C policy units. NOT native profile/storage qualification.
# No Win32/JNI implementation, DLL, custody smoke, account operation or protected supervisor is used.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -lt 7 -or -not $IsWindows -or
    $env:GITHUB_ACTIONS -cne 'true' -or $env:GITHUB_EVENT_NAME -cne 'workflow_dispatch' -or
    $env:GITHUB_REPOSITORY -cne 'p2pKit/P2pKit' -or
    $env:GITHUB_REF -cne 'refs/heads/work/rpc-windows-validation-20261012' -or
    $env:GITHUB_JOB -cne 'rpc-windows' -or $env:RUNNER_ENVIRONMENT -cne 'github-hosted' -or
    $env:RUNNER_OS -cne 'Windows' -or $env:RUNNER_ARCH -cne 'X64' -or $env:ImageOS -cne 'win22' -or
    [Runtime.InteropServices.RuntimeInformation]::OSArchitecture -ne 'X64' -or
    [Runtime.InteropServices.RuntimeInformation]::ProcessArchitecture -ne 'X64' -or
    $env:GITHUB_SHA -cnotmatch '\A[0-9a-f]{40}\z') {
    throw 'Expected the exact owner-authorized hosted Windows policy-unit job'
}
function Read-PolicyGit([string[]]$Arguments, [int]$ExpectedLines = -1) {
    $lines = @(& git @Arguments)
    if ($LASTEXITCODE -ne 0 -or ($ExpectedLines -ge 0 -and $lines.Count -ne $ExpectedLines)) {
        throw 'Git source observation failed or returned an unexpected inventory'
    }
    return $lines
}
$source = (Read-PolicyGit -Arguments @('rev-parse', '--show-toplevel') -ExpectedLines 1).Trim()
if ((Read-PolicyGit -Arguments @('rev-parse', 'HEAD') -ExpectedLines 1) -cne $env:GITHUB_SHA) {
    throw 'Expected clean exact-source checkout'
}
$null = Read-PolicyGit -Arguments @('status', '--porcelain') -ExpectedLines 0
$native = Join-Path $source 'samples/p2p-sample-rpc/native/windows-profile'
$output = Join-Path $env:RUNNER_TEMP 'p2pkit-windows-validation/policy-units'
if (Test-Path -LiteralPath $output) { throw 'Policy-unit output must be new' }
$null = New-Item -ItemType Directory -Path $output

# Each selection names precisely one reviewed portable test. No caller source/EXE/path override or glob.
$tests = @('policy', 'stage', 'lock', 'delete', 'child', 'role', 'candidate', 'rename',
    'sync', 'replace', 'write', 'record_delete', 'namespace', 'publication_probe', 'creation_result', 'token_sid')
$inputs = @('profile_policy.c', 'profile_policy.h', 'tests/windows/check-hosted-policy-tests.ps1')
$inputs += @($tests | ForEach-Object { "tests/profile_$($_)_test.c" })
$hashes = [ordered]@{}
$blobs = [ordered]@{}
foreach ($relative in $inputs) {
    $item = Get-Item -LiteralPath (Join-Path $native $relative)
    if ($item.Attributes.HasFlag([IO.FileAttributes]::ReparsePoint) -or $item.Length -gt 1MB) {
        throw 'Unexpected policy-unit source input'
    }
    $hashes[$relative] = (Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    $blobs[$relative] = (Read-PolicyGit -Arguments @('rev-parse',
        "HEAD:samples/p2p-sample-rpc/native/windows-profile/$relative") -ExpectedLines 1).Trim()
    if ($blobs[$relative] -cnotmatch '\A[0-9a-f]{40}\z') {
        throw 'Missing exact source blob'
    }
}
$receipt = [ordered]@{
    scope = 'WINDOWS_NATIVE_POLICY_UNIT_NOT_STORAGE_OR_RELEASE'
    source = $env:GITHUB_SHA
    tree = (Read-PolicyGit -Arguments @('rev-parse', 'HEAD^{tree}') -ExpectedLines 1).Trim()
    run = $env:GITHUB_RUN_ID
    attempt = $env:GITHUB_RUN_ATTEMPT
    result = 'NOT_COMPLETED'
    profileNativeExecution = 'NOT_PERFORMED'
    nativeStorageExecution = 'NOT_PERFORMED'
    smokeSupervisorQualification = 'NOT_PERFORMED'
    sourceHashes = $hashes
    sourceBlobIds = $blobs
    sourceEol = @(Read-PolicyGit -Arguments (@('ls-files', '--eol', '--') + @($inputs | ForEach-Object {
        "samples/p2p-sample-rpc/native/windows-profile/$_"
    })) -ExpectedLines 19)
    sourceUnchanged = $false
    tests = @()
}

function Assert-CommandPath([string]$Path) {
    if (-not [IO.Path]::IsPathFullyQualified($Path) -or $Path -match '[\r\n"%!^&|<>]' -or
        $Path.ToCharArray().Where({ [int]$_ -gt 127 }).Count) { throw 'Unsupported command path' }
}

# Ordinary compiler/unit children only. Original Process ownership, finite waits and bounded pipe capture;
# NOT atomic Windows job admission, a profile smoke supervisor or proof of arbitrary descendant cleanup.
# Process creation/finalization remain additionally bounded by the hosted step/job, not a claimed syscall timeout.
function Invoke-PolicyCommand([string]$File, [string]$Arguments, [string]$Directory,
                              [string]$Prefix, [int]$Milliseconds) {
    $row = [ordered]@{ exitCode = $null; timedOut = $false; outputExceeded = $false;
        processExitObserved = $false; finalizationCompleted = $false; elapsedMs = 0; passed = $false }
    $process = [Diagnostics.Process]::new()
    $process.StartInfo.FileName = $File
    $process.StartInfo.Arguments = $Arguments
    $process.StartInfo.WorkingDirectory = $Directory
    $process.StartInfo.UseShellExecute = $false
    $process.StartInfo.CreateNoWindow = $true
    $process.StartInfo.RedirectStandardOutput = $true
    $process.StartInfo.RedirectStandardError = $true
    $logs = @()
    $started = $false
    $clock = [Diagnostics.Stopwatch]::StartNew()
    try {
        foreach ($kind in @('stdout', 'stderr')) {
            $logs += [IO.File]::Open((Join-Path $Directory "$Prefix-$kind.log"),
                [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::Read)
        }
        $started = $process.Start()
        if (-not $started) { throw 'Process creation did not return an owner' }
        $streams = @($process.StandardOutput.BaseStream, $process.StandardError.BaseStream)
        $buffers = @([byte[]]::new(4096), [byte[]]::new(4096))
        $reads = @($streams[0].ReadAsync($buffers[0], 0, 4096), $streams[1].ReadAsync($buffers[1], 0, 4096))
        $done = @($false, $false)
        $counts = @(0, 0)
        while (-not ($done[0] -and $done[1] -and $process.HasExited)) {
            if ($clock.ElapsedMilliseconds -ge $Milliseconds) { $row.timedOut = $true; throw 'Command deadline' }
            for ($index = 0; $index -lt 2; $index++) {
                if (-not $done[$index] -and $reads[$index].IsCompleted) {
                    $count = $reads[$index].GetAwaiter().GetResult()
                    if ($count -eq 0) { $done[$index] = $true; continue }
                    $counts[$index] += $count
                    if ($counts[$index] -gt 65536) { $row.outputExceeded = $true; throw 'Command output bound' }
                    $logs[$index].Write($buffers[$index], 0, $count)
                    $reads[$index] = $streams[$index].ReadAsync($buffers[$index], 0, 4096)
                }
            }
            [Threading.Thread]::Sleep(10)
        }
        $row.processExitObserved = $true
        $row.exitCode = $process.ExitCode
        $row.passed = $row.exitCode -eq 0 -and $clock.ElapsedMilliseconds -lt $Milliseconds
        if ($clock.ElapsedMilliseconds -ge $Milliseconds) { $row.timedOut = $true }
    } catch {
        # Source/compiler diagnostics are bounded files; never dump arbitrary environment/exception text.
        $row.passed = $false
    } finally {
        $finalized = $true
        try {
            if ($started -and -not $process.HasExited) {
                $process.Kill($true)
                $row.processExitObserved = $process.WaitForExit(5000)
            } elseif ($started) { $row.processExitObserved = $true }
        } catch { $finalized = $false }
        if ($started) {
            try { $process.StandardOutput.Dispose() } catch { $finalized = $false }
            try { $process.StandardError.Dispose() } catch { $finalized = $false }
        }
        foreach ($log in $logs) { try { $log.Dispose() } catch { $finalized = $false } }
        try { $process.Dispose() } catch { $finalized = $false }
        $row.elapsedMs = $clock.ElapsedMilliseconds
        $clock.Stop()
        if ($row.elapsedMs -ge $Milliseconds) { $row.timedOut = $true }
        $row.finalizationCompleted = $finalized
        $row.passed = $row.passed -and $finalized -and $row.processExitObserved -and
            $row.elapsedMs -lt $Milliseconds
    }
    return $row
}

try {
    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
    $commandProcessor = Join-Path ([Environment]::SystemDirectory) 'cmd.exe'
    foreach ($path in @($source, $native, $output, $vswhere, $commandProcessor)) { Assert-CommandPath $path }
    $query = Invoke-PolicyCommand $vswhere `
        '-latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath' `
        $output 'vswhere' 10000
    $receipt.toolchainQuery = $query
    if (-not $query.passed) { throw 'MSVC discovery failed' }
    $installation = @(Get-Content -LiteralPath (Join-Path $output 'vswhere-stdout.log'))
    if ($installation.Count -ne 1) { throw 'Expected one MSVC installation' }
    $developer = Join-Path $installation[0] 'Common7/Tools/VsDevCmd.bat'
    Assert-CommandPath $developer
    foreach ($test in $tests) {
        $case = Join-Path $output $test
        $null = New-Item -ItemType Directory -Path $case
        $testSource = Join-Path $native "tests/profile_$($test)_test.c"
        $executable = Join-Path $case "profile_$($test)_test.exe"
        $commandPath = Join-Path $case 'compile.cmd'
        foreach ($path in @($case, $testSource, $executable, $commandPath)) { Assert-CommandPath $path }
        $command = @"
@echo off
setlocal DisableDelayedExpansion
set "INCLUDE="
set "LIB="
set "LIBPATH="
set "ERRORLEVEL="
call "$developer" -arch=x64 -host_arch=x64
if errorlevel 1 exit /b 2
if /i not "%VSCMD_ARG_TGT_ARCH%"=="x64" exit /b 2
set "CL="
set "_CL_="
set "LINK="
set "_LINK_="
set "ERRORLEVEL="
cl.exe /nologo /Bv /std:c11 /W4 /WX /O2 /MT /GS /sdl /guard:cf /UNDEBUG ^
 "$native\profile_policy.c" "$testSource" /Fe:"$executable" ^
 /link /MACHINE:X64 /DYNAMICBASE /HIGHENTROPYVA /NXCOMPAT /GUARD:CF ^
 /INCREMENTAL:NO /MANIFEST:EMBED /OPT:REF /OPT:ICF
exit /b %ERRORLEVEL%
"@
        [IO.File]::WriteAllText($commandPath, $command, [Text.Encoding]::ASCII)
        $entry = [ordered]@{ name = $test; execution = 'NOT_PERFORMED' }
        $receipt.tests += $entry
        $entry.compilation = Invoke-PolicyCommand $commandProcessor ('/d /s /c ""' + $commandPath + '""') `
            $case 'compile' 60000
        if (-not $entry.compilation.passed) { throw 'Policy-unit compilation failed' }
        $binary = Get-Item -LiteralPath $executable
        if ($binary.Length -le 0 -or $binary.Length -gt 32MB -or
            $binary.Attributes.HasFlag([IO.FileAttributes]::ReparsePoint)) { throw 'Unexpected policy-unit executable' }
        $entry.executable = @{ name = $binary.Name; bytes = $binary.Length;
            sha256 = (Get-FileHash -LiteralPath $executable -Algorithm SHA256).Hash.ToLowerInvariant() }
        $entry.execution = Invoke-PolicyCommand $executable '' $case 'test' 10000
        if (-not $entry.execution.passed) { throw 'Policy-unit execution failed' }
        if ((Get-FileHash -LiteralPath $executable -Algorithm SHA256).Hash.ToLowerInvariant() -cne
            $entry.executable.sha256) { throw 'Policy-unit executable changed during execution' }
    }
    foreach ($relative in $inputs) {
        if ((Get-FileHash -LiteralPath (Join-Path $native $relative) -Algorithm SHA256).Hash.ToLowerInvariant() -cne
            $hashes[$relative]) { throw 'Policy-unit source changed' }
    }
    if ((Read-PolicyGit -Arguments @('rev-parse', 'HEAD') -ExpectedLines 1) -cne $receipt.source -or
        (Read-PolicyGit -Arguments @('rev-parse', 'HEAD^{tree}') -ExpectedLines 1) -cne $receipt.tree -or
        $receipt.tests.Count -ne 16) { throw 'Policy-unit source/inventory changed' }
    $null = Read-PolicyGit -Arguments @('status', '--porcelain') -ExpectedLines 0
    $receipt.sourceUnchanged = $true
    $receipt.result = 'PASS'
} finally {
    $receipt | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $output 'policy-unit-results.json') -Encoding utf8
}
