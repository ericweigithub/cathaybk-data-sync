package com.cathaybk.datasync.client;

import com.cathaybk.datasync.config.CloudabilityProperties;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.util.List;
import java.util.stream.Collectors;

/**
 * CloudabilityClient 工廠
 * 負責為每個環境（子公司 × 7 + FCoE × 1）建立對應的 CloudabilityClient
 */
@Component
public class CloudabilityClientFactory {

    private final RestClient.Builder restClientBuilder;
    private final CloudabilityProperties properties;

    public CloudabilityClientFactory(
            RestClient.Builder restClientBuilder,
            CloudabilityProperties properties) {
        this.restClientBuilder = restClientBuilder;
        this.properties = properties;
    }

    /**
     * 建立所有子公司環境的 CloudabilityClient
     *
     * @return 子公司 Client 清單（順序與 application.yml 設定相同）
     */
    public List<CloudabilityClient> createSubsidiaryClients() {
        return properties.getSubsidiaries().stream()
                .map(env -> new CloudabilityClient(restClientBuilder.clone(), properties, env))
                .collect(Collectors.toList());
    }

    /**
     * 建立 FCoE 環境的 CloudabilityClient
     *
     * @return FCoE Client
     */
    public CloudabilityClient createFcoeClient() {
        return new CloudabilityClient(
                restClientBuilder.clone(),
                properties,
                properties.getFcoe());
    }
}
