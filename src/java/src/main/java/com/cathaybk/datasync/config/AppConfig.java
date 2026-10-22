package com.cathaybk.datasync.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.web.client.RestClient;

/**
 * Spring 應用程式設定
 * - 啟用排程（@EnableScheduling）
 * - 建立共用 RestClient Bean
 */
@Configuration
@EnableScheduling
public class AppConfig {

    /**
     * 提供預設 RestClient.Builder Bean，供各 API Client 使用。
     * 各 API Client 在建立時會覆寫 baseUrl 與 Authorization Header。
     */
    @Bean
    public RestClient.Builder restClientBuilder(CloudabilityProperties properties) {
        return RestClient.builder()
                .requestInterceptor((request, body, execution) -> {
                    // 設定 Content-Type（POST/PUT 使用）
                    request.getHeaders().set("Content-Type", "application/json");
                    return execution.execute(request, body);
                });
    }
}
