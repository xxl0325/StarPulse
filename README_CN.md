# StarPulse

StarPulse 是一个每天运行的 GitHub star 增长检测项目。它通过 GH Archive + BigQuery 统计上一自然日全站 `WatchEvent`，把日增 Star Top500 保存到 SQLite，再基于历史数据生成日榜、周榜、趋势榜和突然爆发榜。系统还会为 Top20 和爆发榜项目抓取 GitHub 元数据与 README 摘要，用 OpenAI 兼容模型生成简短中文日报，并在每天北京时间 10:00 推送到钉钉机器人。

English documentation: [README.md](./README.md)

## 开源说明

- 仓库不需要提交密钥文件
- 使用 `.env.example` 作为本地配置模板
- `.env`、SQLite 文件、Google Cloud 凭据文件不要提交到版本库
- 本地开发优先使用 ADC
- GitHub Actions 优先使用 Workload Identity Federation，不要长期依赖 service account JSON key

## 功能

- 每天导入 GitHub Top500 star 增长数据
- 使用 SQLite 保存榜单和日报
- 支持日榜、周榜、趋势榜、突然爆发榜
- 补充 GitHub description、topics、language、README 摘要
- 生成简短中文日报
- 推送到钉钉并支持重试

## 本地开发

### 本地环境

- Python 3.11+
- `gcloud` CLI
- 有 BigQuery 权限的 Google Cloud 项目
- 一个 GitHub Personal Access Token
- 一个 OpenAI-compatible LLM 接口
- 一个钉钉机器人 webhook

### 本地认证

推荐使用 ADC：

```bash
gcloud auth application-default login
gcloud auth application-default set-quota-project <your-gcp-project-id>
unset GOOGLE_APPLICATION_CREDENTIALS
```

如果你确实要用 service account JSON，也可以把 `GOOGLE_APPLICATION_CREDENTIALS` 指向本机存在的绝对路径。

### 环境变量

必需变量：

- `GCP_PROJECT`
- `GITHUB_TOKEN`
- `LLM_BASE_URL`
- `LLM_API_KEY`
- `LLM_MODEL`
- `DINGTALK_WEBHOOK_URL`
- `DINGTALK_KEYWORD`

可选变量：

- `TOP_N` 默认 `500`
- `REPORT_TOP_N` 默认 `20`
- `TIMEZONE` 默认 `Asia/Shanghai`
- `SQLITE_PATH` 默认 `data/starpulse.sqlite3`
- `GITHUB_API_BASE_URL` 默认 `https://api.github.com`
- `GITHUB_DAILY_DATASET` 默认 `githubarchive.day`
- `README_EXCERPT_CHARS` 默认 `6000`
- `GOOGLE_APPLICATION_CREDENTIALS` 可选，但如果设置，必须指向真实文件

### 本地命令

只导入每日数据：

```bash
python scripts/import_daily_stars.py --date 2026-04-29
```

运行完整流水线：

```bash
python scripts/run_daily_pipeline.py --date 2026-04-29
```

重发钉钉日报：

```bash
python scripts/retry_dingtalk.py --date 2026-04-29
```

## 部署

### GitHub Actions + Workload Identity Federation

不要再上传长期有效的 Google service account key。推荐用 Workload Identity Federation。

1. 在 Google Cloud 创建 Workload Identity Pool 和 Provider
2. 给 GitHub 仓库身份授予目标 service account 的 `roles/iam.workloadIdentityUser`
3. 给 service account 授予 BigQuery 所需权限，例如 `roles/bigquery.jobUser`
4. 在 GitHub Secrets 中添加：

- `GCP_PROJECT`
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_SERVICE_ACCOUNT_EMAIL`
- `GITHUB_TOKEN_FOR_STARPULSE`
- `LLM_BASE_URL`
- `LLM_API_KEY`
- `LLM_MODEL`
- `DINGTALK_WEBHOOK_URL`
- `DINGTALK_KEYWORD`

### 定时任务

GitHub Actions 默认每天 `02:00 UTC` 执行，对应北京时间 `10:00`。

## 测试

```bash
python -m pytest
```
