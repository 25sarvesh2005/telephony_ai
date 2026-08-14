"""Seed initial test orders for the AI Commerce Recovery Engine."""
from app.database import SessionLocal, init_db
from app.models import Order

SAMPLE_ORDERS = [
    {
        "order_id": "ORD-9481",
        "customer_name": "Rahul Sharma",
        "customer_phone": "+919876543210",
        "amount": 2499.00,
        "currency": "INR",
        "payment_method": "COD",
        "status": "DELIVERY_FAILED",
        "delivery_attempts": 1,
        "delivery_address": "Flat 204, Green Glen Layout, Bellandur",
        "city": "Bengaluru",
        "notes": "Courier reported: Customer unavailable at residence during morning delivery window.",
    },
    {
        "order_id": "ORD-8712",
        "customer_name": "Priya Nair",
        "customer_phone": "+919812345678",
        "amount": 1850.00,
        "currency": "INR",
        "payment_method": "COD",
        "status": "DELIVERY_FAILED",
        "delivery_attempts": 1,
        "delivery_address": "House 14, 5th Main, Indiranagar",
        "city": "Bengaluru",
        "notes": "Courier reported: Door locked / phone not reachable.",
    },
    {
        "order_id": "ORD-6204",
        "customer_name": "Vikram Malhotra",
        "customer_phone": "+919700112233",
        "amount": 4999.00,
        "currency": "INR",
        "payment_method": "COD",
        "status": "DELIVERY_FAILED",
        "delivery_attempts": 2,
        "delivery_address": "Tower B, Apt 1102, Hiranandani Estate",
        "city": "Mumbai",
        "notes": "Courier reported: Delivery refused - customer requested later date.",
    },
    {
        "order_id": "ORD-5190",
        "customer_name": "Ananya Deshmukh",
        "customer_phone": "+919833445566",
        "amount": 1290.00,
        "currency": "INR",
        "payment_method": "COD",
        "status": "DELIVERY_FAILED",
        "delivery_attempts": 1,
        "delivery_address": "Plot 88, Baner Road",
        "city": "Pune",
        "notes": "Courier reported: Incorrect building number.",
    },
    {
        "order_id": "ORD-3042",
        "customer_name": "Karan Johar",
        "customer_phone": "+919988776655",
        "amount": 8900.00,
        "currency": "INR",
        "payment_method": "COD",
        "status": "DELIVERY_FAILED",
        "delivery_attempts": 3,
        "delivery_address": "Sea Mist Villa, Bandra West",
        "city": "Mumbai",
        "notes": "High value COD - 3 failed delivery attempts.",
    },
]


def seed_database():
    init_db()
    db = SessionLocal()
    try:
        count = 0
        for sample in SAMPLE_ORDERS:
            existing = db.query(Order).filter(Order.order_id == sample["order_id"]).first()
            if not existing:
                order = Order(**sample)
                db.add(order)
                count += 1
        db.commit()
        print(f"Successfully seeded {count} new orders into database.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
