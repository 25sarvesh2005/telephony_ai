import json
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from app.database import Base


class Order(Base):
    __tablename__ = "orders"

    order_id = Column(String(50), primary_key=True, index=True)
    customer_name = Column(String(100), nullable=False)
    customer_phone = Column(String(30), nullable=False, index=True)
    amount = Column(Float, nullable=False, default=0.0)
    currency = Column(String(10), default="INR")
    payment_method = Column(String(20), default="COD")
    status = Column(String(50), default="DELIVERY_FAILED", index=True)
    delivery_attempts = Column(Integer, default=1)
    delivery_address = Column(Text, nullable=True)
    city = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    call_logs = relationship("CallLog", back_populates="order", cascade="all, delete-orphan")
    resolutions = relationship("Resolution", back_populates="order", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "order_id": self.order_id,
            "customer_name": self.customer_name,
            "customer_phone": self.customer_phone,
            "amount": self.amount,
            "currency": self.currency,
            "payment_method": self.payment_method,
            "status": self.status,
            "delivery_attempts": self.delivery_attempts,
            "delivery_address": self.delivery_address,
            "city": self.city,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class CallLog(Base):
    __tablename__ = "call_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    call_id = Column(String(100), unique=True, index=True, nullable=False)
    order_id = Column(String(50), ForeignKey("orders.order_id"), nullable=False, index=True)
    duration_seconds = Column(Integer, default=0)
    call_outcome = Column(String(50), default="reached")  # reached, no_answer, voicemail, busy, failed
    transcript = Column(Text, nullable=True)
    recording_url = Column(String(500), nullable=True)
    extracted_intent_json = Column(Text, nullable=True)  # JSON-encoded string
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    order = relationship("Order", back_populates="call_logs")

    @property
    def extracted_intent(self):
        if self.extracted_intent_json:
            try:
                return json.loads(self.extracted_intent_json)
            except Exception:
                return {}
        return {}

    @extracted_intent.setter
    def extracted_intent(self, value):
        if value is not None:
            self.extracted_intent_json = json.dumps(value)
        else:
            self.extracted_intent_json = None

    def to_dict(self):
        return {
            "id": self.id,
            "call_id": self.call_id,
            "order_id": self.order_id,
            "duration_seconds": self.duration_seconds,
            "call_outcome": self.call_outcome,
            "transcript": self.transcript,
            "recording_url": self.recording_url,
            "extracted_intent": self.extracted_intent,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Resolution(Base):
    __tablename__ = "resolutions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    call_id = Column(String(100), nullable=True, index=True)
    order_id = Column(String(50), ForeignKey("orders.order_id"), nullable=False, index=True)
    decided_action = Column(String(50), nullable=False)  # reschedule, initiate_cancellation, flag_address_correction, escalate_to_human, retry_call
    action_payload_json = Column(Text, nullable=True)
    status = Column(String(30), default="EXECUTED")  # EXECUTED, PENDING, FAILED
    outcome = Column(Text, nullable=True)
    executed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    order = relationship("Order", back_populates="resolutions")

    @property
    def action_payload(self):
        if self.action_payload_json:
            try:
                return json.loads(self.action_payload_json)
            except Exception:
                return {}
        return {}

    @action_payload.setter
    def action_payload(self, value):
        if value is not None:
            self.action_payload_json = json.dumps(value)
        else:
            self.action_payload_json = None

    def to_dict(self):
        return {
            "id": self.id,
            "call_id": self.call_id,
            "order_id": self.order_id,
            "decided_action": self.decided_action,
            "action_payload": self.action_payload,
            "status": self.status,
            "outcome": self.outcome,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
        }
