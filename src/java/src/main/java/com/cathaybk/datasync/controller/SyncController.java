package com.cathaybk.datasync.controller;

import com.cathaybk.datasync.model.SyncResult;
import com.cathaybk.datasync.service.SyncService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 同步作業手動觸發 REST 控制器
 *
 * <p>提供 HTTP 端點供排程主機或維運人員手動觸發同步作業，
 * 無需等待排程時間。</p>
 */
@Slf4j
@RestController
@RequestMapping("/api/sync")
@RequiredArgsConstructor
public class SyncController {

    private final SyncService syncService;

    /**
     * 手動觸發同步作業
     *
     * <pre>
     * POST /api/sync/trigger
     * </pre>
     *
     * @return 同步結果摘要
     */
    @PostMapping("/trigger")
    public ResponseEntity<SyncResultResponse> triggerSync() {
        log.info("接收手動觸發同步請求");

        SyncResult result = syncService.sync();

        SyncResultResponse response = SyncResultResponse.from(result);
        return result.isSuccess()
                ? ResponseEntity.ok(response)
                : ResponseEntity.internalServerError().body(response);
    }

    // ----------------------------------------------------------------
    // Response DTO
    // ----------------------------------------------------------------

    /**
     * 同步結果回應 DTO
     */
    public record SyncResultResponse(
            boolean success,
            String startedAt,
            String finishedAt,
            int createdCount,
            int updatedCount,
            int skippedCount,
            int failedCount,
            String errorMessage
    ) {
        public static SyncResultResponse from(SyncResult result) {
            return new SyncResultResponse(
                    result.isSuccess(),
                    result.getStartedAt() != null ? result.getStartedAt().toString() : null,
                    result.getFinishedAt() != null ? result.getFinishedAt().toString() : null,
                    result.getCreatedCount(),
                    result.getUpdatedCount(),
                    result.getSkippedCount(),
                    result.getFailedCount(),
                    result.getErrorMessage()
            );
        }
    }
}
