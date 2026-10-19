package com.cathaybk.datasync.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;

/**
 * Cloudability Vendor Account 資料模型
 * 對應 GET /v3/vendors/{vendor}/accounts 回應中的單一帳號物件
 */
@Data
@NoArgsConstructor
@JsonIgnoreProperties(ignoreUnknown = true)
public class VendorAccount {

    /** 帳號 ID（同 vendorAccountId） */
    private String id;

    /** 帳號名稱 */
    private String vendorAccountName;

    /** Vendor 帳號 ID（AWS Account ID 或 GCP Project ID） */
    private String vendorAccountId;

    /**
     * Vendor 類型
     * aws → Amazon Web Services
     * gcp → Google Cloud Platform
     */
    private String vendorKey;

    /** 帳號驗證狀態 */
    private Verification verification;

    /** 帳號授權設定 */
    private Authorization authorization;

    /** 建立時間 */
    private Instant createdAt;

    /** 父帳號 ID（linked account 才有） */
    private String parentAccountId;

    /** Consumer Org ID */
    private String consumerOrgId;

    /** BYOD Vendor 狀態 */
    private String byodVendor;
}
