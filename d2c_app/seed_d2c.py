"""Seed sample products and demo orders for the D2C Store."""
import random
from d2c_app.database import D2CSessionLocal, init_d2c_db
from d2c_app.models import Customer, D2COrder, D2COrderItem, Product, ShipmentTracking

SAMPLE_PRODUCTS = [
    {
        "sku": "ETHNIC-SAREE-01",
        "title": "Royal Banarasi Silk Zari Saree",
        "description": "Authentic handwoven pure Banarasi silk saree with intricate golden zari work, matching unstitched blouse piece.",
        "category": "Ethnic Wear",
        "price": 3000.00,
        "compare_at_price": 5499.00,
        "stock_quantity": 45,
        "image_url": "https://images.unsplash.com/photo-1610030469983-98e550d6193c?auto=format&fit=crop&w=600&q=80",
        "tags": "saree,ethnic,silk,wedding",
    },
    {
        "sku": "AUDIO-ANC-EARBUDS",
        "title": "AuraPod Pro Wireless ANC Earbuds",
        "description": "Active Noise Cancelling Bluetooth 5.3 earbuds with 42-hour playtime, ultra low latency gaming mode, and deep bass boost.",
        "category": "Electronics",
        "price": 2199.00,
        "compare_at_price": 4999.00,
        "stock_quantity": 80,
        "image_url": "https://images.unsplash.com/photo-1590658268037-6bf12165a8df?auto=format&fit=crop&w=600&q=80",
        "tags": "audio,earbuds,anc,wireless",
    },
    {
        "sku": "SKIN-GLOW-SERUM",
        "title": "Radiance 15% Vitamin C Glow Serum (30ml)",
        "description": "Dermatologically tested brightening facial serum with Vitamin C, Ferulic Acid, and Hyaluronic Acid for radiant, spot-free skin.",
        "category": "Skincare",
        "price": 899.00,
        "compare_at_price": 1299.00,
        "stock_quantity": 120,
        "image_url": "https://images.unsplash.com/photo-1620916566398-39f1143ab7be?auto=format&fit=crop&w=600&q=80",
        "tags": "skincare,serum,glow,vitaminc",
    },
    {
        "sku": "APPAREL-DENIM-JACKET",
        "title": "Vintage Wash Slim-Fit Denim Jacket",
        "description": "100% premium cotton denim jacket with distressed finish, custom brass buttons, and dual chest pockets.",
        "category": "Apparel",
        "price": 2499.00,
        "compare_at_price": 3999.00,
        "stock_quantity": 60,
        "image_url": "https://images.unsplash.com/photo-1576995853123-5a10305d93c0?auto=format&fit=crop&w=600&q=80",
        "tags": "apparel,jacket,denim,men,women",
    },
    {
        "sku": "TECH-FITNESS-WATCH",
        "title": "AuraPulse AMOLED Smart Fitness Watch",
        "description": "1.43-inch AMOLED display smartwatch with Bluetooth calling, 120+ sports modes, 24/7 SpO2 & heart rate monitoring.",
        "category": "Electronics",
        "price": 3499.00,
        "compare_at_price": 6999.00,
        "stock_quantity": 50,
        "image_url": "https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&w=600&q=80",
        "tags": "smartwatch,fitness,amoled,tech",
    },
    {
        "sku": "LUXE-LEATHER-BAG",
        "title": "Handcrafted Top-Grain Leather Messenger Bag",
        "description": "Full-grain genuine vintage leather laptop messenger bag with padded 15.6-inch sleeve and antique brass hardware.",
        "category": "Accessories",
        "price": 4299.00,
        "compare_at_price": 7500.00,
        "stock_quantity": 30,
        "image_url": "https://images.unsplash.com/photo-1548036328-c9fa89d128fa?auto=format&fit=crop&w=600&q=80",
        "tags": "leather,bag,accessories,laptop",
    },
]


def seed_d2c_database():
    init_d2c_db()
    db = D2CSessionLocal()
    try:
        # 1. Seed Products
        prod_count = 0
        for p_data in SAMPLE_PRODUCTS:
            existing = db.query(Product).filter(Product.sku == p_data["sku"]).first()
            if not existing:
                p = Product(**p_data)
                db.add(p)
                prod_count += 1
        db.commit()
        print(f"[D2C] Seeded {prod_count} D2C products into catalog.")

        # 2. Seed Initial Demo Orders if none exist
        if db.query(D2COrder).count() == 0:
            demo_orders = [
                {
                    "order_id": "ORD-7732",
                    "customer_name": "Alka Sharma",
                    "customer_phone": "+919325922986",
                    "delivery_address": "Flat 402, Green Meadows",
                    "city": "Nagpur",
                    "pincode": "440015",
                    "subtotal": 3000.00,
                    "shipping_fee": 0.0,
                    "total_amount": 3000.00,
                    "payment_method": "COD",
                    "order_status": "DELIVERY_FAILED_NDR",
                    "delivery_attempts": 1,
                    "courier_partner": "Bluedart Express",
                    "awb_number": "BLUEDART-88391204",
                    "ndr_reason": "Customer phone unanswered during delivery window.",
                    "sku": "ETHNIC-SAREE-01",
                    "title": "Royal Banarasi Silk Zari Saree",
                    "price": 3000.00,
                },
                {
                    "order_id": "ORD-5521",
                    "customer_name": "Ayush Dubey",
                    "customer_phone": "+918446079712",
                    "delivery_address": "Near Ajni Metro Station",
                    "city": "Nagpur",
                    "pincode": "440003",
                    "subtotal": 2199.00,
                    "shipping_fee": 0.0,
                    "total_amount": 2199.00,
                    "payment_method": "COD",
                    "order_status": "DELIVERY_FAILED_NDR",
                    "delivery_attempts": 1,
                    "courier_partner": "Delhivery Express",
                    "awb_number": "DELHIVERY-77491823",
                    "ndr_reason": "Customer requested re-attempt at office address.",
                    "sku": "AUDIO-ANC-EARBUDS",
                    "title": "AuraPod Pro Wireless ANC Earbuds",
                    "price": 2199.00,
                },
                {
                    "order_id": "ORD-6603",
                    "customer_name": "Rahul Deshmukh",
                    "customer_phone": "+919423266503",
                    "delivery_address": "Plot 12, Baner Road",
                    "city": "Pune",
                    "pincode": "411045",
                    "subtotal": 2499.00,
                    "shipping_fee": 0.0,
                    "total_amount": 2499.00,
                    "payment_method": "COD",
                    "order_status": "CONFIRMED",
                    "delivery_attempts": 0,
                    "courier_partner": "Bluedart Express",
                    "awb_number": "BLUEDART-99381204",
                    "sku": "APPAREL-DENIM-JACKET",
                    "title": "Vintage Wash Slim-Fit Denim Jacket",
                    "price": 2499.00,
                }
            ]

            for d in demo_orders:
                order = D2COrder(
                    order_id=d["order_id"],
                    customer_name=d["customer_name"],
                    customer_phone=d["customer_phone"],
                    delivery_address=d["delivery_address"],
                    city=d["city"],
                    pincode=d["pincode"],
                    subtotal=d["subtotal"],
                    shipping_fee=d["shipping_fee"],
                    total_amount=d["total_amount"],
                    payment_method=d["payment_method"],
                    order_status=d["order_status"],
                    delivery_attempts=d.get("delivery_attempts", 0),
                    courier_partner=d["courier_partner"],
                    awb_number=d["awb_number"],
                    ndr_reason=d.get("ndr_reason"),
                )
                db.add(order)
                db.flush()

                item = D2COrderItem(
                    order_id=order.id,
                    product_sku=d["sku"],
                    product_title=d["title"],
                    unit_price=d["price"],
                    quantity=1,
                    total_price=d["price"],
                )
                db.add(item)

                m = ShipmentTracking(
                    order_id=order.id,
                    status=order.order_status,
                    location=f"{order.city} Hub",
                    description=f"Initial tracking registered for #{order.order_id}.",
                )
                db.add(m)

            db.commit()
            print("[D2C] Seeded initial D2C orders.")
    finally:
        db.close()



if __name__ == "__main__":
    seed_d2c_database()
