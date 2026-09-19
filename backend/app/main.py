"""FastAPI application entrypoint for Skylark Drones Monday.com BI Agent."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.agent.orchestrator import AgentLLMError, AgentOrchestrator
from app.config import settings
from app.monday_mcp.client import MondayAPIError

logger = logging.getLogger(__name__)

# Locate compiled frontend assets if available (local development or container)
_candidate_paths = [
    Path(__file__).resolve().parent.parent.parent / "frontend" / "dist",
    Path("/app/frontend/dist"),
    Path("frontend/dist"),
]
FRONTEND_DIST: Path | None = next((p for p in _candidate_paths if p.is_dir()), None)

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


# ---------------------------------------------------------------------------
# Request & Response Models
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    environment: str
    version: str


class ChatRequest(BaseModel):
    message: str = Field(..., description="User's query or instruction for the BI agent")
    history: list[dict[str, str]] | None = Field(
        default=None,
        description="Optional prior conversation turns: [{'role': 'user'|'assistant', 'content': '...'}]"
    )


class ChatResponse(BaseModel):
    response: str
    tools_used: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    needs_clarification: bool = False
    suggested_options: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint for container orchestrators and monitors."""
    return HealthResponse(
        status="healthy",
        environment=settings.environment,
        version="0.1.0",
    )


@app.get("/")
async def root(request: Request) -> Any:
    """Base entrypoint: returns the SPA frontend for browsers, or API metadata for JSON callers."""
    accept = request.headers.get("accept", "").lower()
    if "text/html" in accept and FRONTEND_DIST is not None:
        index_file = FRONTEND_DIST / "index.html"
        if index_file.is_file():
            return FileResponse(index_file)
    return {
        "name": settings.app_name,
        "status": "online",
        "docs_url": "/docs",
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest) -> ChatResponse:
    """Conversational BI chat endpoint orchestrating Claude tool use and data caveats."""
    if not request.message.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query message cannot be empty.",
        )

    try:
        orchestrator = AgentOrchestrator()
        result = orchestrator.ask(request.message, history=request.history)
        return ChatResponse(
            response=result.response,
            tools_used=result.tools_used,
            caveats=result.caveats,
            needs_clarification=result.needs_clarification,
            suggested_options=result.suggested_options,
        )
    except AgentLLMError as llm_ex:
        logger.error("LLM provider failure while processing chat request: %s", llm_ex)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Reasoning engine unavailable: {llm_ex}",
        )
    except MondayAPIError as monday_ex:
        logger.error("Monday.com API failure while processing chat request: %s", monday_ex)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Monday.com is currently unavailable: {monday_ex}",
        )
    except ValueError as ve:
        logger.warning("Configuration or validation error in chat: %s", ve)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(ve),
        )
    except Exception as ex:
        logger.exception("Unexpected error processing chat request")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while processing your request: {ex}",
        )


@app.get("/api/overview")
async def get_overview_metrics() -> dict[str, Any]:
    """Provides deterministic executive overview KPIs from Monday.com boards."""
    try:
        from app.agent.tools import _load_normalized_deals, _load_normalized_work_orders
        from app.data.analytics import (
            compute_cross_board_delivery,
            compute_pipeline_summary,
            compute_revenue_summary,
            get_data_quality_summary,
        )

        deals_df = _load_normalized_deals()
        wo_df, wo_items = _load_normalized_work_orders()
        pipe = compute_pipeline_summary(deals_df)
        rev = compute_revenue_summary(wo_df)
        delivery = compute_cross_board_delivery(wo_df, deals_df, wo_items=wo_items)

        # Data-quality telemetry for dashboard banner annotations (all values computed live,
        # never hardcoded in the UI layer).
        quality = get_data_quality_summary(
            norm_wo_df=wo_df,
            norm_deals_df=deals_df,
            board_name="both",
            wo_items=wo_items,
        )
        deals_rep = quality.get("deals", {})
        wo_rep = quality.get("work_orders", {})
        data_quality = {
            "caveat_metrics": quality.get("caveat_metrics", {}),
            "caveats": quality.get("caveats", {}),
            "deals_total_rows": deals_rep.get("total_rows", 0),
            "deals_close_date_null_count": deals_rep.get("null_counts", {}).get("Close Date (A)", 0),
            "work_orders_total_rows": wo_rep.get("total_rows", 0),
            "work_orders_fully_null_columns": wo_rep.get("fully_null_columns", []),
        }

        return {
            "pipeline": pipe,
            "revenue": rev,
            "delivery": delivery,
            "data_quality": data_quality,
        }
    except MondayAPIError as monday_ex:
        logger.error("Monday.com API failure while calculating overview metrics: %s", monday_ex)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Monday.com is currently unavailable: {monday_ex}",
        )
    except Exception as ex:
        logger.exception("Error calculating overview metrics")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculating overview metrics: {ex}",
        )


@app.get("/api/quality")
async def get_quality_metrics() -> dict[str, Any]:
    """Provides data quality audit and null-rate metrics across boards."""
    try:
        from app.agent.tools import _load_normalized_deals, _load_normalized_work_orders
        from app.data.analytics import get_data_quality_summary

        deals_df = _load_normalized_deals()
        wo_df, wo_items = _load_normalized_work_orders()
        return get_data_quality_summary(
            norm_wo_df=wo_df,
            norm_deals_df=deals_df,
            board_name="both",
            wo_items=wo_items,
        )
    except MondayAPIError as monday_ex:
        logger.error("Monday.com API failure while calculating quality metrics: %s", monday_ex)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Monday.com is currently unavailable: {monday_ex}",
        )
    except Exception as ex:
        logger.exception("Error calculating quality metrics")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculating quality metrics: {ex}",
        )


@app.get("/api/cross-board")
async def get_cross_board_intelligence(
    sector: str | None = None,
    view: str | None = None,
) -> dict[str, Any]:
    """Provides detailed cross-board intelligence between Deals (CRM) and Work Orders (Fulfillment)."""
    try:
        from app.agent.tools import _load_normalized_deals, _load_normalized_work_orders
        from app.data.analytics import compute_cross_board_delivery

        deals_df = _load_normalized_deals()
        wo_df, wo_items = _load_normalized_work_orders()
        return compute_cross_board_delivery(
            norm_wo_df=wo_df,
            norm_deals_df=deals_df,
            wo_items=wo_items,
            sector=sector,
            view=view,
        )
    except MondayAPIError as monday_ex:
        logger.error("Monday.com API failure while calculating cross-board metrics: %s", monday_ex)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Monday.com is currently unavailable: {monday_ex}",
        )
    except Exception as ex:
        logger.exception("Error calculating cross-board metrics")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculating cross-board metrics: {ex}",
        )


# Mount compiled frontend static assets for SPA production serving
if FRONTEND_DIST is not None and (FRONTEND_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")


