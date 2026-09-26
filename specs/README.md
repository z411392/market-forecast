# Story 規格與交付操作模板

> [!IMPORTANT]
> **CLEAN REBUILD AUTHORIZED（2026-09-09）**：
> 既有 Story 規格（`specs/2-*` 至 `specs/9-*`）為舊版單租戶架構產物，現已封存為歷史參考。
> 新產品之目標架構與生命週期依 [Clean Rebuild 架構與目標產品權威](../docs/architecture/clean-rebuild.md) 執行。

本頁是 GitHub → Story spec／Task／BDD 的操作模板，不依賴桌面附件，也不承載產品 authority。

文件與 GitHub 工作管理的唯一歸屬依 [Rule 80](../.claude/rules/80-documentation.md)；角色、provider/model、dispatch、fresh Task Pack、continuation、Reviewer、Project Status synchronization 依 [Rule 15](../.claude/rules/15-execution-strategy.md#execution-topology-and-dispatch)。本頁不得複製第二套 authority 或 routing policy。

Task-local readiness、Story acceptance 與 Roadmap phase completion 仍分離；禁止以 generic global Design gate 作現行前提。

## 操作導覽

- Story business scenario／專屬 AC：依 Rule 80 建立 `specs/<真實-story-issue-number>-<slug>/spec.md`。
- Story technical design：同目錄 `plan.md`。
- Story meaningful progress／evidence／decisions：同目錄 `progress.md`。
- Epic／Story／Task／Bug／Spike hierarchy：GitHub Issues。
- Status／Priority／Sprint／Views：GitHub Delivery Project；不在本頁另存 workflow state。
- 其他產品／架構文件歸屬一律回 Rule 80，不在本頁重抄。

文件路徑用 lowercase kebab-case；既有 source 命名與 GitHub 特殊路徑不受此規則改寫。
不建 epics／stories／tasks／deliveries 目錄，不為 Epic、Task 或 Spike 建規格資料夾。
Story issue 只連結 spec 的 AC，不保留競爭版本；共通 AC 在 spec 用 ID 與連結引用。

## EventStorming 到驗收：有限流程

輸入：已確認的需求、目標流程、Hot Spots、現有契約與可查驗的程式證據。

1. 從 Big Picture 的業務成果找 Epic 候選；不得將 BC 或 agent 當成 Epic。
2. 從流程取出 Actor／觸發 → Command → 行為 → Event → Policy／例外 → 可觀察終點，形成有獨立價值的 Story 候選。一個 Story 可跨多個 F 流程與 BC。
3. 對每個情境列出成功、拒絕、零結果、失敗、重複與中斷分支；不適用者說明理由。Hot Spot 只有阻止 Ready 且需查證時才成為有時間上限的 Spike；業務裁決仍問使用者。
4. 取得真實 Story issue number 後建立三個文件；spec 中為情境與專屬 AC 編局部穩定 ID，引用全域 AC，不將每張事件卡變成工作項。
5. plan 指定 Context Map 邊界、接口、設計決策、整合點與驗證方法；再以原生 sub-issues 依實作責任建立有限 Task。Analysis／Design／Verify 等是 leaf 內階段，不是第四層 Agile item。
6. 依 [Task-local readiness 唯一規則](../.claude/rules/15-execution-strategy.md#task-local-readiness)核對本 Task 的必要前提；不等待無關 Story／BC／後續 Phase。七條完整判準只由該 rule 維護，不在此複製。Task Ready 不代表 Story accepted 或產品 Phase complete。
7. 具名任務依 Task → parent Story → spec → plan → progress → 直接依賴接手；完整派工 prompt 與 route／ACK 放 Task issue，重要成果由指定唯一 writer 記 progress。不得新開子代理或將 GitHub issue 當成新的 agent session。
8. 工具驗證後由 Independent Reviewer 唯讀驗收，逐 AC 連結實際證據與 PR。必要 Tasks／Bugs 完成、Story AC 通過、必要 PR merged 才可結案。Epic 核對成果，不以 child 數量或事件數量判定。

輸出：可從業務成果追到情境、AC、Task、測試、PR、驗收人的交付鏈；有缺件則留下具體 blocker 與解除條件，Commander 依 [continuation ownership](../.claude/rules/15-execution-strategy.md#commander-continuation-ownership) 路由並收束，不以內部 handoff 結案。文件或 unit test 通過不是產品驗收。

## 操作方法：從需求到可驗收的 GitHub 工作

本流程由 Commander 主持；實際 Architect／Implementer／Reviewer 拓撲、provider/model 與 effort 一律引用 Rule 15，本頁不自行定義。每批限定一個業務成果；bounded work item 結束後控制權返回 Commander scheduler；Commander 依 Portfolio Reconciliation 判斷下一個授權工作；整體執行鏈的終止條件唯一依 [Rule 15 合法 terminal outcome 與 Final-response gate](../.claude/rules/15-execution-strategy.md#合法-terminal-outcome)。worker 有阻擋只停止受影響操作，Commander 依 [continuation ownership](../.claude/rules/15-execution-strategy.md#commander-continuation-ownership) 續推，不無限補文件。

| 步驟 | 輸入 → 實際操作 → 輸出／停止條件 |
|---|---|
| 1 收需求 | 使用者原文與現行規則 → 核對路線、AC、事件／BC、Context Map、工作五類影響 → 在 Story progress 留修改位置或不改理由；產品歧義記共通需求並詢問，不自行裁決。 |
| 2 拼事件敘事 | 已確認需求 → 先按時間串出已發生事件，再補觸發者、命令與因果；走成功、零結果、拒絕、失敗、重複、中斷 → 更新唯一 EventStorming 流程及共同語言。F 編號是流程，不是 BC 或工作編號。 |
| 3 確認流程邊界 | 事件鏈 → 核對 Actor、UI、Command、Aggregate、Event、Policy、External Service、Read Model；以身份及不變條件判斷 BC → 更新必要 Context Map 交接。未解業務敘事需使用者確認，不能以圖畫完代替。 |
| 4 切業務成果 | 路線成果與完整流程 → 建 Epic；切出能獨立展示結果的 Story，允許跨 BC → 真實 Epic／Story Issue 及原生 parent 關係；不按 DTO、事件張數或 agent 數切 Story。 |
| 5 寫驗收 | 每條 Story 情境 → 編 SC 與 AC ID，逐條寫 Given 前置資料、When 一次操作、Then 可觀察結果及禁止副作用 → spec；每項指定正例、反例與證據方法，無法判定通過就不能 Ready。共通規則只引用。 |
| 6 設計與拆工 | spec、既有程式及 Context 契約 → 在 plan 定接口、依賴、整合 owner、驗證方法；依唯一 writer 切 Task／Bug／有期限 Spike → 每個 leaf 有輸入、輸出、exact paths、Done、測試命令及停止點，逐 Subtask 映射 SC／AC、Roadmap phase／exit IDs／effect 與 GWT 正反 oracle。Subtask 用 leaf 內 checklist，不建第四層 Issue。 |
| 7 配置與派工 | 本 Task 的 Ready 前置 → 依 15 readiness owner 判定；每 Issue 恰好一個 type label、原生 parent、所屬 repo Project；完整 prompt 只寫 Task 頂部再投遞 roster 具名任務 → route ACK（中間狀態，非批次完成）。Ready 成立即進對應實作，不追加非必要設計；不建立子代理。 |
| 8 驗證與驗收 | diff 與實際測試結果 → 工具保存命令、exit code、日期、revision；Independent Reviewer 唯讀逐 AC 判定 → progress 證據及 Task 引用。未執行、局部通過、完整通過分開，不以 Issue 已關閉推定 AC 通過。 |
| 9 結案與接續 | AC 判定與相依工作 → 必要修正回原 leaf；必要 PR merged、Tasks 完成且 Story AC 全通過才結 Story → Project 狀態及路線成果回報；前置齊才派下一有限批次，否則記 owner／解除條件。 |

例：手動 ai triage 的情境是「使用者按主文最後更新時間篩選 → 勾選文章 → 提交批次 → 固定提交時最新版完整 retain 結果 → 取得可查閱判斷」。驗收必須同時證明選取時 v1、提交時 v2、提交後 v3 只採 v2，以及未提交時不呼叫 LLM；不是只驗 DTO 欄位存在。共通規則及 AC-V1-07 唯一正文在[需求](../docs/delivery/requirements-specification.md#ac-v1-07)，[Story 6](6-manual-ai-triage/spec.md)只定義局部情境與專屬 AC 並引用它；不可把此篩選當作 AC09 latest／AC10 hot 閱讀排序。

## Roadmap 貢獻與證據

每個現行 Story、Task 及 Subtask 必填 `Roadmap phase`、`Roadmap exit IDs`、`Roadmap effect`。跨 Phase 工作逐 Subtask 明列實際映射，不以整張工作籠統歸類；不承接 Exit 的治理工作填 `None（僅支援）` 並連回所支援的產品階段。

| Roadmap effect | 唯一語義 |
|---|---|
| ADVANCES | 本批實作推進列出的 Exit；未執行時只是預定貢獻，不能記成新產品事實。 |
| PROVES | 本批產出該 Exit 必要驗證及獨立判定；標籤本身不是 PROVEN。 |
| SUPPORT_ONLY | 文件、Design、治理、工具等支援，不擁有或證明產品 Exit。 |
| FUTURE_PHASE | 相對目前產品 Phase 的後續產品工作；不能抵扣目前未成立的 Exit。 |

Exit verdict 使用 `NOT_PROVEN`、`PROVEN` 或有具體依賴的 `BLOCKED`。PROVEN 必須具備必要 implementation revision、正例及反例的實際命令／exit code／日期／結果、適用的中斷恢復與真來源直接證據，以及未參與修改者的獨立審閱結論。必要資料缺一則不能 PROVEN；`NOT_RUN` 的 exit code 填 N/A，禁止填 0。Design、DTO、Done Issue、歷史 scoped PASS、fake／parser 結果不足以證明 scan、每日截止或 durable reopen。
產品 first blocking exit 是依 Roadmap 順序第一個未成立條件；工程 dependency 另列，不能以 P5 或 SUPPORT_ONLY 完成抵扣 P1。任何 BLOCKED 必須列 concrete Task／AC／dependency、影響哪個 Task 及 Exit、為何阻止該 Task 開始或完成、owner 與 clear condition。未知 readiness 如實列未核對，不以整體未設計作 blocker。
Task 可以局部 Ready／Implement／Verify／Accept；Story 必要 AC 全通過才 accepted；Phase 全部必要 Exit 成立才 complete。三者不互相推定。貢獻數、Task／文件／事件／DTO 數與百分比都不是完成證據。

跨 repo 時 parent Story 與三檔只有一份；frontend Task 留在 frontend repo／Project，原生 parent 指向 backend Story。GitHub API 可完成 Issues、labels、parent 與 items；需 UI 的 view／workflow 設定用瀏覽器保存後重讀，不能把未保存畫面算驗證。模板與 spec 未推送時明記本機未發布。

## 三個 Story 文件的必填結構（模板）

`spec.md`：

```markdown
# <Story 名稱>
Story: <真實 Issue URL>
Roadmap phase: <P1–P6 或支援範圍>
Roadmap exit IDs: <精確 ID；治理為 None（僅支援）>
Roadmap effect: <ADVANCES / PROVES / SUPPORT_ONLY / FUTURE_PHASE>
## Problem / outcome
## Scope / non-goals
## EventStorming scenarios
每項含 SC-01、來源流程錨點、Actor、Command、事件因果、Policy／例外、可觀察終點。
## Business rules
引用全域規則；只在此定義該 Story 專屬規則。
## Acceptance criteria
每項含 AC-01、SC-01、共通 AC 引用、Given／When／Then、反例及不可發生的副作用。
## Open questions
產品問題連回共通需求的裁決位置；工程缺件連 plan／progress。
```

`plan.md`：

```markdown
# Plan
## Approach
## Boundaries / dependencies
Context Map 引用、supplier／consumer、整合 owner 與前置契約。
## Decisions
局部技術取捨；跨 Story ADR 只引用。
## Interfaces / files
精確接口及 writable／frozen 路徑；不重抄權威 schema。
## Validation approach
AC ID → 測試層級、oracle、指定命令、預期值、必要人工驗收。
```

`progress.md`：

```markdown
# Progress
Roadmap phase: <當前產品階段；另註本 Story 貢獻範圍>
Roadmap exits affected: <逐 Exit owner 引用；無則 None>
Exit verdicts: <逐 ID 的 PROVEN / NOT_PROVEN / BLOCKED 及原 owner 證據連結>
What became true since previous update: <新增產品事實；若只有支援變更，明記沒有產品事實成立>
First blocking exit: <首個未成立產品 Exit 與 owner；不要填泛用工程 gate>
Remaining conditions preventing phase exit: <仍缺哪些必要產品條件／直接證據>

## Current work
current Task／route、goal、新 facts、具體 blocker、next；保持簡短，不複製 Status／Priority／Sprint。
## Findings
直接來源與發現，區分已證實與假設。
## Decisions
決策引用與適用範圍，不重抄規則。
## Validation
AC ID | 測試／人工證據 | revision／diff 範圍 | 命令、exit code、日期 | 驗收結論與審閱者
未執行明記未執行，不以預期結果當實測。
## Blockers
concrete Task／AC／dependency、阻擋的 Task／Exit、原因、owner、解除條件；沒有則 None。
## Next
下一個直接 owner、Ready／最小缺件及下一動作；是否為原批次 terminal 依 [continuation ownership](../.claude/rules/15-execution-strategy.md#commander-continuation-ownership) 判定，不以 ACK／worker stopped／內部 handoff 結案。
```

progress 第一屏必須依上述六個英文欄名及順序呈現，再放短 Current work 和有界 evidence；不先展示工程歷程。其他 Story 的 Exit 只引用原 owner，不建立競爭 verdict；支援 Story 的總覽只能是有日期的引用快照。

## 新需求的維護

### Task／Subtask 的驗收落實

Story 的 BDD 必須向下分解到每個 Task 及 leaf checklist 的 Subtask，而非只停在 Story 文件。
輸入為 EventStorming 情境、Story SC／AC、共通規則及既有契約；執行以下四步，輸出原 Task 的驗收表與 Story progress 的實證：

1. 定位：每個 Subtask 引用流程錨點、Story SC／AC，說清自己承接哪個命令／結果或支援哪段交付；技術／文件工作不虛構領域事件。
2. 定義：寫 Given 固定資料／前置狀態、When 一次操作、Then 可觀察結果及禁止副作用；列正例、反例與適用的零結果／重複／失敗／中斷。不適用分支附理由，不重抄或更改共通業務規則。
3. 凍結：指定測試層級、exact oracle、命令或有限人工步驟、預期值、驗收人及本批不能證明的範圍。缺追溯、可判定 GWT 或 oracle，不得 Ready；完整 prompt 必須附此映射。
4. 驗收：實作遵循 RED→GREEN→Refactor；文件／設計工作用內容與追溯驗證，不造假 RED。逐項記實際 revision、命令／結果、正反證據及未執行項；必要驗收未通過不得 Done。按 Subtask commit，commit 或測試 exit 0 本身不代替獨立驗收。bounded work item 結束後控制權返回 Commander scheduler；Commander 依 Portfolio Reconciliation 判斷下一個授權工作；整體執行鏈的終止條件唯一依 [Rule 15 合法 terminal outcome 與 Final-response gate](../.claude/rules/15-execution-strategy.md#合法-terminal-outcome)。

原 Task 使用以下欄位，不另建驗收文件庫：

| Subtask | ES 情境錨點／Story SC／AC | Roadmap phase／exit IDs／effect | Given／When／Then | 正例／反例／禁止副作用 | Oracle／命令／預期值 | revision／實證／驗收人 |
|---|---|---|---|---|---|---|

操作細節依 [測試規則](../.claude/rules/70-testing.md#tasksubtask-的-eventstorming-與-bdd-驗收)。產品級完整流程的通過仍須 Story AC 審收，不能把局部 helper、DTO 或檔案驗證相加當端到端成功。

Git 交付：initial commit 基線之後，先按真實 Task 開 `codex/<task-id>-<slug>` 分支再修改或派工；leaf 內每個 Subtask 通過指定驗證後獨立 commit，附 Task／Subtask ID。完整 prompt 指定 owner、integration owner、branch、exact writable／frozen、GWT 正反例、禁止副作用、命令／預期結果、Done 與停止條件，且必須有明示 Git 授權；不混入其他工作，不自行 force-push。這不新增第四層 Issue；局部 readiness 依 15 唯一規則。共用 checkout 只能有一個 writer，不並行切分支；worker route 完成後返回 Commander 依 Portfolio Reconciliation 續派，不讓 Task type 隱含 Commander stop。

## 有限歷史保全與清理

輸入是不可變備份、舊檔 exact revision／行範圍和現行唯一 owner。刪除 transcript 前，先逐範圍映射到 surviving canonical facts 的檔案／錨點，或明列 KEEP；無法證明等價的範圍一律 KEEP。將完整已接受設計放 plan、局部 SC／AC 放 spec、失敗→修正→通過及安全恢復收據放 progress；只留摘要不等於完整設計已保全，NOT_RUN、deadline、failure semantics 不可掉落。比對通過、獨立 review 及精確授權俱全才刪，完成本批即停。
清理 branch 前逐 remote 列出完整 refs 與 SHA、review 唯一 commits／未合流工作、備份可達性及 exact deletion allowlist；root／initial commit 不是全歷史備份，frontend local main 不等於 remote main。保留 initial、不可變 backup 及所有非 allowlist 分支；allowlist 空就刪除零支，不自動把舊分支整支合回。不得回滾、reset、覆蓋 dirty work 或把驗證缺口寫成完成。

跨 repo Story 必須指定唯一 spec／plan／progress 所屬 repository；另一 repo 的 Issues 與導覽引用該正式位置，
只管理自己有權實作的工作，不複製第二套 Story AC。各 repo 仍各有一個 Delivery，不將跨 repo 文件集中誤解為共用看板或共同 writer。

每次需求仍做五類影響檢查：路線、業務 AC、事件／BC、Context Map、工作分解。
已遷移 Story 的專屬 AC 更新 spec、實作影響更新 plan、檢查結果與證據更新 progress；
跨 Story 規則留原共通需求。Task issue 連結這次差異，先同步前提再派工。
同一 Story 多位執行者回報到各自 Issue，由 Commander 或明示的唯一 writer 合入 progress，避免搶寫。

## 遷移與遠端啟用邊界

本機表示方式與模板已建立；使用者後續已授權遠端配置與 Story 遷移。
本 repository 的五個 `type/*` labels 已建立並讀回確認。
後續確認 #2／#3 屬 Thesiscope 前後端；本案專屬 [Delivery #4](https://github.com/users/z411392/projects/4)
已連結 Market Forecast，Status／Priority／兩週 Sprint 欄位已建立。Epic #1 → Story #2–#8 使用原生父子關係，
Story #4 → Task #9 為第一張設計交接工作。各 Story 已有真實編號的初始三檔，完整證據搬移與 Ready 審查尚未完成。
Views、auto-add 與預設 repository 設定仍待核對；未建立 PR 或推送本地模板／spec，不能宣稱完整 GitHub 配置完成。
2026-09-08 唯讀 `gh issue list --repo z411392/market-forecast --limit 30 --json number,title,url` 返回空清單；
這只證明查詢時沒有開啟的 Issues，不推論沒有歷史 Issues 或 Project。

1. 遠端寫入獲授權後，先核對既有 Project、labels 與所有狀態 Issues，避免重複建立。
2. 核對每 repo 一個 Delivery：Status 為 Backlog／Ready／In Progress／Review／Blocked／Done，Priority 為 P0–P3，Sprint 為兩週；配置 Delivery Board、Work Breakdown、Current Sprint、Roadmap 與 issue auto-add。實際建成才記驗證證據。
3. 逐 Story 建原生階層並取得號碼，按本頁結構搬移有效 spec／plan／evidence；保持舊 ID 到真實 Issue 的追溯，不機械複製所有歷史 phase。
4. 檢查引用與證據後，在舊工作分解該 Story 位置只留下遷移指標；其後只寫新 owner。不雙寫進度，也不提前刪除尚未搬移的證據。
5. 全部切換後舊工作分解退為入口。未切換的既有 Task 暫依舊執行區塊收件；不得因此新增整棵舊式 Subtask 層級。

尚未取得真實 Issue number 的候選只留既有工作分解，不使用假號碼／本地 T-ID 冒充 Story 目錄。
已送出的有限 design 回報可依原 route 收件；格式遷移不授予新操作權，也不使過期 WI 路徑重新有效。歷史 global-gate 文字不作 current authority；readiness 只依 [15 的 Task-local 規則](../.claude/rules/15-execution-strategy.md#task-local-readiness)。rules 以 tracked 檔案交付，本機 commit 與遠端發布分開記錄於原 Task；未 push／核對 remote ref 前不得宣稱已發布。
