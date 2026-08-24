[CmdletBinding()]
param([switch]$SkipQwen36,[switch]$SkipQwen14,[switch]$IncludeQwen8)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$Root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')); $Ollama=Join-Path $Root '.runtime\ollama\ollama.exe'
if(-not(Test-Path -LiteralPath $Ollama)){throw 'Run migration/setup before pulling models.'}
$env:OLLAMA_HOST='127.0.0.1:11434'; $env:OLLAMA_MODELS=Join-Path $Root '.runtime\models'
if(-not $SkipQwen36){& $Ollama pull 'qwen3.6:35b';if($LASTEXITCODE-ne 0){throw 'Qwen3.6 pull failed'}}
if(-not $SkipQwen14){& $Ollama pull 'qwen3:14b';if($LASTEXITCODE-ne 0){throw 'Qwen3-14B pull failed'}}
if($IncludeQwen8){& $Ollama pull 'qwen3:8b';if($LASTEXITCODE-ne 0){throw 'Qwen3-8B pull failed'}}
& $Ollama list
