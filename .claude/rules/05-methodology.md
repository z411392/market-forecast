# 有限工作與派工

工作載體依 [Story 規格與交付契約](../../specs/README.md) 逐 Story 切換。
已切換時，下文 Task 執行區塊指 GitHub Task issue，Subtask 指 leaf 內有限操作，不新增第四層 Agile issue；
phase／route 是執行證據，不是另一套 Project Status。先讀 parent Story 的 spec、plan、progress 才派工。
未切換工作保持原 route 的有限收件，不因改格式自動進入下一 phase。

## 輸入、輸出與唯一記錄

輸入：使用者需求、現行業務 AC、owner Context、既有程式／測試證據。
輸出：有證據的答案，或一個 Task 的 DONE／RETURNED／BLOCKED。
工作記錄直接放在該 Task 的執行區塊，不另建 WI、phase 文件、recovery chain 或狀態庫。

每次收到新增需求、補充或更正，先依
[文件規則的需求影響檢查](80-documentation.md#每次需求的文件影響檢查) 同步必要文件，再承接以下有限 phase；
本檔不另定一套文件更新流程。

## 角色與執行拓撲

本產品由一位 Commander 接收需求、確認 owner／scope／依賴、派工、接收回報、更新狀態與結案。

角色、模型分工、既有具名任務重用、fresh Task Pack 與獨立驗收例外，唯一依 [執行拓撲與派工入口](15-execution-strategy.md#execution-topology-and-dispatch)；本檔不另定 provider 矩陣。

Product Owner／Product-Governance Coordinator／Commander 的控制面責任邊界亦唯一引用 Rule 15；本檔只定義有限工作生命週期，不建立第二套 routing authority。Product / Governance Coordinator 依 Product Owner 明示授權 materialize product-level Issue authority 後，Commander 的下一步是 fresh-read 並 reconcile；不是覆寫該 authority，也不是把 Coordinator 當 Implementer／Reviewer。

同一路徑同時只有一位 writer；Implementer 不派工、不修改狀態或自己的外部驗收 oracle。
身份清冊見 root `.claude/roster.json`，僅為上述唯一規則的非權威機器投影；派工須依該規則核對既有任務適任性與當次授權。

## Git 交付規則

Git 分支、Subtask 提交與整合邊界以 [90-operations.md](90-operations.md#task-分支與-subtask-提交) 為準：
基線整理完成後，所有新派工與修改先綁定真實 Task，使用 `codex/<task-id>-<slug>` 專屬分支，不在 main 混合施工。每個 Subtask 完成指定驗證後獨立 commit；訊息使用英文，引用真實 Issue 與驗收證據。預設由 Commander stage／commit，worker 不得自行 stage、commit 或 restore。

## 有限階段（執行順序）

1. **Intake**：Commander 用明確需求定位一個 owner，選既有或建立 Task；列出輸入、輸出、依賴與範圍。
2. **Analysis**：由 Design session 只讀 owner 程式與證據，產出 AC mapping、缺口與產品疑問；有疑問即回報。
3. **Clarify**：技術事實由證據回答；會改產品行為的選擇由 Commander 問使用者，取得裁決前不猜。
4. **Plan**：由 Design session 把已釐清工作拆成有限 owner-local Subtasks，寫清每項輸入、輸出、依賴及停止點。
5. **Design**：由 Design session 凍結 ports／DTO／parser、正反 oracle、exact writable／frozen paths、命令與 Done Contract。
6. **Implement**：只在 [Task-local readiness](15-execution-strategy.md#task-local-readiness) 成立且授權具備後依[執行拓撲](15-execution-strategy.md#execution-topology-and-dispatch)派工給適任 Implementer，依 RED → GREEN → Refactor 工作。
7. **Verify**：工具串行執行指定命令，保存命令、exit code、時間與安全結果；focused PASS 不能冒稱完整 gate PASS。
8. **Accept**：由獨立 Review/Accept session 唯讀比對 AC、diff 與工具證據；不能自己補改使其通過。
9. **Closeout**：輸出為 bounded slice 的結果與 evidence；Closeout 不結束 Commander execution chain。Closeout 後若 parent execution 尚可前進，立即依 [Commander scheduler loop](15-execution-strategy.md#commander-scheduler-loop) 重新排程續推；只有在 [Final-response gate](15-execution-strategy.md#commander-final-response-gate) 合法成立時，Commander 才能進入 terminal。禁止將 Closeout 隱含為「回報後停止等待使用者」。

步驟可以在同一 Task 內簡短記錄，但不能把 Clarify、Plan、Design 混成「開始做」。每次 Analysis／Plan／Design／Review 回報後，Commander 立即依 [15](15-execution-strategy.md#task-local-readiness) 核對本 Task；全部成立且已授權即派有限實作，不追加非必要 Design；否則只補最小直接缺口。Task 開始、Story 必要 AC 驗收、Roadmap 全部必要 Exit 完成不得混稱。
只讀回答在 Analysis 得到有證據結論後停止。純文件維護使用文字／連結／範圍 oracle，不虛構程式 RED。
使用者明示的跨庫文件改寫可由 Commander 作唯一文件 writer；不因此取得產品程式實作權。

## 派工 prompt 必須完整

Commander 將下列內容寫在 Task 的執行區塊，再原文投遞目標；不可只說「接著做」「按 rules」：

- Task／Subtask ID、owner、目標角色、本次唯一 phase、指定模型與工具。
- 使用者目標、引用的 AC、已決策事項、non-goals 及尚未解除的 blocker。
- Task／Subtask 的 EventStorming 情境→Story SC／AC→BDD Given／When／Then→oracle／驗收證據映射，含正反例、禁止副作用與未證明範圍；具體門檻依 specs/README.md「Task／Subtask 的驗收落實」及 70-testing，不只寫「使用 BDD」。
- 原 Task 的[文件影響檢查](80-documentation.md#每次需求的文件影響檢查)結果及本次需同步／維持的唯一文件引用；接手者本人核對，不只承諾稍後更新。
- 每一份必讀規則的 exact path、owner 文件、契約與直接 evidence；要求完整讀取，不委派別人代讀。
- current authority、exact branch／base SHA／worktree、Subtask 提交邊界、exact writable／frozen paths、既有 dirty work、依賴及唯一 writer；每次依[執行拓撲](15-execution-strategy.md#execution-topology-and-dispatch)建立 fresh Task Pack。
- 有限操作順序、輸入／輸出、指定測試命令與預期值、授權副作用及 worker 返回條件（ROUTE_RETURN_CONDITION）。
- 回報格式：route ID、已讀檔案、差異／證據、第一個 blocker、建議下一步；worker 產生 report 後停止其本次操作；Commander 依 [continuation ownership](15-execution-strategy.md#commander-continuation-ownership) 消費結果並續推原批次。

只有實際投遞且同 route 收到 ROUTE_ACK 才記 IN_PROGRESS；讀取承諾本身不是遵循證據。
工作者必須回報與產品或契約有關的疑問，不能私下補完假設。
下一 phase 已在核准有限順序且前置成立時直接續送，不把每一步都交使用者批准。
每次收到依執行拓撲派工的具名任務回報，Commander 必須核對 route／readset／完整輸出與驗收邊界，更新原 Task，辨識是否有新的業務裁決或工程缺件；前置已齊就續推下一步，未齊只派不受阻的已授權工作。不得只轉述 ACK 就停下，也不得為了續派而跳過審收或重問已決事項。

## 跨專案協作訊息

使用者要求同步跨專案流程／docs 時，輸入為兩邊現行入口、規則、文件歸屬及實際差異。
先比對共用方法與產品特例，再由各自 Commander 修改本庫；送出需對方處理的精確項目、理由、
必要來源、可寫／禁止範圍、驗證及停止點。回覆後核對實際差異，一輪已處理或留下明確缺件即停止。
輸出是已採用的改善、刻意保留的產品差異與驗證證據，不是兩份檔案必須逐字相同。
不得以同步為由把某產品的 BC、來源技術、資料庫路徑、測試命令或進度套到另一產品。

跨專案訊息必須有收件者需要處理的具體審閱、修改、相依缺件或待回答問題，並附必要輸入、預期輸出與停止點。
只傳達與該事項有關的差異；不把本產品的新需求、裁決或進度當作例行公告送給另一專案的 Commander。
沒有需對方採取的行動就不送；使用者要求停止無用通知時，在本案規則／原 Task 記錄即可，不再傳「已停止通知」。
既有具體 peer review 的授權不因此取消，但不能藉該授權持續送無需處理的更新，也不把本案規則套到 sibling 產品。

## 停止與回報

本 Task 的 owner 不唯一、直接必要產品決策未定、直接必要依賴未成立、writer 衝突或缺可驗證契約時，依 [15 的 BLOCKED 收據](15-execution-strategy.md#task-local-readiness) 回報 exact 被阻擋操作、因果證據與解除條件；不以無關工作阻擋。
實作缺契約或 frozen oracle 有問題，回 DESIGN_BLOCKED；越出 owner scope，回 SCOPE_EXPANSION_REQUIRED。
同一根因最多三次 focused 嘗試；仍失敗就回 Design session 做一次根因修正設計，不能串出無限續篇。
需要新產品決策或新權限時問使用者；沒有新權限就停止，不以自行新增任務消解限制。

## 三種工具的入口

Root AGENTS.md／CLAUDE.md／GEMINI.md 使用同一內容，入口明示完整讀取 rules，不依賴跨工具隱含載入。
工具官方行為依 [Codex AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md)、
[Claude Code memory](https://code.claude.com/docs/en/memory)、
[Gemini CLI GEMINI.md](https://geminicli.com/docs/cli/gemini-md/)。
靜態連結與內容檢查只能證明入口一致；真實 CLI smoke 需另外授權，不可冒稱已執行。
