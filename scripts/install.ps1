# install.ps1 — install the space-ocr skill into Claude Code or Cursor (Windows).
#
# Usage:
#   .\install.ps1                  # interactive, asks which target
#   .\install.ps1 -Target claude   # install for Claude Code only
#   .\install.ps1 -Target cursor   # install for Cursor only
#   .\install.ps1 -Target both     # install for both
#
# IRM-piped usage:
#   iwr -useb <raw-url>/scripts/install.ps1 | iex
#   (interactive prompt will appear)

[CmdletBinding()]
param(
    [ValidateSet('claude','cursor','both','')]
    [string]$Target = ''
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$repo = 'oisidonut/claude-space-ocr-skill'
$zipUrl = "https://github.com/$repo/archive/refs/heads/main.zip"

if (-not $Target) {
    Write-Host 'Install space-ocr skill - pick a target:'
    Write-Host '  1) Claude Code  (%USERPROFILE%\.claude\skills\)'
    Write-Host '  2) Cursor       (%USERPROFILE%\.cursor\skills\)'
    Write-Host '  3) Both'
    $choice = Read-Host 'Choice [1/2/3]'
    switch ($choice) {
        '1' { $Target = 'claude' }
        '2' { $Target = 'cursor' }
        '3' { $Target = 'both' }
        default { Write-Error 'Cancelled.'; exit 1 }
    }
}

$tmp = Join-Path $env:TEMP ("space-ocr-install-" + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tmp | Out-Null

try {
    $zipPath = Join-Path $tmp 'src.zip'
    Write-Host "Downloading skill from $repo..."
    Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath -UseBasicParsing
    Expand-Archive -Path $zipPath -DestinationPath $tmp -Force

    $srcSkill = Get-ChildItem -Path $tmp -Recurse -Directory `
        | Where-Object { $_.Name -eq 'space-ocr' -and $_.FullName -like '*\skills\space-ocr' } `
        | Select-Object -First 1

    if (-not $srcSkill) {
        Write-Error 'Could not locate skills\space-ocr in the downloaded archive.'
        exit 3
    }

    function Install-To {
        param([string]$DestRoot, [string]$Label)
        $dest = Join-Path $DestRoot 'space-ocr'
        if (-not (Test-Path $DestRoot)) {
            New-Item -ItemType Directory -Path $DestRoot -Force | Out-Null
        }
        if (Test-Path $dest) {
            $backup = "$dest.bak.$([DateTimeOffset]::Now.ToUnixTimeSeconds())"
            Write-Host "Existing install found - backing up to: $backup"
            Move-Item -Path $dest -Destination $backup
        }
        Copy-Item -Path $srcSkill.FullName -Destination $dest -Recurse
        Write-Host "Installed for $Label`: $dest"
    }

    if ($Target -in @('claude','both')) {
        Install-To -DestRoot (Join-Path $env:USERPROFILE '.claude\skills') -Label 'Claude Code'
    }
    if ($Target -in @('cursor','both')) {
        Install-To -DestRoot (Join-Path $env:USERPROFILE '.cursor\skills') -Label 'Cursor'
    }

    Write-Host ''
    Write-Host 'Done. Set your API key next:'
    Write-Host '  $env:SPACE_OCR_API_KEY = "spocr_..."'
    Write-Host 'Get one at https://space-ocr.com (100 free scans, no card).'
}
finally {
    Remove-Item -Path $tmp -Recurse -Force -ErrorAction SilentlyContinue
}
