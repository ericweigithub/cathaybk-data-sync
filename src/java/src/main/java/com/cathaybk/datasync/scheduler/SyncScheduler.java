package com.cathaybk.datasync.scheduler;

import com.cathaybk.datasync.model.SyncResult;
import com.cathaybk.datasync.service.SyncService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/**
 * 同步排程器
 *
 * <p>
 * 依照 application.yml 中 {@code sync.cron} 設定自動觸發同步作業。
 * 預設為每日凌晨 02:00 執行一次。
 * </p>
 *
 * <p>
 * 若要停用排程（僅手動觸發），可設定 {@code sync.schedule-enabled=false}，
 * 將 cron 設為 {@code "-"} 即可停用此排程。
 * </p>
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class SyncScheduler {

    private final SyncService syncService;

    /**
     * 排程同步作業
     * Cron 表達式由 application.yml 的 sync.cron 設定注入
     * 若 sync.schedule-enabled=false，cron 值設為 "-" 停用
     */
    @Scheduled(cron = "#{syncProperties.scheduleEnabled ? syncProperties.cron : '-'}")
    public void scheduledSync() {
        log.info("排程同步作業觸發");
        SyncResult result = syncService.sync();
        logSyncResult(result);
    }

    /**
     * 記錄同步結果摘要至 Log
     */
    private void logSyncResult(SyncResult result) {
        if (result.isSuccess()) {
            log.info("排程同步作業完成：新增 {} 筆、更新 {} 筆、跳過 {} 筆、失敗 {} 筆，耗時 {} 秒",
                    result.getCreatedCount(),
                    result.getUpdatedCount(),
                    result.getSkippedCount(),
                    result.getFailedCount(),
                    computeDurationSeconds(result));
        } else {
            log.error("排程同步作業失敗：{}，新增 {} 筆、更新 {} 筆、失敗 {} 筆",
                    result.getErrorMessage(),
                    result.getCreatedCount(),
                    result.getUpdatedCount(),
                    result.getFailedCount());
        }
    }

    private long computeDurationSeconds(SyncResult result) {
        if (result.getStartedAt() == null || result.getFinishedAt() == null) {
            return 0;
        }
        return result.getFinishedAt().getEpochSecond() - result.getStartedAt().getEpochSecond();
    }
}
