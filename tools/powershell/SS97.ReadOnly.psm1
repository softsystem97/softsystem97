#requires -Version 7.0
Set-StrictMode -Version Latest

function New-SS97Client {
    $handler = [System.Net.Http.HttpClientHandler]::new()
    $handler.AllowAutoRedirect = $false
    $handler.UseCookies = $false
    $handler.UseDefaultCredentials = $false
    $client = [System.Net.Http.HttpClient]::new($handler)
    $client.Timeout = [TimeSpan]::FromSeconds(20)
    return $client
}

function Set-SS97Authorization($Client) {
    # Plaintext is needed only in process memory to construct the HTTPS header.
    $keySecure = Read-Host 'API Key (saisie masquée)' -AsSecureString
    $secretSecure = Read-Host 'API Secret (saisie masquée)' -AsSecureString
    $key = $secret = $null
    try {
        $key = [System.Net.NetworkCredential]::new('', $keySecure).Password
        $secret = [System.Net.NetworkCredential]::new('', $secretSecure).Password
        if ([string]::IsNullOrWhiteSpace($key) -or [string]::IsNullOrWhiteSpace($secret) -or
            $key -match '[\r\n:]' -or $secret -match '[\r\n:]') { throw 'InvalidCredentialInput' }
        $Client.DefaultRequestHeaders.Authorization =
            [System.Net.Http.Headers.AuthenticationHeaderValue]::new('token', ($key + ':' + $secret))
    } finally {
        $key = $secret = $null
        $keySecure.Dispose()
        $secretSecure.Dispose()
    }
}

function Invoke-SS97Read($Client, [string]$Uri) {
    $response = $null
    try {
        $response = $Client.GetAsync($Uri).GetAwaiter().GetResult()
        $status = [int]$response.StatusCode
        $payload = $null
        if ($status -ge 200 -and $status -lt 300) {
            try {
                $text = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
                $payload = ConvertFrom-Json -InputObject $text -AsHashtable -Depth 32 -ErrorAction Stop
            } catch { $payload = $null }
        }
        return @{ Status = $status; Payload = $payload }
    } catch {
        # Exception/request/response bodies can contain private data. Never return them.
        return @{ Status = 0; Payload = $null }
    } finally {
        if ($null -ne $response) { $response.Dispose() }
    }
}

function Get-SS97ResourcePath([string]$DocType, $Filters, [int]$Limit) {
    $fields = [Uri]::EscapeDataString('["name"]')
    $filterText = [Uri]::EscapeDataString((ConvertTo-Json -InputObject $Filters -Compress -Depth 8))
    return '/api/resource/' + [Uri]::EscapeDataString($DocType) +
        '?fields=' + $fields + '&limit_page_length=' + $Limit + '&filters=' + $filterText
}

function Invoke-SS97Check {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][ValidateSet('API','Tickets','Technicien','Diagnostic')][string]$Kind,
        [Parameter(Mandatory)][Uri]$BaseUri,
        [string]$TicketDocType,
        [ValidateRange(1,100)][int]$Limit = 20,
        [string]$ExpectedDeniedTicketName
    )
    $client = $null
    try {
        if ($BaseUri.Scheme -ne 'https' -or $BaseUri.UserInfo -or $BaseUri.Query -or
            $BaseUri.Fragment -or $BaseUri.AbsolutePath -ne '/') { throw 'InvalidOrigin' }
        if ($Kind -in @('Tickets','Technicien') -and [string]::IsNullOrWhiteSpace($TicketDocType)) {
            throw 'ConfirmedTicketDocTypeRequired'
        }
        $origin = $BaseUri.GetLeftPart([UriPartial]::Authority)
        $client = New-SS97Client
        if ($Kind -eq 'Diagnostic') {
            # Deliberately anonymous; no private content is displayed, and no login is attempted.
            foreach ($path in @('/api/method/ping', '/api/method/frappe.auth.get_logged_user')) {
                $read = Invoke-SS97Read $client ($origin + $path)
                [pscustomobject]@{ Check = 'Diagnostic'; Endpoint = $path; HttpStatus = $read.Status }
            }
            return
        }
        Set-SS97Authorization $client
        $auth = Invoke-SS97Read $client ($origin + '/api/method/frappe.auth.get_logged_user')
        if ($auth.Status -ne 200 -or $null -eq $auth.Payload -or
            -not $auth.Payload.ContainsKey('message') -or
            $auth.Payload.message -isnot [string] -or
            [string]::IsNullOrWhiteSpace($auth.Payload.message) -or $auth.Payload.message -eq 'Guest') {
            return [pscustomobject]@{ Check = $Kind; Success = $false; Stage = 'Authentication'; HttpStatus = $auth.Status }
        }
        if ($Kind -eq 'API') {
            return [pscustomobject]@{ Check = 'API'; Success = $true; HttpStatus = 200 }
        }
        if ($Kind -eq 'Tickets') {
            $path = Get-SS97ResourcePath $TicketDocType @() $Limit
            $read = Invoke-SS97Read $client ($origin + $path)
            $ok = $read.Status -eq 200 -and $null -ne $read.Payload -and $read.Payload.data -is [array]
            $count = if ($ok) { @($read.Payload.data).Count } else { 0 }
            return [pscustomobject]@{ Check = 'Tickets'; Success = $ok; HttpStatus = $read.Status;
                AccessibleCount = $count; Limit = $Limit; CompleteWorkflowValidated = $false }
        }
        # Native assignment baseline only; the custom active-technician profile/API is unknown.
        $filters = @(@('allocated_to','=',$auth.Payload.message), @('reference_type','=',$TicketDocType),
                     @('status','=','Open'))
        $encoded = [Uri]::EscapeDataString((ConvertTo-Json -InputObject $filters -Compress -Depth 8))
        $path = '/api/resource/ToDo?fields=%5B%22reference_name%22%5D&limit_page_length=' + $Limit + '&filters=' + $encoded
        $assigned = Invoke-SS97Read $client ($origin + $path)
        if ($assigned.Status -ne 200 -or $null -eq $assigned.Payload -or $assigned.Payload.data -isnot [array]) {
            return [pscustomobject]@{ Check='Technicien'; Success=$false; Stage='NativeAssignments'; HttpStatus=$assigned.Status }
        }
        $accessible = 0
        foreach ($row in $assigned.Payload.data) {
            if (-not $row.ContainsKey('reference_name') -or -not $row.reference_name) { throw 'InvalidAssignmentResponse' }
            $filter = ,@('name','=',$row.reference_name)
            $read = Invoke-SS97Read $client ($origin + (Get-SS97ResourcePath $TicketDocType $filter 1))
            if ($read.Status -eq 200 -and $null -ne $read.Payload -and $read.Payload.data -is [array] -and
                @($read.Payload.data).Count -eq 1 -and $read.Payload.data[0].name -eq $row.reference_name) { $accessible++ }
        }
        $denied = $null
        if ($ExpectedDeniedTicketName) {
            $filter = ,@('name','=',$ExpectedDeniedTicketName)
            $read = Invoke-SS97Read $client ($origin + (Get-SS97ResourcePath $TicketDocType $filter 1))
            $denied = $read.Status -in @(401,403) -or ($read.Status -eq 200 -and
                $null -ne $read.Payload -and $read.Payload.data -is [array] -and @($read.Payload.data).Count -eq 0)
        }
        [pscustomobject]@{ Check='Technicien'; Success=(@($assigned.Payload.data).Count -gt 0 -and $accessible -eq @($assigned.Payload.data).Count -and $denied -ne $false);
            AssignedCount=@($assigned.Payload.data).Count; AccessibleAssignedCount=$accessible;
            ExpectedDenialObserved=$denied; CustomTechnicianProfileValidated=$false; Limit=$Limit }
    } catch {
        [pscustomobject]@{ Check=$Kind; Success=$false; Stage='InputOrTransport'; HttpStatus=0 }
    } finally {
        if ($null -ne $client) {
            $client.DefaultRequestHeaders.Authorization = $null
            $client.Dispose()
        }
    }
}
Export-ModuleMember -Function Invoke-SS97Check
