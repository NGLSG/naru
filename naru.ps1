# Package-aware launcher. Native naru.exe remains usable without Python or Git.
& python (Join-Path $PSScriptRoot 'tools\pkg\naru.py') @args
exit $LASTEXITCODE
