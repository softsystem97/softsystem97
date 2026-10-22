#requires -Version 7.0
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'SS97.CloudRules.psm1') -Force
$result = Export-SS97CloudRules
$result
if (-not $result.Success) { exit 1 }
