# 工作與規格

Task Issue：
Parent Story／spec／plan：
Subtask／SC／AC：
Roadmap phase：
Roadmap exit IDs（支援工作填 None；跨階段逐 Subtask 映射）：
Roadmap effect（ADVANCES／PROVES／SUPPORT_ONLY／FUTURE_PHASE）：
目前完整 prompt（Task Issue 頂部）：
Task branch／本 Subtask commit／writer／integration owner：

## 變更與邊界

實作範圍、未改範圍、契約影響：
Exact writable／frozen 與明示授權：
Task-local readiness（引用 [.claude/rules/15-execution-strategy.md#task-local-readiness](../.claude/rules/15-execution-strategy.md#task-local-readiness)；與 Story acceptance／Phase completion 分開，附 exact Task 七項證據或最小缺口）：

## 驗證證據

AC ID → 測試／命令 → revision、exit code、日期 → 結果：
Given／When／Then 正例、反例及禁止副作用 → Exit／effect：
尚未執行及原因：
NOT_RUN 的 exit code 為 N/A，不填 0：
Story progress 證據位置：
Exit verdict／獨立 reviewer（必要實作與正反證據不全則 NOT_PROVEN）：
What became true since previous update（僅支援則無新產品事實）：
First blocking exit／Remaining conditions preventing phase exit：
具體工程 dependency、受阻 Task／AC／Exit、原因、owner 與 clear condition：

## 審閱

- [ ] 五類文件影響已檢查，必要 spec／plan／progress 已同步
- [ ] 未修改 frozen oracle，或另有明確設計授權
- [ ] 無私有來源、session、secret 或未授權副作用
- [ ] 局部 PASS 未冒稱 Story 驗收；由指定 Steward 驗收
- [ ] SUPPORT_ONLY／FUTURE_PHASE／未執行 ADVANCES 未冒充當前產品 Exit 通過
- [ ] 如涉及歷史清理，原範圍→canonical survivor／KEEP、完整備份及獨立 review 齊全；空 branch deletion allowlist 即零刪除
- [ ] 不以 generic global Design gate 阻擋局部 Ready；本 Subtask 後停止，不默認授權下一 phase

本 PR 合併不自動代表整個 Story／Epic 完成。
