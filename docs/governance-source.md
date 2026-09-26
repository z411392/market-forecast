# Governance Source

本 repo 的治理基線 fork 自：

- Repository: `z411392/kaledoxa`
- Commit: `aa37bdb63d22dbc0bbd3337a1f8f1b23616fbd6b`
- Fork date: 2026-09-26

## 原則

- 複製治理機制，不複製 Kaledoxa 的產品語義。
- 保留完整 rule chain、GitHub human-readable records、Task-local readiness、獨立驗收、文件影響檢查、Git writer、small-commit delivery 等契約。
- Kaledoxa-specific BC、provider、UI、privacy/browser 規則若與 Market Forecast 不相干，必須由 Market Forecast 的 context/authority/spec 明確覆寫或移除，不能默認成產品需求。
- 治理差異必須以 Task/ADR/issue comment 留紀錄，不可在聊天中靜默漂移。

## Market Forecast 目前產品不變式

- Risk Forecast 與 B50 Current-State Momentum 永久分離。
- Primary target: future H=5 average realized variance。
- H=20 僅 confirmatory。
- Primary metric: QLIKE。
- 先 measurement harmonization，再判斷 global / market-specific / partial-pooling。
- TradingView/Pine 是 frozen deterministic inference 目標；Python/uv 負責多市場資料與研究 fitting。


## 2026-09-26 compatibility-link decision

使用者明示要求工具入口與規則目錄使用實體軟連結：

- `CLAUDE.md` 是 root canonical agent entrypoint。
- `AGENTS.md -> CLAUDE.md`。
- `GEMINI.md -> CLAUDE.md`。
- `.agents -> .claude`。

前三者與 Kaledoxa 現行 Git 形狀一致；`.agents` 則由 Kaledoxa 的「本機未追蹤 alias」改為本 repo 的 tracked symlink。這是使用者明示的治理差異，內容權威仍只在 `.claude/`。
