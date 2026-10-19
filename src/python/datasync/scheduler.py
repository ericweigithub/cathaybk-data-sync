"""
同步排程器

使用 APScheduler 依照 config.yaml 中 sync.cron 設定自動觸發同步作業。
預設為每日凌晨 02:00 執行一次（cron: "0 2 * * *"）。

若 sync.schedule_enabled = false，將跳過排程設定，僅支援手動觸發。
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import SyncConfig
from .models import SyncResult
from .service import SyncService

logger = logging.getLogger(__name__)


class SyncScheduler:
    """
    同步排程管理器

    以 BackgroundScheduler 在背景執行排程，不阻塞主執行緒。
    """

    def __init__(self, sync_service: SyncService, sync_config: SyncConfig) -> None:
        self._service = sync_service
        self._config = sync_config
        self._scheduler = BackgroundScheduler(timezone="Asia/Taipei")

    def start(self) -> None:
        """啟動排程（若 schedule_enabled = False 則略過）"""
        if not self._config.schedule_enabled:
            logger.info("排程已停用（schedule_enabled=false），僅支援手動觸發")
            return

        trigger = CronTrigger.from_crontab(self._config.cron, timezone="Asia/Taipei")
        self._scheduler.add_job(
            self._run_scheduled_sync,
            trigger=trigger,
            id="data_sync",
            replace_existing=True,
        )
        self._scheduler.start()
        logger.info("排程已啟動，Cron 表達式：%s", self._config.cron)

    def stop(self) -> None:
        """停止排程"""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("排程已停止")

    def _run_scheduled_sync(self) -> None:
        """排程觸發的同步作業"""
        logger.info("排程同步作業觸發")
        result = self._service.sync()
        self._log_result(result)

    @staticmethod
    def _log_result(result: SyncResult) -> None:
        if result.success:
            duration = 0
            if result.started_at and result.finished_at:
                duration = int(
                    (result.finished_at - result.started_at).total_seconds()
                )
            logger.info(
                "排程同步作業完成：新增 %d 筆、更新 %d 筆、跳過 %d 筆、失敗 %d 筆，耗時 %d 秒",
                result.created_count,
                result.updated_count,
                result.skipped_count,
                result.failed_count,
                duration,
            )
        else:
            logger.error(
                "排程同步作業失敗：%s，新增 %d 筆、更新 %d 筆、失敗 %d 筆",
                result.error_message,
                result.created_count,
                result.updated_count,
                result.failed_count,
            )
