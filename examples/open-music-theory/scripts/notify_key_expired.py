#!/usr/bin/env python3
"""
Notify when IMA API key is expired/invalid.

Behavior:
  - Always prints a human-readable notification to stderr and exits with code 1.
  - If the environment variable IMA_KEY_EXPIRED_WEBHOOK is set, POSTs a JSON
    payload to that webhook URL (compatible with Feishu/Lark/Slack custom bots).

Usage:
  python notify_key_expired.py [reason]

No credentials, webhook URLs, or user identifiers are hardcoded.
"""
import json
import os
import sys
import urllib.request
import datetime


def build_text(reason=""):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return (
        "🔔 IMA 知识库 API 密钥失效通知\n"
        f"时间：{now}\n"
        "任务：omt-daily-push 每日双语卡片推送\n"
        f"原因：{reason or 'API 调用返回认证失败（密钥过期或无效）'}\n\n"
        "请提供最新的 IMA OpenAPI 凭证以继续推送：\n"
        "1. 打开 https://ima.qq.com/agent-interface 获取新的 Client ID 和 API Key\n"
        "2. 更新配置：\n"
        '   echo "<新Client ID>" > ~/.config/ima/client_id\n'
        "   printf '%s' \"<新API Key>\" > ~/.config/ima/api_key\n"
        "\n⚠️ 本次卡片推送未完成，不计入进度，凭证更新后将自动重推同一张卡片。"
    )


def send_webhook(url, text):
    """POST text to a generic incoming webhook. Works with Feishu/Lark custom bots."""
    # Feishu/Lark custom bot format
    body = json.dumps({
        "msg_type": "text",
        "content": {"text": text},
    }, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": "omt-daily-push/1.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.load(resp)
        return True, data
    except Exception as e:
        return False, str(e)


def main():
    reason = sys.argv[1] if len(sys.argv) > 1 else ""
    text = build_text(reason)

    # Always notify via stderr so the caller (agent/CI log) sees it.
    print(text, file=sys.stderr)

    # Webhook URL: env var first, then config.json in skill root
    webhook = os.environ.get("IMA_KEY_EXPIRED_WEBHOOK", "").strip()
    if not webhook:
        _skill_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        _cfg_path = os.path.join(_skill_root, 'config.json')
        if os.path.isfile(_cfg_path):
            try:
                _cfg = json.load(open(_cfg_path, encoding='utf-8'))
                webhook = (_cfg.get('keyExpiredWebhook') or '').strip()
            except Exception:
                pass
    webhook_status = {"webhook_configured": bool(webhook)}
    if webhook:
        ok, info = send_webhook(webhook, text)
        webhook_status["webhook_sent"] = ok
        webhook_status["webhook_info"] = info

    # Machine-readable summary on stdout.
    print(json.dumps({
        "event": "ima_key_expired",
        "notified": True,
        **webhook_status,
    }, ensure_ascii=False))
    return 0 if not webhook or webhook_status.get("webhook_sent") else 1


if __name__ == "__main__":
    sys.exit(main())
