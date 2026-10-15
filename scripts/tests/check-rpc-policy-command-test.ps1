param([Parameter(Mandatory = $true)][string]$OutputDirectory)
# Ordinary synthetic child controls, not native profile/Windows storage execution or supervisor qualification.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
if (-not [IO.Path]::IsPathFullyQualified($OutputDirectory)) { throw 'Absolute create-only evidence path required' }
$output = [IO.Path]::GetFullPath($OutputDirectory)
if ($output -ceq $root -or $output.StartsWith($root + [IO.Path]::DirectorySeparatorChar,
        [StringComparison]::OrdinalIgnoreCase) -or (Test-Path -LiteralPath $output)) {
    throw 'Use a new evidence directory outside the checkout'
}
$null = New-Item -ItemType Directory -Path $output
$helper = Join-Path $root 'samples/p2p-sample-rpc/native/windows-profile/tests/windows/check-hosted-policy-tests.ps1'
$tokens = $null
$errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile($helper, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw 'Policy-command source did not parse' }
$functions = @($ast.FindAll({
    param($node)
    $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -ceq 'Invoke-PolicyCommand'
}, $true))
if ($functions.Count -ne 1) { throw 'Expected exactly one reviewed ordinary process function' }
# Install only the parsed function definition. Never execute or bypass the full helper's host guard.
. ([scriptblock]::Create($functions[0].Extent.Text))
$shell = Join-Path $PSHOME $(if ($IsWindows) { 'pwsh.exe' } else { 'pwsh' })
$results = [ordered]@{}
$outcome = 'NOT_COMPLETED'
$gitControlsPassed = $false
function Run-Synthetic([string]$Name, [string]$Code, [int]$Budget = 5000) {
    $directory = Join-Path $output $Name
    $null = New-Item -ItemType Directory -Path $directory
    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($Code))
    $row = Invoke-PolicyCommand $shell "-NoLogo -NoProfile -NonInteractive -EncodedCommand $encoded" `
        $directory 'test' $Budget
    $results[$Name] = $row
    return $row
}
function Require([bool]$Condition, [string]$Control) {
    if (-not $Condition) { throw "Ordinary policy-command control failed: $Control" }
}
try {
    $success = Run-Synthetic 'success' "[Console]::Out.Write(('out-' * 2050)); [Console]::Error.Write(('err-' * 2050))"
    Require ($success.passed -and $success.exitCode -eq 0 -and $success.processExitObserved -and
        $success.finalizationCompleted -and -not $success.timedOut -and -not $success.outputExceeded) 'success outcome'
    Require ([IO.File]::ReadAllText((Join-Path $output 'success/test-stdout.log')) -ceq ('out-' * 2050)) 'stdout chunks'
    Require ([IO.File]::ReadAllText((Join-Path $output 'success/test-stderr.log')) -ceq ('err-' * 2050)) 'stderr chunks'
    $failed = Run-Synthetic 'nonzero' 'exit 7'
    Require (-not $failed.passed -and $failed.exitCode -eq 7 -and $failed.processExitObserved -and
        $failed.finalizationCompleted -and -not $failed.timedOut) 'nonzero exit'
    foreach ($stream in @('Out', 'Error')) {
        $name = 'overflow-' + $stream
        $over = Run-Synthetic $name "[Console]::$stream.Write(('x' * 70000)); Start-Sleep -Seconds 30"
        Require (-not $over.passed -and $over.outputExceeded -and $over.processExitObserved -and
            $over.finalizationCompleted) "bounded $stream outcome"
        foreach ($kind in @('stdout', 'stderr')) {
            Require ((Get-Item -LiteralPath (Join-Path $output "$name/test-$kind.log")).Length -le 65536) 'bounded log'
        }
    }
    $late = Run-Synthetic 'deadline' 'Start-Sleep -Seconds 30' 1000
    Require (-not $late.passed -and $late.timedOut -and $late.processExitObserved -and
        $late.finalizationCompleted) 'deadline exit'
    $missing = Join-Path $output 'missing'
    $null = New-Item -ItemType Directory -Path $missing
    $refusal = Invoke-PolicyCommand (Join-Path $missing 'never-created.exe') '' $missing 'test' 5000
    $results['start-refusal'] = $refusal
    Require (-not $refusal.passed -and -not $refusal.processExitObserved -and
        $refusal.finalizationCompleted) 'no started owner'
    $gitFunctions = @($ast.FindAll({
        param($node)
        $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -ceq 'Read-PolicyGit'
    }, $true))
    Require ($gitFunctions.Count -eq 1) 'one checked Git reader'
    . ([scriptblock]::Create($gitFunctions[0].Extent.Text))
    # Script-scoped fake git only; no repository/process/environment modification.
    function git { $global:LASTEXITCODE = 0 }
    $null = Read-PolicyGit -Arguments @('status', '--porcelain') -ExpectedLines 0
    function git { $global:LASTEXITCODE = 17 }
    $rejected = $false
    try { $null = Read-PolicyGit -Arguments @('status', '--porcelain') -ExpectedLines 0 } catch { $rejected = $true }
    Require $rejected 'failed empty Git status'
    function git { $global:LASTEXITCODE = 0; '?? synthetic-change' }
    $rejected = $false
    try { $null = Read-PolicyGit -Arguments @('status', '--porcelain') -ExpectedLines 0 } catch { $rejected = $true }
    Require $rejected 'dirty Git status'
    Remove-Item Function:git
    $gitControlsPassed = $true
    $outcome = 'PASS'
    Write-Output 'PASS 6 ordinary process and 3 Git controls; NOT Windows profile or supervisor qualification'
} finally {
    [ordered]@{
        scope = 'ORDINARY_POLICY_COMMAND_TESTS_NOT_WINDOWS_PROFILE_OR_SUPERVISOR'
        result = $outcome
        gitControlsPassed = $gitControlsPassed
        helperSha256 = (Get-FileHash -LiteralPath $helper -Algorithm SHA256).Hash.ToLowerInvariant()
        controls = $results
    } | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $output 'command-control-results.json') -Encoding utf8
}
