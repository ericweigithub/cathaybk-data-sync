package com.cathaybk.datasync.model;

import lombok.Builder;
import lombok.Data;

import java.time.Instant;
import java.util.List;

/**
 * 單次同步作業執行結果
 */
@Data
@Builder
public class SyncResult {

    /** 同步開始時間 */
    private Instant startedAt;

    /** 同步結束時間 */
    private Instant finishedAt;

    /** 本次同步是否成功 */
    private boolean success;

    /** 新增帳號數量 */
    private int createdCount;

    /** 更新帳號數量 */
    private int updatedCount;

    /** 跳過帳號數量（無變更） */
    private int skippedCount;

    /** 失敗帳號數量 */
    private int failedCount;

    /** 各環境同步詳細結果 */
    private List<EnvironmentSyncResult> environmentResults;

    /** 錯誤訊息（若 success = false） */
    private String errorMessage;

    // ----------------------------------------------------------------
    // 內部類別
    // ----------------------------------------------------------------

    /**
     * 單一環境的同步結果
     */
    @Data
    @Builder
    public static class EnvironmentSyncResult {

        /** 環境名稱 */
        private String environmentName;

        /** 是否成功 */
        private boolean success;

        /** 讀取到的帳號數量 */
        private int fetchedCount;

        /** 新增數量 */
        private int createdCount;

        /** 更新數量 */
        private int updatedCount;

        /** 跳過數量 */
        private int skippedCount;

        /** 失敗數量 */
        private int failedCount;

        /** 錯誤訊息 */
        private String errorMessage;
    }
}
