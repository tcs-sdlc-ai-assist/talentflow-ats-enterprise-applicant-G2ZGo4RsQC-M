import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.core.config import settings
from app.core.database import Base, engine, async_session
from app.routers import auth, landing, jobs, candidates, applications, interviews, dashboard, audit
from app.services.auth_service import seed_admin

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting TalentFlow ATS...")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created/verified")

    async with async_session() as db:
        try:
            admin = await seed_admin(db)
            if admin:
                logger.info("Default admin user seeded: %s", admin.username)
            await db.commit()
        except Exception:
            await db.rollback()
            logger.exception("Failed to seed default admin user")

    logger.info("TalentFlow ATS startup complete")
    yield

    await engine.dispose()
    logger.info("TalentFlow ATS shutdown complete")


app = FastAPI(
    title="TalentFlow ATS",
    description="Applicant Tracking System",
    version="1.0.0",
    lifespan=lifespan,
)

static_dir = Path(__file__).resolve().parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
else:
    logger.warning("Static directory not found at %s", static_dir)

app.include_router(landing.router)
app.include_router(auth.router)
app.include_router(jobs.router)
app.include_router(candidates.router)
app.include_router(applications.router)
app.include_router(interviews.router)
app.include_router(dashboard.router)
app.include_router(audit.router, prefix="/dashboard")