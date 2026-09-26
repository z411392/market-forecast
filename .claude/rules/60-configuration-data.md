# 設定、Assets 與資料安全

## 設定分類

- 路徑、憑證、provider、部署座標等 machine facts 來自環境變數。
- 演算法預設值、門檻與窗口是受 review 的 code constants。
- 研究 universe、exchange/session 規則、measurement/model specification 與 promotion gate 是受 review 的 repo authority，不用環境變數偷偷改變。

環境變數是不可信輸入：

- 缺少 required value 時 fail fast。
- Safety boundary 格式錯誤時 fail fast；不得靜默變成 `0`、`None` 或 unlimited。
- Optional、空字串、零與 invalid 是不同狀態。
- Secret 不得提交、不得寫入文件、fixture、console 或持久 log。

## 誰可以讀環境變數

允許：

- `apps/<app>/module.py` provider
- `__main__.py` bootstrap
- 刻意採 request-time 設定的 driving handler
- 專用 `read_env_*` parser

禁止：

- driven adapter
- application command／query
- domain service
- DTO 檔

## Data 與 artifacts

- `data/`、provider cache、raw observations、Parquet/CSV/SQLite 與 private research artifacts 在產生前先完成 gitignore，並用 `git check-ignore` 驗證。
- 不使用 `COPY . .` 將 raw market data、provider credentials、holdout outcomes 或本機 cache 帶進 image。
- 付費／有 quota 的 provider 取得、bulk backfill、raw overwrite、universe/model freeze 都是具副作用操作，必須由 Task 明示授權。
- Raw observation 若需持久化，保留 provider、request range、retrieved-at、content hash／artifact identity；derived data 必須可由 raw + transform version 重建。

## Provider credentials 與 licensed data

- API key、token、account identifier 與授權憑證不得上版控、不得寫入文件／fixture／console／持久 log。
- Licensed raw market data 與 provider exports 不進 Git，也不得被 context/indexing 工具讀入。
- Provider 不可用時 fail explicitly；不得無記錄切換來源後把結果當成同一 authoritative series。
- 測試只使用 synthetic fixtures 或經明確允許的小型去識別樣本；真 provider smoke 屬 opt-in live integration。

## Market data 與研究資料

- Raw provider observation 不可變；canonical 1m bars、5m/10m/15m aggregation、RV/RQ/semivariance、targets、features 與 study outputs 都是可重建衍生物。
- Canonicalization 必須保存 symbol/exchange、timezone、session、bar interval、adjustment/corporate-action convention 與 source identity。
- Measurement sampling rule 在 forecast scoring 前凍結；不得以較好的 QLIKE 反向改寫 measurement。
- Final holdout outcomes、symbol-transfer holdout 與 post-freeze prospective outcomes 不得提前進入 model-selection context。
- 同一研究比較若混用 provider，必須由 spec 明示並做 overlap/measurement audit；不得默認不同供應商數值可直接拼接。

## Logging

可記錄：timing、row counts、provider id、symbol、exchange、time range、run id、artifact/content hash、穩定 error type。

不得記錄：

- API key、token、authorization header 或完整 raw provider response
- provider account/billing identity
- licensed raw dataset content 或未授權 sample payload
- final-holdout outcomes 在 freeze 前的 selection log
- 任何會讓 secret 或 provider entitlement 外洩的 request header/query
