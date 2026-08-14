import datetime
import random
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from d2c_app.models import D2COrder, NDRTicket, ShipmentTracking
from d2c_app.services.recovery_bridge import recovery_bridge


class CourierEngine:
    """Simulates real-world courier partner logistics (Shiprocket / Delhivery / Bluedart)."""

    def generate_awb(self, courier_name: str = "Bluedart Express") -> str:
        prefix = "BLUEDART" if "blue" in courier_name.lower() else ("DELHIVERY" if "delhi" in courier_name.lower() else "EXP")
        num = random.randint(10000000, 99999999)
        return f"{prefix}-{num}"

    def dispatch_order(self, order: D2COrder, courier_partner: str, db: Session) -> D2COrder:
        """Dispatches an order, assigns AWB, and records tracking milestones."""
        order.awb_number = self.generate_awb(courier_partner)
        order.courier_partner = courier_partner
        order.order_status = "SHIPPED"
        
        # Expected delivery within 2 days
        expected = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=2)
        order.expected_delivery_date = expected.strftime("%d %b %Y, by 8:00 PM")

        # Initial tracking milestones
        m1 = ShipmentTracking(
            order_id=order.id,
            status="PICKED_UP",
            location="Fulfillment Center, Bengaluru",
            description=f"Package packed and handed over to {courier_partner}. AWB: {order.awb_number}",
        )
        m2 = ShipmentTracking(
            order_id=order.id,
            status="IN_TRANSIT",
            location="Mother Hub, Bengaluru",
            description="Package sorted and dispatched to destination delivery center.",
        )
        db.add(m1)
        db.add(m2)
        db.commit()
        db.refresh(order)
        return order

    def mark_out_for_delivery(self, order: D2COrder, courier_name: str, db: Session) -> D2COrder:
        """Marks shipment out for delivery by courier delivery executive."""
        order.order_status = "OUT_FOR_DELIVERY"
        order.delivery_attempts = (order.delivery_attempts or 0) + 1
        
        milestone = ShipmentTracking(
            order_id=order.id,
            status="OUT_FOR_DELIVERY",
            location=f"{order.city} Hub",
            description=f"Out for delivery by {courier_name}. Delivery attempt #{order.delivery_attempts}.",
        )
        db.add(milestone)
        db.commit()
        db.refresh(order)
        return order

    async def report_delivery_failure(
        self,
        order: D2COrder,
        failure_code: str,
        remarks: Optional[str],
        auto_call: bool,
        telephony_provider: Optional[str],
        db: Session,
    ) -> Dict[str, Any]:
        """
        Reports a Non-Delivery Report (NDR) failure event and triggers the AI voice recovery workflow.
        """
        order.order_status = "DELIVERY_FAILED_NDR"
        order.ndr_reason = remarks or f"Delivery attempt failed: {failure_code}"

        # 1. Create NDR Ticket
        ndr = NDRTicket(
            order_id=order.id,
            order_reference=order.order_id,
            attempt_number=order.delivery_attempts or 1,
            failure_code=failure_code,
            courier_remarks=remarks,
            recovery_status="PENDING_CALL",
        )
        db.add(ndr)

        # 2. Add Tracking Milestone
        milestone = ShipmentTracking(
            order_id=order.id,
            status="NDR_TRIGGERED",
            location=f"{order.city} Hub",
            description=f"Delivery attempt #{order.delivery_attempts} unsuccessful. Reason: {order.ndr_reason}. Initiating automated AI voice recovery.",
        )
        db.add(milestone)
        db.commit()
        db.refresh(order)
        db.refresh(ndr)

        call_result = None
        if auto_call:
            order.order_status = "CALL_IN_PROGRESS"
            ndr.recovery_status = "CALL_IN_PROGRESS"
            db.commit()

            # Trigger AI Voice Call via Recovery Bridge
            call_result = await recovery_bridge.trigger_recovery_call(
                order=order,
                telephony_provider=telephony_provider,
            )
            if call_result and call_result.get("call_info"):
                ndr.telephony_call_id = call_result["call_info"].get("call_id")
                db.commit()

        return {
            "order": order.to_dict(),
            "ndr_ticket": ndr.to_dict(),
            "call_dispatch": call_result,
        }

    def mark_delivered(self, order: D2COrder, db: Session) -> D2COrder:
        """Marks package as successfully delivered to the customer."""
        order.order_status = "DELIVERED"
        if order.payment_method == "COD":
            order.payment_status = "PAID"
        
        milestone = ShipmentTracking(
            order_id=order.id,
            status="DELIVERED",
            location=f"{order.city}",
            description="Package delivered successfully to the customer. COD payment collected.",
        )
        db.add(milestone)
        db.commit()
        db.refresh(order)
        return order


courier_engine = CourierEngine()
