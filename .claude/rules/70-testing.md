# 測試

## 核心原則

測試組織依據兩個正交維度劃分：

1. 真相擁有權與修改權限維度（誰擁有真相、是否凍結）
2. 執行拓撲與回饋成本維度（測試執行的物理邊界與時間預算）

測試跟著 owner 與真相放置，不放 repo 根目錄無主的 `tests/`，也不建立獨立的 `tests/regression/` 目錄。

## 真相擁有權與放置位置

```text
Acceptance   → 跟 Requirement / Product Behavior（業務場景、端到端驗收）
Contract     → 跟 Contract Owner（Ports、DTOs、OpenAPI、Schemas 定義處）
Architecture → 跟 Architecture Owner（架構防線、依賴方向、去識別約束）
Governance   → 跟 Governance Owner（控制面、Delivery Matrix、DAG 一致性）
Regression   → 跟原本的 Test Level / Component 放一起（不獨立成目錄）
```

目錄放置映射：

```text
apps/<app>/tests/acceptance/       app 專屬流程驗收（如 CLI 專屬命令流程）
apps/<app>/tests/contract/         app 對外傳輸與 API 契約（如 OpenAPI、HTTP 路由契約）
apps/<app>/tests/integration/      app 驅動適配器與 DI 組裝（Hermetic）
apps/<app>/tests/unit/             app 內部 handler 與參數解析
apps/<app>/tests/e2e/              已接線 app 完整端到端演練
libs/<feature>/tests/contract/     feature 擁有的 ports 與公開契約
libs/<feature>/tests/integration/  具體 driven adapters 與儲存引擎（如本機 SQLite）
libs/<feature>/tests/unit/         領域邏輯、純函數、DTO 驗證與局部回歸
libs/kernel/tests/architecture/    全域架構防線、import 方向、Thin Apps 約束
libs/kernel/tests/governance/      交付矩陣、Task 依賴、控制面一致性檢查
libs/kernel/tests/unit/            kernel 內部純工具函數
```

跨多個 feature 或整個系統的驗收與架構測試，放置於 `tests/acceptance/` 與 `tests/architecture/`。

## 執行階層與回饋預算（Tier 0 ～ Tier 5）

所有測試按回饋成本與執行特性劃分為六個階層：

```text
Tier 0: Invariants & Guards   (< 2 秒，架構防線、型別約束、Schema 不變式，最先失敗)
Tier 1: Pure Domain Unit       (< 15 秒，純領域模型、純函數公式、Parser 解析，零 I/O)
Tier 2: Contract & Adapter     (< 30 秒，Ports 契約、Fake I/O 適配器、本機 SQLite 隔離交易)
Tier 3: Heavy Computation     (< 45 秒，蒙地卡羅、大矩陣運算、重型統計模擬)
Tier 4: Hermetic E2E           (< 30 秒，已組裝 CLI/HTTP、離線端到端流程)
Tier 5: Live Integration       (真實外部網路、provider API、即時平台觀測，非 hermetic)
```

Tier 0 至 Tier 4 屬於離線 hermetic 測試，必須全數納入 `make ci-fast`。Tier 5 標記 `@pytest.mark.live_external`，只在 release gate 或手動觸發。`integration` marker 保留給本機、離線的 adapter／storage integration tests。

## AI Agent 治理與 Done Contract

派工時必須以目錄與檔案路徑明確宣告 Frozen Scope 與 Writable Scope，不得要求模型自行猜測修改邊界：

1. Frozen External Oracle（外部真相，由 Design 凍結，Implementer 嚴禁修改）：
   - `tests/acceptance/**` 與 `apps/*/tests/acceptance/**`
   - `src/libs/*/tests/contract/**` 與 `apps/*/tests/contract/**`
   - `src/libs/kernel/tests/architecture/**` 與 `tests/architecture/**`
   - `src/libs/kernel/tests/governance/**` 與 `tests/governance/**`
2. Implementer Writable（實作可寫）：
   - Production 程式碼（指定之 Leaf 模組）
   - `src/libs/*/tests/unit/**` 與 `apps/*/tests/unit/**`
   - `src/libs/*/tests/integration/**` 與 `apps/*/tests/integration/**`
   - `src/libs/*/tests/fixtures/**` 與測試輔助函式

Implementer 發現測試失敗時，只准修改 Writable 範圍內的實作或 unit/integration 測試；若認為 Frozen 測試有誤，必須停止並回報 `DESIGN_BLOCKED`。

## TDD 與 BDD

### Task／Subtask 的 EventStorming 與 BDD 驗收

每個 Task 及其 leaf 內 Subtask 的驗收，必須有可追溯鏈：EventStorming 流程錨點／情境 → Story SC／AC → Task／Subtask → Given／When／Then → oracle／證據。不得只有檔案清單、DTO 欄位存在、命令 exit 0 或「遵守 BDD」字樣。

1. 輸入是 Story spec、共通 AC 與相關事件因果。先指定該 Subtask 支援的觸發者／命令、前置狀態、成立事件或可觀察結果，以及失敗停止點；不為每個函式或測試新增領域事件。
2. 在原 Task 的 Subtask checklist 定義 Given（固定資料及狀態）、When（一次操作／觸發）、Then（可判定輸出、狀態變化、次數與禁止副作用）。引用 Story 的既有 AC，不另立競爭業務規則。
3. 每個適用分支至少有正例及反例；逐項判斷零結果、重複、失敗、中斷／重播是否適用，不適用寫理由。技術／文件 Subtask 可以驗證其交付行為，但必須連回支持的 Story AC；不虛构 UI 或業務事件。
4. 指定每個 GWT 的測試層級、exact oracle、命令／人工步驟、預期值、負責驗收者。純 helper 的 PASS 不證 durable／外部來源／跨 BC 端到端 PASS。設計與文件工作用有界內容／追溯檢查，不虛構程式 RED。
5. 實作依 RED→GREEN→Refactor；完成時逐 GWT 記 revision、實際證據與未執行項。缺追溯或 oracle 不得 Ready；指定驗收未通過不得 Done。獨立審收後才結案；Subtask commit 不能取代驗收。

輸出為原 Task 中可查驗的 BDD 驗收表及 Story progress 的直接證據；完成該批核對即停止，不建立另一份驗收文件庫。無關 Subtask 不因共用同 Story 被強制重跑所有流程，但須說明本批證明與未證明的範圍。

- 每個 Task 先將其相關 Story BDD scenarios／AC 轉為因缺少目標行為而失敗的自動驗收測試、contract tests 或 unit tests；不要求無關的整張 Story 先 RED。開工依 [Task-local readiness](15-execution-strategy.md#task-local-readiness)，不降低本 Task frozen oracle、TDD 或 Story 必要 AC 的獨立驗收標準。
- 每次開發循環遵守 Red → Green → Refactor；不得完成整套實作後才補測試。
- Green 階段只完成讓目前目標行為成立的最小改動；重構不得改變已通過的公開行為。
- 外部平台本身無法 hermetic 測試時，先以 fixtures 測試 port、parser、狀態機與失敗契約，再另做帶日期的真站台觀測。
- BDD scenario 若刻意不自動化，交接時必須說明原因與替代證據。

## 測試行為規範

- Unit test 使用 fake ports 與合成資料，不呼叫真 provider API、不連真實網路、不讀取 licensed／raw market data。
- E2E 使用正式 composition root 或標準 test bindings，驗證真實 CLI/HTTP 契約。
- 測試必須自行固定行為標記與環境設定，開發者的本機 `.env` 不得改變測試結果。
- 測試資料使用明顯虛構內容，不得包含真實機構、個人姓名、私有帳號或真實 URL。
- Source ownership、版本、已封存狀態、coverage gap 與來源連結 fallback 必須包含正反案例。

## Gates 與開發者指令

```text
make ci-fast
├── lint
├── typecheck
├── architecture-check   (Tier 0 架構防線)
├── governance-check     (Tier 0 交付矩陣與一致性)
└── test
      ├── contract-check (Tier 2 契約與 Ports)
      ├── acceptance     (Tier 4 / 產品驗收)
      ├── unit           (Tier 1 純領域與單元)
      ├── integration    (Tier 2/3 本機隔離整合與重運算)
      └── e2e            (Tier 4 應用程式端到端)
```

開發者快速回饋指令：

```bash
make test-fast     # < 15 秒，執行 Tier 0 與 Tier 1 純領域測試
make test-contract # 執行 Tier 0 架構與 Tier 2 契約測試
make test-pkg      # 執行指定套件的隔離測試 (PKG=libs/foo)
make integration   # 執行 Tier 5 真外部整合測試
```

## 架構規則注入驗證（Architecture Rule Staging）

1. 先將架構規則寫成測試。
2. 讓目前 repo 在本機全綠。
3. 注入一個真實違規，確認測試精確失敗。
4. 加入相近的合法對照組，確認測試通過。
5. 移除所有 injection 痕跡。
6. 最後才將測試納入 `architecture-check`。

只證明違規會失敗可能代表規則過寬；合法對照組用來證明它精確防護目標邊界。

## 安全故障注入

正式變更尚未 commit 前，嚴禁使用 `git checkout -- <file>` 還原注入，避免連同正常改動一併刪除。

依序偏好：

1. 先 commit 正式變更，再注入與還原。
2. 保存並還原精確 scratch copy。
3. 使用臨時 worktree。

注入完成後確認 `INJECTED` 零命中，再執行完整 gate。

## 真實站台觀測

真實觀測不是一般自動化測試。它只證明特定日期、特定設定下觀察到的外部行為，必須記錄日期、目標類型、結果與資料是否被修改；不得把單次觀測成功當作平台永久契約。
