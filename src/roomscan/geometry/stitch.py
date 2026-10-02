"""Whole-property stitching: place rooms via shared openings, enforce no overlaps, compute footprint."""
from ..models import PropertyPlan


def finalize(plan: PropertyPlan) -> PropertyPlan:
    # TODO: constraint layout (shared-door alignment, shapely overlap check), adjacency, footprint interval.
    return plan
