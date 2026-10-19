package com.cathaybk.datasync.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * Cloudability API v3 回應包裝物件（單一物件版本）
 * 對應 GET /v3/vendors/{vendor}/accounts/{id}、POST、PUT 回應格式：
 * { "result": {...} }
 */
@Data
@NoArgsConstructor
@JsonIgnoreProperties(ignoreUnknown = true)
public class VendorAccountResponse {

    /** 單一帳號物件 */
    private VendorAccount result;
}
