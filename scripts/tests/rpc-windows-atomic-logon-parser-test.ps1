# Pure parser controls only: import its unique AST function, never the guarded Windows fixture recipe.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$path = Join-Path $root 'samples/p2p-sample-rpc/native/windows-profile/tests/windows/check-hosted-atomic-logon-environment.ps1'
$tokens = $null; $errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile($path, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw 'Invalid wrapper source' }
$functions = @($ast.FindAll({ param($node)
    $node -is [Management.Automation.Language.FunctionDefinitionAst] -and
    $node.Name -ceq 'Assert-AtomicLogonObservation'
}, $true))
if ($functions.Count -ne 1) { throw 'Missing unique parser function' }
. ([scriptblock]::Create($functions[0].Extent.Text))
$record = @{
    scope = 'ATOMIC_LOGON_JOB_LIST_API_PROBE_NOT_PROTECTED_SUPERVISION'; launchApi = 'CreateProcessWithLogonW'
    result = 0; stage = 10; systemCode = 0; childExit = 42; finalJobActiveProcesses = 0; jobObservations = 1
    accountCreated = $true; accountEnabled = $true; accountDisabledObserved = $true; creationAttempted = $true
    startupInfoExRequested = $true; jobListRequested = $true; created = $true; memberBeforeResume = $true
    tokenMatched = $true; resumed = $true; childExecuted = $true; childExitObserved = $true
    jobEmptyObserved = $true; cleanupObserved = $true; explicitFailureCleanup = $false
    profileRequested = $false; nativeStorageExecuted = $false
    inFlightCreationQualified = $false; protectedSupervisorQualified = $false
}
$execution = [ordered]@{ exitCode = 0; timedOut = $false; outputExceeded = $false; processExitObserved = $true
    finalizationCompleted = $true; elapsedMs = [long]100; passed = $true }
$cases = [Collections.Generic.List[object]]::new()
$cases.Add(@{ record = $record; execution = $execution; accepted = $true })
$cases.Add(@{ record = ($record | ConvertTo-Json -Compress | ConvertFrom-Json -AsHashtable)
    execution = ($execution | ConvertTo-Json -Compress | ConvertFrom-Json -AsHashtable); accepted = $true })
$arrayRecordFields = [Collections.Generic.List[string]]::new()
$arrayExecutionFields = [Collections.Generic.List[string]]::new()
foreach ($key in @($record.Keys)) {
    $bad = $record.Clone(); $bad.Remove($key)
    $cases.Add(@{ record = $bad; execution = $execution; accepted = $false })
    # Add each candidate directly: PowerShell pipeline enumeration must not flatten array mutations.
    $values = [Collections.Generic.List[object]]::new()
    $values.Add($null); $values.Add(@($record[$key]))
    if ($record[$key] -is [bool]) {
        foreach ($value in @((-not $record[$key]), 0, 1, 'true')) { $values.Add($value) }
    } elseif ($record[$key] -is [int]) {
        foreach ($value in @(-1, [long]4294967296, $true, $false, [double]0, '0')) { $values.Add($value) }
    } else {
        foreach ($value in @(@{ value = $record[$key] }, 'PROTECTED_SUPERVISION', 1, $true)) { $values.Add($value) }
    }
    foreach ($value in $values) {
        $bad = $record.Clone(); $bad[$key] = $value
        if ($bad[$key] -is [array]) { $arrayRecordFields.Add($key) }
        $cases.Add(@{ record = $bad; execution = $execution; accepted = $false })
    }
}
foreach ($key in @('Count', 'Keys', 'Values', 'Unexpected')) {
    $bad = $record.Clone(); $bad[$key] = $record.Count
    $cases.Add(@{ record = $bad; execution = $execution; accepted = $false })
    $badExecution = @{}; foreach ($name in $execution.Keys) { $badExecution[$name] = $execution[$name] }
    $badExecution[$key] = $execution.Count
    $cases.Add(@{ record = $record; execution = $badExecution; accepted = $false })
}
$outcomes = @{ result = @(5, 8); stage = @(6, 9); systemCode = @(87, 1314)
    childExit = @(0, 125, 259); finalJobActiveProcesses = @(1, 2); jobObservations = @(0, 65537) }
foreach ($key in $outcomes.Keys) {
    foreach ($value in $outcomes[$key]) {
        $bad = $record.Clone(); $bad[$key] = $value
        $cases.Add(@{ record = $bad; execution = $execution; accepted = $false })
    }
}
foreach ($key in @($execution.Keys)) {
    $bad = @{}; foreach ($name in $execution.Keys) { if ($name -cne $key) { $bad[$name] = $execution[$name] } }
    $cases.Add(@{ record = $record; execution = $bad; accepted = $false })
    $values = [Collections.Generic.List[object]]::new()
    $values.Add($null); $values.Add(@($execution[$key]))
    if ($execution[$key] -is [bool]) {
        foreach ($value in @((-not $execution[$key]), 0, 1, 'true')) { $values.Add($value) }
    } else {
        foreach ($value in @(-1, $true, $false, [double]0, '0')) { $values.Add($value) }
    }
    foreach ($value in $values) {
        $bad = @{}; foreach ($name in $execution.Keys) { $bad[$name] = $execution[$name] }; $bad[$key] = $value
        if ($bad[$key] -is [array]) { $arrayExecutionFields.Add($key) }
        $cases.Add(@{ record = $record; execution = $bad; accepted = $false })
    }
}
foreach ($value in @(70000, [long]4294967296)) {
    $bad = @{}; foreach ($name in $execution.Keys) { $bad[$name] = $execution[$name] }; $bad.elapsedMs = $value
    $cases.Add(@{ record = $record; execution = $bad; accepted = $false })
}
if ($arrayRecordFields.Count -ne 27 -or @($arrayRecordFields | Sort-Object -Unique).Count -ne 27 -or
    $arrayExecutionFields.Count -ne 7 -or @($arrayExecutionFields | Sort-Object -Unique).Count -ne 7) {
    throw 'Array-valued mutation coverage collapsed or omitted fields'
}
foreach ($case in $cases) {
    $accepted = $true
    try { Assert-AtomicLogonObservation -Record $case.record -Execution $case.execution } catch { $accepted = $false }
    if ($accepted -ne $case.accepted) { throw 'Atomic-logon parser mutation accepted incorrectly' }
}
Write-Output ('PASS ' + $cases.Count + ' local atomic-logon parser controls; NOT Windows runtime')
