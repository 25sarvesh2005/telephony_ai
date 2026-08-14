import logging
import os
import re
import uuid
from typing import Any, Dict, List, Optional
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db, init_db
from app.models import CallLog, Order, Resolution
from app.schemas import (
    EigiWebhookPayload,
    ExtractedIntent,
    OrderCreate,
    OrderResponse,
    ResolutionDecision,
    SimulateCallRequest,
    TriggerCallRequest,
)
from app.services.eigi_client import eigi_client
from app.services.extractor import intent_extractor
from app.services.operations_agent import operations_agent
from app.services.resolution_agent import resolution_agent

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("recovery_engine")

# Initialize database tables on startup
init_db()

app = FastAPI(
    title="AI Commerce Recovery Engine (eigi.ai)",
    description="Automated voice telephony orchestrator for COD failed deliveries and cart recovery",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for Voice AI
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Mount D2C Static Files & Routers
d2c_static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "d2c_app", "static"))
if os.path.exists(d2c_static_dir):
    app.mount("/d2c/static", StaticFiles(directory=d2c_static_dir), name="d2c_static")

try:
    from d2c_app.main import d2c_app
    from d2c_app.routes.products import router as d2c_prod
    from d2c_app.routes.cart import router as d2c_cart
    from d2c_app.routes.checkout import router as d2c_chk
    from d2c_app.routes.orders import router as d2c_ord
    from d2c_app.routes.logistics import router as d2c_log
    from d2c_app.routes.analytics import router as d2c_ana

    app.include_router(d2c_prod, prefix="/api/d2c")
    app.include_router(d2c_cart, prefix="/api/d2c")
    app.include_router(d2c_chk, prefix="/api/d2c")
    app.include_router(d2c_ord, prefix="/api/d2c")
    app.include_router(d2c_log, prefix="/api/d2c")
    app.include_router(d2c_ana, prefix="/api/d2c")
    app.mount("/d2c", d2c_app)
except Exception as e:
    logger.warning(f"D2C App Mount Note: {e}")


@app.get("/d2c", include_in_schema=False)
@app.get("/d2c/", include_in_schema=False)
async def serve_d2c_root():
    index_file = os.path.join(d2c_static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "D2C Storefront is loading..."}


@app.get("/", include_in_schema=False)
async def serve_dashboard():
    """Serves the interactive Recovery Engine Web Dashboard."""
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "AI Commerce Recovery Engine API is running. UI assets initializing..."}


# ---------------------------------------------------------------------------
# STEP 5: Trigger Outbound Call
# ---------------------------------------------------------------------------
@app.post("/trigger-call", summary="Trigger outbound recovery call via eigi.ai")
async def trigger_call(req: TriggerCallRequest, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.order_id == req.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {req.order_id} not found")

    target_phone = req.phone_override or order.customer_phone

    # Variables injected into eigi.ai voice agent prompt template
    prompt_variables = {
        "order_id": order.order_id,
        "customer_name": order.customer_name,
        "amount": f"{order.currency} {order.amount:.2f}",
        "merchant_name": settings.MERCHANT_NAME,
        "delivery_attempts": order.delivery_attempts,
        "city": order.city or "your area",
    }
    if req.custom_prompt_variables:
        prompt_variables.update(req.custom_prompt_variables)

    # Update order state to indicate call in progress
    order.status = "CALL_IN_PROGRESS"
    order.notes = f"Outbound call initiated to {target_phone} via eigi.ai voice agent."
    db.commit()

    # Call eigi.ai API
    call_result = await eigi_client.start_call(
        to_number=target_phone,
        variables=prompt_variables,
        agent_id=settings.EIGI_AGENT_ID,
    )

    return {
        "status": "success",
        "order_id": order.order_id,
        "customer_phone": target_phone,
        "call_info": call_result,
    }


# ---------------------------------------------------------------------------
# STEP 3: Webhook Receiver for eigi.ai Completed Calls
# ---------------------------------------------------------------------------
@app.post("/webhooks/eigi/call-completed", summary="Webhook receiver for eigi.ai completed calls")
async def eigi_call_completed_webhook(payload: EigiWebhookPayload, db: Session = Depends(get_db)):
    logger.info(f"[Webhook Received] Call ID: {payload.call_id}, Order ID: {payload.order_id}")

    # Resolve order_id
    order_id = payload.order_id
    if not order_id and payload.variables:
        order_id = payload.variables.get("order_id")

    order = None
    if order_id:
        order = db.query(Order).filter(Order.order_id == order_id).first()

    # Step 2 & 6: Structured intent extraction (payload or transcript fallback)
    extracted: ExtractedIntent = intent_extractor.extract_from_payload(
        payload_intent=payload.extracted_intent,
        transcript=payload.transcript,
        order_id=order_id,
    )

    # Check for existing call log or create new
    existing_log = db.query(CallLog).filter(CallLog.call_id == payload.call_id).first()
    if not existing_log:
        call_log = CallLog(
            call_id=payload.call_id,
            order_id=order_id or "UNKNOWN",
            duration_seconds=payload.duration_seconds or 45,
            call_outcome=extracted.call_outcome,
            transcript=payload.transcript,
            recording_url=payload.recording_url or "https://actions.google.com/sounds/v1/telephones/phone_calling.ogg",
        )
        call_log.extracted_intent = extracted.model_dump()
        db.add(call_log)
        db.commit()
        db.refresh(call_log)
    else:
        call_log = existing_log

    # Step 6: Run Resolution Agent Decision Engine
    decision: ResolutionDecision = resolution_agent.decide(
        extracted_intent=extracted,
        order=order,
        call_id=payload.call_id,
    )

    # Step 7: Run Operations Agent (Execute & Log Action)
    resolution: Resolution = operations_agent.execute(decision=decision, db=db)

    return {
        "status": "ok",
        "call_id": payload.call_id,
        "order_id": order_id,
        "extracted_intent": extracted.model_dump(),
        "decision": {
            "action": decision.action,
            "reason": decision.reason,
            "payload": decision.payload,
        },
        "resolution_id": resolution.id,
        "resolution_outcome": resolution.outcome,
    }


# ---------------------------------------------------------------------------
# STEP 8: Simulator Sandbox for Offline Testing & Demos
# ---------------------------------------------------------------------------
@app.post("/simulate-call", summary="Simulate customer call interaction and run end-to-end recovery loop")
async def simulate_call(req: SimulateCallRequest, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.order_id == req.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {req.order_id} not found")

    sim_call_id = f"sim_{uuid.uuid4().hex[:10]}"
    customer_first_name = order.customer_name.split()[0]

    # Pre-crafted realistic transcripts and intent structures for different test scenarios
    scenarios_data = {
        "reschedule": {
            "call_outcome": "reached",
            "intent": "reschedule",
            "reschedule_datetime": req.reschedule_datetime or "Tomorrow at 6:00 PM",
            "transcript": (
                f"Agent: Hello, this is an automated call on behalf of {settings.MERCHANT_NAME} regarding order #{order.order_id}. "
                f"This call is recorded for quality purposes. Our courier attempted delivery of your COD package today, but was unable to reach you. "
                f"Would you like to reschedule or cancel?\n"
                f"Customer ({customer_first_name}): Hi! Sorry, I was stuck at office and wasn't home. Can you please deliver tomorrow evening after 6 PM?\n"
                f"Agent: Absolutely! I have scheduled delivery for tomorrow evening after 6:00 PM. Thank you for shopping with {settings.MERCHANT_NAME}!"
            ),
            "notes": "Customer wasn't home, requested next day evening delivery after 6 PM.",
        },
        "cancel": {
            "call_outcome": "reached",
            "intent": "cancel",
            "reschedule_datetime": None,
            "transcript": (
                f"Agent: Hello, this is an automated call on behalf of {settings.MERCHANT_NAME} regarding order #{order.order_id}. "
                f"This call is recorded for quality purposes. Our delivery partner could not reach you today. Would you like to reschedule delivery?\n"
                f"Customer ({customer_first_name}): No, please cancel this order. The delivery took too long and I already bought the item from a local retail store.\n"
                f"Agent: Understood. I will initiate the cancellation and Return to Origin for order #{order.order_id}. Have a great day."
            ),
            "notes": "Customer cancelled due to delivery delay; bought locally.",
        },
        "wrong_address": {
            "call_outcome": "reached",
            "intent": "wrong_address",
            "reschedule_datetime": None,
            "updated_address": req.updated_address or "Flat 402, Sunshine Heights, Koramangala 4th Block",
            "transcript": (
                f"Agent: Hello, calling from {settings.MERCHANT_NAME} regarding order #{order.order_id}. Delivery was unsuccessful today. "
                f"Would you like to reschedule?\n"
                f"Customer ({customer_first_name}): The delivery guy went to my old office address! My new address is Flat 402, Sunshine Heights, Koramangala.\n"
                f"Agent: Got it. I've noted down your updated address and put delivery on hold until our team verifies the new location."
            ),
            "notes": "Customer moved to new address, provided updated location details.",
        },
        "escalate_human": {
            "call_outcome": "reached",
            "intent": "escalate_human",
            "reschedule_datetime": None,
            "transcript": (
                f"Agent: Hello, calling from {settings.MERCHANT_NAME} regarding order #{order.order_id}. "
                f"Delivery was unsuccessful today. Can we help you reschedule?\n"
                f"Customer ({customer_first_name}): Listen, I ordered 3 items and only 1 box was brought, plus the box was damaged! Let me speak to a real human manager right now.\n"
                f"Agent: I apologize for the inconvenience. I am creating a priority escalation ticket for a senior support specialist to call you back shortly."
            ),
            "notes": "Customer reported damaged parcel and missing items; requested human supervisor.",
        },
        "no_answer": {
            "call_outcome": "no_answer",
            "intent": "no_answer",
            "reschedule_datetime": None,
            "transcript": "System: Outbound call placed to customer. Phone rang for 45 seconds. Customer did not pick up. Call disconnected.",
            "notes": "No answer after multiple rings.",
        },
        "voicemail": {
            "call_outcome": "voicemail",
            "intent": "no_answer",
            "reschedule_datetime": None,
            "transcript": "Voicemail System: You have reached the voicemail of the customer. Please leave a message after the beep. [Tone]. Agent: Automated message from ShopAura...",
            "notes": "Call routed to automated voicemail box.",
        },
        "unclear": {
            "call_outcome": "reached",
            "intent": "unclear",
            "reschedule_datetime": None,
            "transcript": (
                f"Agent: Hello, calling from {settings.MERCHANT_NAME} regarding order #{order.order_id}. Delivery failed today. Would you like to reschedule?\n"
                f"Customer ({customer_first_name}): Uh... I don't know, maybe? Let me check with my brother who ordered it... hello? Can you hear me?\n"
                f"Agent: I will make a note for our team to follow up with you. Thank you."
            ),
            "notes": "Customer uncertain about order placement; ambiguous response.",
        },
    }

    scenario_cfg = scenarios_data.get(req.scenario, scenarios_data["reschedule"])
    transcript = req.custom_transcript or scenario_cfg["transcript"]
    intent_type = req.custom_intent or scenario_cfg["intent"]
    call_outcome = scenario_cfg["call_outcome"]
    reschedule_dt = req.reschedule_datetime or scenario_cfg.get("reschedule_datetime")
    updated_addr = req.updated_address or scenario_cfg.get("updated_address")
    notes = req.notes or scenario_cfg.get("notes")

    # Construct synthesized webhook payload
    webhook_payload = EigiWebhookPayload(
        call_id=sim_call_id,
        order_id=order.order_id,
        to_number=order.customer_phone,
        duration_seconds=58,
        status="completed",
        recording_url="https://actions.google.com/sounds/v1/telephones/phone_calling.ogg",
        transcript=transcript,
        extracted_intent=ExtractedIntent(
            order_id=order.order_id,
            call_outcome=call_outcome,
            customer_intent=intent_type,
            reschedule_datetime=reschedule_dt,
            updated_address=updated_addr,
            notes=notes,
            confidence=0.96,
        ),
        variables={
            "order_id": order.order_id,
            "customer_name": order.customer_name,
            "scenario": req.scenario,
        },
    )

    # Route through the exact same webhook handler!
    result = await eigi_call_completed_webhook(payload=webhook_payload, db=db)
    return {
        "simulation_status": "success",
        "scenario": req.scenario,
        "webhook_result": result,
    }


@app.get("/api/sync-calls", summary="Sync and ingest recent call transcripts directly from eigi.ai API")
@app.post("/api/sync-calls", summary="Sync and ingest recent call transcripts directly from eigi.ai API")
async def sync_eigi_calls(db: Session = Depends(get_db)):
    """Actively polls and ingests all conversations, transcripts, and audio recordings from eigi.ai cloud."""
    if settings.SIMULATION_MODE or settings.EIGI_API_KEY.startswith("mock_"):
        return {"synced_count": 0, "message": "Simulation mode active; no live cloud sync needed."}

    conversations = await eigi_client.list_conversations(limit=20)
    synced_items = []

    for conv in conversations:
        call_id = conv.get("conversation_id") or conv.get("id")
        if not call_id:
            continue

        raw_transcript = conv.get("conversation_transcript")
        meta = conv.get("conversation_metadata") or {}
        dyn_vars = meta.get("dynamic_variables") or {}
        to_phone = meta.get("to_mobile_number") or conv.get("to_mobile_number")
        duration = meta.get("conversation_duration") or conv.get("duration") or 0
        rec_url = meta.get("conversation_recording_url") or conv.get("recording_url")
        notes = conv.get("notes") or ""

        order_id = dyn_vars.get("order_id")
        if not order_id and raw_transcript:
            match = re.search(r"#?(ORD-\d+)", str(raw_transcript), re.IGNORECASE)
            if match:
                order_id = match.group(1).upper()

        order = None
        if order_id:
            order = db.query(Order).filter(Order.order_id == order_id).first()

        if not order and to_phone:
            clean_p = to_phone.replace("+", "").replace(" ", "").replace("-", "")
            order = db.query(Order).filter((Order.customer_phone == to_phone) | (Order.customer_phone.endswith(clean_p[-10:]))).first()
            if order:
                order_id = order.order_id

        # If order still not found in DB, auto-create order record for this phone call
        if not order:
            customer_name = dyn_vars.get("customer_name") or "Customer"
            order = Order(
                order_id=order_id or f"ORD-{call_id[-4:].upper()}",
                customer_name=customer_name,
                customer_phone=to_phone or "+919876543210",
                amount=float(dyn_vars.get("order_amount") or 2499.00),
                currency=dyn_vars.get("currency") or "INR",
                payment_method="COD",
                status="DELIVERY_FAILED",
                delivery_attempts=1,
                delivery_address=dyn_vars.get("delivery_address") or "Residence Address",
                city=dyn_vars.get("city") or "City",
                notes=f"Auto-synced from eigi.ai call: {notes}",
            )
            db.add(order)
            db.commit()
            db.refresh(order)
            order_id = order.order_id

        formatted_transcript = intent_extractor.format_transcript(raw_transcript)
        extracted: ExtractedIntent = intent_extractor.extract_from_payload(
            transcript=raw_transcript,
            order_id=order_id,
        )

        existing_log = db.query(CallLog).filter(CallLog.call_id == call_id).first()
        if not existing_log:
            call_log = CallLog(
                call_id=call_id,
                order_id=order_id,
                duration_seconds=duration,
                call_outcome=extracted.call_outcome,
                transcript=formatted_transcript,
                recording_url=rec_url,
            )
            call_log.extracted_intent = extracted.model_dump()
            db.add(call_log)
            db.commit()
            db.refresh(call_log)

            decision: ResolutionDecision = resolution_agent.decide(
                extracted_intent=extracted,
                order=order,
                call_id=call_id,
            )
            resolution: Resolution = operations_agent.execute(decision=decision, db=db)
            synced_items.append({"call_id": call_id, "order_id": order_id, "intent": extracted.customer_intent, "action": decision.action})
        else:
            # Update transcript and recording URL if previously empty
            if (not existing_log.transcript or existing_log.transcript == "None") and formatted_transcript:
                existing_log.transcript = formatted_transcript
                existing_log.recording_url = rec_url
                existing_log.duration_seconds = duration
                existing_log.extracted_intent = extracted.model_dump()
                db.commit()
                synced_items.append({"call_id": call_id, "order_id": order_id, "status": "updated"})

    return {
        "status": "success",
        "synced_count": len(synced_items),
        "synced_items": synced_items,
        "total_conversations_checked": len(conversations),
    }


# ---------------------------------------------------------------------------
# API: Orders & Dashboard Metrics
# ---------------------------------------------------------------------------
@app.get("/api/orders", response_model=List[OrderResponse])
def list_orders(db: Session = Depends(get_db)):
    return [order.to_dict() for order in db.query(Order).order_by(Order.created_at.desc()).all()]


@app.get("/api/orders/{order_id}")
def get_order_details(order_id: str, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.order_id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    call_logs = [cl.to_dict() for cl in db.query(CallLog).filter(CallLog.order_id == order_id).order_by(CallLog.created_at.desc()).all()]
    resolutions = [res.to_dict() for res in db.query(Resolution).filter(Resolution.order_id == order_id).order_by(Resolution.executed_at.desc()).all()]

    return {
        "order": order.to_dict(),
        "call_logs": call_logs,
        "resolutions": resolutions,
    }


@app.post("/api/orders", response_model=OrderResponse)
def create_order(req: OrderCreate, db: Session = Depends(get_db)):
    existing = db.query(Order).filter(Order.order_id == req.order_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Order ID already exists")

    order = Order(
        order_id=req.order_id,
        customer_name=req.customer_name,
        customer_phone=req.customer_phone,
        amount=req.amount,
        currency=req.currency,
        payment_method=req.payment_method,
        status="DELIVERY_FAILED",
        delivery_attempts=req.delivery_attempts,
        delivery_address=req.delivery_address,
        city=req.city,
        notes=req.notes,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order.to_dict()


@app.post("/api/orders/{order_id}/reset")
def reset_order(order_id: str, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.order_id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    order.status = "DELIVERY_FAILED"
    order.notes = "Reset to failed delivery state for testing."
    db.commit()
    return {"status": "reset", "order": order.to_dict()}


@app.get("/api/call-logs")
def list_call_logs(limit: int = 50, db: Session = Depends(get_db)):
    logs = db.query(CallLog).order_by(CallLog.created_at.desc()).limit(limit).all()
    return [log.to_dict() for log in logs]


@app.get("/api/resolutions")
def list_resolutions(limit: int = 50, db: Session = Depends(get_db)):
    resolutions = db.query(Resolution).order_by(Resolution.executed_at.desc()).limit(limit).all()
    return [res.to_dict() for res in resolutions]


@app.get("/api/stats")
@app.get("/api/dashboard-stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    total_orders = db.query(Order).count()
    failed = db.query(Order).filter(Order.status == "DELIVERY_FAILED").count()
    rescheduled = db.query(Order).filter(Order.status == "RESCHEDULED").count()
    cancelled = db.query(Order).filter(Order.status == "CANCELLED_RTO").count()
    escalated = db.query(Order).filter(Order.status == "HUMAN_ESCALATION").count()
    address_updates = db.query(Order).filter(Order.status == "ADDRESS_UPDATE_REQUIRED").count()
    total_calls = db.query(CallLog).count()
    total_resolutions = db.query(Resolution).count()

    # Calculate recovery rate
    recovered = rescheduled + address_updates
    decided_total = rescheduled + cancelled + escalated + address_updates
    recovery_rate = (recovered / decided_total * 100) if decided_total > 0 else 0.0

    return {
        "total_orders": total_orders,
        "failed_deliveries": failed,
        "rescheduled_recovered": rescheduled,
        "cancelled_rto": cancelled,
        "human_escalated": escalated,
        "address_updates": address_updates,
        "total_calls": total_calls,
        "total_resolutions": total_resolutions,
        "recovery_rate_pct": round(recovery_rate, 1),
    }
