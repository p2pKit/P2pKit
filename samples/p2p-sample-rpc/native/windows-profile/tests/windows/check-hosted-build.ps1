# Build-only, exact-source validation on an owner-authorized disposable GitHub runner.
# Does not execute/load the DLL or smoke EXE, touch a user profile, sign or publish.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (-not $IsWindows -or $env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_ARCH -ne 'X64' -or
    $env:GITHUB_REPOSITORY -ne 'p2pKit/P2pKit' -or
    $env:GITHUB_REF -ne 'refs/heads/work/rpc-windows-validation-20261012') {
    throw 'Expected the explicitly authorized Windows validation job'
}
$source = (git rev-parse --show-toplevel).Trim()
if ($LASTEXITCODE -ne 0 -or (git rev-parse HEAD) -ne $env:GITHUB_SHA -or (git status --porcelain)) {
    throw 'Expected clean exact-source checkout'
}
$output = Join-Path $env:RUNNER_TEMP 'p2pkit-windows-validation'
if (Test-Path -LiteralPath $output) { throw 'Validation output must be new' }
$null = New-Item -ItemType Directory -Path $output
$receipt = [ordered]@{
    scope = 'WINDOWS_NATIVE_BUILD_ONLY_NOT_RUNTIME_OR_RELEASE'
    source = $env:GITHUB_SHA
    tree = (git rev-parse 'HEAD^{tree}').Trim()
    run = $env:GITHUB_RUN_ID
    attempt = $env:GITHUB_RUN_ATTEMPT
    os = [Environment]::OSVersion.Version.ToString()
    architecture = [Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString()
    nativeBuild = 'NOT_COMPLETED'
    nativeExecution = 'NOT_PERFORMED'
    signing = 'NOT_PERFORMED'
    files = @()
}
try {
    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
    $installation = & $vswhere -latest -products '*' `
        -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    if ($LASTEXITCODE -ne 0 -or @($installation).Count -ne 1) { throw 'MSVC installation unavailable' }
    $developer = Join-Path $installation 'Common7/Tools/VsDevCmd.bat'
    $native = Join-Path $source 'samples/p2p-sample-rpc/native/windows-profile'
    $dllRecipe = Join-Path $native 'build-windows.cmd'
    $smokeRecipe = Join-Path $PSScriptRoot 'build-windows-test.cmd'
    $dll = Join-Path $output 'dll'
    $smoke = Join-Path $output 'smoke'
    foreach ($path in @($developer, $native, $dllRecipe, $smokeRecipe, $dll, $smoke, $env:JAVA_HOME)) {
        if (-not [IO.Path]::IsPathFullyQualified($path) -or $path -match '[\r\n"%!]' -or
            $path.ToCharArray().Where({ [int]$_ -gt 127 }).Count) { throw 'Unsupported command path' }
    }
    $command = @"
@echo off
call "$developer" -arch=x64 -host_arch=x64
if errorlevel 1 exit /b 2
call "$dllRecipe" "$dll"
if errorlevel 1 exit /b 3
call "$smokeRecipe" "$native" "$smoke"
if errorlevel 1 exit /b 4
dumpbin /headers "$dll\p2pkit-windows-profile.dll" > "$output\dll-headers.txt"
if errorlevel 1 exit /b 5
dumpbin /imports "$dll\p2pkit-windows-profile.dll" > "$output\dll-imports.txt"
if errorlevel 1 exit /b 5
dumpbin /exports "$dll\p2pkit-windows-profile.dll" > "$output\dll-exports.txt"
if errorlevel 1 exit /b 5
exit /b 0
"@
    $commandPath = Join-Path $output 'build.cmd'
    [IO.File]::WriteAllText($commandPath, $command, [Text.Encoding]::ASCII)
    & $env:ComSpec /d /c $commandPath 2>&1 | Tee-Object -FilePath (Join-Path $output 'build.log')
    if ($LASTEXITCODE -ne 0) { throw 'Actual MSVC native build failed; inspect retained compiler log' }
    foreach ($file in @((Join-Path $dll 'p2pkit-windows-profile.dll'),
                       (Join-Path $smoke 'p2pkit-windows-profile-smoke.exe'))) {
        $item = Get-Item -LiteralPath $file
        if ($item.Length -le 0 -or $item.Length -gt 32MB) { throw 'Unexpected native output bound' }
        $receipt.files += @{name = $item.Name; bytes = $item.Length; sha256 = (Get-FileHash $file -Algorithm SHA256).Hash}
    }
    if ((git rev-parse HEAD) -ne $env:GITHUB_SHA -or (git status --porcelain)) {
        throw 'Source changed during native compilation'
    }
    $receipt.nativeBuild = 'PASS'
} finally {
    $receipt | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $output 'native-build.json') -Encoding utf8
}
