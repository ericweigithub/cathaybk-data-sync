"""
Cloudability API v3 HTTP Client

每個環境（子公司或 FCoE）持有一個獨立 CloudabilityClient 實例，
以對應不同的 API Key。

認證：HTTP Basic Auth — BASE64(api_key:)
重試：針對 429 / 5xx 採用 Exponential Backoff
"""

from __future__ import annotations

import base64
import logging
import time
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import CloudabilityConfig, EnvironmentConfig
from .models import (
    VendorAccount,
    VendorAccountListResponse,
    VendorAccountRequest,
    VendorAccountResponse,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 例外定義
# ---------------------------------------------------------------------------


class CloudabilityApiException(Exception):
    """Cloudability API 呼叫失敗時拋出"""

    def __init__(self, message: str, http_status: int = 0) -> None:
        super().__init__(message)
        self.http_status = http_status


# ---------------------------------------------------------------------------
# HTTP Client
# ---------------------------------------------------------------------------

_ACCOUNTS_PATH = "/vendors/{vendor}/accounts"
_ACCOUNT_PATH = "/vendors/{vendor}/accounts/{account_id}"


class CloudabilityClient:
    """
    Cloudability API v3 客戶端

    封裝對 Cloudability REST API 的所有 HTTP 操作。
    每個環境各自持有一個實例，以對應不同的 API Key。
    """

    def __init__(
        self,
        properties: CloudabilityConfig,
        env_config: EnvironmentConfig,
    ) -> None:
        self._env_name = env_config.name
        self._base_url = properties.base_url.rstrip("/")
        self._http_cfg = properties.http

        # 產生 Basic Auth Header：BASE64(api_key:)
        credentials = f"{env_config.api_key}:"
        encoded = base64.b64encode(credentials.encode("utf-8")).decode("ascii")
        self._auth_header = f"Basic {encoded}"

        # 建立 requests.Session（設定連線逾時，重試由 _execute_with_retry 自行處理）
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": self._auth_header,
                "Content-Type": "application/json",
            }
        )
        adapter = HTTPAdapter(max_retries=Retry(total=0))
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

        self._timeout = (
            properties.http.connect_timeout_seconds,
            properties.http.read_timeout_seconds,
        )

    # ------------------------------------------------------------------
    # Public API Methods
    # ------------------------------------------------------------------

    def list_accounts(self, vendor: str) -> list[VendorAccount]:
        """
        取得指定 Vendor 的所有帳號清單

        Args:
            vendor: "AWS" 或 "GCP"

        Returns:
            帳號清單（若環境無該 Vendor 帳號則回傳空 list）
        """
        logger.debug("[%s] 開始讀取 %s 帳號清單", self._env_name, vendor)

        url = self._build_url(_ACCOUNTS_PATH.format(vendor=vendor))
        response = self._execute_with_retry(
            lambda: self._session.get(url, params={"viewId": "0"}, timeout=self._timeout)
        )
        self._raise_for_status(response)

        data = VendorAccountListResponse.model_validate(response.json())
        accounts = data.result

        logger.info("[%s] 讀取 %s 帳號清單完成，共 %d 筆", self._env_name, vendor, len(accounts))
        return accounts

    def get_account(self, vendor: str, vendor_account_id: str) -> VendorAccount | None:
        """
        取得指定 Vendor Account（用於確認 FCoE 環境是否已存在）

        Returns:
            帳號物件；若不存在（404）則回傳 None
        """
        logger.debug("[%s] 查詢 %s 帳號 %s", self._env_name, vendor, vendor_account_id)

        url = self._build_url(_ACCOUNT_PATH.format(vendor=vendor, account_id=vendor_account_id))
        try:
            response = self._session.get(url, timeout=self._timeout)
        except requests.RequestException as exc:
            raise CloudabilityApiException(str(exc)) from exc

        if response.status_code == 404:
            return None
        self._raise_for_status(response)

        data = VendorAccountResponse.model_validate(response.json())
        return data.result

    def create_account(self, vendor: str, request: VendorAccountRequest) -> VendorAccount:
        """
        在 FCoE 環境新增 Vendor Account（POST）

        Returns:
            新增後的帳號物件

        Raises:
            CloudabilityApiException: 400 / 401 / 409 等非預期錯誤
        """
        logger.info("[%s] 新增 %s 帳號 %s", self._env_name, vendor, request.vendor_account_id)

        url = self._build_url(_ACCOUNTS_PATH.format(vendor=vendor))
        response = self._execute_with_retry(
            lambda: self._session.post(url, json=request.to_api_dict(), timeout=self._timeout)
        )
        self._raise_for_status(response)

        data = VendorAccountResponse.model_validate(response.json())
        if data.result is None:
            raise CloudabilityApiException(
                f"[{self._env_name}] POST 回應為空", http_status=0
            )

        logger.info(
            "[%s] 新增 %s 帳號 %s 成功",
            self._env_name,
            vendor,
            data.result.vendor_account_id,
        )
        return data.result

    def update_account(
        self, vendor: str, vendor_account_id: str, request: VendorAccountRequest
    ) -> VendorAccount:
        """
        在 FCoE 環境更新既有 Vendor Account（PUT）

        Returns:
            更新後的帳號物件

        Raises:
            CloudabilityApiException: 400 / 401 / 404 等錯誤
        """
        logger.info("[%s] 更新 %s 帳號 %s", self._env_name, vendor, vendor_account_id)

        url = self._build_url(_ACCOUNT_PATH.format(vendor=vendor, account_id=vendor_account_id))
        response = self._execute_with_retry(
            lambda: self._session.put(url, json=request.to_api_dict(), timeout=self._timeout)
        )
        self._raise_for_status(response)

        data = VendorAccountResponse.model_validate(response.json())
        if data.result is None:
            raise CloudabilityApiException(
                f"[{self._env_name}] PUT 回應為空", http_status=0
            )

        logger.info(
            "[%s] 更新 %s 帳號 %s 成功",
            self._env_name,
            vendor,
            vendor_account_id,
        )
        return data.result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_url(self, path: str) -> str:
        return f"{self._base_url}{path}"

    def _raise_for_status(self, response: requests.Response) -> None:
        """根據 HTTP 狀態碼拋出對應的 CloudabilityApiException"""
        status = response.status_code
        if status < 400:
            return

        if status == 400:
            raise CloudabilityApiException(
                f"[{self._env_name}] 請求格式錯誤（400）", http_status=400
            )
        if status == 401:
            raise CloudabilityApiException(
                f"[{self._env_name}] API Key 無效（401 Unauthorized）", http_status=401
            )
        if status == 404:
            raise CloudabilityApiException(
                f"[{self._env_name}] 資源不存在（404 Not Found）", http_status=404
            )
        if status == 409:
            raise CloudabilityApiException(
                f"[{self._env_name}] 帳號已存在（409 Conflict）", http_status=409
            )
        if status == 429:
            raise CloudabilityApiException(
                f"[{self._env_name}] 已達 Rate Limit（429）", http_status=429
            )
        if status >= 500:
            raise CloudabilityApiException(
                f"[{self._env_name}] Cloudability 服務異常（{status}）", http_status=status
            )

        raise CloudabilityApiException(
            f"[{self._env_name}] 未預期的 HTTP 狀態碼 {status}", http_status=status
        )

    def _execute_with_retry(
        self, call: Any  # Callable[[], requests.Response]
    ) -> requests.Response:
        """
        執行 API 呼叫，並依設定自動重試（Exponential Backoff）。
        針對 429 / 5xx 觸發重試，401 / 400 / 409 直接拋出。

        Args:
            call: 無參數 callable，回傳 requests.Response

        Returns:
            成功的 requests.Response
        """
        max_retry = self._http_cfg.max_retry
        interval_ms = self._http_cfg.retry_interval_seconds * 1000

        attempt = 0
        while True:
            try:
                response = call()
            except requests.RequestException as exc:
                raise CloudabilityApiException(str(exc)) from exc

            status = response.status_code

            # 不觸發重試的情況：成功 或 4xx（除 429）
            if status < 500 and status != 429:
                return response

            # 需要重試
            attempt += 1
            if attempt > max_retry:
                logger.error(
                    "[%s] 已達最大重試次數 %d，放棄本次呼叫（HTTP %d）",
                    self._env_name,
                    max_retry,
                    status,
                )
                return response  # 讓 _raise_for_status 處理

            # Exponential Backoff：interval × 2^(attempt-1)
            wait_ms = interval_ms * (2 ** (attempt - 1))
            logger.warning(
                "[%s] API 呼叫失敗（HTTP %d），第 %d/%d 次重試，等待 %d ms",
                self._env_name,
                status,
                attempt,
                max_retry,
                wait_ms,
            )
            time.sleep(wait_ms / 1000)


# ---------------------------------------------------------------------------
# Client Factory
# ---------------------------------------------------------------------------


class CloudabilityClientFactory:
    """建立各環境 CloudabilityClient 的工廠類別"""

    def __init__(self, config: CloudabilityConfig) -> None:
        self._config = config

    def create_fcoe_client(self) -> CloudabilityClient:
        return CloudabilityClient(self._config, self._config.fcoe)

    def create_subsidiary_clients(self) -> list[CloudabilityClient]:
        """建立所有已啟用子公司環境的 Client（enabled = false 的子公司將被跳過）"""
        return [
            CloudabilityClient(self._config, env)
            for env in self._config.subsidiaries
            if env.enabled
        ]
