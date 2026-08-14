import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import CallLog, Order, Resolution

# Test SQLite in-memory database
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    # Seed sample orders for testing
    order1 = Order(
        order_id="TEST-101",
        customer_name="Test User 1",
        customer_phone="+919876543210",
        amount=1500.0,
        currency="INR",
        payment_method="COD",
        status="DELIVERY_FAILED",
        delivery_attempts=1,
        delivery_address="123 Test St",
        city="Bengaluru",
    )
    order2 = Order(
        order_id="TEST-102",
        customer_name="Test User 2",
        customer_phone="+919876543211",
        amount=2800.0,
        currency="INR",
        payment_method="COD",
        status="DELIVERY_FAILED",
        delivery_attempts=3,  # High attempts
        delivery_address="456 Test Ave",
        city="Mumbai",
    )
    db.add(order1)
    db.add(order2)
    db.commit()
    db.close()

    yield

    Base.metadata.drop_all(bind=engine)


def test_trigger_call():
    response = client.post("/trigger-call", json={"order_id": "TEST-101"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["order_id"] == "TEST-101"
    assert data["call_info"]["status"] == "queued"


def test_webhook_reschedule_flow():
    payload = {
        "call_id": "call_test_resched_01",
        "order_id": "TEST-101",
        "duration_seconds": 45,
        "transcript": "Customer said they weren't home, requested delivery tomorrow at 5 PM.",
        "extracted_intent": {
            "order_id": "TEST-101",
            "call_outcome": "reached",
            "customer_intent": "reschedule",
            "reschedule_datetime": "Tomorrow at 5:00 PM",
            "notes": "Customer requested evening delivery",
        },
    }
    response = client.post("/webhooks/eigi/call-completed", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["decision"]["action"] == "reschedule"

    # Check updated order in DB
    order_res = client.get("/api/orders/TEST-101")
    assert order_res.status_code == 200
    order_data = order_res.json()["order"]
    assert order_data["status"] == "RESCHEDULED"
    assert len(order_res.json()["resolutions"]) == 1


def test_webhook_cancellation_flow():
    payload = {
        "call_id": "call_test_cancel_01",
        "order_id": "TEST-101",
        "duration_seconds": 30,
        "transcript": "Agent: Would you like to reschedule? Customer: No, please cancel the order, I don't want it anymore.",
    }
    # Note: extracted_intent is omitted here to test transcript NLP extraction!
    response = client.post("/webhooks/eigi/call-completed", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["extracted_intent"]["customer_intent"] == "cancel"
    assert data["decision"]["action"] == "initiate_cancellation"

    order_res = client.get("/api/orders/TEST-101")
    assert order_res.json()["order"]["status"] == "CANCELLED_RTO"


def test_webhook_wrong_address_flow():
    payload = {
        "call_id": "call_test_addr_01",
        "order_id": "TEST-101",
        "duration_seconds": 50,
        "transcript": "Customer stated delivery address is incorrect. New address is Flat 501, Palm Grove Apartments.",
    }
    response = client.post("/webhooks/eigi/call-completed", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["decision"]["action"] == "flag_address_correction"

    order_res = client.get("/api/orders/TEST-101")
    assert order_res.json()["order"]["status"] == "ADDRESS_UPDATE_REQUIRED"


def test_high_attempts_reschedule_escalates():
    # Order TEST-102 has delivery_attempts = 3
    payload = {
        "call_id": "call_test_attempt_max",
        "order_id": "TEST-102",
        "extracted_intent": {
            "order_id": "TEST-102",
            "call_outcome": "reached",
            "customer_intent": "reschedule",
            "reschedule_datetime": "Tomorrow",
            "notes": "Customer wanted to reschedule for 4th attempt",
        },
    }
    response = client.post("/webhooks/eigi/call-completed", json=payload)
    assert response.status_code == 200
    data = response.json()
    # Policy should escalate because attempts >= 3
    assert data["decision"]["action"] == "escalate_to_human"

    order_res = client.get("/api/orders/TEST-102")
    assert order_res.json()["order"]["status"] == "HUMAN_ESCALATION"


def test_simulation_endpoint():
    response = client.post(
        "/simulate-call",
        json={
            "order_id": "TEST-101",
            "scenario": "reschedule",
            "reschedule_datetime": "Saturday morning at 10 AM",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["simulation_status"] == "success"
    assert data["webhook_result"]["decision"]["action"] == "reschedule"


def test_dashboard_stats_endpoint():
    # Trigger simulation to populate numbers
    client.post("/simulate-call", json={"order_id": "TEST-101", "scenario": "reschedule"})
    res = client.get("/api/stats")
    assert res.status_code == 200
    stats = res.json()
    assert stats["total_orders"] == 2
    assert stats["rescheduled_recovered"] == 1
