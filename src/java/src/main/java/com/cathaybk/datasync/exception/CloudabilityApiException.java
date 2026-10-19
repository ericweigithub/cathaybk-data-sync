package com.cathaybk.datasync.exception;

/**
 * Cloudability API 呼叫例外
 * 攜帶 HTTP 狀態碼，供呼叫端判斷處理方式
 */
public class CloudabilityApiException extends RuntimeException {

    private final int httpStatus;

    public CloudabilityApiException(String message, int httpStatus) {
        super(message);
        this.httpStatus = httpStatus;
    }

    public CloudabilityApiException(String message, int httpStatus, Throwable cause) {
        super(message, cause);
        this.httpStatus = httpStatus;
    }

    /**
     * @return HTTP 狀態碼（0 表示非 HTTP 錯誤）
     */
    public int getHttpStatus() {
        return httpStatus;
    }
}
