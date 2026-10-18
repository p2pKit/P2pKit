# One fixed harmless case through the SAME external observer; no installed route.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Normal','Nonzero','OutputOverflow','BlockedWorker','BlockedOuter','ObserverOutputOverflow')][string]$Case,
    [Parameter(Mandatory = $true)][string]$PrivateParent,
    [Parameter(Mandatory = $true)][string]$Python
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
try {
    $scripts = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
    Add-Type -Path (Join-Path $scripts 'windows_installed_observer.cs')
    $control = [Enum]::Parse([P2pKit.WindowsQualification.Control], $Case, $false)
    $observed = [P2pKit.WindowsQualification.InstalledObserver]::RunControl($scripts, $Python, $PrivateParent, $control)
    # Private test result; this wrapper never converts a supervisor failure to PASS.
    [ordered]@{schema=1;scope='HARMLESS_OBSERVER_CONTROL_NOT_INSTALLED';case=$Case;
        status=$observed.Status;capsule=$observed.Capsule;observation=$observed.Receipt} | ConvertTo-Json -Depth 8
    if ($observed.Status -cne 'PASS') { exit 125 }
    exit 0
} catch {
    Write-Output 'HARMLESS_OBSERVER_CONTROL_FAILED'
    exit 125
}
