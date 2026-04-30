# StarPulse: GitHub Star Growth Detection Plan

## 背景

StarPulse 目标是每天发现 GitHub 上 Star 增长最快的开源项目，核心指标为：

```text
昨日新增 Star = 昨日 WatchEvent 数
```

每天运行一次，聚合前一天 GitHub public events 中的 `WatchEvent`，按仓库维度统计新增 Star 数，并生成日榜。

## 核心问题

1. GitHub 官方 Trending 不等价于日增 Star 排名，口径不透明，不适合作为稳定数据源。
2. 直接调用 GitHub API 扫全站仓库会遇到覆盖和速率限制问题，不适合作为主链路。
3. `昨天 star 总数 - 前天 star 总数` 与 `昨天新增 WatchEvent 数` 口径不同，前者会受 unstar 影响，后者更适合衡量“昨日新增关注热度”。

## 推荐方案

采用 **GH Archive + BigQuery 单日表** 做日聚合。

GH Archive 会按小时归档 GitHub public events。GitHub 用户给仓库加 Star 时，对应事件类型为 `WatchEvent`。因此可以按天聚合 `WatchEvent`，得到仓库的日新增 Star 数。

## 数据源

- GH Archive: https://www.gharchive.org/
- BigQuery Public Datasets: https://docs.cloud.google.com/bigquery/public-data
- GitHub event types: https://docs.github.com/en/rest/using-the-rest-api/github-event-types

## 成本判断

GH Archive 数据公开可用。

推荐通过 BigQuery 查询公共数据集：

1. 数据本身公开。
2. 成本主要来自 BigQuery 查询扫描量。
3. BigQuery 通常有每月免费查询额度，按单日表查询可以控制扫描量。
4. 对“一天一跑，只查昨天 WatchEvent”的场景，成本通常可控。

## 查询口径

建议 MVP 使用，每天保存 Top 500：

```sql
SELECT
  repo.name AS repo_name,
  COUNT(*) AS star_delta
FROM
  `githubarchive.day.YYYYMMDD`
WHERE
  type = 'WatchEvent'
GROUP BY
  repo_name
ORDER BY
  star_delta DESC
LIMIT 500;
```

其中 `YYYYMMDD` 替换为昨天日期，例如 `20260429`。

## 存储方案

MVP 直接使用 SQLite。SQLite 足够支撑每日 Top 500 的历史存储、榜单查询和本地开发，后续如果需要多用户在线服务，再迁移到 PostgreSQL。

数据库文件建议放在：

```text
data/starpulse.sqlite3
```

核心表：

```sql
CREATE TABLE IF NOT EXISTS daily_repo_stars (
  date TEXT NOT NULL,
  repo_name TEXT NOT NULL,
  star_delta INTEGER NOT NULL,
  rank INTEGER NOT NULL,
  html_url TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (date, repo_name)
);

CREATE INDEX IF NOT EXISTS idx_daily_repo_stars_date_rank
  ON daily_repo_stars (date, rank);

CREATE INDEX IF NOT EXISTS idx_daily_repo_stars_repo_date
  ON daily_repo_stars (repo_name, date);
```

说明：

1. `date` 使用 `YYYY-MM-DD` 字符串，便于 SQLite 直接排序和查询。
2. `star_delta` 表示当天新增 Star 事件数，即 `WatchEvent` count。
3. `rank` 表示该仓库在当天 Top 500 中的日榜排名。
4. 使用 `(date, repo_name)` 做主键，支持重复跑同一天任务时 upsert。

## 输出结果

每日任务产出一份榜单，字段建议包括：

- `date`: 榜单日期
- `repo_name`: 仓库名，例如 `owner/repo`
- `star_delta`: 昨日新增 Star 数
- `rank`: 当日排名
- `html_url`: GitHub 仓库链接
- `description`: 仓库描述，可后续补充
- `language`: 主语言，可后续补充
- `topics`: GitHub topics，可后续补充
- `created_at`: 仓库创建时间，可后续补充

MVP 阶段以 SQLite 为准，也可以额外导出 JSON 供前端静态读取：

```text
data/exports/daily/2026-04-29.json
```

## MVP 范围

第一阶段只做日榜生成：

1. 每天定时计算昨天的 `WatchEvent`。
2. 生成 Top 500 日增 Star 仓库。
3. 将结果写入 SQLite。
4. 基于 SQLite 提供日榜、周榜、趋势榜、突然爆发榜。
5. 提供一个简单页面或 API 查询最新榜单。

## 榜单口径

### 日榜

日榜展示指定日期 Top 500 中 Star 增长最快的仓库。

```sql
SELECT
  rank,
  repo_name,
  star_delta,
  html_url
FROM daily_repo_stars
WHERE date = :date
ORDER BY rank ASC
LIMIT :limit;
```

### 周榜

周榜统计最近 7 天累计新增 Star 数。注意这里的覆盖范围只包含每天进入 Top 500 的仓库，因此它是“Top 500 历史样本上的周榜”，不是全 GitHub 完整周榜。后续如果要完整周榜，需要每天保存全量聚合结果，或直接对 GH Archive 查询 7 天数据。

```sql
SELECT
  repo_name,
  SUM(star_delta) AS stars_7d,
  COUNT(*) AS active_days,
  MAX(html_url) AS html_url
FROM daily_repo_stars
WHERE date BETWEEN :start_date AND :end_date
GROUP BY repo_name
ORDER BY stars_7d DESC
LIMIT :limit;
```

### 趋势榜

趋势榜看增长动能，推荐用最近 3 天与之前 3 天对比：

```text
trend_score = recent_3d_stars - previous_3d_stars
trend_ratio = recent_3d_stars / max(previous_3d_stars, 1)
```

排序建议优先使用 `trend_score`，并展示 `trend_ratio` 辅助判断。这样可以避免低基数项目因为从 1 涨到 5 而被过度放大。

```sql
WITH recent AS (
  SELECT repo_name, SUM(star_delta) AS recent_3d_stars
  FROM daily_repo_stars
  WHERE date BETWEEN :recent_start AND :recent_end
  GROUP BY repo_name
),
previous AS (
  SELECT repo_name, SUM(star_delta) AS previous_3d_stars
  FROM daily_repo_stars
  WHERE date BETWEEN :previous_start AND :previous_end
  GROUP BY repo_name
)
SELECT
  recent.repo_name,
  recent.recent_3d_stars,
  COALESCE(previous.previous_3d_stars, 0) AS previous_3d_stars,
  recent.recent_3d_stars - COALESCE(previous.previous_3d_stars, 0) AS trend_score,
  1.0 * recent.recent_3d_stars / MAX(COALESCE(previous.previous_3d_stars, 0), 1) AS trend_ratio,
  MAX(daily_repo_stars.html_url) AS html_url
FROM recent
LEFT JOIN previous ON previous.repo_name = recent.repo_name
JOIN daily_repo_stars ON daily_repo_stars.repo_name = recent.repo_name
WHERE recent.recent_3d_stars >= :min_recent_stars
GROUP BY recent.repo_name
ORDER BY trend_score DESC
LIMIT :limit;
```

### 突然爆发榜

突然爆发榜用于发现“昨日明显异常升温”的项目。推荐使用昨日新增与过去 7 天日均新增对比：

```text
burst_score = yesterday_stars - avg_previous_7d_stars
burst_ratio = yesterday_stars / max(avg_previous_7d_stars, 1)
```

需要设置最小昨日新增阈值，避免小数值噪声：

```text
yesterday_stars >= 20
burst_ratio >= 2
```

```sql
WITH yesterday AS (
  SELECT repo_name, star_delta AS yesterday_stars, html_url
  FROM daily_repo_stars
  WHERE date = :yesterday
),
baseline AS (
  SELECT repo_name, AVG(star_delta) AS avg_previous_7d_stars
  FROM daily_repo_stars
  WHERE date BETWEEN :baseline_start AND :baseline_end
  GROUP BY repo_name
)
SELECT
  yesterday.repo_name,
  yesterday.yesterday_stars,
  COALESCE(baseline.avg_previous_7d_stars, 0) AS avg_previous_7d_stars,
  yesterday.yesterday_stars - COALESCE(baseline.avg_previous_7d_stars, 0) AS burst_score,
  1.0 * yesterday.yesterday_stars / MAX(COALESCE(baseline.avg_previous_7d_stars, 0), 1) AS burst_ratio,
  yesterday.html_url
FROM yesterday
LEFT JOIN baseline ON baseline.repo_name = yesterday.repo_name
WHERE yesterday.yesterday_stars >= :min_yesterday_stars
  AND 1.0 * yesterday.yesterday_stars / MAX(COALESCE(baseline.avg_previous_7d_stars, 0), 1) >= :min_burst_ratio
ORDER BY burst_score DESC
LIMIT :limit;
```

## 每日任务流程

1. 计算目标日期，默认取昨天。
2. 校验日期并拼接 BigQuery 单日表名 `githubarchive.day.YYYYMMDD`。
3. 查询 `WatchEvent` Top 500。
4. 按查询结果顺序生成 `rank`。
5. 使用 SQLite transaction 写入 `daily_repo_stars`。
6. 同一天重复运行时，使用 upsert 覆盖旧结果。
7. 运行榜单查询，生成最新日榜、周榜、趋势榜、突然爆发榜缓存或导出文件。
8. 读取日榜 Top20 和突然爆发榜 Top5，拉取 GitHub 元数据和 README 摘要。
9. 调用 LLM provider 生成简短情报版日报。
10. 保存日报到 SQLite，再推送到钉钉机器人。

SQLite upsert 示例：

```sql
INSERT INTO daily_repo_stars (
  date,
  repo_name,
  star_delta,
  rank,
  html_url,
  created_at
) VALUES (
  :date,
  :repo_name,
  :star_delta,
  :rank,
  :html_url,
  CURRENT_TIMESTAMP
)
ON CONFLICT(date, repo_name) DO UPDATE SET
  star_delta = excluded.star_delta,
  rank = excluded.rank,
  html_url = excluded.html_url,
  created_at = CURRENT_TIMESTAMP;
```

## 大模型日报与钉钉推送

日报目标用户是项目作者本人，用于每天快速了解 GitHub 开源项目增长信号。日报采用简短情报版，不做 Top20 长篇逐项分析。

推送节奏：

```text
每天北京时间 10:00 推送一次
```

日报结构：

1. 今日概览：Top20 总新增 Star、最高增长项目、主要技术方向。
2. 今日重点 3-5 条：从 Top20 和突然爆发榜中提炼最值得关注的项目或技术信号。
3. Top20 表格：展示排名、仓库、昨日新增 Star、语言、一句话介绍。
4. 突然爆发 Top5：展示昨日明显高于历史基线的项目。

### 事实增强

大模型不得只基于 `repo_name` 和 `star_delta` 生成介绍。生成日报前必须先拉取并保存以下事实：

1. GitHub repository description。
2. primary language。
3. topics。
4. license。
5. total stars、forks。
6. README 前若干字符的清洗摘要，例如 4,000-8,000 字符以内。

README 处理规则：

1. 删除 badges、图片、目录、安装日志等低价值内容。
2. 控制长度，避免 LLM token 成本失控。
3. 如果 README 获取失败，只允许模型基于 description、topics、language 总结，并在输入中标记 `readme_available = false`。

### 追加 SQLite 表

```sql
CREATE TABLE IF NOT EXISTS repo_metadata (
  repo_name TEXT PRIMARY KEY,
  html_url TEXT NOT NULL,
  description TEXT,
  language TEXT,
  topics_json TEXT,
  stars INTEGER,
  forks INTEGER,
  license TEXT,
  readme_excerpt TEXT,
  fetched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS daily_reports (
  date TEXT PRIMARY KEY,
  report_markdown TEXT NOT NULL,
  report_json TEXT,
  llm_provider TEXT NOT NULL,
  llm_model TEXT NOT NULL,
  sent_to_dingtalk INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### LLM Provider 抽象

LLM 按 OpenAI-compatible provider 抽象，后续可接 OpenAI、DeepSeek、通义千问兼容接口或其他兼容服务。

环境变量建议：

```text
LLM_PROVIDER=openai-compatible
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=...
LLM_MODEL=...
```

代码接口建议：

```python
class LLMProvider:
    def generate_daily_report(self, *, date, top20, burst_top5):
        ...
```

LLM 输入必须是结构化 JSON，不直接拼接大段自然语言：

```json
{
  "date": "2026-04-29",
  "top20": [
    {
      "rank": 1,
      "repo_name": "owner/repo",
      "star_delta": 123,
      "description": "...",
      "language": "Python",
      "topics": ["ai", "rag"],
      "readme_available": true,
      "readme_excerpt": "..."
    }
  ],
  "burst_top5": []
}
```

模型输出要求：

1. 中文 Markdown。
2. 今日重点 3-5 条，每条说明“为什么值得关注”。
3. Top20 每个项目一句话介绍，最多 40 字。
4. 不编造未出现在输入事实里的功能、公司、融资、作者背景。
5. 信息不足时写“信息不足”，不要猜测。

系统提示词核心约束：

```text
你是开源项目情报分析员。只能基于输入 JSON 中的事实写日报。
如果事实不足，明确写“信息不足”，不要猜测。
不要编造项目用途、作者背景、商业进展、融资信息。
输出简短中文 Markdown。
```

### 钉钉机器人

环境变量建议：

```text
DINGTALK_WEBHOOK_URL=...
DINGTALK_SECRET=...
```

推送策略：

1. Webhook 和 secret 只能放在环境变量或 CI Secret，不能写入代码、配置文件或 SQLite。
2. 推送前先保存 `daily_reports`，避免 LLM 成功但推送失败后无法重试。
3. 推送成功后将 `sent_to_dingtalk` 更新为 `1`。
4. 钉钉消息长度超限时，保留今日概览、重点 3-5 条和 Top20 表格，截断低优先级内容。
5. 推送失败需要记录错误日志，并允许单独重试推送，不重复调用 LLM。

GitHub Actions 定时建议：

```yaml
on:
  schedule:
    - cron: "0 2 * * *"
```

`02:00 UTC` 对应北京时间 `10:00`。

### 推荐模块拆分

```text
src/starpulse/
  bigquery_daily.py       # 查询 GH Archive 单日 Top500
  storage.py              # SQLite schema、upsert、榜单查询
  github_metadata.py      # 拉取 description/topics/language/README
  rankings.py             # 日榜、周榜、趋势榜、突然爆发榜
  llm_provider.py         # OpenAI-compatible LLM 抽象
  report_builder.py       # 组织日报输入、调用 LLM、保存 daily_reports
  dingtalk.py             # 钉钉签名和 webhook 推送

scripts/
  run_daily_pipeline.py   # 每天完整流水线
  retry_dingtalk.py       # 只重试推送
```

## 后续增强

1. 增加 3 日、7 日、30 日增长趋势。
2. 过滤 archived、fork、非开源或异常仓库。
3. 补充仓库元信息：description、language、topics、license、total stars。
4. 增加分类榜：AI、Developer Tools、Frontend、Data、Security 等。
5. 增加异常检测：识别突然爆发项目、疑似刷星项目。
6. 增加订阅推送：邮件、飞书、Webhook、RSS。
7. 对日报增加多 provider fallback，例如主模型失败后切换备用模型。

## 主要风险

1. 正确性风险：`WatchEvent` 表示新增 Star 行为，不等于仓库总 Star 数差值；如果用户 unstar，不会体现在日增事件中。
2. 数据延迟风险：GH Archive 和 BigQuery 公共数据集可能存在同步延迟，任务应允许延后运行或重试。
3. 成本风险：如果查询范围写成多日或全表，BigQuery 扫描量会增加，需要强制限定单日表。
4. 滥用风险：榜单可能被刷星行为影响，后续需要异常检测和过滤策略。
5. 依赖风险：OSSInsight API 可用于快速验证，但 beta API 不适合作为核心生产依赖。
6. 趋势偏差风险：每天只保存 Top 500 会漏掉未上榜仓库，周榜和趋势榜是基于 Top 500 样本的近似结果，不是严格全量结果。
7. 幻觉风险：LLM 必须基于 GitHub description、topics、language、README 摘要生成，不能只基于仓库名生成项目介绍。
8. 密钥风险：LLM API Key、GitHub Token、钉钉 Webhook Secret 不能入库或提交到仓库。
9. 推送噪音风险：Top20 全量长文摘要会降低可读性，因此日报固定为 3-5 条重点 + Top20 表格。

## 命名

项目名：**StarPulse**

含义：捕捉 GitHub 开源项目的 Star 增长脉冲，突出“速度”和“热度变化”，避免与 GitHub 官方 Trending 混淆。

## 推荐技术路线

1. 定时任务：GitHub Actions、Cloud Scheduler 或本地 cron。
2. 数据查询：BigQuery SQL。
3. 数据落库：SQLite。
4. 元数据补充：GitHub REST API，后续可换 GraphQL API。
5. 大模型总结：OpenAI-compatible provider 抽象。
6. 推送：钉钉机器人 Webhook。
7. 后端服务：FastAPI、Node.js API 或 Next.js API routes。
8. 前端展示：日榜、趋势图、仓库详情页。

## MVP 验收标准

1. 每天能自动生成上一自然日的 Star 增长榜。
2. 每天保存 Top 500，榜单中每个仓库有明确的 `repo_name`、`star_delta` 和 `rank`。
3. 查询只扫描指定日期的 GH Archive 单日表。
4. 失败时有日志和重试机制。
5. 结果可以通过 SQLite 查询、JSON 文件或页面访问。
6. 支持日榜、周榜、趋势榜、突然爆发榜四种查询。
7. 每天能为日榜 Top20 拉取 GitHub 元数据和 README 摘要。
8. 每天能生成简短中文情报日报：3-5 条重点 + Top20 表格。
9. 每天北京时间 10:00 能推送到钉钉机器人。
10. 钉钉推送失败时可以复用已保存日报重试，不重复调用 LLM。
