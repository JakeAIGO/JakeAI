"""End-to-end private reference workflow for Move the Damn Data™.

This module models the product as a deterministic administrative chain:
Lead Relay -> Quote Relay -> Job Relay -> Invoice Relay -> Follow-Up Relay.

It is intentionally connector-agnostic and side-effect free. It never sends mail,
changes prices, spends money, deletes records, publishes content, or writes to a
production system. External actions are represented only as prepared work products.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from typing import Any, Dict, Mapping, MutableMapping, Optional


@dataclass(frozen=True)
class ChainResult:
    status: str
    stage: str
    case_id: str
    output: Mapping[str, Any] = field(default_factory=dict)
    reason: Optional[str] = None
    audit_id: Optional[str] = None


class MoveTheDamnDataChain:
    """Fail-closed, deterministic business-admin workflow reference implementation."""

    STAGES = ("lead", "quote", "job", "invoice", "follow_up")

    def __init__(self) -> None:
        self._processed: MutableMapping[str, ChainResult] = {}
        self._audit: list[Dict[str, Any]] = []

    @property
    def audit_log(self) -> tuple[Dict[str, Any], ...]:
        return tuple(self._audit)

    def process_lead(self, case_id: str, payload: Mapping[str, Any]) -> ChainResult:
        duplicate = self._duplicate(case_id, "lead")
        if duplicate:
            return duplicate
        missing = self._missing(payload, "name", "email", "request")
        if missing:
            return self._record(case_id, "lead", "human_review", reason=self._missing_reason(missing))
        if not self._looks_like_email(str(payload["email"])):
            return self._record(case_id, "lead", "human_review", reason="invalid email address")
        if payload.get("opt_in") is not True:
            return self._record(case_id, "lead", "blocked", reason="no verified opt-in")

        output = {
            "contact": {"name": str(payload["name"]).strip(), "email": str(payload["email"]).strip()},
            "request": str(payload["request"]).strip(),
            "record_action": "create_or_update_record",
            "next_action": "prepare_quote_inputs_or_followup",
        }
        return self._record(case_id, "lead", "completed", output=output)

    def process_quote(self, case_id: str, payload: Mapping[str, Any]) -> ChainResult:
        duplicate = self._duplicate(case_id, "quote")
        if duplicate:
            return duplicate
        missing = self._missing(payload, "customer_name", "scope", "verified_price")
        if missing:
            return self._record(case_id, "quote", "human_review", reason=self._missing_reason(missing))
        amount = self._money(payload["verified_price"])
        if amount is None or amount < 0:
            return self._record(case_id, "quote", "human_review", reason="verified_price is invalid")
        if payload.get("price_verified") is not True:
            return self._record(case_id, "quote", "blocked", reason="price has not been explicitly verified")

        output = {
            "customer_name": str(payload["customer_name"]).strip(),
            "scope": str(payload["scope"]).strip(),
            "quote_total": f"{amount:.2f}",
            "delivery_state": "draft_only",
            "approval_required_before_send": True,
        }
        return self._record(case_id, "quote", "prepared", output=output)

    def process_job(self, case_id: str, payload: Mapping[str, Any]) -> ChainResult:
        duplicate = self._duplicate(case_id, "job")
        if duplicate:
            return duplicate
        missing = self._missing(payload, "job_id", "approved_scope", "status")
        if missing:
            return self._record(case_id, "job", "human_review", reason=self._missing_reason(missing))
        if payload.get("quote_approved") is not True:
            return self._record(case_id, "job", "blocked", reason="job cannot advance without approved quote")
        allowed_statuses = {"scheduled", "in_progress", "completed", "on_hold"}
        status = str(payload["status"]).strip().lower()
        if status not in allowed_statuses:
            return self._record(case_id, "job", "human_review", reason="unrecognized job status")

        output = {
            "job_id": str(payload["job_id"]).strip(),
            "approved_scope": str(payload["approved_scope"]).strip(),
            "status": status,
            "record_action": "update_job_state",
        }
        return self._record(case_id, "job", "completed", output=output)

    def process_invoice(self, case_id: str, payload: Mapping[str, Any]) -> ChainResult:
        duplicate = self._duplicate(case_id, "invoice")
        if duplicate:
            return duplicate
        missing = self._missing(payload, "invoice_id", "quoted_total", "invoice_total")
        if missing:
            return self._record(case_id, "invoice", "human_review", reason=self._missing_reason(missing))
        quoted = self._money(payload["quoted_total"])
        invoiced = self._money(payload["invoice_total"])
        if quoted is None or invoiced is None:
            return self._record(case_id, "invoice", "human_review", reason="invoice amounts are invalid")
        delta = invoiced - quoted
        if delta != Decimal("0.00") and payload.get("difference_verified") is not True:
            return self._record(
                case_id,
                "invoice",
                "human_review",
                output={"difference": f"{delta:.2f}"},
                reason="invoice differs from quote and difference is not verified",
            )

        output = {
            "invoice_id": str(payload["invoice_id"]).strip(),
            "quoted_total": f"{quoted:.2f}",
            "invoice_total": f"{invoiced:.2f}",
            "difference": f"{delta:.2f}",
            "reconciliation": "matched" if delta == 0 else "verified_difference",
        }
        return self._record(case_id, "invoice", "completed", output=output)

    def process_follow_up(self, case_id: str, payload: Mapping[str, Any]) -> ChainResult:
        duplicate = self._duplicate(case_id, "follow_up")
        if duplicate:
            return duplicate
        missing = self._missing(payload, "recipient", "purpose", "message")
        if missing:
            return self._record(case_id, "follow_up", "human_review", reason=self._missing_reason(missing))
        if not self._looks_like_email(str(payload["recipient"])):
            return self._record(case_id, "follow_up", "human_review", reason="invalid recipient address")
        if payload.get("communication_allowed") is not True:
            return self._record(case_id, "follow_up", "blocked", reason="communication is not authorized")

        output = {
            "recipient": str(payload["recipient"]).strip(),
            "purpose": str(payload["purpose"]).strip(),
            "message": str(payload["message"]).strip(),
            "external_action": "send_external_message",
            "delivery_state": "prepared_not_sent",
            "human_approval_required": True,
        }
        return self._record(case_id, "follow_up", "awaiting_approval", output=output)

    def run_case(self, case_id: str, case: Mapping[str, Mapping[str, Any]]) -> tuple[ChainResult, ...]:
        """Run the full synthetic chain until a stage requires review/approval or blocks.

        This convenience method is intentionally conservative: `prepared` quote output
        may advance because no external action occurred, while `awaiting_approval`,
        `human_review`, and `blocked` always stop the chain.
        """
        handlers = (
            ("lead", self.process_lead),
            ("quote", self.process_quote),
            ("job", self.process_job),
            ("invoice", self.process_invoice),
            ("follow_up", self.process_follow_up),
        )
        results: list[ChainResult] = []
        for stage, handler in handlers:
            payload = case.get(stage)
            if payload is None:
                results.append(self._record(case_id, stage, "human_review", reason=f"missing stage payload: {stage}"))
                break
            result = handler(case_id, payload)
            results.append(result)
            if result.status in {"blocked", "human_review", "awaiting_approval"}:
                break
        return tuple(results)

    def _duplicate(self, case_id: str, stage: str) -> Optional[ChainResult]:
        key = f"{case_id}:{stage}"
        previous = self._processed.get(key)
        if previous is None:
            return None
        return ChainResult(
            status="duplicate",
            stage=stage,
            case_id=case_id,
            output=previous.output,
            reason="case stage already processed; no second action performed",
            audit_id=previous.audit_id,
        )

    def _record(
        self,
        case_id: str,
        stage: str,
        status: str,
        *,
        output: Optional[Mapping[str, Any]] = None,
        reason: Optional[str] = None,
    ) -> ChainResult:
        key = f"{case_id}:{stage}"
        audit_id = sha256(key.encode()).hexdigest()[:16]
        result = ChainResult(
            status=status,
            stage=stage,
            case_id=case_id,
            output=dict(output or {}),
            reason=reason,
            audit_id=audit_id,
        )
        self._processed[key] = result
        self._audit.append(
            {"audit_id": audit_id, "case_id": case_id, "stage": stage, "status": status, "reason": reason}
        )
        return result

    @staticmethod
    def _missing(payload: Mapping[str, Any], *fields: str) -> list[str]:
        missing: list[str] = []
        for name in fields:
            value = payload.get(name)
            if value is None or (isinstance(value, str) and not value.strip()):
                missing.append(name)
        return missing

    @staticmethod
    def _missing_reason(fields: list[str]) -> str:
        return "missing required fields: " + ", ".join(sorted(fields))

    @staticmethod
    def _looks_like_email(value: str) -> bool:
        value = value.strip()
        return "@" in value and "." in value.rsplit("@", 1)[-1] and " " not in value

    @staticmethod
    def _money(value: Any) -> Optional[Decimal]:
        try:
            return Decimal(str(value)).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError, TypeError):
            return None
