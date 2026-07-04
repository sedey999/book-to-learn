#!/usr/bin/env python3
"""
Generate a supplementary image (flashcard style) — auto-height.
Used as a visual supplement to Feishu card messages — NOT for standalone push.

Design: BIG fonts, MINIMAL content. Like a physical flashcard.
  - Title: huge (40-56px auto-sized)
  - Quote: large (28-32px)
  - Terms: large (22-26px)
  - NO core idea, NO explanation, NO links — just the essentials
  - Width fixed at 750px; height auto-adapts to content (no fixed aspect ratio)

Usage:
  python gen_image.py --payload <payload.json> [--zh <zh.json>] --out <output.png> [--format <1:1|1:4|auto>] [--language <zh|en>]

Image generation: HTML → weasyprint PDF → pdf2image PNG
Design inspired by react-paper-memo (github.com/JustinChia/react-paper-memo) large-font card concept.

NOTE: No emoji/special symbols in HTML output — weasyprint cannot render them.
NOTE: After generation, the script auto-verifies the PNG is valid and non-empty.
"""
import json, sys, os, argparse, datetime, re, html as html_mod, tempfile
from weasyprint import HTML
from normalize_quotes import normalize_all

def esc(s):
    return html_mod.escape(s or '', quote=False)

def estimate_title_size(topic):
    """Auto-size title: shorter = bigger. Min 36px."""
    length = len(topic)
    if length <= 6:
        return 56
    elif length <= 10:
        return 48
    elif length <= 16:
        return 40
    else:
        return max(36, 48 - 24)

def build_html(payload, zh, date_str, language='en', fmt='auto'):
    idx = payload.get('cardIndex', '?')
    total = payload.get('totalCards', '?')
    topic = esc(payload.get('topic', ''))
    chapter = esc(payload.get('chapter', ''))
    bilingual = language == 'en' and zh
    topic_zh = (zh or {}).get('topicZh', '')
    main_title = esc(topic_zh) if (bilingual and topic_zh) else topic
    en_subtitle = topic if (bilingual and topic_zh) else ''

    # Width fixed; height auto-adapts to content
    page_w = '750px'
    padding = '32px'

    title_size = estimate_title_size(main_title)

    sections = []

    # Terms (minimal, large)
    terms_zh = (zh or {}).get('terminologyZh', {})
    if bilingual and terms_zh:
        rows = ''.join('<div class="term-row"><span class="term-en">%s</span> <span class="term-arrow">→</span> <span class="term-cn">%s</span></div>'
                       % (esc(en), esc(cn)) for en, cn in list(terms_zh.items())[:5])
        sections.append('<div class="sec"><div class="sec-h term-h">术语</div>%s</div>' % rows)

    # Quote only (NO core idea, NO explanation)
    quote_zh = (zh or {}).get('quoteZh', '') if bilingual else payload.get('quote', '')
    if quote_zh:
        sections.append('<div class="sec"><div class="quote-box">%s</div></div>' % esc(quote_zh))

    # image
    img_html = ''
    if payload.get('image'):
        img_html = '<div class="img-wrap"><img src="%s"></div>' % esc(payload['image'])

    body = ''.join(sections)

    html_str = f'''<!DOCTYPE html><html lang="zh"><head><meta charset="UTF-8">
<style>
@page {{ size: {page_w} auto; margin: 0; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: "Microsoft YaHei", "微软雅黑", "PingFang SC", "Hiragino Sans GB", "Noto Sans CJK SC", "SimSun", "宋体", sans-serif; color: #1f2328; width: {page_w}; }}
.card {{ background: linear-gradient(180deg, #f8f9fa 0%, #fff 30%, #fff 100%); display: flex; flex-direction: column; min-height: 400px; }}
.card-head {{ background: linear-gradient(135deg, #1a73e8, #1557b0); color: #fff; padding: {padding}; text-align: center; border-radius: 0; }}
.card-head .topic {{ font-size: {title_size}px; font-weight: 900; line-height: 1.2; word-break: keep-all; }}
.card-head .topic-en {{ font-size: 20px; font-weight: 500; margin-top: 8px; opacity: .8; font-style: italic; }}
.card-head .progress {{ font-size: 18px; opacity: .85; margin-bottom: 12px; }}
.card-body {{ flex: 1; display: flex; flex-direction: column; justify-content: center; padding: {padding}; }}
.sec {{ margin-bottom: 24px; }}
.sec-h {{ font-size: 24px; font-weight: 800; margin-bottom: 12px; }}
.term-h {{ color: #d93025; }}
.term-row {{ font-size: 26px; margin-bottom: 10px; line-height: 1.5; }}
.term-en {{ color: #f9ab00; font-weight: 700; }}
.term-arrow {{ color: #999; margin: 0 8px; }}
.term-cn {{ color: #1f2328; }}
.quote-box {{ font-size: 32px; font-style: italic; color: #7b1fa2; line-height: 1.5; text-align: center; padding: 16px 0; }}
.img-wrap {{ text-align: center; margin-bottom: 20px; }}
.img-wrap img {{ max-width: 85%; border-radius: 12px; border: 1px solid #eee; }}
.footer {{ padding: 16px {padding}; font-size: 16px; color: #5f6368; text-align: center; border-top: 1px solid #eee; }}
</style></head><body>
<div class="card">
  <div class="card-head">
    <div class="progress">第 {idx} / {total} 张</div>
    <div class="topic">{main_title}</div>
    {('<div class="topic-en">' + en_subtitle + '</div>') if en_subtitle else ''}
  </div>
  <div class="card-body">
    {img_html}
    {body}
  </div>
  <div class="footer">{esc(date_str)}</div>
</div>
</body></html>'''
    return html_str


def verify_image(img_path):
    """Verify the generated PNG is valid and non-empty."""
    from PIL import Image
    try:
        img = Image.open(img_path)
        w, h = img.size
        if w < 10 or h < 10:
            return {'ok': False, 'error': f'Image too small: {w}x{h}'}
        # Check it's not all-white or all-transparent
        pixels = list(img.convert('RGB').getdata())
        unique_colors = set(pixels[:1000])  # sample first 1000 pixels
        if len(unique_colors) <= 1:
            return {'ok': False, 'error': 'Image appears to be blank (single color)'}
        return {'ok': True, 'width': w, 'height': h, 'mode': img.mode}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def main():
    ap = argparse.ArgumentParser(description='Generate flashcard image (auto-height)')
    ap.add_argument('--payload', required=True)
    ap.add_argument('--zh', help='translation JSON (for English books)')
    ap.add_argument('--out', required=True, help='output PNG path')
    ap.add_argument('--format', default='auto', choices=['1:1', '1:4', 'auto'],
                    help='1:1=750x750, 1:4=750x3000, auto=height adapts to content')
    ap.add_argument('--language', default='en', choices=['zh', 'en'])
    args = ap.parse_args()
    payload = json.load(open(args.payload, encoding='utf-8'))
    zh = json.load(open(args.zh, encoding='utf-8')) if args.zh else None
    language = args.language or payload.get('language', 'en')
    zh, payload = normalize_all(zh, payload, language)  # 规范化中文引号
    date_str = datetime.date.today().isoformat()

    html_str = build_html(payload, zh, date_str, language=language, fmt=args.format)
    tmp_pdf = tempfile.mktemp(suffix='.pdf')
    HTML(string=html_str).write_pdf(tmp_pdf)

    try:
        from pdf2image import convert_from_path
        images = convert_from_path(tmp_pdf, dpi=150)
        if images:
            # If multiple pages, concatenate vertically
            if len(images) > 1:
                from PIL import Image as PILImage
                total_h = sum(img.height for img in images)
                max_w = max(img.width for img in images)
                combined = PILImage.new('RGB', (max_w, total_h), 'white')
                y = 0
                for img in images:
                    combined.paste(img, (0, y))
                    y += img.height
                combined.save(args.out, 'PNG')
            else:
                images[0].save(args.out, 'PNG')

            # Auto-verify
            verification = verify_image(args.out)
            result = {'ok': True, 'image': args.out, 'format': args.format,
                      'size': os.path.getsize(args.out), 'date': date_str,
                      'pages': len(images), 'verification': verification}
            print(json.dumps(result, ensure_ascii=False))
            if not verification.get('ok'):
                sys.exit(2)  # exit code 2 = image generated but verification failed
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
