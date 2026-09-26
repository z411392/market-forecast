# Ports、Adapters 與 DI

Port 是 `libs/<feature>/ports/` 裡的 ABC。一檔一個 port，類別名稱以 `Port` 結尾。
所有參數與回傳值都有明確型別。Port 簽名裡的 DTO 屬於同一 feature 的 `dtos/`。
Port 與其傳遞 DTO 閉包不得 import application、domain 或 adapters。

Port 只活在擁有該能力的 `libs/<feature>/ports/`。不准定義在 `apps/`，不准建 `apps/<app>/ports/`，
也不准把 outbound port 放進 kernel 來隱藏 feature 依賴。

Port 分兩種，都放在同一個 `libs/<feature>/ports/`，用誰實作來區分，不另建 `inbound/`、`outbound/` 目錄。
Outbound／driven port 屬於提供該 I/O 或可替換整合的 feature，不屬於呼叫它的 app。

## Inbound port

Inbound port 是對外 use case 契約。

- 由 application command／query 實作，見 [30-application-domain.md](30-application-domain.md)。
- Driving adapter 只把 transport 翻成一次呼叫，再把結果寫回 transport。它不實作 port。
- Driving adapter 解析 inbound port，不解析 application 具體 class，也不解析 outbound port。

不是每個 function 都需要 inbound port。只有 driving surface 會呼叫的公開 use case 才建立。

## Outbound port

Outbound port 是 application 向外取得能力的契約。

- 由 driven adapter 實作。
- Application 只依賴 outbound port 型別，不依賴 adapter class。
- 純計算不是 outbound port；那是 domain service。

不是每個 function 都需要 outbound port。只有 I/O、可替換整合、跨 feature 能力，或測試必須替換的
資源才建立。

## Driven adapters

- Driven adapter 只放在 `libs/<feature>/adapters/driven/`，實作一個或多個 outbound ports。
- 不准放在 `apps/`。App 只有 driving adapter 與 composition root。
- 以 constructor parameter 接收已解析的設定，絕不自己讀環境變數。
- 可擁有 SQLite connection、FAISS index、LadybugDB connection、HTTP client 或 browser resource。
- 基礎設施資源不得是 module-level global。
- 來源 adapter 回傳 feature DTO，不讓外部 SDK response 穿過 port。

## Composition root

- 具體綁定只能發生在 `apps/<app>/module.py` 或薄 bootstrap。
- Inbound port 綁到 application command／query。
- Outbound port 綁到 driven adapter。
- Provider 讀取並驗證環境變數，再把 typed value 傳入 adapter。
- CLI handler 由 `entrypoints.py` 以 `partial(handler, injector)` 交給 Fire。
- Injector 由 app entrypoint 建立一次。

## 資源 identity

多個 outbound ports 必須共用同一 transaction、browser lease 或 store instance 時，providers 必須回傳
同一個 memoized adapter。兩個獨立 `@singleton` provider 仍可能各建立一個物件。

## DI smoke test

每個 composition root 使用正式 module 做 smoke test，只替換外部重資源。以 `injector.get(...)` 解析
正式 inbound port；只測 FakeModule 無法證明 production wiring 可建立。

## 正確

```python
class ListRadarTopicsPort(ABC):
    def __call__(self, query: RadarTopicQuery) -> RadarTopicPage: ...


class ReadRadarPort(ABC):
    def list_topics(self, query: RadarTopicQuery) -> RadarTopicPage: ...


class ListRadarTopics(ListRadarTopicsPort):
    def __init__(self, radar_store: ReadRadarPort) -> None:
        self._radar_store = radar_store

    def __call__(self, query: RadarTopicQuery) -> RadarTopicPage:
        return self._radar_store.list_topics(query)


class MassiveAdapter(ReadMinuteBarsPort):
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
```

```python
def list_radar_topics(injector: Injector, cursor: str | None = None) -> None:
    page = injector.get(ListRadarTopicsPort)(RadarTopicQuery(cursor=cursor))
    print(dumps(page))
```

## 錯誤

```python
# apps/cli/ports/source_fetcher_port.py
class SourceFetcherPort(ABC):
    def fetch(self, request: SourceFetchRequest) -> TargetFetchResult: ...
```

```python
class RunPipelineHandler(RunPipelinePort):
    def __call__(self, request: PipelineRequest) -> PipelineReceipt:
        ...
```

```python
class SqliteRadarAdapter(ReadRadarPort):
    def __init__(self) -> None:
        self._api_key = environ["MASSIVE_API_KEY"]
```

```python
class BuildRealizedVariance:
    def __init__(self) -> None:
        self._adapter = MassiveAdapter()
```

```python
def get_radar(request: Request) -> ApiResponse:
    content = request.app.state.injector.get(ReadContentPort)
    embeddings = request.app.state.injector.get(SearchEmbeddingsPort)
    radar = request.app.state.injector.get(ReadRadarPort)
```
