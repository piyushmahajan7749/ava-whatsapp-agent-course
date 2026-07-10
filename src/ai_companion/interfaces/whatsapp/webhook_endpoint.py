import logging

from fastapi import FastAPI

from ai_companion.interfaces.dashboard import dashboard_router
from ai_companion.interfaces.whatsapp.whatsapp_response import whatsapp_router
from ai_companion.modules.angc import db as angc_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("=" * 60)
logger.info("STARTING ANGC ASSISTANT")
logger.info("=" * 60)

app = FastAPI(title="ANGC Executive Assistant API", version="1.0.0")


@app.on_event("startup")
def startup() -> None:
    angc_db.init_db()
    logger.info("✓ ANGC tasks DB initialised at %s", angc_db._db_path())


app.include_router(whatsapp_router)
app.include_router(dashboard_router)

logger.info("✓ Routers included: whatsapp webhook + dashboard")
