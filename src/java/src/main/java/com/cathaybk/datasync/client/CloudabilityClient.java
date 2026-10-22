package com.cathaybk.datasync.client;

import com.cathaybk.datasync.config.CloudabilityProperties;
import com.cathaybk.datasync.exception.CloudabilityApiException;
import com.cathaybk.datasync.model.*;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.web.client.RestClient;

import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.util.Collections;
import java.util.List;
import java.util.Optional;

/**
 * Cloudability API v3 客戶端
 * 封裝對 Cloudability REST API 的所有 HTTP 操作
 *
 * <p>每個環境（子公司或 FCoE）各自持有一個 CloudabilityClient 實例，
 * 以對應不同的 API Key。</p>
 */
@Slf4j
public class CloudabilityClient {

    /** Vendor 路徑常數 */
    private static final String VENDOR_AWS = "AWS";
    private static final String VENDOR_GCP = "GCP";

    /** 帳號清單端點 */
    private static final String ACCOUNTS_PATH = "/vendors/{vendor}/accounts";

    /** 單一帳號端點 */
    private static final String ACCOUNT_PATH = "/vendors/{vendor}/accounts/{accountId}";

    private final RestClient restClient;
    private final String environmentName;
    private final CloudabilityProperties.HttpConfig httpConfig;

    /**
     * 建立 CloudabilityClient
     *
     * @param builder         Spring RestClient.Builder（由 AppConfig 提供）
     * @param properties      Cloudability 全域設定
     * @param envConfig       此客戶端對應的環境設定
     */
    public CloudabilityClient(
            RestClient.Builder builder,
            CloudabilityProperties properties,
            CloudabilityProperties.EnvironmentConfig envConfig) {

        this.environmentName = envConfig.getName();
        this.httpConfig = properties.getHttp();

        // 產生 Basic Auth Header：BASE64(api_key:)
        String credentials = envConfig.getApiKey() + ":";
        String encoded = Base64.getEncoder().encodeToString(
                credentials.getBytes(StandardCharsets.UTF_8));

        this.restClient = builder
                .baseUrl(properties.getBaseUrl())
                .defaultHeader(HttpHeaders.AUTHORIZATION, "Basic " + encoded)
                .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
                .build();
    }

    // ----------------------------------------------------------------
    // Public API Methods
    // ----------------------------------------------------------------

    /**
     * 取得指定 Vendor 的所有帳號清單
     *
     * @param vendor "AWS" 或 "GCP"
     * @return 帳號清單（若環境無該 Vendor 帳號則回傳空 List）
     */
    public List<VendorAccount> listAccounts(String vendor) {
        log.debug("[{}] 開始讀取 {} 帳號清單", environmentName, vendor);

        VendorAccountListResponse response = executeWithRetry(() ->
                restClient.get()
                        .uri(uriBuilder -> uriBuilder
                                .path(ACCOUNTS_PATH)
                                .queryParam("viewId", "0")
                                .build(vendor))
                        .retrieve()
                        .onStatus(status -> status.value() == 401,
                                (req, res) -> {
                                    throw new CloudabilityApiException(
                                            "[%s] API Key 無效（401 Unauthorized）".formatted(environmentName),
                                            401);
                                })
                        .onStatus(status -> status.value() == 429,
                                (req, res) -> {
                                    throw new CloudabilityApiException(
                                            "[%s] 已達 Rate Limit（429）".formatted(environmentName),
                                            429);
                                })
                        .onStatus(HttpStatus.Series.SERVER_ERROR::equals,
                                (req, res) -> {
                                    throw new CloudabilityApiException(
                                            "[%s] Cloudability 服務異常（5xx）".formatted(environmentName),
                                            res.getStatusCode().value());
                                })
                        .body(VendorAccountListResponse.class)
        );

        List<VendorAccount> accounts = (response != null && response.getResult() != null)
                ? response.getResult()
                : Collections.emptyList();

        log.info("[{}] 讀取 {} 帳號清單完成，共 {} 筆", environmentName, vendor, accounts.size());
        if (log.isDebugEnabled()) {
            accounts.forEach(account ->
                    log.debug("[{}] {} 帳號：{}", environmentName, vendor, account.getVendorAccountId()));
        }
        return accounts;
    }

    /**
     * 取得 FCoE 環境中指定 Vendor Account（用於確認是否存在）
     *
     * @param vendor          "AWS" 或 "GCP"
     * @param vendorAccountId 要查詢的帳號 ID
     * @return 帳號（若不存在則回傳 empty）
     */
    public Optional<VendorAccount> getAccount(String vendor, String vendorAccountId) {
        log.debug("[{}] 查詢 {} 帳號 {}", environmentName, vendor, vendorAccountId);

        try {
            VendorAccountResponse response = restClient.get()
                    .uri(ACCOUNT_PATH, vendor, vendorAccountId)
                    .retrieve()
                    .onStatus(status -> status.value() == 404,
                            (req, res) -> {
                                // 404 表示帳號不存在，非真正錯誤
                                throw new CloudabilityApiException("NOT_FOUND", 404);
                            })
                    .onStatus(status -> status.value() == 401,
                            (req, res) -> {
                                throw new CloudabilityApiException(
                                        "[%s] API Key 無效（401）".formatted(environmentName), 401);
                            })
                    .body(VendorAccountResponse.class);

            return Optional.ofNullable(response).map(VendorAccountResponse::getResult);

        } catch (CloudabilityApiException e) {
            if (e.getHttpStatus() == 404) {
                return Optional.empty();
            }
            throw e;
        }
    }

    /**
     * 在 FCoE 環境新增 Vendor Account（POST）
     *
     * @param vendor  "AWS" 或 "GCP"
     * @param request 新增請求 Body
     * @return 新增後的帳號物件
     */
    public VendorAccount createAccount(String vendor, VendorAccountRequest request) {
        log.info("[{}] 新增 {} 帳號 {}", environmentName, vendor, request.getVendorAccountId());

        VendorAccountResponse response = executeWithRetry(() ->
                restClient.post()
                        .uri(ACCOUNTS_PATH, vendor)
                        .body(request)
                        .retrieve()
                        .onStatus(status -> status.value() == 400,
                                (req, res) -> {
                                    throw new CloudabilityApiException(
                                            "[%s] 請求格式錯誤（400）：%s".formatted(
                                                    environmentName, request.getVendorAccountId()),
                                            400);
                                })
                        .onStatus(status -> status.value() == 401,
                                (req, res) -> {
                                    throw new CloudabilityApiException(
                                            "[%s] API Key 無效（401）".formatted(environmentName), 401);
                                })
                        .onStatus(status -> status.value() == 409,
                                (req, res) -> {
                                    // 帳號已存在，呼叫端應改以 PUT 更新
                                    throw new CloudabilityApiException(
                                            "[%s] 帳號已存在（409）：%s".formatted(
                                                    environmentName, request.getVendorAccountId()),
                                            409);
                                })
                        .onStatus(HttpStatus.Series.SERVER_ERROR::equals,
                                (req, res) -> {
                                    throw new CloudabilityApiException(
                                            "[%s] Cloudability 服務異常（5xx）".formatted(environmentName),
                                            res.getStatusCode().value());
                                })
                        .body(VendorAccountResponse.class)
        );

        VendorAccount created = Optional.ofNullable(response)
                .map(VendorAccountResponse::getResult)
                .orElseThrow(() -> new CloudabilityApiException(
                        "[%s] POST 回應為空".formatted(environmentName), 0));

        log.info("[{}] 新增 {} 帳號 {} 成功", environmentName, vendor, created.getVendorAccountId());
        return created;
    }

    /**
     * 在 FCoE 環境更新既有 Vendor Account（PUT）
     *
     * @param vendor          "AWS" 或 "GCP"
     * @param vendorAccountId 要更新的帳號 ID
     * @param request         更新請求 Body
     * @return 更新後的帳號物件
     */
    public VendorAccount updateAccount(String vendor, String vendorAccountId, VendorAccountRequest request) {
        log.info("[{}] 更新 {} 帳號 {}", environmentName, vendor, vendorAccountId);

        VendorAccountResponse response = executeWithRetry(() ->
                restClient.put()
                        .uri(ACCOUNT_PATH, vendor, vendorAccountId)
                        .body(request)
                        .retrieve()
                        .onStatus(status -> status.value() == 400,
                                (req, res) -> {
                                    throw new CloudabilityApiException(
                                            "[%s] 請求格式錯誤（400）：%s".formatted(
                                                    environmentName, vendorAccountId),
                                            400);
                                })
                        .onStatus(status -> status.value() == 401,
                                (req, res) -> {
                                    throw new CloudabilityApiException(
                                            "[%s] API Key 無效（401）".formatted(environmentName), 401);
                                })
                        .onStatus(status -> status.value() == 404,
                                (req, res) -> {
                                    // 帳號不存在，呼叫端應改以 POST 新增
                                    throw new CloudabilityApiException(
                                            "[%s] 帳號不存在（404）：%s".formatted(
                                                    environmentName, vendorAccountId),
                                            404);
                                })
                        .onStatus(HttpStatus.Series.SERVER_ERROR::equals,
                                (req, res) -> {
                                    throw new CloudabilityApiException(
                                            "[%s] Cloudability 服務異常（5xx）".formatted(environmentName),
                                            res.getStatusCode().value());
                                })
                        .body(VendorAccountResponse.class)
        );

        VendorAccount updated = Optional.ofNullable(response)
                .map(VendorAccountResponse::getResult)
                .orElseThrow(() -> new CloudabilityApiException(
                        "[%s] PUT 回應為空".formatted(environmentName), 0));

        log.info("[{}] 更新 {} 帳號 {} 成功", environmentName, vendor, vendorAccountId);
        return updated;
    }

    // ----------------------------------------------------------------
    // Private helpers
    // ----------------------------------------------------------------

    /**
     * 執行 API 呼叫，並依設定自動重試（Exponential Backoff）
     * 針對 429 / 5xx 觸發重試，401 / 400 直接拋出
     *
     * @param supplier 要執行的 API 呼叫
     * @param <T>      回應型別
     * @return API 回應物件
     */
    private <T> T executeWithRetry(ApiCall<T> supplier) {
        int attempt = 0;
        int maxRetry = httpConfig.getMaxRetry();
        long intervalMs = httpConfig.getRetryIntervalSeconds() * 1000L;

        while (true) {
            try {
                return supplier.call();
            } catch (CloudabilityApiException e) {
                int status = e.getHttpStatus();

                // 401 / 400 / 409 不重試，直接往上拋
                if (status == 401 || status == 400 || status == 409) {
                    throw e;
                }

                attempt++;
                if (attempt > maxRetry) {
                    log.error("[{}] 已達最大重試次數 {}，放棄本次呼叫：{}",
                            environmentName, maxRetry, e.getMessage());
                    throw e;
                }

                // Exponential Backoff：間隔 × 2^(attempt-1)
                long waitMs = intervalMs * (1L << (attempt - 1));
                log.warn("[{}] API 呼叫失敗（HTTP {}），第 {}/{} 次重試，等待 {} ms",
                        environmentName, status, attempt, maxRetry, waitMs);

                try {
                    Thread.sleep(waitMs);
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                    throw new CloudabilityApiException("重試被中斷", 0);
                }
            }
        }
    }

    /** 函式型介面，用於 executeWithRetry */
    @FunctionalInterface
    private interface ApiCall<T> {
        T call();
    }
}
