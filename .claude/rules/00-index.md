# 規則索引

此目錄是三種 coding agent 共用的工程規則真相。`.agents` 是未追蹤的本機相容 alias（`.agents -> .claude`），不是遠端閱讀依賴；正式 tracked 來源是本目錄。
規則不放產品範圍、業務 AC、工作進度或模型清單；這些各自的入口見 [docs/README.md](../../docs/README.md)。

## 必讀清單

開始任何工作前完整讀完以下檔案；派工 prompt 必須明列它們，而非只寫「遵守專案規則」。

1. [05-methodology.md](05-methodology.md)：接手、有限 phase、派工、回報與停止。
2. [10-architecture.md](10-architecture.md)：目錄、依賴方向與公開邊界。
3. [15-execution-strategy.md](15-execution-strategy.md)：查證、決策、Task-local readiness 唯一判準、驗證成本與協作。
4. [16-github-human-readable-records.md](16-github-human-readable-records.md)：Issue／Comment 的人類可讀雙層格式、歷史摘要與 append-only 遷移規則。
5. [20-code-style.md](20-code-style.md)：語言、檔案、import 與命名。
6. [30-application-domain.md](30-application-domain.md)：application／domain。
7. [40-ports-adapters-di.md](40-ports-adapters-di.md)：ports、adapters、DI 與 composition。
8. [50-dtos-errors-http.md](50-dtos-errors-http.md)：DTO、parser、錯誤與 HTTP。
9. [60-configuration-data.md](60-configuration-data.md)：設定、資料、安全與 logging。
10. [70-testing.md](70-testing.md)：TDD、測試 oracle、focused／完整 gate。
11. [80-documentation.md](80-documentation.md)：MECE／SSOT、文件格式與維護。
12. [90-operations.md](90-operations.md)：操作、破壞性限制與 Git 交付規則。

跨 repo 寫 frontend 時另讀 frontend `.claude/rules/00-index.md` 全部指定檔案。
規則與程式衝突時先指出哪一條過期或越界，不自開例外。既有 source tests 是 oracle，不能為了改文件而偷偷放寬。
