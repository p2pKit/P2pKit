# Token-only elevated rejection, not a standard-user session or native profile/runtime qualification.
# No account/profile/credential/privilege mutation and no fallback to the credentialed admission lane.
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
    throw 'Expected the exact owner-authorized hosted Windows elevated negative-control job'
}

function Assert-ElevatedStandardUserRefusal([object]$Run, [string]$Text) {
    if ($Run.passed -or $Run.exitCode -ne 3 -or $Run.timedOut -or $Run.outputExceeded -or
        -not $Run.processExitObserved -or -not $Run.finalizationCompleted -or
        $Run.elapsedMs -lt 0 -or $Run.elapsedMs -ge 10000) { throw 'No exact bounded observed refusal' }
    if ($Text.Length -gt 4096 -or $Text -notmatch '\A[^\r\n]+\r?\n\z') {
        throw 'Expected one bounded complete native refusal record'
    }
    $record = $Text | ConvertFrom-Json -AsHashtable
    $keys = @('scope', 'launchApi', 'accountCreated', 'result', 'stage', 'systemCode',
        'created', 'resumed', 'cleanupObserved', 'nativeStorageExecuted')
    if ($record -isnot [Collections.IDictionary] -or $record.Count -ne $keys.Count) {
        throw 'Unexpected refusal record shape'
    }
    foreach ($key in $keys) { if (-not $record.Contains($key)) { throw 'Missing refusal field' } }
    foreach ($key in @('accountCreated', 'created', 'resumed', 'cleanupObserved', 'nativeStorageExecuted')) {
        if ($record[$key] -isnot [bool]) { throw 'Non-boolean refusal field' }
    }
    foreach ($key in @('result', 'stage', 'systemCode')) {
        if ($record[$key] -isnot [int] -and $record[$key] -isnot [long]) { throw 'Non-integer refusal field' }
    }
    if ($record.scope -cne 'EXISTING_STANDARD_USER_ADMISSION_NOT_SMOKE_OR_RELEASE' -or
        $record.launchApi -cne 'CreateProcessW' -or $record.accountCreated -or $record.created -or
        $record.resumed -or -not $record.cleanupObserved -or $record.nativeStorageExecuted -or
        $record.result -ne 3 -or $record.stage -ne 10 -or $record.systemCode -ne 0) {
        throw 'Native elevated rejection was not positively established'
    }
    return $record
}

# Exact checkout and compiler-source binding precede importing the existing ordinary child helper.
$head = @(git rev-parse HEAD)
if ($LASTEXITCODE -ne 0 -or $head.Count -ne 1 -or $head[0] -cne $env:GITHUB_SHA) { throw 'Wrong source HEAD' }
$tree = @(git rev-parse 'HEAD^{tree}')
if ($LASTEXITCODE -ne 0 -or $tree.Count -ne 1 -or $tree[0] -cnotmatch '\A[0-9a-f]{40}\z') { throw 'No source tree' }
$dirty = @(git status --porcelain)
if ($LASTEXITCODE -ne 0 -or $dirty.Count) { throw 'Expected clean exact-source checkout' }
$directory = Join-Path $env:RUNNER_TEMP 'p2pkit-windows-validation'
$receiptPath = Join-Path $directory 'native-build.json'
$receiptItem = Get-Item -LiteralPath $receiptPath
if ($receiptItem.Length -gt 65536 -or $receiptItem.Attributes.HasFlag([IO.FileAttributes]::ReparsePoint)) {
    throw 'Unexpected compiler receipt'
}
$build = Get-Content -Raw -LiteralPath $receiptPath | ConvertFrom-Json
if ($build.scope -cne 'WINDOWS_NATIVE_BUILD_ONLY_NOT_RUNTIME_OR_RELEASE' -or
    $build.source -cne $head[0] -or $build.tree -cne $tree[0] -or
    $build.run -cne $env:GITHUB_RUN_ID -or $build.attempt -cne $env:GITHUB_RUN_ATTEMPT -or
    $build.nativeBuild -cne 'PASS') { throw 'Compiler receipt is not this exact successful build' }
$rows = @($build.files | Where-Object { $_.name -ceq 'p2pkit-account-admission-probe.exe' })
if ($rows.Count -ne 1 -or $rows[0].sha256 -cnotmatch '\A[0-9a-fA-F]{64}\z') { throw 'No exact probe identity' }
$probe = Join-Path $directory 'account-probe/p2pkit-account-admission-probe.exe'
$item = Get-Item -LiteralPath $probe
if ($item.Length -le 0 -or $item.Length -gt 32MB -or $item.Length -ne $rows[0].bytes -or
    $item.Attributes.HasFlag([IO.FileAttributes]::ReparsePoint) -or
    (Get-FileHash -LiteralPath $probe -Algorithm SHA256).Hash -cne $rows[0].sha256) { throw 'Changed probe bytes' }
$helper = Join-Path $PSScriptRoot 'check-hosted-policy-tests.ps1'
$tokens = $null; $errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile($helper, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw 'Ordinary process-helper source did not parse' }
$functions = @($ast.FindAll({
    param($node)
    $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -ceq 'Invoke-PolicyCommand'
}, $true))
if ($functions.Count -ne 1) { throw 'Expected the one reviewed ordinary child function' }
# Install only that existing function; never execute/bypass the policy script's guarded top-level commands.
. ([scriptblock]::Create($functions[0].Extent.Text))
$output = Join-Path $directory 'standard-user-refusal'
if (Test-Path -LiteralPath $output) { throw 'Refusal output must be new' }
$null = New-Item -ItemType Directory -Path $output
$result = [ordered]@{
    scope = 'HOSTED_ELEVATED_REFUSAL_NOT_STANDARD_USER_OR_PROFILE_RUNTIME'
    source = $head[0]; tree = $tree[0]; run = $env:GITHUB_RUN_ID; attempt = $env:GITHUB_RUN_ATTEMPT
    result = 'NOT_COMPLETED'; nativeStorageExecution = 'NOT_PERFORMED'; accountMutation = 'NOT_PERFORMED'
    standardUserPositiveExecution = 'NOT_PERFORMED'; smokeSupervisorQualification = 'NOT_PERFORMED'
    probeSha256 = $rows[0].sha256.ToLowerInvariant()
    helperSha256 = (Get-FileHash -LiteralPath $helper -Algorithm SHA256).Hash.ToLowerInvariant()
}
$receipt = [IO.File]::Open((Join-Path $output 'elevated-refusal.json'), [IO.FileMode]::CreateNew,
    [IO.FileAccess]::Write, [IO.FileShare]::None)
try {
    $run = Invoke-PolicyCommand $probe '--existing-disposable-standard-user-probe' $output 'probe' 10000
    $result.execution = $run
    if ((Get-Item -LiteralPath (Join-Path $output 'probe-stderr.log')).Length -ne 0) {
        throw 'Unexpected native stderr; not a valid refusal'
    }
    $text = [IO.File]::ReadAllText((Join-Path $output 'probe-stdout.log'))
    $result.observation = Assert-ElevatedStandardUserRefusal $run $text
    $afterHead = @(git rev-parse HEAD)
    if ($LASTEXITCODE -ne 0 -or $afterHead.Count -ne 1 -or $afterHead[0] -cne $head[0]) { throw 'Source changed' }
    $afterStatus = @(git status --porcelain)
    if ($LASTEXITCODE -ne 0 -or $afterStatus.Count -or
        (Get-FileHash -LiteralPath $probe -Algorithm SHA256).Hash -cne $rows[0].sha256) { throw 'Source/bytes changed' }
    $result.result = 'PASS'
    Write-Output 'PASS positively observed elevated refusal; NOT standard-user runtime or native storage'
} finally {
    try {
        $bytes = [Text.Encoding]::UTF8.GetBytes(($result | ConvertTo-Json -Depth 6) + "`n")
        $receipt.Write($bytes, 0, $bytes.Length)
    } finally { $receipt.Dispose() }
}
