package com.cathaybk.datasync.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * Cloudability API 設定屬性
 * 對應 application.yml 中的 cloudability.* 設定
 */
@Data
@Component
@ConfigurationProperties(prefix = "cloudability")
public class CloudabilityProperties {

    /** Cloudability API Base URL */
    private String baseUrl = "https://api.cloudability.com/v3";

    /** 7 個子公司環境設定 */
    private List<EnvironmentConfig> subsidiaries;

    /** FCoE 環境設定 */
    private EnvironmentConfig fcoe;

    /** HTTP Client 設定 */
    private HttpConfig http = new HttpConfig();

    // ----------------------------------------------------------------
    // 內部類別
    // ----------------------------------------------------------------

    /**
     * 單一 Cloudability 環境設定（子公司或 FCoE）
     */
    @Data
    public static class EnvironmentConfig {

        /** 環境名稱（顯示用） */
        private String name;

        /** Cloudability API Key（請由環境變數注入，切勿明文） */
        private String apiKey;

        /** 是否啟用同步（false 時跳過此子公司，預設 true） */
        private boolean enabled = true;
    }

    /**
     * HTTP Client 連線設定
     */
    @Data
    public static class HttpConfig {

        /** 連線逾時（秒） */
        private int connectTimeoutSeconds = 30;

        /** 讀取逾時（秒） */
        private int readTimeoutSeconds = 60;

        /** 最大重試次數 */
        private int maxRetry = 3;

        /** 重試間隔（秒） */
        private int retryIntervalSeconds = 60;
    }
}
