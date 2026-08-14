import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from d2c_app.models import Customer, D2COrder

logger = logging.getLogger("d2c_threshold_bot")


class ThresholdBot:
    """
    Intelligent Risk & Threshold Policy Bot for D2C Orders.
    Evaluates COD risk, delivery attempt thresholds, address quality, and repeat RTO patterns.
    """

    # Configurable Threshold Rules
    MAX_ALLOWED_DELIVERY_ATTEMPTS: int = 3
    HIGH_COD_VALUE_THRESHOLD: float = 3000.0
    MIN_ADDRESS_LENGTH: int = 15
    MAX_HISTORICAL_RTOS_ALLOWED: int = 2

    def evaluate_order(self, order: D2COrder, db: Optional[Session] = None) -> Dict[str, Any]:
        """
        Evaluates an order against threshold policies and returns risk assessment & flags.
        """
        flags: List[str] = []
        risk_score: int = 0
        recommendations: List[str] = []

        # 1. Delivery Attempt Threshold Rule
        attempts = order.delivery_attempts or 0
        if attempts >= self.MAX_ALLOWED_DELIVERY_ATTEMPTS:
            flags.append("MAX_ATTEMPTS_EXCEEDED")
            risk_score += 45
            recommendations.append(
                f"Delivery has failed {attempts} times (Threshold: {self.MAX_ALLOWED_DELIVERY_ATTEMPTS}). Block autonomous re-attempt and require supervisor approval."
            )
        elif attempts == 2:
            flags.append("CRITICAL_SECOND_ATTEMPT_FAILED")
            risk_score += 25
            recommendations.append("Second attempt failed. Next failure will trigger automatic RTO.")

        # 2. High COD Value Threshold Rule
        if order.payment_method == "COD" and order.total_amount >= self.HIGH_COD_VALUE_THRESHOLD:
            flags.append("HIGH_COD_VALUE_RISK")
            risk_score += 25
            recommendations.append(
                f"High-value COD parcel (₹{order.total_amount:.2f} >= ₹{self.HIGH_COD_VALUE_THRESHOLD:.2f}). Priority recovery call required to prevent freight loss."
            )

        # 3. Address Quality & Completeness Rule
        addr = (order.delivery_address or "").strip()
        if len(addr) < self.MIN_ADDRESS_LENGTH or not any(char.isdigit() for char in addr):
            flags.append("INCOMPLETE_ADDRESS_RISK")
            risk_score += 20
            recommendations.append("Address appears incomplete (missing flat/house number). Flag for WhatsApp address verification.")

        # 4. Repeat Customer Historical RTO Rule
        if db and order.customer_phone:
            past_rtos = db.query(D2COrder).filter(
                D2COrder.customer_phone == order.customer_phone,
                D2COrder.order_status == "CANCELLED_RTO",
                D2COrder.order_id != order.order_id
            ).count()

            if past_rtos >= self.MAX_HISTORICAL_RTOS_ALLOWED:
                flags.append("REPEAT_SERIAL_RTO_BUYER")
                risk_score += 40
                recommendations.append(
                    f"Buyer has {past_rtos} past RTO cancellations. Highly recommend converting future orders to Prepaid only."
                )

        # Cap risk score between 0 and 100
        risk_score = min(100, risk_score)
        risk_level = "HIGH" if risk_score >= 60 else ("MEDIUM" if risk_score >= 30 else "LOW")
        should_block_auto_dispatch = risk_score >= 60

        result = {
            "order_id": order.order_id,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "is_flagged": len(flags) > 0,
            "flags": flags,
            "recommendations": recommendations,
            "should_block_auto_dispatch": should_block_auto_dispatch,
        }

        if len(flags) > 0:
            logger.info(f"🚩 [ThresholdBot] Order #{order.order_id} flagged: Level={risk_level}, Score={risk_score}, Flags={flags}")

        return result


threshold_bot = ThresholdBot()
