Raw captures live OUTSIDE git, one level up in `property project/`:
  single_room/c00a170fe1                    LiDAR, single room
  single_scan_floor_only/1a8384c3f6         LiDAR, floor-only sweep (ceiling not scanned)
  single_scan_with_ceiling/c7d28f72c6       LiDAR, with ceiling sweep
Add a manifest (benchmark/manifest.yaml) mapping each capture -> room, tier, date, device, ground-truth file.
Large files: share via volume / fetch script; never commit mp4/depth PNGs.
