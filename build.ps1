param(
    [string]$VyxSdk = $env:VYX_SDK_ROOT,
    [switch]$Release,
    [string]$MlirRoot = '',
    [switch]$RebuildBackend,
    [ValidateRange(1,64)][int]$Jobs = 4
)
$ErrorActionPreference = 'Stop'
$naruSdkArgs = @()
if ($VyxSdk) { $naruSdkArgs = @('--sdk', $VyxSdk) }
$naruSdkPath = & python (Join-Path $PSScriptRoot 'tools\vyx_sdk.py') @naruSdkArgs
if ($LASTEXITCODE -ne 0) { throw 'Configure a Vyx SDK before building; see docs/building.md' }
$VyxSdk = "$naruSdkPath".Trim()
$naruCompiler = Join-Path $VyxSdk 'bin\vyxc.exe'
if (-not (Test-Path -LiteralPath $naruCompiler)) { throw "Vyx compiler not found: $naruCompiler" }
Push-Location -LiteralPath $PSScriptRoot
try {
    & python (Join-Path $PSScriptRoot 'packages\vyx-logger\prepare.py') --sdk $VyxSdk --jobs $Jobs
    if ($LASTEXITCODE -ne 0) { throw 'Preparing Vyx std/logger failed' }
    $naruBackend = Join-Path $PSScriptRoot 'target\naru_mlir_backend.dll'
    $naruNativeSources = @('backend\native\bridge.cpp', 'backend\native\exact.cpp', 'backend\native\toolchain.cpp', 'backend\native\toolchain.h', 'backend\native\naru_mlir.h', 'backend\native\build-native.ps1', 'backend\native\export_symbols.py')
    $naruBackendStale = $RebuildBackend -or -not (Test-Path -LiteralPath $naruBackend)
    if (-not $naruBackendStale) {
        $naruBackendTime = (Get-Item -LiteralPath $naruBackend).LastWriteTimeUtc
        foreach ($naruNativeSource in $naruNativeSources) {
            if ((Get-Item -LiteralPath $naruNativeSource).LastWriteTimeUtc -gt $naruBackendTime) { $naruBackendStale = $true }
        }
    }
    if ($naruBackendStale) {
        $naruNativeArgs = @{ Output = $naruBackend }
        if ($MlirRoot) { $naruNativeArgs.LlvmRoot = $MlirRoot }
        & (Join-Path $PSScriptRoot 'backend\native\build-native.ps1') @naruNativeArgs
    }
    $naruBuildArgs = @('build', '--target', 'naru', "-j$Jobs")
    if ($Release) { $naruBuildArgs += '-O2' }
    & $naruCompiler @naruBuildArgs
    if ($LASTEXITCODE -ne 0) { throw "Naru build failed ($LASTEXITCODE)" }
    $naruPluginBuildArgs = @{}
    if ($MlirRoot) { $naruPluginBuildArgs.LlvmRoot = $MlirRoot }
    & (Join-Path $PSScriptRoot 'backend\native\plugins\build.ps1') @naruPluginBuildArgs
    & (Join-Path $PSScriptRoot 'runtime\coro\build.ps1')
} finally { Pop-Location }
