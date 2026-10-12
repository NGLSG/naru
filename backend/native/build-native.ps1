param(
  [string]$LlvmRoot = "",
  [string]$Compiler = "",
  [string]$Output = ""
)
$ErrorActionPreference = 'Stop'
$workspace = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
if (!$LlvmRoot) { $LlvmRoot = Join-Path $workspace '.tools\mlir\toolchain\llvm-install' }
if (!$Output) { $Output = Join-Path $workspace 'target\naru_mlir_backend.dll' }
if (!$Compiler) {
  $nativeCompiler = Get-Command 'clang++.exe' -ErrorAction SilentlyContinue
  if (!$nativeCompiler) { throw 'clang++.exe is required to build the embedded backend' }
  $Compiler = $nativeCompiler.Source
}
if (!(Test-Path -LiteralPath (Join-Path $LlvmRoot 'include\mlir\IR\MLIRContext.h'))) {
  throw 'Install the pinned MLIR SDK first: python tools/mlir/bootstrap.py'
}
$Output = [IO.Path]::GetFullPath($Output)
$buildDir = Join-Path $PSScriptRoot 'build'
New-Item -ItemType Directory -Force $buildDir | Out-Null
New-Item -ItemType Directory -Force ([IO.Path]::GetDirectoryName($Output)) | Out-Null
$lldMetadata = Join-Path $PSScriptRoot 'lld\libraries.json'
if (!(Test-Path -LiteralPath $lldMetadata)) {
  & python (Join-Path $PSScriptRoot 'lld\build.py') --llvm-root $LlvmRoot
  if ($LASTEXITCODE -ne 0) { throw 'Preparing native LLD libraries failed' }
}
$lld = Get-Content -Raw $lldMetadata | ConvertFrom-Json
foreach ($lib in $lld.libraries) { if (!(Test-Path -LiteralPath $lib)) { throw "Missing native LLD library: $lib. Run python backend/native/lld/build.py" } }
if ((Get-Content -Raw (Join-Path $LlvmRoot 'include\llvm\Support\VCSRevision.h')) -notmatch [regex]::Escape($lld.revision)) {
  throw 'MLIR/LLVM and LLD revisions must match'
}
$naruNm = Get-Command 'llvm-nm.exe' -ErrorAction SilentlyContinue
if (!$naruNm) { throw 'llvm-nm.exe is required to prepare the shared native plugin ABI' }
$naruExports = Join-Path $buildDir 'plugins.def'
& python (Join-Path $PSScriptRoot 'export_symbols.py') --llvm-root $LlvmRoot --nm $naruNm.Source --output $naruExports
if ($LASTEXITCODE -ne 0) { throw 'Preparing native plugin exports failed' }
$argsList = [Collections.Generic.List[string]]::new()
foreach ($arg in @('-std=c++17','-O2','-shared','-fuse-ld=lld','-fms-runtime-lib=static','-D_CRT_SECURE_NO_WARNINGS','-DNARU_WITH_LLD=1','-DUNICODE','-D_UNICODE')) { $argsList.Add($arg) }
$argsList.Add('-I"' + (Join-Path $LlvmRoot 'include') + '"')
foreach ($dir in $lld.include_directories) { $argsList.Add('-I"' + $dir + '"') }
$argsList.Add('"' + (Join-Path $PSScriptRoot 'bridge.cpp') + '"')
$argsList.Add('"' + (Join-Path $PSScriptRoot 'exact.cpp') + '"')
$argsList.Add('"' + (Join-Path $PSScriptRoot 'toolchain.cpp') + '"')
$argsList.Add('-Wl,/def:"' + $naruExports + '"')
foreach ($lib in $lld.libraries) { $argsList.Add('"' + $lib + '"') }
foreach ($lib in Get-ChildItem (Join-Path $LlvmRoot 'lib') -Filter '*.lib' | Where-Object { $_.Name -match '^(LLVM|MLIR)' -and $_.Name -ne 'LLVM-C.lib' }) { $argsList.Add('"' + $lib.FullName + '"') }
foreach ($lib in @('psapi.lib','shell32.lib','ole32.lib','uuid.lib','advapi32.lib','ws2_32.lib','ntdll.lib')) { $argsList.Add('-l' + [IO.Path]::GetFileNameWithoutExtension($lib)) }
$argsList.Add('-o')
$argsList.Add('"' + $Output + '"')
$response = Join-Path $buildDir 'native.rsp'
[IO.File]::WriteAllLines($response, ($argsList | ForEach-Object { $_.Replace('\', '/') }), [Text.UTF8Encoding]::new($false))
& $Compiler ('@' + $response)
if ($LASTEXITCODE -ne 0) { throw "Native backend compilation failed with exit code $LASTEXITCODE" }
Write-Host "Native MLIR backend: $Output"

