param([string]$Output = '')
$ErrorActionPreference = 'Stop'
$naruRuntimeRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
if (!$Output) { $Output = Join-Path $naruRuntimeRoot 'target\naru_tasks.lib' }
$naruRuntimeObject = Join-Path (Split-Path $Output) 'naru_tasks.obj'
New-Item -ItemType Directory -Force (Split-Path $Output) | Out-Null
& clang++ -std=c++20 -O2 -fms-runtime-lib=static -c (Join-Path $PSScriptRoot 'tasks.cpp') -o $naruRuntimeObject
if ($LASTEXITCODE -ne 0) { throw 'Compiling the coroutine executor failed' }
& llvm-lib ('/out:' + $Output) $naruRuntimeObject
if ($LASTEXITCODE -ne 0) { throw 'Archiving the coroutine executor failed' }
