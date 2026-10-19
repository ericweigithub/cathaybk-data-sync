package com.cathaybk.datasync.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;

/**
 * Vendor Account 驗證狀態
 */
@Data
@NoArgsConstructor
@JsonIgnoreProperties(ignoreUnknown = true)
public class Verification {

    /** 驗證狀態（verified / unverified / error） */
    private String state;

    /** 上次驗證時間 */
    private Instant lastVerificationAttemptedAt;
}
