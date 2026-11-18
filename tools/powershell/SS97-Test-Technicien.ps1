#requires -Version 7.0
[CmdletBinding()]
param(
    [Parameter(Mandatory)][Uri]$BaseUri,
    [Parameter(Mandatory)][string]$TicketDocType,
    [ValidateRange(1,100)][int]$Limit=20,
    [string]$ExpectedDeniedTicketName
)
Import-Module (Join-Path $PSScriptRoot 'SS97.ReadOnly.psm1') -Force
$result = @(Invoke-SS97Check -Kind 'Technicien' @PSBoundParameters)
$result
if (@($result | Where-Object { $_.PSObject.Properties['Success'] -and -not $_.Success }).Count) { exit 1 }
