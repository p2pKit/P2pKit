# Synthetic PE-field regression controls only, NOT a compiled-image or Windows runtime qualification.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$source = Join-Path $root 'samples/p2p-sample-rpc/native/windows-profile/tests/windows/check-hosted-job-inheritance-environment.ps1'
$tokens = $null; $errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile($source, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw 'Invalid producer source' }
$functions = @($ast.FindAll({ param($node)
    $node -is [Management.Automation.Language.FunctionDefinitionAst] -and
        $node.Name -ceq 'Assert-EnvironmentFixtureImage'
}, $true))
if ($functions.Count -ne 1) { throw 'Missing unique maintained fixture inspector' }
. ([scriptblock]::Create($functions[0].Extent.Text))
$directory = [IO.Path]::Combine([IO.Path]::GetTempPath(), 'p2pkit-gui-fixture-fields-' + [Guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path $directory
try {
    $valid = [byte[]]::new(1024)
    $valid[0] = 0x4d; $valid[1] = 0x5a
    [BitConverter]::GetBytes([int]64).CopyTo($valid, 60)
    [BitConverter]::GetBytes([uint32]0x4550).CopyTo($valid, 64)
    [BitConverter]::GetBytes([uint16]0x8664).CopyTo($valid, 68)
    [BitConverter]::GetBytes([uint16]1).CopyTo($valid, 70)
    [BitConverter]::GetBytes([uint16]240).CopyTo($valid, 84)
    [BitConverter]::GetBytes([uint16]2).CopyTo($valid, 86)
    [BitConverter]::GetBytes([uint16]0x20b).CopyTo($valid, 88)
    [BitConverter]::GetBytes([uint32]0x1000).CopyTo($valid, 104)
    [BitConverter]::GetBytes([uint32]0x2000).CopyTo($valid, 144)
    [BitConverter]::GetBytes([uint16]2).CopyTo($valid, 156)
    $path = Join-Path $directory 'valid.exe'
    [IO.File]::WriteAllBytes($path, $valid)
    $result = Assert-EnvironmentFixtureImage $path
    if ($result.subsystemValue -ne 2 -or $result.machine -cne 'AMD64' -or
        $result.scope -cne 'ENVIRONMENT_TEST_FIXTURE_NOT_APPLICATION_LAUNCHER') { throw 'Wrong positive fields' }
    $cases = @(
        @{ name = 'missing-dos'; offset = 0; bytes = [byte[]]@(0, 0) },
        @{ name = 'bad-offset'; offset = 60; bytes = [BitConverter]::GetBytes([int]-1) },
        @{ name = 'missing-pe'; offset = 64; bytes = [byte[]]@(0, 0, 0, 0) },
        @{ name = 'wrong-architecture'; offset = 68; bytes = [BitConverter]::GetBytes([uint16]0xaa64) },
        @{ name = 'zero-sections'; offset = 70; bytes = [BitConverter]::GetBytes([uint16]0) },
        @{ name = 'oversized-sections'; offset = 70; bytes = [BitConverter]::GetBytes([uint16]33) },
        @{ name = 'truncated-section-table'; offset = 70; bytes = [BitConverter]::GetBytes([uint16]32) },
        @{ name = 'wrong-optional-size'; offset = 84; bytes = [BitConverter]::GetBytes([uint16]70) },
        @{ name = 'dll-not-fixture'; offset = 86; bytes = [BitConverter]::GetBytes([uint16]0x2002) },
        @{ name = 'wrong-optional-magic'; offset = 88; bytes = [BitConverter]::GetBytes([uint16]0x10b) },
        @{ name = 'zero-entry'; offset = 104; bytes = [BitConverter]::GetBytes([uint32]0) },
        @{ name = 'entry-outside-image'; offset = 104; bytes = [BitConverter]::GetBytes([uint32]0x2000) },
        @{ name = 'console-subsystem'; offset = 156; bytes = [BitConverter]::GetBytes([uint16]3) }
    )
    foreach ($case in $cases) {
        $candidate = [byte[]]$valid.Clone()
        $case.bytes.CopyTo($candidate, $case.offset)
        $path = Join-Path $directory ($case.name + '.exe')
        [IO.File]::WriteAllBytes($path, $candidate)
        $rejected = $false
        try { $null = Assert-EnvironmentFixtureImage $path } catch { $rejected = $true }
        if (-not $rejected) { throw ('Accepted malformed fixture: ' + $case.name) }
    }
    Write-Output 'PASS 14 synthetic GUI-fixture PE field controls; NOT Windows runtime or complete PE validation'
} finally {
    Remove-Item -LiteralPath $directory -Recurse -Force
}
