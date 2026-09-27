param(
    [string]$RequestPath,
    [switch]$Probe,
    [switch]$Fonts
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
try {
    if ($Fonts) {
        Add-Type -AssemblyName System.Drawing
        $collection = New-Object System.Drawing.Text.InstalledFontCollection
        try { @($collection.Families | ForEach-Object { $_.Name } | Sort-Object -Unique) | ConvertTo-Json }
        finally { $collection.Dispose() }
        exit 0
    }
    $powerPointType = [type]::GetTypeFromProgID('PowerPoint.Application')
    if ($null -eq $powerPointType) { throw 'Desktop PowerPoint COM registration was not found.' }
    if ($Probe) {
        Write-Output '{"ready":true,"check":"COM registration only; export not yet verified"}'
        exit 0
    }
    # Do not attach to or terminate an existing user session.
    if (Get-Process -Name POWERPNT -ErrorAction SilentlyContinue) {
        throw 'PowerPoint is already running. Save and close it yourself before export, or select another renderer.'
    }
    $request = Get-Content -LiteralPath $RequestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $app = $null
    $presentation = $null
    try {
        $app = New-Object -ComObject PowerPoint.Application
        # A session could have appeared after the process check. Never close it.
        if ($app.Presentations.Count -ne 0) { throw 'An existing PowerPoint presentation was detected; export cancelled.' }
        $previousSecurity = $app.AutomationSecurity
        try {
            $app.AutomationSecurity = 3 # msoAutomationSecurityForceDisable
            # ReadOnly=true, Untitled=false, WithWindow=false. Input is a generated local PPTX.
            $presentation = $app.Presentations.Open([string]$request.pptx, -1, 0, 0)
        } finally {
            $app.AutomationSecurity = $previousSecurity
        }
        if ($presentation.Slides.Count -ne [int]$request.count) { throw 'Slide count mismatch.' }
        for ($index = 1; $index -le $presentation.Slides.Count; $index++) {
            $slide = $presentation.Slides.Item($index)
            try {
                $png = Join-Path $request.preview ('slide-{0:D2}.png' -f $index)
                $slide.Export($png, 'PNG', [int]$request.width, [int]$request.height)
            } finally {
                [void][Runtime.InteropServices.Marshal]::ReleaseComObject($slide)
            }
        }
        if ($request.pdf) {
            # SaveAs has a simpler COM signature than ExportAsFixedFormat. Supply
            # every argument explicitly: ppSaveAsPDF=32, msoFalse=0. Only the
            # generated read-only candidate is open; never save over its PPTX.
            # https://learn.microsoft.com/office/vba/api/powerpoint.presentation.saveas
            try { $presentation.SaveAs([string]$request.pdf, [int]32, [int]0) }
            catch { throw ('PDF_EXPORT_FAILED: ' + $_.Exception.Message) }
        }
    } finally {
        if ($null -ne $presentation) {
            try { $presentation.Close() } finally {
                [void][Runtime.InteropServices.Marshal]::ReleaseComObject($presentation)
            }
        }
        if ($null -ne $app) {
            # Never call Quit or kill POWERPNT: the user may have opened a file meanwhile.
            [void][Runtime.InteropServices.Marshal]::ReleaseComObject($app)
        }
        [GC]::Collect()
        [GC]::WaitForPendingFinalizers()
    }
    Write-Output '{"exported":true}'
} catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 2
}
