package com.cathaybk.datasync.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * Vendor Account 授權設定
 * 同時支援 AWS（aws_role）與 GCP（gcp_service_account）授權類型
 */
@Data
@NoArgsConstructor
@JsonIgnoreProperties(ignoreUnknown = true)
public class Authorization {

    /**
     * 授權類型
     * AWS：aws_role
     * GCP：gcp_service_account
     */
    private String type;

    // ----------------------------------------------------------------
    // AWS 專屬欄位
    // ----------------------------------------------------------------

    /** IAM Role 名稱（AWS） */
    private String roleName;

    /** S3 Bucket 名稱（AWS CUR） */
    private String bucketName;

    /** External ID（AWS Role 信任政策用） */
    private String externalId;

    /** Cost and Usage Report 設定（AWS） */
    private CostAndUsageReport costAndUsageReport;

    /** AWS Region */
    private String region;

    /** 是否啟用 Org Level Policy（AWS） */
    private Boolean isOrgLevelPolicyEnabled;

    /** 是否啟用 Turbo Execution（AWS） */
    private Boolean turboExecutionEnabled;

    /** Application 類型（AWS） */
    private String applicationType;

    /** 額外 IAM 權限清單（AWS linked account） */
    private List<String> permissions;

    // ----------------------------------------------------------------
    // GCP 專屬欄位
    // ----------------------------------------------------------------

    /** GCP Service Account Email */
    private String serviceAccountEmail;

    /** GCP Project ID */
    private String projectId;

    // ----------------------------------------------------------------
    // 內部類別
    // ----------------------------------------------------------------

    /**
     * AWS Cost and Usage Report 設定
     */
    @Data
    @NoArgsConstructor
    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class CostAndUsageReport {

        /** Report 名稱 */
        private String name;

        /** S3 Prefix */
        private String prefix;
    }
}
