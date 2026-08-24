[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$taskName='FVA-LocalLLM-Platform'
if(Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue){
  Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}
Write-Host "Removed startup task: $taskName"
