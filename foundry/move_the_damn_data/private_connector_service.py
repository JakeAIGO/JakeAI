"""Private deployable service boundary for Move the Damn Data™.

This service is intentionally fail-closed. It can ingest an authorized lead and prepare
work for a connector, but it does not contain Google credentials and does not send email.
Real connector execution remains disabled unless a separately reviewed adapter is added.
"""
from __future__ import annotations

import hmac
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from durable_state import DurableState, DurableStateError
from workflow_chain import MoveTheDamnDataChain


SERVICE_NAME = "move-the-damn-data-private-connector"
STATE_PATH = os.getenv("MTDD_STATE_PATH", "/tmp/move-the-damn-data/state.json")
OPERATOR_TOKEN = os.getenv("JAKEAI_PRIVATE_OPERATOR_TOKEN", "")
LIVE_CONNECTORS_ENABLED = os.getenv("MTDD_LIVE_CONNECTORS_ENABLED", "false").lower() == "true"

app = FastAPI(title=SERVICE_NAME, version="0.1.0")


class LeadIntake(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    request: str = Field(min_length=1, max_length=5000)
    opt_in: bool


class PrepareResult(BaseModel):
    status: str
    event_id: str
    audit_id: str | None = None
    connector_execution: str
    prepared_draft: dict[str, Any] | None = None
    reason: str | None = None


def _authorized(provided: str | None) -> None:
    if not OPERATOR_TOKEN:
        raise HTTPException(status_code=503, detail="operator token is not configured")
    if provided is None or not hmac.compare_digest(provided, OPERATOR_TOKEN):
        raise HTTPException(status_code=401, detail="unauthorized")


def _state() -> DurableState:
    try:
        return DurableState(Path(STATE_PATH))
    except DurableStateError as exc:
        raise HTTPException(status_code=503, detail="durable state unavailable; fail closed") from exc


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "service": SERVICE_NAME,
        "status": "ok",
        "live_connectors_enabled": LIVE_CONNECTORS_ENABLED,
        "external_send_enabled": False,
        "human_approval_required": True,
    }


@app.post("/v1/leads/prepare", response_model=PrepareResult)
def prepare_lead(
    intake: LeadIntake,
    x_jakeai_operator_token: str | None = Header(default=None),
) -> PrepareResult:
    _authorized(x_jakeai_operator_token)
    state = _state()

    existing = state.recovery(intake.event_id)
    if existing is not None:
        return PrepareResult(
            status="duplicate",
            event_id=intake.event_id,
            audit_id=existing.get("audit_id"),
            connector_execution="none",
            reason="event already recorded; no second preparation performed",
        )

    chain = MoveTheDamnDataChain()
    lead = chain.process_lead(
        intake.event_id,
        {
            "name": intake.name,
            "email": intake.email,
            "request": intake.request,
            "opt_in": intake.opt_in,
        },
    )
    if lead.status != "completed":
        state.put_recovery(
            intake.event_id,
            {
                "stage": "lead",
                "status": lead.status,
                "audit_id": lead.audit_id,
                "reason": lead.reason,
            },
        )
        return PrepareResult(
            status=lead.status,
            event_id=intake.event_id,
            audit_id=lead.audit_id,
            connector_execution="none",
            reason=lead.reason,
        )

    draft = {
        "to": intake.email.strip(),
        "subject": "We received your request",
        "body": (
            f"Hello {intake.name.strip()},\n\n"
            "We received your request and have prepared it for review. "
            "A human must approve any external send.\n\n"
            "— JakeAI Communications Department"
        ),
        "delivery_state": "prepared_not_sent",
        "human_approval_required": True,
    }
    state.put_recovery(
        intake.event_id,
        {
            "stage": "follow_up",
            "status": "awaiting_approval",
            "audit_id": lead.audit_id,
            "recipient": intake.email.strip(),
            "connector_execution": "none",
        },
    )
    return PrepareResult(
        status="awaiting_approval",
        event_id=intake.event_id,
        audit_id=lead.audit_id,
        connector_execution="none",
        prepared_draft=draft,
    )


@app.post("/v1/connectors/execute")
def execute_connector(x_jakeai_operator_token: str | None = Header(default=None)) -> dict[str, Any]:
    _authorized(x_jakeai_operator_token)
    raise HTTPException(
        status_code=503,
        detail="live connector execution is not installed; external action remains disabled",
    )
