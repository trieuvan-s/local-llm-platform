[CmdletBinding()]
param([ValidateSet('qwen3.6:35b','qwen3:14b')][string]$Model='qwen3:14b')
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$Root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$line=Get-Content -LiteralPath (Join-Path $Root '.env') | Where-Object {$_ -like 'LOCAL_LLM_API_KEY=*'} | Select-Object -First 1
if(-not $line){throw 'LOCAL_LLM_API_KEY is missing'}
$key=$line.Substring($line.IndexOf('=')+1); $headers=@{Authorization="Bearer $key"}
$models=Invoke-RestMethod http://127.0.0.1:8080/v1/models -Headers $headers -TimeoutSec 10
$body=@{model=$Model;messages=@(@{role='user';content='Return exactly: LOCAL_LLM_OK'});stream=$false;think=$false;max_tokens=32;temperature=0}|ConvertTo-Json -Depth 6
$chat=Invoke-RestMethod http://127.0.0.1:8080/v1/chat/completions -Method Post -Headers $headers -ContentType 'application/json' -Body $body -TimeoutSec 900
[ordered]@{models=@($models.data.id);selected=$chat.model;answer=$chat.choices[0].message.content;metrics=$chat.local_metrics}|ConvertTo-Json -Depth 6
