#requires -Version 7.0
[CmdletBinding()]
param(
    [Parameter(Mandatory)][Uri]$BaseUri
)
Import-Module (Join-Path $PSScriptRoot 'SS97.ReadOnly.psm1') -Force
$result = @(Invoke-SS97Check -Kind 'Diagnostic' @PSBoundParameters)
$result
if (@($result | Where-Object { $_.PSObject.Properties['Success'] -and -not $_.Success }).Count) { exit 1 }
if (@($result | Where-Object { $_.HttpStatus -eq 0 -or ($_.Endpoint -eq '/api/method/ping' -and $_.HttpStatus -ne 200) }).Count) { exit 1 }
