# Build plan

Order matters: LiDAR first (it is the ground-truth-quality path the others reuse), photos last but
start the benchmark capture early because it is the bottleneck.

## Phase 0 - Foundations (done by scaffold)
- repo, schema, CLI skeleton, calibration module, capture protocol, compliance matrix

## Phase 1 - Benchmark capture (start immediately, needs physical access)
- Pick property A: >= 3 rooms + a connector (hall). Pick room X: furnished, staged damage in 2 classes
  (e.g. water-stain on ceiling + crack/peeling on wall).
- Capture each at ALL THREE tiers following docs/CAPTURE_PROTOCOL.md literally.
- Capture at least one room TWICE at the same tier (repeatability).
- Ground truth with laser/tape: every wall length, ceiling height (several points), every opening width/height/offset.
  Record in benchmark/ground_truth/*.csv (template provided). Photograph the measurement too.
- Also capture a small "hostile" set: mirror, glass door, glossy floor, dim room.
- Head-to-head: scan 2 rooms with a free app (Polycam or magicplan free tier); save exports + app version.

## Phase 2 - LiDAR tier
- load Stray Scanner data -> fuse depth (confidence filtered) -> planes -> room polygon -> ceiling -> openings
- drift: pose graph + plane anchors; ablation with --no-drift-correction

## Phase 3 - Stitching + render + schema validation tests

## Phase 4 - Video tier (poses + metric scale + shared plane code)

## Phase 5 - Photo tier + constraint stitch; input-quality gate

## Phase 6 - Calibration: fit conformal quantiles on benchmark residuals per tier/kind; report coverage

## Phase 7 - Damage + concealed rules + scope

## Phase 8 - Fix loop
- find worst gate in own benchmark -> fixloop/FIX_DECLARATION.md BEFORE fixing (commit it)
- ship the fix, regenerate before/after with reproduction/run_all.ps1, commit the diff

## Phase 9 - Report (<= 6 pages), reproduction bundle, README timing test on a clean machine

## Defense readiness (walk-in test = 30%)
- All 3 tiers must run cold and live. Time each. No network calls to your infra. Weights pre-fetched.
- Have a degrade path: if the tier fails, return wide intervals + warnings, never confident garbage.
- Practice explaining every design decision with tools closed.

## Commit hygiene
Commit after every small working step (feature, benchmark capture batch, calibration fit, bug fix).
