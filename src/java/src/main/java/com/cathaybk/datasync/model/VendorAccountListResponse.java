package com.cathaybk.datasync.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * Cloudability API v3 回應包裝物件（List 版本）
 * 對應 GET /v3/vendors/{vendor}/accounts 回應格式：
 * { "result": [...] }
 */
@Data
@NoArgsConstructor
@JsonIgnoreProperties(ignoreUnknown = true)
public class VendorAccountListResponse {

    /** 帳號清單 */
    private List<VendorAccount> result;
}
