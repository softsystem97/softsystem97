#requires -Version 7.0
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$script:count=0
function Assert($Condition,[string]$Label) {
    if (-not $Condition) { throw "FAIL: $Label" }
    $script:count++
    Write-Output "PASS: $Label"
}
$root=Split-Path $PSScriptRoot -Parent
foreach ($file in Get-ChildItem $root -Recurse -File | Where-Object Extension -in @('.ps1','.psm1')) {
    $tokens=$errors=$null
    $null=[Management.Automation.Language.Parser]::ParseFile($file.FullName,[ref]$tokens,[ref]$errors)
    Assert ($errors.Count -eq 0) ('Syntax: '+$file.Name)
}
Add-Type -TypeDefinition @'
using System; using System.Net; using System.Net.Http; using System.Threading; using System.Threading.Tasks; using System.Collections.Generic;
public class SS97OfflineHandler : HttpMessageHandler {
 public static Queue<HttpResponseMessage> Replies = new Queue<HttpResponseMessage>();
 public static List<string> Uris = new List<string>(); public static List<string> Methods = new List<string>();
 public static void Reset() { Replies.Clear(); Uris.Clear(); Methods.Clear(); }
 public static void Add(int code, string json) { Replies.Enqueue(new HttpResponseMessage((HttpStatusCode)code) { Content=new StringContent(json) }); }
 protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage r, CancellationToken c) {
  Uris.Add(r.RequestUri.ToString()); Methods.Add(r.Method.ToString());
  if(Replies.Count==0) throw new InvalidOperationException("Unexpected offline request");
  return Task.FromResult(Replies.Dequeue());
 }
}
'@
Import-Module (Join-Path $root 'SS97.ReadOnly.psm1') -Force
$module=Get-Module 'SS97.ReadOnly'
# No key or secret is generated or requested. HTTP responses are offline fixtures.
& $module {
    function script:New-SS97Client { [Net.Http.HttpClient]::new([SS97OfflineHandler]::new()) }
    function script:Set-SS97Authorization($Client) { }
}
function Start-Case { [SS97OfflineHandler]::Reset() }
function Login-Response { [SS97OfflineHandler]::Add(200,'{"message":"lab-user@example.invalid"}') }
Start-Case; Login-Response
$r=Invoke-SS97Check -Kind API -BaseUri https://lab.example.invalid
Assert $r.Success 'Authenticated response contract (offline, no credentials)'
Start-Case; [SS97OfflineHandler]::Add(200,'{"message":"Guest"}')
$r=Invoke-SS97Check -Kind API -BaseUri https://lab.example.invalid
Assert (-not $r.Success) 'Guest never reported authenticated'
Start-Case; [SS97OfflineHandler]::Add(403,'{"private":"body must not escape"}')
$r=Invoke-SS97Check -Kind API -BaseUri https://lab.example.invalid
Assert (-not $r.Success -and $r.HttpStatus -eq 403 -and ($r|ConvertTo-Json) -notmatch 'private|body must') '403 sanitized'
Start-Case; [SS97OfflineHandler]::Add(302,'')
$r=Invoke-SS97Check -Kind API -BaseUri https://lab.example.invalid
Assert (-not $r.Success -and [SS97OfflineHandler]::Uris.Count -eq 1) 'Redirect response rejected'
Start-Case; [SS97OfflineHandler]::Add(200,'not-json')
$r=Invoke-SS97Check -Kind API -BaseUri https://lab.example.invalid
Assert (-not $r.Success) 'Invalid response rejected'
Start-Case
$r=Invoke-SS97Check -Kind API -BaseUri http://lab.example.invalid
Assert (-not $r.Success -and [SS97OfflineHandler]::Uris.Count -eq 0) 'HTTP origin rejected before input or network'
Start-Case
$r=Invoke-SS97Check -Kind API -BaseUri https://lab.example.invalid/unapproved-path
Assert (-not $r.Success -and [SS97OfflineHandler]::Uris.Count -eq 0) 'Origin path rejected'
Start-Case
$r=Invoke-SS97Check -Kind Tickets -BaseUri https://lab.example.invalid
Assert (-not $r.Success -and [SS97OfflineHandler]::Uris.Count -eq 0) 'Ticket DocType must be confirmed explicitly'
Start-Case; Login-Response; [SS97OfflineHandler]::Add(200,'{"data":[]}')
$r=Invoke-SS97Check -Kind Tickets -BaseUri https://lab.example.invalid -TicketDocType Issue
Assert ($r.Success -and $r.AccessibleCount -eq 0 -and -not $r.CompleteWorkflowValidated) 'Empty list does not validate ticket workflow'
Start-Case; Login-Response; [SS97OfflineHandler]::Add(403,'{}')
$r=Invoke-SS97Check -Kind Tickets -BaseUri https://lab.example.invalid -TicketDocType Issue
Assert (-not $r.Success) 'Ticket permission denial preserved'
Start-Case; Login-Response; [SS97OfflineHandler]::Add(200,'{"data":[{"reference_name":"lab-ticket"}]}')
[SS97OfflineHandler]::Add(200,'{"data":[{"name":"lab-ticket"}]}'); [SS97OfflineHandler]::Add(200,'{"data":[]}')
$r=Invoke-SS97Check -Kind Technicien -BaseUri https://lab.example.invalid -TicketDocType Issue -ExpectedDeniedTicketName other-lab-ticket
Assert ($r.Success -and $r.ExpectedDenialObserved -and -not $r.CustomTechnicianProfileValidated) 'Native assignment/read and expected denial, custom profile unvalidated'
$decoded=[Uri]::UnescapeDataString([SS97OfflineHandler]::Uris[1])
Assert ($decoded -match 'allocated_to.*lab-user@example.invalid') 'Assignments scoped to authenticated identity'
$decoded=[Uri]::UnescapeDataString([SS97OfflineHandler]::Uris[2])
Assert ($decoded -match '\[\["name","=","lab-ticket"\]\]') 'Single filter retains nested array JSON'
Assert (@([SS97OfflineHandler]::Methods | Where-Object {$_ -ne 'GET'}).Count -eq 0) 'Only GET requests issued'
Assert (($r|ConvertTo-Json) -notmatch 'lab-ticket|lab-user') 'Output omits identities and ticket names'
Start-Case; Login-Response; [SS97OfflineHandler]::Add(200,'{"data":[]}')
$r=Invoke-SS97Check -Kind Technicien -BaseUri https://lab.example.invalid -TicketDocType Issue
Assert (-not $r.Success -and $r.AssignedCount -eq 0) 'No assignment cannot validate technician access'
Start-Case; Login-Response; [SS97OfflineHandler]::Add(200,'{"data":[{"reference_name":"lab-ticket"}]}'); [SS97OfflineHandler]::Add(200,'{"data":[{"name":"wrong-ticket"}]}')
$r=Invoke-SS97Check -Kind Technicien -BaseUri https://lab.example.invalid -TicketDocType Issue
Assert (-not $r.Success) 'Mismatched returned document never counts as authorized assignment'
Start-Case; Login-Response; [SS97OfflineHandler]::Add(200,'{"data":[{"reference_name":"lab-ticket"}]}'); [SS97OfflineHandler]::Add(403,'{}')
$r=Invoke-SS97Check -Kind Technicien -BaseUri https://lab.example.invalid -TicketDocType Issue
Assert (-not $r.Success) 'Unreadable assigned ticket fails check'
Start-Case; Login-Response; [SS97OfflineHandler]::Add(200,'{"data":[]}'); [SS97OfflineHandler]::Add(200,'{"data":[{"name":"unexpected-access"}]}')
$r=Invoke-SS97Check -Kind Technicien -BaseUri https://lab.example.invalid -TicketDocType Issue -ExpectedDeniedTicketName other-lab-ticket
Assert (-not $r.Success) 'Expected forbidden ticket visible is a failure'
Start-Case; [SS97OfflineHandler]::Add(200,'{"message":"pong"}'); [SS97OfflineHandler]::Add(403,'{}')
$r=@(Invoke-SS97Check -Kind Diagnostic -BaseUri https://lab.example.invalid)
Assert ($r.Count -eq 2 -and $r[0].HttpStatus -eq 200 -and $r[1].HttpStatus -eq 403) 'Anonymous diagnostics report HTTP status only'
$fixture=Join-Path ([IO.Path]::GetTempPath()) ('ss97-discovery-'+[guid]::NewGuid().ToString('N'))
try {
    $null=New-Item -ItemType Directory -Path $fixture
    $null=New-Item -ItemType Directory -Path (Join-Path $fixture 'sites'),(Join-Path $fixture '.env-hidden')
    Set-Content (Join-Path $fixture 'client_ticket_api.py') 'Portal synthetic marker'
    Set-Content (Join-Path $fixture 'site_config.json') 'Portal excluded marker'
    Set-Content (Join-Path $fixture 'sites/hidden.py') 'Portal excluded marker'
    Set-Content (Join-Path $fixture '.env-hidden/hidden.py') 'Portal excluded marker'
    Set-Content (Join-Path $fixture 'token_helper.py') 'Portal excluded marker'
    $found=@(& (Join-Path $root 'SS97-Find-TechnicianSources.ps1') -Root $fixture)
    Assert ($found.Count -eq 1 -and $found[0].RelativePath -eq 'client_ticket_api.py') 'Discovery excludes configuration, environment, sites and token filenames'
    Assert (($found|ConvertTo-Json) -notmatch 'synthetic marker|excluded marker') 'Discovery emits paths, never source lines'
} finally { Remove-Item -LiteralPath $fixture -Recurse -Force }
Write-Output "TOTAL: $script:count assertions passed (offline; no real token authentication)."
