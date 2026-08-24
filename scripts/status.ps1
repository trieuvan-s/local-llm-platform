[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$Root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')); $envFile=Join-Path $Root '.env'; $key=''
if(Test-Path -LiteralPath $envFile){$line=Get-Content -LiteralPath $envFile | Where-Object {$_ -like 'LOCAL_LLM_API_KEY=*'} | Select-Object -First 1;if($line){$key=$line.Substring($line.IndexOf('=')+1)}}
$headers=@{Authorization="Bearer $key"}; $out=[ordered]@{}
try{$out.ollama=(Invoke-RestMethod http://127.0.0.1:11434/api/version -TimeoutSec 3).version}catch{$out.ollama='stopped'}
try{$out.gateway=Invoke-RestMethod http://127.0.0.1:8080/health/ready -Headers $headers -TimeoutSec 5}catch{$out.gateway='stopped'}
try{$r=Invoke-WebRequest http://127.0.0.1:7860 -UseBasicParsing -TimeoutSec 3;$out.webui=if($r.StatusCode -eq 200){'ready'}else{'error'}}catch{$out.webui='stopped'}
$out | ConvertTo-Json -Depth 5

