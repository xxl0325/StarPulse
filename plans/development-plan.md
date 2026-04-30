# Implementation Plan: StarPulse

## Overview

StarPulse 是一个每日运行的 GitHub 开源项目增长监测系统。它通过 GH Archive + BigQuery 查询上一自然日全 GitHub public `WatchEvent`，保存日增 Star Top500 到 SQLite，并基于历史数据生成日榜、周榜、趋势榜、突然爆发榜。系统还会为日榜 Top20 和突然爆发 Top5 拉取 GitHub 元数据与 README 摘要，通过 OpenAI-compatible LLM provider 生成简短中文情报日报，并在每天北京时间 10:00 推送到钉钉机器人。

## Architecture Decisions

- 使用 BigQuery 查询 GH Archive 单日表：避免 GitHub API 全站扫描的覆盖和限流问题；每次必须只查 `githubarchive.day.YYYYMMDD`。
- 使用 SQLite 作为 MVP 存储：数据规模是每日 Top500，SQLite 足够支撑本地开发、定时任务和简单查询。
- 每天保存 Top500，而不是只保存 Top20：为周榜、趋势榜和突然爆发榜保留历史样本。
- LLM 只负责总结，不负责事实发现：项目介绍必须先由 GitHub metadata + README excerpt 提供事实，降低幻觉风险。
- 推送前先落库日报：LLM 成功但钉钉失败时，可以复用 `daily_reports` 重试，避免重复消耗模型调用。
- 密钥全部走环境变量或 CI Secret：`GCP_PROJECT`、`GOOGLE_APPLICATION_CREDENTIALS`、`GITHUB_TOKEN`、`LLM_API_KEY`、`DINGTALK_WEBHOOK_URL`、`DINGTALK_SECRET` 不写入代码和数据库。

## Dependency Graph

```text
Project scaffold and config
    │
    ├── SQLite schema and storage layer
    │       │
    │       ├── Ranking queries
    │       │       │
    │       │       └── Report input assembly
    │       │
    │       └── Daily BigQuery import
    │               │
    │               └── Daily pipeline
    │
    ├── GitHub metadata fetcher
    │       │
    │       └── Report input assembly
    │
    ├── LLM provider
    │       │
    │       └── Daily report builder
    │
    └── DingTalk notifier
            │
            └── Daily pipeline and retry script
```

## Task List

### Phase 1: Project Foundation

## Task 1: Scaffold Python Project

**Description:** Create the minimal Python project structure, dependency config, package layout, and command entry points needed for the rest of the implementation.

**Acceptance criteria:**
- [ ] Project has `pyproject.toml` with runtime dependencies and test dependencies.
- [ ] Package exists under `src/starpulse/`.
- [ ] Scripts directory exists with planned command files.

**Verification:**
- [ ] Tests command runs, even if only a placeholder test exists: `python -m pytest`.
- [ ] Import check passes: `python -c "import starpulse"`.

**Dependencies:** None

**Files likely touched:**
- `pyproject.toml`
- `src/starpulse/__init__.py`
- `scripts/run_daily_pipeline.py`
- `tests/test_imports.py`

**Estimated scope:** Small: 3-5 files

## Task 2: Add Configuration Loader

**Description:** Implement centralized environment configuration for BigQuery, GitHub, LLM, DingTalk, SQLite path, default limits, and timezone behavior.

**Acceptance criteria:**
- [ ] Required and optional environment variables are documented in code.
- [ ] Missing required variables fail with clear errors only when the related feature is used.
- [ ] Defaults exist for `TOP_N=500`, `REPORT_TOP_N=20`, `TIMEZONE=Asia/Shanghai`, and SQLite path.

**Verification:**
- [ ] Unit tests cover default values.
- [ ] Unit tests cover missing required values for BigQuery, GitHub, LLM, and DingTalk.

**Dependencies:** Task 1

**Files likely touched:**
- `src/starpulse/config.py`
- `tests/test_config.py`

**Estimated scope:** Small: 2 files

## Task 3: Implement Date Utilities

**Description:** Add date handling for target date calculation, BigQuery table suffix generation, and validation of `YYYY-MM-DD` and `YYYYMMDD`.

**Acceptance criteria:**
- [ ] Default target date is yesterday in configured timezone.
- [ ] BigQuery table suffix is strictly validated as 8 digits.
- [ ] Invalid date input raises a clear error.

**Verification:**
- [ ] Unit tests cover default yesterday calculation with fixed clock.
- [ ] Unit tests reject malformed table suffixes.

**Dependencies:** Task 1

**Files likely touched:**
- `src/starpulse/dates.py`
- `tests/test_dates.py`

**Estimated scope:** Small: 2 files

### Checkpoint: Foundation

- [ ] `python -m pytest` passes.
- [ ] Project imports cleanly.
- [ ] No external API calls are required for tests.

### Phase 2: SQLite Storage and Rankings

## Task 4: Implement SQLite Schema

**Description:** Create the SQLite schema for `daily_repo_stars`, `repo_metadata`, and `daily_reports`, including indexes and idempotent initialization.

**Acceptance criteria:**
- [ ] `init_db()` creates all tables and indexes.
- [ ] Calling `init_db()` multiple times is safe.
- [ ] Database path parent directory is created when missing.

**Verification:**
- [ ] Unit tests create a temporary SQLite database and assert table/index existence.

**Dependencies:** Task 2

**Files likely touched:**
- `src/starpulse/storage.py`
- `tests/test_storage_schema.py`

**Estimated scope:** Medium: 2-3 files

## Task 5: Implement Daily Stars Upsert

**Description:** Add storage functions to upsert daily Top500 rows into `daily_repo_stars` with deterministic ranks and transaction handling.

**Acceptance criteria:**
- [ ] Inserts daily rows with `date`, `repo_name`, `star_delta`, `rank`, and `html_url`.
- [ ] Re-running the same date updates existing rows without duplicates.
- [ ] Transaction rolls back on failure.

**Verification:**
- [ ] Unit tests cover insert, update, and duplicate prevention.
- [ ] Unit tests verify `(date, repo_name)` primary key behavior.

**Dependencies:** Task 4

**Files likely touched:**
- `src/starpulse/storage.py`
- `tests/test_daily_upsert.py`

**Estimated scope:** Small: 2 files

## Task 6: Implement Ranking Queries

**Description:** Implement query functions for日榜、周榜、趋势榜、突然爆发榜 based on `daily_repo_stars`.

**Acceptance criteria:**
- [ ] Daily ranking returns rows ordered by `rank`.
- [ ] Weekly ranking sums `star_delta` across the requested 7-day window.
- [ ] Trend ranking computes recent 3-day vs previous 3-day score and ratio.
- [ ] Burst ranking compares yesterday against previous 7-day average with thresholds.

**Verification:**
- [ ] Unit tests seed fixture data and assert ranking order and computed scores.
- [ ] Tests document that weekly/trend rankings are based on saved Top500 samples, not full GitHub history.

**Dependencies:** Task 5

**Files likely touched:**
- `src/starpulse/rankings.py`
- `tests/test_rankings.py`

**Estimated scope:** Medium: 2-3 files

### Checkpoint: Storage and Rankings

- [ ] SQLite schema is stable.
- [ ] Ranking queries pass fixture-based tests.
- [ ] Top500 sample limitation is documented in tests or docstrings.

### Phase 3: BigQuery Daily Import

## Task 7: Build BigQuery SQL Generator

**Description:** Generate the GH Archive SQL for one validated date and limit, without exposing table-name injection risk.

**Acceptance criteria:**
- [ ] SQL reads only `repo.name` and `type`.
- [ ] SQL uses exactly one table: `githubarchive.day.YYYYMMDD`.
- [ ] Limit is validated as a positive integer within a configured max.

**Verification:**
- [ ] Unit tests assert generated SQL for a known date.
- [ ] Unit tests reject malformed dates and unsafe suffixes.

**Dependencies:** Task 3

**Files likely touched:**
- `src/starpulse/bigquery_daily.py`
- `tests/test_bigquery_sql.py`

**Estimated scope:** Small: 2 files

## Task 8: Implement BigQuery Client Runner

**Description:** Execute the generated SQL via Google BigQuery client and normalize rows into internal daily star records.

**Acceptance criteria:**
- [ ] BigQuery client uses configured `GCP_PROJECT`.
- [ ] Returned records include `repo_name`, `star_delta`, `rank`, and `html_url`.
- [ ] BigQuery failures surface clear errors and do not partially write SQLite data.

**Verification:**
- [ ] Unit tests mock BigQuery client results.
- [ ] Unit tests verify rank assignment from query order.

**Dependencies:** Task 7

**Files likely touched:**
- `src/starpulse/bigquery_daily.py`
- `tests/test_bigquery_daily.py`

**Estimated scope:** Medium: 2-3 files

## Task 9: Add Daily Import Script

**Description:** Create a CLI command that imports one target date from BigQuery into SQLite.

**Acceptance criteria:**
- [ ] Supports `--date YYYY-MM-DD`.
- [ ] Defaults to yesterday when `--date` is omitted.
- [ ] Supports `--limit`, defaulting to 500.
- [ ] Prints a concise summary of imported row count.

**Verification:**
- [ ] CLI unit/integration test runs against mocked BigQuery and temporary SQLite.
- [ ] Manual dry run documents required environment variables.

**Dependencies:** Task 5, Task 8

**Files likely touched:**
- `scripts/import_daily_stars.py`
- `src/starpulse/cli.py`
- `tests/test_import_daily_cli.py`

**Estimated scope:** Medium: 3-4 files

### Checkpoint: Daily Import

- [ ] `python -m pytest` passes.
- [ ] Mocked daily import writes Top500-style rows to SQLite.
- [ ] Generated SQL is confirmed to scan only a single GH Archive day table.

### Phase 4: GitHub Metadata Enrichment

## Task 10: Implement GitHub Repository Metadata Fetcher

**Description:** Fetch repository description, primary language, topics, stars, forks, license, and HTML URL for a repo.

**Acceptance criteria:**
- [ ] Uses `GITHUB_TOKEN` when available.
- [ ] Handles rate limits and missing repositories with explicit errors or skipped records.
- [ ] Normalizes metadata into a stable internal structure.

**Verification:**
- [ ] Unit tests mock GitHub API responses for success, not found, and rate-limited cases.

**Dependencies:** Task 2

**Files likely touched:**
- `src/starpulse/github_metadata.py`
- `tests/test_github_metadata.py`

**Estimated scope:** Medium: 2-3 files

## Task 11: Implement README Fetch and Cleaning

**Description:** Fetch README content for a repo, remove low-value markdown noise, and truncate to a configured excerpt length.

**Acceptance criteria:**
- [ ] Extracts README text when available.
- [ ] Removes badges/images and obvious table-of-contents noise.
- [ ] Truncates to 4,000-8,000 characters based on config.
- [ ] Marks `readme_available = false` when missing or inaccessible.

**Verification:**
- [ ] Unit tests cover markdown cleaning and truncation.
- [ ] Unit tests cover missing README behavior.

**Dependencies:** Task 10

**Files likely touched:**
- `src/starpulse/github_metadata.py`
- `tests/test_readme_cleaning.py`

**Estimated scope:** Medium: 2-3 files

## Task 12: Store and Refresh Metadata for Report Candidates

**Description:** Save metadata into `repo_metadata` for daily Top20 and burst Top5, with cache freshness rules.

**Acceptance criteria:**
- [ ] Fetches metadata for union of Top20 and burst Top5.
- [ ] Upserts `repo_metadata`.
- [ ] Avoids refetching recently fetched metadata unless forced.

**Verification:**
- [ ] Unit tests cover upsert and cache skip behavior.
- [ ] Integration test uses temporary SQLite and mocked GitHub client.

**Dependencies:** Task 6, Task 10, Task 11

**Files likely touched:**
- `src/starpulse/storage.py`
- `src/starpulse/github_metadata.py`
- `tests/test_metadata_refresh.py`

**Estimated scope:** Medium: 3 files

### Checkpoint: Metadata

- [ ] Report candidate metadata is present in SQLite.
- [ ] README failure does not block report generation.
- [ ] GitHub token is never logged.

### Phase 5: LLM Report Generation

## Task 13: Implement OpenAI-Compatible LLM Provider

**Description:** Add an LLM provider abstraction that calls an OpenAI-compatible chat endpoint using configured base URL, API key, and model.

**Acceptance criteria:**
- [ ] Provider reads `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL`.
- [ ] Provider sends structured JSON input and system prompt constraints.
- [ ] Provider returns Markdown text.
- [ ] API key is never logged.

**Verification:**
- [ ] Unit tests mock HTTP response.
- [ ] Unit tests assert request contains no unsupported freeform repo-name-only prompt.

**Dependencies:** Task 2

**Files likely touched:**
- `src/starpulse/llm_provider.py`
- `tests/test_llm_provider.py`

**Estimated scope:** Medium: 2-3 files

## Task 14: Build Daily Report Input

**Description:** Assemble the report input from日榜 Top20、突然爆发 Top5、and `repo_metadata`.

**Acceptance criteria:**
- [ ] Top20 records include rank, repo, star delta, language, topics, description, and README excerpt availability.
- [ ] Burst Top5 records are included separately.
- [ ] Missing metadata is represented explicitly instead of guessed.

**Verification:**
- [ ] Unit tests seed SQLite and assert JSON input shape.

**Dependencies:** Task 6, Task 12

**Files likely touched:**
- `src/starpulse/report_builder.py`
- `tests/test_report_input.py`

**Estimated scope:** Medium: 2-3 files

## Task 15: Generate and Store Daily Report

**Description:** Call the LLM provider, validate the report shape enough for safe delivery, and store it in `daily_reports`.

**Acceptance criteria:**
- [ ] Report is saved with date, markdown, JSON input, provider, model, and `sent_to_dingtalk = 0`.
- [ ] Re-running the same date updates the stored report.
- [ ] LLM failure does not mark the report as sent.

**Verification:**
- [ ] Unit tests mock LLM output and assert database row.
- [ ] Unit tests cover LLM failure path.

**Dependencies:** Task 13, Task 14

**Files likely touched:**
- `src/starpulse/report_builder.py`
- `src/starpulse/storage.py`
- `tests/test_report_builder.py`

**Estimated scope:** Medium: 3 files

### Checkpoint: Report Generation

- [ ] Report generation works with mocked LLM.
- [ ] Report input contains only fact-backed metadata.
- [ ] Stored report can be reused without re-calling LLM.

### Phase 6: DingTalk Delivery

## Task 16: Implement DingTalk Webhook Client

**Description:** Implement DingTalk robot webhook delivery, including optional secret signing.

**Acceptance criteria:**
- [ ] Reads webhook URL and secret from environment/config.
- [ ] Signs request when `DINGTALK_SECRET` is configured.
- [ ] Sends Markdown content.
- [ ] Raises clear error on non-success response.

**Verification:**
- [ ] Unit tests cover signature generation.
- [ ] Unit tests mock webhook success and failure.

**Dependencies:** Task 2

**Files likely touched:**
- `src/starpulse/dingtalk.py`
- `tests/test_dingtalk.py`

**Estimated scope:** Small: 2 files

## Task 17: Send Stored Report and Mark Delivery

**Description:** Load a report from `daily_reports`, send it to DingTalk, and update `sent_to_dingtalk`.

**Acceptance criteria:**
- [ ] Sends an existing stored report without calling LLM.
- [ ] Marks `sent_to_dingtalk = 1` only after successful webhook response.
- [ ] Failed send leaves report available for retry.

**Verification:**
- [ ] Unit tests cover successful send and failed send.

**Dependencies:** Task 15, Task 16

**Files likely touched:**
- `src/starpulse/report_delivery.py`
- `src/starpulse/storage.py`
- `tests/test_report_delivery.py`

**Estimated scope:** Medium: 2-3 files

## Task 18: Add Retry DingTalk Script

**Description:** Create a CLI script to resend an existing stored report for a date without regenerating it.

**Acceptance criteria:**
- [ ] Supports `--date YYYY-MM-DD`.
- [ ] Fails clearly if no report exists for the date.
- [ ] Does not call BigQuery, GitHub, or LLM.

**Verification:**
- [ ] CLI test confirms only delivery path is executed.

**Dependencies:** Task 17

**Files likely touched:**
- `scripts/retry_dingtalk.py`
- `tests/test_retry_dingtalk_cli.py`

**Estimated scope:** Small: 2 files

### Checkpoint: Delivery

- [ ] Stored report can be sent to mocked DingTalk.
- [ ] Retry script works without LLM.
- [ ] DingTalk secret is never printed.

### Phase 7: End-to-End Pipeline and Scheduling

## Task 19: Compose Daily Pipeline

**Description:** Implement `run_daily_pipeline.py` to run the full sequence: import Top500, compute rankings, refresh metadata, generate report, and send DingTalk notification.

**Acceptance criteria:**
- [ ] Supports `--date YYYY-MM-DD`.
- [ ] Supports flags to skip LLM or skip DingTalk for local testing.
- [ ] Each stage logs concise progress and row counts.
- [ ] A failure in later stages does not corrupt earlier SQLite writes.

**Verification:**
- [ ] Integration test runs the pipeline with mocked BigQuery, GitHub, LLM, and DingTalk.

**Dependencies:** Task 9, Task 12, Task 15, Task 17

**Files likely touched:**
- `scripts/run_daily_pipeline.py`
- `src/starpulse/pipeline.py`
- `tests/test_pipeline.py`

**Estimated scope:** Medium: 3-4 files

## Task 20: Add GitHub Actions Schedule

**Description:** Configure CI scheduling to run the daily pipeline every day at `02:00 UTC`, which is北京时间 `10:00`.

**Acceptance criteria:**
- [ ] Workflow installs dependencies and runs tests.
- [ ] Scheduled job runs daily pipeline.
- [ ] Secrets are referenced from GitHub Actions secrets.
- [ ] Workflow avoids committing secrets or generated credentials.

**Verification:**
- [ ] YAML syntax validates.
- [ ] Manual workflow dispatch can run with a specified date.

**Dependencies:** Task 19

**Files likely touched:**
- `.github/workflows/daily.yml`

**Estimated scope:** Small: 1 file

## Task 21: Add Operational Documentation

**Description:** Document local setup, required cloud credentials, quota controls, environment variables, and common operations.

**Acceptance criteria:**
- [ ] README explains how to create/use `GCP_PROJECT`.
- [ ] README explains BigQuery custom query quota recommendation.
- [ ] README lists required secrets for GitHub Actions.
- [ ] README documents local dry-run and DingTalk retry.

**Verification:**
- [ ] Fresh setup instructions are runnable from a clean checkout.

**Dependencies:** Task 19, Task 20

**Files likely touched:**
- `README.md`
- `.env.example`

**Estimated scope:** Medium: 2 files

### Checkpoint: Complete MVP

- [ ] All tests pass: `python -m pytest`.
- [ ] Pipeline works end-to-end with mocked external services.
- [ ] Manual run can import a real date when credentials are configured.
- [ ] GitHub Actions has daily schedule for北京时间 10:00.
- [ ] DingTalk retry does not regenerate LLM report.

## Parallelization Opportunities

- Tasks 4-6 can be implemented while Tasks 7-8 are developed, after Task 1 and Task 2 are stable.
- Tasks 10-12 can be implemented in parallel with Tasks 13-15 once storage interfaces are defined.
- Task 16 can be implemented independently after Task 2.
- Task 21 can start once config names and CLI commands stabilize.

## Must Be Sequential

- SQLite schema must land before storage upsert and ranking queries.
- BigQuery SQL validation must land before real BigQuery execution.
- Metadata fetch must land before LLM report input.
- Daily report storage must land before DingTalk retry.
- Pipeline composition must wait until import, metadata, LLM, and delivery are each testable.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| BigQuery SQL accidentally scans too much data | High | Generate table name only from validated `YYYYMMDD`; add tests asserting single-day table usage; configure BigQuery custom query quota. |
| LLM hallucinates project purpose | High | Fetch GitHub description/topics/language/README first; prompt says facts-only; input uses structured JSON; missing facts become `信息不足`. |
| Secrets leak into repo, logs, or SQLite | High | Read secrets only from env/CI Secret; redact logs; never persist token values. |
| Top500 sample biases weekly/trend rankings | Medium | Document ranking scope clearly; later consider saving full daily aggregation or querying multi-day GH Archive when needed. |
| GH Archive/BigQuery data delay | Medium | Run at北京时间 10:00; allow manual rerun by date; upsert same date idempotently. |
| GitHub API rate limit blocks metadata | Medium | Fetch only Top20 + burst Top5; cache `repo_metadata`; use `GITHUB_TOKEN`; tolerate missing README. |
| DingTalk push fails after LLM succeeds | Medium | Save report before push; provide `retry_dingtalk.py` that does not call LLM. |
| Report becomes too long for DingTalk | Low | Use concise Markdown; cap Top20 summaries at 40 Chinese chars; truncate low-priority sections first. |

## Open Questions

- 是否第一版需要前端页面，还是先只保留 SQLite + 钉钉日报 + CLI 查询？
- SQLite 数据库是否需要提交到仓库，还是作为运行产物保存在服务器/Actions artifact？
- GitHub Actions 运行时是否有持久化 SQLite 的位置？如果没有，需要选择 artifact、对象存储、或改为部署到固定服务器运行。
- LLM 首选 provider 和模型名称是什么？
- 钉钉机器人是否启用加签模式？建议启用。

## Not Doing in MVP

- 不做全 GitHub 完整周榜：MVP 的周榜和趋势榜基于每日 Top500 样本。
- 不做用户系统和多租户配置：当前目标用户是项目作者本人。
- 不做复杂前端：先保证数据链路和钉钉日报稳定。
- 不做刷星检测模型：先保留突然爆发榜和风险提示，后续再做异常检测。
- 不做多推送渠道：MVP 只做钉钉机器人。

## Implementation Order Summary

1. Foundation: Tasks 1-3
2. SQLite and rankings: Tasks 4-6
3. BigQuery import: Tasks 7-9
4. GitHub metadata: Tasks 10-12
5. LLM report: Tasks 13-15
6. DingTalk delivery: Tasks 16-18
7. Pipeline and scheduling: Tasks 19-21
