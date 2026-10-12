param([string]$LlvmRoot = '', [string]$OutputDirectory = '')
$ErrorActionPreference = 'Stop'
$naruPluginWorkspace = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
if (!$LlvmRoot) { $LlvmRoot = Join-Path $naruPluginWorkspace '.tools\mlir\toolchain\llvm-install' }
if (!$OutputDirectory) { $OutputDirectory = Join-Path $naruPluginWorkspace 'target' }
$naruPluginImport = Join-Path $naruPluginWorkspace 'target\naru_mlir_backend.lib'
if (!(Test-Path -LiteralPath $naruPluginImport)) { throw 'Build the backend before building plugins' }
New-Item -ItemType Directory -Force $OutputDirectory | Out-Null
$naruPluginHeaders = Join-Path $naruPluginWorkspace 'backend\native\build\plugin-headers'
& python (Join-Path $PSScriptRoot 'prepare_headers.py') --llvm-root $LlvmRoot --output $naruPluginHeaders
if ($LASTEXITCODE -ne 0) { throw 'Preparing native plugin import headers failed' }
foreach ($naruPlugin in @(@('mark', 'mlirGetPassPluginInfo'), @('device', 'mlirGetDialectPluginInfo'))) {
    $naruPluginArguments = @('-std=c++17', '-O2', '-shared', '-fuse-ld=lld', '-fms-runtime-lib=static',
        '-I', $naruPluginHeaders, '-I', (Join-Path $LlvmRoot 'include'), (Join-Path $PSScriptRoot ($naruPlugin[0] + '.cpp')),
        $naruPluginImport, ('-Wl,/export:' + $naruPlugin[1]), '-o',
        (Join-Path $OutputDirectory ('naru_' + $naruPlugin[0] + '_plugin.dll')))
    & clang++ @naruPluginArguments
    if ($LASTEXITCODE -ne 0) { throw ('Plugin compilation failed: ' + $naruPlugin[0]) }
}
