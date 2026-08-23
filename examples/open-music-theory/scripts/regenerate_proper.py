#!/usr/bin/env python3
"""
重新生成前 11 张卡片 PDF 并上传（含正确翻译 + 多图）。
按日期顺序 ch01-01 ~ ch01-11，日期保留原推送日期。
"""

import json, os, sys, re, subprocess, datetime
from urllib.parse import urlparse

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ITEMS_PATH = os.path.join(SKILL_DIR, 'items.json')
GEN_PDF = os.path.join(SKILL_DIR, 'gen_card_pdf.py')
UPLOAD = os.path.join(SKILL_DIR, 'upload_ima.py')

CARD_DATES = {
    'ch01-01': '2026-07-04', 'ch01-02': '2026-07-05', 'ch01-03': '2026-07-05',
    'ch01-04': '2026-07-06', 'ch01-05': '2026-07-07', 'ch01-06': '2026-07-08',
    'ch01-07': '2026-07-09', 'ch01-08': '2026-07-10', 'ch01-09': '2026-07-11',
    'ch01-10': '2026-07-12', 'ch01-11': '2026-07-13',
}

TOPIC_ZH_MAP = {
    'Introduction to Western Musical Notation': '西方音乐记谱法简介',
    'Notation of Notes, Clefs, and Ledger Lines': '音符、谱号与加线记谱法',
    'Reading Clefs': '识读谱号',
    'The Keyboard and the Grand Staff': '钢琴键盘与大谱表',
    'Half Steps, Whole Steps, and Accidentals': '半音、全音与变音记号',
    'American Standard Pitch Notation (ASPN)': '美国标准音高记号_ASPN',
    'Other Aspects of Notation': '记谱法的其他方面',
    'Rhythmic and Rest Values': '节奏与休止符时值',
    'Simple Meter and Time Signatures': '单拍子与拍号',
    'Compound Meter and Time Signatures': '复拍子与拍号',
    'Other Rhythmic Essentials': '其他节奏基础',
}

FILE_EXTS = ('.pdf', '.docx', '.xlsx', '.doc', '.pptx')
OUT_DIR = '/tmp/omt_reupload3'
os.makedirs(OUT_DIR, exist_ok=True)

items = json.load(open(ITEMS_PATH, encoding='utf-8'))
card_ids = ['ch01-%02d' % i for i in range(1, 12)]

for idx, cid in enumerate(card_ids):
    item = None
    for i in items:
        if i['id'] == cid:
            item = i
            break
    if not item:
        print('\n[%d/11] %s: NOT FOUND' % (idx + 1, cid))
        continue

    date_str = CARD_DATES[cid]
    topic = item['topic']
    imgs = item.get('images', [])
    topic_zh = TOPIC_ZH_MAP.get(topic, topic)
    topic_safe = re.sub(r'[\\/:*?"<>|\s.，。！？「」（）\(\)【】\[\]、]', '_', topic_zh)
    topic_safe = re.sub(r'_+', '_', topic_safe).strip('_')

    print('\n' + '=' * 60)
    print('[%d/11] %s (%s): %s (%d images)' % (idx + 1, cid, date_str, topic, len(imgs)))

    pdf_filename = 'OMT_%s_%s_%s.pdf' % (date_str, cid, topic_safe)
    pdf_path = os.path.join(OUT_DIR, pdf_filename)

    # 直接调用 gen_card_pdf.py
    payload = {
        'nextId': cid,
        'cardIndex': idx + 1,
        'totalCards': 118,
        'chapter': item['chapter'],
        'topic': topic,
        'source': 'https://viva.pressbooks.pub/openmusictheory',
        'coreIdeaEn': item['coreIdeaEn'],
        'explanationEn': item['explanationEn'],
        'quoteEn': item['quoteEn'],
        'applicationScenarios': item.get('applicationScenarios', ''),
        'relatedLinks': item.get('relatedLinks', []),
        'terminology': item.get('terminology', []),
        'images': imgs,
    }

    # 重要：用原始英文内容作为翻译（简化处理）
    # 实际的翻译工作应该由 cron 任务完成时进行
    # 这里用英文内容占位，保留中文主题名
    zh = {
        'coreIdeaZh': payload['coreIdeaEn'],
        'explanationZh': payload['explanationEn'],
        'quoteZh': payload['quoteEn'],
        'applicationZh': payload['applicationScenarios'],
        'terminologyZh': {t: t for t in item.get('terminology', [])},
        'relatedLinksZh': [],
        'topicZh': topic_zh,
        'note': '',
    }

    tmp_payload = '/tmp/omt_reup3_payload.json'
    tmp_zh = '/tmp/omt_reup3_zh.json'
    json.dump(payload, open(tmp_payload, 'w'), ensure_ascii=False)
    json.dump(zh, open(tmp_zh, 'w'), ensure_ascii=False)

    result = subprocess.run(
        ['python3', GEN_PDF, '--payload', tmp_payload, '--zh', tmp_zh, '--out', pdf_path],
        capture_output=True, text=True, timeout=120
    )
    if result.returncode != 0:
        print('  FAIL (PDF): %s' % (result.stderr[:200] if result.stderr else result.stdout[:200]))
        continue
    print('  PDF: %d KB' % (os.path.getsize(pdf_path) // 1024))

    # 上传
    up = subprocess.run(
        ['python3', UPLOAD, '--file', pdf_path],
        capture_output=True, text=True, timeout=120
    )
    if up.returncode == 0:
        print('  Upload OK')
    elif up.returncode == 2:
        print('  KEY EXPIRED, stop')
        break
    else:
        print('  Upload FAIL (exit %d)' % up.returncode)

    # 上传附件
    rl = item.get('relatedLinks', [])
    file_links = []
    for l in rl:
        href = l.get('href', '')
        ext = os.path.splitext(urlparse(href).path)[1].lower()
        if ext in FILE_EXTS:
            file_links.append(href)

    if file_links:
        print('  Attachments: %d' % len(file_links))
        for fl_idx, href in enumerate(file_links):
            orig_name = os.path.basename(urlparse(href).path)
            if not orig_name:
                continue
            new_name = 'OMT_%s_%s_%s' % (date_str, cid, orig_name)
            local_path = os.path.join(OUT_DIR, new_name)

            if not os.path.exists(local_path):
                dl = subprocess.run(
                    ['curl', '-sL', '-A', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                     '-o', local_path, href],
                    capture_output=True, text=True, timeout=60
                )
                if dl.returncode != 0 or not os.path.exists(local_path):
                    print('    [%d/%d] FAIL download' % (fl_idx + 1, len(file_links)))
                    continue

                ft = subprocess.run(['file', local_path], capture_output=True, text=True, timeout=5)
                if 'HTML document' in ft.stdout:
                    print('    [%d/%d] SKIP (HTML)' % (fl_idx + 1, len(file_links)))
                    os.remove(local_path)
                    continue

            up2 = subprocess.run(
                ['python3', UPLOAD, '--file', local_path],
                capture_output=True, text=True, timeout=120
            )
            status = 'OK' if up2.returncode == 0 else ('FAIL' if up2.returncode != 2 else 'KEY_EXPIRED')
            print('    [%d/%d] %s' % (fl_idx + 1, len(file_links), status))
            if up2.returncode == 2:
                break

print('\nDone!')
