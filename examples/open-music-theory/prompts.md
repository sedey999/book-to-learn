# 定时任务配置建议

本 skill 不内置任何定时任务（cron job）。公开发布版不硬编码任何 agent 平台的 job ID。

## 建议调度方案

根据你使用的 agent 平台自行设置：

### OpenClaw cron 示例

```jsonc
// 每天 18:30 主推送
{
  "name": "omt-daily-push",
  "schedule": { "kind": "cron", "expr": "30 18 * * *", "tz": "Asia/Shanghai" },
  "payload": {
    "kind": "agentTurn",
    "message": "执行 omt-daily-push skill，按 SKILL.md Step 1~10 推送今日乐理卡片。"
  },
  "sessionTarget": "isolated"
}
```

### crontab 示例

```cron
30 18 * * * cd /path/to/skills/omt-daily-push && /path/to/agent "执行 omt-daily-push 推送今日乐理卡片" >> /var/log/omt-push.log 2>&1
```

### GitHub Actions 示例

```yaml
on:
  schedule:
    - cron: '30 10 * * *'  # 18:30 Asia/Shanghai = 10:30 UTC
jobs:
  push:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      # 调用你的 agent CLI 执行 skill
```

## 监督/重试任务（可选）

主推送后 1 小时，可安排一次检查任务：
- 读取 `progress.json`，若 `lastPushDate != today`，则重跑推送
- 失败则通过 webhook 通知（见 SKILL.md「密钥失效 webhook 通知」）
