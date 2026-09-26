# DTO、錯誤與 HTTP 契約

一檔一個公開 symbol 見 [20-code-style.md](20-code-style.md)。

## DTO

結構化資料是具名 `TypedDict`，放在 owner 的 `dtos/<noun>.py`，公開名稱是 `<Noun>`。

- 不准 `@dataclass`。
- 不准另外一套資料物件。
- 原生 scalar、mapping 或 tuple 已足以表意時不必再包一層。
- Production code 不得用匿名 record dict 或未標明值型別的 `list[dict]` 表達契約。
- Feature DTO 放 `libs/<feature>/dtos/`。
- App-only transport DTO 放 `apps/<app>/dtos/`。
- 不得把跨 feature DTO 推進 `libs/kernel/dtos/`。
- 不建立 `contracts/`、`types/` 等第二套資料目錄。
- 需要預設值或驗證的建構放在獨立 helper（`build_*`、`parse_*`），不得做成 TypedDict 的 method。
- 欄位存取使用 `value["field"]`，不得使用 `value.field`。

Owner 指誰有權改變資料形狀。Import 數量只是證據，不是判定。

## 正確

```python
from typing import TypedDict


class StoredEntity(TypedDict):
    entity_id: str
    label: str
```

## 錯誤

```python
from dataclasses import dataclass


@dataclass
class StoredEntity:
    entity_id: str
    label: str
```

```python
row: dict = {"entity_id": entity_id, "label": label}
```

## Runtime parsing

`TypedDict` 不做 runtime validation。HTTP body、query、header、環境變數、SQLite row、平台 response 與
外部 API response 必須先經 parser，再取得 DTO 型別。格式錯誤要產生具型別錯誤，不得部分接受。

## Typed exceptions

- Feature error 放在 `libs/<feature>/exceptions/`，一檔一類別。
- Exception 攜帶穩定機器 `type`，不含 HTTP status、response 或已 render 的使用者文案。
- Driving adapter 負責映射成 transport status code 或 CLI 英文輸出。
- 不把真實 URL、帳號、session id、來源文字或 secret 放進 exception message。

## HTTP contract

成功 payload 使用 endpoint 擁有的 transport DTO。錯誤統一使用：

```json
{
  "status": "error",
  "type": "<stable-error-code>"
}
```

- 成功或失敗由 HTTP status code 決定。
- `type` 是前端可以穩定分支的機器碼。
- Handler 使用具名 DTO，不手拼匿名 response records。
- API 不回傳 session 路徑、登入帳號、cookie、token、完整指紋或未遮蔽的內部錯誤。
- 一個 major version 內只保留一種成功 envelope。
