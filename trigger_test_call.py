#!/usr/bin/env python3
"""
CLI Helper to trigger a real or simulated recovery phone call to your personal phone number.
Usage:
    python trigger_test_call.py
    python trigger_test_call.py --phone +919876543210 --order ORD-9481
"""
import argparse
import asyncio
import sys

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from voice_ai.config import settings
from voice_ai.database import SessionLocal, init_db
from voice_ai.models import Order
from voice_ai.services.eigi_client import eigi_client


def list_failed_orders(db):
    return db.query(Order).filter(Order.status == "DELIVERY_FAILED").all()


async def main():
    parser = argparse.ArgumentParser(description="Trigger recovery call to your personal phone")
    parser.add_argument("--phone", "-p", help="Customer phone number in E.164 format (e.g. +919876543210)")
    parser.add_argument("--from-number", "-f", help="Caller ID phone number (your personal verified number)")
    parser.add_argument("--order", "-o", help="Order ID to use (e.g. ORD-9481)")
    args = parser.parse_args()

    init_db()
    db = SessionLocal()

    try:
        # 1. Resolve Order ID
        order_id = args.order
        if not order_id:
            failed_orders = list_failed_orders(db)
            if not failed_orders:
                print("⚠️ No failed orders found. Run 'python seed_data.py' first.")
                return

            print("\nAvailable Failed Orders:")
            for idx, o in enumerate(failed_orders, 1):
                print(f"  [{idx}] {o.order_id} - {o.customer_name} ({o.currency} {o.amount:.2f}, {o.delivery_attempts} attempt(s)) - {o.city}")

            choice = input(f"\nSelect order [1-{len(failed_orders)}] (default 1): ").strip()
            idx = int(choice) - 1 if choice.isdigit() and 1 <= int(choice) <= len(failed_orders) else 0
            order_id = failed_orders[idx].order_id

        order = db.query(Order).filter(Order.order_id == order_id).first()
        if not order:
            print(f"❌ Error: Order {order_id} not found.")
            return

        # 2. Resolve Customer Phone & Caller ID
        phone = args.phone or settings.DEFAULT_TEST_PHONE
        if not phone or phone == "+91XXXXXXXXXX":
            phone = input(f"Enter customer/destination phone number (E.164 format, e.g. +919876543210): ").strip()

        from_phone = args.from_number or settings.CALLER_ID_NUMBER or None

        print("\n" + "=" * 60)
        print("  AI COMMERCE RECOVERY ENGINE — OUTBOUND CALL DISPATCH")
        print("=" * 60)
        print(f"• Caller ID (From): {from_phone or 'Default eigi.ai Trunk'}")
        print(f"• Calling (To):     {phone}")
        print(f"• Order ID:         {order.order_id}")
        print(f"• Customer Name:    {order.customer_name}")
        print(f"• Amount:           {order.currency} {order.amount:.2f} ({order.payment_method})")
        print(f"• Agent ID:         {settings.EIGI_AGENT_ID}")
        print(f"• Mode:             {'SIMULATION (Sandbox)' if settings.SIMULATION_MODE else 'LIVE (eigi.ai Telephony)'}")
        print("=" * 60)

        if settings.SIMULATION_MODE or settings.EIGI_API_KEY.startswith("mock_"):
            print("ℹ️ Note: Running in SIMULATION_MODE. To place a real live call:")
            print("   1. Open .env and set SIMULATION_MODE=False")
            print("   2. Add your EIGI_API_KEY and EIGI_AGENT_ID in .env")
            print("   3. Add your verified personal number as CALLER_ID_NUMBER in .env\n")

        # Injected Prompt Variables
        variables = {
            "order_id": order.order_id,
            "customer_name": order.customer_name,
            "amount": f"{order.currency} {order.amount:.2f}",
            "merchant_name": settings.MERCHANT_NAME,
            "delivery_attempts": order.delivery_attempts,
            "city": order.city or "your area",
        }

        # Update order status
        order.status = "CALL_IN_PROGRESS"
        order.notes = f"Outbound call initiated to {phone} (Caller ID: {from_phone or 'default'}) via eigi.ai."
        db.commit()

        print(f"📞 Dispatching outbound call to {phone} from {from_phone or 'default'}...")
        result = await eigi_client.start_call(
            to_number=phone,
            from_number=from_phone,
            variables=variables,
            agent_id=settings.EIGI_AGENT_ID,
        )

        print("\nResult:")
        print(f"• Success: {result.get('success')}")
        print(f"• Call ID: {result.get('call_id')}")
        print(f"• Status:  {result.get('status')}")
        print(f"• Message: {result.get('message', 'Call queued on provider')}")

        print("\nNext Steps:")
        print("1. When the phone rings, answer and act as the customer (e.g. 'Can you deliver tomorrow at 6 PM?').")
        print("2. When call ends, eigi.ai posts the transcript & intent to your webhook.")
        print("3. Check the dashboard at http://127.0.0.1:8000 to see the live resolution!")
        print("=" * 60 + "\n")

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
