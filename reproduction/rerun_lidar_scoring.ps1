# Re-run only the LiDAR tier + scoring (after a calibration/backend change), then rebuild FINAL_RESULTS.md.
$ErrorActionPreference = "Continue"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Split-Path $here -Parent)
$env:PYTHONIOENCODING = "utf-8"
$exe = ".\.venv\Scripts\roomscan.exe"; $py = ".\.venv\Scripts\python.exe"
$root = (Resolve-Path "..").Path; $O = "out\final"
$sample = [ordered]@{ "single_room" = "single_room\c00a170fe1"; "with_ceiling" = "single_scan_with_ceiling\c7d28f72c6"; "floor_only" = "single_scan_floor_only\1a8384c3f6" }
$own = [ordered]@{ "ark470350_a" = "own_benchmark\ark470350_a"; "ark470350_b" = "own_benchmark\ark470350_b"; "ark470350_c" = "own_benchmark\ark470350_c" }
foreach ($k in $sample.Keys) { & $exe run (Join-Path $root $sample[$k]) --tier lidar --out "$O\sample\lidar\$k" *> $null }
foreach ($k in $own.Keys) { & $exe run (Join-Path $root $own[$k]) --tier lidar --out "$O\own\lidar\$k" *> $null }
$L = "$root\arkitscenes_data\laser\470350\188542.ply", "$root\arkitscenes_data\laser\470350\188545.ply"
foreach ($k in $own.Keys) { & $py scripts\laser_gt.py (Join-Path $root $own[$k]) "$O\own\lidar\$k\plan.json" @L *> "benchmark\results\own\laser_gt_$k.log" }
& $exe repeat (Join-Path $root $own["ark470350_a"]) (Join-Path $root $own["ark470350_b"]) --plan-a "$O\own\lidar\ark470350_a\plan.json" --plan-b "$O\own\lidar\ark470350_b\plan.json" --out benchmark\results\own\repeatability_ab.md *> $null
& $exe repeat (Join-Path $root $own["ark470350_a"]) (Join-Path $root $own["ark470350_c"]) --plan-a "$O\own\lidar\ark470350_a\plan.json" --plan-b "$O\own\lidar\ark470350_c\plan.json" --out benchmark\results\own\repeatability_ac.md *> $null
& $exe repeat (Join-Path $root $sample["with_ceiling"]) (Join-Path $root $sample["floor_only"]) --plan-a "$O\sample\lidar\with_ceiling\plan.json" --plan-b "$O\sample\lidar\floor_only\plan.json" --out benchmark\results\repeatability_sample.md *> $null
& $py scripts\final_tables.py *> "$O\final_tables.log"
"DONE" | Add-Content "$O\lidar_rerun_done.txt"
