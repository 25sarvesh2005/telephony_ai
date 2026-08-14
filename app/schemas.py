from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field


class ExtractedIntent(BaseModel):
    order_id: Optional[str] = None
    call_outcome: Literal["reached", "no_answer", "voicemail", "busy", "failed"] = "reached"
    customer_intent: Literal["reschedule", "cancel", "wrong_address", "unclear", "escalate_human", "no_answer"] = "unclear"
    reschedule_datetime: Optional[str] = None
    updated_address: Optional[str] = None
    notes: Optional[str] = None
    confidence: Optional[float] = Field(default=1.0, ge=0.0, le=1.0)


class EigiWebhookPayload(BaseModel):
    call_id: str
    order_id: Optional[str] = None
    to_number: Optional[str] = None
    duration_seconds: Optional[int] = 0
    status: Optional[str] = "completed"
    recording_url: Optional[str] = None
    transcript: Optional[str] = None
    extracted_intent: Optional[Union[ExtractedIntent, Dict[str, Any]]] = None
    variables: Optional[Dict[str, Any]] = None


class TriggerCallRequest(BaseModel):
    order_id: str
    phone_override: Optional[str] = None
    custom_prompt_variables: Optional[Dict[str, Any]] = None


class SimulateCallRequest(BaseModel):
    order_id: str
    scenario: Literal[
        "reschedule",
        "cancel",
        "wrong_address",
        "escalate_human",
        "unclear",
        "no_answer",
        "voicemail",
        "custom"
    ] = "reschedule"
    custom_transcript: Optional[str] = None
    custom_intent: Optional[str] = None
    reschedule_datetime: Optional[str] = None
    updated_address: Optional[str] = None
    notes: Optional[str] = None


class ResolutionDecision(BaseModel):
    action: str
    reason: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    order_id: str
    call_id: Optional[str] = None


class OrderCreate(BaseModel):
    order_id: str
    customer_name: str
    customer_phone: str
    amount: float
    currency: str = "INR"
    payment_method: str = "COD"
    delivery_attempts: int = 1
    delivery_address: Optional[str] = None
    city: Optional[str] = None
    notes: Optional[str] = None


class OrderResponse(BaseModel):
    order_id: str
    customer_name: str
    customer_phone: str
    amount: float
    currency: str
    payment_method: str
    status: str
    delivery_attempts: int
    delivery_address: Optional[str]
    city: Optional[str]
    notes: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]
