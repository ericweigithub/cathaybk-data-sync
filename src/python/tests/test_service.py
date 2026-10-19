"""
SyncService 單元測試

對應 Java 版 SyncServiceTest.java，以 pytest + pytest-mock 實作。
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from datasync.client import CloudabilityApiException, CloudabilityClientFactory
from datasync.config import SyncConfig
from datasync.models import Authorization, VendorAccount
from datasync.service import SyncService, _build_request, _is_credential_changed

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_vendor_account(account_id: str, vendor_key: str = "aws") -> VendorAccount:
    """建立測試用 VendorAccount（AWS aws_role 類型）"""
    auth = Authorization(
        type="aws_role",
        role_name="CloudabilityRole",
        bucket_name="test-bucket",
        external_id="test-external-id",
        region="us-east-1",
        is_org_level_policy_enabled=True,
    )
    return VendorAccount(
        id=account_id,
        vendor_account_id=account_id,
        vendor_account_name=f"TestAccount-{account_id}",
        vendor_key=vendor_key,
        authorization=auth,
    )


@pytest.fixture()
def sync_config() -> SyncConfig:
    return SyncConfig(vendors=["amazon"], schedule_enabled=False)


@pytest.fixture()
def mock_factory() -> MagicMock:
    return MagicMock(spec=CloudabilityClientFactory)


@pytest.fixture()
def mock_fcoe_client() -> MagicMock:
    return MagicMock()


@pytest.fixture()
def mock_subsidiary_client() -> MagicMock:
    return MagicMock()


@pytest.fixture()
def service(mock_factory: MagicMock, sync_config: SyncConfig) -> SyncService:
    return SyncService(mock_factory, sync_config)


# ---------------------------------------------------------------------------
# SyncService.sync() 情境測試
# ---------------------------------------------------------------------------


class TestSyncService:
    def test_should_create_when_account_not_exists_in_fcoe(
        self,
        service: SyncService,
        mock_factory: MagicMock,
        mock_fcoe_client: MagicMock,
        mock_subsidiary_client: MagicMock,
    ) -> None:
        """子公司有帳號、FCoE 無帳號 → 應新增（POST）"""
        source = _make_vendor_account("111111111111")

        mock_factory.create_fcoe_client.return_value = mock_fcoe_client
        mock_factory.create_subsidiary_clients.return_value = [mock_subsidiary_client]
        mock_fcoe_client.list_accounts.return_value = []
        mock_subsidiary_client.list_accounts.return_value = [source]
        mock_fcoe_client.create_account.return_value = source

        result = service.sync()

        assert result.success is True
        assert result.created_count == 1
        assert result.updated_count == 0
        mock_fcoe_client.create_account.assert_called_once()
        mock_fcoe_client.update_account.assert_not_called()

    def test_should_skip_when_account_exists_with_no_change(
        self,
        service: SyncService,
        mock_factory: MagicMock,
        mock_fcoe_client: MagicMock,
        mock_subsidiary_client: MagicMock,
    ) -> None:
        """子公司有帳號、FCoE 有相同帳號且無變更 → 應跳過"""
        account = _make_vendor_account("111111111111")

        mock_factory.create_fcoe_client.return_value = mock_fcoe_client
        mock_factory.create_subsidiary_clients.return_value = [mock_subsidiary_client]
        mock_fcoe_client.list_accounts.return_value = [account]
        mock_subsidiary_client.list_accounts.return_value = [account]

        result = service.sync()

        assert result.success is True
        assert result.skipped_count == 1
        assert result.created_count == 0
        assert result.updated_count == 0
        mock_fcoe_client.create_account.assert_not_called()
        mock_fcoe_client.update_account.assert_not_called()

    def test_should_update_when_credential_changed(
        self,
        service: SyncService,
        mock_factory: MagicMock,
        mock_fcoe_client: MagicMock,
        mock_subsidiary_client: MagicMock,
    ) -> None:
        """子公司有帳號、FCoE 有相同帳號但 role_name 已變更 → 應更新（PUT）"""
        source = _make_vendor_account("111111111111")
        source.authorization.role_name = "NewRole"  # type: ignore[union-attr]

        existing = _make_vendor_account("111111111111")
        existing.authorization.role_name = "OldRole"  # type: ignore[union-attr]

        mock_factory.create_fcoe_client.return_value = mock_fcoe_client
        mock_factory.create_subsidiary_clients.return_value = [mock_subsidiary_client]
        mock_fcoe_client.list_accounts.return_value = [existing]
        mock_subsidiary_client.list_accounts.return_value = [source]
        mock_fcoe_client.update_account.return_value = source

        result = service.sync()

        assert result.success is True
        assert result.updated_count == 1
        mock_fcoe_client.update_account.assert_called_once_with(
            "AWS", "111111111111", mock_fcoe_client.update_account.call_args[0][2]
        )
        mock_fcoe_client.create_account.assert_not_called()

    def test_should_handle_mixed_create_and_skip(
        self,
        service: SyncService,
        mock_factory: MagicMock,
        mock_fcoe_client: MagicMock,
        mock_subsidiary_client: MagicMock,
    ) -> None:
        """多個子公司帳號，部分已存在，部分未存在 → 混合新增與跳過"""
        account1 = _make_vendor_account("111111111111")
        account2 = _make_vendor_account("222222222222")

        mock_factory.create_fcoe_client.return_value = mock_fcoe_client
        mock_factory.create_subsidiary_clients.return_value = [mock_subsidiary_client]
        mock_fcoe_client.list_accounts.return_value = [account1]  # account2 不存在
        mock_subsidiary_client.list_accounts.return_value = [account1, account2]
        mock_fcoe_client.create_account.return_value = account2

        result = service.sync()

        assert result.created_count == 1
        assert result.skipped_count == 1

    def test_subsidiary_401_should_skip_environment(
        self,
        service: SyncService,
        mock_factory: MagicMock,
        mock_fcoe_client: MagicMock,
        mock_subsidiary_client: MagicMock,
    ) -> None:
        """子公司 API Key 無效（401）→ 跳過該環境，整體不失敗"""
        mock_factory.create_fcoe_client.return_value = mock_fcoe_client
        mock_factory.create_subsidiary_clients.return_value = [mock_subsidiary_client]
        mock_fcoe_client.list_accounts.return_value = []
        mock_subsidiary_client.list_accounts.side_effect = CloudabilityApiException(
            "401 Unauthorized", http_status=401
        )

        result = service.sync()

        # 子公司環境失敗，但整體 success 標記為 False（因為有環境回報失敗）
        assert result.created_count == 0
        env_result = result.environment_results[0]
        assert env_result.success is False

    def test_fcoe_401_should_abort_entire_sync(
        self,
        service: SyncService,
        mock_factory: MagicMock,
        mock_fcoe_client: MagicMock,
        mock_subsidiary_client: MagicMock,
    ) -> None:
        """FCoE API Key 無效（401）→ 終止整體同步作業"""
        mock_factory.create_fcoe_client.return_value = mock_fcoe_client
        mock_factory.create_subsidiary_clients.return_value = [mock_subsidiary_client]
        mock_fcoe_client.list_accounts.side_effect = CloudabilityApiException(
            "401 Unauthorized", http_status=401
        )

        result = service.sync()

        assert result.success is False
        mock_subsidiary_client.list_accounts.assert_not_called()

    def test_create_409_should_fallback_to_put(
        self,
        service: SyncService,
        mock_factory: MagicMock,
        mock_fcoe_client: MagicMock,
        mock_subsidiary_client: MagicMock,
    ) -> None:
        """POST 收到 409 Conflict → 自動改以 PUT 更新"""
        source = _make_vendor_account("111111111111")

        mock_factory.create_fcoe_client.return_value = mock_fcoe_client
        mock_factory.create_subsidiary_clients.return_value = [mock_subsidiary_client]
        mock_fcoe_client.list_accounts.return_value = []
        mock_subsidiary_client.list_accounts.return_value = [source]
        mock_fcoe_client.create_account.side_effect = CloudabilityApiException(
            "409 Conflict", http_status=409
        )
        mock_fcoe_client.update_account.return_value = source

        result = service.sync()

        assert result.updated_count == 1
        mock_fcoe_client.update_account.assert_called_once()

    def test_update_404_should_fallback_to_post(
        self,
        service: SyncService,
        mock_factory: MagicMock,
        mock_fcoe_client: MagicMock,
        mock_subsidiary_client: MagicMock,
    ) -> None:
        """PUT 收到 404 → 自動改以 POST 新增"""
        source = _make_vendor_account("111111111111")
        existing = _make_vendor_account("111111111111")
        existing.authorization.role_name = "OldRole"  # type: ignore[union-attr]

        mock_factory.create_fcoe_client.return_value = mock_fcoe_client
        mock_factory.create_subsidiary_clients.return_value = [mock_subsidiary_client]
        mock_fcoe_client.list_accounts.return_value = [existing]
        mock_subsidiary_client.list_accounts.return_value = [source]
        mock_fcoe_client.update_account.side_effect = CloudabilityApiException(
            "404 Not Found", http_status=404
        )
        mock_fcoe_client.create_account.return_value = source

        result = service.sync()

        assert result.created_count == 1
        mock_fcoe_client.create_account.assert_called_once()


# ---------------------------------------------------------------------------
# _is_credential_changed 單元測試
# ---------------------------------------------------------------------------


class TestIsCredentialChanged:
    def test_no_change_returns_false(self) -> None:
        account = _make_vendor_account("111")
        assert _is_credential_changed(account, account) is False

    def test_role_name_change_returns_true(self) -> None:
        src = _make_vendor_account("111")
        dst = _make_vendor_account("111")
        dst.authorization.role_name = "DifferentRole"  # type: ignore[union-attr]
        assert _is_credential_changed(src, dst) is True

    def test_both_auth_none_returns_false(self) -> None:
        src = VendorAccount(vendor_account_id="111")
        dst = VendorAccount(vendor_account_id="111")
        assert _is_credential_changed(src, dst) is False

    def test_one_auth_none_returns_true(self) -> None:
        src = _make_vendor_account("111")
        dst = VendorAccount(vendor_account_id="111")
        assert _is_credential_changed(src, dst) is True

    def test_region_change_returns_true(self) -> None:
        src = _make_vendor_account("111")
        dst = _make_vendor_account("111")
        dst.authorization.region = "ap-southeast-1"  # type: ignore[union-attr]
        assert _is_credential_changed(src, dst) is True


# ---------------------------------------------------------------------------
# _build_request 單元測試
# ---------------------------------------------------------------------------


class TestBuildRequest:
    def test_builds_request_from_vendor_account(self) -> None:
        account = _make_vendor_account("111111111111")
        request = _build_request(account)

        assert request.vendor_account_id == "111111111111"
        assert request.type == "aws_role"
        assert request.role_name == "CloudabilityRole"
        assert request.bucket_name == "test-bucket"
        assert request.external_id == "test-external-id"
        assert request.region == "us-east-1"
        assert request.is_org_level_policy_enabled is True

    def test_builds_request_with_no_auth(self) -> None:
        account = VendorAccount(vendor_account_id="999")
        request = _build_request(account)

        assert request.vendor_account_id == "999"
        assert request.type is None

    def test_to_api_dict_camel_case(self) -> None:
        account = _make_vendor_account("111111111111")
        request = _build_request(account)
        api_dict = request.to_api_dict()

        assert "vendorAccountId" in api_dict
        assert "roleName" in api_dict
        assert "bucketName" in api_dict
        assert "externalID" in api_dict
        assert "region" in api_dict
        assert "isOrgLevelPolicyEnabled" in api_dict
        # None 值不應出現
        assert "serviceAccountEmail" not in api_dict
        assert "projectId" not in api_dict
