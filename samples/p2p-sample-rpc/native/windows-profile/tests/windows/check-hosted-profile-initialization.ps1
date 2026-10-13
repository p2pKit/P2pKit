# Explicit OS-profile initialization experiment. NOT protected-profile/JNI supervision or acceptance.
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
# Reuse the bounded GUI-fixture inspector without invoking the inheritance test recipe.
$fixtureHelper = Join-Path $PSScriptRoot 'check-hosted-job-inheritance-environment.ps1'
$fixtureAst = [Management.Automation.Language.Parser]::ParseFile($fixtureHelper, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw 'Invalid fixture helper source' }
$fixtureFunctions = @($fixtureAst.FindAll({ param($node)
    $node -is [Management.Automation.Language.FunctionDefinitionAst] -and
        $node.Name -ceq 'Assert-EnvironmentFixtureImage'
}, $true))
if ($fixtureFunctions.Count -ne 1) { throw 'Missing unique environment fixture inspector' }
. ([scriptblock]::Create($fixtureFunctions[0].Extent.Text))
$source = (Read-PolicyGit -Arguments @('rev-parse', '--show-toplevel') -ExpectedLines 1).Trim()
$head = (Read-PolicyGit -Arguments @('rev-parse', 'HEAD') -ExpectedLines 1).Trim()
$tree = (Read-PolicyGit -Arguments @('rev-parse', 'HEAD^{tree}') -ExpectedLines 1).Trim()
if ($head -cne $env:GITHUB_SHA) { throw 'Wrong exact source' }
$null = Read-PolicyGit -Arguments @('status', '--porcelain') -ExpectedLines 0
$output = Join-Path $env:RUNNER_TEMP 'p2pkit-profile-initialization'
if (Test-Path -LiteralPath $output) { throw 'Create-only environment evidence' }
$null = New-Item -ItemType Directory -Path $output
$inputs = @('profile_initialization_environment_probe.c', 'profile_account_probe.c',
    'profile_hive_namespace_observer.h', 'profile_hive_namespace_observer_control.c',
    'check-hosted-profile-initialization.ps1', 'check-hosted-policy-tests.ps1',
    'check-hosted-job-inheritance-environment.ps1')
$hashes = [ordered]@{}
$blobs = [ordered]@{}
foreach ($input in $inputs) {
    $hashes[$input] = (Get-FileHash -LiteralPath (Join-Path $PSScriptRoot $input) -Algorithm SHA256).Hash
    $blobs[$input] = (Read-PolicyGit -Arguments @('rev-parse',
        "HEAD:samples/p2p-sample-rpc/native/windows-profile/tests/windows/$input") -ExpectedLines 1).Trim()
}
$result = [ordered]@{
    scope = 'OS_PROFILE_INITIALIZATION_NOT_PROTECTED_STORAGE_OR_SUPERVISION'
    source = $head; tree = $tree; run = $env:GITHUB_RUN_ID; attempt = $env:GITHUB_RUN_ATTEMPT
    requestedImage = $env:RPC_WINDOWS_ENVIRONMENT_IMAGE; imageOS = $env:ImageOS; imageVersion = $env:ImageVersion
    result = 'NOT_COMPLETED'; sourceHashes = $hashes; sourceBlobIds = $blobs
    osProfileInitialization = 'NOT_COMPLETED'; profileRuntime = 'NOT_PERFORMED'; jniRuntime = 'NOT_PERFORMED'; protectedSupervisor = 'NOT_QUALIFIED'
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
    $nativeSource = Join-Path $PSScriptRoot 'profile_initialization_environment_probe.c'
    $exe = Join-Path $output 'p2pkit-profile-initialization-probe.exe'
    $controlSource = Join-Path $PSScriptRoot 'profile_hive_namespace_observer_control.c'
    $controlExe = Join-Path $output 'p2pkit-hive-observer-controls.exe'
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
 /INCREMENTAL:NO /MANIFEST:EMBED /OPT:REF /OPT:ICF kernel32.lib advapi32.lib netapi32.lib bcrypt.lib userenv.lib shell32.lib ole32.lib uuid.lib ntdll.lib
if errorlevel 1 exit /b %ERRORLEVEL%
cl.exe /nologo /std:c11 /W4 /WX /O2 /MT /GS /sdl /guard:cf "$controlSource" /Fe:"$controlExe" ^
 /link /MACHINE:X64 /DYNAMICBASE /HIGHENTROPYVA /NXCOMPAT /GUARD:CF /INCREMENTAL:NO /OPT:REF /OPT:ICF
exit /b %ERRORLEVEL%
"@
    [IO.File]::WriteAllText($commandPath, $command, [Text.Encoding]::ASCII)
    $result.compilation = Invoke-PolicyCommand $cmd ('/d /s /c ""' + $commandPath + '""') $output 'compile' 60000
    if (-not $result.compilation.passed) { throw 'Environment probe compilation failed' }
    $result.fixtureImage = Assert-EnvironmentFixtureImage $exe
    $binary = Get-Item -LiteralPath $exe
    if ($binary.Length -le 0 -or $binary.Length -gt 32MB -or
        $binary.Attributes.HasFlag([IO.FileAttributes]::ReparsePoint)) { throw 'Unexpected probe bytes' }
    $result.executable = @{ sha256 = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash; bytes = $binary.Length }
    $control = Get-Item -LiteralPath $controlExe
    if ($control.Length -le 0 -or $control.Length -gt 32MB -or
        $control.Attributes.HasFlag([IO.FileAttributes]::ReparsePoint)) { throw 'Unexpected control bytes' }
    $result.controlExecutable = @{ sha256 = (Get-FileHash -LiteralPath $controlExe -Algorithm SHA256).Hash; bytes = $control.Length }
    $result.controlExecution = Invoke-PolicyCommand $controlExe '' $output 'observer-controls' 10000
    $controlText = [IO.File]::ReadAllText((Join-Path $output 'observer-controls-stdout.log'))
    if (-not $result.controlExecution.passed -or $controlText -cnotmatch '\APASS 32 inert parent-namespace/notification ownership controls; NOT Windows runtime evidence\r?\n\z' -or
        (Get-Item -LiteralPath (Join-Path $output 'observer-controls-stderr.log')).Length -ne 0) {
        throw 'Inert namespace observer controls failed'
    }
    $cases = @(
        @{ arguments = '--unknown'; name = 'invalid'; exit = 2 },
        @{ arguments = '--profile-known-folder-child'; name = 'elevated-child'; exit = 3 }
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
    $result.execution = Invoke-PolicyCommand $exe '--disposable-os-profile-probe' $output 'probe' 70000
    $phaseText = [IO.File]::ReadAllText((Join-Path $output 'probe-stderr.log'))
    if ($phaseText.Length -gt 256 -or $phaseText -cnotmatch '\A(?:(?:P2PKIT_HIVE_PHASE [1-8]|P2PKIT_HIVE_SNAPSHOT [1-3] [0-9]{1,10})\r?\n){0,9}\z') {
        throw 'Unexpected native observer diagnostic output'
    }
    $phases = @([regex]::Matches($phaseText, 'P2PKIT_HIVE_PHASE ([1-8])') | ForEach-Object { [int]$_.Groups[1].Value })
    if (@($phases | Select-Object -Unique).Count -ne $phases.Count) { throw 'Repeated phase diagnostics' }
    $result.hiveObserverPhases = $phases
    # At most one diagnostic parent scan. State2 is NOT stabilized absence or acceptance.
    $snapshots = @([regex]::Matches($phaseText, 'P2PKIT_HIVE_SNAPSHOT ([1-3]) ([0-9]{1,10})'))
    if ($snapshots.Count -gt 1) { throw 'Repeated snapshot diagnostic' }
    $result.hiveObserverSnapshot = $null
    if ($snapshots.Count -eq 1) {
        $snapshotState = [int]$snapshots[0].Groups[1].Value
        $snapshotStatus = [ulong]$snapshots[0].Groups[2].Value
        if ($snapshotStatus -gt [uint32]::MaxValue -or
            ($snapshotState -eq 1 -and $snapshotStatus -ne 0) -or
            ($snapshotState -eq 2 -and $snapshotStatus -ne 259) -or
            ($snapshotState -eq 3 -and $snapshotStatus -in @(0, 259))) {
            throw 'Inconsistent snapshot diagnostic'
        }
        $result.hiveObserverSnapshot = @{ state = $snapshotState; status = $snapshotStatus;
            scope = 'ONE_PARENT_ENUMERATION_NOT_STABILIZED_ABSENCE_OR_ACCEPTANCE' }
    }

    $text = [IO.File]::ReadAllText((Join-Path $output 'probe-stdout.log'))
    if ($text.Length -gt 4096 -or $text -notmatch '\A[^\r\n]+\r?\n\z') {
        throw 'Expected one bounded environment result'
    }
    $record = $text | ConvertFrom-Json -AsHashtable
    $result.observation = $record
    $expectedKeys = @('scope', 'launchApi', 'result', 'stage', 'systemCode', 'accountCreated', 'created',
        'assignedBeforeResume', 'resumed', 'profileProbeExit', 'cleanupObserved', 'bootstrapAtomicJobAdmission',
        'profileRequested', 'nativeStorageExecuted', 'finalJobActiveProcesses', 'jobQueryError', 'handleCloseError', 'firstJobActiveProcesses', 'jobObservations',
        'hiveAbsentBefore', 'hiveLoadedBeforeResume', 'hiveUnloadedAfterExit',
        'hiveQueryError', 'hiveCloseError', 'hiveObservations', 'namespaceAbsenceObserved', 'namespaceRetired',
        'namespaceOpenStatus', 'namespaceEnumerationStatus', 'namespaceNotificationStatus', 'namespaceCloseStatus',
        'namespaceSystemError', 'namespaceScans')
    if ($record.Count -ne $expectedKeys.Count) { throw 'Unexpected result shape' }
    foreach ($key in $expectedKeys) { if (-not $record.ContainsKey($key)) { throw 'Missing result field' } }
    foreach ($key in @('accountCreated', 'created', 'assignedBeforeResume', 'resumed', 'cleanupObserved',
        'bootstrapAtomicJobAdmission', 'profileRequested', 'nativeStorageExecuted',
        'hiveAbsentBefore', 'hiveLoadedBeforeResume', 'hiveUnloadedAfterExit',
        'namespaceAbsenceObserved', 'namespaceRetired')) {
        if ($record[$key] -isnot [bool]) { throw 'Expected boolean observation' }
    }
    foreach ($key in @('result', 'stage', 'systemCode', 'profileProbeExit', 'finalJobActiveProcesses', 'jobQueryError', 'handleCloseError', 'firstJobActiveProcesses', 'jobObservations',
        'hiveQueryError', 'hiveCloseError', 'hiveObservations', 'namespaceOpenStatus', 'namespaceEnumerationStatus',
        'namespaceNotificationStatus', 'namespaceCloseStatus', 'namespaceSystemError', 'namespaceScans')) {
        if ($record[$key] -isnot [int] -and $record[$key] -isnot [long]) { throw 'Expected integer observation' }
    }
    if (-not $result.execution.passed -or $record.scope -cne $result.scope -or
        $record.launchApi -cne 'CreateProcessWithLogonW' -or $record.result -ne 0 -or $record.stage -ne 8 -or
        $record.systemCode -ne 0 -or $record.finalJobActiveProcesses -ne 0 -or
        $record.jobQueryError -ne 0 -or $record.handleCloseError -ne 0 -or $record.jobObservations -lt 1 -or $record.profileProbeExit -ne 0 -or -not $record.accountCreated -or
        -not $record.created -or -not $record.assignedBeforeResume -or -not $record.resumed -or
        -not $record.cleanupObserved -or $record.bootstrapAtomicJobAdmission -or
        -not $record.profileRequested -or $record.nativeStorageExecuted -or -not $record.hiveAbsentBefore -or
        -not $record.hiveLoadedBeforeResume -or -not $record.hiveUnloadedAfterExit -or
        $record.hiveQueryError -ne 0 -or $record.hiveCloseError -ne 0 -or $record.hiveObservations -lt 2 -or
        -not $record.namespaceAbsenceObserved -or -not $record.namespaceRetired -or $record.namespaceOpenStatus -ne 0 -or
        $record.namespaceEnumerationStatus -ne 259 -or $record.namespaceNotificationStatus -ne 0 -or
        $record.namespaceCloseStatus -ne 0 -or $record.namespaceSystemError -ne 0 -or $record.namespaceScans -lt 1) { throw 'Environment feasibility did not pass' }
    foreach ($input in $inputs) {
        if ((Get-FileHash -LiteralPath (Join-Path $PSScriptRoot $input) -Algorithm SHA256).Hash -cne
            $hashes[$input]) { throw 'Input changed' }
    }
    if ((Get-FileHash -LiteralPath $controlExe -Algorithm SHA256).Hash -cne $result.controlExecutable.sha256) { throw 'Control bytes changed' }
    if ((Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash -cne $result.executable.sha256 -or
        (Read-PolicyGit -Arguments @('rev-parse', 'HEAD') -ExpectedLines 1) -cne $head) { throw 'Source/EXE changed' }
    $null = Read-PolicyGit -Arguments @('status', '--porcelain') -ExpectedLines 0
    $result.sourceUnchanged = $true
    $result.osProfileInitialization = 'PASS'
    $result.result = 'PASS'
    Write-Output 'PASS OS-created standard-user profile/known folders/NTFS/hive retirement; NOT protected profile/JNI qualification'
} finally {
    try {
        $bytes = [Text.Encoding]::UTF8.GetBytes(($result | ConvertTo-Json -Depth 9) + "`n")
        $receipt.Write($bytes, 0, $bytes.Length)
    } finally { $receipt.Dispose() }
}
