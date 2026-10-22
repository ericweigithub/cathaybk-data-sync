package com.cathaybk.datasync.service;

import com.cathaybk.datasync.client.CloudabilityClient;
import com.cathaybk.datasync.client.CloudabilityClientFactory;
import com.cathaybk.datasync.config.SyncProperties;
import com.cathaybk.datasync.model.*;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
@DisplayName("SyncService 同步邏輯測試")
class SyncServiceTest {

    @Mock
    private CloudabilityClientFactory clientFactory;

    @Mock
    private SyncProperties syncProperties;

    @Mock
    private CloudabilityClient subsidiaryClient;

    @Mock
    private CloudabilityClient fcoeClient;

    @InjectMocks
    private SyncService syncService;

    @BeforeEach
    void setUp() {
        when(syncProperties.getVendors()).thenReturn(List.of("amazon"));
        when(clientFactory.createFcoeClient()).thenReturn(fcoeClient);
        when(clientFactory.createSubsidiaryClients()).thenReturn(List.of(subsidiaryClient));
    }

    @Test
    @DisplayName("子公司有帳號、FCoE 無帳號 → 應新增（POST）")
    void sync_shouldCreate_whenAccountNotExistsInFcoe() {
        // Given
        VendorAccount sourceAccount = buildVendorAccount("111111111111", "aws");
        when(subsidiaryClient.listAccounts("AWS")).thenReturn(List.of(sourceAccount));
        when(fcoeClient.listAccounts("AWS")).thenReturn(List.of());
        when(fcoeClient.createAccount(eq("AWS"), any())).thenReturn(sourceAccount);

        // When
        SyncResult result = syncService.sync();

        // Then
        assertThat(result.isSuccess()).isTrue();
        assertThat(result.getCreatedCount()).isEqualTo(1);
        assertThat(result.getUpdatedCount()).isEqualTo(0);
        verify(fcoeClient).createAccount(eq("AWS"), any(VendorAccountRequest.class));
        verify(fcoeClient, never()).updateAccount(any(), any(), any());
    }

    @Test
    @DisplayName("子公司有帳號、FCoE 有相同帳號且無變更 → 應跳過")
    void sync_shouldSkip_whenAccountExistsWithNoChange() {
        // Given
        VendorAccount account = buildVendorAccount("111111111111", "aws");
        when(subsidiaryClient.listAccounts("AWS")).thenReturn(List.of(account));
        when(fcoeClient.listAccounts("AWS")).thenReturn(List.of(account));

        // When
        SyncResult result = syncService.sync();

        // Then
        assertThat(result.isSuccess()).isTrue();
        assertThat(result.getSkippedCount()).isEqualTo(1);
        assertThat(result.getCreatedCount()).isEqualTo(0);
        assertThat(result.getUpdatedCount()).isEqualTo(0);
        verify(fcoeClient, never()).createAccount(any(), any());
        verify(fcoeClient, never()).updateAccount(any(), any(), any());
    }

    @Test
    @DisplayName("子公司有帳號、FCoE 有相同帳號但 roleName 已變更 → 應更新（PUT）")
    void sync_shouldUpdate_whenCredentialChanged() {
        // Given
        VendorAccount source = buildVendorAccount("111111111111", "aws");
        source.getAuthorization().setRoleName("NewRole");

        VendorAccount existing = buildVendorAccount("111111111111", "aws");
        existing.getAuthorization().setRoleName("OldRole");

        when(subsidiaryClient.listAccounts("AWS")).thenReturn(List.of(source));
        when(fcoeClient.listAccounts("AWS")).thenReturn(List.of(existing));
        when(fcoeClient.updateAccount(eq("AWS"), eq("111111111111"), any())).thenReturn(source);

        // When
        SyncResult result = syncService.sync();

        // Then
        assertThat(result.isSuccess()).isTrue();
        assertThat(result.getUpdatedCount()).isEqualTo(1);
        verify(fcoeClient).updateAccount(eq("AWS"), eq("111111111111"), any(VendorAccountRequest.class));
        verify(fcoeClient, never()).createAccount(any(), any());
    }

    @Test
    @DisplayName("多個子公司帳號，部分已存在，部分未存在 → 混合新增與跳過")
    void sync_shouldHandleMixed() {
        // Given
        VendorAccount account1 = buildVendorAccount("111111111111", "aws");
        VendorAccount account2 = buildVendorAccount("222222222222", "aws");

        when(subsidiaryClient.listAccounts("AWS")).thenReturn(List.of(account1, account2));
        when(fcoeClient.listAccounts("AWS")).thenReturn(List.of(account1)); // account2 不存在
        when(fcoeClient.createAccount(eq("AWS"), any())).thenReturn(account2);

        // When
        SyncResult result = syncService.sync();

        // Then
        assertThat(result.getCreatedCount()).isEqualTo(1);
        assertThat(result.getSkippedCount()).isEqualTo(1);
    }

    // ----------------------------------------------------------------
    // Helper Methods
    // ----------------------------------------------------------------

    private VendorAccount buildVendorAccount(String accountId, String vendorKey) {
        VendorAccount account = new VendorAccount();
        account.setId(accountId);
        account.setVendorAccountId(accountId);
        account.setVendorAccountName("TestAccount-" + accountId);
        account.setVendorKey(vendorKey);

        Authorization auth = new Authorization();
        auth.setType("aws_role");
        auth.setRoleName("CloudabilityRole");
        auth.setBucketName("test-bucket");
        auth.setExternalId("test-external-id");
        auth.setRegion("us-east-1");
        auth.setIsOrgLevelPolicyEnabled(true);
        account.setAuthorization(auth);

        return account;
    }
}
