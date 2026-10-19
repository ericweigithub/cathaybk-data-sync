# cathaybk-data-sync

國泰 Apptio（FinOps）雲端認證資料同步服務。

將 7 個子公司 Cloudability 環境中的 AWS / GCP Vendor Accounts，自動單向同步至 FCoE（+1）環境，使 FCoE 具備集團層級的帳務彙整與統一管理能力。

---

## 目錄

- [專案結構](#專案結構)
- [前置需求](#前置需求)
- [設定檔](#設定檔)
- [Java 版本](#java-版本)
- [Python 版本](#python-版本)
- [API 端點](#api-端點)
- [同步邏輯說明](#同步邏輯說明)

---

## 專案結構

```
cathaybk-data-sync/
├── doc/
│   └── 雲端認證資料同步規格書.md
└── src/
    ├── java/                   # Java / Spring Boot 版本
    │   ├── pom.xml
    │   └── src/
    └── python/                 # Python / FastAPI 版本
        ├── pyproject.toml
        ├── config.yaml         # 設定檔範例
        ├── .env.example        # 環境變數範例
        ├── datasync/
        └── tests/
```

---

## 前置需求

### Java 版本

| 項目 | 版本需求 |
|------|---------|
| JDK  | 21 以上 |
| Maven | 3.9 以上 |

### Python 版本

| 項目 | 版本需求 |
|------|---------|
| Python | 3.11 以上 |
| pip | 23 以上 |

---

## 設定檔

兩個版本共用相同的設定結構。複製 `src/python/config.yaml` 為執行目錄下的 `config.yaml`，並以環境變數注入 API Key。

```yaml
cloudability:
  base_url: "https://api.cloudability.com/v3"
  subsidiaries:
    - name: "子公司A"
      api_key: "${SUBSIDIARY_A_API_KEY}"
    # ... 共 7 個子公司
  fcoe:
    name: "FCoE"
    api_key: "${FCOE_API_KEY}"
  http:
    connect_timeout_seconds: 30
    read_timeout_seconds: 60
    max_retry: 3
    retry_interval_seconds: 60

sync:
  vendors:
    - amazon   # AWS
    - google   # GCP
  enable_delete: false
  cron: "0 2 * * *"       # 每日凌晨 02:00（Python / Unix cron）
  schedule_enabled: true
  log_path: "./logs/sync.log"
```

> **資安注意**：API Key 請一律使用環境變數（`${VAR_NAME}`）或密鑰管理工具注入，切勿明文寫入設定檔。

設定環境變數範例（參考 `src/python/.env.example`）：

```bash
export SUBSIDIARY_A_API_KEY=your_key_here
export SUBSIDIARY_B_API_KEY=your_key_here
# ... 依此類推至 G
export FCOE_API_KEY=your_fcoe_key_here
```

---

## Java 版本

### 環境變數設定

Java 版本透過 Spring Boot 的 `application.yml` 讀取環境變數，格式為 `${ENV_VAR}`：

```bash
export SUBSIDIARY_A_API_KEY=your_key_here
export FCOE_API_KEY=your_fcoe_key_here
# ... 其餘 API Key
```

### 建置

```bash
cd src/java
mvn clean package -DskipTests
```

建置完成後，JAR 檔位於 `target/cathaybk-data-sync-1.0.0-SNAPSHOT.jar`。

### 執行

**方式一：Maven 直接執行（開發用）**

```bash
cd src/java
mvn spring-boot:run
```

**方式二：執行 JAR（正式環境）**

```bash
cd src/java
java -jar target/cathaybk-data-sync-1.0.0-SNAPSHOT.jar
```

**方式三：指定外部設定檔**

```bash
java -jar target/cathaybk-data-sync-1.0.0-SNAPSHOT.jar \
  --spring.config.location=file:/etc/datasync/application.yml
```

**方式四：覆蓋個別設定值**

```bash
java -jar target/cathaybk-data-sync-1.0.0-SNAPSHOT.jar \
  --sync.schedule-enabled=false \
  --logging.level.com.cathaybk=DEBUG
```

服務預設監聽 **Port 8080**。

### 執行測試

```bash
cd src/java
mvn test
```

### 停用排程（僅手動觸發）

在 `application.yml` 或啟動參數設定：

```bash
java -jar target/cathaybk-data-sync-1.0.0-SNAPSHOT.jar \
  --sync.schedule-enabled=false
```

---

## Python 版本

### 安裝依賴

```bash
cd src/python

# 正式環境
pip install -e .

# 開發環境（含測試工具）
pip install -e ".[dev]"
```

### 執行

**方式一：Python 模組執行**

```bash
cd src/python
python -m datasync.main
```

**方式二：安裝後使用指令**

```bash
pip install -e .
datasync
```

**方式三：指定設定檔路徑**

```bash
python -m datasync.main --config /etc/datasync/config.yaml
```

**方式四：完整參數指定**

```bash
python -m datasync.main \
  --config ./config.yaml \
  --host 0.0.0.0 \
  --port 8080 \
  --log-level INFO
```

**方式五：透過環境變數指定**

```bash
CONFIG_PATH=/etc/datasync/config.yaml \
SERVER_PORT=9090 \
LOG_LEVEL=DEBUG \
python -m datasync.main
```

服務預設監聽 **Port 8080**。

### 可用啟動參數

| 參數 | 環境變數 | 預設值 | 說明 |
|------|---------|--------|------|
| `--config` | `CONFIG_PATH` | `./config.yaml` | 設定檔路徑 |
| `--host` | `SERVER_HOST` | `0.0.0.0` | HTTP 服務監聽 IP |
| `--port` | `SERVER_PORT` | `8080` | HTTP 服務監聽 Port |
| `--log-level` | `LOG_LEVEL` | `INFO` | Log 等級 |

### 執行測試

```bash
cd src/python
python -m pytest tests/ -v
```

### 執行 Lint

```bash
cd src/python
python -m ruff check datasync/ tests/
```

### 停用排程（僅手動觸發）

在 `config.yaml` 設定：

```yaml
sync:
  schedule_enabled: false
```

---

## API 端點

兩個版本均提供相同的 HTTP 端點：

### 手動觸發同步

```
POST /api/sync/trigger
```

**回應範例（成功）**

```json
{
  "success": true,
  "started_at": "2026-10-19T02:00:00Z",
  "finished_at": "2026-10-19T02:00:45Z",
  "created_count": 12,
  "updated_count": 3,
  "skipped_count": 42,
  "failed_count": 0,
  "error_message": null
}
```

### 健康檢查

```
GET /health
```

**Java 版本（Spring Actuator）**

```
GET /actuator/health
```

---

## 同步邏輯說明

```
開始
 │
 ├─ 1. 呼叫 FCoE 環境 GET /vendors/{vendor}/accounts
 │       ↓ 建立現有帳號索引（vendor:vendorAccountId 為唯一鍵）
 │
 ├─ 2. 逐一呼叫 7 個子公司環境 GET /vendors/{vendor}/accounts
 │       ↓ 收集所有 AWS + GCP 帳號清單
 │
 ├─ 3. 比對差異
 │       ├─ 子公司有、FCoE 無 → POST 新增
 │       ├─ 子公司有、FCoE 有、credentials 有異動 → PUT 更新
 │       ├─ 子公司有、FCoE 有、credentials 無異動 → 跳過
 │       └─ POST 收到 409 / PUT 收到 404 → 自動切換操作
 │
 ├─ 4. 記錄同步結果至 Log
 │
結束
```

### 錯誤處理

| HTTP 狀態碼 | 處理方式 |
|-------------|---------|
| `401 Unauthorized` | FCoE：終止整體同步；子公司：跳過該環境 |
| `400 Bad Request` | 記錄錯誤，跳過該帳號 |
| `404 Not Found` | PUT 情境改以 POST 新增 |
| `409 Conflict` | POST 情境改以 PUT 更新 |
| `429 Too Many Requests` | Exponential Backoff 重試（最多 3 次） |
| `5xx Server Error` | Exponential Backoff 重試（最多 3 次） |
