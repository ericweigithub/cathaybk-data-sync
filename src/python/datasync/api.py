"""
FastAPI 手動觸發端點

提供 HTTP 端點供排程主機或維運人員手動觸發同步作業，
無需等待排程時間。

端點：
  POST /api/sync/trigger  — 手動觸發同步
  GET  /health            — 健康檢查
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .service import SyncService

logger = logging.getLogger(__name__)

app = FastAPI(
    title="cathaybk-data-sync",
    description="國泰 Apptio 雲端認證資料同步服務",
    version="1.0.0",
)

# SyncService 由 main.py 在啟動時注入
_sync_service: SyncService | None = None


def set_sync_service(service: SyncService) -> None:
    """由 main.py 在應用程式啟動時注入 SyncService"""
    global _sync_service  # noqa: PLW0603
    _sync_service = service


# ---------------------------------------------------------------------------
# Response Schemas
# ---------------------------------------------------------------------------


class SyncResultResponse(BaseModel):
    success: bool
    started_at: str | None = None
    finished_at: str | None = None
    created_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    error_message: str | None = None


class HealthResponse(BaseModel):
    status: str
    timestamp: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post(
    "/api/sync/trigger",
    response_model=SyncResultResponse,
    summary="手動觸發同步作業",
    responses={
        200: {"description": "同步成功"},
        500: {"description": "同步失敗"},
        503: {"description": "服務尚未初始化"},
    },
)
def trigger_sync() -> JSONResponse:
    """手動觸發雲端帳號認證資料同步作業"""
    if _sync_service is None:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "SyncService 尚未初始化"},
        )

    logger.info("接收手動觸發同步請求")
    result = _sync_service.sync()

    response_data = SyncResultResponse(
        success=result.success,
        started_at=result.started_at.isoformat() if result.started_at else None,
        finished_at=result.finished_at.isoformat() if result.finished_at else None,
        created_count=result.created_count,
        updated_count=result.updated_count,
        skipped_count=result.skipped_count,
        failed_count=result.failed_count,
        error_message=result.error_message,
    )

    http_status = status.HTTP_200_OK if result.success else status.HTTP_500_INTERNAL_SERVER_ERROR
    return JSONResponse(status_code=http_status, content=response_data.model_dump())


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="健康檢查",
)
def health_check() -> HealthResponse:
    return HealthResponse(
        status="UP",
        timestamp=datetime.utcnow().isoformat() + "Z",
    )
