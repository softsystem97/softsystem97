#requires -Version 7.0
<#
Soft System 97 - inventaire en LECTURE SEULE des dépendances de production.
Ne crée/modifie ni ticket, ni facture, ni paiement, ni configuration.
N'affiche jamais les clés API, les secrets Stripe, les données clients ou les documents.
#>
[CmdletBinding()]
param(
    [uri]$BaseUri = [uri]"https://app.softsystem97.com"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($BaseUri.Scheme -ne "https" -or
    $BaseUri.Host -ne "app.softsystem97.com" -or
    $BaseUri.UserInfo -or $BaseUri.Query -or $BaseUri.Fragment -or
    $BaseUri.AbsolutePath -ne "/") {
    throw "Site de production inattendu : operation arretee."
}

$handler = [System.Net.Http.HttpClientHandler]::new()
$handler.AllowAutoRedirect = $false
$handler.UseCookies = $false
$handler.UseDefaultCredentials = $false
$client = [System.Net.Http.HttpClient]::new($handler)
$client.Timeout = [TimeSpan]::FromSeconds(20)

function Get-SS97Read([string]$Path) {
    $response = $null
    try {
        $response = $client.GetAsync(([uri]::new($BaseUri, $Path))).GetAwaiter().GetResult()
        $status = [int]$response.StatusCode
        $data = $null
        if ($status -eq 200) {
            $raw = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
            $data = ConvertFrom-Json -InputObject $raw -AsHashtable -Depth 32
        }
        return @{ Status = $status; Data = $data }
    } catch {
        return @{ Status = 0; Data = $null }
    } finally {
        if ($null -ne $response) { $response.Dispose() }
    }
}

function Get-SS97Meta([string]$DocType) {
    $path = "/api/v2/doctype/$([uri]::EscapeDataString($DocType))/meta"
    $response = Get-SS97Read $path
    $fields = @()
    if ($response.Status -eq 200 -and $null -ne $response.Data) {
        $meta = $response.Data["data"]
        if ($null -ne $meta -and $meta.ContainsKey("fields")) {
            $fields = @($meta["fields"])
        }
    }
    return @{ Status = $response.Status; Fields = $fields }
}

function Find-SS97Field($Meta, [string]$Name) {
    return @($Meta.Fields | Where-Object { $_["fieldname"] -eq $Name } | Select-Object -First 1)
}

try {
    Write-Host "=== SS97 : AUDIT PRODUCTION EN LECTURE SEULE ===" -ForegroundColor Cyan
    $keySecure = Read-Host "API KEY RENOUVELEE (masquee)" -AsSecureString
    $secretSecure = Read-Host "API SECRET RENOUVELE (masque)" -AsSecureString
    $key = $secret = $null
    try {
        $key = [System.Net.NetworkCredential]::new("", $keySecure).Password.Trim()
        $secret = [System.Net.NetworkCredential]::new("", $secretSecure).Password.Trim()
        if (-not $key -or -not $secret -or $key -match "[\r\n:]" -or $secret -match "[\r\n:]") {
            throw "Identifiants invalides."
        }
        $client.DefaultRequestHeaders.Authorization =
            [System.Net.Http.Headers.AuthenticationHeaderValue]::new("token", ($key + ":" + $secret))
    } finally {
        $key = $null
        $secret = $null
        $keySecure.Dispose()
        $secretSecure.Dispose()
    }

    $auth = Get-SS97Read "/api/method/frappe.auth.get_logged_user"
    if ($auth.Status -ne 200 -or $null -eq $auth.Data -or
        $auth.Data["message"] -eq "Guest" -or
        [string]::IsNullOrWhiteSpace([string]$auth.Data["message"])) {
        Write-Host "AUTHENTIFICATION REFUSEE : HTTP $($auth.Status)" -ForegroundColor Red
        return
    }
    Write-Host "Connexion : OK / utilisateur $($auth.Data['message'])" -ForegroundColor Green

    $issue = Get-SS97Meta "Issue"
    $invoice = Get-SS97Meta "Sales Invoice"
    $stripe = Get-SS97Meta "SS97 Stripe Config"
    Write-Host "Schema Issue : HTTP $($issue.Status), $(@($issue.Fields).Count) champs"
    Write-Host "Schema Sales Invoice : HTTP $($invoice.Status), $(@($invoice.Fields).Count) champs"
    Write-Host "Schema SS97 Stripe Config : HTTP $($stripe.Status), $(@($stripe.Fields).Count) champs"

    $technician = @(Find-SS97Field $issue "ss97_technician")
    $linkOK = $technician.Count -eq 1 -and
        $technician[0]["fieldtype"] -eq "Link" -and
        $technician[0]["options"] -eq "User"
    Write-Host "Lien Issue.ss97_technician vers User : $linkOK"

    $candidateFields = @()
    foreach ($entry in @(@{Name="Issue"; Other="Sales Invoice"; Meta=$issue},
                          @{Name="Sales Invoice"; Other="Issue"; Meta=$invoice})) {
        foreach ($field in $entry.Meta.Fields) {
            $n = [string]$field["fieldname"]
            $opts = [string]$field["options"]
            if ($opts -eq $entry.Other -or
                $n -match "(?i)(issue|ticket|invoice|facture|stripe)") {
                $candidateFields += "$($entry.Name).$n"
            }
        }
    }
    if ($candidateFields.Count -eq 0) {
        Write-Host "Champs candidats ticket/facture : AUCUN REPERE (relation non prouvee)" -ForegroundColor Yellow
    } else {
        Write-Host "Champs candidats ticket/facture (a confirmer) :"
        $candidateFields | Sort-Object -Unique | ForEach-Object { Write-Host (" - " + $_) }
    }

    $stripeExpected = @("test_mode", "payments_live_enabled", "live_secret_key", "webhook_secret")
    foreach ($field in $stripeExpected) {
        Write-Host "Champ Stripe $field present : $(@(Find-SS97Field $stripe $field).Count -eq 1)"
    }
    $config = Get-SS97Read "/api/resource/SS97%20Stripe%20Config/SS97%20Stripe%20Config"
    if ($config.Status -eq 200 -and $null -ne $config.Data -and $null -ne $config.Data["data"]) {
        $settings = $config.Data["data"]
        Write-Host "Stripe TEST_MODE (valeur, sans secret) : $($settings['test_mode'])"
        Write-Host "Stripe PAYMENTS_LIVE_ENABLED (valeur, sans secret) : $($settings['payments_live_enabled'])"
    } else {
        Write-Host "Stripe mode du DocType : ACCES/CONFIG INCONNU (HTTP $($config.Status))"
    }

    $ready = Get-SS97Read "/api/method/softsystem97.integrations.ticket_bridge.readiness.get_readiness"
    Write-Host "API readiness installee et accessible : HTTP $($ready.Status)"
    if ($ready.Status -eq 200 -and $null -ne $ready.Data -and $null -ne $ready.Data["message"]) {
        $status = $ready.Data["message"]
        Write-Host "Etat readiness : $($status['state'])"
        Write-Host "Bloquants : $(@($status['blockers']) -join ', ')"
    }

    Write-Host "=== AUDIT TERMINE : AUCUNE ECRITURE EFFECTUEE ===" -ForegroundColor Green
    Write-Host "Aucune autorisation d'intervention ni paiement LIVE n'a ete active."
} finally {
    $client.DefaultRequestHeaders.Authorization = $null
    $client.Dispose()
    $handler.Dispose()
}
