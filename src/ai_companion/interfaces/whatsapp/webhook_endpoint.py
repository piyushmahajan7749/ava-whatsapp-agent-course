import logging

from fastapi import FastAPI

from ai_companion.interfaces.dashboard import dashboard_router
from ai_companion.interfaces.whatsapp.whatsapp_response import whatsapp_router
from ai_companion.modules.angc import db as angc_db
from ai_companion.modules.angc import scheduler as angc_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("=" * 60)
logger.info("STARTING ANGC ASSISTANT")
logger.info("=" * 60)

app = FastAPI(title="ANGC Executive Assistant API", version="1.0.0")


@app.on_event("startup")
async def startup() -> None:
    angc_db.init_db()
    logger.info("✓ ANGC tasks DB initialised at %s", angc_db._db_path())
    angc_scheduler.start()


@app.on_event("shutdown")
async def shutdown() -> None:
    angc_scheduler.stop()


app.include_router(whatsapp_router)
app.include_router(dashboard_router)

logger.info("✓ Routers included: whatsapp webhook + dashboard")
