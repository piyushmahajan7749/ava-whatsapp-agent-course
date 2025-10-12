import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ai_companion.interfaces.whatsapp.whatsapp_response import whatsapp_router

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("=" * 60)
logger.info("STARTING WEBHOOK ENDPOINT")
logger.info("=" * 60)

# Import conversations router
try:
    from ai_companion.interfaces.api_endpoints import conversations_router
    logger.info("✓ Successfully imported conversations_router")
    logger.info(f"  Conversations router has {len(conversations_router.routes)} routes")
    for route in conversations_router.routes:
        logger.info(f"    - {route.path}")
except Exception as e:
    logger.error(f"✗ Failed to import conversations_router: {e}")
    logger.exception("Full traceback:")
    conversations_router = None

app = FastAPI(title="Upaai AI Companion API", version="1.0.0")

# CORS middleware for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://upaai.in",
        "https://www.upaai.in",
        "http://localhost:3000",  # For local development
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Include routers
logger.info("Including routers...")
app.include_router(whatsapp_router)
logger.info("✓ Included whatsapp_router")

if conversations_router:
    app.include_router(conversations_router)
    logger.info("✓ Included conversations_router")
else:
    logger.warning("✗ Skipping conversations_router (failed to import)")

logger.info("=" * 60)
logger.info(f"Total routes registered: {len(app.routes)}")
for route in app.routes:
    if hasattr(route, 'path'):
        logger.info(f"  - {route.path}")
logger.info("=" * 60)
