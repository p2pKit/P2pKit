# Test-only fresh-account launch feasibility, NOT the P2pKit native smoke or a release gate.
# Creates/disables one disposable ordinary account, but does not load its profile or touch P2pKit storage.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (-not $IsWindows -or $env:GITHUB_ACTIONS -cne 'true' -or $env:RUNNER_ARCH -cne 'X64' -or
    $env:GITHUB_REPOSITORY -cne 'p2pKit/P2pKit' -or $env:GITHUB_EVENT_NAME -cne 'workflow_dispatch' -or
    $env:GITHUB_REF -cne 'refs/heads/work/rpc-windows-validation-20261012' -or
    $env:GITHUB_JOB -cne 'rpc-windows' -or $env:RUNNER_ENVIRONMENT -cne 'github-hosted' -or
    $env:ImageOS -cne 'win22') { throw 'Expected the owner-authorized disposable Windows test job' }
if ((git rev-parse HEAD) -cne $env:GITHUB_SHA -or (git status --porcelain)) {
    throw 'Expected clean exact-source checkout'
}
$directory = Join-Path $env:RUNNER_TEMP 'p2pkit-windows-validation'
$destination = Join-Path $directory 'account-admission.json'
$result = [ordered]@{
    scope = 'ACCOUNT_ADMISSION_FEASIBILITY_NOT_SMOKE_OR_RELEASE'
    source = $env:GITHUB_SHA
    tree = (git rev-parse 'HEAD^{tree}').Trim()
    run = $env:GITHUB_RUN_ID
    attempt = $env:GITHUB_RUN_ATTEMPT
    result = 'NOT_COMPLETED'
    nativeStorageExecution = 'NOT_PERFORMED'
    smokeSupervisorQualification = 'NOT_PERFORMED'
}
# Reserve before account work; every path after acquisition has an independent close.
$output = [IO.File]::Open($destination, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
try {
    $receiptPath = Join-Path $directory 'native-build.json'
    if ((Get-Item -LiteralPath $receiptPath).Length -gt 65536) { throw 'Oversized compiler receipt' }
    $receipt = Get-Content -Raw -LiteralPath $receiptPath | ConvertFrom-Json
    if ($receipt.source -cne $result.source -or $receipt.tree -cne $result.tree -or
        $receipt.nativeBuild -cne 'PASS') { throw 'Compiler receipt is not bound to this exact successful build' }
    $rows = @($receipt.files | Where-Object { $_.name -ceq 'p2pkit-account-admission-probe.exe' })
    if ($rows.Count -ne 1 -or $rows[0].sha256 -notmatch '\A[0-9a-fA-F]{64}\z') {
        throw 'Expected one compiler-pinned no-payload probe'
    }
    $probe = Join-Path $directory 'account-probe/p2pkit-account-admission-probe.exe'
    $info = Get-Item -LiteralPath $probe
    if ($info.Length -ne $rows[0].bytes -or $info.Length -gt 32MB -or
        $info.Attributes.HasFlag([IO.FileAttributes]::ReparsePoint) -or
        (Get-FileHash -LiteralPath $probe -Algorithm SHA256).Hash -cne $rows[0].sha256) {
        throw 'Probe differs from compiler-pinned bytes'
    }
    $result.probeSha256 = $rows[0].sha256.ToLowerInvariant()
    $timer = [Diagnostics.Stopwatch]::StartNew()
    foreach ($arguments in @(@(), @('--unrecognized'))) {
        $refusal = @(& $probe @arguments)
        if ($LASTEXITCODE -ne 2 -or $refusal.Count -ne 0) { throw 'Invalid-scope native control failed' }
    }
    $refusal = @(& $probe --standard-account-probe-child)
    if ($LASTEXITCODE -ne 3 -or $refusal.Count -ne 0) { throw 'Elevated-runner rejection control failed' }
    $result.negativeAdmissionControls = 'PASS'
    $lines = @(& $probe --disposable-account-admission-probe)
    $code = $LASTEXITCODE
    $timer.Stop()
    $result.exitCode = $code
    $result.elapsedMs = $timer.ElapsedMilliseconds
    # The trusted probe emits at most one fixed-shape public record. Never relay arbitrary native text.
    if ($lines.Count -ne 1 -or $lines[0].Length -gt 4096) { throw 'Missing or oversized probe observation' }
    $observation = $lines[0] | ConvertFrom-Json
    if ($observation.scope -cne $result.scope -or $observation.launchApi -cne 'CreateProcessAsUserW') {
        throw 'Unexpected probe observation scope or launch API'
    }
    $result.observation = [ordered]@{
        launchApi = $observation.launchApi
        accountCreated = [bool]$observation.accountCreated
        result = [int]$observation.result
        stage = [int]$observation.stage
        systemCode = [uint32]$observation.systemCode
        created = [bool]$observation.created
        resumed = [bool]$observation.resumed
        cleanupObserved = [bool]$observation.cleanupObserved
        nativeStorageExecuted = [bool]$observation.nativeStorageExecuted
    }
    if ($code -ne 0 -or $observation.result -ne 0 -or -not $observation.accountCreated -or
        -not $observation.created -or
        -not $observation.resumed -or -not $observation.cleanupObserved -or $observation.nativeStorageExecuted -or
        $timer.ElapsedMilliseconds -ge 70000) {
        # Fixed numeric diagnostics only; never print credentials, native arbitrary text or account identifiers.
        throw ("Credentialed launch feasibility failed: stage={0}; systemCode={1}; exitCode={2}; cleanup={3}" -f
            $result.observation.stage, $result.observation.systemCode, $code, $result.observation.cleanupObserved)
    }
    if ((Get-FileHash -LiteralPath $probe -Algorithm SHA256).Hash -cne $rows[0].sha256 -or
        (git rev-parse HEAD) -cne $result.source -or (git status --porcelain)) {
        throw 'Probe/source changed during observation'
    }
    $result.result = 'PASS'
} finally {
    try {
        $bytes = [Text.Encoding]::UTF8.GetBytes(($result | ConvertTo-Json -Depth 5) + "`n")
        $output.Write($bytes, 0, $bytes.Length)
    } finally { $output.Dispose() }
}
