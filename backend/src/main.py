from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.core.config import settings
from src.core.telemetry import setup_telemetry

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
)

# Set CORS origins
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Set up logging & metrics
setup_telemetry(app)

from src.adapters.api.controllers.auth import router as auth_router
app.include_router(auth_router, prefix=settings.API_V1_STR)

from src.adapters.api.controllers.escrow import router as escrow_router
app.include_router(escrow_router, prefix=settings.API_V1_STR)

from src.adapters.api.controllers.ledger import router as ledger_router
app.include_router(ledger_router, prefix=settings.API_V1_STR)

from src.adapters.api.controllers.dispute import router as dispute_router
app.include_router(dispute_router, prefix=settings.API_V1_STR)

from src.adapters.api.controllers.chat import router as chat_router
app.include_router(chat_router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    return {
        "status": "healthy",
        "project": settings.PROJECT_NAME,
        "environment": settings.ENV
    }

@app.get("/health")
async def health_check():
    # Simple check for API health
    return {"status": "ok"}
