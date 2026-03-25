# Architecture Optimization Issue Backlog

## Overview

This backlog converts the architecture optimization plan into executable issue-sized tasks.

Execution strategy:

- Start with low-risk extraction issues.
- Preserve public APIs first.
- Add regression coverage before high-risk decomposition.
- Use small PRs with narrow scope.


## Phase 0: Stabilization

### ARCH-001: Add analysis payload regression coverage

- Type: `test`
- Priority: `P1`
- Difficulty: `medium`
- Goal: protect current stock analysis payload shape before refactoring orchestration
- Scope:
  - add regression tests for API analysis response structure
  - add snapshot-like assertions for report summary/strategy/details sections
- Acceptance Criteria:
  - analysis response format is covered by automated tests
  - failures clearly show payload drift
- Risk:
  - low


### ARCH-002: Add provider fallback regression tests

- Type: `test`
- Priority: `P1`
- Difficulty: `medium`
- Goal: lock in current data provider fallback behavior
- Scope:
  - test `DataFetcherManager` provider order
  - test fallback when one provider raises an error
  - test batch result aggregation behavior
- Acceptance Criteria:
  - provider fallback path is test-covered
  - batch fetch keeps partial success behavior
- Risk:
  - low


### ARCH-003: Introduce structured log context for analysis flow

- Type: `refactor`
- Priority: `P1`
- Difficulty: `medium`
- Goal: make runtime diagnosis easier before deeper architecture changes
- Scope:
  - standardize `query_id`, `stock_code`, `query_source`, `provider`, `cache_hit`
  - propagate key fields through pipeline and task queue logs
- Acceptance Criteria:
  - major analysis steps include consistent context fields
  - errors can be traced by `query_id`
- Risk:
  - low


## Phase 1: Low-risk extraction

### ARCH-004: Extract rate limiter and code normalization from `data_provider/base.py`

- Type: `refactor`
- Priority: `P1`
- Difficulty: `easy`
- Goal: reduce foundational coupling in the data provider layer
- Scope:
  - move `RateLimiter` into `data_provider/core/rate_limit.py`
  - move `normalize_stock_code` and `canonical_stock_code` into `data_provider/core/code_normalization.py`
  - keep compatibility exports from `data_provider/base.py`
- Acceptance Criteria:
  - existing imports continue to work
  - no runtime behavior change
  - normalization helpers have unit tests
- Risk:
  - low


### ARCH-005: Extract batch fetch orchestration from `data_provider/base.py`

- Type: `refactor`
- Priority: `P1`
- Difficulty: `medium`
- Goal: separate batch execution from provider routing
- Scope:
  - move concurrent batch fetch utility into `data_provider/core/batch_fetch.py`
  - keep `DataFetcherManager.batch_get_daily_data()` as facade
- Acceptance Criteria:
  - batch interface remains unchanged
  - concurrent result handling stays compatible
- Risk:
  - low to medium


### ARCH-006: Extract provider routing logic from `data_provider/base.py`

- Type: `refactor`
- Priority: `P1`
- Difficulty: `medium`
- Goal: isolate provider selection, retry, and fallback policy
- Scope:
  - extract routing/fallback internals into `data_provider/core/provider_router.py`
  - preserve `DataFetcherManager` public behavior
- Acceptance Criteria:
  - provider routing behavior remains unchanged
  - fallback logic becomes independently testable
- Risk:
  - medium


### ARCH-007: Extract content fetching from `src/search_service.py`

- Type: `refactor`
- Priority: `P1`
- Difficulty: `medium`
- Goal: decouple article extraction from search provider orchestration
- Scope:
  - move webpage content extraction into `src/search/content_fetcher.py`
  - keep `SearchService` compatible
- Acceptance Criteria:
  - search output remains unchanged
  - content fetching can be tested separately
- Risk:
  - low to medium


### ARCH-008: Extract search provider adapters from `src/search_service.py`

- Type: `refactor`
- Priority: `P1`
- Difficulty: `medium`
- Goal: isolate external provider implementations
- Scope:
  - move Tavily/SerpAPI/Brave/Bocha providers into `src/search/providers/`
  - preserve dataclasses and service facade
- Acceptance Criteria:
  - provider API remains compatible
  - key rotation and retries still work
- Risk:
  - medium


### ARCH-009: Extract notification transports from `src/notification.py`

- Type: `refactor`
- Priority: `P1`
- Difficulty: `medium`
- Goal: separate delivery channels from report rendering
- Scope:
  - extract transport adapters for webhook/chat/email channels
  - keep existing notification service entrypoints
- Acceptance Criteria:
  - channel behavior remains unchanged
  - transports can be tested with fake payloads
- Risk:
  - medium


### ARCH-010: Extract report rendering from `src/notification.py`

- Type: `refactor`
- Priority: `P1`
- Difficulty: `medium`
- Goal: make report generation independently testable
- Scope:
  - move markdown/html/image rendering into `src/notification/renderers/`
  - leave dispatch logic in service layer
- Acceptance Criteria:
  - rendered output remains compatible
  - rendering has dedicated test coverage
- Risk:
  - medium


## Phase 2: Pipeline decomposition

### ARCH-011: Extract analysis persistence service from `src/core/pipeline.py`

- Type: `refactor`
- Priority: `P1`
- Difficulty: `medium`
- Goal: move save-history/save-intel/save-snapshot responsibilities out of pipeline
- Scope:
  - create `AnalysisPersistenceService`
  - update pipeline to delegate persistence calls
- Acceptance Criteria:
  - pipeline public methods remain unchanged
  - persistence paths are testable independently
- Risk:
  - medium


### ARCH-012: Extract intel orchestration from `src/core/pipeline.py`

- Type: `refactor`
- Priority: `P1`
- Difficulty: `medium`
- Goal: isolate multi-dimensional search behavior
- Scope:
  - create `IntelCoordinator`
  - move news/risk/earnings search formatting logic
- Acceptance Criteria:
  - intel content remains compatible
  - pipeline delegates search orchestration
- Risk:
  - medium


### ARCH-013: Extract delivery orchestration from `src/core/pipeline.py`

- Type: `refactor`
- Priority: `P1`
- Difficulty: `medium`
- Goal: separate notification triggering and output packaging
- Scope:
  - create `AnalysisDeliveryService`
  - delegate single-stock and summary delivery operations
- Acceptance Criteria:
  - notification timing and payload remain compatible
- Risk:
  - medium


### ARCH-014: Extract engine routing from `src/core/pipeline.py`

- Type: `refactor`
- Priority: `P1`
- Difficulty: `medium`
- Goal: isolate standard analysis vs agent analysis selection
- Scope:
  - create `AnalysisEngineRouter`
  - centralize agent mode decision logic
- Acceptance Criteria:
  - agent and non-agent flows stay behavior-compatible
- Risk:
  - medium


### ARCH-015: Convert `StockAnalysisPipeline` into thin orchestration facade

- Type: `refactor`
- Priority: `P1`
- Difficulty: `hard`
- Goal: reduce the main pipeline to coordination logic only
- Scope:
  - replace in-class heavy methods with delegating façade methods
  - preserve external interfaces
- Acceptance Criteria:
  - pipeline file size is materially reduced
  - external callers do not need behavior changes
- Risk:
  - high


## Phase 3: Domain clarification

### ARCH-016: Rename backtest engines by domain responsibility

- Type: `refactor`
- Priority: `P1`
- Difficulty: `medium`
- Goal: remove ambiguity between strategy backtesting and AI advice evaluation
- Scope:
  - rename logical roles to `StrategyBacktestEngine` and `AdviceEvaluationEngine`
  - add compatibility aliases during migration
- Acceptance Criteria:
  - docs/API terminology becomes clearer
  - existing imports keep working during transition
- Risk:
  - low to medium


### ARCH-017: Extract provider adapters from `src/analyzer.py`

- Type: `refactor`
- Priority: `P2`
- Difficulty: `medium`
- Goal: separate model provider integration from analysis prompt logic
- Scope:
  - move provider-specific logic into `src/llm/providers/`
  - keep high-level analyzer entrypoint stable
- Acceptance Criteria:
  - fallback behavior remains intact
  - provider adapters become testable independently
- Risk:
  - medium


### ARCH-018: Extract parser/result builder from `src/analyzer.py`

- Type: `refactor`
- Priority: `P2`
- Difficulty: `medium`
- Goal: isolate output parsing and result shaping
- Scope:
  - move parsing and result assembly into dedicated modules
- Acceptance Criteria:
  - model response parsing has direct tests
- Risk:
  - medium


## Phase 4: Persistence and config consolidation

### ARCH-019: Extract ORM models and DB manager from `src/storage.py`

- Type: `refactor`
- Priority: `P2`
- Difficulty: `medium`
- Goal: separate schema definitions from data access operations
- Scope:
  - create `src/storage/models.py`
  - create `src/storage/database.py`
  - keep compatibility exports
- Acceptance Criteria:
  - imports remain compatible
  - no schema behavior changes
- Risk:
  - medium


### ARCH-020: Move business queries into repositories

- Type: `refactor`
- Priority: `P2`
- Difficulty: `medium`
- Goal: reduce implicit business logic inside database manager
- Scope:
  - migrate stock/history/backtest related reads and writes into repositories
- Acceptance Criteria:
  - service layer depends on repositories instead of generic DB helpers
- Risk:
  - medium


### ARCH-021: Add config validation and grouped schema export

- Type: `refactor`
- Priority: `P2`
- Difficulty: `medium`
- Goal: improve config governance across CLI/API/Web
- Scope:
  - group config sections
  - add validation helpers
  - prepare config metadata for Web UI usage
- Acceptance Criteria:
  - config errors become easier to diagnose
  - Web/API can share one config schema source
- Risk:
  - medium


## Recommended Development Order

1. `ARCH-001`
2. `ARCH-002`
3. `ARCH-004`
4. `ARCH-005`
5. `ARCH-007`
6. `ARCH-009`
7. `ARCH-011`
8. `ARCH-012`
9. `ARCH-013`
10. `ARCH-014`
11. `ARCH-015`
12. `ARCH-016`
13. `ARCH-019`
14. `ARCH-021`


## Current Execution Status

- `ARCH-001`: completed
- `ARCH-002`: completed
- `ARCH-003`: completed
- `ARCH-004`: completed
- `ARCH-005`: completed
- `ARCH-006`: completed
- `ARCH-007`: completed
- `ARCH-008`: completed
- `ARCH-016`: completed
- `ARCH-009`: completed
- `ARCH-010`: completed
- `ARCH-011`: completed
- `ARCH-012`: completed
- `ARCH-013`: completed
- `ARCH-014`: completed
- `ARCH-015`: completed
- `ARCH-017`: completed
- `ARCH-018`: completed
- `ARCH-019`: completed
- `ARCH-020`: completed
- `ARCH-021`: completed
