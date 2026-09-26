# Market Forecast — coding agent 共用入口

本專案採用自 Kaledoxa 治理 baseline fork 的 GitHub Agile + Story spec 工作流。治理來源與差異見 [docs/governance-source.md](docs/governance-source.md)。

## 必讀順序

1. [docs/README.md](docs/README.md) 與 [.claude/rules/00-index.md](.claude/rules/00-index.md)。
2. [docs/delivery/mvp-phases.md](docs/delivery/mvp-phases.md)。
3. [docs/architecture/event-storming.md](docs/architecture/event-storming.md) 與 [docs/architecture/context-map.md](docs/architecture/context-map.md)。
4. 本次 GitHub Task、parent Story/Epic，以及 `specs/<issue>-<slug>/{spec,plan,progress}.md`。
5. Task 指定原始碼、契約、鄰近測試與直接失敗證據。

## 執行不變式

- Commander 是唯一 Git writer；規劃/設計、實作、獨立驗收分離。
- 每次需求先做文件影響檢查，再進受影響工作。
- 小段完成就 commit + push；每個 Task 在 issue/comment 留研究、探索、發現、驗證與阻塞證據。
- 薄 apps、厚 libs；Python 以 `uv run` 執行，不用 PYTHONPATH hack。
- Research fitting 可離線；production inference 優先回到 TradingView/Pine。
- B50 是另一個 frozen current-state momentum product，不在本 repo 重新優化。
- H=5 是 Risk Forecast primary；H=20 僅 confirmatory；QLIKE 是 primary loss。
- 新文件使用繁體中文；程式識別字與 commit message 使用英文。
