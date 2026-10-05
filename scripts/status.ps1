[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$Root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')); $envFile=Join-Path $Root '.env'; $key=''
function Get-LocalEnvValue([string]$Name,[string]$Default){
    if(-not(Test-Path -LiteralPath $envFile)){return $Default}
    $line=Get-Content -LiteralPath $envFile | Where-Object {$_ -like "$Name=*"} | Select-Object -First 1
    if(-not $line){return $Default}
    $value=$line.Substring($line.IndexOf('=')+1).Trim()
    if($value.Length -eq 0){return $Default}
    return $value
}
if(Test-Path -LiteralPath $envFile){$line=Get-Content -LiteralPath $envFile | Where-Object {$_ -like 'LOCAL_LLM_API_KEY=*'} | Select-Object -First 1;if($line){$key=$line.Substring($line.IndexOf('=')+1)}}
$gatewayPort=Get-LocalEnvValue 'LOCAL_LLM_GATEWAY_PORT' '8080'
$webuiPort=Get-LocalEnvValue 'LOCAL_LLM_WEBUI_PORT' '7860'
$webuiBind=Get-LocalEnvValue 'LOCAL_LLM_WEBUI_HOST' '127.0.0.1'
$gatewayBind=Get-LocalEnvValue 'LOCAL_LLM_GATEWAY_HOST' '127.0.0.1'
$allowedCidrs=Get-LocalEnvValue 'LOCAL_LLM_ALLOWED_CLIENT_CIDRS' '127.0.0.1/32,::1/128'
$webuiAllowedCidrs=Get-LocalEnvValue 'LOCAL_LLM_WEBUI_ALLOWED_CLIENT_CIDRS' '127.0.0.1/32,::1/128'
$tailscaleIp=''
try{$tailscaleIp=(& tailscale ip -4 2>$null | Select-Object -First 1).Trim()}catch{$tailscaleIp=''}
$gatewayCheckHost=if($gatewayBind -eq '0.0.0.0' -or $gatewayBind -eq '::'){'127.0.0.1'}else{$gatewayBind}
$webuiCheckHost=if($webuiBind -eq '0.0.0.0' -or $webuiBind -eq '::'){'127.0.0.1'}else{$webuiBind}
$headers=@{Authorization="Bearer $key"}; $out=[ordered]@{}
try{$out.ollama=(Invoke-RestMethod http://127.0.0.1:11434/api/version -TimeoutSec 3).version}catch{$out.ollama='stopped'}
try{$out.gateway=Invoke-RestMethod "http://$gatewayCheckHost`:$gatewayPort/health/ready" -Headers $headers -TimeoutSec 5}catch{$out.gateway='stopped'}
try{$r=Invoke-WebRequest "http://$webuiCheckHost`:$webuiPort" -UseBasicParsing -TimeoutSec 3;$out.webui=if($r.StatusCode -eq 401){'auth_required'}elseif($r.StatusCode -eq 200){'ready'}else{'error'}}catch{if($_.Exception.Response -and $_.Exception.Response.StatusCode.value__ -eq 401){$out.webui='auth_required'}else{$out.webui='stopped'}}
$out.gateway_bind=$gatewayBind
$out.allowed_client_cidrs=$allowedCidrs
$out.webui_bind=$webuiBind
$out.webui_allowed_client_cidrs=$webuiAllowedCidrs
if($tailscaleIp){$out.tailscale_api_base="http://$tailscaleIp`:$gatewayPort/v1"}
if($tailscaleIp){$out.tailscale_webui_url="http://$tailscaleIp`:$webuiPort/"}
$out | ConvertTo-Json -Depth 5
