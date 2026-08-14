from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Product Schemas
# ---------------------------------------------------------------------------
class ProductCreate(BaseModel):
    sku: str
    title: str
    description: Optional[str] = None
    category: str
    price: float
    compare_at_price: Optional[float] = None
    stock_quantity: int = 100
    image_url: Optional[str] = None
    tags: Optional[str] = None


class ProductResponse(BaseModel):
    id: int
    sku: str
    title: str
    description: Optional[str] = None
    category: str
    price: float
    compare_at_price: Optional[float] = None
    stock_quantity: int
    image_url: Optional[str] = None
    tags: List[str] = []
    is_active: bool


# ---------------------------------------------------------------------------
# Cart Schemas
# ---------------------------------------------------------------------------
class CartItemAdd(BaseModel):
    session_id: str
    sku: str
    quantity: int = 1


class CartItemUpdate(BaseModel):
    quantity: int


class CartItemResponse(BaseModel):
    id: int
    sku: str
    title: str
    unit_price: float
    quantity: int
    subtotal: float
    image_url: Optional[str] = None


class CartResponse(BaseModel):
    session_id: str
    customer_phone: Optional[str] = None
    items: List[CartItemResponse] = []
    subtotal: float
    item_count: int


# ---------------------------------------------------------------------------
# Checkout & Order Schemas
# ---------------------------------------------------------------------------
class CheckoutRequest(BaseModel):
    session_id: Optional[str] = None
    customer_name: str
    customer_phone: str
    customer_email: Optional[str] = None
    delivery_address: str
    city: str
    state: Optional[str] = "Karnataka"
    pincode: str
    payment_method: str = "COD"  # "COD" or "PREPAID"
    # Direct items if not using session cart
    items: Optional[List[Dict[str, Any]]] = None


class OrderItemResponse(BaseModel):
    sku: str
    title: str
    unit_price: float
    quantity: int
    total_price: float
    image_url: Optional[str] = None


class OrderResponse(BaseModel):
    order_id: str
    customer_name: str
    customer_phone: str
    customer_email: Optional[str] = None
    delivery_address: str
    city: str
    state: Optional[str] = None
    pincode: str
    subtotal: float
    shipping_fee: float
    discount_amount: float
    total_amount: float
    currency: str
    payment_method: str
    payment_status: str
    order_status: str
    delivery_attempts: int
    courier_partner: Optional[str] = None
    awb_number: Optional[str] = None
    expected_delivery_date: Optional[str] = None
    rescheduled_for: Optional[str] = None
    ndr_reason: Optional[str] = None
    resolution_notes: Optional[str] = None
    items: List[OrderItemResponse] = []
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ---------------------------------------------------------------------------
# Logistics & NDR Event Schemas
# ---------------------------------------------------------------------------
class CourierDispatchRequest(BaseModel):
    order_id: str
    courier_partner: str = "Bluedart Express"


class OutForDeliveryRequest(BaseModel):
    order_id: str
    courier_name: Optional[str] = "Delivery Executive (Ramesh Kumar)"


class NDRTriggerRequest(BaseModel):
    """Simulates a delivery failure reported by courier (NDR event)."""
    order_id: str
    failure_code: str = "CUSTOMER_UNAVAILABLE"  # "CUSTOMER_UNAVAILABLE", "WRONG_ADDRESS", "REJECTED_ON_ARRIVAL", "PHONE_UNREACHABLE"
    courier_remarks: Optional[str] = "Customer was not reachable at the delivery address during morning round."
    auto_trigger_call: bool = True
    telephony_provider: Optional[str] = "eigi"


class NDRResolutionSyncRequest(BaseModel):
    """Payload received from AI Telephony Recovery Engine when call completes."""
    order_id: str
    action: str  # "reschedule", "initiate_cancellation", "flag_address_correction", "escalate_to_human", "retry_call"
    reschedule_datetime: Optional[str] = None
    updated_address: Optional[str] = None
    customer_notes: Optional[str] = None
    call_id: Optional[str] = None


# ---------------------------------------------------------------------------
# D2C Analytics Schemas
# ---------------------------------------------------------------------------
class D2CAnalyticsResponse(BaseModel):
    total_orders: int
    gross_merchandise_value: float
    cod_orders: int
    prepaid_orders: int
    delivered_orders: int
    ndr_failed_orders: int
    recovered_orders: int
    rto_cancelled_orders: int
    recovery_rate_pct: float
    estimated_rto_cost_saved: float
