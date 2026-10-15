# Pure synthetic JSON-shape controls. No hosted guard, JVM, native code, account or profile operation is run.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot 'check-hosted-runtime-readback.ps1'
$tokens = $null; $errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile($source, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw 'Hosted runtime readback source did not parse' }
$functions = @($ast.FindAll({
    param($node)
    $node -is [Management.Automation.Language.FunctionDefinitionAst] -and
        $node.Name -ceq 'Assert-PreviewRuntimeObservation'
}, $true))
if ($functions.Count -ne 1) { throw 'Expected exactly one maintained pure preview parser' }
. ([scriptblock]::Create($functions[0].Extent.Text))
$expectedSource = 'a' * 40
$declaredVersion = '21.0.12.1'
$cases = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)

function New-Observation {
    return @{
        source = $expectedSource
        adapter = @{
            schema = 1; scope = 'JDK21_PREVIEW_MODULE_DIAGNOSTIC_NOT_DLL_OR_PROFILE'
            javaFeature = 21; javaVersion = '21.0.12.1+1-LTS'; module = 'dev.p2pkit.rpc.windows.loader'
            previewEnabled = $true; namedNativeAccess = $true; unnamedNativeAccess = $false
            ffmFromJavaBase = $true; windowsX64Hint = $true; productionAvailable = $false
            nativeLoad = 'NOT_PERFORMED'; profileAccess = 'NOT_PERFORMED'
            javaVendor = 'Synthetic Vendor'; javaRuntimeVersion = '21.0.12.1+1-LTS'; javaVmVersion = '21.0.12.1+1-LTS'
        }
    } | ConvertTo-Json -Depth 4 -Compress | ConvertFrom-Json
}

function Test-Accept([string]$Name, [object]$Record) {
    if (-not $cases.Add($Name)) { throw 'Duplicate preview parser control' }
    $output = @(Assert-PreviewRuntimeObservation $Record $expectedSource $declaredVersion)
    if ($output.Count) { throw 'Pure parser unexpectedly returned authority/output' }
}

function Test-Reject([string]$Name, [object]$Record,
                     [object]$BoundSource = $expectedSource, [object]$Version = $declaredVersion) {
    if (-not $cases.Add($Name)) { throw 'Duplicate preview parser control' }
    $rejected = $false
    try { Assert-PreviewRuntimeObservation $Record $BoundSource $Version } catch { $rejected = $true }
    if (-not $rejected) { throw "Malformed preview observation was admitted: $Name" }
}

Test-Accept 'canonical-parsed-json' (New-Observation)
$record = New-Observation; $record.adapter.schema = [int]1; $record.adapter.javaFeature = [int]21
Test-Accept 'explicit-int-fields' $record
$record = New-Observation; $record.adapter.schema = [long]1; $record.adapter.javaFeature = [long]21
Test-Accept 'explicit-long-fields' $record
foreach ($name in @('javaVendor', 'javaRuntimeVersion', 'javaVmVersion')) {
    $record = New-Observation; $record.adapter.$name = 'x' * 128
    Test-Accept "$name-boundary128" $record
    $record = New-Observation; $record.adapter.$name = 'Quote" and slash\'
    Test-Accept "$name-printable-escaped-json" ($record | ConvertTo-Json -Depth 4 | ConvertFrom-Json)
}

foreach ($name in @('previewEnabled', 'namedNativeAccess', 'unnamedNativeAccess',
                   'ffmFromJavaBase', 'windowsX64Hint', 'productionAvailable')) {
    $invalid = @('true', 'false', 0, 1, $null, @($true))
    for ($i = 0; $i -lt $invalid.Count; $i++) {
        $record = New-Observation; $record.adapter.$name = $invalid[$i]
        Test-Reject "$name-type-$i" $record
    }
    $record = New-Observation; $record.adapter.$name = -not $record.adapter.$name
    Test-Reject "$name-wrong-boolean" $record
}
foreach ($name in @('schema', 'javaFeature')) {
    $correct = if ($name -ceq 'schema') { 1 } else { 21 }
    $invalid = @([string]$correct, [double]$correct, [decimal]$correct, $true, $null, @($correct))
    for ($i = 0; $i -lt $invalid.Count; $i++) {
        $record = New-Observation; $record.adapter.$name = $invalid[$i]
        Test-Reject "$name-type-$i" $record
    }
    $record = New-Observation; $record.adapter.$name = $correct + 1
    Test-Reject "$name-wrong-integer" $record
}
foreach ($name in @('scope', 'module', 'nativeLoad', 'profileAccess')) {
    $invalid = @(21, $null, @('NOT_PERFORMED'), 'wrong')
    for ($i = 0; $i -lt $invalid.Count; $i++) {
        $record = New-Observation; $record.adapter.$name = $invalid[$i]
        Test-Reject "$name-value-$i" $record
    }
}
foreach ($name in @('javaVendor', 'javaRuntimeVersion', 'javaVmVersion')) {
    $invalid = @($null, '', ('x' * 129), "x`0x", "x`nx", [string][char]127, [string][char]128, 21, @('Vendor'))
    for ($i = 0; $i -lt $invalid.Count; $i++) {
        $record = New-Observation; $record.adapter.$name = $invalid[$i]
        Test-Reject "$name-value-$i" $record
    }
}
$invalidVersions = @($null, '', 21, @('21.0.12.1'), '17.0.12.1', '210.0.12.1', '21.0.12.2',
    '21.0.12.1 extra', ("21.0.12.1`n"), ('21.0.12.1+' + ('x' * 119)))
for ($i = 0; $i -lt $invalidVersions.Count; $i++) {
    $record = New-Observation; $record.adapter.javaVersion = $invalidVersions[$i]
    Test-Reject "javaVersion-value-$i" $record
}
$invalidSources = @($null, 21, @($expectedSource), ('b' * 40), $expectedSource.ToUpperInvariant())
for ($i = 0; $i -lt $invalidSources.Count; $i++) {
    $record = New-Observation; $record.source = $invalidSources[$i]
    Test-Reject "source-value-$i" $record
}
Test-Reject 'outer-null' $null
Test-Reject 'outer-array' @((New-Observation))
Test-Reject 'outer-hashtable' @{ source = $expectedSource; adapter = @{} }
$record = New-Observation; $record | Add-Member NoteProperty extra $false
Test-Reject 'outer-extra-key' $record
$record = New-Observation; $record.PSObject.Properties.Remove('source')
Test-Reject 'outer-missing-key' $record
$record = New-Observation; $record.adapter = $null
Test-Reject 'adapter-null' $record
$record = New-Observation; $record.adapter = @($record.adapter)
Test-Reject 'adapter-array' $record
$record = New-Observation; $record.adapter | Add-Member NoteProperty extra $false
Test-Reject 'adapter-extra-key' $record
$record = New-Observation; $record.adapter.PSObject.Properties.Remove('schema')
Test-Reject 'adapter-missing-key' $record
$record = New-Observation; $record.adapter.PSObject.Properties.Remove('module')
$record.adapter | Add-Member NoteProperty Module 'dev.p2pkit.rpc.windows.loader'
Test-Reject 'adapter-key-case' $record
Test-Reject 'expected-source-null' (New-Observation) $null
Test-Reject 'expected-source-array' (New-Observation) @($expectedSource)
Test-Reject 'declared-version-null' (New-Observation) $expectedSource $null
Test-Reject 'declared-version-wrong-major' (New-Observation) $expectedSource '17.0.12.1'
Test-Reject 'declared-version-array' (New-Observation) $expectedSource @($declaredVersion)

# Fixed independent inventory: 9 positives and 129 negative shape/type/boundary controls.
if ($cases.Count -ne 138) { throw 'Preview parser control inventory changed' }
@{ scope = 'SYNTHETIC_PREVIEW_JSON_PARSER_ONLY_NOT_JVM_NATIVE_OR_PROFILE'; result = 'PASS'
   controls = $cases.Count; sourceExecution = 'AST_EXTRACTED_PURE_FUNCTION_ONLY'
   nativeExecution = 'NOT_PERFORMED'; profileAccess = 'NOT_PERFORMED' } | ConvertTo-Json -Compress
