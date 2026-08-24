[CmdletBinding()]
param([switch]$OpenWebUI)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$Runtime = Join-Path $Root '.runtime'; $State = Join-Path $Root 'state'; $Logs = Join-Path $Root 'logs'
$Ollama = Join-Path $Runtime 'ollama\ollama.exe'; $Python = Join-Path $Runtime 'venv\Scripts\python.exe'
$Models = Join-Path $Runtime 'models'; $UserProfile = Join-Path $Runtime 'ollama-user'
foreach($leaf in @($Ollama,$Python,(Join-Path $Root '.env'))) { if(-not(Test-Path -LiteralPath $leaf -PathType Leaf)){throw "Missing runtime file: $leaf"} }
New-Item -ItemType Directory -Force -Path $State,$Logs,$Models,$UserProfile | Out-Null
$env:USERPROFILE=$UserProfile; $env:OLLAMA_HOST='127.0.0.1:11434'; $env:OLLAMA_MODELS=$Models
$env:OLLAMA_KEEP_ALIVE='30m'; $env:OLLAMA_MAX_LOADED_MODELS='1'; $env:OLLAMA_NUM_PARALLEL='1'; $env:OLLAMA_MAX_QUEUE='4'
try { Invoke-RestMethod http://127.0.0.1:11434/api/version -TimeoutSec 2 | Out-Null } catch {
    $p=Start-Process -FilePath $Ollama -ArgumentList 'serve' -WorkingDirectory $Root -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $Logs 'ollama.stdout.log') -RedirectStandardError (Join-Path $Logs 'ollama.stderr.log')
    Set-Content -LiteralPath (Join-Path $State 'ollama.pid') -Value $p.Id -Encoding ascii
}
foreach($i in 1..30){try{Invoke-RestMethod http://127.0.0.1:11434/api/version -TimeoutSec 2|Out-Null;break}catch{Start-Sleep 1}}
try { Invoke-RestMethod http://127.0.0.1:8080/health/live -TimeoutSec 2 | Out-Null } catch {
    $p=Start-Process -FilePath $Python -ArgumentList @('-m','uvicorn','local_llm.gateway:app','--host','127.0.0.1','--port','8080','--no-access-log') -WorkingDirectory $Root -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $Logs 'gateway.stdout.log') -RedirectStandardError (Join-Path $Logs 'gateway.stderr.log')
    Set-Content -LiteralPath (Join-Path $State 'gateway.pid') -Value $p.Id -Encoding ascii
}
foreach($i in 1..30){try{Invoke-RestMethod http://127.0.0.1:8080/health/live -TimeoutSec 2|Out-Null;break}catch{Start-Sleep 1}}
try { Invoke-WebRequest http://127.0.0.1:7860 -UseBasicParsing -TimeoutSec 2 | Out-Null } catch {
    $p=Start-Process -FilePath $Python -ArgumentList @('-m','local_llm.webui') -WorkingDirectory $Root -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $Logs 'webui.stdout.log') -RedirectStandardError (Join-Path $Logs 'webui.stderr.log')
    Set-Content -LiteralPath (Join-Path $State 'webui.pid') -Value $p.Id -Encoding ascii
}
& (Join-Path $PSScriptRoot 'status.ps1')
if($OpenWebUI){Start-Process 'http://127.0.0.1:7860'}

