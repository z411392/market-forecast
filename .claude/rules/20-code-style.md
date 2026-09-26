# 程式碼風格與命名

資料形狀見 [50-dtos-errors-http.md](50-dtos-errors-http.md)。文件語言見 [80-documentation.md](80-documentation.md)。

## 語言

- 原始碼、識別字、註解、docstring、commit message 與 CLI 輸出使用英文。
- `.claude/rules/` 與人類閱讀的專案文件使用繁體中文。
- 機器規格維持其原生格式。

## 檔案

- 一個檔案恰好一個公開 symbol：一個 class、一個 function，或一個 `TypedDict`。
- `TypedDict` 算公開 symbol。
- 私有 helper（`_` 開頭）可以跟它唯一的呼叫者同檔。
- 檔名 `snake_case`；類別與 TypedDict `PascalCase`。
- 不准 `__init__.py`。測試 fixture 也不准。
- 不准把多個公開型別塞進同一個檔。
- 不建立 `utils.py`、`common.py`、`misc.py`、`errors.py`、`ports.py`、`service.py`。

## Imports

- 只用 absolute imports。
- Imports 全部放 module scope；不得函式內 lazy import。
- 只引入實際用到的名稱。不准 `import package` 再寫 `package.member`。
- 不准 `from package import module` 再寫 `module.member`。
- 標準庫沒有例外：`sys`、`os`、`json`、`asyncio`、`logging`、`stat`、`sqlite3` 都寫 `from x import name`。
- 獲准的整模組別名只有 `import numpy as np`。
- 不准 `from x import *`。
- 不新增 `PYTHONPATH` workaround。Package 由專案設定從 `src/` 安裝。

## 命名

| 產物 | 檔名 | Symbol |
| --- | --- | --- |
| Port | `<verb>_<noun>_port.py` | `<Verb><Noun>Port` |
| Driven adapter | `<integration>_adapter.py` | `<Integration>Adapter` |
| Command／query | `<verb>_<noun>.py` | `<Verb><Noun>` |
| Domain service | `<verb>_<noun>.py` | `<Verb><Noun>` |
| DTO | `<noun>.py` | `<Noun>` |
| Typed exception | `<error_name>.py` | `<ErrorName>` |
| CLI handler | `apps/cli/adapters/driving/<verb>.py` | `<verb>` |
| HTTP handler | `<verb>_<noun>.py` | `<verb>_<noun>` |

## 型別

- 公開 method、port、parser 與 adapter boundary 必須完整標註型別。
- 不用擴大的 `Any`、無理由的 `cast` 或 `# type: ignore` 掩蓋契約問題。
- 外部不可信資料先 parse，再取得內部 DTO 型別。

## 正確

```python
from asyncio import run
from fire import Fire
from functools import partial
from json import dumps
from libs.market_data.ports.read_minute_bars_port import ReadMinuteBarsPort
```

## 錯誤

```python
import sys
print(message, file=sys.stderr)
```

```python
def load_adapter() -> object:
    from libs.market_data.adapters.driven.massive_adapter import MassiveAdapter
    return MassiveAdapter()
```

## 工具

- `make format` 改寫格式，必須能跑。
- `make lint` 檢查格式與 lint。
- `make typecheck` 執行 Pyright。
- 修正警告；只有狹窄且附理由的例外才能忽略。
