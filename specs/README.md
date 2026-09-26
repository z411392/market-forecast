# Story 規格與交付操作契約

本頁定義 GitHub 工作階層如何落到 Story spec、Task、BDD、驗證與獨立驗收。
它是操作契約，不是產品 authority；產品範圍、業務規則、路線圖、領域邊界與工程規則仍由各自唯一文件維護。

- 文件歸屬：[`.claude/rules/80-documentation.md`](../.claude/rules/80-documentation.md)
- 執行拓撲與 Task-local readiness：[`.claude/rules/15-execution-strategy.md`](../.claude/rules/15-execution-strategy.md)
- 測試與驗收：[`.claude/rules/70-testing.md`](../.claude/rules/70-testing.md)
- Git 交付：[`.claude/rules/90-operations.md`](../.claude/rules/90-operations.md)
- 產品路線圖：[`docs/delivery/mvp-phases.md`](../docs/delivery/mvp-phases.md)

## 工作階層

GitHub 原生階層固定為：

```text
Epic
└── Story
    ├── Task
    ├── Bug
    └── Spike
```

Task／Bug／Spike 內的有限步驟用 S1、S2… checklist 或驗收表表示，不建立第四層 Agile Issue。
Project 只保存 Status／Priority／Sprint 等工作管理欄位；產品規則與驗收正文不放進 Project field。

## Story 三檔與 SSOT

只有 Story 建立 `specs/<issue>-<slug>/`：

- `spec.md`：Story 特有情境、規則與 Acceptance Criteria。
- `plan.md`：技術方案、邊界、依賴、接口與驗證方法。
- `progress.md`：目前事實、研究發現、決策引用、驗證證據、阻塞與下一步。

Epic、Task、Bug、Spike 不建立自己的 specs 目錄。
跨 Story 的共同產品規則留在 `docs/delivery/requirements-specification.md`；Event Storming、Context Map、Roadmap 各自維持唯一正文，不在 Story 三檔複製第二份。

## 從 Event Storming 到可驗收 Story

1. 從 Roadmap outcome 與 Event Storming 的完整業務流程切 Epic／Story，不按資料夾、DTO、模型或 agent 數量切工作。
2. Story 必須有 Actor／觸發、Command、主要事件因果、Policy／例外與可觀察終點；引用 Event Storming 的唯一流程位置。
3. `spec.md` 為 Story 情境建立局部穩定的 `SC-xx` 與 `AC-xx`，並以 Given／When／Then 說清正例、反例、禁止副作用與無法證明的範圍。
4. `plan.md` 把 AC 映射到 Context Map owner、ports／DTO／adapter 邊界、exact writable／frozen paths、依賴與 oracle。
5. 依實作責任建立有限 Task／Bug／Spike；每個 leaf issue 只承接一個可判定責任。
6. 實作前依 Rule 15 核對 Task-local readiness；不得用無關 Story、後續 Phase 或 generic global gate 阻擋已具備直接前提的工作。
7. Verify 保存實際 revision、命令、exit code、日期與正反結果；未執行就寫 `NOT_RUN`，不得把預期值當成實測。
8. Accept 由未參與該修改的 Reviewer 唯讀比對 AC、diff 與工具證據；作者不能自我驗收。

## Task／Subtask 的驗收落實

每個 leaf issue 的每一個 Subtask 都要把 Story AC 落到可執行證據。至少記錄：

| 欄位 | 內容 |
|---|---|
| Subtask | S1、S2…穩定識別 |
| Event／SC／AC | 對應流程、Story scenario 與 AC |
| Roadmap | phase、exit ID、effect |
| Given／When／Then | 固定前置、單一操作、可觀察結果 |
| 正反例 | success、reject／failure、禁止副作用；不適用者寫理由 |
| Oracle | 測試層級、命令或有限人工步驟、預期值 |
| Revision／evidence | commit、實測結果、日期、Reviewer |

文件／治理工作不虛構 domain event 或程式 RED；它們用內容、連結、schema、tree mode、deterministic checker 等適合的 oracle。

## Roadmap 貢獻與證據

Roadmap phase 只使用現行 `P0`–`P4`；exit ID 以 `docs/delivery/mvp-phases.md` 為準。

| Roadmap effect | 語義 |
|---|---|
| `ADVANCES` | 本批讓指定 Exit 更接近成立，但不等於已證明。 |
| `PROVES` | 本批提供該 Exit 必要驗證與獨立判定。 |
| `SUPPORT_ONLY` | 治理、文件、設計、工具等支援工作，不擁有產品 Exit。 |
| `FUTURE_PHASE` | 後續產品工作，不抵扣目前尚未成立的 Exit。 |

Exit verdict 使用 `NOT_PROVEN`、`PROVEN` 或有具體解除條件的 `BLOCKED`。
`PROVEN` 必須有必要 implementation revision、適用的正反證據、實際命令／日期，以及未參與修改者的獨立審閱；Task Done、文件存在或局部 test exit 0 都不能單獨推出 Exit 已成立。

## 三個 Story 文件的必填結構

`spec.md`：

```markdown
# Story #<n> — <name>
Story: <GitHub Issue URL>
Roadmap phase: <P0-P4>
Roadmap exit IDs: <exact IDs>
Roadmap effect: <ADVANCES / PROVES / SUPPORT_ONLY / FUTURE_PHASE>

## Problem / outcome
## Scope / non-goals
## EventStorming scenarios
## Business rules
## Acceptance criteria
## Open questions
```

`plan.md`：

```markdown
# Plan

## Approach
## Boundaries / dependencies
## Decisions
## Interfaces / files
## Validation approach
```

`progress.md`：

```markdown
# Progress
Roadmap phase: <P0-P4>
Roadmap exits affected: <exact IDs or None>
Exit verdicts: <ID -> PROVEN / NOT_PROVEN / BLOCKED>
What became true since previous update: <new facts>
First blocking exit: <first unmet product Exit>
Remaining conditions preventing phase exit: <conditions>

## Current work
## Findings
## Decisions
## Validation
## Blockers
## Next
```

Progress 第一屏先回答產品與 Exit 現況，再放工程歷程。其他 Story 的 Exit 只引用 owner evidence，不在本 Story 建競爭 verdict。

## Git、PR 與獨立驗收

- initial bootstrap 之後，每個 Task 使用 `codex/<task-id>-<slug>` 專屬分支。
- leaf issue 內每個 Subtask 經指定驗證後形成一個可追溯 commit；不同 Subtask／Task 不混提交。
- commit message 使用英文；Issue／comment／文件敘述使用繁體中文。
- PR 必須引用 Task、parent Story／spec／plan、Subtask、Roadmap mapping、exact writable／frozen paths、驗證證據與 Reviewer 結論。
- 合流保留 Subtask commit 歷史；Task 未取得必要獨立驗收前不得因「有 commit」自行判定 accepted。
- live provider、付費／quota market-data、bulk backfill、export、model／universe freeze 等副作用只在 Task 明示授權範圍內執行。

## 新需求與維護

每次需求、補充、更正或需求反轉先依 Rule 80 完成五類文件影響檢查：

1. Roadmap／產品成果。
2. 共通業務規則與 AC。
3. Event Storming／Ubiquitous Language／BC。
4. Context Map／公開契約與 owner。
5. GitHub 工作分解與 Story 三檔。

只修改唯一 owner；不建立 WI、平行總計畫、第二份 Story AC 或 archive 文件樹。
研究、探索、失敗、修正、驗證與 blocker 寫回原 Task／Story progress，讓後續接手者不依賴聊天紀錄。

## 跨 repository 邊界

目前 Market Forecast 以單一 repository 為產品 authority。若未來出現 sibling repository：

- parent Story 與 `spec/plan/progress` 仍只有一份 owner。
- 每個 repository 只修改自己有權實作的 Task。
- 跨 repo 工作者必須讀目標 repository 自己的規則；不得把本 repo 的 runtime identity、Project 狀態或產品文件複製成對方現行事實。
