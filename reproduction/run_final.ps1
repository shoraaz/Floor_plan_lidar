# Final benchmark run: sample data (organisers) + own benchmark (ARKitScenes venue 470350, laser GT).
# Produces out/final/<set>/<tier>/<capture>/plan.json, timing.csv, and the result files under benchmark/results/.
$ErrorActionPreference = "Continue"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Split-Path $here -Parent)
$env:PYTHONIOENCODING = "utf-8"
$exe = ".\.venv\Scripts\roomscan.exe"; $py = ".\.venv\Scripts\python.exe"
$root = (Resolve-Path "..").Path
$O = "out\final"; New-Item -ItemType Directory -Force $O | Out-Null
$T = "$O\timing.csv"; if (Test-Path $T) { Remove-Item $T }
function Run($set, $tier, $name, $src) {
  $sw = [Diagnostics.Stopwatch]::StartNew()
  & $exe run $src --tier $tier --out "$O\$set\$tier\$name" *> "$O\${set}_${tier}_$name.log"
  "$set,$tier,$name,$([math]::Round($sw.Elapsed.TotalSeconds,1))" | Add-Content $T
}
$sample = [ordered]@{ "single_room" = "single_room\c00a170fe1"; "with_ceiling" = "single_scan_with_ceiling\c7d28f72c6"; "floor_only" = "single_scan_floor_only\1a8384c3f6" }
$own = [ordered]@{ "ark470350_a" = "own_benchmark\ark470350_a"; "ark470350_b" = "own_benchmark\ark470350_b"; "ark470350_c" = "own_benchmark\ark470350_c" }
# 1. LiDAR everywhere (CPU)
foreach ($k in $sample.Keys) { Run "sample" "lidar" $k (Join-Path $root $sample[$k]) }
foreach ($k in $own.Keys)    { Run "own" "lidar" $k (Join-Path $root $own[$k]) }
# 2. photo folders from LiDAR room membership, then video + photo (GPU)
foreach ($k in $sample.Keys) {
  & $py scripts\make_photo_folders.py (Join-Path $root $sample[$k]) "$O\sample\lidar\$k\plan.json" "benchmark\photos_final\$k" 5 *> $null
  Run "sample" "video" $k (Join-Path $root $sample[$k]); Run "sample" "photo" $k "benchmark\photos_final\$k"
}
& $py scripts\make_photo_folders.py (Join-Path $root $own["ark470350_a"]) "$O\own\lidar\ark470350_a\plan.json" "benchmark\photos_final\ark470350_a" 5 *> $null
Run "own" "video" "ark470350_a" (Join-Path $root $own["ark470350_a"])
Run "own" "photo" "ark470350_a" "benchmark\photos_final\ark470350_a"
# 3. scoring
$L = "$root\arkitscenes_data\laser\470350\188542.ply", "$root\arkitscenes_data\laser\470350\188545.ply"
foreach ($k in $own.Keys) { & $py scripts\laser_gt.py (Join-Path $root $own[$k]) "$O\own\lidar\$k\plan.json" @L *> "benchmark\results\own\laser_gt_$k.log" }
& $exe repeat (Join-Path $root $own["ark470350_a"]) (Join-Path $root $own["ark470350_b"]) --plan-a "$O\own\lidar\ark470350_a\plan.json" --plan-b "$O\own\lidar\ark470350_b\plan.json" --out benchmark\results\own\repeatability_ab.md *> $null
& $exe repeat (Join-Path $root $own["ark470350_a"]) (Join-Path $root $own["ark470350_c"]) --plan-a "$O\own\lidar\ark470350_a\plan.json" --plan-b "$O\own\lidar\ark470350_c\plan.json" --out benchmark\results\own\repeatability_ac.md *> $null
& $exe repeat (Join-Path $root $sample["with_ceiling"]) (Join-Path $root $sample["floor_only"]) --plan-a "$O\sample\lidar\with_ceiling\plan.json" --plan-b "$O\sample\lidar\floor_only\plan.json" --out benchmark\results\repeatability_sample.md *> $null
"DONE" | Add-Content "$O\done.txt"
