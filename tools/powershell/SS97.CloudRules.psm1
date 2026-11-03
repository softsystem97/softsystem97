#requires -Version 7.0
Set-StrictMode -Version Latest
$script:Transport = Import-Module (Join-Path $PSScriptRoot 'SS97.ReadOnly.psm1') -PassThru
$script:Origin = 'https://app.softsystem97.com'

function Get-SS97CloudPage($Client, [string]$DocType, [string[]]$Fields, $Filters, [int]$Start, [int]$PageSize, [string]$Parent) {
    $query = @{
        doctype = $DocType
        fields = ConvertTo-Json -InputObject @($Fields) -Compress
        filters = ConvertTo-Json -InputObject $Filters -Depth 10 -Compress
        order_by = 'name asc'
        limit_start = [string]$Start
        limit_page_length = [string]$PageSize
    }
    if ($Parent) { $query.parent = $Parent }
    $pairs = foreach ($key in ($query.Keys | Sort-Object)) {
        [Uri]::EscapeDataString($key) + '=' + [Uri]::EscapeDataString($query[$key])
    }
    # Frappe v16 supports parent=Workflow/DocType for permission-checked child lists.
    $uri = $script:Origin + '/api/method/frappe.client.get_list?' + ($pairs -join '&')
    return & $script:Transport { param($c, $u) Invoke-SS97Read $c $u } $Client $uri
}

function Get-SS97CloudReference([string]$Text, [byte[]]$Salt) {
    $hmac = [Security.Cryptography.HMACSHA256]::new($Salt)
    try { return 'ref_' + [BitConverter]::ToString($hmac.ComputeHash([Text.Encoding]::UTF8.GetBytes($Text))).Replace('-','').ToLowerInvariant() }
    finally { $hmac.Dispose() }
}

function ConvertTo-SS97CloudMetadata($Row, [string]$Section, [byte[]]$Salt) {
    # Default deny: never serialize the API response, unknown fields or script bodies.
    $out = [ordered]@{}
    $flags = @('is_active','enabled','disabled','read','write','create','delete','submit','cancel','amend',
        'report','export','import','share','print','email','select','if_owner','reqd','hidden','read_only','allow_self_approval')
    $numbers = @('permlevel','doc_status','idx')
    $technical = @('fieldname','workflow_state_field','field_name')
    $known = @('Issue','User','Customer','Employee','DocType','Workflow','System Manager','Administrator',
        'SS97 Technician','SS97 Technicien','Customer','Support Team','All','Guest',
        'Open','Replied','On Hold','Resolved','Closed','DocType Event','API','Scheduler Event',
        'Before Insert','After Insert','Before Validate','Before Save','After Save','Before Submit','After Submit',
        'Before Cancel','After Cancel','Before Delete','After Delete','Check','Data','Select','Link','Text',
        'Small Text','Text Editor','Datetime','Date','Int','Float','Currency','Table','Section Break',
        'Column Break','HTML','Button','Read Only','Attach','Attach Image','Long Text','Code')

    # Public vocabulary from the committed catalogue; not an authorization rule.
    $known += @(
        'Accepter',
        'Accepté',
        'Accepté par le technicien',
        'Accepté technicien',
        'Accorder',
        'Affecter',
        'Affecté',
        'Affecté au technicien',
        'Analyse IA en cours',
        'Analyse terminée',
        'Annuler',
        'Annulé',
        'Archiver',
        'Archivé',
        'Arriver / démarrer',
        'Attente client',
        'Attribuer',
        'Attribué',
        'Autorisation distante accordée',
        'Autorisation distante demandée',
        'Autorisation distante refusée',
        'Brouillon',
        'Closed',
        'Clôturer',
        'Clôturer ticket',
        'Clôturé',
        'Commencer',
        'Demander document',
        'Demander info client',
        'Demander paiement',
        'Demander validation',
        'Devis nécessaire',
        'Diagnostic',
        'Diagnostic en cours',
        'Démarrer intervention',
        'En attente',
        'En attente client',
        'En attente d''attribution',
        'En attente d''un document',
        'En attente de paiement',
        'En attente de validation',
        'En attente document',
        'En attente du client',
        'En cours',
        'En déplacement',
        'En pause',
        'Fermer',
        'Fermé',
        'File d''attente',
        'Informations client manquantes',
        'Infos reçues',
        'Intervention en cours',
        'Intervention en pause',
        'Intervention planifiée',
        'Intervention terminée',
        'Marquer résolu',
        'Mettre en attente',
        'Mettre en pause',
        'Notification technicien envoyée',
        'Notifier technicien',
        'Nouveau',
        'On Hold',
        'Open',
        'Ouvert',
        'Ouvrir',
        'Ouvrir session',
        'Paiement confirmé',
        'Paiement requis',
        'Partir en déplacement',
        'Payé',
        'Planifier intervention',
        'Prendre en charge',
        'Prêt à commencer',
        'Rapport',
        'Rapport disponible',
        'Rapport en préparation',
        'Rapport soumis',
        'Rechercher technicien',
        'Refuser',
        'Refusé par le technicien',
        'Rendez-vous planifié',
        'Reprendre',
        'Reprendre déplacement',
        'Repris',
        'Resolved',
        'Rouvert',
        'Réaffecter',
        'Réouvert',
        'Réouvrir',
        'Résolu',
        'Résoudre',
        'Session distante active',
        'Session distante terminée',
        'Solution',
        'Solution appliquée',
        'Soumettre',
        'Soumettre rapport',
        'Suspendu — risque sécurité',
        'Technicien affecté',
        'Technicien recherché',
        'Terminer',
        'Terminer session',
        'Terminé',
        'Tests',
        'Tests OK',
        'Tests en cours',
        'Tests réussis',
        'Ticket clôturé',
        'Ticket prêt pour validation',
        'Validation administrateur en attente',
        'Validation client',
        'Validation client en attente',
        'Valider',
        'Valider client',
        'Validé',
        'Validé par le client',
        'À affecter'
    )
    foreach ($key in $Row.Keys) {
        $value = $Row[$key]
        if ($null -eq $value) { continue }
        if ($key -in $flags) {
            if ($value -is [bool]) { $out[$key] = [int]$value }
            elseif ([string]$value -in @('0','1')) { $out[$key] = [int]$value }
        } elseif ($key -in $numbers) {
            $number = 0
            if ([int]::TryParse([string]$value, [ref]$number) -and $number -ge 0 -and $number -le 10000) { $out[$key] = $number }
        } elseif ($key -in $technical -and [string]$value -cmatch '^[a-z][a-z0-9_]{0,139}$') {
            $out[$key] = [string]$value
        } elseif ($key -eq 'options' -and $Row.Contains('fieldtype') -and $Row.fieldtype -eq 'Select') {
            $out.options = @(foreach ($option in ([string]$value -split '\r?\n')) {
                if ($option -in $known -or $option -eq '') { @{ value=$option } }
                else { @{ value_ref=(Get-SS97CloudReference $option $Salt) } }
            })
        } elseif ($key -eq 'condition') {
            # Only existence is requested in a separate approved source export, never the expression.
            continue
        } elseif ($key -in @('name','parent','role','state','next_state','action','allow_edit','allowed','options','value','property','fieldtype','script_type','reference_doctype','api_method','document_type','event','doctype_event')) {
            if ([string]$value -in $known) { $out[$key] = [string]$value }
            else { $out[$key + '_ref'] = Get-SS97CloudReference ([string]$value) $Salt }
        }
    }
    return $out
}

function Export-SS97CloudRules {
    [CmdletBinding()]
    param([string]$OutputPath, [ValidateRange(1,100)][int]$PageSize = 100,
          [ValidateRange(1,1000)][int]$MaxPages = 100)
    $client = $null
    $temporary = $null
    $salt = [byte[]]::new(32)
    [Security.Cryptography.RandomNumberGenerator]::Fill($salt)
    $admin = 'Administrateur autorisé : vérifier la paire API et le compte actif (401) ; pour 403, exécuter cet export avec votre compte administratif existant autorisé à lire les DocTypes des sections en échec. Toute extension de permissions exige un accord préalable. Ne pas élever le technicien, rendre les API publiques ni renouveler une clé sans accord.'
    try {
        if (-not $OutputPath) {
            $documents = [Environment]::GetFolderPath([Environment+SpecialFolder]::MyDocuments)
            if (-not $documents -or -not [IO.Directory]::Exists($documents)) { throw 'DocumentsUnavailable' }
            $OutputPath = Join-Path $documents 'SS97_CLOUD_RULES.json'
        }
        $client = & $script:Transport { New-SS97Client }
        & $script:Transport { param($c) Set-SS97Authorization $c } $client
        $auth = & $script:Transport { param($c, $u) Invoke-SS97Read $c $u } $client ($script:Origin + '/api/method/frappe.auth.get_logged_user')
        if ($auth.Status -ne 200 -or $null -eq $auth.Payload -or -not $auth.Payload.ContainsKey('message') -or
            $auth.Payload.message -isnot [string] -or [string]::IsNullOrWhiteSpace($auth.Payload.message) -or $auth.Payload.message -eq 'Guest') {
            return [pscustomobject]@{ Success=$false; Stage='Authentication'; HttpStatus=$auth.Status; Instruction=$admin; ReportWritten=$false; Note='Tout ancien rapport est inchangé et ne représente pas cette tentative.' }
        }
        # Exact field lists, parent filters and no /User, /Issue business records, secrets or script source.
        $specs = @(
            @{ Key='workflows'; Type='Workflow'; Fields=@('name','document_type','is_active','workflow_state_field'); Filters=@{document_type='Issue';is_active=1}; Parent='' },
            @{ Key='custom_fields'; Type='Custom Field'; Fields=@('name','fieldname','fieldtype','options','reqd','hidden','read_only','permlevel'); Filters=@{dt='Issue'}; Parent='' },
            @{ Key='permissions'; Type='DocPerm'; Fields=@('name','role','permlevel','read','write','create','delete','submit','cancel','amend','if_owner','report','export','import','share','print','email','select'); Filters=@{parent='Issue';parenttype='DocType'}; Parent='DocType' },
            @{ Key='custom_permissions'; Type='Custom DocPerm'; Fields=@('name','role','permlevel','read','write','create','delete','submit','cancel','amend','if_owner','report','export','import','share','print','email','select'); Filters=@{parent='Issue'}; Parent='' },
            @{ Key='property_setters'; Type='Property Setter'; Fields=@('name','field_name','property','value'); Filters=@{doc_type='Issue'}; Parent='' },
            @{ Key='issue_server_scripts'; Type='Server Script'; Fields=@('name','script_type','reference_doctype','doctype_event','disabled'); Filters=@{reference_doctype='Issue';disabled=0}; Parent='' },
            @{ Key='api_server_scripts'; Type='Server Script'; Fields=@('name','script_type','api_method','disabled'); Filters=@{script_type='API';disabled=0}; Parent='' },
            @{ Key='client_scripts'; Type='Client Script'; Fields=@('name','enabled','view'); Filters=@{dt='Issue';enabled=1}; Parent='' }
        )
        $report = [ordered]@{ schema_version=1; site=$script:Origin; generated_at=[DateTime]::UtcNow.ToString('o'); authenticated=$true;
            visibility='permission_scoped_not_exhaustiveness_proof'; authorization_rules_validated=$false; sections=[ordered]@{} }
        $allFinished = $true
        $workflowNames = [Collections.Generic.List[string]]::new()
        # Child workflow rows are fetched only for names actually returned by the authorized list.
        for ($index=0; $index -lt $specs.Count; $index++) {
            $spec = $specs[$index]
            $rows = [Collections.Generic.List[object]]::new()
            $seen = [Collections.Generic.HashSet[string]]::new()
            $finished = $false; $status = 0; $reason = 'page_limit'
            for ($page=0; $page -lt $MaxPages; $page++) {
                $read = Get-SS97CloudPage $client $spec.Type $spec.Fields $spec.Filters ($page*$PageSize) $PageSize $spec.Parent
                $status = $read.Status
                if ($status -ne 200) { $reason='http_error'; break }
                if ($null -eq $read.Payload -or -not $read.Payload.ContainsKey('message') -or $read.Payload.message -isnot [array]) { $reason='invalid_response'; break }
                $batch = $read.Payload.message
                if ($batch.Count -gt $PageSize) { $reason='invalid_page_size'; break }
                $invalid = $false
                foreach ($row in $batch) {
                    if ($row -isnot [System.Collections.IDictionary] -or -not $row.Contains('name') -or $row.name -isnot [string] -or -not $seen.Add($row.name)) { $invalid=$true; break }
                    $rows.Add((ConvertTo-SS97CloudMetadata $row $spec.Key $salt))
                    if ($spec.Key -eq 'workflows') { $workflowNames.Add($row.name) }
                }
                if ($invalid) { $reason='duplicate_or_invalid_row'; break }
                if ($batch.Count -lt $PageSize) { $finished=$true; $reason='pagination_finished'; break }
            }
            $report.sections[$spec.Key] = [ordered]@{ rows=$rows.ToArray(); pagination_finished=$finished; http_status=$status; result=$reason }
            if (-not $finished) { $allFinished=$false }
            if ($status -eq 401) { break }
            if ($spec.Key -eq 'workflows' -and $workflowNames.Count -gt 0) {
                $specs += @(
                    @{ Key='workflow_states'; Type='Workflow Document State'; Fields=@('name','parent','state','doc_status','allow_edit','idx'); Filters=@{parent=@('in',$workflowNames.ToArray());parenttype='Workflow'}; Parent='Workflow' },
                    @{ Key='workflow_transitions'; Type='Workflow Transition'; Fields=@('name','parent','state','action','next_state','allowed','allow_self_approval','idx'); Filters=@{parent=@('in',$workflowNames.ToArray());parenttype='Workflow'}; Parent='Workflow' }
                )
            }
        }
        $report.collection_finished = $allFinished
        $directory = Split-Path -Parent ([IO.Path]::GetFullPath($OutputPath))
        if (-not [IO.Directory]::Exists($directory)) { throw 'OutputDirectoryMissing' }
        $temporary = Join-Path $directory ('.ss97-' + [Guid]::NewGuid().ToString('N') + '.tmp')
        $json = ConvertTo-Json -InputObject $report -Depth 24
        [IO.File]::WriteAllText($temporary, $json, [Text.UTF8Encoding]::new($false))
        [IO.File]::Move($temporary, [IO.Path]::GetFullPath($OutputPath), $true)
        return [pscustomobject]@{ Success=$allFinished; Stage='Metadata'; ReportWritten=$true; Path=$OutputPath; Instruction=$(if ($allFinished) {'Relire le JSON expurgé avant transmission ; ce rapport ne valide aucune autorisation métier.'} else {$admin}) }
    } catch {
        # Do not return exception text: HTTP requests, credentials and local identity may appear there.
        return [pscustomobject]@{ Success=$false; Stage='LocalOrTransportFailure'; ReportWritten=$false; Instruction=$admin }
    } finally {
        [Array]::Clear($salt,0,$salt.Length)
        if ($temporary -and [IO.File]::Exists($temporary)) { [IO.File]::Delete($temporary) }
        if ($null -ne $client) { $client.DefaultRequestHeaders.Authorization=$null; $client.Dispose() }
    }
}
Export-ModuleMember -Function Export-SS97CloudRules
