# 協作與執行策略

核心目標不是累積完成項目，而是用與成果壽命相稱的成本，持續縮短與最終目標的距離。每一輪都要能回答：
這一步讓目標更近了、沒有變，還是被阻塞了，以及原因。

## 規則優先順序

專案規則、測試要求與文件合約優先。本檔不能被當成跳過必要測試、文件或完成定義的授權。

流程最佳化與既有規則衝突時：

1. 指出衝突的兩條要求。
2. 採取成本最低但仍合規的做法。
3. 若仍無法兼容，交由使用者決定，不自行採用較寬鬆的規則。

測試細節以 [70-testing.md](70-testing.md) 為準，文件歸屬以 [80-documentation.md](80-documentation.md) 為準。
本檔不重複定義它們。

## 每輪開始前

先確認三件事：

1. 問題已被重現，或已有足以採取行動的證據。
2. 問題屬於技術修正，還是產品、範圍、架構或權限決策。
3. 預定動作會讓最終目標前進多少，以及如何判定。

不得根據過時文件、片段紀錄或表面現象直接派工。需要使用者決定的問題，最遲在第一輪查證後提出，
不能連續繞路後才回報。

連續兩個改動都沒有帶來目標淨進度時，停止增加修正，重新檢查方法；若真正的阻塞是決策，直接提出決策，
不用更多技術工作掩蓋它。

<a id="task-local-implementation-readiness"></a>
<a id="task-local-readiness"></a>
## Task-local implementation readiness

輸入：一個 exact Task／Subtask 或明示有限 slice、其 parent Story 的相關 SC／AC、實際 Roadmap phase／Exit，以及有效 Design、直接必要依賴、操作授權與 writer 證據。
輸出：一次七項收據及 `READY_FOR_IMPLEMENTATION` 或 `NOT_READY` 及未滿足項；不是整個 Story 或產品階段的完成判定。本節是 Task-local、不是 project-global 的實作準備判準，適用 Commander、Planner、Designer、Implementer、Reviewer；完整規則只在本節維護，其他文件只引用。

Commander 每次收到 Analysis／Plan／Design／Review 回報，立即回答 `Does this Task now satisfy READY_FOR_IMPLEMENTATION?`，並有限地逐項核對下表。每項只能填 `PROVEN`、`MISSING` 或 `NOT_EXAMINED`，附直接來源與適用範圍；未查不能猜成通過：

| 檢查 | PROVEN 所需直接證據 |
|---|---|
| 1．相關情境與 AC | 這個 Task 實際服務的 Story scenario／AC 清楚，有可判定的正反結果。 |
| 2．產品成果位置 | 實際 Roadmap phase／Exit 及本 Task 適用的條件明確，不要求整個 Exit 先完成；支援工作明示 Exit=None、SUPPORT_ONLY，不虛構產品 Exit。 |
| 3．直接必要依賴 | 只檢查這項操作確實需要的依賴；需要契約就查契約，需要 runtime 就查實作，不要求整個上游 Task／Story Done。 |
| 4．產品決策 | 沒有尚未決定且會影響本 Task 的產品規則。 |
| 5．可施工邊界 | 適用接口／契約、exact writable／frozen paths、失敗語義、正反外部 oracle、命令與預期結果均已固定。 |
| 6．實作者責任 | 實作者不需代做產品選擇或重新設計上游；必要設計已有唯一有效來源。 |
| 7．派工責任 | 唯一 writer、integration owner、授權範圍與停止條件清楚。 |

七項全部 PROVEN 即回答 `YES — READY_FOR_IMPLEMENTATION`，立即停止非必要 Analysis／Plan／Design，不得另加第八條「再多做設計」或以更多分析設計延後。已有有效授權時，Commander 依[執行拓撲](#execution-topology-and-dispatch)交由適任 Implementer 有限實作，再執行 Verify 與 independent Accept；沒有授權仍須停在授權邊界，不以 READY 自動擴權。任一項缺件或未查即回答 `NO — NOT_READY`，只列解除該 Task 所需的最小直接缺口，不另啟無界盤點。需求變更只重查受影響項目，其他證據仍依其有效範圍保留。

<a id="blocked-traceability"></a>
### 跨階段 blocker 追溯

若以 BLOCKED 阻擋工作，收據必須逐項寫明：

- blocked Task／Subtask；
- exact blocking Task、contract、AC 或未決 decision；
- 受影響的 Roadmap phase／Exit／具體 condition；SUPPORT_ONLY 填 Exit=None，另列本 Task 的直接必要條件，不捏造產品 Exit blocker；
- 被阻止的是哪個開始／完成操作，以及直接因果理由；
- missing evidence；
- release owner；
- 可觀察的 clear condition；
- 最小下一步及停止條件。

無關的同 Phase Tasks、其他 Story／BC、後續 Phase、SUPPORT_ONLY／FUTURE_PHASE 或整體盤點缺件，不能阻擋本 Task；只有已證實會阻止本項操作的直接必要 dependency 才能作為依賴 blocker。禁止要求全案、全板塊或所有相關 Story 的 Design 全部完成才可開始一般實作；不得以 `global design gate not cleared`、`全案設計尚未完成`、`全板塊尚未收斂` 作泛用 blocker。整體盤點／設計仍可按使用者指定範圍有限執行，但不能作為無直接依賴之局部實作的額外開工門檻。

三種 gate 分開：Task-local readiness 決定能否開始本項實作；Story acceptance 仍要求其全部必要 AC 的實作與獨立驗收；Roadmap phase completion 仍要求全部必要 Exit 已證明。因此 A Task READY、B Task BLOCKED、C Task 尚在 Design 可同時成立，而產品 phase 仍 NOT_PROVEN。局部 READY 不降低 TDD、已凍結的外部 oracle、隱私、無 fallback、必要 durable reopen 或獨立 Accept 標準。

本輪若是限定治理／文件且完成後 STOP，七項核對不授權續派產品。需求影響紀錄依 [文件規則](80-documentation.md#每次需求的文件影響檢查)，測試與驗收依 [測試規則](70-testing.md)。

<a id="execution-topology-and-dispatch"></a>
## 執行拓撲與派工入口

本節是執行拓撲與模型分工的唯一權威（2026-09-20 Product Owner 裁決正式切換為角色共享具名任務與動態 Effort 政策）；入口與 rule05 只引用本節，`.claude/roster.json` 僅為非權威（noncanonical）機器投影。本次遷移中，歷史 task receipts 與 identities 完整保留不變、Context 與 product ownership 維持不變，而 current routing 則依本次決策指向新的 shared role identity。其他文件只能引用，不得複製出第二份完整 routing authority。`.claude/roster.json` 因既有治理測試合約鎖定其 execution_policy.model 為 `gpt-6-astra`，僅作為機器投影，不代表現行真實路由；現行真實派工以本節正式模型拓撲為唯一權威。

### Control-plane responsibility boundary

本節同時是 Product Owner、Product / Governance Coordinator、Commander、Architect、Implementer、Reviewer 的責任邊界與控制面順序唯一權威。產品語意仍由對應 Product Authority 保存；本節只規範誰能把既有 authority 轉成治理／執行動作。

- Product Owner：負責產品方向、scope、authority 與必須由人類裁決的產品決策。Product Owner 可明示授權 Product / Governance Coordinator 將已做出的產品決策 materialize 到 GitHub 與產品層導航。
- Product / Governance Coordinator：Issue-level control-plane role，不是 engineering worker。在 Product Owner 明示授權下，可 create/update/close GitHub Issues、更新 Epic／Story navigation、建立 successor hierarchy、加入 supersession／scope-transfer receipt、將已批准 Product Design authority materialize 到 GitHub，並維護 product-level roadmap truth。不得假造 implementation receipt、不得自行給 engineering `ACCEPT`、不得把 planning 當 implementation complete、不得自行配置 Architect／Reviewer model budget，也不得取代 Commander 的 execution ownership。除非未來成為可 dispatch runtime agent，否則不加入 `.claude/roster.json`。
- Commander：repo 唯一 execution control plane，負責 fresh-read current Product Authority、task-local readiness、routing、dispatch、continuation、integration、repo docs migration、result consumption，以及 GitHub Project execution Status synchronization + readback。若 Product / Governance Coordinator 已合法更新 product-level Issues，Commander 必須 `fresh-read → reconcile`；不得以舊 execution context 覆寫外部合法 product authority，也不得自行發明 Product Owner 決策。
- Architect：跨 BC 共用 analysis／planning／architecture／design／root cause／contract-oracle role；不做 mechanical implementation，不驗收自己設計的 candidate。
- Implementer：在 frozen contract 與 writer ownership 內做有限 implementation；不取得 product authority，不 self-review。
- Reviewer：跨 BC 共用獨立驗收角色；必須 READ_ONLY、NON_INTERACTIVE、NO_WRITE_AUTHORITY，依 exact candidate 與 current authority 驗證，不修自己的 finding。

正式控制面順序：

```text
Product Owner decision
        ↓
Product Design authority
        ↓
durable GitHub product authority
        ↓
Commander fresh-read / reconciliation
        ↓
Architect design（僅直接必要時）
        ↓
Implementer implementation
        ↓
deterministic Verify
        ↓
independent Reviewer Accept
        ↓
Commander integration
        ↓
GitHub Project Status readback
```

GitHub Project Status 只能投影 execution workflow；不得反向成為 Product Authority、Story acceptance、Roadmap Exit 或 Product GO。

### 拓撲決策理由與核心原則

**問題（舊策略）**：
舊策略採用「一個 Bounded Context × 一個 Astra planning/design task」，會造成每個具名任務反覆在 session 中建立大量共通 context：
- architecture rules 與分層邊界
- Ports & Adapters / DDD 慣例
- Product Authority 與決策鏈
- Task Pack conventions
- Git / docs governance
- cross-BC contracts
- review standards
隨著 Bounded Context 數量增加，相同的 context 與 Astra quota 被近似重複支付，造成資源巨大浪費與維護負擔。

**不採用另一個極端**：
我們亦不採用「整個 Market Forecast 只有一個全能 Super Agent」，因為這會造成：
- Design 與 Review 的角色污染（Role Contamination）
- 提案草案（proposal）與正式定案（accepted truth）混淆
- 舊 candidate 與 current main 混淆
- 獨立驗收的身分與客觀性（independent review identity）消失
- 長期對話 context 嚴重污染

**採納模型（Chosen Model）**：
持久存在的是**角色（Role）**，而不是 **Bounded Context**。因此：
- 1 個跨 BC 共用的 Architect 具名任務
- 1 個跨 BC 共用的 Reviewer 具名任務
- Bounded Context 的隔離改由每次派工的 **fresh Task Pack** 嚴格提供。
- Persistent task context 只可作為背景參考，永遠不是 current authority。
- 每一輪派工仍必須 fresh-read：
  - current main SHA
  - exact Issue / Story / AC
  - current Product Authority
  - relevant BC files
  - direct dependencies
  - frozen paths
  - current candidate

**關鍵原則**：
- `Role identity is persistent.`
- `BC/task scope is ephemeral and supplied by the Task Pack.`

### 正式模型拓撲與規範角色

| 角色／活動 | Runtime 與模型／effort | 責任邊界 |
|---|---|---|
| Commander | Antigravity / Agy (Gemini 3.8 Flash) | 唯一長住 control plane，持有產品理解、任務依賴、readiness、routing、continuation、Git integration、current product state、Task 建立與成果消費；不設計、不實作、不做獨立 Accept。 |
| Implementation、test authoring、mechanical refactor、bugfix | Antigravity / Agy (Gemini 3.8 Flash) | 依固定契約有限實作；context-local 保持 writer ownership 與 worktree 隔離；debug 指已定位問題的修復，不包含根因分析。 |
| Architect（跨 BC 共用） | Codex (OpenAI Codex gpt-6-astra, Medium 預設 / High 門檻升級) | 有界架構專家，跨所有 BC 共用具名任務（`01a0bf82-2f55-7152-82e0-71a276cb8087`），負責 analysis、planning、architecture、design、root-cause reasoning、technical option evaluation、Task decomposition、oracle design、current-main retriage。只補本 Task 直接必要架構缺口，不成為第二個長住 Commander，不擔任一般 mechanical implementation。 |
| Reviewer（跨 BC 共用） | Codex (OpenAI Codex gpt-6-astra, Medium 一般驗證預設 / High 獨立驗收門檻) | 獨立審查者，跨所有 BC 共用具名任務（`01a0bf82-79e6-7e70-a2d6-f528485ff252`），依角色隔離與當次授權核對證據；全面核對 production、tests、authority 與 AC，給出明確 `VERDICT: ACCEPT` 或 `VERDICT: REJECT`，以及 ready-for-external-review signoff。 |

#### 規範角色定義

1. **Architect（架構師）**：
   - 具名任務：`Market Forecast｜Architect｜分析・規劃・設計`
   - Runtime：**Codex**（OpenAI Codex `gpt-6-astra`），跨所有 Bounded Context 共用真實 persistent task `01a0bf82-2f55-7152-82e0-71a276cb8087`。
   - 歷史 Antigravity Architect subagent（`9d69eb51-45db-47a8-aafe-ee865a6f2439`）已標記為 `LEGACY_NO_NEW_DISPATCH`；歷史收據有效，但禁止向 Agy 續派 Architect 任務。
   - 責任：analysis、planning、architecture、design、root cause、technical option evaluation、external capability analysis、Task-local architecture contract、positive / negative oracle design、current-main retriage。
   - 禁止：mechanical implementation、candidate implementation、independent acceptance of a candidate it designed、whole-project continuation ownership。
2. **Reviewer（審查者）**：
   - 具名任務：`Market Forecast｜Reviewer｜驗證・獨立驗收`
   - Runtime：**Codex**（OpenAI Codex `gpt-6-astra`），跨所有 Bounded Context 共用真實 persistent task `01a0bf82-79e6-7e70-a2d6-f528485ff252`。
   - 歷史 Antigravity Reviewer subagents（`ccd0fbdb-3dee-4ba2-9264-4125b487f5b2` / `859fcbe8-5891-40e0-84ed-15dc6e29cdee`）已標記為 `LEGACY_NO_NEW_DISPATCH`；歷史收據有效，但禁止向 Agy 續派 Reviewer 任務。
   - 責任：verification reasoning、candidate diff、architecture compliance、Product Authority review、integration review、independent acceptance、regression boundary analysis、ready-for-external-review signoff。
   - 禁止：implementation、fixing candidate under review、acting as Architect for the same candidate、becoming Commander。Reviewer 必須與 Architect / Implementer 保持嚴格 role isolation。


<a id="independent-reviewer-runtime-isolation"></a>
### Independent Reviewer runtime isolation

Independent Review／Accept／Forensic Audit 的角色隔離必須由 runtime 權限實際強制，不能只靠 prompt 文字要求「不要修改」。

1. Reviewer 預設只有 read authority：
   - 可讀 source、tests、authority、candidate diff、logs、manifest 與 evidence；
   - 可執行不改變受驗收現場的 deterministic verification；
   - 不得修改 production／test／evidence 檔案，不得 commit、push、merge、改 Issue／PR／Project，也不得使用外部 write action 修正 candidate；
   - finding 只能回交 Commander／Implementer 修正，Reviewer 自己修正後再驗收不構成 independent acceptance。
2. Codex CLI 執行 Independent Reviewer 時，若本機 runtime 支援 sandbox，規範的非互動唯讀形式為：
   ```bash
   codex --sandbox read-only --ask-for-approval never exec ...
   ```
   重用既有 reviewer session 時使用：
   ```bash
   codex --sandbox read-only --ask-for-approval never exec resume <reviewer-session-id> ...
   ```
   sandbox／approval 旗標放在 top-level `codex` 後、`exec` 前，避免不同 CLI 版本對 `exec` 子命令旗標解析不一致。
3. Independent Reviewer 禁止使用：
   - `--dangerously-bypass-approvals-and-sandbox`／`--yolo`
   - `--sandbox danger-full-access`
   - `--sandbox workspace-write`
   - 任何等價的 unrestricted write mode。
   Reviewer prompt 即使明示「唯讀」也不能替代 runtime sandbox。
4. Implementer 與 Reviewer 權限分離：
   - Implementer 依 writer ownership 可使用受控的 workspace-write；
   - Reviewer 保持 read-only；
   - Architect／analysis 是否需要 write 依該有限工作另定，但不得用 Reviewer 身分取得 write authority。
5. 若 read-only sandbox 因平台／容器限制無法執行必要驗證，不得靜默降級到 dangerous bypass。Commander 必須改用可提供唯讀保證的 worktree／mount／container／runtime，或記錄 `REVIEW_RUNTIME_ISOLATION_UNAVAILABLE`；在隔離未恢復前，不得把該次執行當 final independent ACCEPT。
6. 若本規則生效時已有 elevated／unrestricted Reviewer 正在執行，不因治理規則更新本身強制 kill 已接近完成的 run；run 結束後必須先做 contamination check，至少包含：
   - `git status --porcelain`
   - `git diff --`
   - reviewed candidate SHA／ref 未被 Reviewer 移動
   - Task 指定的關鍵 evidence／manifest hash 未改變。
   任一污染、未能證明 clean，或 reviewed bytes 與原 candidate 不同，該 verdict 不得作 final acceptance，必須以 read-only Reviewer 對 clean exact candidate 重跑。
7. Exact-candidate receipt：
   - final Reviewer 收據必須列出每個受驗收 repository 的 exact base SHA 與 exact reviewed SHA；
   - 多 repo delivery 必須逐 repo 記錄，不得只寫 branch name；
   - review 期間任一 candidate head 改變，舊 verdict 對新 SHA 自動失效；
   - 收據另記 Reviewer runtime mode（至少 `read-only`）與實際 verification commands／results。
8. Output artifact 可由 CLI 的 `-o`／等價 host-side capture 保存到 repo 外；這不授權 agent 寫入受驗收 worktree。若 output capture 本身在該 runtime 受 sandbox 限制，改用 host-side stdout redirection／CLI-supported capture，不放寬 Reviewer worktree 權限。

此節只規範 Independent Reviewer 的 runtime isolation，不改 Task-local Ready、產品 AC、測試門檻、Git integration authority 或 Commander continuation ownership。

### 動態 Effort 政策與升級規則

歷史 Astra 派工模型為 `gpt-6-astra low` 與 `gpt-6-astra high`。從現在起，Codex Astra 僅使用 `Medium` 與 `High`，不再使用 `Low`（亦不得使用 xhigh / max / ultra 等非標準 effort）。一般 mechanical implementation 由 Gemini 3.8 Flash 承接。歷史已完成之 Astra / Grok / Claude receipts 全部完整保留有效，不得竄改歷史收據。嚴禁合成或捏造假 Codex ID，所有 Codex 派工必須透過真實 Codex 工具（`codex exec`）執行並取得真實收據。

1. **Medium = DEFAULT（預設）**：
   以下分析與驗收工作一律預設為 Medium：
   - fresh-read / bounded analysis
   - ordinary planning
   - ordinary architecture analysis
   - API / schema review
   - BC-local design
   - root-cause exploration
   - Task decomposition
   - test / oracle planning
   - ordinary candidate diff
   - ordinary validation
   - regression review
   概念上應占大多數 Astra 工作，避免無謂消耗 high-effort quota。
2. **High = GATE / ESCALATION（門檻與升級）**：
   High 不拿來從零做大範圍全庫探索。推薦工作流為：
   `Medium exploration` → `bounded candidate` → `High gate`。
   High 嚴格限定於以下關鍵門檻與複雜度升級：
   - `CROSS_BC_CONTRACT_GATE`：跨 BC 契約與邊界決策
   - `CONCURRENCY_CORRECTNESS_GATE`：高難度並行、分散式鎖或交易語義正確性
   - `SECURITY_TENANCY_GATE`：租戶隔離、隱私法規或安全性邊界
   - `MIGRATION_GATE`：具不可逆後果的資料庫或架構遷移
   - `FINAL_ARCHITECTURE_FREEZE`：架構凍結或最終架構審查門檻
   - `FINAL_INDEPENDENT_ACCEPT`：最終獨立 ACCEPT / REJECT 驗收門檻（假陽性接受成本高時）
   - `MEDIUM_UNRESOLVED_CONFLICT`：Medium 分析結論衝突需進行權威仲裁
   - 或具實質後果的 Product Authority 歧義解析。
3. **升級規則（Escalation Rule）**：
   Commander 每次派工 Architect / Reviewer 時，Task Pack 必須包含：
   `ASTRA_EFFORT: MEDIUM | HIGH`
   並附帶明確的升級理由（Escalation Reason，如上述代碼之一）。Default 為 `MEDIUM`。禁止以「因為這是架構／驗收，所以一律 High」為由濫用 High。High gate 必須收到縮小聚焦的 narrowed Task Pack，不得重新進行無界全庫探索。Commander 可以在同一具名任務中依本次 dispatch 動態切換 Medium / High。

### 具名任務重用與 Fresh Task Pack 不變式

所有派工都優先選擇既有適任具名任務。worker 不自行 spawn 或派工，不要每次工作都建立新的 agent / subagent / session。

1. **具名任務重用原則**：
   - 舊有「每 BC 一個 planning/design Astra task」的推薦拓撲已廢除。**Bounded Context 不再是建立新 Astra named task 的理由。**
   - 不得因 collection-watch、entity-knowledge、semantic-grouping、runtime-ops、product-ui 等領域各建一個 Astra Architect。同一 Architect 具名任務依序服務不同 BC；同一 Reviewer 具名任務審查不同 BC candidate。
   - 建立新 Astra named task 的唯一允許條件：
     - role conflict（角色衝突，無法兼任）
     - independent validation isolation（獨立驗收需要完全隔離的對話 context）
     - existing task context 已實質污染或漂移
     - tool / session 失效無法安全運作
     - security / permission isolation
     - genuine separate product（真正獨立的不同專案產品）
     「different BC」本身絕不成立為新建 Astra 具名任務之理由。
   - 舊有 BC-specific Astra 任務不要刪除或 kill（保留歷史可追溯性），改標為 `IDLE / LEGACY_NO_NEW_DISPATCH`，之後新工作不得再路由給它們。
2. **Fresh Task Pack 是 BC 隔離的唯一邊界**：
   - 重用具名任務不等於沿用舊 context。每次派工 Architect / Reviewer 必須發送完整的 fresh Task Pack，不得省略。
   - Task Pack 至少必須包含：
     ```
     ROLE:
     ASTRA_EFFORT: MEDIUM | HIGH
     ESCALATION_REASON: (required if HIGH)
     CURRENT_TASK:
     CURRENT_BC:
     current_main_sha:
     candidate_sha:
     AUTHORITIES:
     AC:
     WRITABLE:
     READ_ONLY_DEPENDENCIES:
     FROZEN:
     POSITIVE_ORACLES:
     NEGATIVE_ORACLES:
     REQUIRED_READSET:
     REQUIRED_COMMANDS:
     ROLE_BOUNDARY:
     ROUTE_RETURN_CONDITION:
     ```
   - 舊 context 只能作為背景參考，絕對不能作為 current authority。如果舊 context 與新 Task Pack 衝突，一律以 Task Pack 及 current repo truth 為準。
3. **實作者拓撲維持（Implementer Topology）**：
   - 現有 Gemini Flash Implementer 依 writer ownership、worktree 及 repo 路徑繼續保持 context-local（例如搜尋、上下文分析、概念分群、前端介面、執行治理等），不強制合併為單一實作者。
   - Implementer 的隔離主要服務於唯一的 writer ownership、worktree 隔離以及並行實作的安全性，這與 Astra 分析 quota 問題截然不同。未有直接理由前，不更動 Implementer 拓撲。

### 角色隔離與獨立驗收不變式

- **角色隔離**：
  - Gemini Implementer（Antigravity）不得驗收自己的 candidate。
  - Codex Architect 不得直接接著實作。
  - Codex Reviewer 不得是該 candidate 的 Implementer 或 Architect。同一具名任務不得在同一 candidate 上 Design → Implement → Independent Accept 全部包辦。
- **標準流程**：
  `Gemini Commander (Antigravity)` → `Codex Medium/High Architect（僅必要時）` → `Gemini Flash Implementation (Antigravity)` → `deterministic verification` → `Codex High Reviewer（Independent Validation）` → `Gemini Commander integration`。
- **Codex Architect 使用規則**：
  若 External review finding 或 Task 已明確指定 defect、violated invariant、required behavior 及 oracle，通常**不需要** Architect，直接由 Gemini 3.8 Flash Implementer 進行實作或修復。
  只有當 Implementer 或 Commander 遇到以下情況時，才派工 `Market Forecast｜Architect｜分析・規劃・設計`（Codex `01a0bf82-2f55-7152-82e0-71a276cb8087`）：
  - architecture ambiguity（架構歧義）
  - root cause 不明
  - contract 存在兩種以上合理實作取捨
  - cross-BC 邊界決策
  - concurrency / transactional semantics 未定
  預設 effort 為 `ASTRA_EFFORT: MEDIUM`。Architect 回覆後，Commander 必須立即 consume 並 dispatch Implementer，**不得停在 `ARCHITECT_HANDOFF`**。
- **Codex Reviewer 使用規則**：
  - 普通 implementation iteration：可使用 Reviewer Medium 進行 bounded candidate validation。
  - 真正 local final candidate：使用 `Market Forecast｜Reviewer｜驗證・獨立驗收`（Codex `01a0bf82-79e6-7e70-a2d6-f528485ff252`），設定 `ASTRA_EFFORT: HIGH` 與 `ESCALATION_REASON: FINAL_INDEPENDENT_ACCEPT`。
  Reviewer 必須 fresh-read exact SHA。若 Reviewer REJECT，且 findings 屬於 local engineering defects，Commander **必須立即派工 Gemini Implementer 修復**，不得停下來向使用者回報 status summary，更**不得在 local reject 下尋求外部審查**。
  此狀態轉移現為標準強制不變式：
  `CODEX_REVIEW_REJECT -> LOCAL_REVISION_REQUIRED -> IMPLEMENTER_DISPATCH`
  兩者之間不存在中間終止狀態（`REVIEW_REJECT_WITH_ACTIONABLE_FINDINGS` implies `FINAL_RESPONSE_FORBIDDEN`）。若 workflow state 處於：
  `review_verdict = REJECT` 且 `findings_actionability = LOCAL_ENGINEERING`，
  則允許的後續狀態僅有：
  - `LOCAL_REVISION_IN_PROGRESS`
  - `IMPLEMENTER_RUNNING`
  嚴禁轉為 `WAITING`、`COMPLETE`、`USER_HANDOFF` 或 `INTEGRATION_READY`。
  當 Reviewer 判定 `VERDICT: ACCEPT` 且無已知 local blocker，直接進入 `INTEGRATION_READY`。此狀態轉移現為標準強制不變式：
  `CODEX_REVIEW_ACCEPT -> INTEGRATION_READY -> COMMANDER_INTEGRATION`
  `INTEGRATION_COMPLETE -> PORTFOLIO_RECONCILIATION`
- **獨立驗收標準**：
  `tests green != ACCEPT`。Codex High 獨立驗收仍必須：
  - fresh-read exact SHA
  - fresh-read Product Authority
  - fresh-read AC
  - 檢查 production diff
  - 檢查 tests
  - 最後只能輸出明確的 `VERDICT: ACCEPT` 或 `VERDICT: REJECT`。

#57 的 grandfathered checkpoint 僅指原 Claude Sonnet 4.6 Thinking reviewer `task-16666`、trajectory `22a16b0c-9f61-4844-a15f-fac1d9dd501f` 與 exact SHA `dc0b815fd641263e3c199523f2b051426c2b990e`。依 2026-09-13 最新使用者裁決，實際仍 RUNNING 時不 kill、不改原候選；無有效 reviewed SHA／verdict／findings 收據時記 `LEGACY_REVIEW_EVIDENCE_UNAVAILABLE`，不得冒作 ACCEPT，也不要求使用者恢復舊對話或將其作為永久依賴。保存舊候選後，在 latest main 重播並由獨立 Codex High fresh-read 新 exact SHA 重新驗收，仍須遵守角色隔離與既有整合 gate。舊收據日後返回僅作歷史補充，其中具體 correctness finding 按 defect 處理；此有限例外不改一般新 validation 的 provider 政策，不包含憑證。

#55、#56、#57、#58 既有 delivery / acceptance 全部保留。不要因 routing 改變重新驗收 immutable historical SHA。只有未來 candidate bytes 改變，才需要 Codex High 驗收新 exact SHA。

<a id="收到執行結果後接續"></a>
## 收到執行結果後接續

每次收到依本節拓撲派工的具名任務回應，以回應、原 Task／AC 與目前依賴為輸入，由 Commander 完成以下一次有限處理，不等待使用者再次催派：

1. 每次 Analysis／Plan／Design／Review 收件先核本次範圍、實際結果、讀取／驗證證據及停止狀態，立即依上述七項判 Ready，不只記「已交設計」。結果保存父 Story progress，Project 狀態另行更新；自報成功不等接受。
2. Ready 時依[執行拓撲](#execution-topology-and-dispatch)安排同一 ownership 的適任 Implementer 進行實作、決定性 verify 及 Independent Acceptance Reviewer 進行 independent accept，不重派已完成設計。超出本批操作授權時記 ready-but-not-dispatched 與停止原因，不改稱工程缺件。
3. Not Ready 時只處理第一個必要缺件，依 [跨階段 blocker 追溯](#blocked-traceability) 保存完整依據。產品待決依文件影響檢查回原需求；工程缺件查證後回原 Task，不要求無關 BC 或 Phase 先完成。
4. 消費結果並執行下一個直接動作，只有符合 [Commander continuation ownership](#commander-continuation-ownership) 的 terminal outcome 才結束批次；不以回報下一步代替執行。整合 gate 未過只阻擋需要它的合流／接受，不回溯否定已證的 local start 前提。

<a id="commander-continuation-ownership"></a>
## Commander continuation ownership

輸入：一個已授權的有限批次、其 scope／terminal contract、worker 回報、直接依賴及驗證證據。輸出：有證據的 terminal outcome，或仍由 Commander 持有的下一個直接行動；不是成功 dispatch 的收據。本節是 continuation 的唯一 owner，適用 Commander 及向其回報的執行角色。

Commander 負責把已授權批次收束到 terminal outcome。下列只是中間 execution state，不能作為 Commander 的成功停止點：prompt 已送出、route／dispatch 已建立、READ_ACK／ACK、worker 已開始、STOPPED_WRITING、worker 測試失敗、可由專案另一既有 owner 解決的 BLOCKED、已交另一 owner、已要求原 worker 繼續、waiting for review，以及 candidate commit 仍 pending integration。

具體強制遵循六項接續不變式：
1. **驗收提示詞建立完成僅屬中間狀態**：建立驗收 prompt 或測試腳本絕非停止點，必須實際啟動驗收者並取得裁決。
2. **Reviewer 已啟動 != 驗收完成**：啟動 reviewer 後必須等待並讀取結果，直至獲得明確裁決或實質錯誤。
3. **收件即時重估與推進**：收到任何 worker／reviewer 回報後，Commander 必須立即重新評估剩餘工作並直接推進，不得把責任推回使用者。
4. **列出下一步 != 執行下一步**：在存在可執行的任務時，必須立即呼叫工具執行，不得只回覆下一步清單或計畫。
5. **局部 blocker 僅限局部**：局部 blocker 僅阻擋其直接依賴之局部範圍，絕不得停擺其他獨立任務。
6. **報告不得代替執行**：任何成果報告或文字總結均不能代替尚未執行的驗收裁決、缺陷修復或遠端推送。

`handoff != completion`；`handoff != terminal`；`ACK != progress terminal`；`internal BLOCKED != user blocker`。Worker 的有限寫入／回報停止點不是 Commander 的批次完成點；不得只更新 progress 或寫「已交原作者繼續」就停止。

### Local Route Stop Semantics

`STOP / HANDOFF / RETURN from a worker route terminates only that invocation.`
`It never terminates Commander continuation ownership.`

`LOCAL_ROUTE_STOP != COMMANDER_STOP`
`HANDOFF != COMMANDER_TERMINAL`
`REVIEWER_ACCEPT != COMMANDER_TERMINAL`
`AWAITING_EXTERNAL_REVIEW != GLOBAL_PROJECT_STOP`

Worker、Architect 或 Reviewer 的：
- `STOP`
- `HANDOFF`
- `RETURN`
- `REVIEW_COMPLETE`

只代表：**該 route 本次 invocation 結束，控制權返回 Commander。**

Commander 收件後必須：
1. consume result（解析並核對實際產物與資料）；
2. 判斷目前批次還剩餘什麼必要工作；
3. 立即執行下一個可執行動作（如派工 Implementer、執行 Verify、或啟動 Reviewer）；
4. 直到真正 terminal condition 成立。

嚴禁看見 `STOP_FOR_INDEPENDENT_REVIEW`、`HANDOFF`、`STOPPED_WRITING` 或 `REVIEWER_ACCEPT` 即作為 Commander terminal 結束 turn。

### 外部審查角色（Optional External Audit）與本機整合權威

`Codex Reviewer is the authoritative independent acceptance authority for locally-final candidates.`
`External ChatGPT is an optional external audit only when explicitly requested by Product Owner, not a mandatory candidate integration gate.`

Codex Reviewer（`01a0bf82-79e6-7e70-a2d6-f528485ff252`）是專案正式的本機獨立驗收權威。
本機 development & acceptance loop 必須由 Commander 自行持續推進：
`Gemini Implementer → deterministic verify → Codex Reviewer → (若 REJECT) → Gemini Implementer 修 → verify → Codex Reviewer → ... → Codex Reviewer FINAL ACCEPT`

當 Codex Reviewer 判定 `VERDICT: ACCEPT`，且 deterministic / integration 前置全部成立後，候選版本即達到 `INTEGRATION_READY`。Commander 必須自行執行 merge、readback、close，並進入 `PORTFOLIO_RECONCILIATION` 繼續推動下一個授權工作，**不得等待外部審查，亦不得停止**。

External ChatGPT 不再是每個 candidate 的 mandatory integration gate。若且唯若 Product Owner 明確指示需要外部審計（`OPTIONAL_EXTERNAL_AUDIT`）時，才在 `LOCAL_FINAL_ACCEPTED` 後觸發外部審查旁路；審查結束後回到 `INTEGRATION_READY`。

### Local Closure Loop

`Implementation revisions must be iterated locally through Gemini Implementer + deterministic verification + Codex Reviewer until local FINAL ACCEPT.`

若在選配的外部審查或其他稽核中收到 `REVISION_REQUIRED` 或 findings：
Commander 絕不得修完單一局部 finding 就立刻再次尋求外部審查。
執行流程必須嚴格回到本機閉環：
`Findings → Gemini Implementer → deterministic verify → Codex Reviewer`

若 Codex Reviewer REJECT，繼續本機閉環修正（Implementer 修復 → Verify → Reviewer 驗收）。
只有在再次取得 Codex Reviewer `FINAL LOCAL VERDICT: ACCEPT`，且 exact candidate 已重新收斂至合流候選時，方可進入整合或再次送審。

### Candidate 狀態機與狀態流轉（Status Machine）

本機 active candidate 狀態流轉遵循以下狀態機：

```text
LOCAL_IMPLEMENTATION_IN_PROGRESS
       ↓
LOCAL_VERIFICATION_IN_PROGRESS
       ↓
LOCAL_REVIEW_IN_PROGRESS
       ↓
[Codex Reviewer Verdict]
  ├─ REJECT ──→ LOCAL_REVISION_IN_PROGRESS ──↺（回 Implementer 修正）
  └─ ACCEPT ──→ LOCAL_FINAL_ACCEPTED
                      ↓
               INTEGRATION_READY
     (Optional Audit if PO explicitly requested)
                      ↓
                   MERGING
                      ↓
                 INTEGRATED
                      ↓
            PORTFOLIO_RECONCILIATION
                      ↓
       [Next Locally Actionable Work]
```

- 主幹路徑：`LOCAL_FINAL_ACCEPTED -> INTEGRATION_READY -> MERGING -> INTEGRATED -> PORTFOLIO_RECONCILIATION -> next locally actionable work`。
- 可選旁路：若 Product Owner 明確要求外部審計，則走 `LOCAL_FINAL_ACCEPTED -> [Optional External Audit] -> INTEGRATION_READY`。
- `AWAITING_EXTERNAL_REVIEW` 只能在 Product Owner 明確要求外部審計且已送審時使用，絕非預設或必經狀態；它絕對不能表示 Commander 整個專案停止。若有其他獨立 Task 可執行，Commander 必須繼續推進其他任務。若同一 Issue 仍有 local defect 或尚未取得 local final accept，嚴禁標記外部審查狀態，應標記 `LOCAL_REVISION_IN_PROGRESS` 或 `LOCAL_VERIFICATION_IN_PROGRESS`。

### 收件後的直接行動

每次收到 Implementer／Designer／Reviewer／Operations 等具名任務結果，Commander 在同一已授權批次依序：

1. 核對結果與證據，判定是否符合下方真正 terminal outcome；不把狀態名稱當作證明。
2. 若尚未 terminal，定位下一個直接 owning Task／Slice 與既有 owning agent。
3. 依 [Task-local readiness](#task-local-readiness) 核對下一步必要前提，不新增全域 gate。
4. 已 Ready 且在現有授權內，立即續派該 owner。
5. Not Ready，只解除最小直接缺件；owner 回覆後立即消費結果，重新判斷並續推原工作。

### Internal blocker routing

deterministic test failure、manifest／inventory mismatch、caller integration 缺件、同 repo 另一 owner 的既存 RED、branch／worktree／test registration 配套、verifier finding，以及可由既有 Design／code／owner 查證的工程問題，都先追到：

`具體 failure → owning Task/Slice → owning agent → clear condition`

已 Ready 即派對應 owner；僅缺有限 Design 時，只派 high 補最小 readiness gap；收件後立即續推原工作。此類內部問題本身不得轉成「等待使用者」，不得以 handoff 解除 Commander 的責任，也不授權 worker 越過 writable／frozen 邊界。若證據顯示確有超出授權的外部條件，依下方 external blocker 收據處理，不由 BLOCKED 字樣推定。

### 合法 terminal outcome

只有以下三類可結束原已授權批次；判定範圍是原批次，不是把它臨時拆成只到 dispatch／ACK 的小批次：

- `SUCCESS`：指定有限 slice 已 Implement → Verify → independent Accept，必要 integration 完成，依既有 Git 規則 commit／push／merge 到應有位置，對應 evidence 已保存。缺任一必要步驟仍是中間狀態。
- `VALID INTERNAL TERMINAL`：原批次本來只授權 Design／Review／Spike，且有限輸出已完整交付；或使用者明示「到候選 commit 即停」。不能把整體實作批次內某位 worker 的有限停止授權，冒充整批可停。
- `TRUE EXTERNAL BLOCKER`：需要新的使用者產品裁決、使用者才能提供的 credential／permission、外部服務權限或付費能力、不可由 repo 證明的必要外部事實，或其他超出現有授權且無法安全推進的外部條件。嚴格禁止把 PR 等待外部審查、Codex ACCEPT 等待手動合流、候選版本本機就緒等列為外部阻擋。

**以下狀態絕非合法 Commander terminal**（嚴禁作為停止執行的理由）：
- `Implementer handoff`
- `Architect handoff`
- `Reviewer dispatched`
- `Reviewer ACCEPT`
- `tests green`
- `commit pushed`
- `PR ready`
- `integration ready`
- `locally-final candidate`
- `external review requested`
- `PR waiting for external ChatGPT`
- `Codex ACCEPT waiting for human merge`
- `one support-only task closed`
- `one Issue waiting review`

External blocker 必須列 `exact blocked scope`、`concrete dependency`、`Roadmap condition`、`why project agents cannot resolve it`、`exact user action / decision required`；禁止只寫 BLOCKED。SUPPORT_ONLY 的產品 Exit 仍填 None，另列本批直接必要條件，不捏造產品阻擋。

### 事件驅動與有限收斂

派工後用既有具名任務回報／等待機制接收事件；回報抵達就消費並續推，不以「已派送」作本輪成果。本規則不要求每五分鐘監督、不建立無限 polling loop、不新增排程。

連續兩次 routing／correction 沒有新的可觀察淨進度時，沿本檔「每輪開始前」重新檢查方法，停止擴大修補，查明真正 blocker；不得無限 agent ping-pong。保留原有 focused 嘗試與權限邊界，不因更換 owner 重置失敗次數，也不得把未解的內部問題直接包裝成使用者 blocker 或成功 terminal。

Task-local Ready 決定「可不可以開始一個 slice」；本節決定「開始後由 Commander 負責推到真正停止點」。有效路徑是：

`Ready → Dispatch → Implement → result → Commander consumes result → next direct action → Verify → Accept → Integration → terminal`

`Ready → Dispatch → ACK → Commander stops` 與 `Implement → internal failure → handoff → Commander stops` 都不是合法完成路徑。Task-local 七條、Story 必要 AC、Roadmap 全部必要 Exit 與獨立驗收不降低；有限續推不擴張產品範圍或操作授權。使用者限定治理批次完成後停止，不能據此重派其他產品工作。

<a id="commander-scheduler-loop"></a>
### Commander scheduler loop

任何 Task / Subtask / slice 完成 Closeout 後，Closeout 只結束該 bounded work item，**不結束 Commander execution chain**。
Commander 必須立即執行排程循環（Scheduler loop）：

1. **consume actual result**：解析並確認前一切片之實際執行產物與資料。
2. **保存 Verify / Accept / integration evidence**：將命令、輸出、exit code 與各項證據落檔。
3. **sync GitHub Project Status if boundary crossed**：跨越狀態流轉邊界時立即更新並讀回驗證 Project Status。
4. **re-evaluate parent Task**：重新評估所屬 Task 之剩餘 Subtasks 與當前狀態。
5. **re-evaluate Story AC**：重新評估 Story 業務 AC 達成度與差距。
6. **re-evaluate current Roadmap Exit**：重新評估當前 Phase Exit verdict。
7. **找 first authorized next direct action**：尋找下一項直接已授權且必要之行動。
8. **實際 dispatch / execute**：真正發送訊息、啟動命令或執行調度（見下方 Handoff 證據要求）。
9. **consume 下一個 result**：接續等待並消費下一階段成果。

形成不間斷之執行推進鏈：
`result → Closeout slice → scheduler re-entry → next direct action → dispatch → result → ...`

**嚴禁形成中斷鏈**：
`result → Closeout slice → report → wait for user`（此為嚴重的排程中斷違規）。

<a id="portfolio-reconciliation-loop"></a>
### 專案級接續循環與組合調節（Project-Level Continuation & Portfolio Reconciliation）

Commander 不僅是既有 leaf Task 的 scheduler，同時是 **Roadmap continuation owner**。
當 leaf queue 沒有任何 Ready Task 時，絕不等於整個專案可停止：

`EMPTY_LEAF_QUEUE != PROJECT_TERMINAL`
`NO_READY_TASK => PORTFOLIO_RECONCILIATION`

#### 核心治理不變式

1. **EMPTY_LEAF_QUEUE_IS_NOT_TERMINAL**：
   > Absence of a ready leaf issue is not evidence that no local project work exists. Commander must reconcile current Roadmap, open Epics/Stories, and accepted Product Owner handoffs before terminalizing.
   leaf queue 為空絕非 terminal 證據。只要 Roadmap 尚未完成、Epic 尚有未收斂 outcome、Product Owner 已留下尚未轉成 leaf Task 的 handoff、Story / Epic 有 current-main gap 可以在既定產品權威內分析，或存在可以透過 repo evidence 釐清的未證明 Exit，Commander 絕不得因「目前沒有 Ready leaf Task」停止。

2. **NO_READY_TASK_REQUIRES_PORTFOLIO_RECONCILIATION**：
   當 leaf queue 為空時，Commander 必須自動進入組合調節（Portfolio Reconciliation）流程：
   1. fresh-read current main
   2. fresh-read 產品路線圖（Roadmap）
   3. fresh-read 所有 OPEN Epic（如 #27, #28, #29, #30）
   4. fresh-read OPEN Story / Task
   5. fresh-read Product Owner 尚未完全承接的 handoff / comments
   6. 尋找 first unresolved locally-actionable outcome
   7. 判定執行途徑：
      - 已有 Task → 依執行拓撲 route
      - 沒有 Task 但 contract 足夠 → 依授權建立 bounded Task
      - 需要分析才能切 Task → 派工 Architect Medium 收斂 gap
      - 真正產品歧義 → 標記 `PRODUCT_DECISION_REQUIRED`
      - 真正外部證據缺件 → 標記局部 `TRUE_EXTERNAL_BLOCKER`
   8. 立即續推，不得等待「必須先有人類建好 Task」。

3. **COMMANDER_MAY_CREATE_BOUNDED_TASK_FROM_EXISTING_AUTHORITY**：
   > When existing authority is sufficient to define a bounded task without inventing product behavior, Commander is authorized to create and route that task.
   在以下條件全部成立時，Commander 被授權自行建立下一個 bounded Task，無須徵詢使用者同意：
   - Product Outcome 已存在於 current Product Authority / Roadmap / explicit Product Owner handoff；
   - 不需要自行發明新產品需求（嚴禁 invent feature / busywork）；
   - 可以明確定位 parent Epic / Story；
   - 可以寫出 bounded scope；
   - 可以寫出 Given / When / Then；
   - 可以定義 positive / negative oracle；
   - 可以指定 owner / writable / frozen；
   - 沒有 unresolved Product Decision。
   建立完成後，立即派工進入 `Architect / Implementer / Reviewer` 本機閉環。

4. **EXTERNAL_BLOCKER_IS_SCOPED_NOT_GLOBAL**：
   > A blocker on one leaf does not block unrelated Roadmap outcomes.
   單一 leaf Task 的外部阻塞（如 #61 之 `BLOCKED_EXTERNAL_EVIDENCE`）只阻塞其直接相依之局部功能，絕不代表整個 Market Forecast 專案停止。Commander 必須繼續調節其他獨立之 Epic / Story / Task。

5. **OPEN_ROADMAP_OUTCOME_REQUIRES_CLASSIFICATION**：
   Roadmap 頂部記錄 `NOT_PROVEN` 時，不能以單一批次的 `SUCCESS` 作為整個專案 terminal。所有 open Epics 與 Roadmap Exit 成果必須逐項分類為：
   - `CURRENT_PROVEN`（可安排 Epic closeout）
   - `LOCALLY_ACTIONABLE_GAP`（切下一 Task 續推）
   - `TRUE_EXTERNAL_BLOCKER`（記錄局部外部阻塞原因與解除條件）
   - `PRODUCT_DECISION_REQUIRED`（向 Product Owner 提請決策）
   - `FUTURE_OUT_OF_SCOPE`（明確標記並凍結）

<a id="commander-final-response-gate"></a>
### Final-response gate

對 Commander 而言，「發送 user-facing final response」本身即視為 **terminal action**。
一旦 Commander 送出 final response，本次 execution turn 即告結束。
因此只要 active batch 還存在任何可由本機完成的下一步，**絕對禁止產生 intermediate user-facing final response**。

#### NO_INTERMEDIATE_FINAL_RESPONSE

> A user-facing/final response is itself a Commander terminal action. While any local route is running, any local result can still be consumed, or any authorized local next action remains executable, Commander must remain inside the execution loop and must not return an intermediate status report.

只要 active batch 還存在以下任何狀況：
- Architect 尚在 running
- Implementer 尚在 running
- Reviewer 尚在 running
- deterministic verification 尚未完成
- local Reviewer REJECT 後仍可本機修復
- local candidate 尚未取得 final ACCEPT
- 尚有下一個已授權之 Ready Task 可執行
- 尚有可從 current Roadmap / Epic / Story / PO handoff 自行拆出並執行的下一個 bounded Task

這些情況均只能留在 internal execution loop。
**嚴禁對使用者輸出「目前狀態」、「等待實作者」、「等待 reviewer」、「保持待命」、「稍後自動喚醒」、「下一步是……」或 `STOP_FOR_*` 等中間狀態報告並結束 turn。**

#### ACTIVE_LOCAL_ROUTE_MUST_BE_CONSUMED

> Dispatching a local route transfers work, not continuation ownership. Commander must obtain and consume the route's terminal result through the available runtime mechanism before the active batch may terminate.

派出 local subagent 後，Commander 不得回覆使用者。必須使用本機 runtime 提供的機制追蹤並取得該 route 的完成產物：
`dispatch → obtain route state → RUNNING（繼續追蹤同一 route）→ COMPLETED（讀取完整 result 並 consume）→ 下一步`
嚴禁因 worker 尚未完成而直接發送 final response，亦嚴禁重複 dispatch。

#### ASSUMED_AUTO_WAKE_FORBIDDEN

> Commander must not rely on or claim future automatic wake-up unless the runtime exposes a verified continuation mechanism. If no such mechanism exists, report the exact runtime limitation rather than presenting waiting as successful continuation.

如果本機 runtime 實際沒有任何可取得已派 subagent 後續 completion/result 的機制，不得虛構「系統稍後會自動喚醒」，必須明確將此判定為 `LOCAL_RUNTIME_CONTINUATION_UNAVAILABLE` 並提供具體 tool/runtime evidence。

#### 合法終止條件（Tightened Terminal Conditions）

只有在同時滿足以下所有條件（A + B + C + D + E 全數成立）時，方可發送 final response 並停止本次 execution turn：

A. **沒有 running local route**（所有 worker / architect / reviewer 均非 running）。
B. **沒有 unconsumed local result**（所有已交付之收據均已消費並落檔）。
C. **沒有 Ready leaf Task**。
D. **沒有可以從 current Roadmap / Epic / Story / Product Owner handoff 在現有產品權威內自行拆出的下一個 bounded Task**（已完成 Portfolio Reconciliation，無 locally-actionable gap）。
E. **所有剩餘未解決之 product work 均已逐項證明屬於以下三類之一**：
   - `TRUE_EXTERNAL_BLOCKER`（附帶 exact dependency、為何專案內部無法解決、及解除條件）
   - `PRODUCT_DECISION_REQUIRED`（附帶具體產品決策取捨與待決事項）
   - `FUTURE_OUT_OF_SCOPE`（已明確標記並凍結）

若上述 A+B+C+D+E 任一條件未滿足，**絕對禁止發送 final response**，必須留在 internal execution loop 推進。

**Continuation 違規判定**：
如果 Commander 自己準備在狀態標頭輸出：
`TRUE EXTERNAL BLOCKER: NO`
以及上下文存在可推進的 Next Direct Action 或可拆解的 locally-actionable gap，那麼在該 Action 尚未實際 execute / dispatch 前，**絕對不得發送 final response**。
此組合（`TRUE EXTERNAL BLOCKER = NO` + `Next Direct Action / Gap exists` + `Commander final response`）本身即判定為 continuation violation。

### Handoff 必須有實際 dispatch evidence

派工交接必須有傳輸證據，以下均**不構成**合法 handoff：
- 「寫好 prompt」 != handoff
- 「列出驗收封包」 != handoff
- 「說正在等待 reviewer」 != handoff

合法 handoff 必須具備實際 transport evidence，例如：
- 依[執行拓撲](#execution-topology-and-dispatch)選定的具名任務已收到訊息且 task ID 可核對；
- Task／policy 明示要求的外部具名 reviewer 已實際啟動，且當次 session receipt 可核對；
- task handle / process / background task receipt 證明已啟動。

若僅有 prompt 文字或驗收封包草稿，Commander 必須在同一 turn 內立即完成實際 dispatch。

### Running worker 不能讓 Commander final

如果依執行拓撲派工的 worker 正在 `RUNNING`，且其結果仍需 Commander consume 才能 continuation：
Commander 不得因「正在等待」而發送 final response。必須等待並接收實際 result，再依 scheduler loop 繼續執行。
- `RUNNING` 不是 terminal；
- `IDLE` 不是 terminal；
- `RESULT_RETURNED` 也不是 terminal。
只有經過 Commander consume、Closeout 並通過 Final-response gate 後，才可決定是否 terminal。

<a id="project-task-status-synchronization"></a>
## Project Task status synchronization

輸入：專案 GitHub Project（如 Market Forecast Delivery Project #4）的 Project items、Status 欄位現況、相關 Task/Story 的 current truth、獨立驗收收據及 Git 合流證據。
輸出：精確且已讀回驗證（read-back verified）的 Project Task `Status` 更新，或維持現狀的具體理由；不新增 Task、不改產品需求／AC／Roadmap／Sprint。

### 權威與責任（Authority & Ownership）

1. **工作流程投影**：GitHub Project 的 `Status` 表示 Task 的工作流程狀態。它不是 Story acceptance、Roadmap Exit verdict、Phase completion verdict 或 Product GO。Project Status 必須投影 current Task truth，不可反過來覆蓋產品證據。
2. **唯一權威**：Commander 是 Task Project Status synchronization owner。只有 Commander 擁有檢核與更新 Project Task `Status` 的權威與責任。
3. **嚴禁代理篡改**：Implementation、Review、Design 等工作者、外部自動化腳本均無權修改 Project 狀態，亦不得在未經 Commander 檢核之情形下自行調動看板。
4. **拒絕片面推論**：嚴禁僅憑 commit 數、分支存在、PR 開立、Issue close、progress update 或「感覺快完成了」直接推定 Project Status 已同步。必須在同一 continuation chain 實際 update Project field 並 read back。

### 狀態流轉門檻（Required transition checks）

至少在以下事件發生後，立即重判並同步 Task Project Status：
1. Task 首個 Ready slice 真正開始 implementation；
2. Task 從 implementation 進入 final independent review；
3. direct blocker 出現或解除；
4. independent Accept 返回；
5. required integration 完成；
6. main delivery 完成；
7. Task success condition 成立；
8. Task 被重新打開或 acceptance 被撤回。

看板狀態必須嚴格對齊 Project 既有有效選項（`Backlog`、`Ready`、`In Progress`、`Review`、`Blocked`、`Done`），不得自創狀態名稱：

- **`Backlog` → `Ready`**：
  該 Task 依 [Task-local readiness](#task-local-readiness) 完成必要分析／規格確認，直接必要前提已滿足，具備開工所需之 exact writable scope 與 oracle，隨時可供指派實作。
- **`Ready` → `In Progress`**：
  該 Task 已由 Commander 正式派工給具名 Implementer 施工，且實作正在進行中。
- **`In Progress` → `Review`**：
  實作者已完成候選產物交付與自測驗證，進入由獨立 Reviewer 進行規格、契約與回歸之獨立驗收階段。
- **`Review` → `Done`**：
  必須完全滿足下方「嚴禁偽完成（No false Done）」之所有條件。
- **Any → `Blocked`**：
  僅在發生下方「真實阻擋語義（Blocked semantics）」所定義之外部阻擋時方得標記，且須附帶可觀察之 clear condition。

### 嚴禁偽完成（No false Done）

1. **Task-local slice Done != Task Done**：
   單一切片（Slice）或局部 Subtask（例如 T-V1-07.5）的實作完成或驗收，絕不等於整張 Task（例如 T-V1-07）完成。只要該 Task 仍有未完成的 Subtasks 或後續 Phase/Slice 需求，整張 Task 絕不得標記為 `Done`。
2. **完整 Done 門檻**：
   只有在整張 Task 的 success condition 完全滿足時，方可轉為 `Done`：
   - Task 範疇內所有必要 Subtasks 均已實作完成；
   - 產品行為與契約通過完整 gate（如 `make ci-fast`）；
   - 取得非作者之獨立 Reviewer 的具名驗收收據（含命令、結果與日期）；
   - 成果已正確合流至 `main` 分支並推送至遠端；
   - 對應的 GitHub Issue 已經正式結案（Closed）或具備完整結案證據。
3. 若僅完成部分切片而 Issue 保持 Open，該 Task 應依當前實際狀態維持在 `Backlog`（等待下階段切片）、`Ready` 或 `In Progress`，嚴禁虛報 `Done`。

### 嚴禁懸掛進行中（No stale In Progress）

1. 如果 Task 已 SUCCESS，就不能仍留 `In Progress`。
2. 如果 Task 已沒有 active execution，但仍未達 Review / Blocked / Done，依 Project 現有 workflow 選擇正確狀態（退回 `Backlog` 或 `Ready`），不用歷史「曾經開始」維持假性 `In Progress`。

### 真實阻擋語義（Blocked semantics）

1. **內部問題不標 Blocked**：
   測試失敗、編譯錯誤、契約缺件、待補設計、相依套件調整等工程內部問題，屬於 Commander 內部路由（Internal blocker routing）職責。若 Commander 可繼續 routing，不得因單一 worker 回報 BLOCKED 就機械把整張 Task 設 `Blocked`，亦不得藉此規避推進責任。
2. **外部阻擋嚴格定義**：
   只有直接必要 blocker 真正阻止整張 Task 下一步時方可把 Task 設 `Blocked`（`TRUE EXTERNAL BLOCKER`：需要使用者產品裁決、外部系統帳號／憑證／權限、第三方計費額度、或無法自 repo 推理證明的外部限制）且當前無法安全推進。
3. 標記 `Blocked` 時，必須在 Task/Issue 註明 `exact blocker → Task → clear condition`，包含 blocking scope、concrete dependency、release owner 與明確可觀察的 clear condition。

### 讀回驗證（Read-back verification）

1. 每次透過 GitHub CLI 或 API 執行 Project Item Status 更新後，**必須立即執行 Read-back 查詢**（例如 `gh project item-list`）。
2. 比對讀回的實際 JSON 欄位值與預期設定值是否完全一致。
3. 嚴禁僅憑指令執行結束（exit code 0）即推定修改成功；只有在讀回驗證完全相符後，方可在回報中確認狀態同步完成。
4. 寫入失敗（write failure）屬於 internal operations blocker，由 Commander 立即處理，絕不把產品 Task 冒稱 Done。

## 驗證成本

- 完整驗證便宜時，每次修改都跑。
- 完整驗證昂貴時，開發中先跑受影響的 focused tests，在明確批次或里程碑邊界跑約定的完整 gate。
- focused tests 通過只能回報局部驗證通過。完成約定的完整 gate 之前，不得宣稱該批次完成。
- 宣稱某項改動無影響、不需要完整驗證時，要附上影響範圍的判斷依據。
- 真實觀測若可能沒有答案，先縮小並指定觀測目標、提高命中率，並事先說明無答案的可能性。
- 視覺驗收盡量轉成自動閘門；人工只檢查尚無法自動判定的少量殘差。

驗證安排不能只由趕時間決定。這個 repo 的完整本機 gate 是 `make ci-fast`。碰到 Camoufox、平台登入判定或
頁面掃描時，另依 [70-testing.md](70-testing.md) 完成真實手動驗證。

## 成果壽命

- 長期契約、資料格式、公開行為與保留的產品程式，要有完整測試、文件與決策紀錄。
- 臨時工具或預定替換的實作，做到可運作、可驗證，並保留專案要求的最低合規紀錄。
- 實測需要留痕時，放在 owner Task 的帶日期驗收區塊；長期產品決策的理由緊接唯一業務規則，不另建 ADR。
- 階段或實作預定被替換時，及早把預期重工成本列為需要決策。流程最佳化只能減少損失，不能代替是否繼續
  該架構或階段的決定。

## 責任與需求反轉

執行者負責查證前提、排序工作、辨識非技術決策，並區分已證實問題、推測與待決策事項。Review 速度不能
無上限地製造 backlog；每一項新發現都要先比較它對最終目標的影響。

執行者負責主動回報自己造成的返工，不重複查證已確立的事實，不對短命成果過度設計或過度文件化，並在
第一輪查證內回報真正阻塞。

若答案不會改變安全且可逆的做法，明示合理假設後繼續，不製造不必要的決策等待。需求反轉時要明示新決定
取代哪一條舊要求，以及既有成果的預期重工成本。

## 分工與合流

只有多人可能修改同一產物時，才正式劃分所有權。單一執行者不增加管理儀式。

多人協作開始時，同時指定：

1. 實作所有者。
2. 契約或資料來源的單一真相。
3. 整合所有者。
4. 合流的時點與驗證方式。

不得只拆開工作而不指定最後由誰整合。整合所有者負責確認合併後的完整 gate，不能把各自局部通過相加後
宣稱整體完成。

## 受控的連鎖修正

小型、已證實、低風險且直接阻擋下一步的問題，可以修正、驗證後繼續，不必每一步等待回覆。

連鎖修正不得：

- 擴大產品範圍。
- 改變公開契約。
- 引入新的架構方向。
- 代替應由使用者做出的決策。

## 回報

單項小修正使用三項短回報：

```text
處理          修了什麼，以及前提是否已證實
驗證          跑了什麼；局部驗證或完整驗證
目標淨進度    這一步讓最終目標前進多少，還缺什麼
```

批次或里程碑才使用完整回報，內容包括：已確認的問題與優先順序、需要使用者決策的事項、所有者與合流點、
局部與完整驗證邊界、對最終目標的淨進度，以及尚未完成、未驗證或刻意延後的缺口。

完成很多乾淨修改不等於接近最終目標。回報不得用完成項目數取代目標淨進度。
