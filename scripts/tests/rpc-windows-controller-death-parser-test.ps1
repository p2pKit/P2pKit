# Execute only the reviewed pure parser function; never the Windows account/process fixture recipe.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$path = Join-Path $root 'samples/p2p-sample-rpc/native/windows-profile/tests/windows/check-hosted-job-inheritance-environment.ps1'
$tokens = $null; $errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile($path, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw 'Invalid wrapper source' }
$functions = @($ast.FindAll({ param($node)
    $node -is [Management.Automation.Language.FunctionDefinitionAst] -and
    $node.Name -ceq 'Assert-ControllerDeathObservation'
}, $true))
if ($functions.Count -ne 1) { throw 'Missing unique parser function' }
. ([scriptblock]::Create($functions[0].Extent.Text))
$record = @{
    scope = 'CONTROLLER_DEATH_POST_RETURN_GATE_NOT_INFLIGHT_OR_PROTECTED_SUPERVISION'
    mode = 2; result = 0; stage = 6; systemCode = 0
    accountAcknowledged = $true; accountDisabledObserved = $true; controllerCreated = $true
    controllerAtomicOuterAdmission = $true; auditedGateObserved = $true; brokerHandlePulled = $true
    childHandlePulled = $true; controllerDeathInjected = $true; controllerExitObserved = $true
    brokerExitObserved = $true; childExitObserved = $true; controllerExit = 126; brokerExit = 0; childExit = 0
    outerJobOpenDuringObservation = $true; outerJobEmptyObserved = $true; explicitFailureTermination = $false
    cleanupObserved = $true; knownHandleChecked = 3; knownHandleAbsent = 2; knownHandleReused = 1
    privateJobDuplicated = $false; profileRequested = $false; nativeStorageExecuted = $false
    inFlightCreationQualified = $false; protectedSupervisorQualified = $false
}
$execution = [ordered]@{ exitCode = 0; timedOut = $false; outputExceeded = $false; processExitObserved = $true
    finalizationCompleted = $true; elapsedMs = [long]100; passed = $true }
$cases = [Collections.Generic.List[object]]::new()
$cases.Add(@{ record = $record; execution = $execution; accepted = $true })
$cases.Add(@{ record = ($record | ConvertTo-Json -Compress | ConvertFrom-Json -AsHashtable)
    execution = ($execution | ConvertTo-Json -Compress | ConvertFrom-Json -AsHashtable); accepted = $true })
foreach ($key in @($record.Keys)) {
    $bad = $record.Clone(); $bad.Remove($key)
    $cases.Add(@{ record = $bad; execution = $execution; accepted = $false })
    if ($record[$key] -is [bool]) {
        foreach ($value in @((-not $record[$key]), 0, 1, 'true', @($record[$key]), $null)) {
            $bad = $record.Clone(); $bad[$key] = $value
            $cases.Add(@{ record = $bad; execution = $execution; accepted = $false })
        }
    } elseif ($record[$key] -is [int]) {
        foreach ($value in @(-1, [long]4294967296, $true, $false, [double]0, '0', @($record[$key]), $null)) {
            $bad = $record.Clone(); $bad[$key] = $value
            $cases.Add(@{ record = $bad; execution = $execution; accepted = $false })
        }
    }
}
foreach ($value in @(@($record.scope), @{ value = $record.scope }, 'PROTECTED_SUPERVISION', $null, 1, $true)) {
    $bad = $record.Clone(); $bad.scope = $value
    $cases.Add(@{ record = $bad; execution = $execution; accepted = $false })
}
foreach ($key in @('Count', 'Keys', 'Values', 'Unexpected')) {
    $bad = $record.Clone(); $bad[$key] = $record.Count
    $cases.Add(@{ record = $bad; execution = $execution; accepted = $false })
}
$outcomes = @{ mode = @(0, 1); result = @(5, 8); stage = @(4, 5); systemCode = @(6)
    controllerExit = @(124, 125, 127, 259); brokerExit = @(124, 125, 259, [long]3221226505)
    childExit = @(42, 259); knownHandleChecked = @(2, 4); knownHandleAbsent = @(1, 3); knownHandleReused = @(0, 2) }
foreach ($key in $outcomes.Keys) {
    foreach ($value in $outcomes[$key]) {
        $bad = $record.Clone(); $bad[$key] = $value
        $cases.Add(@{ record = $bad; execution = $execution; accepted = $false })
    }
}
foreach ($key in @($execution.Keys)) {
    $bad = @{}; foreach ($name in $execution.Keys) { if ($name -cne $key) { $bad[$name] = $execution[$name] } }
    $cases.Add(@{ record = $record; execution = $bad; accepted = $false })
    $values = if ($execution[$key] -is [bool]) { @((-not $execution[$key]), 0, 1, 'true', $null) } else {
        @(-1, $true, $false, [double]0, '0', $null)
    }
    foreach ($value in $values) {
        $bad = @{}; foreach ($name in $execution.Keys) { $bad[$name] = $execution[$name] }; $bad[$key] = $value
        $cases.Add(@{ record = $record; execution = $bad; accepted = $false })
    }
}
foreach ($value in @(70000, [long]4294967296)) {
    $bad = @{}; foreach ($name in $execution.Keys) { $bad[$name] = $execution[$name] }; $bad.elapsedMs = $value
    $cases.Add(@{ record = $record; execution = $bad; accepted = $false })
}
foreach ($case in $cases) {
    $accepted = $true
    try { Assert-ControllerDeathObservation -Record $case.record -Execution $case.execution } catch { $accepted = $false }
    if ($accepted -ne $case.accepted) { throw 'Controller-death parser mutation accepted incorrectly' }
}
Write-Output ('PASS ' + $cases.Count + ' local controller-death parser controls; NOT Windows runtime')
