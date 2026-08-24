[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$Runtime = Join-Path $Root '.runtime'
$Venv = Join-Path $Runtime 'venv'
foreach ($path in @($Runtime,(Join-Path $Root 'logs'),(Join-Path $Root 'state'),(Join-Path $Root 'benchmarks\results'))) { New-Item -ItemType Directory -Force -Path $path | Out-Null }
if (-not (Test-Path -LiteralPath (Join-Path $Root '.env'))) {
    $bytes = New-Object byte[] 32
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    $key = ([BitConverter]::ToString($bytes)).Replace('-', '').ToLowerInvariant()
    $template = (Get-Content -LiteralPath (Join-Path $Root '.env.example') -Raw).Replace('replace-with-a-long-random-secret',$key)
    Set-Content -LiteralPath (Join-Path $Root '.env') -Value $template -Encoding UTF8
}
if (-not (Test-Path -LiteralPath (Join-Path $Venv 'Scripts\python.exe'))) { python -m venv $Venv }
& (Join-Path $Venv 'Scripts\python.exe') -m pip install --disable-pip-version-check -r (Join-Path $Root 'requirements.txt')
Write-Host "Standalone platform prepared at $Root"
