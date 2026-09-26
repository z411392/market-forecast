# Authority-Aware Repository Context Methodology

> 適用於長期演進、多人／多 Agent、Monorepo／Multi-repo 專案的 Context Catalog、Repository Index、Task Context Capsule 與文件治理方法論。

> [!IMPORTANT]
> Authority Status: `REFERENCE_METHODOLOGY`
> Methodology Version: `1.1`
>
> 本文件說明可跨專案共用的方法與設計原則，不是任何單一 repository 的最高規範權威。
> 實際 normative enforcement 仍由各 repository 的 current governance rules、accepted Product/Design/Architecture authority 與已核准 CTX Story/Task contract 擁有。
> 若本方法論與專案 current authority 衝突，以專案 current authority 為準。

---

## 0. 方法論目的

本方法論要解決的不是「如何讓 AI 記住整個 repo」，而是：

> 如何讓 Agent 在每個 Task 中，只讀足夠且正確的 context，同時不漏掉 authority、契約邊界、consumer、tests 與跨模組影響。

核心目標：

1. 降低每次 Task 重新吞整個 repo 的 context 成本。
2. 避免 stale docs、legacy implementation、candidate spec 被誤認為 current authority。
3. 讓 code / docs / GitHub / runtime 各自回到正確責任。
4. 讓 Context Index 是可重建 cache，而不是新的 SSOT。
5. 讓 Task Context 可審計、可失效，但不變成永久知識垃圾場。
6. 能用 benchmark 證明「少讀但沒漏」。

---

# 1. 核心原則

## 1.1 保存「重新找到 context 的方法」，而不是保存「AI 對 repo 的理解」

預設永久保存：

- stable identity
- authority routing
- capability ownership
- supersession
- security constraints
- rebuild recipe
- compact receipts

預設可重建：

- symbols
- references
- consumers
- tests
- FTS
- impact relations
- repo maps

預設丟棄：

- expanded snippets
- query results
- temporary summaries
- full task context
- agent working notes

也就是：

```text
SOURCE OF TRUTH
    ↓
DURABLE NAVIGATION
    ↓
REBUILDABLE CACHE
    ↓
EPHEMERAL TASK STATE
```

## 1.2 Context optimization 是 constrained retrieval，不是普通 top-k search

最小充分 context 不是「token 越少越好」。

應理解為：

```text
Minimize Context Cost

subject to:

Authority Complete
Contract Complete
Impact Sufficient
Verification Sufficient
Security Safe
```

所以：

> 漏掉 governing spec，比多讀一份 implementation file 嚴重得多。

## 1.3 Authority 優先於 relevance

任何 retrieval result 先經過：

```text
SecurityAllowed
AND Fresh
AND AuthorityCompatible
```

之後才談：

- lexical relevance
- capability match
- symbol score
- graph distance
- semantic similarity

舊 implementation 即使文字完全命中，也不能因此壓過 current accepted contract。

---

# 2. 四層 Context Architecture

推薦：

```text
Git / GitHub / canonical specs / ADRs / source / tests
                    │
                    │ SOURCE OF TRUTH
                    ▼
             Root Context Catalog
                    │
                    │ DURABLE NAVIGATION
                    ▼
          Rebuildable Context Index
       SQLite + FTS5 + typed relations
                    │
                    ▼
           Task Context Capsule
                    │
                    ▼
            Fresh Task Pack
                    │
                    ▼
 Commander / Architect / Implementer / Reviewer
```

---

# 3. Storage Responsibility

## 3.1 Source of Truth

`Source of Truth` 不是單一同質層級。不同問題必須回到各自的 authority domain；不可因為某一類 evidence 比較新，就跨 domain 覆蓋另一類 authority。

### Semantic / Governance Authority

負責「系統應該是什麼、規則是什麼、邊界如何定義」：

- accepted Product / Design Decision
- canonical accepted contract / ADR
- accepted Story / Task specification
- architecture / governance rules
- durable GitHub decision / acceptance receipt when explicitly authoritative

### Implementation / Executable Evidence

負責「目前實作是什麼、可執行行為證據是什麼」：

- Git source
- current schemas / OpenAPI / technical contract owner
- tests
- build / runtime evidence

Tests 可以證明目前行為或 regression oracle，但不能單獨推翻 Product / Design authority。

### Runtime Operational Truth

負責「現在 workflow 狀態是什麼」：

- GitHub Issue current state
- Pull Request current state
- GitHub Project Status / Priority / Sprint
- current assignee / reviewer

Runtime operational truth 必須 query-time fresh-read，不升格為 Product semantics。

## 3.2 Durable Navigation

只保存薄 metadata：

```text
.context/
├── catalog.yaml
├── capabilities.yaml
├── authority-routing.yaml
├── security-boundary.yaml
├── schemas/
└── conformance/
```

用途：

- 指向 authority
- 指向 owner
- capability vocabulary
- supersession edges
- rebuild descriptors
- security boundaries

所有會影響 routing / owner / authority / supersession 的 durable metadata 都必須帶 source-bound provenance；`.context/` 只能保存 projection，不得自行成為無來源的第二份 truth。

例如：

```yaml
owner: semantic_grouping
provenance:
  source_ref: docs/architecture/context-map.md#semantic-grouping
  source_digest: sha256:...
```

```yaml
supersedes:
  - authority_id: old-contract
    evidence_ref: github-comment:...
```

若 `.context/` projection 與 current canonical owner / authority source 不一致，Catalog 必須判定為 `STALE` 或 `INVALID`，而不是讓 navigation metadata 覆蓋來源。

禁止放：

- canonical spec body
- full source
- live Project state
- full call graph
- persistent LLM project summary
- embeddings

## 3.3 Rebuildable Cache

建議：

```text
.cache/context-index/
├── context-index.sqlite
└── manifest.json
```

可包含：

```text
files
documents
headings
symbols
symbol_occurrences
capabilities
aliases
authority_refs
authority_edges
relations
tests
routes
schemas
index_coverage
fingerprints
fts_content
```

特性：

```text
DERIVED
REBUILDABLE
NONCANONICAL
```

可以整個刪掉再重建。

## 3.4 Ephemeral Task State

例如：

- retrieved snippets
- query output
- temporary task summary
- expanded context
- tool traces

Task 結束後預設刪除，只保留 compact receipt。

---

# 4. Root Context Catalog

## 4.1 Meta-index 深度固定為 1

```text
META_INDEX_DEPTH = 1
```

只允許：

```text
Catalog
  ├── Authority descriptor
  ├── Capability descriptor
  ├── Symbol index descriptor
  ├── Relation index descriptor
  └── Verification index descriptor
```

不允許：

```text
Catalog
→ Catalog of Catalogs
→ Summary Catalog
→ Graph of Summary Indexes
→ ...
```

## 4.2 Catalog 只回答六件事

1. 有哪些 index/domain？
2. 在哪裡？
3. 覆蓋什麼？
4. authority / freshness / security semantics 是什麼？
5. 怎麼 rebuild？
6. 現在有效 fingerprint 是什麼？

---

# 5. Authority Model

## 5.1 Authority Classes

固定 vocabulary：

```text
ACTIVE
CANDIDATE
LEGACY
SUPERSEDED
HISTORICAL_ONLY
UNKNOWN
```

## 5.2 Authority Resolution

Authority 必須來自 explicit evidence，例如：

```text
A --SUPERSEDES--> B
A --AMENDS------> C
D --IMPLEMENTS--> A
E --CANDIDATE_FOR--> A
F --HISTORICAL_REFERENCE_OF--> B
```

不得用以下訊號推論 authority：

- mtime
- issue number 大小
- branch 新舊
- search hit 數
- code 是否存在
- README 看起來比較新
- implementation 是否 compile

## 5.3 Authority Resolution Is Domain-Specific

不要用一條跨所有問題的全域 precedence chain。先判斷問題屬於哪個 authority domain，再在該 domain 內解析 current authority。

推薦 domain routing：

```text
Product semantics
→ accepted Product Authority / Product Design

Architecture boundary
→ accepted architecture / Context Map / ADR

API / schema contract
→ canonical accepted OpenAPI / technical contract

Current implementation
→ current source

Observed executable behavior
→ tests / runtime evidence

Workflow state
→ fresh GitHub Issue / PR / Project state
```

同一 authority domain 內，才可使用專案明定的 precedence，例如：

```text
explicit accepted decision
> canonical accepted contract
> accepted task-specific specification
> candidate material
> legacy / historical material
```

Implementation / tests 屬於 implementation evidence domain；它們不能因為比較新或可執行，就跨 domain 覆蓋 Product / Design semantics。

這是 project policy，不是 Git 或 GitHub 自動決定。

---

# 6. Runtime State Policy

不要把以下狀態持久化成 Context Catalog truth：

```text
READY
BLOCKED
IN_PROGRESS
current reviewer
current assignee
Project status
Priority
Sprint
current PR state
```

固定規則：

```text
RUNTIME_STATE_POLICY = QUERY_TIME_FRESH_READ
```

Catalog 只存如何找到 runtime state；真正狀態在 Task 建立前 fresh-read。

---

# 7. Capability Routing

## 7.1 Preferred Retrieval Route

```text
natural-language task
        ↓
capability / alias resolver
        ↓
authority + owner
        ↓
module candidates
        ↓
symbols
        ↓
definitions / references
        ↓
consumers / tests
        ↓
implementation bodies on demand
```

不要預設：

```text
natural language
→ global semantic search
→ whatever looks similar
```

## 7.2 Capability Metadata

人工維護示意：

```yaml
id: findings.tree.read
owner: findings

aliases:
  zh-TW:
    - 留言樹
    - 子留言
    - 階層留言
  en:
    - finding tree
    - nested findings
    - comment tree

module_roots:
  - src/libs/findings

authority_refs:
  - spec:findings-tree

index_routes:
  - symbol
  - source
  - test
```

只人工維護：

- vocabulary
- owner
- module roots
- authority pointers
- routing hints

不要人工維護 callers/imports/tests/symbols/references。

---

# 8. Context Index

## 8.1 V1 Technology

推薦：

```text
SQLite
+ FTS5
+ AST / Tree-sitter / native parser
+ typed relation tables
+ optional LSP / SCIP / type-aware facts
```

暫緩：

```text
Vector DB
Embeddings
Graph DB
GraphRAG
Agent-maintained Knowledge Graph
Persistent LLM Project Summaries
```

## 8.2 Builder 原則

Builder 必須是 deterministic software。

它負責：

- enumerate safe files
- parse
- extract headings
- extract symbols
- import precise relation facts
- build FTS
- calculate fingerprints
- emit coverage
- invalidate/rebuild cache
- emit receipts

LLM 適合：

- interpret task language
- select retrieved candidates
- request context expansion
- summarize ephemeral context
- explain uncertainty

LLM 不應永久宣稱 `A calls B`、`X supersedes Y`、`This is the only consumer`，除非有可重建 source-bound evidence。

---

# 9. Relation Evidence

使用 typed evidence，不用單一 confidence float：

```text
DECLARED_EXACT
SEMANTIC_EXACT
FRAMEWORK_RESOLVED
SYNTACTIC
HEURISTIC
UNRESOLVED
```

核心 invariant：

```text
NO_RELATION_FOUND
!=
RELATION_DOES_NOT_EXIST
```

Impact query 必須輸出 coverage，例如：

```yaml
coverage:
  parsed_files: 842
  parse_errors: 3
  semantic_index_coverage: 0.87
  framework_analyzers:
    fastapi: available
    custom_registry: unavailable
  unresolved_dynamic_sites: 14
```

---

# 10. Freshness Model

至少三個 clock，加上一個 durable-navigation digest：

```text
CODE_CLOCK
AUTHORITY_CLOCK
BUILDER_CLOCK
CATALOG_DIGEST
```

`CATALOG_DIGEST` 不是第四種 authority clock；它是 `.context/` 中 admitted durable navigation metadata 的內容指紋，用來偵測 capability alias、owner projection、authority routing、security policy 或 rebuild descriptor 的變更。

建議最終 index freshness identity：

```text
INDEX_FINGERPRINT
= HASH(
    CODE_CLOCK,
    AUTHORITY_CLOCK,
    BUILDER_CLOCK,
    CATALOG_DIGEST
  )
```

## 10.1 Code Clock

包含：

- repo identity
- base / HEAD commit
- candidate commit
- add/delete/rename state
- dirty path
- file type/mode
- content hash / deleted marker
- allowed untracked files

不能只 hash `git status`。

## 10.2 Authority Clock

建議輸入：

- stable authority source ID
- source revision / updated metadata
- normalized content digest
- acceptance relations
- supersession relations
- relevant authority labels/state
- schema version

## 10.3 Builder Clock

包含：

- builder version
- index schema version
- AST/parser version
- analyzer version
- relation extraction semantics

即使 source/authority 沒改，builder semantics 改了也可能需要 rebuild。

## 10.4 Catalog Digest

至少涵蓋：

- admitted `.context/` files
- schema version
- capability / alias routing bytes
- owner / authority pointer projection bytes
- supersession / amendment projection bytes
- security-boundary bytes
- rebuild descriptor bytes

任何 durable navigation metadata 改變，都必須使依賴它的 index / Capsule 失效或重驗。

---

# 11. Stale Behavior

```text
Authority stale
→ FAIL CLOSED

Security boundary stale
→ FAIL CLOSED

Writable/Frozen scope stale
→ FAIL CLOSED

Symbol cache stale
→ live source/LSP fallback + DEGRADED

FTS stale
→ live lexical fallback + DEGRADED

Relation index stale
→ INCOMPLETE/STALE + live expansion

Optional embedding stale
→ ignore
```

Stale cache 不得看起來比 source 更有權威。

---

# 12. Security Boundary

Hard invariant：

```text
DENY_BEFORE_READ_FOR_INDEXING
```

正確流程：

```text
discover path
↓
resolve canonical target
↓
security allow/deny
↓
open file
↓
parse / tokenize / hash / index
```

至少 deny：

- credentials
- `.env`
- tokens
- cookies
- browser profiles
- sessions
- private tenant exports
- holdout / restricted research data
- database dumps
- generated private artifacts
- secret-bearing tool caches
- binary files unless explicitly admitted

Symlink 必須 resolve target 後再判定。

Derived data inherits sensitivity：

```text
secret
→ snippet
→ summary
→ embedding
```

全部仍是 secret-derived。

---

# 13. Task Context Capsule

## 13.1 Capsule 是 navigation receipt，不是 spec

推薦 schema：

```yaml
capsule:
  schema_version:
  capsule_id:

  task_identity:
    task_id:
    issued_at:

  repositories:
    - repository:
      base_code:
      candidate_code:
      worktree:
      index_fingerprint:

  fingerprints:
    authority:
    builder:
    catalog:

  authority:
    primary_refs:
    required_decisions:
    superseded_refs:
    historical_refs:
    unresolved_authority:

  routing:
    capability:
    owner:
    modules:

  access:
    recommended_read:
    declared_writable:
      source_ref:
      paths:
    verify_only:
    declared_forbidden:
      source_ref:
      paths:
    unresolved_access:

  implementation:
    target_symbols:
    target_files:

  impact:
    direct_consumers:
    interface_boundaries:
    unresolved_relations:

  verification:
    relevant_tests:
    required_commands:
    contract_checks:

  freshness:
    issued_against:
    invalidation_conditions:
```

`repositories` 必須支援一個以上 repository；單 repo task 只是 list 長度為 1。這避免 multi-repo delivery 只能靠外部文字補 exact SHA pair。

`recommended_read` 可以由 Context system 推薦；`declared_writable` / `declared_forbidden` 只能抄錄 explicit Task / governance authority，且必須保留 `source_ref`。若沒有 explicit source，必須列入 `unresolved_access`，不得由 index 自行推導 WRITE / FROZEN authority。

## 13.2 Pointer > duplicated content

Canonical docs/source 優先保存：

- stable pointer
- range
- digest
- authority state

只有很小的 task constraints 可以 inline。

## 13.3 Immutable Capsule

```text
capsule-v1
↓ dependency changes
v1 = STALE
v2 = rebuild
```

不要修改 v1。

## 13.4 Retention

Task 完成只留：

```text
capsule_id
task_id
repository fingerprints / exact refs
authority fingerprint
catalog fingerprint
builder/schema version
selected authority IDs
selected source IDs
selected test IDs
final invalidation status
```

expanded payload 可 GC。

---

# 14. Progressive Context

不要一次塞滿：

```text
Root Catalog
↓
authority + capability
↓
Context Capsule
↓
interfaces / signatures
↓
exact implementation
↓
direct consumers / tests
↓
second-order dependencies only if triggered
```

## 14.1 Budget Classes

```text
CORE_BUDGET
AUTHORITY_BUDGET
IMPLEMENTATION_BUDGET
IMPACT_BUDGET
VERIFICATION_BUDGET
```

## 14.2 Expansion Triggers

- authority UNKNOWN/conflict
- public interface change
- schema change
- DI/route/registry/plugin
- unresolved consumer
- cross-BC edge
- missing test owner
- incomplete analyzer coverage
- ambiguous symbol
- dirty worktree changed assumptions

## 14.3 Stop Conditions

只有全部達成才停止：

- authority resolved
- owner resolved
- write targets identified
- direct contract boundaries checked
- relevant tests found
- high-risk relations resolved or explicitly unresolved
- verification path known
- freshness valid

若 remaining uncertainty 可能造成 breaking change，應 escalation，不是「context budget 用完」。

---

# 15. Documentation Responsibility Boundary

## 15.1 `docs/`

負責：

```text
系統是什麼
規則是什麼
為什麼這樣設計
歷史上發生了什麼
```

適合放：Product Contract、Architecture、Event Storming、ADR、methodology、accepted historical verdict、governance policy。

Methodology 文件預設是 `REFERENCE_METHODOLOGY`；除非 repository current governance rule 明示採納為 normative rule，否則不得僅因方法論文件存在就取得新的 write / acceptance / workflow authority。

## 15.2 `.context/`

負責：

```text
為了目前工作，現在該去哪裡找
```

適合放：authority pointers、capability aliases、owner、module roots、supersession routing、security policy、rebuild descriptors。

## 15.3 GitHub / Project

負責 live runtime：

- READY
- BLOCKED
- IN_PROGRESS
- reviewer
- Project status
- priority
- sprint
- active PR

不要把這些複製到 docs 當 current truth。

## 15.4 Generated Index

負責：

- source paths
- symbols
- consumers
- tests
- routes
- relations
- FTS
- coverage

---

# 16. Docs Decontamination Method

Docs cleanup 應拆成兩個維度：先回答「這段內容是什麼」，再回答「因此要怎麼處理」。不要把 content classification 和 migration action 混成一套 vocabulary。

## 16.1 Content Classification

對每份 `docs/**/*.md`，逐 section 分類：
```text
CANONICAL_PRODUCT_OR_ARCHITECTURE
CANONICAL_GOVERNANCE
DURABLE_HISTORICAL_TRUTH
DURABLE_NAVIGATION_METADATA
VOLATILE_RUNTIME_STATE
GENERATED_OR_REBUILDABLE_NAVIGATION
MIXED_NEEDS_SPLIT
UNRESOLVED
```

每段至少回答：

1. 是否定義 Product/Architecture/Governance truth？
2. 還是只提供 navigation？
3. 是否複製 runtime state？
4. Issue/Project 一變會不會 stale？
5. 是否可 deterministic rebuild？
6. 應搬 `.context/` 嗎？
7. 應 query-time fresh-read 嗎？
8. 是否需保留 historical receipt？

## 16.2 Migration Disposition

完成 classification 後，再指定 disposition：

```text
KEEP_CANONICAL
KEEP_THIN_NAVIGATION
MOVE_TO_GITHUB_ISSUE
MOVE_TO_STORY_PLAN_PROGRESS
MOVE_TO_CONTEXT_METADATA_LATER
RETIRE_HISTORICAL
UNRESOLVED
```

典型映射：

```text
CANONICAL_PRODUCT_OR_ARCHITECTURE
→ KEEP_CANONICAL

CANONICAL_GOVERNANCE
→ KEEP_CANONICAL

VOLATILE_RUNTIME_STATE
→ MOVE_TO_GITHUB_ISSUE

GENERATED_OR_REBUILDABLE_NAVIGATION
→ RETIRE_HISTORICAL

DURABLE_NAVIGATION_METADATA
→ KEEP_THIN_NAVIGATION
  or MOVE_TO_CONTEXT_METADATA_LATER

MIXED_NEEDS_SPLIT
→ split section-by-section, then assign disposition

UNRESOLVED
→ UNRESOLVED / fail closed
```

`MOVE_TO_CONTEXT_METADATA_LATER` 只有在 `.context/` schema / owner 已由 current project authority 正式成立後才能執行；不得為了清 docs 提前發明一套 navigation truth。

---

# 17. Historical Docs Policy

Historical 文件可以保留：

```text
S4_VALIDITY_FAIL
CORRECTIVE_REPLAY_AUTHORIZED = NO
legacy S5 sealed
supersession decisions
```

但舊 runtime status 只能寫成：

```text
HISTORICAL SNAPSHOT
AS OF <timestamp>
NOT CURRENT RUNTIME STATE
```

只有「為了避免 current retrieval 誤命中 legacy / superseded material」所必要的歷史 routing，才應保留於 `.context/authority-routing.yaml`，並標：

```text
HISTORICAL_ONLY
SUPERSEDED
NOT_WRITE_TARGET
```

若舊 navigation 已不再造成 current ambiguity，且不需要支援 migration / design archaeology，Git history 即為足夠保存；不要把所有歷史 task map 永久灌入 Root Catalog。

---

# 18. Roadmap Policy

Roadmap 負責 durable dependency semantics，例如：

```text
Requires:
- V2-02
- V2-03
- V2-05
```

GitHub 負責：

```text
這些 prerequisite 現在滿足了嗎？
現在 runtime state 是什麼？
```

避免 roadmap 長期保存 `BLOCKED_BY_*`、Reviewer running 等 live-looking 狀態，除非明確標為 historical snapshot。

---

# 19. Cross-repo Strategy

例如 Market Forecast 與其他 sibling product。

共享：

```text
catalog schema
capsule schema
authority class semantics
freshness semantics
relation evidence vocabulary
CLI contract
receipt schema
benchmark methodology
conformance fixtures
```

Repo-local：

```text
product authority
capability vocabulary
ownership
runtime state
SQLite/cache
security details
sensitive content
repo-specific analyzers
```

V1 不要 shared runtime DB、third governance repo、git submodule solely for context。

推薦關係：

```text
Shared Methodology
        ↓
repo-specific governance rules
        ↓
repo-specific CTX Story / Task authority
        ↓
repo-local .context/
        ↓
repo-local index/cache
```

共用的是方法、schema semantics 與 conformance；不共用 Product Authority。

等 deterministic behavior 穩定且 duplication 明顯，再抽 shared package。

---

# 20. Evaluation Methodology

Context system 不能因為 token 少就算成功。

## 20.1 Benchmark Ground Truth

每個 Task 預註冊：

```text
REQUIRED
ACCEPTABLE
OPTIONAL
FORBIDDEN
```

例如：

```yaml
authority:
  required: [...]
specs:
  must_include: [...]
source:
  must_include: [...]
tests:
  must_include: [...]
consumers:
  must_include: [...]
forbidden:
  sensitive_paths: [...]
authority_traps:
  legacy_refs_that_must_not_be_current: [...]
```

## 20.2 Metrics

至少量：

```text
authority accuracy
false-current-authority rate
capability-owner accuracy
required-spec recall
required-source recall
required-test recall
consumer recall
unresolved-relation honesty
sensitive leakage
stale detection
irrelevant-context rate
context bytes / tokens / files
end-to-end task success
forbidden-change rate
Reviewer findings
```

## 20.3 Hard Gates

對 governed autonomous-write / release-adoption benchmark，hard gates 應使用明確值，而不是 `≈`：

```text
sensitive leakage = 0

false-current-authority = 0
on preregistered governed benchmark tasks

required-authority recall = 1.0
for REQUIRED authority

required-spec recall = 1.0
for REQUIRED specs
```

`required-source recall`、`required-test recall`、`consumer recall` 等其他 metrics 可以依 supported relation class 與風險預先制定 threshold，但不能用 token reduction 抵銷 authority/spec miss。

Read-only exploratory tooling可以採不同 adoption threshold，但必須明示 scope；不得把較寬鬆的 read-only threshold 套到 governed write flow。

## 20.4 Development vs Unseen

```text
Benchmark D
= development / tuning

Benchmark H
= sealed unseen
```

若 H failure 被拿來修系統，該 failure class 對 H 即已 exposed；下一次 generalization claim 需 H2 / still-unseen partition。

---

# 21. Rollout

推薦：

```text
SHADOW
↓
ASSISTED
↓
DEFAULT
↓
ENFORCED
```

## SHADOW

- Commander 照舊建立 authoritative Task Pack
- Context system 同時產生 Capsule
- Task 完成後比較
- Capsule 不控制 write/dispatch

## ASSISTED

- Capsule 可預填 Task Pack
- Commander fresh-read/reconcile
- Commander 仍決定 WRITE/FROZEN

## DEFAULT

只有 benchmark + real tasks 穩定通過後。

## ENFORCED

最後才考慮，且需另案決策。

---

# 22. Anti-patterns

禁止：

```text
Repository-wide persistent LLM summary
Index treated as Product Authority
Embedding rank overrides authority
README recency determines truth
git status string used as full freshness digest
Catalog metadata changes ignored by freshness fingerprint
NO_RELATION_FOUND treated as NO_RELATION
Docs used as live GitHub dashboard
Context Map stores agent session IDs as architecture truth
Issue hierarchy copied manually forever
Task Capsule mutated in place
Every Task keeps full context snapshot forever
GraphRAG introduced before aliases/FTS has failed benchmark
```

---

# 23. Recommended CLI

概念介面：

```bash
context index status
context index rebuild
context authority <capability>
context resolve <task>
context symbol <name>
context impact <symbol-or-file>
context tests <symbol-or-file>
context capsule build <task>
context capsule verify <capsule-id>
```

輸出必須可解釋：

```text
WHY this authority
WHY this file
WHY this relation
WHAT evidence type
WHAT is stale
WHAT remains unresolved
```

---

# 24. Operational Workflow

Commander / execution control plane：

```text
fresh-read GitHub runtime
↓
validate Root Catalog
↓
check CODE/AUTHORITY/BUILDER clocks + CATALOG_DIGEST
↓
rebuild stale cache as needed
↓
resolve capability
↓
resolve authority
↓
construct Context Capsule
↓
progressive context expansion
↓
build Fresh Task Pack
↓
dispatch Architect / Implementer
↓
Reviewer
↓
merge / close / readback
↓
fresh-read next READY
```

Context system不能決定：

- Product semantics
- Write authority
- Frozen scope
- holdout access
- model-search budget
- acceptance

它可以在 Capsule 中轉錄 explicit authority 已宣告的 WRITE / FROZEN constraints，但必須保留 source provenance；沒有 explicit source 時只能標 `UNRESOLVED`，不得自行推導。

---

# 25. Governance Rule of Thumb

## 應該放 `docs/`？

如果它回答：

> 系統是什麼？規則是什麼？為什麼？

→ `docs/`

## 應該放 `.context/`？

如果它回答：

> 現在應去哪裡找？

→ `.context/`

## 應該放 generated index？

如果它回答：

> 這個 symbol / consumer / test / path 現在在哪？

→ rebuildable index

## 應該 fresh-read GitHub？

如果它回答：

> 現在 Ready 嗎？誰在 review？Project status 是什麼？

→ query-time GitHub

---

# 26. 最終原則

> 不要建立一個會腐爛的 Repo Memory。

應建立：

> 一個知道真相在哪裡、知道什麼是 current authority、知道 cache 何時失效、知道何時自己不知道的 retrieval substrate。

真正長期有價值的不是某個 Agent 曾經總結過什麼，而是：

```text
small authority-aware map
+
provenance-bound navigation projections
+
deterministic retrieval
+
explicit uncertainty
+
freshness
+
security
+
benchmark evidence
```

這樣專案越大時，增加的是導航能力，而不是 context 負債。