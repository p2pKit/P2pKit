# Existing build-image launcher, fixed module-resolution command only. No installation/profile/native-provider load.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (-not $IsWindows -or $env:GITHUB_ACTIONS -cne 'true' -or
    $env:GITHUB_EVENT_NAME -cne 'workflow_dispatch' -or $env:GITHUB_REPOSITORY -cne 'p2pKit/P2pKit' -or
    $env:GITHUB_REF -cne 'refs/heads/work/rpc-windows-validation-20261012' -or
    $env:GITHUB_JOB -cne 'rpc-windows' -or $env:RUNNER_ENVIRONMENT -cne 'github-hosted' -or
    $env:RUNNER_ARCH -cne 'X64' -or $env:ImageOS -cne 'win22' -or
    [Runtime.InteropServices.RuntimeInformation]::OSArchitecture -ne [Runtime.InteropServices.Architecture]::X64 -or
    [Runtime.InteropServices.RuntimeInformation]::ProcessArchitecture -ne [Runtime.InteropServices.Architecture]::X64) {
    throw 'Expected the owner-authorized existing Windows build-image runtime test job'
}
foreach ($name in @('JAVA_TOOL_OPTIONS', '_JAVA_OPTIONS', 'JDK_JAVA_OPTIONS', 'JPACKAGE_DEBUG')) {
    if (-not [string]::IsNullOrEmpty([Environment]::GetEnvironmentVariable($name))) {
        throw 'Ambient Java or launcher overrides are not admitted for runtime readback'
    }
}
$head = @(git rev-parse HEAD)
if ($LASTEXITCODE -ne 0 -or $head.Count -ne 1 -or $head[0] -cne $env:GITHUB_SHA) { throw 'Wrong source HEAD' }
$tree = @(git rev-parse 'HEAD^{tree}')
if ($LASTEXITCODE -ne 0 -or $tree.Count -ne 1 -or $tree[0] -cnotmatch '\A[0-9a-f]{40}\z') { throw 'Wrong source tree' }
$dirty = @(git status --porcelain)
if ($LASTEXITCODE -ne 0 -or $dirty.Count) { throw 'Expected clean build-image source' }
$evidence = Join-Path $env:RUNNER_TEMP 'p2pkit-windows-validation'
$inspection = Join-Path $evidence 'app-image-inspection.json'
if ((Get-Item -LiteralPath $inspection).Length -gt 65536) { throw 'Oversized image receipt' }
$imageRecord = Get-Content -LiteralPath $inspection -Raw | ConvertFrom-Json
if ($imageRecord.source -cne $head[0] -or $imageRecord.tree -cne $tree[0] -or $imageRecord.result -cne 'PASS' -or
    $imageRecord.scope -cne 'WINDOWS_APP_IMAGE_BYTES_NOT_INSTALLED_OR_RUNTIME_QUALIFIED') {
    throw 'No current successful existing-app byte inspection'
}
if ($imageRecord.applicationJar -cnotmatch '\A[A-Za-z0-9_.-]+\.jar\z') { throw 'Invalid application JAR member' }
$image = Join-Path (Get-Location) 'samples/p2p-sample-desktop-ui/build/compose/binaries/main/app/P2pKit Sample'
# Bind maintained launcher/config, module/JVM entry files and packaged classpath. This is not installed ACL authority.
$members = @('P2pKit Sample.exe', 'app/P2pKit Sample.cfg', 'runtime/release',
    'runtime/lib/modules', 'runtime/bin/server/jvm.dll', 'runtime/bin/jli.dll')
function Observe-RuntimeInputs {
    $result = [ordered]@{}
    # The probe and its source stamp live in sample-rpc, not the main Desktop JAR.
    $jars = @(Get-ChildItem -LiteralPath (Join-Path $image 'app') -Filter '*.jar' -File | Sort-Object Name)
    if ($jars.Count -le 0 -or $jars.Count -gt 512) { throw 'Unexpected packaged classpath size' }
    if ($imageRecord.applicationJar -cnotin @($jars.Name)) { throw 'Maintained application JAR is missing' }
    [long]$total = 0
    foreach ($member in @($members) + @($jars | ForEach-Object { 'app/' + $_.Name })) {
        $file = Get-Item -LiteralPath (Join-Path $image $member)
        if ($file.PSIsContainer -or $file.Length -le 0 -or $file.Length -gt 512MB -or
            $file.Attributes.HasFlag([IO.FileAttributes]::ReparsePoint)) { throw 'Unexpected runtime input' }
        $total += $file.Length
        if ($total -gt 1GB) { throw 'Runtime readback input inventory exceeds its bound' }
        $result[$member] = [ordered]@{bytes = $file.Length
            sha256 = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}
    }
    return $result
}
$before = Observe-RuntimeInputs
if ($before['runtime/release'].bytes -gt 65536) { throw 'Oversized bundled runtime metadata' }
$release = [IO.File]::ReadAllText((Join-Path $image 'runtime/release'))
$versions = [regex]::Matches($release, '(?m)^JAVA_VERSION="([0-9][0-9A-Za-z.+_-]*)"\r?$')
if ($versions.Count -ne 1) { throw 'Missing unique bundled runtime version declaration' }
$declaredVersion = $versions[0].Groups[1].Value
$logs = Join-Path $evidence 'runtime-module-readback'
if (Test-Path -LiteralPath $logs) { throw 'Runtime evidence must be fresh' }
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
$run = Invoke-PolicyCommand (Join-Path $image 'P2pKit Sample.exe') '--rpc-windows-runtime-readback' $logs 'readback' 15000
@{scope = 'BUILD_IMAGE_MODULE_COMMAND_NOT_INSTALLED_APP_SUPERVISION'; execution = $run; source = $head[0]} |
    ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $logs 'command-result.json') -Encoding utf8
if (-not $run.passed) { throw 'Existing launcher module-resolution command failed' }
$stdout = [IO.File]::ReadAllText((Join-Path $logs 'readback-stdout.log'))
$stderr = [IO.File]::ReadAllText((Join-Path $logs 'readback-stderr.log'))
if ($stdout.Length -gt 2048 -or $stdout -cnotmatch '\A\{[^\r\n]+\}\r?\n\z' -or $stderr -cne '') {
    throw 'Unexpected module-resolution output; process exit alone is not success'
}
$observation = $stdout | ConvertFrom-Json
$keys = @($observation.PSObject.Properties.Name | Sort-Object)
$expectedKeys = @('scope', 'source', 'javaFeature', 'javaVersion', 'module', 'options', 'nativeLoad', 'profileAccess' | Sort-Object)
if (($keys -join ',') -cne ($expectedKeys -join ',') -or
    $observation.scope -cne 'WINDOWS_RUNTIME_MODULE_RESOLUTION_ONLY_NOT_PROFILE_OR_RELEASE' -or
    $observation.source -cne $head[0] -or $observation.javaFeature -notin @(17, 21) -or
    $observation.module -cne 'jdk.unsupported' -or
    ($observation.options -join ',') -cne 'NOSHARE_READ,NOSHARE_WRITE,NOSHARE_DELETE' -or
    $observation.nativeLoad -cne 'NOT_PERFORMED' -or $observation.profileAccess -cne 'NOT_PERFORMED' -or
    ($observation.javaVersion -split '\+')[0] -cne ($declaredVersion -split '\+')[0]) {
    throw 'Module-resolution observation does not match the fixed source/runtime contract'
}
$after = Observe-RuntimeInputs
if (($before | ConvertTo-Json -Depth 4 -Compress) -cne ($after | ConvertTo-Json -Depth 4 -Compress)) {
    throw 'Build-image runtime inputs changed during readback'
}
$afterHead = @(git rev-parse HEAD)
if ($LASTEXITCODE -ne 0 -or $afterHead.Count -ne 1 -or $afterHead[0] -cne $head[0]) { throw 'Source changed' }
$afterStatus = @(git status --porcelain)
if ($LASTEXITCODE -ne 0 -or $afterStatus.Count) { throw 'Source changed during runtime readback' }
@{scope = 'EXISTING_BUILD_IMAGE_MODULE_RESOLUTION_NOT_INSTALLED_PROFILE_OR_RELEASE'; result = 'PASS';
    source = $head[0]; tree = $tree[0]; run = $env:GITHUB_RUN_ID; attempt = $env:GITHUB_RUN_ATTEMPT;
    msi = $imageRecord.msi; imageInspectionSha256 =
        (Get-FileHash -LiteralPath $inspection -Algorithm SHA256).Hash.ToLowerInvariant();
    inputs = $before; observation = $observation; execution = $run;
    installedRuntime = 'NOT_PERFORMED'; nativeProvider = 'NOT_PERFORMED'; wholeLifetimeSupervision = 'NOT_PERFORMED'} |
    ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $logs 'runtime-result.json') -Encoding utf8
Write-Output 'Existing build-image launcher resolved jdk.unsupported options. NOT installed-profile or release evidence.'
