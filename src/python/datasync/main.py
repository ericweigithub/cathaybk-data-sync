"""
應用程式進入點

啟動流程：
  1. 載入 config.yaml（或環境變數指定路徑）
  2. 設定 Log（檔案輪替 + Console）
  3. 建立 SyncService
  4. 啟動 APScheduler 排程
  5. 啟動 FastAPI / uvicorn HTTP 服務（供健康檢查與手動觸發使用）

執行方式：
  python -m datasync.main
  datasync          # 若已安裝 wheel
"""

from __future__ import annotations

import argparse
import logging
import logging.handlers
import os
import signal
import sys
from pathlib import Path

import uvicorn

from .api import app, set_sync_service
from .client import CloudabilityClientFactory
from .config import load_config
from .scheduler import SyncScheduler
from .service import SyncService

# ---------------------------------------------------------------------------
# Logging 設定
# ---------------------------------------------------------------------------


def _setup_logging(log_path: str, level: str = "INFO") -> None:
    log_dir = Path(log_path).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    # Console Handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    root_logger.addHandler(console)

    # Rotating File Handler（保留 30 天，每個檔案最大 50 MB）
    file_handler = logging.handlers.TimedRotatingFileHandler(
        log_path,
        when="midnight",
        backupCount=30,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    root_logger.addHandler(file_handler)


# ---------------------------------------------------------------------------
# 主程式
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="國泰 Apptio 雲端認證資料同步服務")
    parser.add_argument(
        "--config",
        default=os.environ.get("CONFIG_PATH", "config.yaml"),
        help="config.yaml 路徑（預設：./config.yaml）",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("SERVER_HOST", "0.0.0.0"),
        help="HTTP 服務監聽 IP（預設：0.0.0.0）",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("SERVER_PORT", "8080")),
        help="HTTP 服務監聽 Port（預設：8080）",
    )
    parser.add_argument(
        "--log-level",
        default=os.environ.get("LOG_LEVEL", "INFO"),
        help="Log 等級（預設：INFO）",
    )
    args = parser.parse_args()

    # 1. 載入設定
    config = load_config(args.config)

    # 2. 設定 Log
    _setup_logging(config.sync.log_path, level=args.log_level)

    logger.info("cathaybk-data-sync 啟動中，設定檔：%s", args.config)
    logger.info(
        "子公司環境數量：%d，Vendors：%s",
        len(config.cloudability.subsidiaries),
        config.sync.vendors,
    )

    # 3. 建立服務
    factory = CloudabilityClientFactory(config.cloudability)
    service = SyncService(factory, config.sync)
    set_sync_service(service)

    # 4. 啟動排程
    scheduler = SyncScheduler(service, config.sync)
    scheduler.start()

    # 優雅關機：捕捉 SIGTERM / SIGINT
    def _shutdown(signum: int, frame: object) -> None:
        logger.info("收到關機信號（%d），停止排程...", signum)
        scheduler.stop()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    # 5. 啟動 uvicorn
    logger.info("HTTP 服務啟動：http://%s:%d", args.host, args.port)
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_config=None,   # 使用上面設定的 logging，不讓 uvicorn 覆蓋
    )


if __name__ == "__main__":
    main()
