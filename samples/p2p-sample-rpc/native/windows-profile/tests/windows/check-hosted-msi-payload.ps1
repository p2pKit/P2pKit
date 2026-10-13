# Static decompilation of our existing MSI with installed WiX. No MSI installation or native profile execution.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (-not $IsWindows -or $env:GITHUB_ACTIONS -cne 'true' -or
    $env:GITHUB_EVENT_NAME -cne 'workflow_dispatch' -or $env:GITHUB_REPOSITORY -cne 'p2pKit/P2pKit' -or
    $env:GITHUB_REF -cne 'refs/heads/work/rpc-windows-validation-20261012' -or
    $env:GITHUB_JOB -cne 'rpc-windows' -or $env:RUNNER_ENVIRONMENT -cne 'github-hosted' -or
    $env:RUNNER_ARCH -cne 'X64' -or $env:ImageOS -cne 'win22') {
    throw 'Expected the owner-authorized existing Windows package test job'
}
$head = @(git rev-parse HEAD)
if ($LASTEXITCODE -ne 0 -or $head.Count -ne 1 -or $head[0] -cne $env:GITHUB_SHA) { throw 'Wrong source HEAD' }
$tree = @(git rev-parse 'HEAD^{tree}')
if ($LASTEXITCODE -ne 0 -or $tree.Count -ne 1 -or $tree[0] -cnotmatch '\A[0-9a-f]{40}\z') {
    throw 'Cannot bind package tree'
}
$dirty = @(git status --porcelain)
if ($LASTEXITCODE -ne 0 -or $dirty.Count) { throw 'Expected clean package source' }
$evidence = Join-Path $env:RUNNER_TEMP 'p2pkit-windows-validation'
$inspection = Join-Path $evidence 'app-image-inspection.json'
if ((Get-Item -LiteralPath $inspection).Length -gt 65536) { throw 'Oversized image receipt' }
$imageRecord = Get-Content -LiteralPath $inspection -Raw | ConvertFrom-Json
if ($imageRecord.source -cne $env:GITHUB_SHA -or $imageRecord.tree -cne $tree[0] -or
    $imageRecord.result -cne 'PASS' -or
    $imageRecord.scope -cne 'WINDOWS_APP_IMAGE_BYTES_NOT_INSTALLED_OR_RUNTIME_QUALIFIED') {
    throw 'No current successful existing-app byte inspection'
}
$base = Join-Path (Get-Location) 'samples/p2p-sample-desktop-ui/build/compose/binaries/main'
$msis = @(Get-ChildItem -LiteralPath (Join-Path $base 'msi') -Filter '*.msi' -File)
if ($msis.Count -ne 1 -or $msis[0].Name -cne $imageRecord.msi.file -or
    $msis[0].Length -ne $imageRecord.msi.bytes -or
    (Get-FileHash -LiteralPath $msis[0].FullName -Algorithm SHA256).Hash.ToLowerInvariant() -cne
        $imageRecord.msi.sha256) { throw 'MSI no longer matches the image inspection' }
if (-not $env:WIX) { throw 'Installed WiX toolchain location is unavailable; no tool download attempted' }
$dark = Join-Path $env:WIX 'bin/dark.exe'
$tool = Get-Item -LiteralPath $dark
if ($tool.PSIsContainer -or $tool.Length -le 0 -or $tool.Length -gt 32MB -or
    $tool.Attributes.HasFlag([IO.FileAttributes]::ReparsePoint)) {
    throw 'Unexpected installed WiX decompiler'
}
$toolHash = (Get-FileHash -LiteralPath $dark -Algorithm SHA256).Hash.ToLowerInvariant()
# Full extraction remains outside the evidence upload tree. It contains application/runtime bytes, not user data.
$work = Join-Path $env:RUNNER_TEMP 'p2pkit-windows-msi-static-extraction'
if (Test-Path -LiteralPath $work) { throw 'Static extraction output must be fresh' }
$null = New-Item -ItemType Directory -Path $work
$extracted = Join-Path $work 'payload'
$wxs = Join-Path $work 'product.wxs'
$logs = Join-Path $evidence 'msi-static-tool'
$null = New-Item -ItemType Directory -Path $logs
$helper = Join-Path $PSScriptRoot 'check-hosted-policy-tests.ps1'
$tokens = $null; $errors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile($helper, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw 'Process helper did not parse' }
$functions = @($ast.FindAll({
    param($node)
    $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -ceq 'Invoke-PolicyCommand'
}, $true))
if ($functions.Count -ne 1) { throw 'Missing reviewed ordinary bounded tool invocation helper' }
. ([scriptblock]::Create($functions[0].Extent.Text))
foreach ($path in @($dark, $msis[0].FullName, $extracted, $wxs)) {
    if (-not [IO.Path]::IsPathFullyQualified($path) -or $path -match '["\r\n]') {
        throw 'Unsupported static decompiler argument'
    }
}
$arguments = '-nologo -x "{0}" "{1}" "{2}"' -f $extracted, $msis[0].FullName, $wxs
$temporary = Join-Path $work 'temp'
$null = New-Item -ItemType Directory -Path $temporary
$previousTemporary = $env:WIX_TEMP
try {
    $env:WIX_TEMP = $temporary
    $result = Invoke-PolicyCommand $dark $arguments $logs 'dark' 60000
} finally {
    $env:WIX_TEMP = $previousTemporary
}
$unchangedTool = (Get-FileHash -LiteralPath $dark -Algorithm SHA256).Hash.ToLowerInvariant() -ceq $toolHash
@{scope = 'STATIC_MSI_DECOMPILER_NOT_INSTALLATION'; source = $env:GITHUB_SHA; execution = $result;
    toolSha256 = $toolHash; toolBytes = $tool.Length; toolVersion = $tool.VersionInfo.FileVersion;
    toolUnchanged = $unchangedTool} |
    ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $logs 'tool-result.json') -Encoding utf8
if (-not $unchangedTool) { throw 'Installed static decompiler changed during use' }
if (-not $result.passed) { throw 'Static WiX decompilation failed; no installation was attempted' }
# Retain bounded package metadata before verification, including on a fail-closed verifier result.
# It contains this builder's product/file inventory, not installed profile or user data.
$xml = Get-Item -LiteralPath $wxs
if ($xml.PSIsContainer -or $xml.Length -le 0 -or $xml.Length -gt 8MB -or
    $xml.Attributes.HasFlag([IO.FileAttributes]::ReparsePoint)) { throw 'Unexpected decompiled MSI inventory' }
$xmlHash = (Get-FileHash -LiteralPath $wxs -Algorithm SHA256).Hash.ToLowerInvariant()
$xmlCopy = Join-Path $logs 'decompiled-product.wxs'
[IO.File]::Copy($wxs, $xmlCopy, $false)
if ((Get-Item -LiteralPath $xmlCopy).Length -ne $xml.Length -or
    (Get-FileHash -LiteralPath $xmlCopy -Algorithm SHA256).Hash.ToLowerInvariant() -cne $xmlHash) {
    throw 'Decompiler inventory evidence copy differs'
}
python -I -B ./scripts/verify-rpc-windows-msi-payload.py --wxs $wxs --extracted $extracted `
    --image (Join-Path $base 'app/P2pKit Sample') --inspection $inspection --msi $msis[0].FullName `
    --output (Join-Path $evidence 'msi-payload-inspection.json')
if ($LASTEXITCODE -ne 0) { throw 'Static MSI component verification failed' }
$payloadReceipt = Join-Path $evidence 'msi-payload-inspection.json'
if ((Get-Item -LiteralPath $payloadReceipt).Length -gt 65536) { throw 'Oversized static MSI receipt' }
$payload = Get-Content -LiteralPath $payloadReceipt -Raw | ConvertFrom-Json
$aliases = @('msi-library.bytes', 'msi-manifest.bytes', 'msi-parent-pin.jar.bytes')
$adapterProperty = $imageRecord.PSObject.Properties['adapter']
if ($null -ne $adapterProperty) {
    $adapter = $adapterProperty.Value
    if ($null -eq $adapter -or $adapter.scope -cne 'STATIC_JDK21_PREVIEW_MODULE_NOT_LOAD_AUTHORITY' -or
        $adapter.file -cne 'app/resources/rpc-loader-jdk21/p2pkit-windows-loader-jdk21.jar' -or
        $adapter.module -cne 'dev.p2pkit.rpc.windows.loader' -or
        $adapter.probeMajor -ne 65 -or $adapter.probeMinor -ne 65535 -or
        $adapter.jarBytes -le 0 -or $adapter.jarBytes -gt 16MB -or
        $adapter.jarSha256 -cnotmatch '\A[0-9a-f]{64}\z') { throw 'Unexpected optional adapter observation' }
    $aliases += 'msi-loader-adapter.jar.bytes'
}
if ($payload.scope -cne 'MSI_STATIC_COMPONENT_EQUALITY_NOT_INSTALLED_RUNTIME' -or
    $payload.result -cne 'PASS' -or $payload.source -cne $env:GITHUB_SHA -or $payload.tree -cne $tree[0] -or
    $payload.comparedFiles.Count -ne $aliases.Count) {
    throw 'Unexpected static MSI result'
}
if ($null -ne $adapterProperty) {
    $observed = $payload.comparedFiles[3]
    if ($observed.target -cne $adapter.file -or $observed.bytes -ne $adapter.jarBytes -or
        $observed.sha256 -cne $adapter.jarSha256) { throw 'MSI adapter observation differs from image receipt' }
}
for ($index = 0; $index -lt $aliases.Count; $index++) {
    $member = $payload.comparedFiles[$index]
    if ($member.extractedMember -cnotmatch '\AFile/[A-Za-z_][A-Za-z0-9_.]{0,71}\z') {
        throw 'Invalid extracted evidence member'
    }
    $original = Join-Path $extracted $member.extractedMember
    $copy = Join-Path $logs $aliases[$index]
    [IO.File]::Copy($original, $copy, $false)
    if ((Get-Item -LiteralPath $copy).Length -ne $member.bytes -or
        (Get-FileHash -LiteralPath $copy -Algorithm SHA256).Hash.ToLowerInvariant() -cne $member.sha256) {
        throw 'Static payload evidence copy differs'
    }
}
$afterHead = @(git rev-parse HEAD)
if ($LASTEXITCODE -ne 0 -or $afterHead.Count -ne 1 -or $afterHead[0] -cne $head[0]) { throw 'Source changed' }
$afterStatus = @(git status --porcelain)
if ($LASTEXITCODE -ne 0 -or $afterStatus.Count) { throw 'Source changed during static MSI inspection' }
Write-Output 'Static MSI component bytes match app image. NOT installed runtime, signing or release qualification.'
