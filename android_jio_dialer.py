#!/usr/bin/env python3
"""
Android Jio Phone Dialer CLI
Triggers automated calls directly from your Android phone with Jio SIM.
Usage:
    python android_jio_dialer.py
    python android_jio_dialer.py --order ORD-9481 --phone +919876543210
"""
import argparse
import sys

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from app.database import SessionLocal, init_db
from app.models import Order
from app.services.android_gateway import android_gateway


def main():
    parser = argparse.ArgumentParser(description="Dial customers directly using your Android Jio SIM phone")
    parser.add_argument("--phone", "-p", help="Customer destination phone number (e.g. +919876543210)")
    parser.add_argument("--order", "-o", help="Order ID to resolve (e.g. ORD-9481)")
    args = parser.parse_args()

    init_db()
    db = SessionLocal()

    try:
        order_id = args.order
        if not order_id:
            failed_orders = db.query(Order).filter(Order.status == "DELIVERY_FAILED").all()
            if not failed_orders:
                print("No failed orders in database. Run 'python seed_data.py' first.")
                return

            print("\n" + "=" * 55)
            print("  SELECT FAILED ORDER TO CALL VIA YOUR JIO PHONE:")
            print("=" * 55)
            for idx, o in enumerate(failed_orders, 1):
                print(f"  [{idx}] {o.order_id} - {o.customer_name} ({o.currency} {o.amount:.2f}) - {o.city}")

            choice = input(f"\nSelect order [1-{len(failed_orders)}] (default 1): ").strip()
            idx = int(choice) - 1 if choice.isdigit() and 1 <= int(choice) <= len(failed_orders) else 0
            order_id = failed_orders[idx].order_id

        order = db.query(Order).filter(Order.order_id == order_id).first()
        if not order:
            print(f"Order {order_id} not found.")
            return

        phone = args.phone or order.customer_phone

        print("\n" + "=" * 55)
        print("  ANDROID JIO TELEPHONY BRIDGE — OUTBOUND CALL")
        print("=" * 55)
        print(f"• Calling Customer:  {phone} ({order.customer_name})")
        print(f"• Order Reference:   {order.order_id} - Amount: {order.currency} {order.amount:.2f}")
        print(f"• Dialing Method:    Android Phone (Jio VoLTE SIM - ₹0 Free Calling)")
        print("=" * 55)

        print(f"\nInitiating call to {phone} via Termux Gateway (http://192.0.0.4:8080)...")
        import asyncio
        result = asyncio.run(android_gateway.dial_via_http_gateway(phone_number=phone))

        if not result.get("success"):
            # Fallback to ADB if HTTP fails
            print(f"HTTP Gateway failed ({result.get('error')}), trying ADB USB bridge...")
            result = android_gateway.dial_via_adb(phone_number=phone)

        if result.get("success"):
            print(f"\n✅ SUCCESS: Call triggered on your Jio Phone!")
            print(f"• Target Phone: {result.get('phone_number')}")
            print(f"• Status:       {result.get('status')}")
            print("\nYour Android phone is now actively dialing the customer using your Jio VoLTE SIM!")
        else:
            print(f"\n❌ Dialing failed: {result.get('error')}")
            print("Make sure Termux is running 'python gateway.py' on your phone.")

        print("=" * 55 + "\n")

    finally:
        db.close()


if __name__ == "__main__":
    main()
