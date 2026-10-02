$ErrorActionPreference = "Continue"
Set-Location (Split-Path $PSScriptRoot -Parent)
$py = ".\.venv\Scripts\python.exe"
$base = Resolve-Path ".."
$caps = @{
  "single_room"  = "single_room\c00a170fe1"
  "with_ceiling" = "single_scan_with_ceiling\c7d28f72c6"
  "floor_only"   = "single_scan_floor_only\1a8384c3f6"
}
New-Item -ItemType Directory -Force out\explore | Out-Null
foreach ($k in $caps.Keys) {
  & $py scripts\explore_lidar.py (Join-Path $base $caps[$k]) "out\explore\$k" *> "out\explore\$k.log"
}
"ALL_DONE" | Set-Content out\explore\done.flag
