# Explicit WithLogonW JOB_LIST API experiment. NOT a fallback or protected-profile/JNI qualification.
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

function Assert-AtomicLogonObservation {
    param($Record, $Execution)
    # No typed/coercing parameters: arrays, strings and bool-as-int values must not become evidence.
    $requiredTrue = @('accountCreated', 'accountEnabled', 'accountDisabledObserved', 'creationAttempted',
        'startupInfoExRequested', 'jobListRequested', 'created', 'memberBeforeResume', 'tokenMatched',
        'resumed', 'childExecuted', 'childExitObserved', 'jobEmptyObserved', 'cleanupObserved')
    $requiredFalse = @('explicitFailureCleanup', 'profileRequested', 'nativeStorageExecuted',
        'inFlightCreationQualified', 'protectedSupervisorQualified')
    $integerKeys = @('result', 'stage', 'systemCode', 'childExit', 'finalJobActiveProcesses', 'jobObservations')
    $keys = @('scope', 'launchApi') + $requiredTrue + $requiredFalse + $integerKeys
    if ($Record -isnot [hashtable] -or $Record.psbase.Count -ne $keys.Count) {
        throw 'Unexpected atomic-logon result shape'
    }
    foreach ($key in $Record.psbase.Keys) {
        if ($key -isnot [string] -or $key -cnotin $keys) { throw 'Unexpected atomic-logon field' }
    }
    foreach ($key in $keys) {
        if (-not $Record.ContainsKey($key)) { throw 'Missing atomic-logon field' }
    }
    if ($Record['scope'] -isnot [string] -or $Record['launchApi'] -isnot [string] -or
        $Record['scope'] -cne 'ATOMIC_LOGON_JOB_LIST_API_PROBE_NOT_PROTECTED_SUPERVISION' -or
        $Record['launchApi'] -cne 'CreateProcessWithLogonW') { throw 'Wrong atomic-logon scope/API' }
    foreach ($key in $requiredTrue + $requiredFalse) {
        if ($Record[$key] -isnot [bool]) { throw 'Expected scalar atomic-logon boolean' }
    }
    foreach ($key in $integerKeys) {
        if (($Record[$key] -isnot [int] -and $Record[$key] -isnot [long]) -or
            $Record[$key] -lt 0 -or $Record[$key] -gt [uint32]::MaxValue) {
            throw 'Expected scalar atomic-logon DWORD'
        }
    }
    foreach ($key in $requiredTrue) { if (-not $Record[$key]) { throw 'Missing atomic-logon observation' } }
    foreach ($key in $requiredFalse) { if ($Record[$key]) { throw 'Forbidden atomic-logon substitute' } }
    # An API refusal (including error87/1314), absent observation or explicit failure cleanup is FAILED.
    if ($Record.result -ne 0 -or $Record.stage -ne 10 -or $Record.systemCode -ne 0 -or
        $Record.childExit -ne 42 -or $Record.finalJobActiveProcesses -ne 0 -or
        $Record.jobObservations -lt 1 -or $Record.jobObservations -gt 65536) {
        throw 'Atomic-logon API experiment did not pass'
    }
    $executionKeys = @('exitCode', 'timedOut', 'outputExceeded', 'processExitObserved',
        'finalizationCompleted', 'elapsedMs', 'passed')
    if ($Execution -isnot [Collections.IDictionary] -or $Execution.psbase.Count -ne $executionKeys.Count) {
        throw 'Unexpected atomic-logon execution shape'
    }
    foreach ($key in $Execution.psbase.Keys) {
        if ($key -isnot [string] -or $key -cnotin $executionKeys) { throw 'Unexpected execution field' }
    }
    foreach ($key in $executionKeys) {
        if (-not $Execution.Contains($key)) { throw 'Missing execution field' }
    }
    foreach ($key in @('passed', 'processExitObserved', 'finalizationCompleted', 'timedOut', 'outputExceeded')) {
        if ($Execution[$key] -isnot [bool]) { throw 'Expected scalar execution boolean' }
    }
    foreach ($key in @('exitCode', 'elapsedMs')) {
        if (($Execution[$key] -isnot [int] -and $Execution[$key] -isnot [long]) -or $Execution[$key] -lt 0) {
            throw 'Expected nonnegative scalar execution integer'
        }
    }
    if (-not $Execution.passed -or -not $Execution.processExitObserved -or -not $Execution.finalizationCompleted -or
        $Execution.timedOut -or $Execution.outputExceeded -or $Execution.exitCode -ne 0 -or
        $Execution.elapsedMs -ge 70000) { throw 'Atomic-logon execution failed or exceeded its original deadline' }
}

$source = (Read-PolicyGit -Arguments @('rev-parse', '--show-toplevel') -ExpectedLines 1).Trim()
$head = (Read-PolicyGit -Arguments @('rev-parse', 'HEAD') -ExpectedLines 1).Trim()
$tree = (Read-PolicyGit -Arguments @('rev-parse', 'HEAD^{tree}') -ExpectedLines 1).Trim()
if ($head -cne $env:GITHUB_SHA) { throw 'Wrong exact source' }
$null = Read-PolicyGit -Arguments @('status', '--porcelain') -ExpectedLines 0
$output = Join-Path $env:RUNNER_TEMP 'p2pkit-atomic-logon-environment'
if (Test-Path -LiteralPath $output) { throw 'Create-only environment evidence' }
$null = New-Item -ItemType Directory -Path $output
$inputs = @('profile_atomic_logon_environment_probe.c', 'profile_account_probe.c',
    'check-hosted-atomic-logon-environment.ps1', 'check-hosted-policy-tests.ps1',
    'check-hosted-job-inheritance-environment.ps1')
$hashes = [ordered]@{}
$blobs = [ordered]@{}
foreach ($input in $inputs) {
    $hashes[$input] = (Get-FileHash -LiteralPath (Join-Path $PSScriptRoot $input) -Algorithm SHA256).Hash
    $blobs[$input] = (Read-PolicyGit -Arguments @('rev-parse',
        "HEAD:samples/p2p-sample-rpc/native/windows-profile/tests/windows/$input") -ExpectedLines 1).Trim()
}
$result = [ordered]@{
    scope = 'ATOMIC_LOGON_JOB_LIST_API_PROBE_NOT_PROTECTED_SUPERVISION'
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
    $nativeSource = Join-Path $PSScriptRoot 'profile_atomic_logon_environment_probe.c'
    $exe = Join-Path $output 'p2pkit-atomic-logon-environment-probe.exe'
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
 /INCREMENTAL:NO /MANIFEST:EMBED /OPT:REF /OPT:ICF kernel32.lib advapi32.lib netapi32.lib bcrypt.lib
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
    $cases = @(
        @{ arguments = '--unknown'; name = 'invalid'; exit = 2 },
        @{ arguments = '--atomic-logon-standard-child'; name = 'elevated-child'; exit = 3 }
    )
    foreach ($case in $cases) {
        $run = Invoke-PolicyCommand $exe $case.arguments $output $case.name 10000
        $result.negativeControls += @{ name = $case.name; expectedExit = $case.exit; execution = $run }
        if ($run.exitCode -ne $case.exit -or $run.timedOut -or $run.outputExceeded -or
            -not $run.processExitObserved -or -not $run.finalizationCompleted -or $run.elapsedMs -ge 10000) {
            throw 'Negative environment control failed'
        }
        foreach ($stream in @('stdout', 'stderr')) {
            if ((Get-Item -LiteralPath (Join-Path $output ($case.name + '-' + $stream + '.log'))).Length -ne 0) {
                throw 'Unexpected negative output'
            }
        }
    }
    $result.execution = Invoke-PolicyCommand $exe '--disposable-atomic-logon-environment-probe' $output 'probe' 70000
    if ((Get-Item -LiteralPath (Join-Path $output 'probe-stderr.log')).Length -ne 0) {
        throw 'Unexpected atomic-logon stderr'
    }
    $text = [IO.File]::ReadAllText((Join-Path $output 'probe-stdout.log'))
    if ($text.Length -gt 4096 -or $text -cnotmatch '\A[^\r\n]+\r?\n\z') {
        throw 'Expected one bounded environment result'
    }
    $record = $text | ConvertFrom-Json -AsHashtable
    $result.observation = $record
    Assert-AtomicLogonObservation -Record $record -Execution $result.execution
    foreach ($input in $inputs) {
        if ((Get-FileHash -LiteralPath (Join-Path $PSScriptRoot $input) -Algorithm SHA256).Hash -cne
            $hashes[$input]) { throw 'Input changed' }
    }
    if ((Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash -cne $result.executable.sha256 -or
        (Read-PolicyGit -Arguments @('rev-parse', 'HEAD') -ExpectedLines 1) -cne $head) { throw 'Source/EXE changed' }
    $null = Read-PolicyGit -Arguments @('status', '--porcelain') -ExpectedLines 0
    $result.sourceUnchanged = $true
    $result.result = 'PASS'
    Write-Output 'PASS explicit WithLogonW JOB_LIST API experiment; NOT protected-profile/JNI or full supervisor qualification'
} finally {
    try {
        $bytes = [Text.Encoding]::UTF8.GetBytes(($result | ConvertTo-Json -Depth 9) + "`n")
        $receipt.Write($bytes, 0, $bytes.Length)
    } finally { $receipt.Dispose() }
}
