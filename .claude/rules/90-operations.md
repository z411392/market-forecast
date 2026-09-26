# 操作

## 破壞性操作

刪除或覆寫之前先解析精確目標。

- `make clean-generated` 只碰明示列出的可重建產物。
- `data/`、provider raw/cache、Parquet/CSV/SQLite、holdout outcomes、exports 與金鑰憑證依 [60-configuration-data.md](60-configuration-data.md) 嚴格隔離，絕不納入版本控制或任意覆寫。
- live provider call、付費／quota market-data、bulk backfill、export、reset、universe/model freeze 或其他有副作用的操作必須在 Task 明示授權。
- 保留使用者未提交工作（dirty work）。不得自行 stage、commit、restore。
- 失敗 attempt 是診斷證據，不靠刪除它防止誤用；消費者以 completion 與 acceptance gate 拒絕。
- 移除唯一副本或不可重建檔案前，先保留 SHA256、引用掃描與可還原來源；被現行架構完全取代的程式／文件由 Git history 保存，不另建 archive 副本。

## 本機執行

- `make ci-fast` 是完整 hermetic gate：lint、typecheck、architecture-check、governance-check、test。不連外部 provider 或公開平台來源。
- 生產入口、CLI、lint 與本機 tests 依規則使用 `uv run`。
- 真 provider API／下載與 TradingView manual parity observation 依 [70-testing.md](70-testing.md) 僅在明示授權且特定 gate 執行。
- Token、API key、provider account／billing identity 與憑證不寫進 repo、公開契約或 log。

## 完成定義

本節是完成／合流邊界，不是開工 gate；施工前提只依 [Task-local Ready](15-execution-strategy.md#task-local-readiness)，不降低以下驗證與獨立接受要求。

一個 Task 可合流，是指：

1. `Verifies` 的 BDD scenarios 已自動化，或已記錄無法自動化的原因與替代證據。
2. 新行為有正向與反向測試。
3. Owner 範圍的 focused tests 與 lint 通過。
4. 影響到的文件與決策在同一變更內更新。
5. Production source 是 committed Python，薄 apps／厚 libs、無 fallback 或 shim。
6. 沒有為了讓檢查通過而放寬 schema、reason code 或 gate。

一個 milestone 完成，另外需要：

1. 波次合流後 `make ci-fast` 全綠（或明確授權之 baseline 處置）。
2. 驗收結果記在對應 Task／Subtask，列出命令、exit code 與必要 artifact identity；數據從磁碟回讀。
3. 取得非作者之獨立 Reviewer 具名驗收收據。
4. Working tree 只包含已分類變更，沒有殘留背景程序。

## Checkpoint 與交接

交接回報包含：

```text
commit        可回復的 Git commit
rollback      上一個已知良好 commit
working tree  clean／已分類的未提交變更
background    背景程序數
run           run id、cutoff、accepted 狀態
```

## Commit

### Task 分支與 Subtask 提交

基線整理完成後，所有新派工與修改先綁定真實 Task，使用專屬分支，不在 main 混合施工。

1. 輸入為真實 Task／Bug／Spike issue、父 Story、固定 plan、依賴及最近已接受基線。Commander 先指定 `codex/<task-id>-<slug>` 分支，記錄 repo、base SHA、分支及工作目錄；同 repo 不同 Task 不共用可寫 checkout。多 Task 平行用各自 worktree，不在另一 worker 的 cwd 切分支。
2. GitHub leaf issue 內的有限 Subtask/checklist 步驟使用穩定 S1、S2…標記；不另建第四層 Agile Issue。每個步驟固定輸入、精確修改範圍、驗證與停止點，完整派工帶 Task URL、Subtask ID、branch、base SHA、cwd；唯讀 reviewer 讀同一指定分支，不取得 writer。
3. 每一 Subtask 形成一個可理解且可追溯的 commit，相關程式、測試與文件同批。訊息用英文，例如 `task-12 S1: implement scan contract adapter`；body 引用真實 Issue、驗證證據及理由。不同 Subtask／Task 不混提交，不用空 commit 偽造進度。
4. 提交前核對分支、實際 diff、owner-local 指定驗證及精確 staged paths。預設仍由 Commander stage／commit，worker 不自行 stage、commit、restore；只有完整 Task 派工明示授權後才由唯一 Git writer 提交。使用者髒工作不得順手納入，不使用全庫 stage 掩蓋範圍。文件-only 的後續修改也歸其 Task 分支與 Subtask commit。
5. 未實作者覆核 AC 與完整 Task 分支，必要修正仍回原 Task，以對應 Subtask 的修正 commit 追溯；不改寫已共享的 Subtask commits。合流保留 Subtask commit 歷史，不 squash 成單筆；僅 Task／產品驗收已成立才更新 Done。commit 存在本身不等於驗收。
6. 輸出 branch、Subtask commit SHA、實測／review 引用及剩餘缺件；本批停止依 [Commander continuation ownership](15-execution-strategy.md#commander-continuation-ownership)，候選 commit 或交接不等完成。Push／遠端合流／deploy 仍須使用者對該操作的授權；已授權的必要交付須續推，不因建立分支取得額外發布權。

跨 repo 工作由各 repo 的真實 Task issue 各開分支，引用唯一 Story spec；每個 repo 只提交本 Task 的檔案。
