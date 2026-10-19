# Exact JSON acceptance controls only: no subprocess, installed file or profile.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Add-Type -Path (Join-Path $PSScriptRoot '../windows_installed_observer.cs')
$source = '0' * 40
$digest = 'a' * 64
$hashes = [Collections.Generic.Dictionary[string,string]]::new([StringComparer]::Ordinal)
$hashes.Add('fixture.py', $digest)
$scope = 'SUPERVISOR_NATIVE_CONTROL_NOT_INSTALLED'
$template = @'
{"schema":1,"scope":"SUPERVISOR_NATIVE_CONTROL_NOT_INSTALLED","status":"PASS","appSource":"SOURCE","supervisorSource":{"fixture.py":"DIGEST"},"startCounter":1000,"counterFrequency":1000,"deadlineCounter":31000,"watchdogCounter":30000,"completedCounter":2000,"workerOutcome":{"schema":1,"appSource":"SOURCE","outcome":{"stage":"COMMAND","code":"PASS","exitCode":0,"timedOut":false,"cleanupKnown":true,"capturesClosed":true,"cleanupReasons":[],"nativeError":null,"pendingContext":null,"elapsedSeconds":0.1},"admissionMatched":true},"outerCleanupKnown":true,"capturesClosed":true}
'@
$valid = $template.Replace('SOURCE', $source).Replace('DIGEST', $digest)
$valid = $valid.Replace('"appSource":"' + $source + '"', '"appSource":"' + $source + '","operation":"admission"')
$utf8 = [Text.UTF8Encoding]::new($false, $true)
function Accept([string]$Json, [string]$Operation = 'admission') {
    [P2pKit.WindowsQualification.InstalledObserver]::ValidateReceipt(
        $utf8.GetBytes($Json), $source, $scope, 1000L, 1000L, $hashes, $Operation)
}
Accept $valid
Accept (" `n" + $valid + "`r`n")
$mutations = @(
    @('"schema":1', '"schema":true'),
    @('"schema":1', '"schema":1.0'),
    @('"schema":1', '"schema":1e0'),
    @('"schema":1', '"schema":"1"'),
    @('"schema":1', '"schema":1,"schema":1'),
    @('"schema":1', '"schema":1,"extra":null'),
    @('"startCounter":1000', '"startCounter":"1000"'),
    @('"startCounter":1000', '"startCounter":999'),
    @('"counterFrequency":1000', '"counterFrequency":1001'),
    @('"deadlineCounter":31000', '"deadlineCounter":31001'),
    @('"watchdogCounter":30000', '"watchdogCounter":30001'),
    @('"completedCounter":2000', '"completedCounter":999'),
    @('"completedCounter":2000', '"completedCounter":31000'),
    @('"completedCounter":2000', '"completedCounter":2000.0'),
    @('"outerCleanupKnown":true', '"outerCleanupKnown":"true"'),
    @('"outerCleanupKnown":true', '"outerCleanupKnown":false'),
    @('"capturesClosed":true', '"capturesClosed":1'),
    @('"admissionMatched":true', '"admissionMatched":false'),
    @('"exitCode":0', '"exitCode":true'),
    @('"exitCode":0', '"exitCode":1'),
    @('"timedOut":false', '"timedOut":true'),
    @('"cleanupKnown":true', '"cleanupKnown":false'),
    @('"cleanupReasons":[]', '"cleanupReasons":["UNKNOWN"]'),
    @('"nativeError":null,', ''),
    @('"pendingContext":null', '"pendingContext":{}'),
    @('"elapsedSeconds":0.1', '"elapsedSeconds":"0.1"'),
    @('"elapsedSeconds":0.1', '"elapsedSeconds":-1'),
    @('"elapsedSeconds":0.1', '"elapsedSeconds":30'),
    @('"elapsedSeconds":0.1', '"elapsedSeconds":NaN'),
    @('"elapsedSeconds":0.1', '"elapsedSeconds":1e999'),
    @('"stage":"COMMAND"', '"stage":"OTHER"'),
    @('"stage":"COMMAND"', '"stage":"COMMAND","extra":null'),
    @('"status":"PASS"', '"status":"FAIL"'),
    @('"operation":"admission"', '"operation":"profile-create"'),
    @('"operation":"admission"', '"operation":null'),
    @('"operation":"admission",', ''),
    @('"scope":"SUPERVISOR_NATIVE_CONTROL_NOT_INSTALLED"', '"scope":"OTHER"'),
    @($digest, ('b' * 64)),
    @($source, ('1' * 40))
)
$refusals = 0
foreach ($change in $mutations) {
    $bad = $valid.Replace($change[0], $change[1])
    if ($bad -ceq $valid) { throw 'Test did not mutate the receipt' }
    $refused = $false
    try { Accept $bad } catch { $refused = $true }
    if (-not $refused) { throw ('Malformed receipt was accepted: ' + $change[0]) }
    $refusals++
}
foreach ($bad in @('', ((' ' * 16385) + $valid), ($valid + $valid))) {
    $refused = $false
    try { Accept $bad } catch { $refused = $true }
    if (-not $refused) { throw 'Unbounded or repeated receipt accepted' }
    $refusals++
}
foreach ($operation in @('profile-create', 'profile-reopen', 'ui-host-cycle')) {
    $matching = $valid.Replace('"operation":"admission"', '"operation":"' + $operation + '"')
    Accept $matching $operation
    foreach ($bad in @($valid, $matching.Replace('"operation":"' + $operation + '","outcome"',
        '"operation":"admission","outcome"'))) {
        $refused = $false
        try { Accept $bad $operation } catch { $refused = $true }
        if (-not $refused) { throw 'Cross-operation receipt was accepted' }
        $refusals++
    }
}
Write-Output ("OBSERVER_RECEIPT_CONTROLS PASS: 5 valid, $refusals refusals; no native process launched")
