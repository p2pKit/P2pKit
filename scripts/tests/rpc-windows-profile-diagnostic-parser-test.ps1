# Parse only fixed numeric diagnostic output; never invoke the guarded Windows test recipe.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$source = Join-Path $root 'samples/p2p-sample-rpc/native/windows-profile/tests/windows/check-hosted-profile-initialization.ps1'
$tokens = $null; $errors = $null
$null = [Management.Automation.Language.Parser]::ParseFile($source, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw 'Parse failure' }
$body = [IO.File]::ReadAllText($source)
$begin = $body.IndexOf('    if ($phaseText.Length -gt 256')
$end = $body.IndexOf('    $text = [IO.File]::ReadAllText', $begin)
if ($begin -lt 0 -or $end -le $begin) { throw 'Missing exact diagnostic parser' }
$parse = [scriptblock]::Create($body.Substring($begin, $end-$begin))
$cases = @(
 @{ text=''; expected=$true },
 @{ text="P2PKIT_HIVE_PHASE 1`nP2PKIT_HIVE_PHASE 2`nP2PKIT_HIVE_PHASE 3`nP2PKIT_HIVE_SNAPSHOT 1 0`n"; expected=$true },
 @{ text="P2PKIT_HIVE_SNAPSHOT 2 259`r`n"; expected=$true },
 @{ text="P2PKIT_HIVE_SNAPSHOT 3 1018`n"; expected=$true },
 @{ text="P2PKIT_HIVE_SNAPSHOT 3 4294967295`n"; expected=$true },
 @{ text="P2PKIT_HIVE_SNAPSHOT 0 0`n"; expected=$false },
 @{ text="P2PKIT_HIVE_SNAPSHOT 4 0`n"; expected=$false },
 @{ text="P2PKIT_HIVE_SNAPSHOT 1 259`n"; expected=$false },
 @{ text="P2PKIT_HIVE_SNAPSHOT 2 0`n"; expected=$false },
 @{ text="P2PKIT_HIVE_SNAPSHOT 3 0`n"; expected=$false },
 @{ text="P2PKIT_HIVE_SNAPSHOT 3 259`n"; expected=$false },
 @{ text="P2PKIT_HIVE_SNAPSHOT 3 4294967296`n"; expected=$false },
 @{ text="P2PKIT_HIVE_SNAPSHOT 1 0`nP2PKIT_HIVE_SNAPSHOT 1 0`n"; expected=$false },
 @{ text="P2PKIT_HIVE_PHASE 1`nP2PKIT_HIVE_PHASE 1`n"; expected=$false },
 @{ text="P2PKIT_HIVE_PHASE 9`n"; expected=$false },
 @{ text="P2PKIT_HIVE_SNAPSHOT 2 name`n"; expected=$false },
 @{ text="P2PKIT_HIVE_SNAPSHOT 1 0"; expected=$false },
 @{ text=('x' * 257); expected=$false }
)
foreach ($case in $cases) {
 $phaseText = $case.text; $result = [ordered]@{}; $accepted = $true
 try { . $parse } catch { $accepted = $false }
 if ($accepted -ne $case.expected) { throw 'Diagnostic parser mismatch' }
}
Write-Output ('PASS ' + $cases.Count + ' local exact-wrapper diagnostic parser controls; NOT Windows runtime')
