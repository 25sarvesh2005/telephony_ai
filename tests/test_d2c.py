from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from d2c_app.config import d2c_settings
from d2c_app.database import D2CBase, get_d2c_db
from d2c_app.main import d2c_app
from d2c_app.models import Customer, D2COrder, Product

# Test SQLite in-memory database
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_d2c_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


d2c_app.dependency_overrides[get_d2c_db] = override_get_d2c_db
client = TestClient(d2c_app)


@pytest.fixture(autouse=True)
def setup_database():
    D2CBase.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()

    # Seed sample product
    p1 = Product(
        sku="TEST-SAREE-01",
        title="Banarasi Silk Saree",
        description="Premium Silk",
        category="Ethnic Wear",
        price=3000.0,
        compare_at_price=5000.0,
        stock_quantity=10,
        is_active=True,
    )
    db.add(p1)
    db.commit()
    db.close()

    yield

    D2CBase.metadata.drop_all(bind=test_engine)


def test_list_products():
    res = client.get("/api/d2c/products")
    assert res.status_code == 200
    products = res.json()
    assert len(products) >= 1
    assert products[0]["sku"] == "TEST-SAREE-01"


def test_cart_workflow():
    session_id = "test_cart_sess_01"
    
    # 1. Add to cart
    add_res = client.post("/api/d2c/cart/add", json={
        "session_id": session_id,
        "sku": "TEST-SAREE-01",
        "quantity": 2
    })
    assert add_res.status_code == 200
    cart = add_res.json()
    assert cart["item_count"] == 2
    assert cart["subtotal"] == 6000.0

    # 2. Get cart
    get_res = client.get(f"/api/d2c/cart/{session_id}")
    assert get_res.status_code == 200
    assert get_res.json()["subtotal"] == 6000.0

    # 3. Remove from cart
    del_res = client.delete(f"/api/d2c/cart/{session_id}/item/TEST-SAREE-01")
    assert del_res.status_code == 200
    assert del_res.json()["item_count"] == 0


def test_checkout_and_order_creation():
    checkout_payload = {
        "customer_name": "Alka Sharma",
        "customer_phone": "+919325922986",
        "customer_email": "alka@example.com",
        "delivery_address": "Flat 402, Green Meadows",
        "city": "Nagpur",
        "pincode": "440015",
        "payment_method": "COD",
        "items": [
            {"sku": "TEST-SAREE-01", "quantity": 1}
        ]
    }
    res = client.post("/api/d2c/checkout", json=checkout_payload)
    assert res.status_code == 200
    order = res.json()
    assert order["order_id"].startswith("ORD-")
    assert order["customer_name"] == "Alka Sharma"
    assert order["total_amount"] == 3000.0
    assert order["order_status"] == "SHIPPED"  # Auto-dispatched
    assert order["awb_number"] is not None


@patch("d2c_app.services.recovery_bridge.recovery_bridge.trigger_recovery_call", new_callable=AsyncMock)
def test_courier_ndr_failure_and_recovery_sync(mock_trigger_call):
    mock_trigger_call.return_value = {
        "success": True,
        "call_info": {"call_id": "call_mock_123", "status": "queued"}
    }

    # 1. Place order
    res = client.post("/api/d2c/checkout", json={
        "customer_name": "Ayush Dubey",
        "customer_phone": "+918446079712",
        "delivery_address": "Near Ajni Metro Station",
        "city": "Nagpur",
        "pincode": "440003",
        "payment_method": "COD",
        "items": [{"sku": "TEST-SAREE-01", "quantity": 1}]
    })
    order_id = res.json()["order_id"]

    # 2. Courier reports delivery failure (NDR event)
    ndr_res = client.post("/api/d2c/logistics/ndr", json={
        "order_id": order_id,
        "failure_code": "CUSTOMER_UNAVAILABLE",
        "courier_remarks": "Customer door locked during morning round.",
        "auto_trigger_call": True,
        "telephony_provider": "eigi"
    })
    assert ndr_res.status_code == 200
    assert mock_trigger_call.called

    # 3. Synchronize AI Voice Call resolution back to D2C OMS
    sync_res = client.post("/api/d2c/logistics/sync-resolution", json={
        "order_id": order_id,
        "action": "reschedule",
        "reschedule_datetime": "Tomorrow at 6:00 PM",
        "customer_notes": "Customer requested evening delivery",
        "call_id": "call_mock_123"
    })
    assert sync_res.status_code == 200
    updated_order = sync_res.json()["order"]
    assert updated_order["order_status"] == "RESCHEDULED"
    assert "Tomorrow at 6:00 PM" in updated_order["rescheduled_for"]


def test_d2c_analytics():
    # Place an order
    client.post("/api/d2c/checkout", json={
        "customer_name": "Test User",
        "customer_phone": "+919988776655",
        "delivery_address": "123 Street",
        "city": "Mumbai",
        "pincode": "400001",
        "payment_method": "COD",
        "items": [{"sku": "TEST-SAREE-01", "quantity": 1}]
    })

    res = client.get("/api/d2c/analytics")
    assert res.status_code == 200
    stats = res.json()
    assert stats["total_orders"] >= 1
    assert stats["gross_merchandise_value"] >= 3000.0
    assert stats["cod_orders"] >= 1


def test_threshold_bot_risk_flagging():
    # Place a high-value COD order
    res = client.post("/api/d2c/checkout", json={
        "customer_name": "Alka Sharma",
        "customer_phone": "+919325922986",
        "delivery_address": "Short",  # Short incomplete address to trigger flag
        "city": "Nagpur",
        "pincode": "440015",
        "payment_method": "COD",
        "items": [{"sku": "TEST-SAREE-01", "quantity": 2}]  # ₹6000 >= ₹3000 threshold
    })
    order_id = res.json()["order_id"]

    # Run threshold analysis
    analysis_res = client.get(f"/api/d2c/orders/{order_id}/threshold-analysis")
    assert analysis_res.status_code == 200
    analysis = analysis_res.json()
    assert analysis["is_flagged"] is True
    assert "HIGH_COD_VALUE_RISK" in analysis["flags"]
    assert "INCOMPLETE_ADDRESS_RISK" in analysis["flags"]
    assert analysis["risk_level"] in ("MEDIUM", "HIGH")

