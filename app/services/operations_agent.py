from datetime import datetime, timezone
import logging
from typing import Optional
from sqlalchemy.orm import Session
from app.models import Order, Resolution
from app.schemas import ResolutionDecision

logger = logging.getLogger(__name__)


class OperationsAgent:
    """Executes resolution actions against the database and dispatches operational integrations."""

    def execute(self, decision: ResolutionDecision, db: Session) -> Resolution:
        logger.info(f"[OperationsAgent] Executing action: {decision.action} for Order: {decision.order_id}")

        order: Optional[Order] = db.query(Order).filter(Order.order_id == decision.order_id).first()
        outcome_message = ""
        action = decision.action

        if action == "reschedule":
            when = decision.payload.get("reschedule_datetime", "Next Business Day")
            if order:
                order.status = "RESCHEDULED"
                order.notes = f"Rescheduled for: {when}. ({decision.reason})"
                order.updated_at = datetime.now(timezone.utc)
            outcome_message = f"Order #{decision.order_id} delivery successfully rescheduled for {when}. Courier dispatch instruction queued."
            logger.info(f"🚚 [MOCK LOGISTICS DISPATCH] Courier API notified -> Reschedule delivery for {when} (Order #{decision.order_id})")

        elif action == "initiate_cancellation":
            if order:
                order.status = "CANCELLED_RTO"
                order.notes = f"Cancelled by customer via AI call. Initiating Return to Origin (RTO). ({decision.reason})"
                order.updated_at = datetime.now(timezone.utc)
            outcome_message = f"Order #{decision.order_id} cancelled. Return to Origin (RTO) workflow initiated and warehouse inventory restock scheduled."
            logger.info(f"📦 [MOCK LOGISTICS RTO] Warehouse API notified -> Cancel delivery and initiate RTO for Order #{decision.order_id}")

        elif action == "flag_address_correction":
            addr = decision.payload.get("updated_address", "Customer requested update")
            if order:
                order.status = "ADDRESS_UPDATE_REQUIRED"
                order.notes = f"Address update flagged: {addr}. ({decision.reason})"
                if decision.payload.get("updated_address"):
                    order.delivery_address = f"{order.delivery_address or ''} (Correction: {addr})"
                order.updated_at = datetime.now(timezone.utc)
            outcome_message = f"Delivery put on hold for Order #{decision.order_id}. Address verification link sent to customer."
            logger.info(f"📍 [MOCK ADDRESS DISPATCH] Address hold flagged -> Updated info: {addr}")

        elif action == "escalate_to_human":
            priority = decision.payload.get("priority", "NORMAL")
            if order:
                order.status = "HUMAN_ESCALATION"
                order.notes = f"Escalated to human support agent [Priority: {priority}]. ({decision.reason})"
                order.updated_at = datetime.now(timezone.utc)
            outcome_message = f"Support desk ticket generated [Priority: {priority}] for Order #{decision.order_id}. Assigned to on-duty recovery specialist."
            logger.info(f"🎧 [MOCK CRM DISPATCH] Zendesk/Freshdesk ticket created -> Order #{decision.order_id}, Priority: {priority}")

        elif action == "retry_call":
            if order:
                order.status = "CALL_RETRY_SCHEDULED"
                order.notes = f"Automated call retry queued. ({decision.reason})"
                order.updated_at = datetime.now(timezone.utc)
            outcome_message = f"Automatic call retry queued in 120 minutes for Order #{decision.order_id}. Fallback WhatsApp/SMS dispatched."
            logger.info(f"📲 [MOCK MESSAGING DISPATCH] WhatsApp/SMS sent to customer for Order #{decision.order_id}")

        else:
            if order:
                order.status = "ACTION_PENDING"
                order.notes = decision.reason
                order.updated_at = datetime.now(timezone.utc)
            outcome_message = f"Custom action executed: {decision.action}"

        # Persist resolution record
        resolution = Resolution(
            call_id=decision.call_id,
            order_id=decision.order_id,
            decided_action=decision.action,
            action_payload=decision.payload,
            status="EXECUTED",
            outcome=outcome_message,
            executed_at=datetime.now(timezone.utc),
        )
        db.add(resolution)
        db.commit()
        db.refresh(resolution)

        logger.info(f"[OperationsAgent] Resolution #{resolution.id} saved with status EXECUTED.")
        return resolution


operations_agent = OperationsAgent()
