# Regenerate a fix-loop run (before or after) from raw captures.
#   git checkout fixloop-before ; .\reproduction\fixloop.ps1 -Label before
#   git checkout fixloop-after  ; .\reproduction\fixloop.ps1 -Label after
# Captures are expected one level above the repo (property project\...) or pass -CaptureRoot.
param([Parameter(Mandatory = $true)][string]$Label,
      [string]$CaptureRoot = "")
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Split-Path $here -Parent)
if (-not $CaptureRoot) { $CaptureRoot = (Resolve-Path "..").Path }
$exe = ".\.venv\Scripts\roomscan.exe"
$A = Join-Path $CaptureRoot "single_scan_with_ceiling\c7d28f72c6"
$B = Join-Path $CaptureRoot "single_scan_floor_only\1a8384c3f6"
$o = "fixloop\$Label"
New-Item -ItemType Directory -Force $o | Out-Null
& $exe run $A --out "$o\with_ceiling"
& $exe run $B --out "$o\floor_only"
& $exe repeat $A $B --plan-a "$o\with_ceiling\plan.json" --plan-b "$o\floor_only\plan.json" --out "$o\repeatability_lidar.md"
