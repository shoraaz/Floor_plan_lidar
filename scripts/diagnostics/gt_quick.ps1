# Quick accuracy loop: LiDAR tier on the 3 own captures -> laser GT -> one summary line each.
param([string]$Tag = "exp")
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Split-Path (Split-Path $here -Parent) -Parent)
$env:PYTHONIOENCODING = "utf-8"
$root = (Resolve-Path "..").Path
$L = "$root\arkitscenes_data\laser\470350\188542.ply", "$root\arkitscenes_data\laser\470350\188545.ply"
foreach ($k in "ark470350_a", "ark470350_b", "ark470350_c") {
  & .\.venv\Scripts\roomscan.exe run "$root\own_benchmark\$k" --out "out\exp\$Tag\$k" *> $null
  $o = & .\.venv\Scripts\python.exe scripts\laser_gt.py "$root\own_benchmark\$k" "out\exp\$Tag\$k\plan.json" @L 2>$null
  $j = Get-Content "benchmark\results\own\laser_gt_$k.json" -Raw | ConvertFrom-Json
  $e = $j.walls | Where-Object { $_.gt_m } | ForEach-Object { [math]::Abs($_.err_cm) }
  "{0} {1}: scored {2}, median {3:N1} cm, <=2cm {4}, <=5cm {5}" -f $Tag, $k, $e.Count, (($e | Sort-Object)[[int][math]::Floor($e.Count/2)]), ($e | Where-Object { $_ -le 2 }).Count, ($e | Where-Object { $_ -le 5 }).Count
}
