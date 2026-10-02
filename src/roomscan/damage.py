"""Damage detection: segment (SAM2 / Grounding-DINO + CLIP zero-shot), project to surface, metric extent."""
from .models import PropertyPlan


def attach(plan: PropertyPlan, capture) -> PropertyPlan:
    return plan
