param([switch]$Force)

$ErrorActionPreference = 'Stop'

$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$repositoryRoot = Split-Path -Parent $scriptDirectory
$outputDirectory = Join-Path $repositoryRoot 'lab1\use-cases'
$htmlPath = Join-Path $outputDirectory 'use-case-descriptions.html'
$pdfPath = Join-Path $outputDirectory 'use-case-descriptions.pdf'

if (-not (Test-Path -LiteralPath $outputDirectory -PathType Container)) {
    throw "Use-case output directory does not exist: $outputDirectory"
}

$outputPaths = @($htmlPath, $pdfPath)
foreach ($outputPath in $outputPaths) {
    if (Test-Path -LiteralPath $outputPath) {
        if (-not $Force) {
            throw "Output already exists. Re-run with -Force to regenerate it: $outputPath"
        }
        $resolvedOutputPath = (Resolve-Path -LiteralPath $outputPath).Path
        if ((Split-Path -Parent $resolvedOutputPath) -ne $outputDirectory) {
            throw "Refusing to replace output outside the intended directory: $resolvedOutputPath"
        }
        Remove-Item -LiteralPath $resolvedOutputPath -Force
    }
}

function Join-NumberedItems {
    param([string[]]$Items)

    $numbered = for ($index = 0; $index -lt $Items.Count; $index++) {
        "$($index + 1). $($Items[$index])"
    }
    return $numbered -join "`r"
}

function Join-Courses {
    param([object[]]$Courses)

    $parts = foreach ($course in $Courses) {
        $steps = Join-NumberedItems -Items $course.Steps
        "$($course.Id) - $($course.Name)`r$steps"
    }
    return $parts -join "`r`r"
}

$uc01Fields = [ordered]@{
    'Use Case ID' = 'UC-01'
    'Use Case Name' = 'Request Carpark Recommendation'
    'Created By' = 'Nestor'
    'Last Updated By' = 'Nestor'
    'Date Created' = '30 August 2026'
    'Date Last Updated' = '30 August 2026'
    'Actor' = 'Anonymous Driver; Parking Data Provider; Destination, Map and Routing Provider'
    'Description' = 'The driver requests ranked carpark recommendations near a destination. ParkChoiceSG applies one fixed Best Overall scoring model using current parking availability, estimated parking cost, and walking distance, then explains why each result is recommended.'
    'Preconditions' = Join-NumberedItems @(
        'ParkChoiceSG is running.'
        'The driver can access the carpark recommendation interface.'
    )
    'Postconditions' = Join-NumberedItems @(
        'On success, the driver receives an explained, time-labelled list of up to five recommendations.'
        'On failure, the driver receives a clear message that no reliable recommendation can be produced.'
        'No account or profile is created.'
    )
    'Priority' = 'Must Have'
    'Frequency of Use' = 'High - normally once per parking search or journey.'
    'Flow of Events' = Join-NumberedItems @(
        'The driver opens the carpark recommendation function.'
        'The driver enters a destination and intended parking duration, then submits the request.'
        'ParkChoiceSG validates the inputs and resolves the destination to a location.'
        'ParkChoiceSG identifies supported nearby carparks and obtains their latest reported availability, published parking rates, and walking-route measurements to the destination.'
        'ParkChoiceSG verifies that each candidate has sufficiently current and comparable evidence. It labels every retained availability value as "Current reported availability" and shows its source timestamp.'
        'ParkChoiceSG estimates the parking cost for the entered duration, calculates each candidate''s fixed Best Overall score using current availability, estimated cost, and walking distance, and ranks the candidates.'
        'ParkChoiceSG presents the highest-ranked carpark as the Best Overall recommendation, followed by up to four alternatives. Each result shows its raw factor values, timestamp, relevant warnings, and a concise explanation of its ranking.'
    )
    'Alternative Flows' = Join-Courses @(
        [pscustomobject]@{ Id = 'UC-01.AC.1'; Name = 'Invalid destination or duration'; Steps = @('At Step 3, ParkChoiceSG identifies an invalid or unsupported input.', 'ParkChoiceSG explains which input must be corrected.', 'The use case resumes at Step 2.') }
        [pscustomobject]@{ Id = 'UC-01.AC.2'; Name = 'Destination cannot be resolved'; Steps = @('At Step 3, the destination provider cannot resolve the entered destination unambiguously.', 'ParkChoiceSG asks the driver to refine the destination or select a suggested match.', 'The use case resumes at Step 2 or Step 3 after the driver responds.') }
        [pscustomobject]@{ Id = 'UC-01.AC.3'; Name = 'Some external data is unavailable'; Steps = @('At Step 4, one provider or part of its data is unavailable.', 'ParkChoiceSG continues only with carparks that still have the current availability, verified rate information, and walking-route measurement required for the fixed comparison.', 'ParkChoiceSG displays a warning that some carparks could not be assessed because data was unavailable.', 'The use case resumes at Step 5.') }
        [pscustomobject]@{ Id = 'UC-01.AC.4'; Name = 'A carpark has missing, stale, or incomparable evidence'; Steps = @('At Step 5, ParkChoiceSG detects that a carpark lacks the minimum evidence required for a fair comparison.', 'ParkChoiceSG excludes that carpark instead of inventing or silently substituting a value.', 'The use case resumes at Step 5 with the remaining candidates.') }
        [pscustomobject]@{ Id = 'UC-01.AC.5'; Name = 'Fewer than five suitable carparks are available'; Steps = @('At Step 7, fewer than five carparks satisfy the evidence and eligibility rules.', 'ParkChoiceSG displays every suitable result and states that no additional comparable carparks were found.') }
        [pscustomobject]@{ Id = 'UC-01.AC.6'; Name = 'No suitable carpark can be recommended'; Steps = @('At Step 5, no candidate has enough current and comparable evidence for the fixed scoring model.', 'ParkChoiceSG explains why a reliable ranking cannot be produced and suggests changing the destination or duration, or retrying later.', 'The use case ends without a recommendation.') }
        [pscustomobject]@{ Id = 'UC-01.AC.7'; Name = 'Driver selects a result'; Steps = @('After Step 7, the driver selects a recommended carpark.', 'ParkChoiceSG starts UC-02 for the selected carpark.') }
    )
    'Exceptions' = Join-Courses @(
        [pscustomobject]@{ Id = 'UC-01.EX.1'; Name = 'All required data sources are unavailable'; Steps = @('ParkChoiceSG cannot obtain enough current evidence to produce a responsible recommendation.', 'ParkChoiceSG informs the driver that recommendations are temporarily unavailable and invites the driver to retry later.', 'The use case ends without a recommendation.') }
        [pscustomobject]@{ Id = 'UC-01.EX.2'; Name = 'Unexpected system error'; Steps = @('ParkChoiceSG records the error without exposing credentials or sensitive technical details.', 'ParkChoiceSG informs the driver that the request could not be completed and provides a retry option.', 'The use case ends.') }
    )
    'Includes' = 'None.'
    'Special Requirements' = Join-NumberedItems @(
        'When every required external dependency responds within one second, at least 95% of recommendation requests should be displayed within three seconds.'
        'Every availability value must be labelled "Current reported availability" and accompanied by its source timestamp.'
        'Every ranked result must show the availability, estimated cost, and walking distance used in its fixed Best Overall score, together with a concise reason for its position.'
        'Missing or stale factor data must not be replaced with an invented value or presented as current.'
        'Partial provider failure must be visible to the driver.'
        'The core recommendation flow must not require an account, profile, origin, or device-location permission.'
        'API credentials and provider tokens must not be embedded in the client application or exposed in user-facing errors.'
        'A first-time driver should be able to submit a search using three required actions: enter a destination, enter a duration, and request recommendations.'
    )
    'Assumptions' = Join-NumberedItems @(
        'The driver is searching for an ordinary passenger-car parking space.'
        'The driver uses ParkChoiceSG only while stationary or through a passenger.'
        'Parking availability and rate data come from authorised sources and may change after retrieval.'
        'Estimated cost is based on verified published rate information and the entered duration; it is not a payment quotation or guarantee.'
        'Current availability does not guarantee that a lot will remain available when the driver arrives.'
        'Turn-by-turn navigation is handed off to an external navigation service.'
        'The scoring weights, normalisation rules, and tie-breaker are defined consistently in the project''s scoring requirements and tests.'
    )
    'Notes and Issues' = 'None.'
}

$uc02Fields = [ordered]@{
    'Use Case ID' = 'UC-02'
    'Use Case Name' = 'Inspect Carpark Information'
    'Created By' = 'Nestor'
    'Last Updated By' = 'Nestor'
    'Date Created' = '30 August 2026'
    'Date Last Updated' = '30 August 2026'
    'Actor' = 'Anonymous Driver'
    'Description' = 'The driver selects a recommended carpark and inspects the information and evidence used to assess it.'
    'Preconditions' = Join-NumberedItems @('UC-01 has produced at least one carpark recommendation.')
    'Postconditions' = Join-NumberedItems @('The selected carpark''s information is displayed.', 'The recommendation results remain unchanged.', 'No account or profile is created.')
    'Priority' = 'Must Have'
    'Frequency of Use' = 'High - normally after a recommendation request.'
    'Flow of Events' = Join-NumberedItems @(
        'The driver selects a carpark from the recommendation results.'
        'ParkChoiceSG opens the information view for the selected carpark.'
        'ParkChoiceSG displays the carpark''s name, address, current reported availability and timestamp, estimated cost for the entered duration, and walking distance to the destination.'
        'ParkChoiceSG displays the carpark''s Best Overall ranking explanation and any relevant data warnings.'
        'ParkChoiceSG provides an option to open external navigation to the carpark.'
    )
    'Alternative Flows' = Join-Courses @(
        [pscustomobject]@{ Id = 'UC-02.AC.1'; Name = 'Selected carpark information is no longer available'; Steps = @('At Step 2, ParkChoiceSG cannot retrieve the selected result from the active recommendation.', 'ParkChoiceSG explains that the information is no longer available.', 'ParkChoiceSG returns the driver to the current recommendation results.') }
        [pscustomobject]@{ Id = 'UC-02.AC.2'; Name = 'Some displayed information is no longer current'; Steps = @('At Step 3, ParkChoiceSG detects that previously retrieved information no longer satisfies the freshness rule.', 'ParkChoiceSG marks the affected information as unavailable or outdated rather than presenting it as current.', 'ParkChoiceSG advises the driver to refresh the recommendation before relying on the result.', 'The use case resumes at Step 4 with the remaining information.') }
        [pscustomobject]@{ Id = 'UC-02.AC.3'; Name = 'Driver requests navigation'; Steps = @('After Step 5, the driver selects the external-navigation option.', 'ParkChoiceSG starts UC-03.') }
    )
    'Exceptions' = Join-Courses @(
        [pscustomobject]@{ Id = 'UC-02.EX.1'; Name = 'Unexpected system error'; Steps = @('ParkChoiceSG records the error without exposing sensitive technical details.', 'ParkChoiceSG informs the driver that the carpark information could not be displayed.', 'ParkChoiceSG provides an option to return to the recommendation results.', 'The use case ends.') }
    )
    'Includes' = 'None.'
    'Special Requirements' = Join-NumberedItems @(
        'Information displayed in UC-02 must use the same values, units, labels, and timestamps as the corresponding UC-01 result.'
        'Availability must be labelled "Current reported availability" and must not be represented as a guaranteed parking space.'
        'The ranking explanation must identify the availability, estimated cost, and walking distance considered by the fixed Best Overall score.'
        'When the information is already available from the recommendation result, the information view should appear within one second for at least 95% of selections on a supported device.'
        'Inspecting a carpark must not require an account, profile, origin, or device-location permission.'
    )
    'Assumptions' = Join-NumberedItems @(
        'The selected carpark belongs to the active recommendation result set.'
        'Estimated cost and walking distance retain the parking duration and destination used in UC-01.'
        'Parking information may change after it is retrieved.'
    )
    'Notes and Issues' = 'None.'
}

$uc03Fields = [ordered]@{
    'Use Case ID' = 'UC-03'
    'Use Case Name' = 'Open External Navigation'
    'Created By' = 'Nestor'
    'Last Updated By' = 'Nestor'
    'Date Created' = '30 August 2026'
    'Date Last Updated' = '30 August 2026'
    'Actor' = 'Anonymous Driver; Destination, Map and Routing Provider; Device Operating System'
    'Description' = 'The driver requests directions to a selected carpark, and ParkChoiceSG hands the carpark destination to an external navigation service.'
    'Preconditions' = Join-NumberedItems @('UC-02 is displaying a selected carpark.')
    'Postconditions' = Join-NumberedItems @('On success, an external navigation service opens with the selected carpark as its destination.', 'On failure, the driver remains in ParkChoiceSG and receives a clear alternative.')
    'Priority' = 'Must Have'
    'Frequency of Use' = 'Medium - when a driver decides to travel to a recommended carpark.'
    'Flow of Events' = Join-NumberedItems @(
        'The driver selects the option to navigate to the displayed carpark.'
        'ParkChoiceSG obtains the selected carpark''s verified name and destination coordinates.'
        'ParkChoiceSG sends the destination to a supported external navigation service through the device operating system.'
        'The external navigation service opens and displays a route to the selected carpark.'
        'ParkChoiceSG completes the handoff without providing turn-by-turn navigation itself.'
    )
    'Alternative Flows' = Join-Courses @(
        [pscustomobject]@{ Id = 'UC-03.AC.1'; Name = 'More than one navigation service is available'; Steps = @('At Step 3, the device operating system asks the driver to select a supported navigation service.', 'The driver selects a service.', 'The use case resumes at Step 4.') }
        [pscustomobject]@{ Id = 'UC-03.AC.2'; Name = 'No supported navigation application is available'; Steps = @('At Step 3, the device cannot open a supported navigation application.', 'ParkChoiceSG keeps the carpark information visible and provides the carpark name, address, and coordinates for manual use.', 'The use case ends without opening navigation.') }
        [pscustomobject]@{ Id = 'UC-03.AC.3'; Name = 'External navigation service cannot calculate a route'; Steps = @('At Step 4, the external navigation service cannot produce a route.', 'The external service informs the driver according to its own failure behaviour.', 'ParkChoiceSG remains responsible only for having supplied the correct selected destination.', 'The use case ends.') }
    )
    'Exceptions' = Join-Courses @(
        [pscustomobject]@{ Id = 'UC-03.EX.1'; Name = 'Selected destination is invalid or unavailable'; Steps = @('At Step 2, ParkChoiceSG detects missing or invalid destination coordinates.', 'ParkChoiceSG does not launch the external navigation service.', 'ParkChoiceSG explains that navigation cannot be opened for this carpark and keeps its information visible.', 'The use case ends.') }
        [pscustomobject]@{ Id = 'UC-03.EX.2'; Name = 'Unexpected handoff error'; Steps = @('ParkChoiceSG records the error without exposing sensitive technical details.', 'ParkChoiceSG informs the driver that navigation could not be opened and keeps the carpark information visible.', 'The use case ends.') }
    )
    'Includes' = 'None.'
    'Special Requirements' = Join-NumberedItems @(
        'ParkChoiceSG must send only the selected carpark''s name and destination coordinates required for the handoff.'
        'ParkChoiceSG must not require or collect the driver''s origin or device location for the handoff. The external navigation service manages any origin or location permission under its own controls.'
        'The external application launch should begin within two seconds for at least 95% of requests on a supported device, excluding time spent inside the external service.'
        'A handoff failure must not close the carpark information view or remove the selected result.'
        'ParkChoiceSG must clearly indicate that navigation is provided by an external service.'
    )
    'Assumptions' = Join-NumberedItems @(
        'The device operating system supports external application links or intents.'
        'At least one suitable external navigation service may be installed or accessible through a web browser.'
        'ParkChoiceSG does not control route availability, traffic information, navigation accuracy, or permissions requested by the external service.'
    )
    'Notes and Issues' = 'None.'
}

$useCases = @(
    [pscustomobject]@{ Id = 'UC-01'; Name = 'Request Carpark Recommendation'; Fields = $uc01Fields }
    [pscustomobject]@{ Id = 'UC-02'; Name = 'Inspect Carpark Information'; Fields = $uc02Fields }
    [pscustomobject]@{ Id = 'UC-03'; Name = 'Open External Navigation'; Fields = $uc03Fields }
)

function ConvertTo-HtmlFragment {
    param([string]$Text)

    $encoded = [System.Net.WebUtility]::HtmlEncode($Text)
    return $encoded -replace "(`r`n|`r|`n)", '<br />'
}

$html = [System.Text.StringBuilder]::new()
[void]$html.AppendLine(@'
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<title>ParkChoiceSG Use Case Descriptions</title>
<style>
@page { size: A4; margin: 2.2cm; }
body { color: #202124; font-family: Aptos, Arial, sans-serif; font-size: 10pt; line-height: 1.28; }
.cover { page-break-after: always; padding-top: 5.5cm; text-align: center; }
.cover h1 { font-size: 26pt; margin: 0; }
.cover h2 { font-size: 20pt; margin: 0.3cm 0 1.2cm; }
.cover p { font-size: 12pt; margin: 0.15cm 0; }
.use-case { page-break-before: always; }
h1 { color: #17365d; font-size: 18pt; margin: 0 0 0.4cm; }
h2 { color: #17365d; font-size: 15pt; margin: 0 0 0.4cm; }
table { border-collapse: collapse; margin-bottom: 0.4cm; width: 100%; }
th, td { border: 1px solid #707070; padding: 0.17cm 0.2cm; text-align: left; vertical-align: top; }
th { background: #d9eaf7; font-weight: 700; }
td.label { background: #eaf2f8; font-weight: 700; width: 24%; }
</style>
</head>
<body>
<section class="cover">
<h1>Use Cases</h1>
<h2>for ParkChoiceSG</h2>
<p>Version 1.0</p>
<p>&nbsp;</p>
<p>Prepared by ParkChoiceSG Team</p>
<p>Nanyang Technological University</p>
<p>SC2006 Software Engineering</p>
<p>30 August 2026</p>
</section>
<section class="revision">
<h1>Revision History</h1>
<table>
<tr><th>Name</th><th>Date</th><th>Reason for Changes</th><th>Version</th></tr>
<tr><td>Nestor</td><td>30 August 2026</td><td>Initial Lab 1 use-case model</td><td>1.0</td></tr>
</table>
</section>
'@)

foreach ($useCase in $useCases) {
    $useCaseId = ConvertTo-HtmlFragment -Text $useCase.Id
    $useCaseName = ConvertTo-HtmlFragment -Text $useCase.Name
    [void]$html.AppendLine('<section class="use-case">')
    [void]$html.AppendLine("<h1>$useCaseId - $useCaseName</h1>")
    [void]$html.AppendLine('<table>')
    foreach ($entry in $useCase.Fields.GetEnumerator()) {
        $label = ConvertTo-HtmlFragment -Text ([string]$entry.Key)
        $value = ConvertTo-HtmlFragment -Text ([string]$entry.Value)
        [void]$html.AppendLine("<tr><td class=`"label`">$label</td><td>$value</td></tr>")
    }
    [void]$html.AppendLine('</table>')
    [void]$html.AppendLine('</section>')
}

[void]$html.AppendLine('</body></html>')
[System.IO.File]::WriteAllText($htmlPath, $html.ToString(), [System.Text.UTF8Encoding]::new($false))

$browserCandidates = @(
    'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
    'C:\Program Files\Microsoft\Edge\Application\msedge.exe'
    'C:\Program Files\Google\Chrome\Application\chrome.exe'
    'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe'
)
$browserPath = $browserCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $browserPath) {
    throw 'No supported Chromium browser was found for PDF rendering.'
}

$temporaryRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
$profileName = "parkchoicesg-print-profile-$([guid]::NewGuid().ToString('N'))"
$profilePath = Join-Path $temporaryRoot $profileName
[void](New-Item -ItemType Directory -Path $profilePath)

try {
    $htmlUri = ([System.Uri]$htmlPath).AbsoluteUri
    $arguments = @(
        '--headless=new'
        '--disable-gpu'
        '--disable-extensions'
        '--no-first-run'
        '--no-pdf-header-footer'
        "--user-data-dir=`"$profilePath`""
        "--print-to-pdf=`"$pdfPath`""
        $htmlUri
    )
    $browserProcess = Start-Process -FilePath $browserPath -ArgumentList $arguments -Wait -PassThru -WindowStyle Hidden
    if ($browserProcess.ExitCode -ne 0) {
        throw "Browser PDF export failed with exit code $($browserProcess.ExitCode)."
    }
}
finally {
    if (Test-Path -LiteralPath $profilePath) {
        $resolvedProfilePath = (Resolve-Path -LiteralPath $profilePath).Path
        if (-not $resolvedProfilePath.StartsWith($temporaryRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
            (Split-Path -Leaf $resolvedProfilePath) -notlike 'parkchoicesg-print-profile-*') {
            throw "Refusing to remove unexpected browser profile path: $resolvedProfilePath"
        }
        Remove-Item -LiteralPath $resolvedProfilePath -Recurse -Force
    }
}

if (-not (Test-Path -LiteralPath $pdfPath -PathType Leaf)) {
    throw "PDF output was not created: $pdfPath"
}

Get-Item -LiteralPath $htmlPath, $pdfPath | Select-Object FullName, Length, LastWriteTime
