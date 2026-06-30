#!/usr/bin/env python3
"""
Generate a LARGE-FONT card-style PDF (A4, body text ≥18px, extra-large title).
Ideal for vocabulary / terminology learning tasks.

Usage:
  python gen_card_pdf_large.py --payload <payload.json> [--zh <zh.json>] --out <output.pdf> [--language <zh|en>]

Design spec:
  - A4 portrait, generous margins
  - Title: 42px bold (super-large)
  - Body text: minimum 18px (core idea 22px, explanation 18px, terms 18px)
  - Bilingual: Chinese on top, English below in italic
  - Chinese-only: single column, large text
  - Cross-platform font stack (Microsoft YaHei / PingFang / Noto CJK)
  - URLs as plain text (copyable, IMA can't click links)
"""
import json, sys, os, argparse, datetime, re, html as html_mod
from weasyprint import HTML

def esc(s):
    return html_mod.escape(s or '', quote=False)

def md_links_to_text(text):
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)',
                  lambda m: '%s (%s)' % (m.group(1), m.group(2)), text or '')

def paras(text, md=False):
    out = []
    for ln in (text or '').split('\n'):
        ln = ln.strip()
        if ln:
            p = esc(ln)
            if md: p = md_links_to_text(p)
            out.append(p)
    return out

def build_html(payload, zh, date_str, language='en'):
    idx = payload.get('cardIndex', '?')
    total = payload.get('totalCards', '?')
    chapter = esc(payload.get('chapter', ''))
    topic = esc(payload.get('topic', ''))
    src = esc(payload.get('source', ''))
    book_title = esc(payload.get('bookTitle', ''))
    bilingual = language == 'en' and zh
    topic_zh = (zh or {}).get('topicZh', '')
    topic_zh_esc = esc(topic_zh) if topic_zh else ''

    sections = []
    # Terminology
    terms_zh = (zh or {}).get('terminologyZh', {})
    terms_en = payload.get('terminology', [])
    if bilingual and terms_zh:
        rows = ''.join('<tr><td class="term-en">%s</td><td class="term-cn">%s</td></tr>' % (esc(en), esc(cn))
                       for en, cn in terms_zh.items())
        sections.append('<div class="sec"><div class="sec-h term-h">术语对照 · Terminology</div><table class="term-tbl">%s</table></div>' % rows)
    elif terms_en:
        chips = ''.join('<span class="term-chip">%s</span>' % esc(t) for t in terms_en)
        sections.append('<div class="sec"><div class="sec-h term-h">关键术语 · Key Terms</div><div class="terms">%s</div></div>' % chips)

    def block(title_cn, title_en, zh_text, en_text, color, md=False):
        zh_ps = ''.join('<p>%s</p>' % p for p in paras(zh_text, md=md)) if zh_text else ''
        en_ps = ''.join('<p class="en">%s</p>' % p for p in paras(en_text, md=md)) if en_text else ''
        if not zh_ps and not en_ps:
            return ''
        if bilingual:
            return ('<div class="sec"><div class="sec-h" style="color:%s">%s · %s</div>'
                    '<div class="zh">%s</div><div class="en-wrap">%s</div></div>'
                    ) % (color, title_cn, title_en, zh_ps, en_ps)
        else:
            content = zh_ps or en_ps
            cls = 'zh' if zh_ps else 'en-wrap'
            return ('<div class="sec"><div class="sec-h" style="color:%s">%s</div>'
                    '<div class="%s">%s</div></div>') % (color, title_cn if zh_ps else title_en, cls, content)

    if bilingual:
        sections.append(block('核心观点', 'Core Idea', zh.get('coreIdeaZh',''), payload.get('coreIdea',''), '#1a7f37'))
        sections.append(block('详细解释', 'Explanation', zh.get('explanationZh',''), payload.get('explanation',''), '#0969da', md=True))
        sections.append(block('金句', 'Key Quote', zh.get('quoteZh',''), payload.get('quote',''), '#8250df'))
        sections.append(block('应用场景', 'Application', zh.get('applicationZh',''), payload.get('application',''), '#bf8700', md=True))
    else:
        label = '核心观点' if language == 'zh' else 'Core Idea'
        sections.append(block(label, label, payload.get('coreIdea',''), '', '#1a7f37'))
        label2 = '详细解释' if language == 'zh' else 'Explanation'
        sections.append(block(label2, label2, payload.get('explanation',''), '', '#0969da', md=True))
        label3 = '金句' if language == 'zh' else 'Key Quote'
        sections.append(block(label3, label3, payload.get('quote',''), '', '#8250df'))
        label4 = '应用场景' if language == 'zh' else 'Application'
        sections.append(block(label4, label4, payload.get('application',''), '', '#bf8700', md=True))

    img_html = ''
    if payload.get('image'):
        img_html = '<div class="img-wrap"><img src="%s"></div>' % esc(payload['image'])

    links_html = ''
    rl = payload.get('relatedLinks', [])
    rl_zh = (zh or {}).get('relatedLinksZh', []) if bilingual else []
    zh_map = {item['href']: item.get('textZh', '') for item in rl_zh if isinstance(item, dict) and item.get('href')}
    if rl:
        link_items = []
        for l in rl:
            if isinstance(l, dict):
                href = l.get('href',''); text_en = l.get('text','')
            else:
                href = str(l); text_en = ''
            text_zh = zh_map.get(href, '')
            label = '%s / %s' % (text_zh, text_en) if (text_zh and text_en) else (text_zh or text_en or '')
            if label:
                link_items.append('<div class="link-item">%s<br><span class="link-url">%s</span></div>' % (esc(label), esc(href)))
            else:
                link_items.append('<div class="link-item"><span class="link-url">%s</span></div>' % esc(href))
        links_html = '<div class="sec"><div class="sec-h" style="color:#0969da">相关链接 · Related Links</div><div class="links">%s</div></div>' % ''.join(link_items)

    note_html = ''
    if (zh or {}).get('note'):
        note_html = '<div class="note">译注：%s</div>' % esc(zh['note'])

    body = ''.join(sections)

    # LARGE FONT design — body ≥18px, title 42px
    html_str = f'''<!DOCTYPE html><html lang="zh"><head><meta charset="UTF-8">
<style>
@page {{ size: 210mm 297mm; margin: 18mm 16mm; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: "Microsoft YaHei", "微软雅黑", "PingFang SC", "Hiragino Sans GB", "Heiti SC", "Noto Sans CJK SC", "Source Han Sans SC", "WenQuanYi Micro Hei", "SimSun", "宋体", sans-serif; color: #1f2328; line-height: 1.8; }}
.card {{ border: 3px solid #e1e4e8; border-radius: 20px; overflow: hidden; }}
.card-head {{ background: linear-gradient(135deg,#1cb0f6,#0969da); color: #fff; padding: 24px 28px; }}
.card-head .progress {{ font-size: 20px; font-weight: 700; opacity: .92; }}
.card-head .topic {{ font-size: 42px; font-weight: 900; margin-top: 10px; line-height: 1.25; }}
.card-head .topic-en {{ font-size: 22px; font-weight: 500; margin-top: 6px; opacity: .85; font-style: italic; }}
.card-head .chapter {{ display:inline-block; font-size: 18px; background: rgba(255,255,255,.22); padding: 5px 16px; border-radius: 99px; margin-top: 12px; }}
.sec {{ padding: 20px 28px; border-bottom: 2px solid #f0f1f3; }}
.sec:last-child {{ border-bottom: none; }}
.sec-h {{ font-size: 22px; font-weight: 800; margin-bottom: 14px; letter-spacing: .5px; }}
.term-h {{ color: #cf222e; }}
.term-tbl {{ width: 100%; border-collapse: collapse; }}
.term-tbl td {{ padding: 10px 14px; border-bottom: 2px solid #f0f1f3; font-size: 20px; }}
.term-en {{ color: #8a5a00; font-weight: 700; width: 38%; white-space: nowrap; }}
.term-cn {{ color: #1f2328; font-size: 20px; }}
.terms {{ display:flex; flex-wrap:wrap; gap:10px; }}
.term-chip {{ font-size:18px; background:#fff7e0; color:#8a5a00; border:2px solid #ffe08a; padding:6px 16px; border-radius:99px; font-weight:600; }}
.zh p {{ font-size: 22px; margin-bottom: 14px; color: #1f2328; line-height: 1.8; }}
.en-wrap {{ margin-top: 12px; padding-top: 12px; border-top: 2px dashed #d8dee4; }}
.en-wrap p.en {{ font-size: 18px; color: #57606a; margin-bottom: 10px; font-style: italic; line-height: 1.7; }}
.en-wrap p {{ font-size: 22px; margin-bottom: 14px; color: #1f2328; line-height: 1.8; }}
.img-wrap {{ padding: 14px 28px; }}
.img-wrap img {{ max-width: 100%; border-radius: 12px; border: 2px solid #eee; }}
.links {{ }}
.link-item {{ font-size: 18px; margin-bottom: 12px; word-break: break-all; }}
.link-url {{ font-size: 16px; color: #6e7781; word-break: break-all; }}
.note {{ padding: 16px 28px 20px; font-size: 18px; color: #6e7781; border-top: 2px solid #f0f1f3; background: #fafbfc; }}
.footer {{ padding: 12px 28px 18px; font-size: 16px; color: #8c959f; text-align: center; word-break: break-all; }}
</style></head><body>
<div class="card">
  <div class="card-head">
    <div class="progress">第 {idx} / {total} 张 · {esc(date_str)}</div>
    <div class="topic">{topic_zh_esc if (bilingual and topic_zh_esc) else topic}</div>
    {('<div class="topic-en">' + topic + '</div>') if (bilingual and topic_zh_esc) else ''}
    <span class="chapter">{chapter}</span>
  </div>
  {img_html}
  {body}
  {links_html}
  {note_html}
  <div class="footer">来源 / Source: {src}</div>
</div>
</body></html>'''
    return html_str

def main():
    ap = argparse.ArgumentParser(description='Generate LARGE-FONT card PDF (body ≥18px)')
    ap.add_argument('--payload', required=True)
    ap.add_argument('--zh', help='translation JSON (for English books)')
    ap.add_argument('--out', required=True)
    ap.add_argument('--language', default='en', choices=['zh', 'en'])
    args = ap.parse_args()
    payload = json.load(open(args.payload, encoding='utf-8'))
    zh = json.load(open(args.zh, encoding='utf-8')) if args.zh else None
    language = args.language or payload.get('language', 'en')
    date_str = datetime.date.today().isoformat()
    card_id = payload.get('nextId', 'card')
    topic_zh = (zh or {}).get('topicZh', '')
    html_str = build_html(payload, zh, date_str, language=language)
    HTML(string=html_str).write_pdf(args.out)
    import re as _re
    safe_zh = _re.sub(r'[\\/:*?"<>|]', '_', topic_zh)[:40] if topic_zh else ''
    print(json.dumps({'ok': True, 'pdf': args.out, 'date': date_str,
                      'size': os.path.getsize(args.out), 'language': language,
                      'card_id': card_id, 'topicZh': topic_zh,
                      'template': 'pdf-large', 'suggestedSuffix': safe_zh}, ensure_ascii=False))

if __name__ == '__main__':
    main()
