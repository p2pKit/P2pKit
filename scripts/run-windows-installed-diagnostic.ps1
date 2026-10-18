# Caller first admits the actual account, startup inputs and installed bytes.
# This fixed observer supplies supervision, never installation/provider authority.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-f]{40}$')][string]$ExpectedSource,
    [Parameter(Mandatory = $true)][string]$PrivateParent,
    [Parameter(Mandatory = $true)][string]$Python
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$status = 'FAIL'
try {
    Add-Type -Path (Join-Path $PSScriptRoot 'windows_installed_observer.cs')
    $observation = [P2pKit.WindowsQualification.InstalledObserver]::RunInstalled(
        $PSScriptRoot, $Python, $PrivateParent, $ExpectedSource)
    $status = $observation.Status
} catch { $status = 'FAIL' }
Write-Output ('WINDOWS_INSTALLED_DIAGNOSTIC_OBSERVER ' + $status)
if ($status -cne 'PASS') { exit 125 }
exit 0
