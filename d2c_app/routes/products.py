from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from d2c_app.database import get_d2c_db
from d2c_app.models import Product
from d2c_app.schemas import ProductCreate, ProductResponse

router = APIRouter(prefix="/products", tags=["D2C Product Catalog"])


@router.get("", response_model=List[ProductResponse], summary="List active products in D2C store")
def list_products(
    category: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_d2c_db),
):
    query = db.query(Product).filter(Product.is_active == True)
    if category:
        query = query.filter(Product.category == category)
    if search:
        query = query.filter(Product.title.ilike(f"%{search}%"))
    products = query.order_by(Product.id.asc()).all()
    return [p.to_dict() for p in products]


@router.get("/{sku}", response_model=ProductResponse, summary="Get product details by SKU")
def get_product(sku: str, db: Session = Depends(get_d2c_db)):
    product = db.query(Product).filter(Product.sku == sku).first()
    if not product:
        raise HTTPException(status_code=404, detail=f"Product with SKU '{sku}' not found")
    return product.to_dict()


@router.post("", response_model=ProductResponse, summary="Create a new D2C product")
def create_product(req: ProductCreate, db: Session = Depends(get_d2c_db)):
    existing = db.query(Product).filter(Product.sku == req.sku).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Product SKU '{req.sku}' already exists")
    
    product = Product(
        sku=req.sku,
        title=req.title,
        description=req.description,
        category=req.category,
        price=req.price,
        compare_at_price=req.compare_at_price,
        stock_quantity=req.stock_quantity,
        image_url=req.image_url,
        tags=req.tags,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product.to_dict()
