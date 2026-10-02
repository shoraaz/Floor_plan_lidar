"""`roomscan run <capture> --out <dir>` : one command per capture."""
from __future__ import annotations
import json
import random
from pathlib import Path

import click
import numpy as np

SEED = 1234


def detect_tier(p: Path) -> str:
    if p.is_file() and p.suffix.lower() in {".mov", ".mp4", ".m4v"}:
        return "video"
    if p.is_dir():
        if (p / "depth").exists() and (p / "odometry.csv").exists():
            return "lidar"
        subs = [d for d in p.iterdir() if d.is_dir()]
        if subs and all(any(f.suffix.lower() in {".jpg", ".jpeg", ".png", ".heic"} for f in d.iterdir()) for d in subs):
            return "photo"
    raise click.ClickException(f"Cannot detect tier for {p}. Use --tier.")


@click.group()
def main():
    """roomscan: phone capture -> calibrated floor plan."""


@main.command()
@click.argument("capture", type=click.Path(exists=True, path_type=Path))
@click.option("--out", type=click.Path(path_type=Path), required=True)
@click.option("--tier", type=click.Choice(["auto", "photo", "video", "lidar"]), default="auto")
@click.option("--no-drift-correction", is_flag=True, help="Ablation switch for the drift-accountability row.")
def run(capture: Path, out: Path, tier: str, no_drift_correction: bool):
    random.seed(SEED); np.random.seed(SEED)
    out.mkdir(parents=True, exist_ok=True)
    tier = detect_tier(capture) if tier == "auto" else tier

    from .tiers import lidar, video, photo
    from . import render, rules, damage
    from .geometry import stitch

    runner = {"lidar": lidar.run, "video": video.run, "photo": photo.run}[tier]
    plan = runner(capture, drift_correction=not no_drift_correction)
    plan = stitch.finalize(plan)
    plan = damage.attach(plan, capture)
    plan = rules.apply(plan)

    doc = json.loads(json.dumps(plan.to_dict()))  # tuples -> lists, as written to disk
    import jsonschema
    schema = json.loads((Path(__file__).resolve().parents[2] / "schema" / "property_plan.schema.json").read_text())
    jsonschema.validate(doc, schema)
    (out / "plan.json").write_text(json.dumps(doc, indent=2))
    render.to_svg(plan, out / "plan.svg")
    click.echo(f"[{tier}] {len(plan.rooms)} rooms, footprint {plan.footprint_m2.value:.2f} m2, "
               f"{len(plan.warnings)} warnings -> {out}")


if __name__ == "__main__":
    main()
