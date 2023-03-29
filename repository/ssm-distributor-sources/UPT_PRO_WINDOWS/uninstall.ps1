<#
.SYNOPSIS
    Installs Uptycs Agent
#>
$msiDisplayName = "Your MSI Display Name Here"
$regKeyPath = "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall"
$regKeyName = Get-ChildItem $regKeyPath | Where-Object { $_.GetValue("DisplayName") -eq $msiDisplayName } | Select-Object -First 1 -ExpandProperty PSChildName
$msiProductCode = (Get-ItemProperty "$regKeyPath\$regKeyName").ProductCode
$arguments = "/x `"$msiProductCode`" /qn"
Start-Process "msiexec.exe" -ArgumentList $arguments -Wait
