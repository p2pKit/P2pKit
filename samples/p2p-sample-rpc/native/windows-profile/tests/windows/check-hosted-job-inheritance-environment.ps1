# Implicit job inheritance experiment. NOT full protected-profile/JNI supervision or acceptance.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -lt 7 -or -not $IsWindows -or
    $env:GITHUB_ACTIONS -cne 'true' -or $env:GITHUB_EVENT_NAME -cne 'workflow_dispatch' -or
    $env:GITHUB_REPOSITORY -cne 'p2pKit/P2pKit' -or
    $env:GITHUB_REF -cne 'refs/heads/work/rpc-windows-validation-20261012' -or
    $env:GITHUB_JOB -cne 'rpc-windows-environment' -or $env:RUNNER_ENVIRONMENT -cne 'github-hosted' -or
    $env:RUNNER_OS -cne 'Windows' -or $env:RUNNER_ARCH -cne 'X64' -or
    $env:ImageOS -cnotin @('win22', 'win25-vs2026') -or
    $env:RPC_WINDOWS_ENVIRONMENT_IMAGE -cnotin @('windows-2022', 'windows-latest') -or
    ($env:RPC_WINDOWS_ENVIRONMENT_IMAGE -ceq 'windows-2022' -and $env:ImageOS -cne 'win22') -or
    ($env:RPC_WINDOWS_ENVIRONMENT_IMAGE -ceq 'windows-latest' -and $env:ImageOS -cne 'win25-vs2026') -or
    $env:GITHUB_SHA -cnotmatch '\A[0-9a-f]{40}\z') { throw 'Unapproved environment-probe scope' }

# Import only existing ordinary compiler/process helpers, not their guarded top-level test recipe.
$helper = Join-Path $PSScriptRoot 'check-hosted-policy-tests.ps1'
$tokens = $null; $errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile($helper, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw 'Invalid ordinary helper source' }
foreach ($name in @('Read-PolicyGit', 'Assert-CommandPath', 'Invoke-PolicyCommand')) {
    $functions = @($ast.FindAll({ param($node)
        $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -ceq $name
    }, $true))
    if ($functions.Count -ne 1) { throw 'Missing unique ordinary helper' }
    . ([scriptblock]::Create($functions[0].Extent.Text))
}
function Assert-EnvironmentFixtureImage([string]$Path) {
    # This producer is only the fixed environment/custody test fixture, NOT a replacement application launcher.
    # OS console creation follows the PE subsystem. Do not silently accept a console-subsystem image.
    $stream = [IO.File]::Open($Path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
    try {
        if ($stream.Length -lt 160 -or $stream.Length -gt 32MB) { throw 'Invalid fixture image length' }
        $reader = [IO.BinaryReader]::new($stream, [Text.Encoding]::ASCII, $true)
        try {
            $dos = $reader.ReadBytes(64)
            if ($dos.Length -ne 64 -or $dos[0] -ne 0x4d -or $dos[1] -ne 0x5a) { throw 'Missing DOS header' }
            $offset = [BitConverter]::ToInt32($dos, 60)
            if ($offset -lt 64 -or $offset -gt $stream.Length - 94) { throw 'Invalid PE header offset' }
            $stream.Position = $offset
            $header = $reader.ReadBytes(94)
            if ($header.Length -ne 94 -or [BitConverter]::ToUInt32($header, 0) -ne 0x00004550 -or
                [BitConverter]::ToUInt16($header, 4) -ne 0x8664 -or
                [BitConverter]::ToUInt16($header, 6) -lt 1 -or [BitConverter]::ToUInt16($header, 6) -gt 32 -or
                [BitConverter]::ToUInt16($header, 20) -ne 240 -or
                $offset + 264 + 40 * [BitConverter]::ToUInt16($header, 6) -gt $stream.Length -or
                ([BitConverter]::ToUInt16($header, 22) -band 0x2002) -ne 2 -or
                [BitConverter]::ToUInt16($header, 24) -ne 0x020b -or
                [BitConverter]::ToUInt32($header, 40) -eq 0 -or
                [BitConverter]::ToUInt32($header, 40) -ge [BitConverter]::ToUInt32($header, 80) -or
                [BitConverter]::ToUInt16($header, 92) -ne 2) { throw 'Expected AMD64 PE32+ GUI fixture' }
            return @{ scope = 'ENVIRONMENT_TEST_FIXTURE_NOT_APPLICATION_LAUNCHER';
                machine = 'AMD64'; optionalHeader = 'PE32+'; subsystem = 'WINDOWS_GUI'; subsystemValue = 2;
                entryPointRva = [BitConverter]::ToUInt32($header, 40); reviewedEntryOption = 'wmainCRTStartup' }
        } finally { $reader.Dispose() }
    } finally { $stream.Dispose() }
}
$source = (Read-PolicyGit -Arguments @('rev-parse', '--show-toplevel') -ExpectedLines 1).Trim()
$head = (Read-PolicyGit -Arguments @('rev-parse', 'HEAD') -ExpectedLines 1).Trim()
$tree = (Read-PolicyGit -Arguments @('rev-parse', 'HEAD^{tree}') -ExpectedLines 1).Trim()
if ($head -cne $env:GITHUB_SHA) { throw 'Wrong exact source' }
$null = Read-PolicyGit -Arguments @('status', '--porcelain') -ExpectedLines 0
$output = Join-Path $env:RUNNER_TEMP 'p2pkit-inheritance-environment'
if (Test-Path -LiteralPath $output) { throw 'Create-only environment evidence' }
$null = New-Item -ItemType Directory -Path $output
$inputs = @('profile_job_inheritance_environment_probe.c', 'profile_account_probe.c',
    'check-hosted-job-inheritance-environment.ps1', 'check-hosted-policy-tests.ps1')
$hashes = [ordered]@{}
$blobs = [ordered]@{}
foreach ($input in $inputs) {
    $hashes[$input] = (Get-FileHash -LiteralPath (Join-Path $PSScriptRoot $input) -Algorithm SHA256).Hash
    $blobs[$input] = (Read-PolicyGit -Arguments @('rev-parse',
        "HEAD:samples/p2p-sample-rpc/native/windows-profile/tests/windows/$input") -ExpectedLines 1).Trim()
}
$result = [ordered]@{
    scope = 'LOGON_JOB_INHERITANCE_EXPERIMENT_NOT_PROTECTED_SUPERVISION'
    source = $head; tree = $tree; run = $env:GITHUB_RUN_ID; attempt = $env:GITHUB_RUN_ATTEMPT
    requestedImage = $env:RPC_WINDOWS_ENVIRONMENT_IMAGE; imageOS = $env:ImageOS; imageVersion = $env:ImageVersion
    result = 'NOT_COMPLETED'; sourceHashes = $hashes; sourceBlobIds = $blobs
    profileRuntime = 'NOT_PERFORMED'; jniRuntime = 'NOT_PERFORMED'; protectedSupervisor = 'NOT_QUALIFIED'
    bootstrapAtomicJobAdmission = $false; sourceUnchanged = $false; negativeControls = @()
}
$receipt = [IO.File]::Open((Join-Path $output 'environment-result.json'), [IO.FileMode]::CreateNew,
    [IO.FileAccess]::Write, [IO.FileShare]::None)
try {
    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
    $cmd = Join-Path ([Environment]::SystemDirectory) 'cmd.exe'
    foreach ($path in @($source, $PSScriptRoot, $output, $vswhere, $cmd)) { Assert-CommandPath $path }
    $result.toolchainQuery = Invoke-PolicyCommand $vswhere `
        '-latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath' `
        $output 'vswhere' 10000
    if (-not $result.toolchainQuery.passed) { throw 'MSVC discovery failed' }
    $installation = @(Get-Content -LiteralPath (Join-Path $output 'vswhere-stdout.log'))
    if ($installation.Count -ne 1) { throw 'No unique installed MSVC' }
    $developer = Join-Path $installation[0] 'Common7/Tools/VsDevCmd.bat'
    Assert-CommandPath $developer
    $nativeSource = Join-Path $PSScriptRoot 'profile_job_inheritance_environment_probe.c'
    $exe = Join-Path $output 'p2pkit-inheritance-environment-probe.exe'
    $commandPath = Join-Path $output 'compile.cmd'
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
cl.exe /nologo /Bv /std:c11 /W4 /WX /O2 /MT /GS /sdl /guard:cf /D_WIN32_WINNT=0x0A00 ^
 "$nativeSource" /Fe:"$exe" ^
 /link /MACHINE:X64 /SUBSYSTEM:WINDOWS /ENTRY:wmainCRTStartup /DYNAMICBASE /HIGHENTROPYVA /NXCOMPAT /GUARD:CF ^
 /INCREMENTAL:NO /MANIFEST:EMBED /OPT:REF /OPT:ICF kernel32.lib kernelbase.lib advapi32.lib netapi32.lib bcrypt.lib
exit /b %ERRORLEVEL%
"@
    [IO.File]::WriteAllText($commandPath, $command, [Text.Encoding]::ASCII)
    $result.compilation = Invoke-PolicyCommand $cmd ('/d /s /c ""' + $commandPath + '""') $output 'compile' 60000
    if (-not $result.compilation.passed) { throw 'Environment probe compilation failed' }
    $binary = Get-Item -LiteralPath $exe
    if ($binary.Length -le 0 -or $binary.Length -gt 32MB -or
        $binary.Attributes.HasFlag([IO.FileAttributes]::ReparsePoint)) { throw 'Unexpected probe bytes' }
    $result.executable = @{ sha256 = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash; bytes = $binary.Length }
    $result.fixtureImage = Assert-EnvironmentFixtureImage $exe
    $cases = @(
        @{ arguments = '--unknown'; name = 'invalid'; exit = 2 },
        @{ arguments = '--standard-account-probe-child'; name = 'elevated-child'; exit = 3 }
    )
    foreach ($case in $cases) {
        $run = Invoke-PolicyCommand $exe $case.arguments $output $case.name 10000
        $result.negativeControls += @{ name = $case.name; expectedExit = $case.exit; execution = $run }
        if ($run.exitCode -ne $case.exit -or $run.timedOut -or $run.outputExceeded -or
            -not $run.processExitObserved -or -not $run.finalizationCompleted -or $run.elapsedMs -ge 10000) {
            throw 'Negative environment control failed'
        }
        if ((Get-Item -LiteralPath (Join-Path $output ($case.name + '-stderr.log'))).Length -ne 0) {
            throw 'Unexpected negative stderr'
        }
        $negativeText = [IO.File]::ReadAllText((Join-Path $output ($case.name + '-stdout.log')))
        if ($negativeText.Length -ne 0) { throw 'Unexpected negative stdout' }
    }
    $result.transferControls = @()
    $modes = @('normal', 'owner-close')
    for ($index = 0; $index -lt $modes.Count; $index++) {
        $mode = $modes[$index]
        $execution = Invoke-PolicyCommand $exe "--disposable-inheritance-$mode-probe" $output $mode 70000
        $text = [IO.File]::ReadAllText((Join-Path $output "$mode-stdout.log"))
        if ($text.Length -gt 4096 -or $text -notmatch '\A[^\r\n]+\r?\n\z' -or
            (Get-Item -LiteralPath (Join-Path $output "$mode-stderr.log")).Length -ne 0) {
            $result.transferControls += @{ mode = $mode; execution = $execution; result = 'INVALID_OBSERVATION' }
            throw 'Expected one bounded inheritance result'
        }
        $record = $text | ConvertFrom-Json -AsHashtable
        $result.transferControls += @{ mode = $mode; execution = $execution; observation = $record }
        $keys = @('scope', 'mode', 'result', 'stage', 'systemCode', 'accountCreated', 'childObserved',
            'inheritedMember', 'lastJobHandleClosed', 'exactTwoBeforeClose', 'emptyJobObserved',
            'childExitObserved', 'childExit', 'brokerExit', 'cleanupObserved',
            'profileRequested', 'nativeStorageExecuted', 'preCloseQuerySucceeded', 'preCloseActiveProcesses',
            'preCloseQueryError', 'preCloseListSucceeded', 'preCloseAssignedCount', 'preCloseListedCount',
            'preCloseInventoryError', 'preCloseBrokerCount', 'preCloseChildCount', 'preCloseConsoleCount',
            'preCloseOtherCount', 'preCloseRetiredCount', 'preCloseIdentityCheckedCount',
            'knownHandleAuditScope', 'knownHandleAuditPassed', 'knownHandleChecked', 'knownHandleAbsent',
            'knownHandleReused', 'knownHandleLeaked', 'knownHandleError', 'knownHandleHelperControlsPassed')
        if ($record.Count -ne $keys.Count) { throw 'Unexpected result shape' }
        foreach ($key in $keys) { if (-not $record.ContainsKey($key)) { throw 'Missing result field' } }
        foreach ($key in @('accountCreated', 'childObserved', 'inheritedMember', 'lastJobHandleClosed',
            'exactTwoBeforeClose', 'emptyJobObserved', 'childExitObserved',
            'cleanupObserved', 'profileRequested', 'nativeStorageExecuted', 'preCloseQuerySucceeded',
            'preCloseListSucceeded', 'knownHandleAuditPassed')) {
            if ($record[$key] -isnot [bool]) { throw 'Expected boolean observation' }
        }
        foreach ($key in @('mode', 'result', 'stage', 'systemCode', 'childExit', 'brokerExit', 'preCloseActiveProcesses',
            'preCloseQueryError', 'preCloseAssignedCount', 'preCloseListedCount', 'preCloseInventoryError',
            'preCloseBrokerCount', 'preCloseChildCount', 'preCloseConsoleCount', 'preCloseOtherCount',
            'preCloseRetiredCount', 'preCloseIdentityCheckedCount', 'knownHandleChecked', 'knownHandleAbsent',
            'knownHandleReused', 'knownHandleLeaked', 'knownHandleError', 'knownHandleHelperControlsPassed')) {
            if ($record[$key] -isnot [int] -and $record[$key] -isnot [long]) { throw 'Expected integer observation' }
        }
        if (-not $execution.passed -or $record.scope -cne $result.scope -or $record.mode -ne $index -or
            $record.result -ne 0 -or $record.stage -ne 6 -or $record.systemCode -ne 0 -or
            -not $record.accountCreated -or -not $record.childObserved -or -not $record.childExitObserved -or
            -not $record.cleanupObserved -or -not $record.inheritedMember -or $record.profileRequested -or $record.nativeStorageExecuted -or
            $record.knownHandleAuditScope -cne 'THREE_BROKER_VALUES_ONLY_NOT_EXHAUSTIVE' -or
            -not $record.knownHandleAuditPassed -or $record.knownHandleChecked -ne 3 -or
            $record.knownHandleAbsent -lt 0 -or $record.knownHandleReused -lt 0 -or
            $record.knownHandleAbsent + $record.knownHandleReused -ne 3 -or $record.knownHandleLeaked -ne 0 -or
            $record.knownHandleError -ne 0 -or $record.knownHandleHelperControlsPassed -ne 6 -or
            $record.preCloseQueryError -ne 0 -or $record.preCloseInventoryError -ne 0 -or
            ($index -eq 0 -and ($record.preCloseQuerySucceeded -or $record.preCloseActiveProcesses -ne 4294967295)) -or
            ($index -ne 0 -and (-not $record.preCloseQuerySucceeded -or $record.preCloseActiveProcesses -ne 2)) -or
            ($index -eq 0 -and ($record.lastJobHandleClosed -or $record.exactTwoBeforeClose -or
                -not $record.emptyJobObserved -or $record.childExit -ne 42 -or $record.brokerExit -ne 0)) -or
            ($index -ne 0 -and (-not $record.lastJobHandleClosed -or -not $record.exactTwoBeforeClose -or
                $record.emptyJobObserved -or $record.childExit -in @(42, 259) -or $record.brokerExit -eq 259))) {
            throw 'Implicit inheritance or automatic-retirement control failed'
        }
    }
    foreach ($input in $inputs) {
        if ((Get-FileHash -LiteralPath (Join-Path $PSScriptRoot $input) -Algorithm SHA256).Hash -cne
            $hashes[$input]) { throw 'Input changed' }
    }
    if ((Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash -cne $result.executable.sha256 -or
        (Read-PolicyGit -Arguments @('rev-parse', 'HEAD') -ExpectedLines 1) -cne $head) { throw 'Source/EXE changed' }
    $null = Read-PolicyGit -Arguments @('status', '--porcelain') -ExpectedLines 0
    $result.sourceUnchanged = $true
    $result.result = 'PASS'
    Write-Output 'PASS focused implicit job membership and last-owner-close controls; NOT protected profile/JNI qualification'
} finally {
    try {
        $bytes = [Text.Encoding]::UTF8.GetBytes(($result | ConvertTo-Json -Depth 9) + "`n")
        $receipt.Write($bytes, 0, $bytes.Length)
    } finally { $receipt.Dispose() }
}
