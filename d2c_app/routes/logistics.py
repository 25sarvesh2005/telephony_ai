import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from d2c_app.database import get_d2c_db
from d2c_app.models import D2COrder, NDRTicket, ShipmentTracking
from d2c_app.schemas import (
    CourierDispatchRequest,
    NDRResolutionSyncRequest,
    NDRTriggerRequest,
    OutForDeliveryRequest,
)
from d2c_app.services.courier_engine import courier_engine
from d2c_app.services.recovery_bridge import recovery_bridge

logger = logging.getLogger("d2c_logistics_router")
router = APIRouter(prefix="/logistics", tags=["D2C Courier Logistics & NDR Engine"])


@router.post("/dispatch", summary="Dispatch order with courier partner (Assigns AWB)")
def dispatch_shipment(req: CourierDispatchRequest, db: Session = Depends(get_d2c_db)):
    order = db.query(D2COrder).filter(D2COrder.order_id == req.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail=f"Order '{req.order_id}' not found")
    
    order = courier_engine.dispatch_order(order, req.courier_partner, db)
    return {"status": "shipped", "order": order.to_dict()}


@router.post("/out-for-delivery", summary="Mark shipment out for delivery by courier")
def mark_out_for_delivery(req: OutForDeliveryRequest, db: Session = Depends(get_d2c_db)):
    order = db.query(D2COrder).filter(D2COrder.order_id == req.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail=f"Order '{req.order_id}' not found")

    order = courier_engine.mark_out_for_delivery(order, req.courier_name or "Delivery Executive", db)
    return {"status": "out_for_delivery", "order": order.to_dict()}


@router.post("/ndr", summary="Report courier delivery failure (NDR) and auto-trigger AI voice recovery call")
async def report_ndr_event(req: NDRTriggerRequest, db: Session = Depends(get_d2c_db)):
    order = db.query(D2COrder).filter(D2COrder.order_id == req.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail=f"Order '{req.order_id}' not found")

    result = await courier_engine.report_delivery_failure(
        order=order,
        failure_code=req.failure_code,
        remarks=req.courier_remarks,
        auto_call=req.auto_trigger_call,
        telephony_provider=req.telephony_provider,
        db=db,
    )
    return result


@router.post("/delivered", summary="Mark shipment delivered successfully")
def mark_delivered(order_id: str, db: Session = Depends(get_d2c_db)):
    order = db.query(D2COrder).filter(D2COrder.order_id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail=f"Order '{order_id}' not found")

    order = courier_engine.mark_delivered(order, db)
    return {"status": "delivered", "order": order.to_dict()}


@router.post("/status", summary="Update shipment status in logistics pipeline")
def update_shipment_status(data: Dict[str, Any], db: Session = Depends(get_d2c_db)):
    order_id = data.get("order_id")
    new_status = data.get("new_status", "OUT_FOR_DELIVERY")
    location = data.get("location", "Local Delivery Center")

    order = db.query(D2COrder).filter(D2COrder.order_id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail=f"Order '{order_id}' not found")

    if new_status == "OUT_FOR_DELIVERY":
        order = courier_engine.mark_out_for_delivery(order, courier_name=location, db=db)
    elif new_status == "DELIVERED":
        order = courier_engine.mark_delivered(order, db=db)
    else:
        order.status = new_status
        db.commit()

    return {"status": "updated", "order": order.to_dict()}


@router.post("/sync-resolution", summary="Sync AI Voice Recovery Engine resolution into D2C OMS")
def sync_recovery_resolution(req: NDRResolutionSyncRequest, db: Session = Depends(get_d2c_db)):
    """Receives post-call intent from recovery engine and updates D2C order & courier schedules."""
    order = db.query(D2COrder).filter(D2COrder.order_id == req.order_id).first()
    if not order:
        logger.warning(f"Sync resolution received for unknown D2C order: {req.order_id}")
        return {"status": "order_not_found", "order_id": req.order_id}

    # Update latest NDR ticket
    ndr = db.query(NDRTicket).filter(NDRTicket.order_id == order.id).order_by(NDRTicket.created_at.desc()).first()
    if ndr:
        ndr.recovery_status = f"RECOVERED_{req.action.upper()}" if req.action != "initiate_cancellation" else "CANCELLED_RTO"
        ndr.customer_response_intent = req.action
        ndr.rescheduled_date = req.reschedule_datetime
        ndr.updated_shipping_address = req.updated_address

    # Apply resolution to D2C order & record tracking milestone
    res = recovery_bridge.apply_resolution_to_d2c_order(
        order=order,
        action=req.action,
        reschedule_datetime=req.reschedule_datetime,
        updated_address=req.updated_address,
        notes=req.customer_notes,
        db=db,
    )

    logger.info(f"Synchronized recovery resolution for D2C order {order.order_id}: {req.action}")
    return {"status": "synchronized", "order": res}
