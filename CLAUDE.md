# Market Forecast — coding agent 共用入口

2026-09-26 起採用 [GitHub Agile + Story spec](specs/README.md)，必須連同 docs 入口閱讀。
工作歸屬與逐 Story 遷移以該契約為準；不改安全、角色與派工授權。

`AGENTS.md`、`GEMINI.md` 軟連結到本檔。Codex、Claude Code、Gemini CLI 都讀同一份內容；
不得假定任何工具會自動載入另一工具的 rules。

## 工具入口與必讀順序

Codex 讀 `AGENTS.md`，Claude Code 讀 `CLAUDE.md`，Gemini CLI 讀 `GEMINI.md`。
三者遵守同一套工程規則。Markdown 連結不代表其他工具已自動載入內容；每個執行者必須實際讀完下列文件再工作：

1. [docs/README.md](docs/README.md) 與 [工程規則索引](.claude/rules/00-index.md)（含完整規則鏈）。
2. [產品路線圖](docs/delivery/mvp-phases.md)。
3. [Event Storming 與領域邊界](docs/architecture/event-storming.md)、[Context Map](docs/architecture/context-map.md)。
4. 本次 GitHub Task issue、原生 parent Story 與 Epic，再讀 [共通業務需求及 AC](docs/delivery/requirements-specification.md) 及該 Story 的 `specs/<issue>-<slug>/{spec,plan,progress}.md`。
5. Task 指定的原始碼、契約、鄰近測試與直接失敗證據。

同一 session 已完整讀取且未變的內容可沿用；變更文件重新讀取。派工時列出實際讀取來源，不能用「已遵守規則」代替讀取與驗證。

## 每次需求先同步文件

每次收到需求、補充、更正或需求反轉，先依 [文件規則的需求影響檢查](.claude/rules/80-documentation.md#每次需求的文件影響檢查) 檢查並更新受影響的唯一正式文件，並在原 Task 留下五類影響結果，再繼續受影響工作的規劃、設計、實作或派工；不能只在對話答應。
收尾必須指出實際修改位置與檢查結果，或具體說明為何不需修改。純詢問不擅自變成產品變更。
EventStorming 的分層探索、共同語言、八元素與共同走查也由該規則定義；文件核對不代替使用者確認業務敘事。
每項派工依 [Task-local readiness](.claude/rules/15-execution-strategy.md#task-local-readiness) 核對直接必要前提；整體盤點不作無關 Task 的開工門檻。

## 文件與工作入口

- 產品路線圖只定義交付順序與階段 Exit 成果。
- Event Storming 定義業務事件、流程與 Bounded Context 邊界。
- Context Map 定義 Context 間關係、公開契約與程式 ownership。
- 共通業務規則與 NFR 在 requirements；Story 特有規則及 AC 全文只在 spec.md。
- GitHub type label 與原生 parent/sub-issue 分解 Epic／Story／Task／Bug／Spike；leaf 的有限步驟留 issue body，不再建立 Agile child。Project 唯一保存 Status／Priority／Sprint，plan 保存方案，progress 保存證據與阻塞原因。

業務模型集中在根 `docs/`，Story 三檔集中在根 `specs/`；跨 repo Story 只留一份 owner spec，不得在各 BC 原始碼目錄重建文件樹。工作入口見 [specs 導覽](specs/README.md)。
工程規則只在 `.claude/rules/`；`.agents` 必須是 tracked 相容軟連結（`.agents -> .claude`），不是另一份規則。
同一需求只在一處定義。各 BC、frontend 不再自建產品文件副本；不要恢復已退役的 WI、Context Plan、shared-methodology control plane 或另外一份總計畫。必要 ADR 依 Story 契約，不複製規則。
跨產品同步由各自 Commander 維護本庫，只有共用方法對齊，不覆蓋 sibling 的產品模型與進度。

## 執行拓撲與分工

角色與模型分工、既有具名任務重用、fresh Task Pack 及獨立驗收例外，唯一依 [執行拓撲與派工入口](.claude/rules/15-execution-strategy.md#execution-topology-and-dispatch)；本入口不另定 provider 矩陣。

- Commander 負責產品理解、任務依賴、唯一 Git writer、完整派工、合流與如實回報；不共用另一產品的狀態。
- 規劃／設計與實作由不同角色處理，驗收由獨立驗收 session 執行；不得自我驗收。
- 任務重用與派工依上述唯一拓撲核對適任角色及當次授權；worker 不自行派工。
- 階段、完整派工 prompt、疑問回報與停止條件見 [05-methodology.md](.claude/rules/05-methodology.md)。
- Task-local readiness、Commander continuation 與 GitHub Project Task Status synchronization 見 [15-execution-strategy.md](.claude/rules/15-execution-strategy.md)。
- 測試細則見 [70-testing.md](.claude/rules/70-testing.md)，文件規則見 [80-documentation.md](.claude/rules/80-documentation.md)，操作與 Git 交付規則見 [90-operations.md](.claude/rules/90-operations.md)。

## Market Forecast 不變式

- B50 是另一個 frozen Current-State Momentum product；本 repo 不重新優化 B50，也不把它包裝成 future-return probability。
- Risk Forecast primary target 是未來 H=5 average realized variance；H=20 僅 confirmatory；QLIKE 是 primary loss。
- 先凍結 measurement，再比較 global／market-specific／partial-pooling dynamics；不得看 forecast winner 後反過來挑 sampling frequency。
- 研究 fitting 可由 Python／uv 離線完成；production inference 優先 freeze 成低維 manifest 並回到 TradingView／Pine。
- 薄 apps／厚 libs、無 fallback、`uv run`、tests、ports/adapters 與資料 provenance 的細則以 rules 為準，不能以文件精簡跳過。
- 保留使用者未提交工作。不得自行 stage、commit、restore；live provider、付費／quota market-data、bulk backfill、export、model/universe freeze 或其他有副作用操作必須在 Task 明示授權。
- 基線後每次派工與修改必須指定 Task 分支、base SHA、工作目錄及 Subtask 提交邊界；依 [Git 工作規則](.claude/rules/90-operations.md#task-分支與-subtask-提交) 執行，不在共用 main 混合施工。
- 新文件使用繁體中文；程式識別字與 commit message 使用英文。
