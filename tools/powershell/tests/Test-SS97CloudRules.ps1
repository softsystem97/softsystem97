#requires -Version 7.0
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$script:count=0
function Assert($Value, [string]$Label) {
    if (-not $Value) { throw ('FAIL: ' + $Label) }
    $script:count++; Write-Output ('PASS: ' + $Label)
}
$root=Split-Path $PSScriptRoot -Parent
foreach ($name in @('Export-SS97CloudRules.ps1','SS97.CloudRules.psm1')) {
    $tokens=$errors=$null
    $null=[Management.Automation.Language.Parser]::ParseFile((Join-Path $root $name),[ref]$tokens,[ref]$errors)
    Assert ($errors.Count -eq 0) ('Syntax '+$name)
}
Add-Type -TypeDefinition @'
using System;using System.Net;using System.Net.Http;using System.Threading;using System.Threading.Tasks;using System.Collections.Generic;
public class SS97CloudOfflineHandler:HttpMessageHandler {
 public static Queue<HttpResponseMessage> Replies=new Queue<HttpResponseMessage>();
 public static List<string> Uris=new List<string>();public static List<string> Methods=new List<string>();
 public static void Reset(){Replies.Clear();Uris.Clear();Methods.Clear();}
 public static void Add(int code,string json){Replies.Enqueue(new HttpResponseMessage((HttpStatusCode)code){Content=new StringContent(json)});}
 protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage r,CancellationToken c){Uris.Add(r.RequestUri.ToString());Methods.Add(r.Method.ToString());if(Replies.Count==0)throw new Exception("Unexpected request");return Task.FromResult(Replies.Dequeue());}
}
'@
Import-Module (Join-Path $root 'SS97.CloudRules.psm1') -Force
$transport=Get-Module SS97.ReadOnly -All | Select-Object -First 1
& $transport {
    function script:New-SS97Client { [Net.Http.HttpClient]::new([SS97CloudOfflineHandler]::new()) }
    function script:Set-SS97Authorization($Client) { } # Never prompts or uses credentials.
}
$folder=Join-Path ([IO.Path]::GetTempPath()) ('ss97-export-tests-'+[Guid]::NewGuid().ToString('N'))
$null=New-Item -ItemType Directory -Path $folder
$output=Join-Path $folder 'SS97_CLOUD_RULES.json'
function Reset-Case { [SS97CloudOfflineHandler]::Reset();Remove-Item $output -ErrorAction SilentlyContinue }
function Login { [SS97CloudOfflineHandler]::Add(200,'{"message":"synthetic-admin@example.invalid"}') }
function Empty { [SS97CloudOfflineHandler]::Add(200,'{"message":[]}') }
try {
    foreach ($status in @(401,403,302)) {
        Reset-Case
        [SS97CloudOfflineHandler]::Add($status,'{"private":"SECRET-CANARY"}')
        $r=Export-SS97CloudRules -OutputPath $output
        Assert (-not $r.Success -and -not $r.ReportWritten -and -not (Test-Path $output)) ('Authentication denial '+$status)
        Assert (([SS97CloudOfflineHandler]::Uris.Count -eq 1) -and ($r|ConvertTo-Json) -notmatch 'SECRET-CANARY') ('No follow-up or raw body '+$status)
    }
    Reset-Case;[SS97CloudOfflineHandler]::Add(200,'{"message":"Guest"}')
    $r=Export-SS97CloudRules -OutputPath $output
    Assert (-not $r.Success -and -not $r.ReportWritten) 'Guest is not authentication proof'
    Reset-Case;Login
    1..8|ForEach-Object {Empty}
    $r=Export-SS97CloudRules -OutputPath $output
    Assert ($r.Success -and $r.ReportWritten) 'Empty metadata response exports actual empty lists'
    $json=Get-Content $output -Raw
    $report=ConvertFrom-Json $json -AsHashtable
    Assert (-not $report.authorization_rules_validated) 'Export never validates business rights'
    Assert ($report.visibility -eq 'permission_scoped_not_exhaustiveness_proof') 'Native permission filtering is explicit'
    Assert ($json -notmatch 'synthetic-admin|SECRET-CANARY') 'Authenticated identity excluded'
    Assert (@([SS97CloudOfflineHandler]::Methods|Where-Object {$_ -ne 'GET'}).Count -eq 0) 'Only GET methods'
    Reset-Case;Login
    [SS97CloudOfflineHandler]::Add(200,'{"message":[{"name":"PRIVATE-WORKFLOW","document_type":"Issue","is_active":1,"workflow_state_field":"ss97_ticket_status","owner":"PRIVATE-PERSON","api_secret":"SECRET-CANARY"}]}')
    Empty
    [SS97CloudOfflineHandler]::Add(200,'{"message":[{"name":"PRIVATE-FIELD","fieldname":"ss97_technician","fieldtype":"Link","options":"User","default":"SECRET-CANARY","owner":"PRIVATE-PERSON"}]}')
    Empty
    1..6|ForEach-Object {Empty}
    [SS97CloudOfflineHandler]::Add(200,'{"message":[{"name":"PRIVATE-STATE","parent":"PRIVATE-WORKFLOW","state":"Resolved","doc_status":0,"allow_edit":"System Manager"}]}')
    Empty
    [SS97CloudOfflineHandler]::Add(200,'{"message":[{"name":"PRIVATE-TRANSITION","parent":"PRIVATE-WORKFLOW","state":"Resolved","next_state":"Closed","allowed":"SS97 Technician","condition":"SECRET-CANARY","action":"PRIVATE-ACTION"}]}')
    Empty
    $r=Export-SS97CloudRules -OutputPath $output -PageSize 1
    Assert $r.Success 'Pagination and permission-checked workflow children'
    $json=Get-Content $output -Raw
    $report=ConvertFrom-Json $json -AsHashtable
    Assert ($report.sections.workflow_states.rows[0].parent_ref -eq $report.sections.workflows.rows[0].name_ref) 'Per-report pseudonyms preserve workflow joins'
    Assert ($report.sections.custom_fields.rows[0].fieldname -eq 'ss97_technician') 'Technical field contract retained'
    Assert ($json -notmatch 'PRIVATE-|SECRET-CANARY|synthetic-admin') 'Unknown metadata, personal fields and source excluded'
    $uris=@([SS97CloudOfflineHandler]::Uris|ForEach-Object {[Uri]::UnescapeDataString($_)})
    Assert (@($uris|Where-Object {$_ -match 'parent=Workflow'}).Count -ge 2) 'Native parent permission parameter supplied'
    Assert (@($uris|Where-Object {$_ -match 'limit_start=1'}).Count -ge 2) 'Offsets actually advance'
    Assert (@($uris|Where-Object {$_ -notlike 'https://app.softsystem97.com/*'}).Count -eq 0) 'Fixed approved HTTPS origin'
    Reset-Case;Login;[SS97CloudOfflineHandler]::Add(403,'{"private":"SECRET-CANARY"}')
    1..7|ForEach-Object {Empty}
    $r=Export-SS97CloudRules -OutputPath $output
    $report=Get-Content $output -Raw|ConvertFrom-Json -AsHashtable
    Assert (-not $r.Success -and $r.ReportWritten -and $report.sections.workflows.http_status -eq 403) 'Partial report records 403 without fabricated workflow'
    Reset-Case;Login;[SS97CloudOfflineHandler]::Add(401,'{}')
    $r=Export-SS97CloudRules -OutputPath $output
    Assert (-not $r.Success -and [SS97CloudOfflineHandler]::Uris.Count -eq 2) 'Expired credentials stop collection immediately'
    Reset-Case;Login;[SS97CloudOfflineHandler]::Add(200,'{"message":[{"name":"REPEATED"}]}');[SS97CloudOfflineHandler]::Add(200,'{"message":[{"name":"REPEATED"}]}')
    1..9|ForEach-Object {Empty}
    $r=Export-SS97CloudRules -OutputPath $output -PageSize 1
    $report=Get-Content $output -Raw|ConvertFrom-Json -AsHashtable
    Assert (-not $r.Success -and $report.sections.workflows.result -eq 'duplicate_or_invalid_row') 'Repeated page cannot be reported complete'
    Reset-Case;Login;[SS97CloudOfflineHandler]::Add(200,'not-json')
    1..7|ForEach-Object {Empty}
    $r=Export-SS97CloudRules -OutputPath $output
    $report=Get-Content $output -Raw|ConvertFrom-Json -AsHashtable
    Assert (-not $r.Success -and $report.sections.workflows.result -eq 'invalid_response') 'Malformed JSON never reported complete'
    Reset-Case;Login;[SS97CloudOfflineHandler]::Add(200,'{"message":[{"name":"LIMITED"}]}')
    1..9|ForEach-Object {Empty}
    $r=Export-SS97CloudRules -OutputPath $output -PageSize 1 -MaxPages 1
    $report=Get-Content $output -Raw|ConvertFrom-Json -AsHashtable
    Assert (-not $r.Success -and $report.sections.workflows.result -eq 'page_limit') 'Bounded pagination remains explicitly incomplete'
    Set-Content -Path $output -Value 'PREVIOUS-REPORT'
    [SS97CloudOfflineHandler]::Reset();[SS97CloudOfflineHandler]::Add(401,'{}')
    $r=Export-SS97CloudRules -OutputPath $output
    Assert (-not $r.ReportWritten -and (Get-Content $output -Raw).Trim() -eq 'PREVIOUS-REPORT') 'Authentication failure does not replace or validate a previous file'
    $module=Get-Module SS97.CloudRules
    $sample=& $module {
        ConvertTo-SS97CloudMetadata @{name='PRIVATE-SELECT';fieldtype='Select';options="Open`nIntervention en pause`nPRIVATE-PERSON"} 'custom_fields' ([byte[]]::new(32))
    }
    $safe=$sample|ConvertTo-Json -Depth 12
    Assert ($safe -match 'Intervention en pause' -and $safe -notmatch 'PRIVATE-') 'Known public status vocabulary retained, unknown choices pseudonymized'
    Write-Output ("TOTAL: $script:count checks PASS (offline, fictional API responses)")
} finally { Remove-Item $folder -Recurse -Force }
