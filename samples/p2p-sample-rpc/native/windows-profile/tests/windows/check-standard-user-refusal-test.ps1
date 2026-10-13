param([Parameter(Mandatory = $true)][string]$OutputDirectory)
# Actual PowerShell parser/negative-scope tests with synthetic records; not a Windows token observation.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (-not [IO.Path]::IsPathFullyQualified($OutputDirectory) -or (Test-Path -LiteralPath $OutputDirectory)) {
    throw 'New absolute test evidence directory required'
}
$null = New-Item -ItemType Directory -Path $OutputDirectory
$script = Join-Path $PSScriptRoot 'check-hosted-standard-user-refusal.ps1'
function Import-OneFunction([string]$File, [string]$Name) {
    $tokens = $null; $errors = $null
    $ast = [Management.Automation.Language.Parser]::ParseFile($File, [ref]$tokens, [ref]$errors)
    if ($errors.Count) { throw 'Source did not parse' }
    $functions = @($ast.FindAll({
        param($node)
        $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -ceq $Name
    }, $true))
    if ($functions.Count -ne 1) { throw 'Expected one exact function' }
    return [scriptblock]::Create($functions[0].Extent.Text)
}
. (Import-OneFunction $script 'Assert-ElevatedStandardUserRefusal')
. (Import-OneFunction (Join-Path $PSScriptRoot 'check-hosted-policy-tests.ps1') 'Invoke-PolicyCommand')
$record = [ordered]@{
    scope = 'EXISTING_STANDARD_USER_ADMISSION_NOT_SMOKE_OR_RELEASE'; launchApi = 'CreateProcessW'
    accountCreated = $false; result = 3; stage = 10; systemCode = 0; created = $false; resumed = $false
    cleanupObserved = $true; nativeStorageExecuted = $false
}
$run = [ordered]@{
    passed = $false; exitCode = 3; timedOut = $false; outputExceeded = $false
    processExitObserved = $true; finalizationCompleted = $true; elapsedMs = 12
}
function Json-Line([object]$Value) { return ($Value | ConvertTo-Json -Depth 5 -Compress) + "`n" }
function Refused([object]$Run, [string]$Text) {
    try { $null = Assert-ElevatedStandardUserRefusal $Run $Text; return $false } catch { return $true }
}
$count = 0
$outcome = 'NOT_COMPLETED'
try {
    $observed = Assert-ElevatedStandardUserRefusal $run (Json-Line $record)
    if ($observed.stage -ne 10) { throw 'Valid synthetic observation rejected' }; $count++
    foreach ($mutation in @(
        @('scope', 'ACCOUNT_ADMISSION_FEASIBILITY_NOT_SMOKE_OR_RELEASE'), @('launchApi', 'CreateProcessAsUserW'),
        @('accountCreated', $true), @('created', $true), @('resumed', $true), @('cleanupObserved', $false),
        @('nativeStorageExecuted', $true), @('result', 0), @('result', 8), @('stage', 1), @('stage', 9),
        @('systemCode', 1314), @('accountCreated', 'false'), @('stage', '10'), @('stage', 10.1)
    )) {
        $copy = [ordered]@{}; foreach ($key in $record.Keys) { $copy[$key] = $record[$key] }
        $copy[$mutation[0]] = $mutation[1]
        if (-not (Refused $run (Json-Line $copy))) { throw "Accepted malformed field: $($mutation[0])" }; $count++
    }
    foreach ($mutation in @(
        @('passed', $true), @('exitCode', 0), @('timedOut', $true), @('outputExceeded', $true),
        @('processExitObserved', $false), @('finalizationCompleted', $false), @('elapsedMs', 10000), @('elapsedMs', -1)
    )) {
        $copy = [ordered]@{}; foreach ($key in $run.Keys) { $copy[$key] = $run[$key] }
        $copy[$mutation[0]] = $mutation[1]
        if (-not (Refused $copy (Json-Line $record))) { throw "Accepted failed process: $($mutation[0])" }; $count++
    }
    foreach ($bad in @('', '{}', "[]`n", (Json-Line $record).TrimEnd(),
        ((Json-Line $record) + (Json-Line $record)), (('x' * 4097) + "`n"))) {
        if (-not (Refused $run $bad)) { throw 'Accepted invalid output shape' }; $count++
    }
    $missing = [ordered]@{}; foreach ($key in $record.Keys) { if ($key -cne 'stage') { $missing[$key] = $record[$key] } }
    if (-not (Refused $run (Json-Line $missing))) { throw 'Accepted missing field' }; $count++
    $missing.extra = $false; $missing.stage = 10
    if (-not (Refused $run (Json-Line $missing))) { throw 'Accepted unexpected field' }; $count++
    # Execute the actual wrapper in a child with explicitly invalid hosted scope, even when tests run on Windows.
    # Only that child's environment changes. No native EXE/account/profile is invoked by this command.
    $message = 'Expected the exact owner-authorized hosted Windows elevated negative-control job'
    $code = '$env:GITHUB_ACTIONS = ''false''; try { & ''' + $script.Replace("'", "''") +
        '''; exit 9 } catch { if ($_.Exception.Message -ceq ''' + $message +
        ''') { [Console]::Error.WriteLine(''EXPECTED_SCOPE_REFUSAL''); exit 1 }; exit 8 }'
    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($code))
    $shell = Join-Path $PSHOME $(if ($IsWindows) { 'pwsh.exe' } else { 'pwsh' })
    $child = Invoke-PolicyCommand $shell "-NoLogo -NoProfile -NonInteractive -EncodedCommand $encoded" `
        $OutputDirectory 'guard' 10000
    if ($child.passed -or $child.exitCode -ne 1 -or $child.timedOut -or $child.outputExceeded -or
        -not $child.processExitObserved -or -not $child.finalizationCompleted) { throw 'Direct scope guard failed' }
    $stdout = [IO.File]::ReadAllText((Join-Path $OutputDirectory 'guard-stdout.log'))
    $stderr = [IO.File]::ReadAllText((Join-Path $OutputDirectory 'guard-stderr.log'))
    if ($stdout -cne '' -or $stderr.TrimEnd() -cne 'EXPECTED_SCOPE_REFUSAL') {
        throw 'Expected direct guard rejection before native/file work'
    }
    $count++; $outcome = 'PASS'
    Write-Output "PASS $count refusal parser/guard controls; NOT Windows native token or runtime evidence"
} finally {
    [ordered]@{
        scope = 'SYNTHETIC_REFUSAL_PARSER_AND_INVALID_HOSTED_SCOPE_NOT_NATIVE_RUNTIME'
        result = $outcome; controls = $count
        wrapperSha256 = (Get-FileHash -LiteralPath $script -Algorithm SHA256).Hash.ToLowerInvariant()
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $OutputDirectory 'refusal-test-results.json') -Encoding utf8
}
