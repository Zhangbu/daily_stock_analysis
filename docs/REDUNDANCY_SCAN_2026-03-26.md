# Redundancy Scan (2026-03-26)

This document records low-value/duplicate code found after the streamlined notification and API-toggle refactor.

## P0 (fixed in this round)

1. Frontend blank page caused by misplaced feature-flag state code
- Location: `apps/dsa-web/src/App.tsx`
- Issue: `useState/useEffect` for `featureFlags` existed after `export default App`.
- Impact: web UI could render blank / fail to bootstrap.
- Status: fixed.

2. Duplicate `discord_bot_status` field in `Config`
- Location: `src/config.py`
- Issue: same dataclass field declared twice.
- Impact: maintenance confusion and possible accidental override behavior.
- Status: fixed (kept only one declaration).

## P1 (fixed in this round)

1. Notification dead helpers no longer reachable from any path
- Location: `src/notification.py`
- Removed:
  - `_send_chunked_messages`
  - `NotificationBuilder.build_simple_alert`
  - `NotificationBuilder.build_stock_summary`
- Impact: reduced code size and mental overhead without behavior change.
- Status: fixed.

## P2 (recommended next, not yet removed)

1. Low-usage config keys likely legacy or not wired in runtime path
- Candidates from static scan (`usage <= 2` in repo text search):
  - `akshare_sleep_min`
  - `akshare_sleep_max`
  - `tushare_rate_limit_per_minute`
  - `retry_base_delay`
  - `retry_max_delay`
  - `telegram_webhook_secret`
  - `wecom_corpid`
  - `wecom_token`
  - `wecom_encoding_aes_key`
  - `wecom_agent_id`
  - `webui_host`
  - `webui_port`
  - `astrbot_token`
  - `custom_webhook_bearer_token`
  - `pushplus_topic`
- Note: some may be consumed indirectly (env-driven plugins/bot integrations). Confirm before deletion.

2. Core profile config/schema rollout to frontend settings page
- Backend support exists (`profile=core`).
- Settings UI can optionally switch to `core` profile by default to reduce noise.

## Suggested execution order

1. Add runtime/reference verification for low-usage config keys (tests + grep + endpoint exposure).
2. Soft-deprecate uncertain keys in docs first.
3. Remove keys in small batches with migration notes in changelog.

