<#
.SYNOPSIS
    Installs Uptycs Agent
#>
[CmdletBinding()]
$filename = "assets-osquery-5.5.1.14-Uptycs-windows.msi"
$arguments = "/i `"$filename`" /qn"
Start-Process "msiexec.exe" -ArgumentList $arguments -Wait