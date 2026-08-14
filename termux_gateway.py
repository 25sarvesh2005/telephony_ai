"""
Auto-Dialing Termux Jio Call Gateway
Opens dialer and immediately auto-presses the green Call button (KEYCODE_CALL).
"""
import os
import time
from flask import Flask, jsonify, request

app = Flask(__name__)


@app.route("/call", methods=["POST"])
def make_call():
    data = request.get_json(force=True) or {}
    phone = data.get("phone", "").strip()
    if not phone:
        return jsonify({"error": "Missing phone"}), 400

    print(f"📞 Auto-dialing {phone} on Jio SIM...")
    
    # 1. Try native termux-telephony-call
    os.system(f"termux-telephony-call {phone}")
    
    # 2. Direct CALL Intent
    os.system(f"am start -a android.intent.action.CALL -d tel:{phone}")
    
    # 3. DIAL Intent + Auto-press Green Call Button (input keyevent 5 = KEYCODE_CALL)
    os.system(f"am start -a android.intent.action.DIAL -d tel:{phone}")
    time.sleep(0.6)
    os.system("input keyevent 5")

    return jsonify({"status": "calling", "phone": phone})


@app.route("/status", methods=["GET"])
def get_status():
    return jsonify({"status": "online", "sim": "Jio VoLTE"})


if __name__ == "__main__":
    print("🚀 Auto-Dialing Jio Gateway RUNNING on port 8080...")
    app.run(host="0.0.0.0", port=8080)
