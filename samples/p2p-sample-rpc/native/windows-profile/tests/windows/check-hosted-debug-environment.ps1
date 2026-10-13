# Debugger-to-job transfer experiment. NOT full protected-profile/JNI supervision or acceptance.
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
$source = (Read-PolicyGit -Arguments @('rev-parse', '--show-toplevel') -ExpectedLines 1).Trim()
$head = (Read-PolicyGit -Arguments @('rev-parse', 'HEAD') -ExpectedLines 1).Trim()
$tree = (Read-PolicyGit -Arguments @('rev-parse', 'HEAD^{tree}') -ExpectedLines 1).Trim()
if ($head -cne $env:GITHUB_SHA) { throw 'Wrong exact source' }
$null = Read-PolicyGit -Arguments @('status', '--porcelain') -ExpectedLines 0
$output = Join-Path $env:RUNNER_TEMP 'p2pkit-debug-environment'
if (Test-Path -LiteralPath $output) { throw 'Create-only environment evidence' }
$null = New-Item -ItemType Directory -Path $output
$inputs = @('profile_debug_environment_probe.c', 'profile_account_probe.c',
    'check-hosted-debug-environment.ps1', 'check-hosted-policy-tests.ps1')
$hashes = [ordered]@{}
$blobs = [ordered]@{}
foreach ($input in $inputs) {
    $hashes[$input] = (Get-FileHash -LiteralPath (Join-Path $PSScriptRoot $input) -Algorithm SHA256).Hash
    $blobs[$input] = (Read-PolicyGit -Arguments @('rev-parse',
        "HEAD:samples/p2p-sample-rpc/native/windows-profile/tests/windows/$input") -ExpectedLines 1).Trim()
}
$result = [ordered]@{
    scope = 'DEBUG_BOOTSTRAP_CUSTODY_EXPERIMENT_NOT_PROTECTED_SUPERVISION'
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
    $nativeSource = Join-Path $PSScriptRoot 'profile_debug_environment_probe.c'
    $exe = Join-Path $output 'p2pkit-debug-environment-probe.exe'
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
 /link /MACHINE:X64 /DYNAMICBASE /HIGHENTROPYVA /NXCOMPAT /GUARD:CF ^
 /INCREMENTAL:NO /MANIFEST:EMBED /OPT:REF /OPT:ICF kernel32.lib advapi32.lib netapi32.lib bcrypt.lib
exit /b %ERRORLEVEL%
"@
    [IO.File]::WriteAllText($commandPath, $command, [Text.Encoding]::ASCII)
    $result.compilation = Invoke-PolicyCommand $cmd ('/d /s /c ""' + $commandPath + '""') $output 'compile' 60000
    if (-not $result.compilation.passed) { throw 'Environment probe compilation failed' }
    $binary = Get-Item -LiteralPath $exe
    if ($binary.Length -le 0 -or $binary.Length -gt 32MB -or
        $binary.Attributes.HasFlag([IO.FileAttributes]::ReparsePoint)) { throw 'Unexpected probe bytes' }
    $result.executable = @{ sha256 = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash; bytes = $binary.Length }
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
    $modes = @('normal', 'prejob-death', 'job-death', 'detached-death')
    for ($index = 0; $index -lt $modes.Count; $index++) {
        $mode = $modes[$index]
        $execution = Invoke-PolicyCommand $exe "--disposable-debug-$mode-probe" $output $mode 70000
        $text = [IO.File]::ReadAllText((Join-Path $output "$mode-stdout.log"))
        if ($text.Length -gt 4096 -or $text -notmatch '\A[^\r\n]+\r?\n\z' -or
            (Get-Item -LiteralPath (Join-Path $output "$mode-stderr.log")).Length -ne 0) {
            $result.transferControls += @{ mode = $mode; execution = $execution; result = 'INVALID_OBSERVATION' }
            throw 'Expected one bounded debug-transfer result'
        }
        $record = $text | ConvertFrom-Json -AsHashtable
        $result.transferControls += @{ mode = $mode; execution = $execution; observation = $record }
        $keys = @('scope', 'mode', 'result', 'stage', 'systemCode', 'accountCreated', 'childObserved',
            'brokerTerminationInjected', 'childExitObserved', 'childExit', 'brokerExit', 'cleanupObserved',
            'profileRequested', 'nativeStorageExecuted')
        if ($record.Count -ne $keys.Count) { throw 'Unexpected result shape' }
        foreach ($key in $keys) { if (-not $record.ContainsKey($key)) { throw 'Missing result field' } }
        foreach ($key in @('accountCreated', 'childObserved', 'brokerTerminationInjected', 'childExitObserved',
            'cleanupObserved', 'profileRequested', 'nativeStorageExecuted')) {
            if ($record[$key] -isnot [bool]) { throw 'Expected boolean observation' }
        }
        foreach ($key in @('mode', 'result', 'stage', 'systemCode', 'childExit', 'brokerExit')) {
            if ($record[$key] -isnot [int] -and $record[$key] -isnot [long]) { throw 'Expected integer observation' }
        }
        if (-not $execution.passed -or $record.scope -cne $result.scope -or $record.mode -ne $index -or
            $record.result -ne 0 -or $record.stage -ne 6 -or $record.systemCode -ne 0 -or
            -not $record.accountCreated -or -not $record.childObserved -or -not $record.childExitObserved -or
            -not $record.cleanupObserved -or $record.profileRequested -or $record.nativeStorageExecuted -or
            ($index -eq 0 -and ($record.brokerTerminationInjected -or $record.childExit -ne 42 -or $record.brokerExit -ne 0)) -or
            ($index -ne 0 -and (-not $record.brokerTerminationInjected -or $record.childExit -in @(42, 259) -or $record.brokerExit -ne 125))) {
            throw 'Debugger transfer or automatic-retirement control failed'
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
    Write-Output 'PASS focused debugger transfer and broker-death controls; NOT protected profile/JNI qualification'
} finally {
    try {
        $bytes = [Text.Encoding]::UTF8.GetBytes(($result | ConvertTo-Json -Depth 9) + "`n")
        $receipt.Write($bytes, 0, $bytes.Length)
    } finally { $receipt.Dispose() }
}
