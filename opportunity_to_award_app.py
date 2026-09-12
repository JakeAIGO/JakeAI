"""Staged JakeAI backend entrypoint with Opportunity-to-Award routes mounted.

This file does not change Railway production behavior by itself. Railway currently
starts ``main:app``. Activating this entrypoint is a separate human-approved step.
"""

from main import app
from opportunity_to_award import router as opportunity_to_award_router

app.include_router(opportunity_to_award_router)
