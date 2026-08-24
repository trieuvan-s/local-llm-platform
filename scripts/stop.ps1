[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$Root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$Runtime=[IO.Path]::GetFullPath((Join-Path $Root '.runtime'))
$processSnapshot=@(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)
function Stop-ProcessTree([int]$TargetProcessId){
  foreach($child in @($processSnapshot | Where-Object {$_.ParentProcessId -eq $TargetProcessId})){
    Stop-ProcessTree -TargetProcessId ([int]$child.ProcessId)
  }
  Stop-Process -Id $TargetProcessId -Force -ErrorAction SilentlyContinue
}
foreach($name in 'webui','gateway','ollama'){
  $file=Join-Path $Root "state\$name.pid"; if(-not(Test-Path -LiteralPath $file)){continue}
  $processId=[int](Get-Content -LiteralPath $file -Raw); $process=Get-Process -Id $processId -ErrorAction SilentlyContinue
  if($process){Stop-ProcessTree -TargetProcessId $processId}; Remove-Item -LiteralPath $file -Force
}
foreach($candidate in @(Get-CimInstance Win32_Process -Filter "Name='llama-server.exe'" -ErrorAction SilentlyContinue)){
  if(-not $candidate.ExecutablePath){continue}
  $exe=[IO.Path]::GetFullPath([string]$candidate.ExecutablePath)
  if($exe.StartsWith($Runtime+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){
    Stop-Process -Id ([int]$candidate.ProcessId) -Force -ErrorAction SilentlyContinue
  }
}
Write-Host 'Local LLM platform stopped.'
