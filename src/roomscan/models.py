"""Core data model. Every measurement carries a calibrated interval."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Interval:
    value: float
    lo: float
    hi: float
    unit: str = "m"
    level: float = 0.90  # nominal coverage

    @staticmethod
    def from_rel(value: float, rel_halfwidth: float, unit: str = "m", level: float = 0.90) -> "Interval":
        h = abs(value) * rel_halfwidth
        return Interval(value, value - h, value + h, unit, level)

    @staticmethod
    def from_abs(value: float, halfwidth: float, unit: str = "m", level: float = 0.90) -> "Interval":
        return Interval(value, value - halfwidth, value + halfwidth, unit, level)


@dataclass
class Opening:
    kind: str                     # door | window | passage
    wall_index: int
    offset_m: Interval            # position along wall from wall start
    width_m: Interval
    height_m: Optional[Interval] = None
    connects_to_room: Optional[str] = None
    confidence: float = 1.0


@dataclass
class Wall:
    start: tuple[float, float]    # room-local metres
    end: tuple[float, float]
    length_m: Interval


@dataclass
class DamageRegion:
    surface_id: str               # e.g. "room1/wall2", "room1/ceiling"
    damage_class: str            # water_stain | crack | mold | ...
    area_m2: Interval
    polygon_surface_uv: list[tuple[float, float]] = field(default_factory=list)
    score: float = 0.0


@dataclass
class ConcealedFlag:
    surface_id: str
    rule_id: str                  # the rule that fired
    rationale: str


@dataclass
class ScopeItem:
    surface_id: str
    code: str
    description: str
    quantity: Interval
    unit: str


@dataclass
class Room:
    room_id: str
    walls: list[Wall]
    ceiling_height_m: Interval
    floor_area_m2: Interval
    openings: list[Opening] = field(default_factory=list)
    damage: list[DamageRegion] = field(default_factory=list)
    concealed_flags: list[ConcealedFlag] = field(default_factory=list)
    scope: list[ScopeItem] = field(default_factory=list)
    # placement in the property frame (filled by stitching)
    origin_xy: tuple[float, float] = (0.0, 0.0)
    rotation_deg: float = 0.0


@dataclass
class PropertyPlan:
    capture_id: str
    tier: str                     # photo | video | lidar
    rooms: list[Room]
    adjacency: list[tuple[str, str]] = field(default_factory=list)
    footprint_m2: Optional[Interval] = None
    warnings: list[str] = field(default_factory=list)
    input_quality: dict = field(default_factory=dict)  # drives interval inflation / refusal

    def to_dict(self) -> dict:
        return asdict(self)
