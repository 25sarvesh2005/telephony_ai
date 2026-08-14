from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from d2c_app.database import get_d2c_db
from d2c_app.models import D2COrder, NDRTicket, ShipmentTracking
from d2c_app.schemas import OrderResponse

router = APIRouter(prefix="/orders", tags=["D2C Order Management System"])


@router.get("", response_model=List[OrderResponse], summary="List D2C Orders")
def list_orders(
    status: Optional[str] = None,
    payment_method: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_d2c_db),
):
    query = db.query(D2COrder)
    if status:
        query = query.filter(D2COrder.order_status == status)
    if payment_method:
        query = query.filter(D2COrder.payment_method == payment_method.upper())
    if search:
        query = query.filter(
            (D2COrder.order_id.ilike(f"%{search}%")) |
            (D2COrder.customer_name.ilike(f"%{search}%")) |
            (D2COrder.customer_phone.ilike(f"%{search}%"))
        )
    orders = query.order_by(D2COrder.created_at.desc()).limit(limit).all()
    return [o.to_dict() for o in orders]


@router.get("/flagged/all", summary="List all orders flagged by Threshold Bot")
def list_flagged_orders(db: Session = Depends(get_d2c_db)):
    from d2c_app.services.threshold_bot import threshold_bot
    orders = db.query(D2COrder).order_by(D2COrder.created_at.desc()).all()
    flagged_list = []
    for o in orders:
        analysis = threshold_bot.evaluate_order(o, db=db)
        if analysis["is_flagged"]:
            flagged_list.append({
                "order": o.to_dict(),
                "threshold_analysis": analysis,
            })
    return flagged_list


@router.get("/{order_id}/threshold-analysis", summary="Run Threshold Bot risk evaluation on an order")
def get_order_threshold_analysis(order_id: str, db: Session = Depends(get_d2c_db)):
    from d2c_app.services.threshold_bot import threshold_bot
    order = db.query(D2COrder).filter(D2COrder.order_id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail=f"Order '{order_id}' not found")

    analysis = threshold_bot.evaluate_order(order, db=db)
    return analysis


@router.get("/{order_id}", summary="Get D2C Order Details with Tracking, NDR History & Threshold Analysis")
def get_order(order_id: str, db: Session = Depends(get_d2c_db)):
    from d2c_app.services.threshold_bot import threshold_bot
    order = db.query(D2COrder).filter(D2COrder.order_id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail=f"Order '{order_id}' not found")

    tracking = [m.to_dict() for m in db.query(ShipmentTracking).filter(ShipmentTracking.order_id == order.id).order_by(ShipmentTracking.timestamp.desc()).all()]
    ndr_tickets = [n.to_dict() for n in db.query(NDRTicket).filter(NDRTicket.order_id == order.id).order_by(NDRTicket.created_at.desc()).all()]
    threshold_analysis = threshold_bot.evaluate_order(order, db=db)

    return {
        "order": order.to_dict(),
        "tracking_milestones": tracking,
        "ndr_tickets": ndr_tickets,
        "threshold_analysis": threshold_analysis,
    }


@router.post("/{order_id}/cancel", summary="Cancel a D2C order")
def cancel_order(order_id: str, reason: Optional[str] = "Customer request", db: Session = Depends(get_d2c_db)):
    order = db.query(D2COrder).filter(D2COrder.order_id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail=f"Order '{order_id}' not found")

    order.order_status = "CANCELLED_RTO"
    order.resolution_notes = f"Cancelled: {reason}"

    milestone = ShipmentTracking(
        order_id=order.id,
        status="CANCELLED_RTO",
        location=f"{order.city} Hub",
        description=f"Order cancelled by admin. Reason: {reason}",
    )
    db.add(milestone)
    db.commit()
    return {"status": "cancelled", "order": order.to_dict()}

