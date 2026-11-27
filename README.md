# Telephony AI — Commerce Recovery Engine

Automated voice telephony orchestrator built with **FastAPI** and **SQLAlchemy** for recovering failed Cash-on-Delivery (COD) deliveries and abandoned carts via [eigi.ai](https://eigi.ai) voice agents, paired with a companion D2C storefront demo (`/d2c`).

---

## Key Capabilities

- **Outbound Recovery Orchestration:** Triggers and tracks outbound AI recovery calls via `/trigger-call` and `/simulate-call`.
- **Structured Webhook Ingestion:** Handles completed call transcripts and structured intent extraction (`reschedule`, `cancel`, `wrong_address`, `escalate_human`) at `/webhooks/eigi/call-completed` and `/api/sync-calls`.
- **Operations & Resolution Pipeline:** Persists orders, call logs, and resolution decisions in SQLAlchemy with REST endpoints (`/api/orders`, `/api/call-logs`, `/api/resolutions`, `/api/dashboard-stats`).
- **Integrated D2C Storefront (`/d2c`):** Mounted sub-application with product catalog, cart, checkout, order tracking, logistics, and recovery bridge routes.
- **Mobile Gateway Helpers:** Includes `android_jio_dialer.py` and `termux_gateway.py` utilities for local dialer testing.

---

## Project Structure

```text
telephony_ai/
├── app/                     # Core FastAPI recovery orchestrator, models & services
│   ├── services/            # eigi_client, extractor, operations_agent, resolution_agent
│   └── static/              # Recovery dashboard frontend
├── d2c_app/                 # Mounted D2C storefront app, routes & services
├── tests/                   # Pytest suites (test_engine.py, test_d2c.py)
├── EIGI_AGENT_SETUP.md      # Voice agent prompt, schema & webhook configuration guide
├── seed_data.py             # Sample order & recovery seed script
├── requirements.txt
└── .env.example
```

---

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # Configure EIGI_* credentials and DATABASE_URL

uvicorn app.main:app --reload
```

- Recovery Dashboard: `http://127.0.0.1:8000/`
- D2C Demo Storefront: `http://127.0.0.1:8000/d2c/`
- OpenAPI Docs: `http://127.0.0.1:8000/docs`

### Running Tests

```bash
python -m pytest -v
```

For agent prompt, structured JSON schema, and webhook setup details, see [EIGI_AGENT_SETUP.md](EIGI_AGENT_SETUP.md).
