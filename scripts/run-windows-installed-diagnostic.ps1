# Caller first admits the actual account, startup inputs and installed bytes.
# This fixed observer supplies supervision, never installation/provider authority.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-f]{40}$')][string]$ExpectedSource,
    [ValidateSet('admission', 'profile-create', 'profile-reopen', 'password-refusal', 'ui-host-cycle', 'native-custody', 'native-restart')][string]$Operation = 'admission',
    [Parameter(Mandatory = $true)][string]$PrivateParent,
    [Parameter(Mandatory = $true)][string]$Python,
    [string]$NativeDirectory,
    [string]$NativeSha256
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$status = 'FAIL'
try {
    Add-Type -Path (Join-Path $PSScriptRoot 'windows_installed_observer.cs')
    if ($Operation -cin @('native-custody', 'native-restart')) {
        $observation = [P2pKit.WindowsQualification.InstalledObserver]::RunNativeSmoke(
            $PSScriptRoot, $Python, $PrivateParent, $ExpectedSource, $Operation, $NativeDirectory, $NativeSha256)
    } else {
        if ($PSBoundParameters.ContainsKey('NativeDirectory') -or $PSBoundParameters.ContainsKey('NativeSha256')) {
            throw 'Native parameters cannot alter an installed operation'
        }
        $observation = [P2pKit.WindowsQualification.InstalledObserver]::RunInstalled(
            $PSScriptRoot, $Python, $PrivateParent, $ExpectedSource, $Operation)
    }
    $status = $observation.Status
} catch { $status = 'FAIL' }
Write-Output ('WINDOWS_INSTALLED_DIAGNOSTIC_OBSERVER ' + $status)
if ($status -cne 'PASS') { exit 125 }
exit 0
