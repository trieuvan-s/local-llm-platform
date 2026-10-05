[CmdletBinding()]
param(
    [string]$LocalIp = "",
    [string]$GatewayPort = "8080",
    [string]$WebUIPort = "7860",
    [string]$RemoteIp = "100.64.0.0/10",
    [string]$GatewayRuleName = "FVA Local LLM Gateway Tailscale 8080",
    [string]$WebUIRuleName = "FVA Local LLM WebUI Tailscale 7860"
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)
if (-not $isAdmin) {
    throw "Run this script from an elevated PowerShell session."
}

if (-not $LocalIp) {
    $LocalIp = (& tailscale ip -4 | Select-Object -First 1).Trim()
}
if (-not $LocalIp) {
    throw "Could not detect a Tailscale IPv4 address."
}

netsh advfirewall firewall delete rule name="$GatewayRuleName" | Out-Null
netsh advfirewall firewall delete rule name="$WebUIRuleName" | Out-Null
netsh advfirewall firewall add rule name="$GatewayRuleName" dir=in action=allow protocol=TCP localip=$LocalIp localport=$GatewayPort remoteip=$RemoteIp profile=any | Out-Null
netsh advfirewall firewall add rule name="$WebUIRuleName" dir=in action=allow protocol=TCP localip=$LocalIp localport=$WebUIPort remoteip=$RemoteIp profile=any | Out-Null

[ordered]@{
    gateway_rule_name = $GatewayRuleName
    webui_rule_name = $WebUIRuleName
    local_ip = $LocalIp
    gateway_port = $GatewayPort
    webui_port = $WebUIPort
    remote_ip = $RemoteIp
    status = "enabled"
} | ConvertTo-Json
