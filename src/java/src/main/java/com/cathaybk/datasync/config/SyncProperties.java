package com.cathaybk.datasync.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * 同步作業設定屬性
 * 對應 application.yml 中的 sync.* 設定
 */
@Data
@Component
@ConfigurationProperties(prefix = "sync")
public class SyncProperties {

    /**
     * 要同步的 Vendor 清單
     * 允許值：amazon（AWS）、google（GCP）
     */
    private List<String> vendors = List.of("amazon", "google");

    /**
     * 是否啟用刪除同步
     * 預設 false，避免誤刪 FCoE 帳號
     */
    private boolean enableDelete = false;

    /**
     * 排程 Cron 表達式（預設每日凌晨 02:00）
     */
    private String cron = "0 0 2 * * ?";

    /**
     * 是否啟用排程自動執行
     */
    private boolean scheduleEnabled = true;
}
