param(
    [string]$VyxSdk = $env:VYX_SDK_ROOT,
    [switch]$Release,
    [string]$MlirRoot = '',
    [switch]$RebuildBackend
)
$ErrorActionPreference = 'Stop'
if (-not $VyxSdk) {
    $VyxSdk = 'E:\Dev\C++\VyxLan-selfhost-yolo\dist\vyx-sdk-windows-x86_64-llvm22'
}
$naruCompiler = Join-Path $VyxSdk 'bin\vyxc.exe'
if (-not (Test-Path -LiteralPath $naruCompiler)) { throw "Vyx compiler not found: $naruCompiler" }
Push-Location -LiteralPath $PSScriptRoot
try {
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
    $naruBuildArgs = @('build', '--target', 'naru', '-j4')
    if ($Release) { $naruBuildArgs += '-O2' }
    & $naruCompiler @naruBuildArgs
    if ($LASTEXITCODE -ne 0) { throw "Naru build failed ($LASTEXITCODE)" }
} finally { Pop-Location }
