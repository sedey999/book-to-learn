#!/usr/bin/env python3
"""
Send knowledge cards or images directly to Feishu chats via Feishu Open API.
Alternative to webhook — supports multimedia (images, files) natively.

Requires: Feishu App ID + App Secret (create a custom app at https://open.feishu.cn/app)
Config in config.json:
  "pushMethod": "feishu-api"
  "feishuApi": {
    "appId": "cli_xxxxx",
    "appSecret": "xxxxx",
    "chatId": "oc_xxxxx"        // group chat or personal chat ID
  }

Usage:
  # Send interactive card (same as webhook but via API)
  python send_feishu_api.py --payload <payload.json> [--zh <zh.json>] --config <config.json> [--language <zh|en>]

  # Send a standalone image (e.g. from gen_image.py)
  python send_feishu_api.py --image <path.png> --config <config.json>

  # Send a PDF file
  python send_feishu_api.py --file <path.pdf> --config <config.json>
"""
import json, sys, os, argparse, urllib.request, urllib.parse, base64, re, time
from normalize_quotes import normalize_all

FEISHU_BASE = 'https://open.feishu.cn/open-apis'


def load_config(path):
    return json.load(open(path, encoding='utf-8'))


def esc_md(text):
    """Escape special chars for Feishu markdown.
    | would break markdown tables (terminology table), so escape it too."""
    if not text: return ''
    return (text.replace('\\', '\\\\').replace('*', '\\*').replace('_', '\\_')
                .replace('[', '\\[').replace('|', '\\|'))


def md_links_to_feishu(text):
    """Convert markdown [text](url) to Feishu-compatible link text (url)."""
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)', lambda m: '%s (%s)' % (m.group(1), m.group(2)), text or '')


def decode_data_uri(data_uri):
    """Extract (bytes, ext) from a data:image/...;base64,... URI."""
    m = re.match(r'data:image/(\w+);base64,(.+)', data_uri or '', re.S)
    if not m:
        return None, None
    ext = m.group(1)
    if ext == 'jpeg': ext = 'jpg'
    try:
        return base64.b64decode(m.group(2)), ext
    except Exception:
        return None, None


def get_tenant_access_token(app_id, app_secret):
    """Get tenant_access_token from Feishu Open API."""
    url = f'{FEISHU_BASE}/auth/v3/tenant_access_token/internal'
    body = json.dumps({'app_id': app_id, 'app_secret': app_secret}).encode('utf-8')
    req = urllib.request.Request(url, data=body, headers={
        'Content-Type': 'application/json; charset=utf-8',
        'User-Agent': 'Mozilla/5.0'
    })
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.load(resp)
        if data.get('code') == 0:
            token = data.get('tenant_access_token')
            expires = data.get('expire', 7200)
            return token, expires
        else:
            print(json.dumps({'ok': False, 'error': f'Auth failed: {data.get("msg", "unknown")}'}, ensure_ascii=False))
            return None, 0
    except Exception as e:
        print(json.dumps({'ok': False, 'error': f'Auth request failed: {e}'}, ensure_ascii=False))
        return None, 0


def upload_image(token, image_path):
    """Upload an image file to Feishu and get image_key."""
    url = f'{FEISHU_BASE}/im/v1/images'
    with open(image_path, 'rb') as f:
        image_data = f.read()

    img_ext = os.path.splitext(image_path)[1].lstrip('.').lower() or 'png'
    img_mime = 'image/png' if img_ext == 'png' else ('image/jpeg' if img_ext in ('jpg','jpeg') else 'image/%s' % img_ext)
    boundary = '----feishuapi' + str(hash(image_data) % 100000)
    body = b''
    body += ('--%s\r\n' % boundary).encode()
    body += b'Content-Disposition: form-data; name="image_type"\r\n\r\n'
    body += b'message\r\n'
    body += ('--%s\r\n' % boundary).encode()
    body += ('Content-Disposition: form-data; name="image"; filename="%s"\r\n' % os.path.basename(image_path)).encode()
    body += b'Content-Type: image/png\r\n\r\n'
    body += image_data
    body += ('\r\n--%s--\r\n' % boundary).encode()

    req = urllib.request.Request(url, data=body, headers={
        'Content-Type': f'multipart/form-data; boundary={boundary}',
        'Authorization': f'Bearer {token}',
        'User-Agent': 'Mozilla/5.0'
    })
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        data = json.load(resp)
        if data.get('code') == 0:
            return data.get('data', {}).get('image_key')
        else:
            print(json.dumps({'ok': False, 'error': f'Image upload failed: {data.get("msg", "unknown")}'}, ensure_ascii=False))
            return None
    except Exception as e:
        print(json.dumps({'ok': False, 'error': f'Image upload request failed: {e}'}, ensure_ascii=False))
        return None


def upload_file(token, file_path):
    """Upload a file (e.g. PDF) to Feishu and get file_key."""
    url = f'{FEISHU_BASE}/im/v1/files'
    with open(file_path, 'rb') as f:
        file_data = f.read()

    ext = os.path.splitext(file_path)[1].lstrip('.').lower()
    file_type = {'pdf': 'pdf', 'doc': 'doc', 'docx': 'doc',
                 'xls': 'xls', 'xlsx': 'xls',
                 'ppt': 'ppt', 'pptx': 'ppt',
                 'mp4': 'mp4', 'opus': 'opus'}.get(ext, 'stream')

    boundary = '----feishuapi' + str(hash(file_data) % 100000)
    body = b''
    body += ('--%s\r\n' % boundary).encode()
    body += b'Content-Disposition: form-data; name="file_type"\r\n\r\n'
    body += f'{file_type}\r\n'.encode()
    body += ('--%s\r\n' % boundary).encode()
    body += ('Content-Disposition: form-data; name="file_name"\r\n\r\n').encode()
    body += f'{os.path.basename(file_path)}\r\n'.encode()
    body += ('--%s\r\n' % boundary).encode()
    body += ('Content-Disposition: form-data; name="file"; filename="%s"\r\n' % os.path.basename(file_path)).encode()
    body += f'Content-Type: application/{ {"doc":"msword","docx":"msword","xls":"vnd.ms-excel","xlsx":"vnd.ms-excel","ppt":"vnd.ms-powerpoint","pptx":"vnd.ms-powerpoint","pdf":"pdf"}.get(ext, "octet-stream") }\r\n\r\n'.encode()
    body += file_data
    body += ('\r\n--%s--\r\n' % boundary).encode()

    req = urllib.request.Request(url, data=body, headers={
        'Content-Type': f'multipart/form-data; boundary={boundary}',
        'Authorization': f'Bearer {token}',
        'User-Agent': 'Mozilla/5.0'
    })
    try:
        resp = urllib.request.urlopen(req, timeout=60)
        data = json.load(resp)
        if data.get('code') == 0:
            return data.get('data', {}).get('file_key')
        else:
            print(json.dumps({'ok': False, 'error': f'File upload failed: {data.get("msg", "unknown")}'}, ensure_ascii=False))
            return None
    except Exception as e:
        print(json.dumps({'ok': False, 'error': f'File upload request failed: {e}'}, ensure_ascii=False))
        return None


def send_message(token, chat_id, msg_type, content):
    """Send a message to a Feishu chat via Open API."""
    url = f'{FEISHU_BASE}/im/v1/messages?receive_id_type=chat_id'
    body = json.dumps({
        'receive_id': chat_id,
        'msg_type': msg_type,
        'content': json.dumps(content, ensure_ascii=False)
    }, ensure_ascii=False).encode('utf-8')

    req = urllib.request.Request(url, data=body, headers={
        'Content-Type': 'application/json; charset=utf-8',
        'Authorization': f'Bearer {token}',
        'User-Agent': 'Mozilla/5.0'
    })
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        data = json.load(resp)
        if data.get('code') == 0:
            print(json.dumps({'sent': True, 'ok': True, 'msg_type': msg_type,
                              'message_id': data.get('data', {}).get('message_id', '')},
                             ensure_ascii=False))
            return 0
        else:
            print(json.dumps({'sent': False, 'ok': False,
                              'error': data.get('msg', 'unknown'),
                              'code': data.get('code', -1)}, ensure_ascii=False))
            return 1
    except Exception as e:
        print(json.dumps({'sent': False, 'error': f'Send message failed: {e}'}, ensure_ascii=False))
        return 1


def build_card_content(payload, zh, language='en'):
    """Build Feishu interactive card content (same structure as webhook)."""
    idx = payload.get('cardIndex', '?')
    total = payload.get('totalCards', '?')
    topic = payload.get('topic', '')
    chapter = payload.get('chapter', '')
    book_title = payload.get('bookTitle', '')
    bilingual = language == 'en' and zh

    elements = []

    elements.append({
        "tag": "div",
        "text": {"tag": "lark_md",
                 "content": f"**第 {idx} / {total} 张** · {esc_md(chapter)}"}
    })
    elements.append({"tag": "hr"})

    terms_zh = (zh or {}).get('terminologyZh', {})
    terms_en = payload.get('terminology', [])
    if bilingual and terms_zh:
        rows = '\n'.join(f"| {esc_md(en)} | {esc_md(cn)} |" for en, cn in terms_zh.items())
        elements.append({"tag": "markdown",
                         "content": f"**术语对照 · Terminology**\n| EN | 中文 |\n|---|---|\n{rows}"})
        elements.append({"tag": "hr"})
    elif terms_en:
        chips = ' '.join('`%s`' % esc_md(t) for t in terms_en)
        elements.append({"tag": "markdown", "content": f"**关键术语**\n{chips}"})
        elements.append({"tag": "hr"})

    def section(title, zh_text, en_text, md=False):
        parts = []
        if zh_text:
            t = md_links_to_feishu(zh_text) if md else zh_text
            parts.append(f"**{title}**\n{esc_md(t)}")
        if en_text and bilingual:
            t = md_links_to_feishu(en_text) if md else en_text
            parts.append(f"*{t}*")
        if parts:
            elements.append({"tag": "markdown", "content": '\n\n'.join(parts)})
            elements.append({"tag": "hr"})

    if bilingual:
        section("核心观点 · Core Idea", zh.get('coreIdeaZh',''), payload.get('coreIdea',''))
        section("详细解释 · Explanation", zh.get('explanationZh',''), payload.get('explanation',''), md=True)
        section("金句 · Key Quote", zh.get('quoteZh',''), payload.get('quote',''))
        section("应用场景 · Application", zh.get('applicationZh',''), payload.get('application',''), md=True)
    else:
        label = '核心观点' if language == 'zh' else 'Core Idea'
        section(label, payload.get('coreIdea',''), '')
        label2 = '详细解释' if language == 'zh' else 'Explanation'
        section(label2, payload.get('explanation',''), '', md=True)
        label3 = '金句' if language == 'zh' else 'Key Quote'
        section(label3, payload.get('quote',''), '')
        label4 = '应用场景' if language == 'zh' else 'Application'
        section(label4, payload.get('application',''), '', md=True)

    # image — via API we can upload directly and use image_key
    img = payload.get('image', '')
    if img:
        img_bytes, ext = decode_data_uri(img)
        if img_bytes:
            # Write to temp file, upload via API
            import tempfile
            tmp_img = tempfile.mktemp(suffix=f'.{ext}')
            with open(tmp_img, 'wb') as f:
                f.write(img_bytes)
            # Will be handled by caller with token
            elements.append({"tag": "markdown", "content": "[配图见下方图片消息]"})
            # Store temp path for later
            payload['_temp_image'] = tmp_img
        else:
            elements.append({"tag": "img", "url": img, "alt": {"tag": "plain_text", "content": "配图"}})
        elements.append({"tag": "hr"})

    rl = payload.get('relatedLinks', [])
    rl_zh = (zh or {}).get('relatedLinksZh', []) if bilingual else []
    zh_map = {item['href']: item.get('textZh', '') for item in rl_zh if isinstance(item, dict) and item.get('href')}
    if rl:
        link_lines = []
        for l in rl:
            if isinstance(l, dict):
                href = l.get('href',''); text_en = l.get('text','')
            else:
                href = str(l); text_en = ''
            text_zh = zh_map.get(href, '')
            label = '%s / %s' % (text_zh, text_en) if (text_zh and text_en) else (text_zh or text_en or href)
            link_lines.append(f"• {esc_md(label)}\n  {href}")
        elements.append({"tag": "markdown", "content": "**相关链接 · Related Links**\n" + '\n'.join(link_lines)})
        elements.append({"tag": "hr"})

    src = payload.get('source', '')
    if src:
        elements.append({"tag": "note", "elements": [{"tag": "plain_text", "content": "来源 / Source: " + src}]})

    card = {
        "header": {
            "title": {"tag": "plain_text", "content": f"{esc_md(book_title)} · {esc_md(topic)}"},
            "template": "blue"
        },
        "elements": elements
    }
    return card


def main():
    ap = argparse.ArgumentParser(description='Send to Feishu via Open API (supports images/files)')
    ap.add_argument('--payload', help='payload JSON (for card messages)')
    ap.add_argument('--zh', help='translation JSON (for English books)')
    ap.add_argument('--config', required=True, help='config.json path')
    ap.add_argument('--language', default='en', choices=['zh', 'en'])
    ap.add_argument('--image', help='standalone image file to send')
    ap.add_argument('--file', help='standalone file (e.g. PDF) to send')
    args = ap.parse_args()

    config = load_config(args.config)
    feishu_api = config.get('feishuApi', {})

    # Also check env vars as fallback
    app_id = feishu_api.get('appId', os.environ.get('FEISHU_APP_ID', ''))
    app_secret = feishu_api.get('appSecret', os.environ.get('FEISHU_APP_SECRET', ''))
    chat_id = feishu_api.get('chatId', os.environ.get('FEISHU_CHAT_ID', ''))

    if not app_id or not app_secret:
        print(json.dumps({'ok': False, 'error': 'feishuApi.appId and feishuApi.appSecret not set in config.json (or env FEISHU_APP_ID/FEISHU_APP_SECRET)'}, ensure_ascii=False))
        sys.exit(1)
    if not chat_id:
        print(json.dumps({'ok': False, 'error': 'feishuApi.chatId not set in config.json (or env FEISHU_CHAT_ID)'}, ensure_ascii=False))
        sys.exit(1)

    # 1. Get access token
    token, expires = get_tenant_access_token(app_id, app_secret)
    if not token:
        sys.exit(1)

    # 2a. Send standalone image
    if args.image:
        if not os.path.exists(args.image):
            print(json.dumps({'ok': False, 'error': f'Image not found: {args.image}'}, ensure_ascii=False))
            sys.exit(1)
        image_key = upload_image(token, args.image)
        if image_key:
            ret = send_message(token, chat_id, 'image', {'image_key': image_key})
            sys.exit(ret)
        else:
            sys.exit(1)

    # 2b. Send standalone file (e.g. PDF)
    if args.file:
        if not os.path.exists(args.file):
            print(json.dumps({'ok': False, 'error': f'File not found: {args.file}'}, ensure_ascii=False))
            sys.exit(1)
        file_key = upload_file(token, args.file)
        if file_key:
            ext = os.path.splitext(args.file)[1].lstrip('.')
            ret = send_message(token, chat_id, 'file', {'file_key': file_key})
            sys.exit(ret)
        else:
            sys.exit(1)

    # 2c. Send interactive card
    if not args.payload:
        print(json.dumps({'ok': False, 'error': 'Must provide --payload, --image, or --file'}, ensure_ascii=False))
        sys.exit(1)

    payload = json.load(open(args.payload, encoding='utf-8'))
    zh = json.load(open(args.zh, encoding='utf-8')) if args.zh else None
    language = args.language or payload.get('language', 'en')
    zh, payload = normalize_all(zh, payload, language)

    # Build and send card
    card = build_card_content(payload, zh, language)
    # Send as interactive message
    url = f'{FEISHU_BASE}/im/v1/messages?receive_id_type=chat_id'
    body = json.dumps({
        'receive_id': chat_id,
        'msg_type': 'interactive',
        'content': json.dumps(card, ensure_ascii=False)
    }, ensure_ascii=False).encode('utf-8')

    req = urllib.request.Request(url, data=body, headers={
        'Content-Type': 'application/json; charset=utf-8',
        'Authorization': f'Bearer {token}',
        'User-Agent': 'Mozilla/5.0'
    })
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        data = json.load(resp)
        if data.get('code') == 0:
            msg_id = data.get('data', {}).get('message_id', '')
            print(json.dumps({'sent': True, 'ok': True, 'msg_type': 'interactive',
                              'message_id': msg_id}, ensure_ascii=False))

            # If payload has image, send it as a separate image message
            temp_img = payload.get('_temp_image')
            if temp_img and os.path.exists(temp_img):
                image_key = upload_image(token, temp_img)
                if image_key:
                    send_message(token, chat_id, 'image', {'image_key': image_key})
                os.remove(temp_img)

            sys.exit(0)
        else:
            print(json.dumps({'sent': False, 'ok': False,
                              'error': data.get('msg', 'unknown'),
                              'code': data.get('code', -1)}, ensure_ascii=False))
            sys.exit(1)
    except Exception as e:
        print(json.dumps({'sent': False, 'error': f'Send card failed: {e}'}, ensure_ascii=False))
        sys.exit(1)


if __name__ == '__main__':
    main()
