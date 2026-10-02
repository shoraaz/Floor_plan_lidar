# Run every tier on every sample capture (LiDAR, video from rgb.mp4, photo folders made by scripts/make_photo_folders.py).
$ErrorActionPreference = "Continue"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Split-Path $here -Parent)
$env:PYTHONIOENCODING = "utf-8"
$exe = ".\.venv\Scripts\roomscan.exe"
$root = (Resolve-Path "..").Path
$caps = [ordered]@{
  "single_room"  = "single_room\c00a170fe1"
  "with_ceiling" = "single_scan_with_ceiling\c7d28f72c6"
  "floor_only"   = "single_scan_floor_only\1a8384c3f6"
}
$tiers = if ($args.Count -gt 0) { $args } else { @("lidar", "video", "photo") }
New-Item -ItemType Directory -Force out\bench | Out-Null
foreach ($t in $tiers) {
  foreach ($k in $caps.Keys) {
    $src = Join-Path $root $caps[$k]
    if ($t -eq "photo") { $src = "benchmark\photos\$k" ; if (-not (Test-Path $src)) { continue } }
    $sw = [Diagnostics.Stopwatch]::StartNew()
    & $exe run $src --tier $t --out "out\bench\$t\$k" *> "out\bench\${t}_$k.log"
    "$t,$k,$([math]::Round($sw.Elapsed.TotalSeconds,1))" | Add-Content out\bench\timing.csv
  }
}
"DONE $($tiers -join ',')" | Add-Content out\bench\done.txt
