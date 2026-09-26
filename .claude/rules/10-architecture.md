# 程式碼架構

薄 app、厚 lib。

```text
src/
├── apps/
│   ├── http/
│   └── cli/
└── libs/
    ├── kernel/
    └── <feature>/
```

- `apps/` 只做啟動、傳輸與組裝，不放業務規則。HTTP 入口是 `apps/http`，不是 `apps/api`。
- `libs/<feature>/` 擁有 use case、domain logic、ports、DTOs 與 driven adapters。
- `libs/kernel/` 只放沒有單一 owner 的跨切面能力，不得變成共用垃圾桶。
- 跨 feature DTO 不推進 kernel 來隱藏依賴。DTO 規則見 [50-dtos-errors-http.md](50-dtos-errors-http.md)。

## Feature 目錄

```text
libs/<feature>/
├── ports/
├── dtos/
├── exceptions/
├── application/
│   ├── commands/
│   ├── queries/
│   └── policies/
├── domain/
│   └── services/
├── adapters/
│   └── driven/
├── constants/
├── helpers/
└── tests/
    ├── unit/
    └── integration/
```

只建立用得到的目錄。不要新增 `contracts/`、`types/`、`application/types/`、`domain/types/`、
`public/`、`shared/` 或 `utils.py`。

## App 目錄

```text
apps/<app>/
├── __main__.py
├── entrypoints.py
├── module.py                 # composition root；不要叫 composition.py
├── dtos/                     # 僅 transport DTO；沒有就不建
├── exceptions/
├── constants/
├── helpers/
├── adapters/
│   └── driving/
└── tests/
    ├── unit/
    └── e2e/
```

禁止在 app 放 `service.py`、`ports.py`、`ports/`、`composition.py`、`errors.py`、`adapters/driven/`。
禁止任何 `__init__.py`。application、domain、port、driven adapter 不得進 app。

CLI、HTTP、排程或批次只是不同 driving surfaces。它們呼叫 inbound port，不實作 port。
業務流程由 lib application 實作 inbound port 擁有。Port 規則見 [40-ports-adapters-di.md](40-ports-adapters-di.md)。

## CLI

`python -m apps.cli <verb>` 是唯一 CLI 入口。`entrypoints.py` 只做 `Fire({verb: partial(handler, injector)})`。

- driving handler 是具名函式，檔名與函式名相同。
- handler 用 typed kwargs，不用 argparse，不讀含 verb 的 argv。
- 不准中央 `inspect.signature`，不准 `main(argv)`，不准 import `main` 當 verb。
- Import 風格見 [20-code-style.md](20-code-style.md)。

## 依賴

```text
允許  libs.A -> libs.B.ports
允許  libs.A -> libs.B.dtos
允許  libs.A -> 明確核准的純算法模組
允許  任一 lib -> libs.kernel
禁止  libs.A -> libs.B.application
禁止  libs.A -> libs.B.adapters
禁止  libs.A -> libs.B.domain
禁止  任一 lib -> apps.*
禁止  libs.kernel -> 任一 feature
允許  driving handler -> feature inbound port、DTO、exception
允許  apps/<app>/module.py -> feature ports、application 實作與 libs driven adapters
禁止  driving handler -> application 具體 class
禁止  driving handler -> outbound port
禁止  driving handler -> driven adapter
禁止  任一 lib -> app transport DTO
禁止  app -> 另一個 app
```

Production feature graph 必須是 DAG。

## 瀏覽器

Camoufox process 是外部資源。開啟、關閉、租用與 profile 由 session／collector adapter 擁有。
Application 不接收 Playwright page、context 或 browser object。

## 正確

```python
from libs.content_store.dtos.stored_entity import StoredEntity
from libs.content_store.ports.read_content_port import ReadContentPort
```

```python
from libs.data_pipeline.ports.run_pipeline_port import RunPipelinePort

receipt = injector.get(RunPipelinePort)(request)
```

```python
from functools import partial
from fire import Fire

Fire({"new": partial(new_session, injector)})
```

## 錯誤

```python
from libs.content_store.adapters.driven.sqlite_content_store_adapter import SqliteContentStoreAdapter
# 另一個 lib 直接依賴實作。
```

```python
from apps.cli.ports.source_fetcher_port import SourceFetcherPort
# port 出現在 apps/。
```

```python
from libs.data_pipeline.application.commands.run_pipeline import RunPipeline
# driving handler 依賴 application 具體 class。
```

```python
from apps.cli.adapters.driving.run_pipeline import main as run_pipeline
```

## 驗證

`src/libs/kernel/tests/unit/test_dependency_direction.py` 掃描 production imports。
修改規則時依 [70-testing.md](70-testing.md) 做故障注入。
