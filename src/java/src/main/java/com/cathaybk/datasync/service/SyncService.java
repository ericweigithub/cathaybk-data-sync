package com.cathaybk.datasync.service;

import com.cathaybk.datasync.client.CloudabilityClient;
import com.cathaybk.datasync.client.CloudabilityClientFactory;
import com.cathaybk.datasync.config.SyncProperties;
import com.cathaybk.datasync.exception.CloudabilityApiException;
import com.cathaybk.datasync.model.*;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.*;

/**
 * 雲端認證資料同步服務
 *
 * <p>
 * 實作規格書第五節的同步邏輯流程：
 * </p>
 * <ol>
 * <li>逐一呼叫 7 個子公司環境取得 AWS + GCP 帳號清單</li>
 * <li>呼叫 FCoE 環境取得現有帳號清單</li>
 * <li>比對差異（以 vendorAccountId + vendor 為唯一鍵）</li>
 * <li>子公司有、FCoE 無 → POST 新增</li>
 * <li>子公司有、FCoE 有 → 比對認證設定是否異動 → 有異動則 PUT 更新</li>
 * <li>記錄同步結果至 Log</li>
 * </ol>
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class SyncService {

    private final CloudabilityClientFactory clientFactory;
    private final SyncProperties syncProperties;

    // ----------------------------------------------------------------
    // Public Methods
    // ----------------------------------------------------------------

    /**
     * 執行完整同步作業
     *
     * @return 同步結果摘要
     */
    public SyncResult sync() {
        Instant startedAt = Instant.now();
        log.info("========== 同步作業開始 ==========");

        List<SyncResult.EnvironmentSyncResult> envResults = new ArrayList<>();
        int totalCreated = 0;
        int totalUpdated = 0;
        int totalSkipped = 0;
        int totalFailed = 0;
        boolean overallSuccess = true;

        try {
            // 步驟 1：取得 FCoE 現有帳號清單（作為比對基準）
            CloudabilityClient fcoeClient = clientFactory.createFcoeClient();
            Map<String, VendorAccount> fcoeAccountMap = buildFcoeAccountMap(fcoeClient);
            log.info("FCoE 現有帳號總數：{}", fcoeAccountMap.size());

            // 步驟 2：逐一處理子公司環境
            List<CloudabilityClient> subsidiaryClients = clientFactory.createSubsidiaryClients();

            for (CloudabilityClient subsidiaryClient : subsidiaryClients) {
                SyncResult.EnvironmentSyncResult envResult = syncSubsidiary(subsidiaryClient, fcoeClient,
                        fcoeAccountMap);

                envResults.add(envResult);
                totalCreated += envResult.getCreatedCount();
                totalUpdated += envResult.getUpdatedCount();
                totalSkipped += envResult.getSkippedCount();
                totalFailed += envResult.getFailedCount();

                if (!envResult.isSuccess()) {
                    overallSuccess = false;
                }
            }

        } catch (CloudabilityApiException e) {
            log.error("同步作業發生嚴重錯誤：{}", e.getMessage(), e);
            overallSuccess = false;
        }

        Instant finishedAt = Instant.now();
        log.info("========== 同步作業結束：新增 {} 筆、更新 {} 筆、跳過 {} 筆、失敗 {} 筆 ==========",
                totalCreated, totalUpdated, totalSkipped, totalFailed);

        return SyncResult.builder()
                .startedAt(startedAt)
                .finishedAt(finishedAt)
                .success(overallSuccess)
                .createdCount(totalCreated)
                .updatedCount(totalUpdated)
                .skippedCount(totalSkipped)
                .failedCount(totalFailed)
                .environmentResults(envResults)
                .build();
    }

    // ----------------------------------------------------------------
    // Private Methods
    // ----------------------------------------------------------------

    /**
     * 建立 FCoE 帳號 Map，以 "{vendor}:{vendorAccountId}" 為 key
     */
    private Map<String, VendorAccount> buildFcoeAccountMap(CloudabilityClient fcoeClient) {
        Map<String, VendorAccount> map = new HashMap<>();

        for (String vendor : syncProperties.getVendors()) {
            String vendorPath = resolveVendorPath(vendor);
            try {
                List<VendorAccount> accounts = fcoeClient.listAccounts(vendorPath);
                for (VendorAccount account : accounts) {
                    String key = buildKey(vendorPath, account.getVendorAccountId());
                    map.put(key, account);
                }
            } catch (CloudabilityApiException e) {
                if (e.getHttpStatus() == 401) {
                    // FCoE API Key 無效時，整體作業無法繼續
                    throw new CloudabilityApiException(
                            "FCoE API Key 無效，終止同步作業：" + e.getMessage(), 401, e);
                }
                log.error("讀取 FCoE {} 帳號清單失敗：{}", vendorPath, e.getMessage());
            }
        }

        return map;
    }

    /**
     * 同步單一子公司環境
     *
     * @param subsidiaryClient 子公司 API Client
     * @param fcoeClient       FCoE API Client（用於 POST / PUT）
     * @param fcoeAccountMap   FCoE 現有帳號 Map（讀取時已載入，同步過程中持續更新）
     * @return 此環境的同步結果
     */
    private SyncResult.EnvironmentSyncResult syncSubsidiary(
            CloudabilityClient subsidiaryClient,
            CloudabilityClient fcoeClient,
            Map<String, VendorAccount> fcoeAccountMap) {

        // 取得環境名稱（透過 toString 方式取，實際上使用 log 輸出）
        int fetched = 0;
        int created = 0;
        int updated = 0;
        int skipped = 0;
        int failed = 0;
        String errorMsg = null;

        // 取得環境名稱（從 client 無法直接取，故以 fcoeAccountMap 大小做為識別即可；
        // 實際環境名稱由 CloudabilityClient 的 log 輸出）

        try {
            for (String vendor : syncProperties.getVendors()) {
                String vendorPath = resolveVendorPath(vendor);

                List<VendorAccount> sourceAccounts;
                try {
                    sourceAccounts = subsidiaryClient.listAccounts(vendorPath);
                } catch (CloudabilityApiException e) {
                    if (e.getHttpStatus() == 401) {
                        // 子公司 API Key 無效，跳過此環境
                        log.error("子公司 {} 環境 API Key 無效，跳過同步", vendorPath);
                        errorMsg = e.getMessage();
                        return SyncResult.EnvironmentSyncResult.builder()
                                .success(false)
                                .fetchedCount(0)
                                .createdCount(0)
                                .updatedCount(0)
                                .skippedCount(0)
                                .failedCount(0)
                                .errorMessage(errorMsg)
                                .build();
                    }
                    log.error("讀取子公司 {} 帳號清單失敗：{}", vendorPath, e.getMessage());
                    continue;
                }

                fetched += sourceAccounts.size();

                for (VendorAccount source : sourceAccounts) {
                    String key = buildKey(vendorPath, source.getVendorAccountId());

                    try {
                        if (fcoeAccountMap.containsKey(key)) {
                            // FCoE 已存在 → 比對是否需要更新
                            VendorAccount existing = fcoeAccountMap.get(key);
                            if (isCredentialChanged(source, existing)) {
                                VendorAccountRequest request = buildRequest(source);
                                VendorAccount updatedAccount = fcoeClient.updateAccount(
                                        vendorPath, source.getVendorAccountId(), request);
                                fcoeAccountMap.put(key, updatedAccount);
                                updated++;
                                log.info("帳號 {} ({}) 已更新至 FCoE",
                                        source.getVendorAccountId(), vendorPath);
                            } else {
                                skipped++;
                                log.debug("帳號 {} ({}) 無變更，跳過",
                                        source.getVendorAccountId(), vendorPath);
                            }
                        } else {
                            // FCoE 不存在 → 新增
                            VendorAccountRequest request = buildRequest(source);
                            VendorAccount createdAccount;
                            try {
                                createdAccount = fcoeClient.createAccount(vendorPath, request);
                            } catch (CloudabilityApiException ex) {
                                if (ex.getHttpStatus() == 409) {
                                    // 409 Conflict：帳號已存在（可能 map 未包含），改以 PUT 更新
                                    log.warn("帳號 {} ({}) 已存在（409），改以 PUT 更新",
                                            source.getVendorAccountId(), vendorPath);
                                    createdAccount = fcoeClient.updateAccount(
                                            vendorPath, source.getVendorAccountId(), request);
                                    updated++;
                                    fcoeAccountMap.put(key, createdAccount);
                                    continue;
                                }
                                throw ex;
                            }
                            fcoeAccountMap.put(key, createdAccount);
                            created++;
                            log.info("帳號 {} ({}) 已新增至 FCoE",
                                    source.getVendorAccountId(), vendorPath);
                        }
                    } catch (CloudabilityApiException e) {
                        int status = e.getHttpStatus();
                        if (status == 404) {
                            // 404 在 PUT 情境代表帳號不存在，改為 POST
                            log.warn("帳號 {} ({}) 在 FCoE 不存在（404），改以 POST 新增",
                                    source.getVendorAccountId(), vendorPath);
                            try {
                                VendorAccountRequest request = buildRequest(source);
                                VendorAccount createdAccount = fcoeClient.createAccount(vendorPath, request);
                                fcoeAccountMap.put(key, createdAccount);
                                created++;
                            } catch (CloudabilityApiException inner) {
                                log.error("帳號 {} ({}) 新增失敗：{}",
                                        source.getVendorAccountId(), vendorPath, inner.getMessage());
                                failed++;
                            }
                        } else {
                            log.error("帳號 {} ({}) 同步失敗（HTTP {}）：{}",
                                    source.getVendorAccountId(), vendorPath,
                                    status, e.getMessage());
                            failed++;
                        }
                    }
                }
            }

        } catch (Exception e) {
            log.error("子公司環境同步發生未預期錯誤：{}", e.getMessage(), e);
            errorMsg = e.getMessage();
        }

        return SyncResult.EnvironmentSyncResult.builder()
                .success(errorMsg == null)
                .fetchedCount(fetched)
                .createdCount(created)
                .updatedCount(updated)
                .skippedCount(skipped)
                .failedCount(failed)
                .errorMessage(errorMsg)
                .build();
    }

    /**
     * 比對來源帳號與 FCoE 現有帳號的認證設定是否有異動
     * 以 authorization 欄位的關鍵值做比對
     */
    private boolean isCredentialChanged(VendorAccount source, VendorAccount existing) {
        Authorization src = source.getAuthorization();
        Authorization dst = existing.getAuthorization();

        if (src == null && dst == null) {
            return false;
        }
        if (src == null || dst == null) {
            return true;
        }

        // 比對授權類型
        if (!Objects.equals(src.getType(), dst.getType())) {
            return true;
        }

        // AWS 欄位比對
        if (!Objects.equals(src.getRoleName(), dst.getRoleName()))
            return true;
        if (!Objects.equals(src.getBucketName(), dst.getBucketName()))
            return true;
        if (!Objects.equals(src.getExternalId(), dst.getExternalId()))
            return true;
        if (!Objects.equals(src.getRegion(), dst.getRegion()))
            return true;
        if (!Objects.equals(src.getIsOrgLevelPolicyEnabled(), dst.getIsOrgLevelPolicyEnabled()))
            return true;

        // GCP 欄位比對
        if (!Objects.equals(src.getServiceAccountEmail(), dst.getServiceAccountEmail()))
            return true;
        if (!Objects.equals(src.getProjectId(), dst.getProjectId()))
            return true;

        // CUR 設定比對
        Authorization.CostAndUsageReport srcCur = src.getCostAndUsageReport();
        Authorization.CostAndUsageReport dstCur = dst.getCostAndUsageReport();
        if (srcCur != null && dstCur != null) {
            if (!Objects.equals(srcCur.getName(), dstCur.getName()))
                return true;
            if (!Objects.equals(srcCur.getPrefix(), dstCur.getPrefix()))
                return true;
        } else if (srcCur != null || dstCur != null) {
            return true;
        }

        return false;
    }

    /**
     * 從 VendorAccount 建立 POST/PUT Request Body
     */
    private VendorAccountRequest buildRequest(VendorAccount source) {
        VendorAccountRequest request = new VendorAccountRequest();
        request.setVendorAccountId(source.getVendorAccountId());

        Authorization auth = source.getAuthorization();
        if (auth != null) {
            request.setType(auth.getType());
            request.setRoleName(auth.getRoleName());
            request.setBucketName(auth.getBucketName());
            request.setExternalID(auth.getExternalId());
            request.setCostAndUsageReport(auth.getCostAndUsageReport());
            request.setRegion(auth.getRegion());
            request.setIsOrgLevelPolicyEnabled(auth.getIsOrgLevelPolicyEnabled());
            request.setServiceAccountEmail(auth.getServiceAccountEmail());
            request.setProjectId(auth.getProjectId());
        }

        return request;
    }

    /**
     * 將設定檔中的 vendor 名稱（amazon/google）轉換為 API 路徑中使用的 Vendor Key
     *
     * @param vendor 設定值（amazon 或 google）
     * @return API 路徑 vendor 段（AWS 或 GCP）
     */
    private String resolveVendorPath(String vendor) {
        return switch (vendor.toLowerCase()) {
            case "amazon" -> "AWS";
            case "google" -> "GCP";
            default -> vendor.toUpperCase();
        };
    }

    /**
     * 建立帳號唯一鍵，格式為 "{vendor}:{vendorAccountId}"
     */
    private String buildKey(String vendor, String vendorAccountId) {
        return vendor + ":" + vendorAccountId;
    }
}
