#requires -Version 7.0
[CmdletBinding()]
param([string]$Root='C:\soft-system-97')
Set-StrictMode -Version Latest
$rootPath = (Resolve-Path -LiteralPath $Root -ErrorAction Stop).Path
$excluded = '(?i)(^|[\\/])(\.git|\.env[^\\/]*|sites|node_modules|\.venv|venv|__pycache__|backups?|logs?|private|secrets?|credentials?)([\\/]|$)'
$forbiddenName = '(?i)(secret|password|token|credential|site_config|common_site_config|private.?key|database|dump|backup|\.env)'
$terms = 'client_ticket_api|ticket_workspace|ticket_types|ss97_client_ticket_api|ss97_client_support|ss97_client_ops|technicien|technician|assigned_to|\bIssue\b|\bToDo\b|User Permission|Has Role|Server Script|Client Script|Website Route|Portal'
function Visit([string]$Directory) {
    foreach ($item in Get-ChildItem -LiteralPath $Directory -Force -ErrorAction Stop) {
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { continue }
        if ($item.FullName -match $excluded -or $item.Name -match $forbiddenName) { continue }
        if ($item.PSIsContainer) { Visit $item.FullName; continue }
        if ($item.Extension -notin @('.py','.js','.html','.json') -or $item.Length -gt 2MB) { continue }
        # Return paths only. Matching lines and source contents are never printed or copied.
        if ($item.Name -match 'client_ticket_api|ticket_workspace|ticket_types' -or
            (Select-String -LiteralPath $item.FullName -Pattern $terms -Quiet -ErrorAction Stop)) {
            [pscustomobject]@{ RelativePath=[IO.Path]::GetRelativePath($rootPath,$item.FullName) }
        }
    }
}
if ((Get-Item -LiteralPath $rootPath).Attributes -band [IO.FileAttributes]::ReparsePoint) {
    throw 'The discovery root must not be a link or junction.'
}
Visit $rootPath
