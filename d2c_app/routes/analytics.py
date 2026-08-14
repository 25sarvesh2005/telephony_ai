from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from d2c_app.database import get_d2c_db
from d2c_app.models import D2COrder, NDRTicket
from d2c_app.schemas import D2CAnalyticsResponse

router = APIRouter(prefix="/analytics", tags=["D2C Business & NDR Analytics"])


@router.get("", response_model=D2CAnalyticsResponse, summary="Get D2C Store Performance & Recovery Metrics")
def get_d2c_analytics(db: Session = Depends(get_d2c_db)):
    total_orders = db.query(D2COrder).count()
    all_orders = db.query(D2COrder).all()
    
    gmv = sum(o.total_amount for o in all_orders)
    cod_orders = sum(1 for o in all_orders if o.payment_method == "COD")
    prepaid_orders = sum(1 for o in all_orders if o.payment_method == "PREPAID")
    delivered = sum(1 for o in all_orders if o.order_status == "DELIVERED")
    
    # NDR & Recovery
    ndr_failed = sum(1 for o in all_orders if o.order_status in ("DELIVERY_FAILED_NDR", "CALL_IN_PROGRESS"))
    recovered = sum(1 for o in all_orders if o.order_status in ("RESCHEDULED", "ADDRESS_UPDATE_REQUIRED"))
    rto_cancelled = sum(1 for o in all_orders if o.order_status == "CANCELLED_RTO")
    
    decided_ndr = recovered + rto_cancelled
    recovery_rate = (recovered / decided_ndr * 100) if decided_ndr > 0 else 0.0
    
    # Estimated RTO Cost Saved: Average ₹180 courier RTO penalty + return logistics per recovered parcel
    estimated_rto_saved = recovered * 180.0

    return {
        "total_orders": total_orders,
        "gross_merchandise_value": round(gmv, 2),
        "cod_orders": cod_orders,
        "prepaid_orders": prepaid_orders,
        "delivered_orders": delivered,
        "ndr_failed_orders": ndr_failed,
        "recovered_orders": recovered,
        "rto_cancelled_orders": rto_cancelled,
        "recovery_rate_pct": round(recovery_rate, 1),
        "estimated_rto_cost_saved": round(estimated_rto_saved, 2),
    }
