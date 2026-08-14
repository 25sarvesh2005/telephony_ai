import logging
from typing import Any, Dict, Optional
from app.models import Order
from app.schemas import ExtractedIntent, ResolutionDecision

logger = logging.getLogger(__name__)


class ResolutionAgent:
    """Decision engine that maps customer understanding and order context to operational actions."""

    def decide(
        self,
        extracted_intent: ExtractedIntent,
        order: Optional[Order] = None,
        call_id: Optional[str] = None,
    ) -> ResolutionDecision:
        intent = extracted_intent.customer_intent
        outcome = extracted_intent.call_outcome
        order_id = order.order_id if order else (extracted_intent.order_id or "UNKNOWN")
        attempts = order.delivery_attempts if order else 1
        amount = order.amount if order else 0.0

        logger.info(
            f"[ResolutionAgent] Evaluating Order={order_id}, Intent={intent}, Outcome={outcome}, Attempts={attempts}, Amount={amount}"
        )

        # 1. Reschedule Scenario
        if intent == "reschedule":
            when = extracted_intent.reschedule_datetime or "Next Business Day"
            # Policy Rule: If already failed 3 times, require human confirmation for further reschedule
            if attempts >= 3:
                return ResolutionDecision(
                    order_id=order_id,
                    call_id=call_id,
                    action="escalate_to_human",
                    reason=f"Customer requested reschedule for {when}, but delivery has already failed {attempts} times (Threshold exceeded).",
                    payload={
                        "reschedule_datetime": when,
                        "attempts": attempts,
                        "notes": extracted_intent.notes,
                        "requires_supervisor": True,
                    },
                )
            return ResolutionDecision(
                order_id=order_id,
                call_id=call_id,
                action="reschedule",
                reason=f"Customer confirmed availability. Reschedule arranged for {when}.",
                payload={
                    "reschedule_datetime": when,
                    "attempts": attempts,
                    "notes": extracted_intent.notes,
                },
            )

        # 2. Cancellation Scenario
        if intent == "cancel":
            return ResolutionDecision(
                order_id=order_id,
                call_id=call_id,
                action="initiate_cancellation",
                reason="Customer declined delivery and requested cancellation.",
                payload={
                    "cancellation_reason": extracted_intent.notes or "Customer requested cancellation during recovery call",
                    "initiate_rto": True,
                    "restock_inventory": True,
                },
            )

        # 3. Wrong Address / Address Correction Scenario
        if intent == "wrong_address":
            return ResolutionDecision(
                order_id=order_id,
                call_id=call_id,
                action="flag_address_correction",
                reason="Customer reported incorrect delivery address or moved location.",
                payload={
                    "updated_address": extracted_intent.updated_address or "Pending customer confirmation",
                    "hold_delivery": True,
                    "send_address_update_link": True,
                },
            )

        # 4. Human Escalation or Unclear Response
        if intent in ("escalate_human", "unclear"):
            priority = "HIGH" if amount >= 2500 else "NORMAL"
            return ResolutionDecision(
                order_id=order_id,
                call_id=call_id,
                action="escalate_to_human",
                reason="Customer requested human agent or intent was ambiguous.",
                payload={
                    "priority": priority,
                    "order_value": amount,
                    "notes": extracted_intent.notes,
                    "ticket_type": "VOICE_CALL_ESCALATION",
                },
            )

        # 5. Non-contact (No answer, Voicemail, Busy, Failed)
        if outcome in ("no_answer", "voicemail", "busy", "failed") or intent == "no_answer":
            if attempts < 3:
                return ResolutionDecision(
                    order_id=order_id,
                    call_id=call_id,
                    action="retry_call",
                    reason=f"Call outcome: {outcome}. Scheduled automatic retry and fallback SMS/WhatsApp outreach.",
                    payload={
                        "retry_scheduled_in_minutes": 120,
                        "send_fallback_sms": True,
                        "attempts_so_far": attempts,
                    },
                )
            else:
                return ResolutionDecision(
                    order_id=order_id,
                    call_id=call_id,
                    action="escalate_to_human",
                    reason=f"Call outcome: {outcome} after {attempts} failed delivery attempts. Escalating to support team.",
                    payload={
                        "priority": "HIGH",
                        "reason": "Max delivery attempts and calls reached without customer contact",
                    },
                )

        # Fallback safety net
        return ResolutionDecision(
            order_id=order_id,
            call_id=call_id,
            action="escalate_to_human",
            reason="Unhandled intent pattern. Defaulting to human agent escalation for safety.",
            payload={"raw_intent": intent, "notes": extracted_intent.notes},
        )


resolution_agent = ResolutionAgent()
