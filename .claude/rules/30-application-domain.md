# Application 與 Domain

Port 誰實作、driving／driven adapter 做什麼，見 [40-ports-adapters-di.md](40-ports-adapters-di.md)。

## Commands 與 queries

Command 或 query 是代表單一 use case 的 callable class，並實作對應的 inbound port。

- `application/commands/` 會改變狀態。
- `application/queries/` 唯讀。
- 一檔一類別。
- 類別繼承該 use case 的 inbound port。
- Outbound 依賴以 outbound port 型別做 constructor injection。
- 工作放在 `__call__`；非同步只在 use case 真正需要時使用 `async def`。
- 回傳 DTO 或原生值；不得回 transport response，也不得 print。
- I/O 只能透過 outbound ports。
- 設定與 threshold 由外層解析後傳入；application 不讀環境變數。
- Application 不實作 outbound port，也不直接建立 driven adapter。

API 可以有狹窄的設定與人工治理寫入，但來源事實的 query surface 唯讀。Driving handler 不得直接改
SQLite 來繞過 inbound port。

## 正確

```python
class ListRadarTopics(ListRadarTopicsPort):
    def __init__(self, radar_store: ReadRadarPort) -> None:
        self._radar_store = radar_store

    def __call__(self, query: RadarTopicQuery) -> RadarTopicPage:
        return self._radar_store.list_topics(query)
```

## 錯誤

```python
def list_topics(request: Request) -> JSONResponse:
    rows = connect("radar.db").execute("SELECT ...")
    return JSONResponse({"rows": rows.fetchall()})
```

```python
class ListRadarTopics:
    def __init__(self, adapter: SqliteRadarAdapter) -> None:
        self._adapter = adapter
```

## Domain services

Domain service 是具名、無狀態、純計算的業務或演算法規則。

- 不得有 I/O、環境變數、framework type 或 adapter dependency。
- 由 application 直接建立；純 service 不放進 DI。
- Generic helper 沒有領域語意。決定 grouping、selection、sentiment target 或 topic admission 的規則屬於
  domain service。
- 不為了形式導入 Aggregate、Entity 或 Value Object；只有具體 invariant、穩定 identity 或 consistency
  boundary 時才建立。

## 跨 feature 純算法

依序處理：

1. 能否透過 outbound port 表達；
2. 能否由 app composition layer 編排；
3. 若必須維持單一實作，才逐模組核准純算法。

不得為了避免 dependency edge，把同一算法複製到兩個 feature。
