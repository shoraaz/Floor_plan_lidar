"""Concealed-damage rules (each flag records rule_id) and scope line items keyed to surfaces."""
from .models import PropertyPlan

RULES = {
    "CD-001": "Ceiling water stain beneath wet room -> possible concealed leak in floor assembly",
    "CD-002": "Stain with tide line near baseboard -> possible wicking into wall cavity",
    "CD-003": "Mold on exterior-wall surface -> possible concealed moisture behind finish",
}


def apply(plan: PropertyPlan) -> PropertyPlan:
    # TODO: evaluate RULES against plan.rooms[*].damage and adjacency; append ConcealedFlag + ScopeItem.
    return plan
