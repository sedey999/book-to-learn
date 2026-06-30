#!/usr/bin/env python3
"""
Generate a supplementary image (1:1 or 1:4) from a knowledge point.
Used as a visual supplement to Feishu card messages — NOT for standalone push.

Usage:
  python gen_image.py --payload <payload.json> [--zh <zh.json>] --out <output.png> [--format <1:1|1:4>] [--language <zh|en>]

Image generation: HTML → weasyprint PDF → pdf2image PNG (sandbox has both).
Design: card-style, large fonts, colorful sections, rounded corners.

Templates referenced:
  - Design style inspired by react-paper-memo (github.com/JustinChia/react-paper-memo)
    large-font printable card concept
  - Color scheme from book-to-learn's own card design (Duolingo-style)
"""
import json, sys, os, argparse, datetime, re, html as html_mod, tempfile
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

def build_html(payload, zh, date_str, language='en', fmt='1:1'):
    idx = payload.get('cardIndex', '?')
    total = payload.get('totalCards', '?')
    topic = esc(payload.get('topic', ''))
    chapter = esc(payload.get('chapter', ''))
    bilingual = language == 'en' and zh
    topic_zh = (zh or {}).get('topicZh', '')
    topic_display = esc(topic_zh) if (bilingual and topic_zh) else topic

    # dimensions: 1:1 = 750x750, 1:4 = 750x3000
    if fmt == '1:4':
        page_w, page_h = '750px', '3000px'
    else:
        page_w, page_h = '750px', '750px'

    sections = []
    terms_zh = (zh or {}).get('terminologyZh', {})
    if bilingual and terms_zh:
        rows = ''.join('<div class="term-row"><span class="term-en">%s</span> <span class="term-arrow">→</span> <span class="term-cn">%s</span></div>'
                       % (esc(en), esc(cn)) for en, cn in list(terms_zh.items())[:6])
        sections.append('<div class="sec"><div class="sec-h" style="color:#cf222e">术语 · Terms</div>%s</div>' % rows)

    def block(title, zh_text, en_text, color, md=False):
        zh_ps = ''.join('<p>%s</p>' % p for p in paras(zh_text, md=md)) if zh_text else ''
        en_ps = ''.join('<p class="en">%s</p>' % p for p in paras(en_text, md=md)) if (en_text and bilingual) else ''
        if not zh_ps and not en_ps: return ''
        return '<div class="sec"><div class="sec-h" style="color:%s">%s</div><div class="content">%s%s</div></div>' % (color, title, zh_ps, en_ps)

    if bilingual:
        sections.append(block('核心观点', zh.get('coreIdeaZh',''), payload.get('coreIdea',''), '#1a7f37'))
        sections.append(block('金句', zh.get('quoteZh',''), payload.get('quote',''), '#8250df'))
    else:
        label = '核心观点' if language == 'zh' else 'Core Idea'
        sections.append(block(label, payload.get('coreIdea',''), '', '#1a7f37'))
        label3 = '金句' if language == 'zh' else 'Key Quote'
        sections.append(block(label3, payload.get('quote',''), '', '#8250df'))

    # image
    img_html = ''
    if payload.get('image'):
        img_html = '<div class="img-wrap"><img src="%s"></div>' % esc(payload['image'])

    body = ''.join(sections)

    html_str = f'''<!DOCTYPE html><html lang="zh"><head><meta charset="UTF-8">
<style>
@page {{ size: {page_w} {page_h}; margin: 0; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: "Microsoft YaHei", "微软雅黑", "PingFang SC", "Hiragino Sans GB", "Noto Sans CJK SC", "SimSun", "宋体", sans-serif; color: #1f2328; width: {page_w}; }}
.card {{ background: linear-gradient(180deg, #eef2f7 0%, #fff 100%); border-radius: 0; min-height: {page_h}; }}
.card-head {{ background: linear-gradient(135deg, #1cb0f6, #0969da); color: #fff; padding: 20px 24px; }}
.card-head .topic {{ font-size: 32px; font-weight: 900; line-height: 1.3; }}
.card-head .progress {{ font-size: 16px; opacity: .9; margin-bottom: 6px; }}
.card-head .chapter {{ font-size: 14px; opacity: .8; margin-top: 8px; }}
.sec {{ padding: 14px 24px; }}
.sec-h {{ font-size: 18px; font-weight: 800; margin-bottom: 8px; }}
.content p {{ font-size: 20px; margin-bottom: 8px; line-height: 1.6; }}
.content p.en {{ font-size: 16px; color: #57606a; font-style: italic; }}
.term-row {{ font-size: 18px; margin-bottom: 6px; }}
.term-en {{ color: #8a5a00; font-weight: 700; }}
.term-arrow {{ color: #999; margin: 0 6px; }}
.term-cn {{ color: #1f2328; }}
.img-wrap {{ padding: 10px 24px; text-align: center; }}
.img-wrap img {{ max-width: 90%; border-radius: 10px; border: 1px solid #eee; }}
.footer {{ padding: 12px 24px; font-size: 14px; color: #8c959f; text-align: center; border-top: 1px solid #eee; }}
</style></head><body>
<div class="card">
  <div class="card-head">
    <div class="progress">第 {idx} / {total} 张 · {esc(date_str)}</div>
    <div class="topic">{topic_display}</div>
    <div class="chapter">{chapter}</div>
  </div>
  {img_html}
  {body}
  <div class="footer">book-to-learn · {esc(date_str)}</div>
</div>
</body></html>'''
    return html_str

def main():
    ap = argparse.ArgumentParser(description='Generate supplementary image (1:1 or 1:4)')
    ap.add_argument('--payload', required=True)
    ap.add_argument('--zh', help='translation JSON (for English books)')
    ap.add_argument('--out', required=True, help='output PNG path')
    ap.add_argument('--format', default='1:1', choices=['1:1', '1:4'])
    ap.add_argument('--language', default='en', choices=['zh', 'en'])
    args = ap.parse_args()
    payload = json.load(open(args.payload, encoding='utf-8'))
    zh = json.load(open(args.zh, encoding='utf-8')) if args.zh else None
    language = args.language or payload.get('language', 'en')
    date_str = datetime.date.today().isoformat()

    # Step 1: HTML → PDF (temporary)
    html_str = build_html(payload, zh, date_str, language=language, fmt=args.format)
    tmp_pdf = tempfile.mktemp(suffix='.pdf')
    HTML(string=html_str).write_pdf(tmp_pdf)

    # Step 2: PDF → PNG (pdf2image)
    try:
        from pdf2image import convert_from_path
        images = convert_from_path(tmp_pdf, dpi=150)
        if images:
            images[0].save(args.out, 'PNG')
            print(json.dumps({'ok': True, 'image': args.out, 'format': args.format,
                              'size': os.path.getsize(args.out), 'date': date_str}, ensure_ascii=False))
        else:
            print(json.dumps({'ok': False, 'error': 'pdf2image returned no images'}, ensure_ascii=False))
            sys.exit(1)
    except ImportError:
        print(json.dumps({'ok': False, 'error': 'pdf2image not installed. Run: pip install pdf2image (also needs poppler)'}, ensure_ascii=False))
        sys.exit(1)
    finally:
        if os.path.exists(tmp_pdf):
            os.remove(tmp_pdf)

if __name__ == '__main__':
    main()
