import os
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from d2c_app.config import d2c_settings
from d2c_app.database import init_d2c_db
from d2c_app.routes.analytics import router as analytics_router
from d2c_app.routes.cart import router as cart_router
from d2c_app.routes.checkout import router as checkout_router
from d2c_app.routes.logistics import router as logistics_router
from d2c_app.routes.orders import router as orders_router
from d2c_app.routes.products import router as products_router
from d2c_app.seed_d2c import seed_d2c_database

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("d2c_app")

# Initialize database and seed products
init_d2c_db()
try:
    seed_d2c_database()
except Exception as e:
    logger.warning(f"D2C seed note: {e}")

d2c_app = FastAPI(
    title="Aura Luxe D2C Commerce Application",
    description="Full-featured Direct-to-Consumer e-commerce platform with automated AI voice recovery integration",
    version="1.0.0",
)

d2c_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount D2C API Routers
d2c_app.include_router(products_router, prefix="/api/d2c")
d2c_app.include_router(cart_router, prefix="/api/d2c")
d2c_app.include_router(checkout_router, prefix="/api/d2c")
d2c_app.include_router(orders_router, prefix="/api/d2c")
d2c_app.include_router(logistics_router, prefix="/api/d2c")
d2c_app.include_router(analytics_router, prefix="/api/d2c")

# Mount Static UI Files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir, exist_ok=True)
d2c_app.mount("/static", StaticFiles(directory=static_dir), name="d2c_static")


@d2c_app.get("/", include_in_schema=False)
@d2c_app.get("/d2c", include_in_schema=False)
async def serve_d2c_storefront():
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "D2C Storefront API is live. Loading UI..."}
