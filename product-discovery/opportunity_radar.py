"""
JakeAI Opportunity Radar
Stage 0 of the Autonomous Product Discovery Pipeline

Version 0.2.0

Purpose:
Evaluate live external signals and determine whether they should be:

- PROMOTE_TO_DISCOVERY
- NEEDS_MORE_EVIDENCE
- REJECT_NOISE

Key principle:
UNKNOWN is not the same as NEGATIVE.

A news story may reveal a major commercial or operational change
without explicitly describing the AI workflow that could solve it.
Those signals should be researched, not automatically rejected.
"""

from __future__ import annotations

import json
import re
import sys

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RADAR_VERSION = "0.2.0"


# ---------------------------------------------------------
# SIGNAL VOCABULARIES
# ---------------------------------------------------------

OPERATIONAL_TERMS = {
    "shortage",
    "bottleneck",
    "capacity",
    "delay",
    "downtime",
    "scrap",
    "rework",
    "yield",
    "maintenance",
    "compliance",
    "integration",
    "supplier",
    "supply chain",
    "inventory",
    "quality",
    "inspection",
    "scheduling",
    "planning",
    "forecasting",
    "monitoring",
    "reporting",
    "optimization",
    "cost",
    "labor",
    "workforce",
    "risk",
    "incident",
    "failure",
    "production",
    "manufacturing",
    "deployment",
    "logistics",
    "energy",
    "infrastructure",
    "construction",
    "robotics",
    "recall",
    "defect",
    "constraint",
    "backlog",
}


VALUE_TERMS = {
    "save",
    "reduce",
    "increase",
    "improve",
    "accelerate",
    "prevent",
    "avoid",
    "optimize",
    "automate",
    "streamline",
    "efficiency",
    "productivity",
    "revenue",
    "cost",
    "downtime",
    "scrap",
    "rework",
    "yield",
    "capacity",
    "margin",
    "profit",
    "savings",
    "growth",
    "billion",
    "million",
    "investment",
}


AI_EXECUTABLE_TERMS = {
    "data",
    "analysis",
    "monitor",
    "detect",
    "classify",
    "compare",
    "score",
    "rank",
    "forecast",
    "schedule",
    "report",
    "alert",
    "document",
    "research",
    "review",
    "optimize",
    "recommend",
    "triage",
    "coordinate",
    "workflow",
    "software",
    "api",
    "digital",
    "model",
    "tracking",
    "planning",
    "inspection",
    "prediction",
}


# These terms indicate BUSINESS CHANGE.
# They are important even when a
