# GitHub Human-Readable Record Standard

本規則是 Issue／Comment 雙層格式、驗收與 historical migration 的規範 authority；遷移前歷史記錄已存檔於 Git history。本規則不得取代 Product Authority、implementation evidence 或 GitHub Project execution state。

本規則定義 Market Forecast 的 GitHub Issue / Comment 如何同時服務兩種讀者：

1. **人類回顧者**：幾個月後仍能快速理解「當時到底在解什麼問題、為什麼這樣決定、現在代表什麼」。
2. **Agent / Reviewer / Audit**：仍能依賴 Issue ID、Finding ID、SHA、狀態碼、Acceptance Criteria、formal status 與 evidence 精確工作。

核心原則是：

> **上層用自然語言解釋；下層保留精確結構。**

不得為了好讀而犧牲可驗證性；也不得只留下機器可讀縮寫，讓人類必須重建整段歷史。

---

## 1. Authority boundary

本規則只定義**記錄方式**，不新增產品規則、不改 Acceptance Criteria、不改 Issue hierarchy、不改 engineering acceptance authority。

- Product Authority / Product Design：產品語意真相。
- Issue body：可執行 contract / scope / AC 的 owner。
- Comment：append-only event log。
- Human-readable layer：對既有正式內容的解釋與導航，不是第二套 authority。
- SHA / formal finding / test oracle / receipt：仍是驗證真相，不因白話摘要而被取代。

若白話摘要與 Formal Contract 衝突，**Formal Contract / accepted authority 優先**，並應立即修正摘要。

---

## 2. Language and readability

Market Forecast GitHub 人類層預設使用**繁體中文自然語言**。

允許保留必要英文術語，例如 Finding、Statement、Entity、Verified Fact、exact match、lease fencing、CAS、current / stale、ACCEPT / REVISION_REQUIRED；但第一次出現時應用一句白話解釋它在本卡的意思。

避免只有 `R40-2`、`V73-3`、`D05`、`PASS`、`BLOCKED`、`current applicability`、`authority binding` 而沒有解釋。formal token 可以保留，但前面必須有「這對系統／使用者實際代表什麼」。

### 人類可讀性品質門檻

Human layer 的最低標準不是「有一段中文」，而是讓一位沒有參與這張卡的人，單獨閱讀 Human layer 就能理解主要故事，不必先讀 Formal Contract 或逐條 comments 才知道發生什麼。

對有實質 implementation、review reject、redesign、authority supersession 或 integration 歷史的 Issue／Comment，人類層必須依實際情況說清楚：

1. 原本遇到的問題，以及為什麼值得處理。
2. 最初打算怎麼解，以及重要前提。
3. 中途發現了哪些問題、哪個方案為什麼被退回或改掉。
4. 最後採用什麼做法，以及它實際改變了什麼行為或系統保證。
5. 現在的結果／狀態，以及後續哪些工作因此可以繼續。
6. 哪些結論不能從本卡推導，避免把 scoped result 誤讀成更大的產品完成。
7. 要深入查證時應看哪些關鍵 comment、SHA、Issue 或 accepted authority。

不得只把 Issue title 換成完整句子、把 formal token 翻成中文、列出「已完成／已通過」、或機械式列舉每則 comment。摘要必須解釋因果與轉折。

白話層應優先使用一般繁體中文。必要術語可以保留，但第一次出現時要說明它在這張卡裡實際代表什麼；能說「舊 worker 已失去這筆工作的所有權，所以不能再覆蓋新結果」時，不應只寫「lease fencing CAS failed」。

回顧性摘要另必須標明：

- `As of`：這份回顧寫到哪個日期／時間點。
- `Last substantive event`：最後一個真正改變產品、設計、實作、review 或 integration 狀態的事件；record migration 本身不算 substantive event。
- `Authority status`：`CURRENT`、`HISTORICAL` 或 `SUPERSEDED`，必要時附取代來源。

Open／長期進行中的 Issue，其 `HUMAN_HISTORY_SUMMARY` 是有日期的回顧 checkpoint，不是假裝永久最新。之後發生重要新進展時追加 `HUMAN_CHECKPOINT`；不得回頭改寫舊 summary 使歷史看起來像當時就知道後續結果。

判斷方式：人類應能在約一至兩分鐘內只看 Human layer 回答「為什麼做、發生什麼轉折、最後／目前怎麼了、不要誤讀成什麼」。回答不了就不算 human-readable 完成。


---

## 3. Issue body：雙層格式

新建或重整 Issue 時，最前面必須有人類導讀；正式契約放後面。

建議格式：

```md
# <Issue title>

## 白話說明

這張卡要解決什麼？
為什麼現在需要做？
如果不做，實際會造成什麼問題？

## 完成後代表什麼

- ...
- ...

## 不代表什麼

- ...
- ...

## 為什麼現在做

說明 dependency / sequencing，但不要只列 Issue 編號。

---

## Formal Contract

### Authority
...

### Scope
...

### Non-scope
...

### Acceptance Criteria
...

### Owner / Priority / Status
...
```

### 白話說明最低要求

至少回答：

1. 現在發生什麼問題？
2. 為什麼值得修？
3. 這張卡實際改變哪個使用流程或系統保證？
4. 完成後下一個工作能因此做什麼？

### 「不代表什麼」很重要

例如：

- 完成模型訓練引擎，不代表模型表現比較好。
- 完成 prototype，不代表 production UI 已驗收。
- 完成 durable store，不代表資料自動成為 Verified Fact。
- tests green，不代表 independent review ACCEPT。

用它防止幾個月後把 scoped receipt 誤讀成整體完成。

---

## 4. Implementation handoff：先講改變，再講 SHA

所有 `IMPLEMENTATION_HANDOFF` / `REVIEW_FIX + IMPLEMENTATION_HANDOFF` 應採雙層格式：

```md
## IMPLEMENTATION_HANDOFF

### 白話結論

這一版實際把什麼行為從 A 改成 B？
使用者或下游系統現在會看到什麼差異？

### 為什麼這樣改

說明它對應哪一個問題，以及不這樣做會有什麼錯誤結果。

### 這版沒有做什麼

避免 handoff 被誤讀成超出 scope 的完成。

### 下一步

- 等 independent review
- ACCEPT 後解除哪個 dependency
- REVISION_REQUIRED 時回哪個 owner

---

## Structured Record

Issue:
Base SHA:
Candidate SHA:
Remote Branch:
Authority:
Changed production paths:
Acceptance Criteria addressed:
Positive oracles:
Negative oracles:
Verification commands:
Known limitations:

STATUS:
READY_FOR_INDEPENDENT_REVIEW
```

Structured Record 欄位不能因為已有白話摘要而省略。

---

## 5. Independent review：先回答「為什麼接受／退回」

Review comment 必須讓人只看前半部就知道 verdict 的實際原因。

```md
## REVIEW_VERDICT: REVISION_REQUIRED

### 白話結論

這版已經正確完成哪些部分？
為什麼目前仍不能 merge？

### 實際風險

Finding 1 用自然語言說明：
「目前 guard 檢查了 X，但 X 本身仍由 caller 決定，因此仍可繞過。」

Finding 2 ...

### 修完之後代表什麼

說明本卡何時可以 ACCEPT，以及會解除哪個 dependency。

---

## Formal Review Findings

### Rxx-1 — <formal title>
Evidence:
Required correction:
Oracle:

### Rxx-2 ...
```

每個 Finding 都要有兩層：

- **人類層**：錯在哪裡、可能造成什麼後果。
- **formal 層**：精確 contract / file / SHA / oracle。

不得只有 reason code 或縮寫。

---

## 6. Product Design decision：必須記「為什麼」

`PRODUCT_DESIGN_DECISION` 除了 canonical rule，至少要有人類可理解的決策故事：

- 原本有哪些合理選項？
- 真正歧義是什麼？
- 最後選哪個？
- 為什麼其他選項不採用？
- 對使用者／管理員／工程的實際影響是什麼？
- 哪些事情刻意留在 non-goal？

Formal state machine、enum、AC、oracles 仍放在後段。

---

## 7. Integration receipt：說明「專案因此變成什麼狀態」

Integration receipt 不得只寫 `main = <SHA>`。應先說：

- 這項能力現在正式成立到什麼範圍。
- 哪個 dependency 已解除。
- 哪個下游工作現在可以開始。
- 還有哪些事情沒有因此自動成立。

格式：

```md
## HUMAN INTEGRATION SUMMARY

### 這次正式完成了什麼
...

### 專案現在有什麼改變
...

### 因此解除的 dependency
...

### 還沒完成的事情
...

---

## INTEGRATION_RECEIPT

Accepted review:
Candidate SHA:
Integrated target:
Remote readback:
Issue state:
...
```

---

## 8. Human checkpoint：Story / Epic / Phase 的回顧入口

當以下事件發生時，應新增 `HUMAN_CHECKPOINT`：

- Story 的主要 contract 成形或完成。
- Epic 進入下一個主要階段。
- Phase closure。
- 一段工作累積大量 revision / reject / rework。
- 重要 authority reset / product reset。

Checkpoint 不重抄所有 comments，而是回答：

1. 一開始想解決什麼？
2. 中間發現哪些原本沒看到的問題？
3. 哪些方案被退回？為什麼？
4. 最後怎麼解？
5. 現在可以做什麼？
6. 還不能做什麼？
7. 想深挖時應看哪些 Issue / comment ID / SHA？

---

## 9. Historical comments：可補白話層，但原始正式內容必須完整保留

使用者已於 2026-09-18 明確要求：既有 Issues **以及 comments 本身**都要做到自然語言、白話、詳實。因此歷史 comment 不再採「完全不編輯」原則。

歷史 comment 可以為了可讀性進行一次 migration edit，但只能採雙層格式：

```md
## 白話導讀（歷史補充）

> Historical readability edit: <日期>
> Original comment body SHA256: <sha256>

用繁體中文解釋：
- 這則留言當時在做什麼；
- 為什麼會出現這則留言；
- 如果是 handoff / reject / accept / design / integration，它對當時工作狀態實際代表什麼；
- 若有具體問題或轉折，白話說明原因與後果；
- 不要把 scoped 結果誤讀成什麼。

---

## Original Formal Record / 原始正式紀錄

<原 comment body 完整保留>
```

約束：

1. 原 comment body 必須完整保留於 `Original Formal Record` 下方；不得刪節、潤飾、改寫、重排或修正當年的措辭。
2. migration 前計算原 body 的 SHA-256，寫入 Human layer；review 可重新計算下方原文確認未被改寫。
3. 編輯造成 GitHub `updated_at` 改變不代表新的產品／工程活動；Human layer 必須明示這只是 historical readability edit。
4. 不因 migration 改 ACCEPT / REJECT / DESIGN_COMPLETE / INTEGRATED 等歷史 verdict，不改 Issue state、authority 或證據適用範圍。
5. 如果 comment 原本已經有符合本規則的完整 Human layer，不重複包裝。
6. 簡單 receipt / status comment 的白話層可以短，但仍要說清楚「這個狀態對當時實際代表什麼」；有 reject、redesign、failure、dependency change 的 comment 必須寫出具體原因與後果，不能只翻譯 marker。
7. `HUMAN_HISTORY_SUMMARY` / `HUMAN_CHECKPOINT` 仍作跨多則 comments 的故事入口；它們不能取代逐則 substantive comment 的白話化。

### 歷史遷移的正確做法

對既有 Issue：

1. Issue body 最前面補 `## 白話導讀（歷史補充）`；原 body 必須在分隔線後逐字保留。
2. 對既有 substantive comments 依本節雙層格式直接補白話導讀，原 comment 原文完整保留並附 SHA-256。
3. 另保留一則 `HUMAN_HISTORY_SUMMARY`，用來串起整張卡跨 comments 的完整故事。
4. Summary 必須明示它是回顧性摘要，並引用關鍵歷史 comment ID / SHA。
5. 不改 Issue open/closed 狀態、不改 AC、不改 accepted verdict。
6. 若 Issue 已被後來 authority supersede，要直接白話說明「這是歷史工作，不是 current authority」。

唯一例外：安全／隱私／敏感資料誤貼需要 redaction 時，依專案安全規則處理。

---

## 10. HUMAN_HISTORY_SUMMARY 模板

```md
## HUMAN_HISTORY_SUMMARY

> 這是 <日期> 補上的回顧性摘要，用來幫助人類閱讀歷史。
> 原始 Issue / comments / SHA / verdict 保持不變；Formal Contract 仍是正式依據。
>
> As of: <回顧截至日期／時間>
> Last substantive event: <日期 + comment / SHA / Issue reference>
> Authority status: <CURRENT / HISTORICAL / SUPERSEDED + 必要取代來源>

### 這張卡在解決什麼
...

### 歷史上發生了什麼
最初...
後來 review 發現...
因此改成...

### 最終／目前結果
...

### 這件事對後續有什麼影響
...

### 不要誤讀成
- ...
- ...

### 想深入查證
- Issue body
- comment #...
- comment #...
- candidate / integrated SHA ...
```

Closed historical leaf 可縮短，但仍要涵蓋「目的／重要轉折（若有）／結果／後續影響／不代表什麼」。若曾有 reject、redesign、authority change 或多次 implementation candidate，不得因已 Closed 就省略主要故事。

---

## 11. 長度原則

不是每個 comment 都要變長文。

建議：

- 小型 handoff/review：人類摘要約 100–250 中文字。
- 複雜 revision：200–500 中文字。
- Human checkpoint：400–1200 中文字。
- Formal evidence 不計入上述長度。

原則是：**人類用一至兩分鐘看懂主要故事；Agent 仍能精確驗證。** 上述字數只是建議，不是上限；若縮短後會失去重要因果、退回原因或 current-vs-historical 邊界，就必須寫完整。

避免複製貼上同一段 authority 到十個 comments。摘要要解釋該事件「新增了什麼理解」。

---

## 12. Status vocabulary 不取消，但必須翻譯

以下 formal marker 繼續使用：

- READY_FOR_IMPLEMENTATION
- READY_FOR_INDEPENDENT_REVIEW
- REVISION_REQUIRED
- ACCEPT
- ACCEPTED_FOR_INTEGRATION
- BLOCKED_BY
- DESIGN_COMPLETE
- PRODUCT_DESIGN_REQUIRED
- INTEGRATION_REQUIRED

但在人類段必須說明。例如：

- `REVISION_REQUIRED` →「這版方向大致正確，但目前還不能 merge，因為仍存在會讓 X 被錯誤當成 Y 的漏洞。」
- `BLOCKED_BY #73` →「Entity Workspace 的其他部分可以做，但 Verified Facts 的 final API binding 必須等 #73 backend contract 通過，否則前端會綁到可能被退回的 DTO。」

---

## 13. Future default

從本規則生效後：

- Commander 建 Issue：先 Human layer，再 Formal Contract。
- 既有 Issue / Comment migration：Issue body 與 substantive comments 都必須補 Human layer；comment 原文保留於 `Original Formal Record` 並記 SHA-256。
- Implementer handoff：先白話說改變，再 Structured Record。
- Independent reviewer：先白話 verdict，再 Formal Findings。
- Product Design：先決策故事，再 canonical decision。
- Integration：先 Human Integration Summary，再 receipt。
- Story/Epic/Phase milestone：補 Human Checkpoint。

任何 agent 都不得以「formal token 比較精確」為理由省略人類導讀，也不得以「白話比較好懂」為理由省略 formal evidence。

---

## 14. Historical migration completion standard

既有 GitHub Issues 的 retrospective migration 完成條件：

1. 每個 Issue body 都有白話導讀，或已有等價自然語言 section。
2. 原 Formal Contract 不被刪除或弱化。
3. 每個有實質歷史的 Issue 都有一則 `HUMAN_HISTORY_SUMMARY`。
4. 每則 substantive historical comment 已有自然語言 Human layer，且其原始正式內容完整保留於 `Original Formal Record`，附原文 SHA-256；既有合格 Human layer 不重複包裝。
5. Closed Issue 不因遷移被 reopen。
6. Open Issue 的 current formal status 不因摘要或 comment readability edit 改變。
7. Summary 能讓未參與該卡的人只看 Human layer 就理解原始問題、重要轉折／退回原因、最終或目前做法、後續影響與不應推論的範圍；不能只重述 title 或 status。
8. 每則 retrospective summary 標明 `As of`、`Last substantive event`、`Authority status`；migration timestamp 不冒充產品／工程最新活動。
9. Epic / Story 另有足以作為回顧入口的 checkpoint 或等價 summary。
10. 全部 migration comment 清楚標示為 retrospective。
11. Batch receipt 必須分開回報 Issue body、comments、history summary 三種 coverage；只證明 coverage，不自動證明敘事品質。
12. Final governance review 必須重新檢查所有 batch 的 Human layer；若既有 summary 太短、漏掉重要 reject／redesign／supersession，追加 `HUMAN_HISTORY_SUPPLEMENT` 補足。
13. 遷移完成後留下 coverage + quality receipt，列出已處理 Issue、已白話化 comments 數量、補充過的 Issue 與例外。
