from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db, close_db
from app.api.routes import auth, exams, syllabus, resources
from app.api.routes.modules import router as modules_router, exam_modules_router
from app.api.routes.daily import router as daily_router
from app.services.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: connect to MongoDB Atlas + init Beanie + start APScheduler. Shutdown: clean up."""
    await init_db()
    start_scheduler()
    yield
    stop_scheduler()
    await close_db()


app = FastAPI(
    title="Ascendra API",
    description="AI-powered exam preparation mentor",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all routers under /api prefix
app.include_router(auth.router, prefix="/api")
app.include_router(exams.router, prefix="/api")
app.include_router(syllabus.router, prefix="/api")
app.include_router(resources.router, prefix="/api")
app.include_router(modules_router, prefix="/api")
app.include_router(exam_modules_router, prefix="/api")
app.include_router(daily_router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}
