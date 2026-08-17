#!/usr/bin/env python3
"""
Notify when OMT attachment downloads/uploads fail.
Reads webhook URL from IMA_KEY_EXPIRED_WEBHOOK env or config.json.

Usage:
  python notify_attachment_failed.py --card-id ch01-08 --date 2026-07-22 \
    --topic "节奏时值与休止符时值" \
    --failures '[{"file":"worksheet-two.pdf","url":"https://...","reason":"404 Not Found"}]'
"""
import json, sys, os, argparse, urllib.request, datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(SCRIPT_DIR)


def get_webhook_url():
    url = os.environ.get("IMA_KEY_EXPIRED_WEBHOOK", "").strip()
    if url:
        return url
    cfg_path = os.path.join(SKILL_ROOT, "config.json")
    if os.path.isfile(cfg_path):
        try:
            cfg = json.load(open(cfg_path, encoding="utf-8"))
            return (cfg.get("keyExpiredWebhook") or "").strip()
        except Exception:
            pass
    return ""


def send(card_id, date, topic, failures):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "⚠️ OMT 附件上传失败通知",
        f"时间：{now}",
        f"卡片：{card_id} {topic}",
        f"推送日期：{date}",
        f"失败数量：{len(failures)} 个",
        "",
    ]
    for i, f in enumerate(failures, 1):
        lines.append(f"{i}. {f.get('file', 'unknown')}")
        lines.append(f"   原因：{f.get('reason', 'unknown')}")
        lines.append(f"   链接：{f.get('url', '')}")
        lines.append("")
    lines.append("以上附件未上传至 IMA 知识库，请手动检查链接是否有效。")

    text = "\n".join(lines)
    webhook_url = get_webhook_url()
    if not webhook_url:
        print(json.dumps({"sent": False, "error": "no webhook URL configured"}), file=sys.stderr)
        print(text, file=sys.stderr)
        return 1

    body = json.dumps({
        "msg_type": "text",
        "content": {"text": text}
    }, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(webhook_url, data=body, headers={
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": "omt-daily-push/1.0"
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.load(resp)
        ok = data.get("code") == 0 or data.get("StatusCode") == 0
        print(json.dumps({"sent": True, "ok": ok}, ensure_ascii=False))
        return 0 if ok else 1
    except Exception as e:
        print(json.dumps({"sent": False, "error": str(e)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--card-id", required=True)
    p.add_argument("--date", required=True)
    p.add_argument("--topic", default="")
    p.add_argument("--failures", required=True, help="JSON array of {file,url,reason}")
    args = p.parse_args()
    failures = json.loads(args.failures)
    sys.exit(send(args.card_id, args.date, args.topic, failures))
