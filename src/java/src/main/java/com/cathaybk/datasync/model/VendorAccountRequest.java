package com.cathaybk.datasync.model;

import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * POST / PUT Vendor Account 的 Request Body
 * 對應 API 規格書第 4.5 節
 */
@Data
@NoArgsConstructor
public class VendorAccountRequest {

    /** Vendor 帳號 ID（AWS Account ID 或 GCP Project ID） */
    private String vendorAccountId;

    /**
     * 授權類型
     * AWS：aws_role
     * GCP：gcp_service_account
     */
    private String type;

    // ----------------------------------------------------------------
    // AWS 欄位
    // ----------------------------------------------------------------

    /** IAM Role 名稱 */
    private String roleName;

    /** S3 Bucket 名稱 */
    private String bucketName;

    /** External ID */
    private String externalID;

    /** Cost and Usage Report 設定 */
    private Authorization.CostAndUsageReport costAndUsageReport;

    /** AWS Region */
    private String region;

    /** 是否啟用 Org Level Policy */
    private Boolean isOrgLevelPolicyEnabled;

    // ----------------------------------------------------------------
    // GCP 欄位
    // ----------------------------------------------------------------

    /** GCP Service Account Email */
    private String serviceAccountEmail;

    /** GCP Project ID */
    private String projectId;
}
