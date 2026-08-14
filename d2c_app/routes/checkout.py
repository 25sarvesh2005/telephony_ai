import random
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from d2c_app.config import d2c_settings
from d2c_app.database import get_d2c_db
from d2c_app.models import Cart, CartItem, Customer, D2COrder, D2COrderItem, Product, ShipmentTracking
from d2c_app.schemas import CheckoutRequest, OrderResponse
from d2c_app.services.courier_engine import courier_engine

router = APIRouter(prefix="/checkout", tags=["D2C Checkout & Order Placement"])


def generate_order_id() -> str:
    """Generates a clean D2C order ID like ORD-48291."""
    return f"ORD-{random.randint(10000, 99999)}"


@router.post("", response_model=OrderResponse, summary="Place a D2C order (COD or Prepaid)")
def place_order(req: CheckoutRequest, db: Session = Depends(get_d2c_db)):
    # 1. Resolve Items
    items_to_order = []
    
    if req.session_id:
        cart = db.query(Cart).filter(Cart.session_id == req.session_id).first()
        if not cart or not cart.items:
            raise HTTPException(status_code=400, detail="Cart is empty or does not exist")
        for ci in cart.items:
            items_to_order.append({
                "sku": ci.product_sku,
                "title": ci.product_title,
                "unit_price": ci.unit_price,
                "quantity": ci.quantity,
                "total_price": ci.unit_price * ci.quantity,
                "image_url": ci.image_url,
            })
    elif req.items:
        for it in req.items:
            product = db.query(Product).filter(Product.sku == it["sku"]).first()
            if not product:
                raise HTTPException(status_code=404, detail=f"Product {it['sku']} not found")
            qty = it.get("quantity", 1)
            items_to_order.append({
                "sku": product.sku,
                "title": product.title,
                "unit_price": product.price,
                "quantity": qty,
                "total_price": product.price * qty,
                "image_url": product.image_url,
            })
    else:
        raise HTTPException(status_code=400, detail="No items provided for checkout")

    # 2. Calculate Financials
    subtotal = sum(i["total_price"] for i in items_to_order)
    shipping_fee = 0.0 if subtotal >= d2c_settings.FREE_SHIPPING_MIN_ORDER else d2c_settings.STANDARD_SHIPPING_FEE
    discount_amount = 0.0
    total_amount = subtotal + shipping_fee - discount_amount

    # 3. Create / Lookup Customer
    clean_phone = req.customer_phone.strip()
    customer = db.query(Customer).filter(Customer.phone == clean_phone).first()
    if not customer:
        customer = Customer(
            customer_id=f"CUST-{uuid.uuid4().hex[:8]}",
            name=req.customer_name,
            email=req.customer_email,
            phone=clean_phone,
            default_address=req.delivery_address,
            city=req.city,
            state=req.state,
            pincode=req.pincode,
            total_orders=1,
        )
        db.add(customer)
        db.flush()
    else:
        customer.total_orders += 1
        customer.default_address = req.delivery_address
        customer.city = req.city
        customer.pincode = req.pincode

    # 4. Create Order Record
    order_id = generate_order_id()
    while db.query(D2COrder).filter(D2COrder.order_id == order_id).first():
        order_id = generate_order_id()

    order = D2COrder(
        order_id=order_id,
        customer_id=customer.id,
        customer_name=req.customer_name,
        customer_phone=clean_phone,
        customer_email=req.customer_email,
        delivery_address=req.delivery_address,
        city=req.city,
        state=req.state,
        pincode=req.pincode,
        subtotal=round(subtotal, 2),
        shipping_fee=round(shipping_fee, 2),
        discount_amount=round(discount_amount, 2),
        total_amount=round(total_amount, 2),
        currency=d2c_settings.STORE_CURRENCY,
        payment_method=req.payment_method.upper(),
        payment_status="PAID" if req.payment_method.upper() == "PREPAID" else "PENDING",
        order_status="CONFIRMED",
    )
    db.add(order)
    db.flush()

    # 5. Add Order Items
    for i in items_to_order:
        oi = D2COrderItem(
            order_id=order.id,
            product_sku=i["sku"],
            product_title=i["title"],
            unit_price=i["unit_price"],
            quantity=i["quantity"],
            total_price=i["total_price"],
            image_url=i.get("image_url"),
        )
        db.add(oi)

    # 6. Initial Tracking Milestone
    milestone = ShipmentTracking(
        order_id=order.id,
        status="ORDER_PLACED",
        location=f"Aura Luxe Fulfillment Hub",
        description=f"Order #{order.order_id} placed successfully. Payment Method: {order.payment_method}.",
    )
    db.add(milestone)

    # 7. Clear cart if checked out with session_id
    if req.session_id:
        cart = db.query(Cart).filter(Cart.session_id == req.session_id).first()
        if cart:
            for item in cart.items:
                db.delete(item)

    db.commit()
    db.refresh(order)

    # 8. Auto-dispatch with courier
    courier_engine.dispatch_order(order, courier_partner="Bluedart Express", db=db)

    return order.to_dict()
