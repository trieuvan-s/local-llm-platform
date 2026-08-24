[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$Root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$StartScript=Join-Path $Root 'scripts\start.ps1'
if(-not(Test-Path -LiteralPath $StartScript -PathType Leaf)){throw "Missing start script: $StartScript"}
$taskName='FVA-LocalLLM-Platform'
$action=New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$StartScript`""
$trigger=New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings=New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description 'Standalone loopback Ollama, authenticated Local LLM Gateway, and WebUI.' -Force | Out-Null
Write-Host "Installed startup task: $taskName"
