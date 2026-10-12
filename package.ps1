param([string]$Output = '', [string]$VyxSdk = $env:VYX_SDK_ROOT, [switch]$NoZip)
$ErrorActionPreference = 'Stop'
if (!$Output) { $Output = Join-Path $PSScriptRoot 'target\dist\naru-windows-x86_64' }
if (!$VyxSdk) { $VyxSdk = 'E:\Dev\C++\VyxLan-selfhost-yolo\dist\vyx-sdk-windows-x86_64-llvm22' }
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
foreach ($naruArtifact in @('naru.exe', 'naru_mlir_backend.dll')) {
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
New-Item -ItemType Directory -Force (Join-Path $naruPackageRoot 'docs') | Out-Null
foreach ($naruDoc in @('rule-system.md', 'projects.md', 'packages.md', 'externc.md', 'rule-libraries.md', 'operators.md', 'c11.md', 'b.md', 'pascal.md', 'dialect-debug.md')) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot ('docs\' + $naruDoc)) -Destination (Join-Path $naruPackageRoot ('docs\' + $naruDoc)) -Force
}
foreach ($naruDataFile in @('Naru.toml', 'Naru.lock', 'README.md')) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $naruDataFile) -Destination $naruPackageRoot -Force
}
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'naru.ps1') -Destination $naruPackageRoot -Force
foreach ($naruPackageData in @('tools\pkg', 'registry', 'templates\dialect')) {
    Copy-NaruProjectData -Source (Join-Path $PSScriptRoot $naruPackageData) -Destination (Join-Path $naruPackageRoot $naruPackageData)
}
$naruProfiles = Join-Path $naruPackageRoot 'backend'
New-Item -ItemType Directory -Force $naruProfiles | Out-Null
Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot 'backend') -Filter '*-target.json' | Copy-Item -Destination $naruProfiles -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'backend\examples') -Destination $naruProfiles -Recurse -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'backend\README.md') -Destination $naruProfiles -Force
$naruPluginDestination = Join-Path $naruPackageRoot 'plugins'
New-Item -ItemType Directory -Force $naruPluginDestination | Out-Null
foreach ($naruPluginArtifact in @('naru_mark_plugin.dll', 'naru_device_plugin.dll')) {
    $naruPluginSource = Join-Path $PSScriptRoot ('target\' + $naruPluginArtifact)
    if (Test-Path -LiteralPath $naruPluginSource) { Copy-Item -LiteralPath $naruPluginSource -Destination $naruPluginDestination -Force }
}
$naruLicenseDestination = Join-Path $naruPackageRoot 'licenses'
New-Item -ItemType Directory -Force $naruLicenseDestination | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'backend\native\lld\source\LICENSE.TXT') -Destination (Join-Path $naruLicenseDestination 'LLVM.txt') -Force
Copy-Item -LiteralPath (Join-Path $VyxSdk 'LICENSE') -Destination (Join-Path $naruLicenseDestination 'Vyx.txt') -Force
Copy-Item -LiteralPath (Join-Path $VyxSdk 'LICENSE-MIT') -Destination (Join-Path $naruLicenseDestination 'Vyx-MIT.txt') -Force
Copy-Item -LiteralPath (Join-Path $VyxSdk 'LICENSE-APACHE') -Destination (Join-Path $naruLicenseDestination 'Vyx-APACHE.txt') -Force
$naruDistribution = [ordered]@{
    format = 1; version = '0.2.0'; platform = 'windows-x86_64'; backend = 'in-process'
    external_toolchain_required = $false; python_required = $false
    package_manager = [ordered]@{ entry = 'naru.ps1'; python = '3.11+'; git_for_repository_sources = $true; registry = 'registry/index.json' }
    crt_linking = [ordered]@{ library_source = 'Installed MSVC and Windows SDK'; external_processes_required = $false }
    artifacts = @('naru.exe', 'naru_mlir_backend.dll') | ForEach-Object {
        [ordered]@{ file = $_; sha256 = (Get-FileHash -LiteralPath (Join-Path $naruPackageRoot $_) -Algorithm SHA256).Hash.ToLowerInvariant() }
    }
}
$naruDistribution | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $naruPackageMarker -Encoding utf8
if (!$NoZip) {
    $naruArchivePath = $naruPackageRoot + '.zip'
    Compress-Archive -LiteralPath $naruPackageRoot -DestinationPath $naruArchivePath -CompressionLevel Optimal -Force
    Write-Host "Distribution archive: $naruArchivePath"
}
Write-Host "Standalone compiler: $(Join-Path $naruPackageRoot 'naru.exe')"
