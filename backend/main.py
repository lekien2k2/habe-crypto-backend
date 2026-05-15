"""HABE Crypto Backend - FastAPI Application.

Hierarchical Attribute-Based Encryption system with CP-ABE and S3 storage.
Provides REST API endpoints for crypto system setup, key generation,
file encryption/upload, and file download/decryption.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.exceptions import register_exception_handlers
from backend.routers import admin, files, health


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager for startup/shutdown.

    Handles resource initialization on startup and cleanup on shutdown.
    """
    # Startup
    yield
    # Shutdown - cleanup resources if needed


app = FastAPI(
    title="HABE Crypto Backend",
    description="Hierarchical Attribute-Based Encryption system with CP-ABE and S3 storage",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health.router)
app.include_router(admin.router)
app.include_router(files.router)

# Register global exception handlers
register_exception_handlers(app)
