# Parse the exact source-bound observation only; never invoke the guarded Windows recipe.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$source = Join-Path $root 'samples/p2p-sample-rpc/native/windows-profile/tests/windows/check-hosted-profile-initialization.ps1'
$tokens = $null; $errors = $null
$null = [Management.Automation.Language.Parser]::ParseFile($source, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw 'Parse failure' }
$body = [IO.File]::ReadAllText($source)
$begin = $body.IndexOf('    if ($text.Length -gt 4096')
$end = $body.IndexOf('    foreach ($input in $inputs)', $begin)
if ($begin -lt 0 -or $end -le $begin) { throw 'Missing exact observation parser' }
$parse = [scriptblock]::Create($body.Substring($begin, $end-$begin))
$valid = @{
    scope = 'OS_PROFILE_INITIALIZATION_NOT_PROTECTED_STORAGE_OR_SUPERVISION'
    launchApi = 'CreateProcessWithLogonW'; result = 0; stage = 8; systemCode = 0
    accountCreated = $true; created = $true; assignedBeforeResume = $true; resumed = $true
    profileProbeExit = 0; cleanupObserved = $true; bootstrapAtomicJobAdmission = $false
    profileRequested = $true; nativeStorageExecuted = $false; finalJobActiveProcesses = 0
    jobQueryError = 0; handleCloseError = 0; firstJobActiveProcesses = 0; jobObservations = 1
    hiveObserverMethod = 'EXACT_RELATIVE_SID_LOOKUP_POINT_IN_TIME'
    hiveAbsentBefore = $true; hiveLoadedBeforeResume = $true; hiveAbsentAfterExit = $true
    hiveObserverRetired = $true; hiveBeforeStatus = 3221225524; hiveLoadedStatus = 0
    hiveAfterStatus = 3221225524; hiveParentOpenStatus = 0; hiveLastLookupStatus = 3221225524
    hiveParentCloseStatus = 0; hiveChildCloseStatus = 0; hiveObserverSystemError = 0
    hiveLookups = 3; hivePresences = 1; hiveAbsences = 2; hiveChildCloses = 1
}
$cases = [Collections.Generic.List[object]]::new()
$cases.Add(@{ text = ($valid | ConvertTo-Json -Compress) + "`n"; expected = $true; execution = $true })
$cases.Add(@{ text = ($valid | ConvertTo-Json -Compress) + "`r`n"; expected = $true; execution = $true })
$cases.Add(@{ text = ($valid | ConvertTo-Json -Compress) + "`n"; expected = $false; execution = $false })
foreach ($key in @($valid.Keys)) {
    $missing = $valid.Clone(); $missing.Remove($key)
    $cases.Add(@{ text = ($missing | ConvertTo-Json -Compress) + "`n"; expected = $false; execution = $true })
}
$mutations = @{
    hiveObserverMethod = @('NAMESPACE_SCAN', $null)
    hiveAbsentBefore = @($false, 1); hiveLoadedBeforeResume = @($false, 1)
    hiveAbsentAfterExit = @($false, 1); hiveObserverRetired = @($false, 1)
    hiveBeforeStatus = @(0, 3221225852, $false); hiveLoadedStatus = @(3221225524, $false)
    hiveAfterStatus = @(0, 3221225852, $false); hiveLastLookupStatus = @(0, 3221225852)
    hiveParentOpenStatus = @(5, $false); hiveParentCloseStatus = @(5, $false)
    hiveChildCloseStatus = @(5, $false); hiveObserverSystemError = @(6, $false)
    hiveLookups = @(0, 4, 65537, $true); hivePresences = @(0, 2, $true)
    hiveAbsences = @(0, 1, 3, $true); hiveChildCloses = @(0, 2, $true)
    namespaceEnumerationStatus = @(259); hiveUnloadedAfterExit = @($true)
    profileRequested = @($false); nativeStorageExecuted = @($true); bootstrapAtomicJobAdmission = @($true)
}
foreach ($key in $mutations.Keys) {
    foreach ($value in $mutations[$key]) {
        $bad = $valid.Clone(); $bad[$key] = $value
        $cases.Add(@{ text = ($bad | ConvertTo-Json -Compress) + "`n"; expected = $false; execution = $true })
    }
}
foreach ($key in @('scope', 'launchApi', 'hiveObserverMethod')) {
    foreach ($value in @(@($valid[$key]), @{ value = $valid[$key] }, $null, 1, $true)) {
        $bad = $valid.Clone(); $bad[$key] = $value
        $cases.Add(@{ text = ($bad | ConvertTo-Json -Depth 4 -Compress) + "`n"; expected = $false; execution = $true })
    }
}
foreach ($key in @('Count', 'Keys', 'Values')) {
    $bad = $valid.Clone(); $bad[$key] = $valid.Count
    $cases.Add(@{ text = ($bad | ConvertTo-Json -Compress) + "`n"; expected = $false; execution = $true })
}
foreach ($text in @('', ($valid | ConvertTo-Json -Compress), "{}`n{}`n", ('x' * 4097))) {
    $cases.Add(@{ text = $text; expected = $false; execution = $true })
}
foreach ($case in $cases) {
    $text = $case.text; $result = @{ execution = @{ passed = $case.execution }; scope = $valid.scope }
    $accepted = $true
    try { . $parse } catch { $accepted = $false }
    if ($accepted -ne $case.expected) { throw 'Exact-SID observation parser mismatch' }
}
Write-Output ('PASS ' + $cases.Count + ' local exact-wrapper SID observation controls; NOT Windows runtime')
