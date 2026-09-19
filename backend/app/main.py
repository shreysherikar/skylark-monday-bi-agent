from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any

from app.config import settings

app = FastAPI(
    title=settings.app_name,
    description="Conversational BI Agent API for Skylark Drones (Monday.com integration)",
    version="0.1.0",
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class HealthResponse(BaseModel):
    status: str
    environment: str
    version: str


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint for container orchestrators and monitors."""
    return HealthResponse(
        status="healthy",
        environment=settings.environment,
        version="0.1.0",
    )


@app.get("/")
async def root() -> Dict[str, Any]:
    """Base entrypoint returning API metadata."""
    return {
        "name": settings.app_name,
        "status": "online",
        "docs_url": "/docs",
    }
