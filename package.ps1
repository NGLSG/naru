param([string]$Output = '', [string]$VyxSdk = $env:VYX_SDK_ROOT, [switch]$NoZip,
      [string]$Version = '0.2.0-preview.1')
$ErrorActionPreference = 'Stop'
if (!$Output) { $Output = Join-Path $PSScriptRoot 'target\dist\naru-windows-x86_64' }
if ($Version -notmatch '^\d+\.\d+\.\d+(-[a-zA-Z0-9.-]+)?$') { throw 'Invalid release version' }
$naruSdkArgs = @()
if ($VyxSdk) { $naruSdkArgs = @('--sdk', $VyxSdk) }
$naruSdkPath = & python (Join-Path $PSScriptRoot 'tools\vyx_sdk.py') @naruSdkArgs
if ($LASTEXITCODE -ne 0) { throw 'Configure a Vyx SDK before packaging; see docs/building.md' }
$VyxSdk = "$naruSdkPath".Trim()
$naruPackageRoot = [IO.Path]::GetFullPath($Output)
$naruPackageMarker = Join-Path $naruPackageRoot 'naru-distribution.json'
if ($naruPackageRoot -eq [IO.Path]::GetFullPath($PSScriptRoot) -or
    [IO.Path]::GetFullPath($PSScriptRoot).StartsWith($naruPackageRoot.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Distribution output must not contain the source workspace'
}
if ((Test-Path -LiteralPath $naruPackageRoot) -and
    (Get-ChildItem -LiteralPath $naruPackageRoot -Force | Select-Object -First 1) -and
    !(Test-Path -LiteralPath $naruPackageMarker)) {
    throw 'Nonempty output is not a Naru distribution directory'
}
foreach ($naruArtifact in @('naru.exe', 'naru_mlir_backend.dll', 'naru_coro_plugin.dll', 'naru_tasks.lib')) {
    if (!(Test-Path -LiteralPath (Join-Path $PSScriptRoot ('target\' + $naruArtifact)))) {
        throw 'Build Naru first: .\build.ps1 -Release'
    }
}
New-Item -ItemType Directory -Force $naruPackageRoot | Out-Null
# Retire files emitted by older versions of this managed distribution. Copying
# the current tree alone would keep the removed substitute standard headers.
foreach ($naruObsoleteFile in @('examples\c11\main.nru',
    'dialects\c11\include\stdio.h', 'dialects\c11\include\stdlib.h',
    'dialects\c11\include\string.h', 'dialects\c11\include\math.h',
    'dialects\c11\include\limits.h', 'dialects\c11\include\stdbool.h',
    'dialects\c11\include\stdalign.h')) {
    $naruObsoletePath = [IO.Path]::GetFullPath((Join-Path $naruPackageRoot $naruObsoleteFile))
    if (!$naruObsoletePath.StartsWith($naruPackageRoot.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Obsolete distribution file escaped the package directory'
    }
    if (Test-Path -LiteralPath $naruObsoletePath -PathType Leaf) { Remove-Item -LiteralPath $naruObsoletePath -Force }
}
foreach ($naruArtifact in @('naru.exe', 'naru_mlir_backend.dll')) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot ('target\' + $naruArtifact)) -Destination $naruPackageRoot -Force
}
function Copy-NaruProjectData([string]$Source, [string]$Destination) {
    New-Item -ItemType Directory -Force $Destination | Out-Null
    foreach ($naruDataItem in (Get-ChildItem -LiteralPath $Source)) {
        if ($naruDataItem.PSIsContainer) {
            if ($naruDataItem.Name -in @('target', '.cache', '__pycache__', '.git')) { continue }
            Copy-NaruProjectData -Source $naruDataItem.FullName -Destination (Join-Path $Destination $naruDataItem.Name)
        } else {
            Copy-Item -LiteralPath $naruDataItem.FullName -Destination $Destination -Force
        }
    }
}
foreach ($naruDataDirectory in @('dialects', 'examples')) {
    $naruDataDestination = Join-Path $naruPackageRoot $naruDataDirectory
    New-Item -ItemType Directory -Force $naruDataDestination | Out-Null
    Copy-NaruProjectData -Source (Join-Path $PSScriptRoot $naruDataDirectory) -Destination $naruDataDestination
}
Copy-NaruProjectData -Source (Join-Path $PSScriptRoot 'docs') -Destination (Join-Path $naruPackageRoot 'docs')
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'tests\c11\support-plan.json') -Destination (Join-Path $naruPackageRoot 'docs\c11-support-plan.json') -Force
foreach ($naruDataFile in @('Naru.toml', 'Naru.lock', 'LICENSE', 'LICENSE-MIT', 'LICENSE-APACHE', 'NOTICE', 'THIRD_PARTY.md')) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $naruDataFile) -Destination $naruPackageRoot -Force
}
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'tools\release\DISTRIBUTION.md') -Destination (Join-Path $naruPackageRoot 'README.md') -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'naru.ps1') -Destination $naruPackageRoot -Force
foreach ($naruPackageData in @('tools\pkg', 'registry', 'templates\dialect')) {
    Copy-NaruProjectData -Source (Join-Path $PSScriptRoot $naruPackageData) -Destination (Join-Path $naruPackageRoot $naruPackageData)
}
$naruProfiles = Join-Path $naruPackageRoot 'backend'
$naruResourceHeaders = Join-Path $PSScriptRoot 'target\runtime\clang'
if (Test-Path -LiteralPath $naruResourceHeaders) {
    Copy-NaruProjectData -Source $naruResourceHeaders -Destination (Join-Path $naruPackageRoot 'runtime\clang')
}
New-Item -ItemType Directory -Force $naruProfiles | Out-Null
Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot 'backend') -Filter '*-target.json' | Copy-Item -Destination $naruProfiles -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'backend\examples') -Destination $naruProfiles -Recurse -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'backend\README.md') -Destination $naruProfiles -Force
$naruPluginDestination = Join-Path $naruPackageRoot 'plugins'
New-Item -ItemType Directory -Force $naruPluginDestination | Out-Null
foreach ($naruPluginArtifact in @('naru_mark_plugin.dll', 'naru_device_plugin.dll', 'naru_coro_plugin.dll')) {
    $naruPluginSource = Join-Path $PSScriptRoot ('target\' + $naruPluginArtifact)
    if (Test-Path -LiteralPath $naruPluginSource) { Copy-Item -LiteralPath $naruPluginSource -Destination $naruPluginDestination -Force }
}
$naruCoroManifest = Join-Path $naruPackageRoot 'examples\coro\Naru.toml'
if (Test-Path -LiteralPath $naruCoroManifest) {
    if (!(Test-Path -LiteralPath (Join-Path $naruPluginDestination 'naru_coro_plugin.dll'))) {
        throw 'Build the coroutine target plugin before packaging: backend/native/plugins/build.ps1'
    }
    $naruCoroProjectText = [IO.File]::ReadAllText($naruCoroManifest).Replace('../../target/naru_coro_plugin.dll', '../../plugins/naru_coro_plugin.dll')
    [IO.File]::WriteAllText($naruCoroManifest, $naruCoroProjectText, [Text.UTF8Encoding]::new($false))
    & (Join-Path $naruPackageRoot 'naru.exe') resolve --project $naruCoroManifest | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Resolving relocated coroutine example failed' }
}
$naruRuntimeDestination = Join-Path $naruPackageRoot 'runtime'
New-Item -ItemType Directory -Force $naruRuntimeDestination | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'target\naru_tasks.lib') -Destination $naruRuntimeDestination -Force
Copy-NaruProjectData -Source (Join-Path $PSScriptRoot 'runtime\coro') -Destination (Join-Path $naruRuntimeDestination 'coro')
$naruAsyncManifest = Join-Path $naruPackageRoot 'examples\async\Naru.toml'
if (Test-Path -LiteralPath $naruAsyncManifest) {
    $naruAsyncProjectText = [IO.File]::ReadAllText($naruAsyncManifest).Replace('../../target/naru_coro_plugin.dll', '../../plugins/naru_coro_plugin.dll').Replace('../../target/naru_tasks.lib', '../../runtime/naru_tasks.lib')
    [IO.File]::WriteAllText($naruAsyncManifest, $naruAsyncProjectText, [Text.UTF8Encoding]::new($false))
    & (Join-Path $naruPackageRoot 'naru.exe') resolve --project $naruAsyncManifest | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Resolving relocated async example failed' }
}
$naruLicenseDestination = Join-Path $naruPackageRoot 'licenses'
New-Item -ItemType Directory -Force $naruLicenseDestination | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'backend\native\lld\source\LICENSE.TXT') -Destination (Join-Path $naruLicenseDestination 'LLVM.txt') -Force
Copy-Item -LiteralPath (Join-Path $VyxSdk 'LICENSE') -Destination (Join-Path $naruLicenseDestination 'Vyx.txt') -Force
Copy-Item -LiteralPath (Join-Path $VyxSdk 'LICENSE-MIT') -Destination (Join-Path $naruLicenseDestination 'Vyx-MIT.txt') -Force
Copy-Item -LiteralPath (Join-Path $VyxSdk 'LICENSE-APACHE') -Destination (Join-Path $naruLicenseDestination 'Vyx-APACHE.txt') -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'packages\vyx-logger\vendor\spdlog\LICENSE') -Destination (Join-Path $naruLicenseDestination 'spdlog.txt') -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'packages\vyx-logger\vendor\spdlog\include\spdlog\fmt\bundled\fmt.license.rst') -Destination (Join-Path $naruLicenseDestination 'fmt.txt') -Force
$naruDistribution = [ordered]@{
    format = 1; version = $Version; compiler_version = '0.2.0'; channel = 'preview'; platform = 'windows-x86_64'; backend = 'in-process'
    license = 'MIT OR Apache-2.0'
    c11 = [ordered]@{ full_conformance_claimed = $false; support_plan = 'docs/c11-support-plan.json' }
    coro = [ordered]@{ kinds = @('synchronous-generator', 'async-task', 'async-generator', 'promise'); ir = 'async.coro'; target_pass = 'plugins/naru_coro_plugin.dll'; runtime = 'runtime/naru_tasks.lib'; contract = 'docs/coro.md'; general_io_library_claimed = $false }
    external_toolchain_required = $false; python_required = $false
    package_manager = [ordered]@{ entry = 'naru.ps1'; python = '3.11+'; git_for_repository_sources = $true; registry = 'registry/index.json' }
    crt_linking = [ordered]@{ library_source = 'Installed MSVC and Windows SDK'; external_processes_required = $false }
    artifacts = @('naru.exe', 'naru_mlir_backend.dll', 'plugins\naru_coro_plugin.dll', 'runtime\naru_tasks.lib') | ForEach-Object {
        [ordered]@{ file = $_; sha256 = (Get-FileHash -LiteralPath (Join-Path $naruPackageRoot $_) -Algorithm SHA256).Hash.ToLowerInvariant() }
    }
}
$naruDistribution | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $naruPackageMarker -Encoding utf8
& python (Join-Path $PSScriptRoot 'tools\release\prepare.py') check-package --package $naruPackageRoot
if ($LASTEXITCODE -ne 0) { throw 'Distribution release checks failed' }
if (!$NoZip) {
    $naruArchivePath = $naruPackageRoot + '.zip'
    Compress-Archive -LiteralPath $naruPackageRoot -DestinationPath $naruArchivePath -CompressionLevel Optimal -Force
    $naruArchiveHash = (Get-FileHash -LiteralPath $naruArchivePath -Algorithm SHA256).Hash.ToLowerInvariant()
    [IO.File]::WriteAllText($naruArchivePath + '.sha256', $naruArchiveHash + '  ' + [IO.Path]::GetFileName($naruArchivePath) + "`n", [Text.UTF8Encoding]::new($false))
    Write-Host "Distribution archive: $naruArchivePath"
}
Write-Host "Standalone compiler: $(Join-Path $naruPackageRoot 'naru.exe')"
