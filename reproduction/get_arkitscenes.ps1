# Download one ARKitScenes venue (visit) for the own-benchmark: small assets for all its videos, one .mov, N laser scans.
# Data: Apple ARKitScenes (CC BY-NC-SA 4.0, https://github.com/apple/ARKitScenes). Disclosed in the report.
param([string]$Visit = "470350", [int]$LaserScans = 2, [int]$Movs = 1, [string]$Dest = "")
$ErrorActionPreference = "Continue"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path (Split-Path $here -Parent) -Parent
if (-not $Dest) { $Dest = Join-Path $root "arkitscenes_data" }
$U = "https://docs-assets.developer.apple.com/ml-research/datasets/arkitscenes/v1/raw"
$meta = Import-Csv (Join-Path $Dest "raw\metadata.csv") | Where-Object visit_id -eq $Visit
$log = Join-Path $Dest "download_$Visit.log"
function Get-File($url, $out) {
  if (Test-Path $out) { "skip $out" | Add-Content $log; return }
  New-Item -ItemType Directory -Force (Split-Path $out) | Out-Null
  $sw = [Diagnostics.Stopwatch]::StartNew()
  curl.exe -s --fail -o "$out.tmp" $url
  if ($LASTEXITCODE -eq 0) { Move-Item "$out.tmp" $out -Force; "ok $out $([math]::Round($sw.Elapsed.TotalSeconds))s" | Add-Content $log }
  else { "FAIL $url" | Add-Content $log }
}
$k = 0
foreach ($v in $meta) {
  $vd = Join-Path $Dest "raw\$($v.fold)\$($v.video_id)"
  foreach ($f in "lowres_wide.traj", "lowres_wide_intrinsics.zip", "confidence.zip", "lowres_depth.zip") {
    Get-File "$U/$($v.fold)/$($v.video_id)/$f" (Join-Path $vd $f)
  }
  if ($k -lt $Movs) { Get-File "$U/$($v.fold)/$($v.video_id)/$($v.video_id).mov" (Join-Path $vd "$($v.video_id).mov") }
  $k++
}
$ids = (Import-Csv (Join-Path $Dest "raw\lsp_mapping.csv") | Where-Object visit_id -eq $Visit).laser_scanner_point_clouds_id | Select-Object -First $LaserScans
foreach ($i in $ids) { Get-File "$U/laser_scanner_point_clouds/$Visit/$i.ply" (Join-Path $Dest "laser\$Visit\$i.ply") }
foreach ($z in Get-ChildItem (Join-Path $Dest "raw") -Recurse -Filter *.zip) {
  $d = Join-Path $z.DirectoryName ($z.BaseName)
  if (-not (Test-Path $d)) { Expand-Archive $z.FullName -DestinationPath $z.DirectoryName -Force; "unzipped $($z.Name)" | Add-Content $log }
}
"DONE" | Add-Content $log
