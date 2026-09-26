# 設定、Assets 與資料安全

## 設定分類

- 路徑、憑證、provider、部署座標等 machine facts 來自環境變數。
- 演算法預設值、門檻與窗口是受 review 的 code constants。
- 客戶機構、分處、來源目標、官方帳號與自訂主題是本機產品設定，不是環境變數。

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

## Assets

- `assets/` 的本機資料在產生前先完成 gitignore，並用 `git check-ignore` 驗證。
- 不使用 `COPY . .` 將整個 repo、sessions 或內容資料帶進 image。
- 暫存觀測若含來源內容，使用 private file 並在工作完成後清除。

## Sessions

- Session store 永不上版控；它包含可登入的 profile、fingerprint 與帳號路徑。
- 目錄是 `<platform>/<account>/`，account 是最細層級，不新增 session-id 或批次子目錄。
- 同一平台只啟用一個帳號；替換後舊 account 目錄保留但停用。
- Cookie、token、完整 fingerprint、真實 email、session id 與 profile path 不得出現在 log、文件或 fixture。
- Session export 與一般資料 export 分開；預設資料匯出不包含可登入 profile。

## Content 與分析資料

- SQLite 保存設定、來源事實、歷史與分析結果；來源文字不得因推論輸出而被改寫。
- 每筆推論必須記 provider、prompt 與 space identity。
- SQLite FTS、FAISS vector indexes 與 LadybugDB graph 都是可重建投影，不是第二個權威。
- 內部分析或 GraphRAG library 不得引入 Neo4j、PostgreSQL 或其他持久資料庫。固定資料棧只有 SQLite、
  FAISS 與 LadybugDB。
- 外部 embedding provider 只收到目前契約允許的文字輸入；不得順便傳作者帳號、來源 URL、cookie 或
  session metadata。

## Logging

可記錄：timing、counts、platform、run id、遮蔽後的 target ordinal、穩定 error type。

不得記錄：

- cookie、token、authorization header 或 raw provider response
- 完整帳號、session id、profile path 或 fingerprint
- 真實 target URL、作者 profile URL 或來源全文
- embedding vectors 或 prompt body
