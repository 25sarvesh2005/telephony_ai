from datetime import datetime, timezone
from typing import Any, Dict, List
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from d2c_app.database import D2CBase


def utcnow():
    return datetime.now(timezone.utc)


class Customer(D2CBase):
    __tablename__ = "d2c_customers"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String(64), unique=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(32), nullable=False, index=True)
    default_address = Column(Text, nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    pincode = Column(String(20), nullable=True)
    total_orders = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow)

    orders = relationship("D2COrder", back_populates="customer")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "customer_id": self.customer_id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "default_address": self.default_address,
            "city": self.city,
            "state": self.state,
            "pincode": self.pincode,
            "total_orders": self.total_orders,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Product(D2CBase):
    __tablename__ = "d2c_products"

    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String(64), unique=True, index=True, nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), index=True, nullable=False)
    price = Column(Float, nullable=False)
    compare_at_price = Column(Float, nullable=True)
    stock_quantity = Column(Integer, default=100)
    image_url = Column(String(512), nullable=True)
    tags = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "sku": self.sku,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "price": self.price,
            "compare_at_price": self.compare_at_price,
            "stock_quantity": self.stock_quantity,
            "image_url": self.image_url,
            "tags": self.tags.split(",") if self.tags else [],
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Cart(D2CBase):
    __tablename__ = "d2c_carts"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(128), unique=True, index=True, nullable=False)
    customer_phone = Column(String(32), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    items = relationship("CartItem", back_populates="cart", cascade="all, delete-orphan")

    def to_dict(self) -> Dict[str, Any]:
        items_list = [item.to_dict() for item in self.items]
        subtotal = sum(i["subtotal"] for i in items_list)
        return {
            "session_id": self.session_id,
            "customer_phone": self.customer_phone,
            "items": items_list,
            "subtotal": round(subtotal, 2),
            "item_count": sum(i["quantity"] for i in items_list),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class CartItem(D2CBase):
    __tablename__ = "d2c_cart_items"

    id = Column(Integer, primary_key=True, index=True)
    cart_id = Column(Integer, ForeignKey("d2c_carts.id"), nullable=False)
    product_sku = Column(String(64), nullable=False)
    product_title = Column(String(255), nullable=False)
    unit_price = Column(Float, nullable=False)
    quantity = Column(Integer, default=1)
    image_url = Column(String(512), nullable=True)

    cart = relationship("Cart", back_populates="items")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "sku": self.product_sku,
            "title": self.product_title,
            "unit_price": self.unit_price,
            "quantity": self.quantity,
            "subtotal": round(self.unit_price * self.quantity, 2),
            "image_url": self.image_url,
        }


class D2COrder(D2CBase):
    __tablename__ = "d2c_orders"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String(64), unique=True, index=True, nullable=False)
    customer_id = Column(Integer, ForeignKey("d2c_customers.id"), nullable=True)
    
    # Customer Details
    customer_name = Column(String(255), nullable=False)
    customer_phone = Column(String(32), nullable=False, index=True)
    customer_email = Column(String(255), nullable=True)
    
    # Shipping Address
    delivery_address = Column(Text, nullable=False)
    city = Column(String(100), nullable=False)
    state = Column(String(100), nullable=True)
    pincode = Column(String(20), nullable=False)
    
    # Financials
    subtotal = Column(Float, nullable=False)
    shipping_fee = Column(Float, default=0.0)
    discount_amount = Column(Float, default=0.0)
    total_amount = Column(Float, nullable=False)
    currency = Column(String(10), default="INR")
    
    # Payment & Fulfillment
    payment_method = Column(String(20), default="COD")  # "COD" or "PREPAID"
    payment_status = Column(String(30), default="PENDING")  # "PENDING", "PAID", "REFUNDED"
    
    # Order Status Lifecycle:
    # "CONFIRMED" -> "SHIPPED" -> "OUT_FOR_DELIVERY" -> "DELIVERED"
    # Or in failure: "DELIVERY_FAILED_NDR" -> "CALL_IN_PROGRESS" -> "RESCHEDULED" / "CANCELLED_RTO" / "ADDRESS_UPDATED"
    order_status = Column(String(50), default="CONFIRMED", index=True)
    delivery_attempts = Column(Integer, default=0)
    
    # Logistics
    courier_partner = Column(String(50), default="Bluedart Express")  # "Bluedart", "Delhivery", "Shiprocket"
    awb_number = Column(String(64), nullable=True, index=True)
    expected_delivery_date = Column(String(64), nullable=True)
    rescheduled_for = Column(String(128), nullable=True)
    
    # Operational notes / NDR context
    ndr_reason = Column(String(255), nullable=True)
    resolution_notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    customer = relationship("Customer", back_populates="orders")
    items = relationship("D2COrderItem", back_populates="order", cascade="all, delete-orphan")
    ndr_tickets = relationship("NDRTicket", back_populates="order", cascade="all, delete-orphan")
    tracking_milestones = relationship("ShipmentTracking", back_populates="order", cascade="all, delete-orphan")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "customer_name": self.customer_name,
            "customer_phone": self.customer_phone,
            "customer_email": self.customer_email,
            "delivery_address": self.delivery_address,
            "city": self.city,
            "state": self.state,
            "pincode": self.pincode,
            "subtotal": self.subtotal,
            "shipping_fee": self.shipping_fee,
            "discount_amount": self.discount_amount,
            "total_amount": self.total_amount,
            "currency": self.currency,
            "payment_method": self.payment_method,
            "payment_status": self.payment_status,
            "order_status": self.order_status,
            "delivery_attempts": self.delivery_attempts,
            "courier_partner": self.courier_partner,
            "awb_number": self.awb_number,
            "expected_delivery_date": self.expected_delivery_date,
            "rescheduled_for": self.rescheduled_for,
            "ndr_reason": self.ndr_reason,
            "resolution_notes": self.resolution_notes,
            "items": [item.to_dict() for item in self.items],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class D2COrderItem(D2CBase):
    __tablename__ = "d2c_order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("d2c_orders.id"), nullable=False)
    product_sku = Column(String(64), nullable=False)
    product_title = Column(String(255), nullable=False)
    unit_price = Column(Float, nullable=False)
    quantity = Column(Integer, default=1)
    total_price = Column(Float, nullable=False)
    image_url = Column(String(512), nullable=True)

    order = relationship("D2COrder", back_populates="items")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sku": self.product_sku,
            "title": self.product_title,
            "unit_price": self.unit_price,
            "quantity": self.quantity,
            "total_price": self.total_price,
            "image_url": self.image_url,
        }


class NDRTicket(D2CBase):
    """Tracks courier Non-Delivery Reports and automated AI recovery dispatches."""
    __tablename__ = "d2c_ndr_tickets"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("d2c_orders.id"), nullable=False)
    order_reference = Column(String(64), index=True, nullable=False)
    attempt_number = Column(Integer, default=1)
    failure_code = Column(String(64), default="CUSTOMER_UNAVAILABLE")  # "CUSTOMER_UNAVAILABLE", "WRONG_ADDRESS", "REJECTED_ON_ARRIVAL"
    courier_remarks = Column(String(512), nullable=True)
    
    # Recovery Status
    recovery_status = Column(String(50), default="PENDING_CALL")  # "PENDING_CALL", "CALL_IN_PROGRESS", "RECOVERED_RESCHEDULED", "CANCELLED_RTO", "ADDRESS_UPDATED", "ESCALATED"
    telephony_call_id = Column(String(128), nullable=True)
    customer_response_intent = Column(String(64), nullable=True)
    rescheduled_date = Column(String(128), nullable=True)
    updated_shipping_address = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=utcnow)
    resolved_at = Column(DateTime, nullable=True)

    order = relationship("D2COrder", back_populates="ndr_tickets")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "order_reference": self.order_reference,
            "attempt_number": self.attempt_number,
            "failure_code": self.failure_code,
            "courier_remarks": self.courier_remarks,
            "recovery_status": self.recovery_status,
            "telephony_call_id": self.telephony_call_id,
            "customer_response_intent": self.customer_response_intent,
            "rescheduled_date": self.rescheduled_date,
            "updated_shipping_address": self.updated_shipping_address,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


class ShipmentTracking(D2CBase):
    """Milestone events in courier logistics."""
    __tablename__ = "d2c_shipment_tracking"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("d2c_orders.id"), nullable=False)
    status = Column(String(64), nullable=False)  # "ORDER_PLACED", "PICKED_UP", "IN_TRANSIT", "OUT_FOR_DELIVERY", "NDR_TRIGGERED", "RESCHEDULED", "DELIVERED", "RTO_INITIATED"
    location = Column(String(128), default="Hub Hub, Logistics Centre")
    description = Column(String(512), nullable=False)
    timestamp = Column(DateTime, default=utcnow)

    order = relationship("D2COrder", back_populates="tracking_milestones")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "location": self.location,
            "description": self.description,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }

