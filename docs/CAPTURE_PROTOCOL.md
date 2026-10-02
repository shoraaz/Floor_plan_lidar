# Capture Protocol (stock tools, free, ~10 min per property)

For a non-engineer. Follow literally. Phone: **iPhone 15 or newer**. LiDAR tier needs a **Pro** model.

## Before you start (once, ~3 min)
1. Install **Stray Scanner** (free, App Store). Needed only for the LiDAR tier.
2. Turn on every light in the property. Open all interior doors fully. Close blinds if sunlight is harsh.
3. Cover or avoid pointing at: mirrors, big glass, TVs that are off (black glass), wet-look floors.
4. Clear the floor edges so the wall/floor line is visible. Move chairs away from walls if easy.

## Tier A: LiDAR (iPhone Pro) - Stray Scanner
1. Open Stray Scanner, tap the red record button.
2. Stand in the doorway of the first room. Hold the phone at chest height, portrait, steady.
3. Walk slowly (about one step per second), keeping the phone pointed at the **walls and the wall/floor line**, then sweep once up to the ceiling edge and down again. Do not spin in place.
4. Go room by room, walking **through** every doorway. After the last room, **walk back to the first room** and stand where you started. (Closing the loop matters.)
5. Total time: about 60-90 seconds per room. Stop recording.
6. Hand over: Stray Scanner > select the recording > Share/Export > AirDrop to the laptop, or save to Files and zip. Name the zip `<property>_lidar.zip`.

## Tier B: Video (any iPhone 15+) - native Camera
1. Camera app > Video, **4K at 30 fps**, main (1x) lens. Do not use zoom or cinematic mode.
2. Same walk as Tier A: slow, steady, through every doorway, return to the start.
3. Keep every doorway fully in frame at least once, and show the floor-wall line in each room.
4. Export: AirDrop the original `.mov` (choose "All Photos Data"/original, not compressed). Name `<property>_video.mov`.

## Tier C: Photos (any iPhone 15+) - native Camera
1. One folder per room, named after the room (`kitchen`, `bedroom1`, ...).
2. Take **4-8 photos per room** (minimum 2), 1x lens, no zoom, no panorama, no portrait mode:
   - from each corner, aim at the opposite corner so two walls and floor/ceiling are visible
   - one photo that clearly shows each **doorway** you could walk through
   - at least one photo with the full height of a wall (floor to ceiling)
3. Avoid: motion blur, flash, filters, cropping, edited photos.
4. AirDrop originals (HEIC/JPG with metadata kept). Put each room's photos in its own folder, zip all as `<property>_photos.zip`.

## What to avoid (all tiers)
- Fast turns, pointing at windows against bright sky, dark rooms, people walking through.
- Covering the camera or lens with fingers. Cleaning the lens first helps.

## Handing files to the pipeline
Unzip into `captures/<property>/<tier>/` and run: `roomscan run captures/<property>/<tier> --out out/<property>_<tier>`.
