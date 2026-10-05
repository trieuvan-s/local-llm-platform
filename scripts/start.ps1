[CmdletBinding()]
param([switch]$OpenWebUI)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$Runtime = Join-Path $Root '.runtime'; $State = Join-Path $Root 'state'; $Logs = Join-Path $Root 'logs'
$Ollama = Join-Path $Runtime 'ollama\ollama.exe'; $Python = Join-Path $Runtime 'venv\Scripts\python.exe'
$Models = Join-Path $Runtime 'models'; $UserProfile = Join-Path $Runtime 'ollama-user'
foreach($leaf in @($Ollama,$Python,(Join-Path $Root '.env'))) { if(-not(Test-Path -LiteralPath $leaf -PathType Leaf)){throw "Missing runtime file: $leaf"} }
$apiKeyLine=Get-Content -LiteralPath (Join-Path $Root '.env') | Where-Object {$_ -like 'LOCAL_LLM_API_KEY=*'} | Select-Object -First 1
if(-not $apiKeyLine){throw 'LOCAL_LLM_API_KEY is missing from the platform .env'}
$apiKey=$apiKeyLine.Substring($apiKeyLine.IndexOf('=')+1).Trim()
if($apiKey.Length -lt 32){throw 'LOCAL_LLM_API_KEY is too short'}
$env:LOCAL_LLM_API_KEY=$apiKey
$envLines=Get-Content -LiteralPath (Join-Path $Root '.env')
function Get-LocalEnvValue([string]$Name,[string]$Default){
    $line=$envLines | Where-Object {$_ -like "$Name=*"} | Select-Object -First 1
    if(-not $line){return $Default}
    $value=$line.Substring($line.IndexOf('=')+1).Trim()
    if($value.Length -eq 0){return $Default}
    return $value
}
$GatewayHost=Get-LocalEnvValue 'LOCAL_LLM_GATEWAY_HOST' '127.0.0.1'
$GatewayPort=Get-LocalEnvValue 'LOCAL_LLM_GATEWAY_PORT' '8080'
$WebUIHost=Get-LocalEnvValue 'LOCAL_LLM_WEBUI_HOST' '127.0.0.1'
$WebUIPort=Get-LocalEnvValue 'LOCAL_LLM_WEBUI_PORT' '7860'
$AllowedCidrs=Get-LocalEnvValue 'LOCAL_LLM_ALLOWED_CLIENT_CIDRS' '127.0.0.1/32,::1/128'
$env:LOCAL_LLM_GATEWAY_HOST=$GatewayHost
$env:LOCAL_LLM_GATEWAY_PORT=$GatewayPort
$env:LOCAL_LLM_WEBUI_HOST=$WebUIHost
$env:LOCAL_LLM_WEBUI_PORT=$WebUIPort
$env:LOCAL_LLM_ALLOWED_CLIENT_CIDRS=$AllowedCidrs
New-Item -ItemType Directory -Force -Path $State,$Logs,$Models,$UserProfile | Out-Null
$env:USERPROFILE=$UserProfile; $env:OLLAMA_HOST='127.0.0.1:11434'; $env:OLLAMA_MODELS=$Models
$env:OLLAMA_KEEP_ALIVE='30m'; $env:OLLAMA_MAX_LOADED_MODELS='1'; $env:OLLAMA_NUM_PARALLEL='1'; $env:OLLAMA_MAX_QUEUE='4'
try { Invoke-RestMethod http://127.0.0.1:11434/api/version -TimeoutSec 2 | Out-Null } catch {
    $p=Start-Process -FilePath $Ollama -ArgumentList 'serve' -WorkingDirectory $Root -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $Logs 'ollama.stdout.log') -RedirectStandardError (Join-Path $Logs 'ollama.stderr.log')
    Set-Content -LiteralPath (Join-Path $State 'ollama.pid') -Value $p.Id -Encoding ascii
}
foreach($i in 1..30){try{Invoke-RestMethod http://127.0.0.1:11434/api/version -TimeoutSec 2|Out-Null;break}catch{Start-Sleep 1}}
$GatewayCheckHost=if($GatewayHost -eq '0.0.0.0' -or $GatewayHost -eq '::'){'127.0.0.1'}else{$GatewayHost}
$GatewayBase="http://$GatewayCheckHost`:$GatewayPort"
try { Invoke-RestMethod "$GatewayBase/health/live" -TimeoutSec 2 | Out-Null } catch {
    $p=Start-Process -FilePath $Python -ArgumentList @('-m','uvicorn','local_llm.gateway:app','--host',$GatewayHost,'--port',$GatewayPort,'--no-access-log') -WorkingDirectory $Root -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $Logs 'gateway.stdout.log') -RedirectStandardError (Join-Path $Logs 'gateway.stderr.log')
    Set-Content -LiteralPath (Join-Path $State 'gateway.pid') -Value $p.Id -Encoding ascii
}
foreach($i in 1..30){try{Invoke-RestMethod "$GatewayBase/health/live" -TimeoutSec 2|Out-Null;break}catch{Start-Sleep 1}}
$WebUICheckHost=if($WebUIHost -eq '0.0.0.0' -or $WebUIHost -eq '::'){'127.0.0.1'}else{$WebUIHost}
$WebUIBase="http://$WebUICheckHost`:$WebUIPort"
try { Invoke-WebRequest $WebUIBase -UseBasicParsing -TimeoutSec 2 | Out-Null } catch {
    $p=Start-Process -FilePath $Python -ArgumentList @('-m','local_llm.webui') -WorkingDirectory $Root -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $Logs 'webui.stdout.log') -RedirectStandardError (Join-Path $Logs 'webui.stderr.log')
    Set-Content -LiteralPath (Join-Path $State 'webui.pid') -Value $p.Id -Encoding ascii
}
& (Join-Path $PSScriptRoot 'status.ps1')
if($OpenWebUI){Start-Process "http://127.0.0.1:$WebUIPort"}
