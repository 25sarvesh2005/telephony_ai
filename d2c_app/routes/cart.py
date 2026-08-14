import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from d2c_app.database import get_d2c_db
from d2c_app.models import Cart, CartItem, Product
from d2c_app.schemas import CartItemAdd, CartItemUpdate, CartResponse

router = APIRouter(prefix="/cart", tags=["D2C Shopping Cart"])


def get_or_create_cart(session_id: str, db: Session) -> Cart:
    cart = db.query(Cart).filter(Cart.session_id == session_id).first()
    if not cart:
        cart = Cart(session_id=session_id)
        db.add(cart)
        db.commit()
        db.refresh(cart)
    return cart


@router.get("/{session_id}", response_model=CartResponse, summary="Get current shopping cart")
def get_cart(session_id: str, db: Session = Depends(get_d2c_db)):
    cart = get_or_create_cart(session_id, db)
    return cart.to_dict()


@router.post("/add", response_model=CartResponse, summary="Add item to shopping cart")
def add_to_cart(req: CartItemAdd, db: Session = Depends(get_d2c_db)):
    product = db.query(Product).filter(Product.sku == req.sku, Product.is_active == True).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found or unavailable")

    cart = get_or_create_cart(req.session_id, db)
    
    # Check if item exists in cart
    existing_item = db.query(CartItem).filter(CartItem.cart_id == cart.id, CartItem.product_sku == req.sku).first()
    if existing_item:
        existing_item.quantity += req.quantity
    else:
        new_item = CartItem(
            cart_id=cart.id,
            product_sku=product.sku,
            product_title=product.title,
            unit_price=product.price,
            quantity=req.quantity,
            image_url=product.image_url,
        )
        db.add(new_item)

    db.commit()
    db.refresh(cart)
    return cart.to_dict()


@router.delete("/{session_id}/item/{sku}", response_model=CartResponse, summary="Remove item from cart")
def remove_from_cart(session_id: str, sku: str, db: Session = Depends(get_d2c_db)):
    cart = db.query(Cart).filter(Cart.session_id == session_id).first()
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    item = db.query(CartItem).filter(CartItem.cart_id == cart.id, CartItem.product_sku == sku).first()
    if item:
        db.delete(item)
        db.commit()
        db.refresh(cart)

    return cart.to_dict()


@router.delete("/{session_id}/clear", summary="Clear all items in cart")
def clear_cart(session_id: str, db: Session = Depends(get_d2c_db)):
    cart = db.query(Cart).filter(Cart.session_id == session_id).first()
    if cart:
        for item in cart.items:
            db.delete(item)
        db.commit()
    return {"status": "cleared", "session_id": session_id}
