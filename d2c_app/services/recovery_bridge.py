import logging
from typing import Any, Dict, Optional
import httpx
from d2c_app.config import d2c_settings
from d2c_app.models import D2COrder, NDRTicket, ShipmentTracking
from sqlalchemy.orm import Session

logger = logging.getLogger("d2c_recovery_bridge")


class RecoveryBridge:
    """Bridges D2C Logistics NDR events to the AI Voice Telephony Recovery Engine."""

    def __init__(self, base_url: str = d2c_settings.RECOVERY_ENGINE_URL):
        self.base_url = base_url.rstrip("/")

    async def ingest_failed_order(self, order: D2COrder) -> Dict[str, Any]:
        """Ensures the failed D2C order is registered in the recovery engine database."""
        item_names = ", ".join([i.product_title for i in order.items]) if order.items else "D2C Luxury Order"
        payload = {
            "order_id": order.order_id,
            "customer_name": order.customer_name,
            "customer_phone": order.customer_phone,
            "amount": order.total_amount,
            "currency": order.currency,
            "payment_method": order.payment_method,
            "delivery_attempts": order.delivery_attempts,
            "delivery_address": order.delivery_address,
            "city": order.city,
            "notes": f"D2C NDR Event: Items: {item_names}. Reason: {order.ndr_reason or 'Customer unavailable'}",
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(f"{self.base_url}/api/orders", json=payload)
                if res.status_code in (200, 201):
                    return res.json()
                elif res.status_code == 400:
                    # Order already exists in recovery DB, return success
                    return {"status": "exists", "order_id": order.order_id}
                logger.warning(f"Ingest order returned status {res.status_code}: {res.text}")
                return {"status": "error", "detail": res.text}
        except Exception as e:
            logger.error(f"Failed to ingest order into recovery engine: {e}")
            return {"status": "error", "error": str(e)}

    async def trigger_recovery_call(
        self,
        order: D2COrder,
        telephony_provider: Optional[str] = None,
        from_number: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Dispatches an outbound AI recovery voice call to the customer."""
        provider = telephony_provider or d2c_settings.DEFAULT_TELEPHONY_PROVIDER
        
        # Build prompt context variables
        first_item = order.items[0].product_title if order.items else "Package"
        custom_vars = {
            "order_id": order.order_id,
            "customer_name": order.customer_name,
            "amount": f"{order.currency} {order.total_amount:.2f}",
            "merchant_name": d2c_settings.STORE_NAME,
            "delivery_attempts": order.delivery_attempts,
            "city": order.city,
            "item": first_item,
            "address": order.delivery_address,
        }

        # 1. Ingest order first
        await self.ingest_failed_order(order)

        # 2. Trigger call
        payload = {
            "order_id": order.order_id,
            "phone_override": order.customer_phone,
            "from_number": from_number,
            "telephony_provider": provider,
            "custom_prompt_variables": custom_vars,
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(f"{self.base_url}/trigger-call", json=payload)
                if res.status_code == 200:
                    data = res.json()
                    logger.info(f"Triggered recovery call for D2C order {order.order_id}: {data}")
                    return data
                logger.error(f"Recovery engine error {res.status_code}: {res.text}")
                return {"success": False, "status": "error", "detail": res.text}
        except Exception as e:
            logger.error(f"Error calling recovery engine: {e}")
            return {"success": False, "error": str(e)}

    def apply_resolution_to_d2c_order(
        self,
        order: D2COrder,
        action: str,
        reschedule_datetime: Optional[str] = None,
        updated_address: Optional[str] = None,
        notes: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Updates D2C Order and logistics milestones based on customer voice intent."""
        now_str = ""

        if action == "reschedule":
            order.order_status = "RESCHEDULED"
            order.rescheduled_for = reschedule_datetime or "Next business day"
            order.resolution_notes = f"Customer rescheduled delivery for: {order.rescheduled_for}. {notes or ''}"
            
            milestone = ShipmentTracking(
                order_id=order.id,
                status="RESCHEDULED",
                location=f"{order.city} Delivery Hub",
                description=f"Delivery re-attempt scheduled for {order.rescheduled_for} following voice call confirmation.",
            )
            if db:
                db.add(milestone)

        elif action == "initiate_cancellation":
            order.order_status = "CANCELLED_RTO"
            order.resolution_notes = f"Customer requested cancellation during recovery call. Initiating Return to Origin (RTO). {notes or ''}"
            
            milestone = ShipmentTracking(
                order_id=order.id,
                status="RTO_INITIATED",
                location=f"{order.city} Delivery Hub",
                description="Return to Origin (RTO) initiated. Package returning to fulfillment warehouse.",
            )
            if db:
                db.add(milestone)

        elif action == "flag_address_correction":
            order.order_status = "ADDRESS_UPDATE_REQUIRED"
            if updated_address:
                order.delivery_address = updated_address
            order.resolution_notes = f"Address updated by customer: {updated_address or 'Pending verification'}. {notes or ''}"
            
            milestone = ShipmentTracking(
                order_id=order.id,
                status="ADDRESS_UPDATED",
                location=f"{order.city} Delivery Hub",
                description=f"Delivery address updated to '{order.delivery_address}'. Package held for next delivery cycle.",
            )
            if db:
                db.add(milestone)

        elif action == "escalate_to_human":
            order.order_status = "HUMAN_ESCALATION"
            order.resolution_notes = f"Customer requested human agent escalation. Priority support ticket raised. {notes or ''}"
            
            milestone = ShipmentTracking(
                order_id=order.id,
                status="ESCALATED_SUPPORT",
                location=f"{order.city} Support Center",
                description="Order escalated to senior customer success supervisor for high-touch resolution.",
            )
            if db:
                db.add(milestone)

        else:
            order.order_status = "DELIVERY_FAILED_NDR"
            order.resolution_notes = f"Action: {action}. {notes or ''}"

        if db:
            db.commit()
            db.refresh(order)

        return order.to_dict()


recovery_bridge = RecoveryBridge()
