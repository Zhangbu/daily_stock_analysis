# Architecture Optimization Plan

## 1. Background

This project has grown from a stock analysis script into a multi-entry platform covering:

- CLI execution
- FastAPI backend
- Web UI
- Bot integrations
- Multi-provider market data ingestion
- LLM-based analysis
- News/intel search
- Notification delivery
- Historical evaluation and backtesting

The current architecture already provides strong end-to-end capability, but several core modules have become too large and now mix orchestration, domain logic, infrastructure access, and delivery concerns. This increases regression risk, slows feature iteration, and makes testing harder.

This document proposes a phased architecture optimization plan focused on:

- reducing coupling
- improving maintainability
- clarifying domain boundaries
- improving observability
- enabling faster feature delivery


## 2. Current Pain Points

### 2.1 Oversized core modules

Several modules have become too large and central:

- `src/core/pipeline.py`
- `src/notification.py`
- `src/search_service.py`
- `src/storage.py`
- `data_provider/base.py`
- `src/analyzer.py`

These modules currently combine multiple responsibilities, which makes isolated change difficult.

### 2.2 Blurred domain boundaries

Key business concepts overlap:

- stock data fetching vs cache vs fallback policy
- AI analysis vs trend analysis vs agent analysis
- strategy backtesting vs AI recommendation evaluation
- report rendering vs channel delivery

### 2.3 Error handling is resilient but not structured

The system is tolerant of third-party instability, but many `except Exception` branches reduce debuggability. Failures are often logged without a normalized error taxonomy.

### 2.4 Testing is constrained by architecture

Pure logic exists in some places, but many important flows still require full-stack setup or runtime-heavy dependencies, making regression checks expensive.

### 2.5 Configuration scale is increasing

The configuration model is feature-rich, but it is gradually becoming a second source of coupling across CLI, API, Web UI, scheduler, bots, and runtime services.


## 3. Target Architecture

The target architecture should move toward layered boundaries:

1. Entry Layer
   - CLI
   - API
   - Web task triggers
   - Bot commands

2. Application Layer
   - analysis orchestration
   - screening orchestration
   - backtest orchestration
   - task management

3. Domain Layer
   - market data models
   - trend analysis
   - AI advice evaluation
   - strategy backtest
   - report domain models

4. Infrastructure Layer
   - data providers
   - search providers
   - storage
   - notification transports
   - external model adapters

5. Shared Cross-Cutting Layer
   - config
   - logging
   - error types
   - metrics/tracing
   - caching policy


## 4. Refactoring Principles

- Preserve behavior before improving behavior.
- Split orchestration from implementation first.
- Favor adapters and facades before deeper rewrites.
- Keep new logic testable with pure-Python unit tests.
- Introduce explicit domain names to remove ambiguity.
- Avoid simultaneous rewrites of business logic and infrastructure.


## 5. Module-by-Module Optimization Plan

### 5.1 `src/core/pipeline.py`

#### Current role

This module currently handles:

- data refresh
- realtime quote access
- chip distribution access
- trend analysis
- search/intel enrichment
- agent mode routing
- AI analysis
- result persistence
- notification dispatch
- batch orchestration

#### Problems

- too many responsibilities in one class
- difficult to test individual steps
- high regression risk when adding new analysis features
- hard to reuse parts of the pipeline in API, bot, and future async jobs

#### Target split

Recommended decomposition:

- `AnalysisDataCoordinator`
  - fetch/save daily data
  - load historical bars
  - load realtime quote
  - load chip distribution

- `IntelCoordinator`
  - news search
  - risk search
  - earnings search
  - intel formatting

- `AnalysisEngineRouter`
  - choose standard AI analysis vs agent analysis
  - normalize inputs for downstream analyzers

- `AnalysisPersistenceService`
  - save history
  - save context snapshots
  - save news intel

- `AnalysisDeliveryService`
  - transform analysis result into output payload
  - call notification service

- `BatchAnalysisOrchestrator`
  - parallel execution
  - task aggregation
  - progress handling

#### Refactoring order

1. Extract persistence methods.
2. Extract intel/search methods.
3. Extract delivery methods.
4. Extract engine routing.
5. Leave `StockAnalysisPipeline` as a thin facade.

#### Risk

- medium to high

#### Risk details

- pipeline touches nearly every business path
- hidden assumptions may exist in current object lifecycle
- API, scheduler, and bot behavior could diverge if refactor is not covered by regression tests

#### Mitigation

- keep public method signatures stable in phase 1
- move code without changing output format first
- add snapshot tests for result payloads before deeper edits


### 5.2 `data_provider/base.py`

#### Current role

This module contains:

- base fetcher abstraction
- manager orchestration
- rate limiting
- fallback logic
- cache integration
- batch fetching
- code normalization helpers

#### Problems

- infrastructure policies are mixed into one file
- provider management and utility logic are coupled
- difficult to reason about retry and fallback behavior

#### Target split

- `data_provider/core/rate_limit.py`
- `data_provider/core/code_normalization.py`
- `data_provider/core/provider_router.py`
- `data_provider/core/batch_fetch.py`
- `data_provider/base.py` kept as compatibility export layer

#### Refactoring order

1. Extract rate limiter and code normalization helpers.
2. Extract batch fetch utility.
3. Extract provider router/fallback policy.
4. Keep import compatibility for existing callers.

#### Risk

- medium

#### Risk details

- many downstream modules import `DataFetcherManager`
- provider fallback order affects runtime results

#### Mitigation

- do not rename public manager in the first pass
- add unit tests for fallback order, normalization, and batch result aggregation


### 5.3 `src/search_service.py`

#### Current role

This module handles:

- provider abstractions
- API key rotation
- retry logic
- news search
- webpage parsing
- result formatting
- comprehensive intel search

#### Problems

- provider logic and domain formatting are mixed
- content fetching/parsing is embedded with search orchestration
- too many responsibilities for one service

#### Target split

- `src/search/providers/`
  - tavily
  - serpapi
  - brave
  - bocha

- `src/search/content_fetcher.py`
  - webpage/article extraction

- `src/search/intel_service.py`
  - multi-dimension intel orchestration

- `src/search/formatters.py`
  - LLM-facing intel formatting

#### Refactoring order

1. Extract content fetching.
2. Extract provider implementations.
3. Extract formatting and orchestration.
4. Leave `SearchService` as facade.

#### Risk

- medium

#### Mitigation

- preserve current response dataclasses
- test provider fallback and max-age filtering separately


### 5.4 `src/notification.py`

#### Current role

This module handles:

- report rendering
- markdown splitting
- image conversion support
- channel selection
- webhook/email/chat sending

#### Problems

- rendering and transport are tightly coupled
- adding a new notification channel is expensive
- difficult to test formatting without real delivery behavior

#### Target split

- `src/notification/renderers/`
  - daily report renderer
  - summary renderer
  - markdown/image renderer

- `src/notification/transports/`
  - wechat
  - feishu
  - telegram
  - email
  - discord
  - custom webhook

- `src/notification/service.py`
  - channel selection
  - delivery orchestration

#### Refactoring order

1. Extract transport adapters.
2. Extract report rendering.
3. Keep current service class as compatibility facade.

#### Risk

- medium

#### Mitigation

- add golden-output tests for rendered reports
- add fake transport tests for multi-channel fan-out


### 5.5 `src/storage.py`

#### Current role

This module includes:

- SQLAlchemy models
- database manager
- CRUD helpers
- parsing utilities
- analysis persistence helpers

#### Problems

- model definitions and operational logic are mixed
- storage utility methods have grown into implicit business logic
- repository layer exists but is not yet the primary boundary

#### Target split

- `src/storage/models.py`
- `src/storage/database.py`
- `src/storage/migrations_support.py` or `schema_manager.py`
- continue moving read/write logic into repositories

#### Refactoring order

1. Extract ORM models and DB manager.
2. Keep current exports stable.
3. Gradually move business queries into repositories.

#### Risk

- medium

#### Mitigation

- avoid changing table schema during initial refactor
- move code only, do not redesign persistence contracts in the same phase


### 5.6 Backtest domain

#### Current role

There are now two backtest-like engines:

- `backtest/engine.py`
  - strategy signal backtest
- `src/core/backtest_engine.py`
  - AI recommendation evaluation

#### Problems

- same concept name for different domains
- likely confusion for API, docs, and future users
- unclear roadmap for unified analytics

#### Target split

- `src/domain/advice_evaluation/`
  - current `src/core/backtest_engine.py`

- `src/domain/strategy_backtest/`
  - current `backtest/engine.py`

Rename engines:

- `AdviceEvaluationEngine`
- `StrategyBacktestEngine`

#### Refactoring order

1. Rename internally and update imports.
2. Update API/docs terminology.
3. If needed later, unify shared metrics helpers.

#### Risk

- low to medium

#### Mitigation

- rename through compatibility aliases first
- keep old imports temporarily with deprecation comments


### 5.7 `src/analyzer.py`

#### Current role

This module mixes:

- LLM provider invocation
- prompt building
- model fallback logic
- response parsing
- analysis result shaping

#### Problems

- provider fallback policy is mixed with domain prompting
- hard to swap models or compare prompts
- difficult to unit test output parsing separately

#### Target split

- `src/llm/providers/`
- `src/llm/fallback_policy.py`
- `src/analysis/prompts/`
- `src/analysis/parsers/`
- `src/analysis/result_builder.py`

#### Refactoring order

1. Extract provider adapters.
2. Extract parser/result builder.
3. Extract prompt templates/builders.

#### Risk

- medium to high

#### Mitigation

- freeze current prompt/output contract first
- add parser tests using stored model responses


## 6. Cross-Cutting Improvements

### 6.1 Error taxonomy

Introduce structured exceptions:

- `ProviderUnavailableError`
- `RateLimitedError`
- `InvalidProviderResponseError`
- `AnalysisExecutionError`
- `NotificationDeliveryError`
- `PersistenceError`

Expected benefits:

- clearer logs
- cleaner retry logic
- more precise API error responses


### 6.2 Observability

Add a minimum runtime trace model for each analysis request:

- `query_id`
- `stock_code`
- `market`
- `provider`
- `cache_hit`
- `retry_count`
- `latency_ms`
- `analysis_mode`
- `notification_channels`

Recommended implementation:

- structured logger wrapper
- consistent log context propagation across pipeline steps


### 6.3 Configuration governance

Improve config handling with:

- grouped config sections
- validation rules
- config export for Web UI forms
- one authoritative schema for CLI/API/Web usage


### 6.4 Testing strategy

Target testing pyramid:

- pure unit tests for domain engines
- service tests with fake repositories/providers
- API tests for critical endpoints
- a small number of end-to-end smoke tests

Priority test areas:

- pipeline result shaping
- provider fallback behavior
- advice evaluation logic
- task queue state transitions
- notification fan-out


## 7. Recommended Refactoring Sequence

### Phase 0: Stabilization

Goal:

- improve confidence before structural change

Tasks:

- add regression tests around current analysis output
- add tests for backtest summary and provider fallback
- add baseline structured logging fields

Risk:

- low


### Phase 1: Low-risk extraction

Modules:

- `data_provider/base.py`
- `src/search_service.py`
- `src/notification.py`

Goal:

- split infrastructure-heavy modules while preserving public APIs

Risk:

- low to medium


### Phase 2: Pipeline decomposition

Modules:

- `src/core/pipeline.py`
- related persistence and delivery services

Goal:

- turn the pipeline into a thin orchestrator facade

Risk:

- high

Reason:

- touches most critical business paths


### Phase 3: Domain clarification

Modules:

- `backtest/engine.py`
- `src/core/backtest_engine.py`
- `src/analyzer.py`

Goal:

- clarify domain terms and isolate analysis engine responsibilities

Risk:

- medium to high


### Phase 4: Storage and config consolidation

Modules:

- `src/storage.py`
- `src/config.py`
- repository layer

Goal:

- make persistence and config better long-term foundations

Risk:

- medium


## 8. Delivery Risks and Controls

### Main risks

- hidden coupling between modules
- behavior drift in LLM analysis output
- notification regressions across channels
- provider fallback behavior changes
- API response shape drift

### Controls

- keep facades stable during extraction
- use compatibility imports during renaming
- add snapshot tests for report payloads
- add fake provider/fake transport integration tests
- use phased PRs with narrow scope


## 9. Suggested Milestones

### Milestone A

- baseline tests added
- logging context standardized
- advice/strategy backtest naming clarified

### Milestone B

- data provider, search, notification modules split
- no behavior change expected

### Milestone C

- pipeline decomposition complete
- API/Bot/CLI share thinner orchestration layer

### Milestone D

- analyzer and storage domains cleaned up
- new features can be added with lower regression cost


## 10. Features Enabled After Refactor

Once the above refactor is complete, the following features will become much easier to implement safely:

- portfolio-level backtesting
- walk-forward validation
- paper trading ledger
- factor attribution and score explainability
- event-driven realtime alerts
- market-specific strategy packs
- confidence scoring and invalidation conditions
- pluggable provider marketplace


## 11. Final Recommendation

The best execution path is:

1. stabilize with tests and logging
2. split infrastructure-heavy modules first
3. refactor the main pipeline only after behavior is covered
4. unify backtest terminology before expanding strategy features

This project already has strong functional breadth. The next major gain will come not from adding more endpoints immediately, but from reducing architectural friction so future features can be built faster and with lower risk.
