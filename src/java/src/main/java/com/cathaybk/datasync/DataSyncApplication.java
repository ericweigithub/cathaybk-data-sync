package com.cathaybk.datasync;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * 國泰 Apptio 雲端認證資料同步服務
 *
 * <p>本應用程式負責將 7 個子公司 Cloudability 環境中的
 * AWS / GCP Vendor Account 認證資料，單向同步至 FCoE 環境。</p>
 *
 * <p>支援排程自動執行（每日凌晨 02:00）與 REST API 手動觸發兩種方式。</p>
 */
@SpringBootApplication
public class DataSyncApplication {

    public static void main(String[] args) {
        SpringApplication.run(DataSyncApplication.class, args);
    }
}
