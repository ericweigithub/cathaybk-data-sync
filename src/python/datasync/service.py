"""
雲端認證資料同步服務

實作規格書第五節的同步邏輯流程：
  1. 逐一呼叫 7 個子公司環境取得 AWS + GCP 帳號清單
  2. 呼叫 FCoE 環境取得現有帳號清單
  3. 比對差異（以 vendor_account_id + vendor 為唯一鍵）
     - 子公司有、FCoE 無 → POST 新增
     - 子公司有、FCoE 有 → 比對 credentials 是否異動 → 有異動則 PUT 更新
  4. 記錄同步結果至 Log
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from .client import CloudabilityApiException, CloudabilityClient, CloudabilityClientFactory
from .config import SyncConfig
from .models import (
    Authorization,
    EnvironmentSyncResult,
    SyncResult,
    VendorAccount,
    VendorAccountRequest,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Vendor 名稱對應（設定值 → API 路徑段）
# ---------------------------------------------------------------------------

_VENDOR_PATH_MAP: dict[str, str] = {
    "amazon": "AWS",
    "google": "GCP",
}


def _resolve_vendor_path(vendor: str) -> str:
    """將設定檔的 vendor 名稱（amazon/google）轉換為 API 路徑中使用的 Vendor Key"""
    return _VENDOR_PATH_MAP.get(vendor.lower(), vendor.upper())


def _build_key(vendor: str, vendor_account_id: str) -> str:
    """建立帳號唯一鍵，格式為 "{vendor}:{vendorAccountId}" """
    return f"{vendor}:{vendor_account_id}"


# ---------------------------------------------------------------------------
# 同步服務
# ---------------------------------------------------------------------------


class SyncService:
    """
    雲端認證資料同步服務

    依規格書流程執行完整的子公司 → FCoE 帳號同步作業。
    """

    def __init__(
        self,
        client_factory: CloudabilityClientFactory,
        sync_config: SyncConfig,
    ) -> None:
        self._factory = client_factory
        self._sync_config = sync_config

    # ------------------------------------------------------------------
    # Public Methods
    # ------------------------------------------------------------------

    def sync(self) -> SyncResult:
        """
        執行完整同步作業。

        Returns:
            SyncResult：本次執行的結果摘要
        """
        started_at = datetime.now(tz=UTC)
        logger.info("========== 同步作業開始 ==========")

        env_results: list[EnvironmentSyncResult] = []
        total_created = total_updated = total_skipped = total_failed = 0
        overall_success = True
        error_message: str | None = None

        try:
            # 步驟 1：取得 FCoE 現有帳號清單（作為比對基準）
            fcoe_client = self._factory.create_fcoe_client()
            fcoe_map = self._build_fcoe_account_map(fcoe_client)
            logger.info("FCoE 現有帳號總數：%d", len(fcoe_map))

            # 步驟 2：逐一處理子公司環境
            subsidiary_clients = self._factory.create_subsidiary_clients()
            for sub_client in subsidiary_clients:
                env_result = self._sync_subsidiary(sub_client, fcoe_client, fcoe_map)
                env_results.append(env_result)
                total_created += env_result.created_count
                total_updated += env_result.updated_count
                total_skipped += env_result.skipped_count
                total_failed += env_result.failed_count
                if not env_result.success:
                    overall_success = False

        except CloudabilityApiException as exc:
            logger.error("同步作業發生嚴重錯誤：%s", exc)
            overall_success = False
            error_message = str(exc)

        finished_at = datetime.now(tz=UTC)
        logger.info(
            "========== 同步作業結束：新增 %d 筆、更新 %d 筆、跳過 %d 筆、失敗 %d 筆 ==========",
            total_created,
            total_updated,
            total_skipped,
            total_failed,
        )

        return SyncResult(
            started_at=started_at,
            finished_at=finished_at,
            success=overall_success,
            created_count=total_created,
            updated_count=total_updated,
            skipped_count=total_skipped,
            failed_count=total_failed,
            environment_results=env_results,
            error_message=error_message,
        )

    # ------------------------------------------------------------------
    # Private Methods
    # ------------------------------------------------------------------

    def _build_fcoe_account_map(
        self, fcoe_client: CloudabilityClient
    ) -> dict[str, VendorAccount]:
        """
        建立 FCoE 帳號 Map，以 "{vendor}:{vendorAccountId}" 為 key。
        """
        fcoe_map: dict[str, VendorAccount] = {}

        for vendor in self._sync_config.vendors:
            vendor_path = _resolve_vendor_path(vendor)
            try:
                accounts = fcoe_client.list_accounts(vendor_path)
                for account in accounts:
                    if account.vendor_account_id:
                        key = _build_key(vendor_path, account.vendor_account_id)
                        fcoe_map[key] = account
            except CloudabilityApiException as exc:
                if exc.http_status == 401:
                    # FCoE API Key 無效時，整體作業無法繼續
                    raise CloudabilityApiException(
                        f"FCoE API Key 無效，終止同步作業：{exc}", http_status=401
                    ) from exc
                logger.error("讀取 FCoE %s 帳號清單失敗：%s", vendor_path, exc)

        return fcoe_map

    def _sync_subsidiary(
        self,
        sub_client: CloudabilityClient,
        fcoe_client: CloudabilityClient,
        fcoe_map: dict[str, VendorAccount],
    ) -> EnvironmentSyncResult:
        """
        同步單一子公司環境。

        Args:
            sub_client: 子公司 API Client
            fcoe_client: FCoE API Client（用於 POST / PUT）
            fcoe_map:    FCoE 現有帳號 Map（同步過程中持續更新）

        Returns:
            此環境的同步結果
        """
        fetched = created = updated = skipped = failed = 0
        error_message: str | None = None

        try:
            for vendor in self._sync_config.vendors:
                vendor_path = _resolve_vendor_path(vendor)

                # 讀取子公司帳號清單
                try:
                    source_accounts = sub_client.list_accounts(vendor_path)
                except CloudabilityApiException as exc:
                    if exc.http_status == 401:
                        logger.error(
                            "子公司環境 API Key 無效（401），跳過同步：%s", exc
                        )
                        return EnvironmentSyncResult(
                            success=False,
                            error_message=str(exc),
                        )
                    logger.error("讀取子公司 %s 帳號清單失敗：%s", vendor_path, exc)
                    continue

                fetched += len(source_accounts)

                for source in source_accounts:
                    if not source.vendor_account_id:
                        continue

                    key = _build_key(vendor_path, source.vendor_account_id)

                    try:
                        if key in fcoe_map:
                            # FCoE 已存在 → 比對是否需要更新
                            existing = fcoe_map[key]
                            if _is_credential_changed(source, existing):
                                request = _build_request(source)
                                updated_account = fcoe_client.update_account(
                                    vendor_path, source.vendor_account_id, request
                                )
                                fcoe_map[key] = updated_account
                                updated += 1
                                logger.info(
                                    "帳號 %s (%s) 已更新至 FCoE",
                                    source.vendor_account_id,
                                    vendor_path,
                                )
                            else:
                                skipped += 1
                                logger.debug(
                                    "帳號 %s (%s) 無變更，跳過",
                                    source.vendor_account_id,
                                    vendor_path,
                                )

                        else:
                            # FCoE 不存在 → 新增
                            request = _build_request(source)
                            try:
                                created_account = fcoe_client.create_account(
                                    vendor_path, request
                                )
                            except CloudabilityApiException as ex:
                                if ex.http_status == 409:
                                    # 409 Conflict：帳號已存在，改以 PUT 更新
                                    logger.warning(
                                        "帳號 %s (%s) 已存在（409），改以 PUT 更新",
                                        source.vendor_account_id,
                                        vendor_path,
                                    )
                                    created_account = fcoe_client.update_account(
                                        vendor_path, source.vendor_account_id, request
                                    )
                                    updated += 1
                                    fcoe_map[key] = created_account
                                    continue
                                raise

                            fcoe_map[key] = created_account
                            created += 1
                            logger.info(
                                "帳號 %s (%s) 已新增至 FCoE",
                                source.vendor_account_id,
                                vendor_path,
                            )

                    except CloudabilityApiException as exc:
                        if exc.http_status == 404:
                            # 404 在 PUT 情境代表帳號不存在，改以 POST 新增
                            logger.warning(
                                "帳號 %s (%s) 在 FCoE 不存在（404），改以 POST 新增",
                                source.vendor_account_id,
                                vendor_path,
                            )
                            try:
                                fallback_request = _build_request(source)
                                created_account = fcoe_client.create_account(
                                    vendor_path, fallback_request
                                )
                                fcoe_map[key] = created_account
                                created += 1
                            except CloudabilityApiException as inner:
                                logger.error(
                                    "帳號 %s (%s) 新增失敗：%s",
                                    source.vendor_account_id,
                                    vendor_path,
                                    inner,
                                )
                                failed += 1
                        else:
                            logger.error(
                                "帳號 %s (%s) 同步失敗（HTTP %d）：%s",
                                source.vendor_account_id,
                                vendor_path,
                                exc.http_status,
                                exc,
                            )
                            failed += 1

        except Exception as exc:  # noqa: BLE001
            logger.exception("子公司環境同步發生未預期錯誤：%s", exc)
            error_message = str(exc)

        return EnvironmentSyncResult(
            success=error_message is None,
            fetched_count=fetched,
            created_count=created,
            updated_count=updated,
            skipped_count=skipped,
            failed_count=failed,
            error_message=error_message,
        )


# ---------------------------------------------------------------------------
# 輔助函式（模組層級，方便單元測試）
# ---------------------------------------------------------------------------


def _is_credential_changed(source: VendorAccount, existing: VendorAccount) -> bool:
    """
    比對來源帳號與 FCoE 現有帳號的認證設定是否有異動。
    以 authorization 欄位的關鍵值做比對。
    """
    src = source.authorization
    dst = existing.authorization

    if src is None and dst is None:
        return False
    if src is None or dst is None:
        return True

    if src.type != dst.type:
        return True

    # AWS 欄位
    if src.role_name != dst.role_name:
        return True
    if src.bucket_name != dst.bucket_name:
        return True
    if src.external_id != dst.external_id:
        return True
    if src.region != dst.region:
        return True
    if src.is_org_level_policy_enabled != dst.is_org_level_policy_enabled:
        return True

    # GCP 欄位
    if src.service_account_email != dst.service_account_email:
        return True
    if src.project_id != dst.project_id:
        return True

    # CUR 設定比對
    src_cur = src.cost_and_usage_report
    dst_cur = dst.cost_and_usage_report
    if src_cur is not None and dst_cur is not None:
        if src_cur.name != dst_cur.name or src_cur.prefix != dst_cur.prefix:
            return True
    elif src_cur is not None or dst_cur is not None:
        return True

    return False


def _build_request(source: VendorAccount) -> VendorAccountRequest:
    """從 VendorAccount 建立 POST/PUT Request Body"""
    request = VendorAccountRequest(vendor_account_id=source.vendor_account_id)

    auth: Authorization | None = source.authorization
    if auth is not None:
        request.type = auth.type
        request.role_name = auth.role_name
        request.bucket_name = auth.bucket_name
        request.external_id = auth.external_id
        request.cost_and_usage_report = auth.cost_and_usage_report
        request.region = auth.region
        request.is_org_level_policy_enabled = auth.is_org_level_policy_enabled
        request.service_account_email = auth.service_account_email
        request.project_id = auth.project_id

    return request
