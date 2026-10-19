"""
資料模型定義
對應 Cloudability API v3 回應結構及同步作業結果
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

# ---------------------------------------------------------------------------
# Cloudability API 回應模型
# ---------------------------------------------------------------------------


class CostAndUsageReport(BaseModel):
    """AWS Cost and Usage Report 設定"""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    name: str | None = None
    prefix: str | None = None


class Authorization(BaseModel):
    """Vendor Account 授權設定（同時支援 AWS aws_role 與 GCP gcp_service_account）"""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    # 通用
    type: str | None = None

    # AWS 專屬
    role_name: str | None = None
    bucket_name: str | None = None
    external_id: str | None = None
    cost_and_usage_report: CostAndUsageReport | None = None
    region: str | None = None
    is_org_level_policy_enabled: bool | None = None
    turbo_execution_enabled: bool | None = None
    application_type: str | None = None
    permissions: list[str] | None = None

    # GCP 專屬
    service_account_email: str | None = None
    project_id: str | None = None

    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore",
        alias_generator=None,
    )

    # Cloudability API 回應中欄位為 camelCase，使用 model_validator 處理
    @classmethod
    def model_validate(cls, obj: Any, **kwargs: Any) -> Authorization:  # type: ignore[override]
        if isinstance(obj, dict):
            obj = _camel_to_authorization(obj)
        return super().model_validate(obj, **kwargs)


def _camel_to_authorization(d: dict) -> dict:
    """將 camelCase API 回應欄位對應至 snake_case Authorization 欄位"""
    mapping = {
        "roleName": "role_name",
        "bucketName": "bucket_name",
        "externalId": "external_id",
        "costAndUsageReport": "cost_and_usage_report",
        "isOrgLevelPolicyEnabled": "is_org_level_policy_enabled",
        "turboExecutionEnabled": "turbo_execution_enabled",
        "applicationType": "application_type",
        "serviceAccountEmail": "service_account_email",
        "projectId": "project_id",
    }
    result: dict = {}
    for k, v in d.items():
        result[mapping.get(k, k)] = v
    return result


class Verification(BaseModel):
    """帳號驗證狀態"""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    state: str | None = None
    last_verification_attempted_at: str | None = None

    @classmethod
    def model_validate(cls, obj: Any, **kwargs: Any) -> Verification:  # type: ignore[override]
        if isinstance(obj, dict):
            obj = {
                "state": obj.get("state"),
                "last_verification_attempted_at": obj.get("lastVerificationAttemptedAt"),
            }
        return super().model_validate(obj, **kwargs)


class VendorAccount(BaseModel):
    """Cloudability Vendor Account（GET /v3/vendors/{vendor}/accounts 回應中的單筆資料）"""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str | None = None
    vendor_account_name: str | None = None
    vendor_account_id: str | None = None
    vendor_key: str | None = None
    verification: Verification | None = None
    authorization: Authorization | None = None
    created_at: str | None = None
    parent_account_id: str | None = None
    consumer_org_id: str | None = None
    byod_vendor: str | None = None

    @classmethod
    def model_validate(cls, obj: Any, **kwargs: Any) -> VendorAccount:  # type: ignore[override]
        if isinstance(obj, dict):
            obj = _camel_to_vendor_account(obj)
        return super().model_validate(obj, **kwargs)


def _camel_to_vendor_account(d: dict) -> dict:
    """將 camelCase API 回應對應至 snake_case VendorAccount 欄位"""
    mapping = {
        "vendorAccountName": "vendor_account_name",
        "vendorAccountId": "vendor_account_id",
        "vendorKey": "vendor_key",
        "createdAt": "created_at",
        "parentAccountId": "parent_account_id",
        "consumerOrgId": "consumer_org_id",
        "byodVendor": "byod_vendor",
    }
    result: dict = {}
    for k, v in d.items():
        mapped_key = mapping.get(k, k)
        if mapped_key == "authorization" and isinstance(v, dict):
            result[mapped_key] = Authorization.model_validate(v)
        elif mapped_key == "verification" and isinstance(v, dict):
            result[mapped_key] = Verification.model_validate(v)
        else:
            result[mapped_key] = v
    return result


class VendorAccountListResponse(BaseModel):
    """GET /v3/vendors/{vendor}/accounts 回應包裝"""

    model_config = ConfigDict(extra="ignore")

    result: list[VendorAccount] = []


class VendorAccountResponse(BaseModel):
    """GET/POST/PUT 單一帳號回應包裝"""

    model_config = ConfigDict(extra="ignore")

    result: VendorAccount | None = None


# ---------------------------------------------------------------------------
# POST / PUT Request Body
# ---------------------------------------------------------------------------


class VendorAccountRequest(BaseModel):
    """POST / PUT /v3/vendors/{vendor}/accounts Request Body"""

    vendor_account_id: str | None = None
    type: str | None = None

    # AWS
    role_name: str | None = None
    bucket_name: str | None = None
    external_id: str | None = None
    cost_and_usage_report: CostAndUsageReport | None = None
    region: str | None = None
    is_org_level_policy_enabled: bool | None = None

    # GCP
    service_account_email: str | None = None
    project_id: str | None = None

    def to_api_dict(self) -> dict:
        """轉換為 API camelCase 格式，排除 None 值"""
        mapping = {
            "vendor_account_id": "vendorAccountId",
            "type": "type",
            "role_name": "roleName",
            "bucket_name": "bucketName",
            "external_id": "externalID",
            "cost_and_usage_report": "costAndUsageReport",
            "region": "region",
            "is_org_level_policy_enabled": "isOrgLevelPolicyEnabled",
            "service_account_email": "serviceAccountEmail",
            "project_id": "projectId",
        }
        result: dict = {}
        for snake_key, camel_key in mapping.items():
            value = getattr(self, snake_key)
            if value is None:
                continue
            if snake_key == "cost_and_usage_report" and isinstance(value, CostAndUsageReport):
                result[camel_key] = value.model_dump(exclude_none=True)
            else:
                result[camel_key] = value
        return result


# ---------------------------------------------------------------------------
# 同步結果模型
# ---------------------------------------------------------------------------


class EnvironmentSyncResult:
    """單一子公司環境的同步結果"""

    def __init__(
        self,
        environment_name: str = "",
        success: bool = True,
        fetched_count: int = 0,
        created_count: int = 0,
        updated_count: int = 0,
        skipped_count: int = 0,
        failed_count: int = 0,
        error_message: str | None = None,
    ) -> None:
        self.environment_name = environment_name
        self.success = success
        self.fetched_count = fetched_count
        self.created_count = created_count
        self.updated_count = updated_count
        self.skipped_count = skipped_count
        self.failed_count = failed_count
        self.error_message = error_message


class SyncResult:
    """完整同步作業的執行結果"""

    def __init__(
        self,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        success: bool = True,
        created_count: int = 0,
        updated_count: int = 0,
        skipped_count: int = 0,
        failed_count: int = 0,
        environment_results: list[EnvironmentSyncResult] | None = None,
        error_message: str | None = None,
    ) -> None:
        self.started_at = started_at
        self.finished_at = finished_at
        self.success = success
        self.created_count = created_count
        self.updated_count = updated_count
        self.skipped_count = skipped_count
        self.failed_count = failed_count
        self.environment_results = environment_results or []
        self.error_message = error_message
