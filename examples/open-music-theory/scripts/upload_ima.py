#!/usr/bin/env python3
"""
Upload a file to an IMA knowledge base folder.
Uses a sibling/installed ima-skill (ima_api.cjs + preflight-check.cjs + cos-upload.cjs).

Usage:
  python upload_ima.py --file <local.pdf> [--kb-name <知识库名>] [--folder-name <文件夹名>]

ima-skill lookup order (first match wins):
  1. $IMA_SKILL_DIR env var
  2. <this_script_dir>/../ima-skill      (sibling dir — recommended for public bundles)
  3. ~/.openclaw/skills/ima-skill        (OpenClaw default)
  4. ~/.agents/skills/ima-skill          (alternate agents path)

Exit codes:
  0 = success
  1 = other error (details on stdout/stderr)
  2 = IMA credentials expired/invalid (notify_key_expired.py triggered)
"""
import json, sys, os, subprocess, argparse

# Scripts live in <skill-root>/scripts/, so skill root is one level up
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(SCRIPT_DIR)


def find_ima_skill_dir():
    candidates = []
    env_dir = os.environ.get('IMA_SKILL_DIR', '').strip()
    if env_dir:
        candidates.append(env_dir)
    # Look for ima-skill in the same parent as omt-daily-push skill root
    candidates.append(os.path.normpath(os.path.join(BASE, '..', 'ima-skill')))
    candidates.append(os.path.expanduser('~/.openclaw/skills/ima-skill'))
    candidates.append(os.path.expanduser('~/.agents/skills/ima-skill'))
    for d in candidates:
        if os.path.isfile(os.path.join(d, 'ima_api.cjs')):
            return d
    return None


def load_target_config():
    """Load kb_name / folder_name from env, config.json, or built-in defaults."""
    kb_name = os.environ.get('OMT_KB_NAME', '').strip()
    folder_name = os.environ.get('OMT_FOLDER_NAME', '').strip()
    cfg_path = os.path.join(BASE, 'config.json')
    if os.path.isfile(cfg_path):
        try:
            cfg = json.load(open(cfg_path, encoding='utf-8'))
            kb_name = kb_name or cfg.get('kbName', '').strip()
            folder_name = folder_name or cfg.get('folderName', '').strip()
        except Exception:
            pass
    kb_name = kb_name or '【权威】音乐制作：风格与流派'
    folder_name = folder_name or '每日一个知识点'
    return kb_name, folder_name


# Resolve paths at import time.
IMA_SKILL_DIR = find_ima_skill_dir()
if not IMA_SKILL_DIR:
    print(json.dumps({
        'ok': False, 'stage': 'init',
        'error': 'ima-skill not found. Set IMA_SKILL_DIR or place ima-skill/ alongside omt-daily-push/.'
    }, ensure_ascii=False))
    sys.exit(1)

IMA_API = os.path.join(IMA_SKILL_DIR, 'ima_api.cjs')
PREFLIGHT = os.path.join(IMA_SKILL_DIR, 'knowledge-base', 'scripts', 'preflight-check.cjs')
COS_UPLOAD = os.path.join(IMA_SKILL_DIR, 'knowledge-base', 'scripts', 'cos-upload.cjs')

# Pick node binary. Prefer /usr/bin/node when available to bypass bun shims.
NODE = '/usr/bin/node' if os.path.isfile('/usr/bin/node') else 'node'

DEFAULT_KB_NAME, DEFAULT_FOLDER_NAME = load_target_config()


def run(cmd, input_str=None):
    """Run a command with clean env (strip NODE_OPTIONS bun shim), return (rc, stdout, stderr)."""
    env = dict(os.environ)
    env.pop('NODE_OPTIONS', None)
    r = subprocess.run(cmd, input=input_str, capture_output=True, text=True, env=env, timeout=300)
    return r.returncode, r.stdout, r.stderr


def read_credentials():
    """Read IMA credentials: env vars first, then ~/.config/ima/ files."""
    cid = os.environ.get('IMA_OPENAPI_CLIENTID') or os.environ.get('IMA_CLIENT_ID')
    akey = os.environ.get('IMA_OPENAPI_APIKEY') or os.environ.get('IMA_API_KEY')
    if not cid:
        p = os.path.expanduser('~/.config/ima/client_id')
        if os.path.isfile(p):
            cid = open(p).read().strip()
    if not akey:
        p = os.path.expanduser('~/.config/ima/api_key')
        if os.path.isfile(p):
            akey = open(p).read().strip()
    if not cid or not akey:
        return None, None
    return cid, akey


def ima_api(api_path, body_dict):
    """Call ima_api.cjs. Returns (True, data) | (False, err) | ('AUTH_FAIL', err)."""
    cid, akey = read_credentials()
    if not cid or not akey:
        return False, {'msg': 'missing IMA credentials (set env vars or place in ~/.config/ima/). See SKILL.md install step 3.', 'code': 'NO_CREDS'}
    opts = json.dumps({'clientId': cid, 'apiKey': akey})
    rc, out, err = run([NODE, IMA_API, api_path, json.dumps(body_dict, ensure_ascii=False), opts])
    if rc != 0:
        err_data = {}
        try:
            err_data = json.loads(err)
        except Exception:
            pass
        msg = err_data.get('msg', err.strip()[:300])
        code = err_data.get('code')
        return False, {'script_error': msg, 'code': code}
    try:
        resp = json.loads(out)
    except Exception:
        return False, {'parse_error': out[:300]}
    if resp.get('code') != 0:
        msg = resp.get('msg', '')
        low = msg.lower()
        if any(k in low for k in ['auth', 'unauthorized', 'invalid', 'expired', 'token', 'credential', '密钥', '认证', '鉴权']):
            return 'AUTH_FAIL', {'msg': msg, 'code': resp.get('code')}
        return False, {'msg': msg, 'code': resp.get('code')}
    return True, resp.get('data', {})


def find_kb_by_name(name):
    cursor = ''
    while True:
        ok, data = ima_api('openapi/wiki/v1/search_knowledge_base', {'query': name, 'cursor': cursor, 'limit': 20})
        if ok is not True:
            return None, data
        for item in data.get('info_list', []):
            if item.get('kb_name') == name:
                return item.get('kb_id'), None
        if data.get('is_end'):
            return None, {'msg': 'knowledge base not found: ' + name}
        cursor = data.get('next_cursor', '')


def find_folder_by_name(kb_id, name):
    ok, data = ima_api('openapi/wiki/v1/get_knowledge_list', {'knowledge_base_id': kb_id, 'cursor': '', 'limit': 50})
    if ok is not True:
        return None, data
    for item in data.get('knowledge_list', []):
        if item.get('media_type') == 99 and item.get('title') == name:
            return item.get('media_id'), None
    return None, {'msg': 'folder not found: ' + name}


def notify_expired(reason):
    """Invoke notify_key_expired.py (prints to stderr; fires webhook if IMA_KEY_EXPIRED_WEBHOOK set)."""
    script = os.path.join(SCRIPT_DIR, 'notify_key_expired.py')
    if os.path.isfile(script):
        subprocess.run([sys.executable, script, reason], timeout=30)


def upload(file_path, kb_name=DEFAULT_KB_NAME, folder_name=DEFAULT_FOLDER_NAME):
    if not os.path.isfile(file_path):
        print(json.dumps({'ok': False, 'stage': 'init', 'error': 'file not found: ' + file_path}, ensure_ascii=False))
        return 1

    # Step 0: resolve kb_id & folder_id
    kb_id, err = find_kb_by_name(kb_name)
    if kb_id is None:
        print(json.dumps({'ok': False, 'stage': 'find_kb', 'error': err}, ensure_ascii=False))
        return 1
    folder_id, err = find_folder_by_name(kb_id, folder_name)
    if folder_id is None:
        # fallback: upload to root of KB
        folder_id = None

    # Step 1: preflight
    rc, out, err = run([NODE, PREFLIGHT, '--file', file_path])
    if rc != 0:
        print(json.dumps({'ok': False, 'stage': 'preflight', 'error': err.strip()[:300]}, ensure_ascii=False))
        return 1
    try:
        pf = json.loads(out)
    except Exception:
        print(json.dumps({'ok': False, 'stage': 'preflight_parse', 'error': out[:300]}, ensure_ascii=False))
        return 1
    if not pf.get('pass'):
        print(json.dumps({'ok': False, 'stage': 'preflight', 'reason': pf.get('reason')}, ensure_ascii=False))
        return 1
    file_name = pf['file_name']; file_ext = pf['file_ext']
    file_size = pf['file_size']; media_type = pf['media_type']; content_type = pf['content_type']

    # Step 2: check_repeated_names
    body = {'params': [{'name': file_name, 'media_type': media_type}], 'knowledge_base_id': kb_id}
    if folder_id:
        body['folder_id'] = folder_id
    ok, data = ima_api('openapi/wiki/v1/check_repeated_names', body)
    if ok == 'AUTH_FAIL':
        notify_expired(data.get('msg', ''))
        print(json.dumps({'ok': False, 'stage': 'check_repeated', 'auth_fail': True, 'msg': data.get('msg')}, ensure_ascii=False))
        return 2
    if ok is not True:
        print(json.dumps({'ok': False, 'stage': 'check_repeated', 'error': data}, ensure_ascii=False))
        return 1
    params = data.get('params', [])
    if params and params[0].get('is_repeated'):
        import datetime
        ts = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        name, ext = os.path.splitext(file_name)
        file_name = f"{name}_{ts}{ext}"

    # Step 3: create_media
    body = {'file_name': file_name, 'file_size': file_size, 'content_type': content_type,
            'knowledge_base_id': kb_id, 'file_ext': file_ext}
    ok, data = ima_api('openapi/wiki/v1/create_media', body)
    if ok == 'AUTH_FAIL':
        notify_expired(data.get('msg', ''))
        print(json.dumps({'ok': False, 'stage': 'create_media', 'auth_fail': True, 'msg': data.get('msg')}, ensure_ascii=False))
        return 2
    if ok is not True:
        print(json.dumps({'ok': False, 'stage': 'create_media', 'error': data}, ensure_ascii=False))
        return 1
    media_id = data.get('media_id')
    cos = data.get('cos_credential', {})

    # Step 4: cos-upload
    cmd = [NODE, COS_UPLOAD,
           '--file', file_path,
           '--secret-id', cos.get('secret_id', ''),
           '--secret-key', cos.get('secret_key', ''),
           '--token', cos.get('token', ''),
           '--bucket', cos.get('bucket_name', ''),
           '--region', cos.get('region', ''),
           '--cos-key', cos.get('cos_key', ''),
           '--content-type', content_type,
           '--start-time', str(cos.get('start_time', '')),
           '--expired-time', str(cos.get('expired_time', '')),
           '--timeout', '300000']
    rc, out, err = run(cmd)
    if rc != 0:
        print(json.dumps({'ok': False, 'stage': 'cos_upload', 'error': err.strip()[:400]}, ensure_ascii=False))
        return 1

    # Step 5: add_knowledge
    body = {'media_type': media_type, 'media_id': media_id, 'title': file_name,
            'knowledge_base_id': kb_id,
            'file_info': {'cos_key': cos.get('cos_key', ''), 'file_size': file_size, 'file_name': file_name}}
    if folder_id:
        body['folder_id'] = folder_id
    ok, data = ima_api('openapi/wiki/v1/add_knowledge', body)
    if ok == 'AUTH_FAIL':
        notify_expired(data.get('msg', ''))
        print(json.dumps({'ok': False, 'stage': 'add_knowledge', 'auth_fail': True, 'msg': data.get('msg')}, ensure_ascii=False))
        return 2
    if ok is not True:
        print(json.dumps({'ok': False, 'stage': 'add_knowledge', 'error': data}, ensure_ascii=False))
        return 1

    print(json.dumps({'ok': True, 'file_name': file_name, 'kb_id': kb_id,
                      'folder_id': folder_id, 'media_id': media_id}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--file', required=True)
    ap.add_argument('--kb-name', default=DEFAULT_KB_NAME)
    ap.add_argument('--folder-name', default=DEFAULT_FOLDER_NAME)
    args = ap.parse_args()
    sys.exit(upload(args.file, args.kb_name, args.folder_name))
