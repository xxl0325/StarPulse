# StarPulse

StarPulse is a daily GitHub star-growth detector. It queries GH Archive through BigQuery, stores daily Top500 results in SQLite, enriches the top projects with GitHub metadata, generates a short Chinese intelligence report with an OpenAI-compatible model, and pushes the report to DingTalk every day at 10:00 Beijing time.

Chinese documentation: [README_CN.md](./README_CN.md)

## Open Source Notes

- The repository does not require checked-in secrets.
- Use `.env.example` as the local configuration template.
- Keep `.env`, SQLite files, and any Google Cloud credential material out of version control.
- Prefer Application Default Credentials for local development.
- For GitHub Actions, move Google authentication to Workload Identity Federation before public release if you want to avoid long-lived service account keys.

## What it does

- Daily Top500 star growth import
- SQLite storage for rankings and reports
- Weekly, trend, and burst rankings
- GitHub description, topics, language, README excerpt enrichment
- Short daily report generation
- DingTalk delivery and retry

## Development

### Local prerequisites

- Python 3.11 or newer
- `gcloud` CLI
- A Google Cloud project with BigQuery access
- A GitHub personal access token for metadata fetches
- An OpenAI-compatible LLM endpoint
- A DingTalk robot webhook

### Local authentication

Use Application Default Credentials for local development:

```bash
gcloud auth application-default login
gcloud auth application-default set-quota-project <your-gcp-project-id>
unset GOOGLE_APPLICATION_CREDENTIALS
```

If you prefer a service account JSON for local testing, set `GOOGLE_APPLICATION_CREDENTIALS` to the absolute path of the file. The path must exist.

### Environment variables

Core variables:

- `GCP_PROJECT`
- `GITHUB_TOKEN`
- `LLM_BASE_URL`
- `LLM_API_KEY`
- `LLM_MODEL`
- `DINGTALK_WEBHOOK_URL`
- `DINGTALK_KEYWORD`

Optional variables:

- `TOP_N` defaults to `500`
- `REPORT_TOP_N` defaults to `20`
- `TIMEZONE` defaults to `Asia/Shanghai`
- `SQLITE_PATH` defaults to `data/starpulse.sqlite3`
- `GITHUB_API_BASE_URL` defaults to `https://api.github.com`
- `GITHUB_DAILY_DATASET` defaults to `githubarchive.day`
- `README_EXCERPT_CHARS` defaults to `6000`
- `GOOGLE_APPLICATION_CREDENTIALS` is optional for local development, but when set it must point to a real file

## Deployment

### GitHub Actions with Workload Identity Federation

Use Workload Identity Federation instead of a long-lived Google service account key.

1. Create a Workload Identity Pool and Provider in Google Cloud.
2. Grant the GitHub repository identity `roles/iam.workloadIdentityUser` on the target service account.
3. Grant the service account BigQuery permissions such as `roles/bigquery.jobUser`.
4. Add these GitHub Actions secrets:

- `GCP_PROJECT`
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_SERVICE_ACCOUNT_EMAIL`
- `GITHUB_TOKEN_FOR_STARPULSE`
- `LLM_BASE_URL`
- `LLM_API_KEY`
- `LLM_MODEL`
- `DINGTALK_WEBHOOK_URL`
- `DINGTALK_KEYWORD`

### Scheduled workflow

The scheduled workflow runs daily at `02:00 UTC`, which is `10:00` Beijing time.

## Setup

1. Copy `.env.example` and fill in the values.
2. Install dependencies.
3. Make sure `GCP_PROJECT` is set. If you use a service account file, `GOOGLE_APPLICATION_CREDENTIALS` must point to an existing JSON file. If you use `gcloud auth application-default login`, you can leave that variable unset.
4. Provide `GITHUB_TOKEN`, `LLM_API_KEY`, `LLM_MODEL`, `DINGTALK_WEBHOOK_URL`, and `DINGTALK_KEYWORD`.

## Release Checklist

- Remove any local `.env` file before publishing or ensure it stays untracked.
- Rotate any tokens that were used during development.
- Verify that no secrets appear in git history.
- Use Workload Identity Federation for GitHub Actions; do not publish long-lived Google service account keys.

## Local commands

Import a daily snapshot only:

```bash
python scripts/import_daily_stars.py --date 2026-04-29
```

Run the full pipeline:

```bash
python scripts/run_daily_pipeline.py --date 2026-04-29
```

Retry DingTalk delivery without regenerating the report:

```bash
python scripts/retry_dingtalk.py --date 2026-04-29
```

## Configuration notes

- BigQuery should query only a single GH Archive day table per run
- Keep secrets out of the repository and out of SQLite
- DingTalk keyword mode is supported; `github` is the default keyword

## Tests

```bash
python -m pytest
```
