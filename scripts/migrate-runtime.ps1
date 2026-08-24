[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$StockProjectRoot)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$Root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')); $Source=[IO.Path]::GetFullPath($StockProjectRoot)
if($Root -eq $Source){throw 'Source and destination must be different.'}
$sourceRuntime=Join-Path $Source '.runtime'; $targetRuntime=Join-Path $Root '.runtime'
if(-not(Test-Path -LiteralPath (Join-Path $sourceRuntime 'ollama\ollama.exe'))){throw 'Source Ollama runtime not found.'}
New-Item -ItemType Directory -Force -Path $targetRuntime,(Join-Path $Root 'logs'),(Join-Path $Root 'state'),(Join-Path $Root 'benchmarks\legacy') | Out-Null
$moves=@(
  @{Source=(Join-Path $sourceRuntime 'ollama');Target=(Join-Path $targetRuntime 'ollama')},
  @{Source=(Join-Path $sourceRuntime 'ollama-models');Target=(Join-Path $targetRuntime 'models')},
  @{Source=(Join-Path $sourceRuntime 'ollama-user');Target=(Join-Path $targetRuntime 'ollama-user')},
  @{Source=(Join-Path $sourceRuntime 'qwen-gateway-venv');Target=(Join-Path $targetRuntime 'venv')}
)
foreach($move in $moves){
  $src=[IO.Path]::GetFullPath($move.Source);$dst=[IO.Path]::GetFullPath($move.Target)
  if(-not $src.StartsWith($sourceRuntime+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw "Unsafe source: $src"}
  if(-not $dst.StartsWith($targetRuntime+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw "Unsafe target: $dst"}
  if(Test-Path -LiteralPath $dst){throw "Target already exists: $dst"}
}
& (Join-Path $Source 'scripts\qwen\stop.ps1')
foreach($move in $moves){Move-Item -LiteralPath $move.Source -Destination $move.Target}
foreach($name in 'qwen-benchmark','qwen-benchmark-v2','qwen-benchmark-v2-final','qwen-benchmark-v3','qwen-real-tests'){
  $src=Join-Path $sourceRuntime $name; if(Test-Path -LiteralPath $src){Move-Item -LiteralPath $src -Destination (Join-Path $Root "benchmarks\legacy\$name")}
}
$artifactTarget=Join-Path $Root 'benchmarks\legacy\artifacts'; New-Item -ItemType Directory -Force -Path $artifactTarget | Out-Null
foreach($name in 'qwen36-benchmark.json','qwen32b-benchmark.json'){
  $src=Join-Path $Source "data\runtime\$name"; if(Test-Path -LiteralPath $src){Move-Item -LiteralPath $src -Destination (Join-Path $artifactTarget $name)}
}
$legacyLogs=Join-Path $Root 'logs\legacy'; New-Item -ItemType Directory -Force -Path $legacyLogs | Out-Null
Get-ChildItem -LiteralPath (Join-Path $Source 'logs') -Filter 'qwen-*.log' -File -ErrorAction SilentlyContinue | ForEach-Object {
  Move-Item -LiteralPath $_.FullName -Destination (Join-Path $legacyLogs $_.Name)
}
Write-Host "Runtime migrated from $Source to $Root"
