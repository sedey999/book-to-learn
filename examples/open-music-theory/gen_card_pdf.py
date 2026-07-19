#!/usr/bin/env python3
"""
Generate a card-style bilingual PDF from a knowledge point payload.
Usage:
  python gen_card_pdf.py --payload <next_payload.json> --zh <zh.json> --out <output.pdf>

Produces a single-page (or multi-page) card-format PDF with large fonts,
designed for readability. Filename convention: OMT_<YYYY-MM-DD>_<id>.pdf
"""
import json, sys, os, argparse, datetime, re, html as html_mod
from weasyprint import HTML

def esc(s):
    return html_mod.escape(s or '', quote=False)

def md_links_to_text(text):
    """Convert markdown [text](url) to plain 'text (url)' so URL is visible & copyable.
    IMA cannot click hyperlinks, so URLs must be shown as literal text."""
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)',
                  lambda m: '%s (%s)' % (m.group(1), m.group(2)),
                  text)

def paras(text, md=False):
    out = []
    for ln in (text or '').split('\n'):
        ln = ln.strip()
        if ln:
            p = esc(ln)
            if md:
                p = md_links_to_text(p)
            out.append(p)
    return out

def build_html(payload, zh, date_str):
    idx = payload.get('cardIndex', '?')
    total = payload.get('totalCards', '?')
    chapter = esc(payload.get('chapter', ''))
    topic = esc(payload.get('topic', ''))
    src = esc(payload.get('source', ''))
    terms_zh = zh.get('terminologyZh', {})

    sections = []
    # Terminology table
    if terms_zh:
        rows = ''.join(
            '<tr><td class="term-en">%s</td><td class="term-cn">%s</td></tr>' % (esc(en), esc(cn))
            for en, cn in terms_zh.items()
        )
        sections.append('<div class="sec"><div class="sec-h term-h">术语对照 · Terminology</div><table class="term-tbl">%s</table></div>' % rows)

    # Core idea / explanation / quote / application
    # explanation & application may contain markdown links -> render as clickable
    def block(cn_title, en_title, zh_text, en_text, color, md=False):
        zh_ps = ''.join('<p>%s</p>' % p for p in paras(zh_text, md=md))
        en_ps = ''.join('<p class="en">%s</p>' % p for p in paras(en_text, md=md))
        if not zh_ps and not en_ps:
            return ''
        return ('<div class="sec"><div class="sec-h" style="color:%s">%s · %s</div>'
                '<div class="zh">%s</div><div class="en-wrap">%s</div></div>'
                ) % (color, cn_title, en_title, zh_ps, en_ps)

    sections.append(block('核心观点', 'Core Idea', zh.get('coreIdeaZh',''), payload.get('coreIdeaEn',''), '#1a7f37'))
    
    sections.append(block('金句', 'Key Quote', zh.get('quoteZh',''), payload.get('quoteEn',''), '#8250df'))
    sections.append(block('应用场景', 'Application', zh.get('applicationZh',''), payload.get('applicationScenarios',''), '#bf8700', md=True))

    # images — 支持 __IMAGE_X__ 标记插入到中文对应位置
    images = payload.get('images', [])
    img_map = {}  # example_num -> img dict
    unmatched = []
    for img in images:
        caption = img.get('caption', '')
        m = re.search(r'Example\s+(\d+)', caption)
        if m:
            ex_num = int(m.group(1))
            img_map[ex_num] = img
        else:
            unmatched.append(img)

    # 处理 explanationZh 中的 __IMAGE_X__ 标记
    expl_zh = zh.get('explanationZh', '')
    if '__IMAGE_' in expl_zh:
        expl_parts = []
        for para in expl_zh.split(chr(10)):
            para_stripped = para.strip()
            if not para_stripped:
                continue
            if '__IMAGE_' in para_stripped:
                tag_match = re.search(r'__IMAGE_(\d+)__', para_stripped)
                if tag_match:
                    ex_num = int(tag_match.group(1))
                    para_clean = re.sub(r'__IMAGE_\d+__', '', para_stripped).strip()
                    if para_clean:
                        expl_parts.append('<p>%s</p>' % esc(para_clean))
                    if ex_num in img_map:
                        img = img_map[ex_num]
                        cap_html = ''
                        if img.get('caption'):
                            cap_html = '<div class="img-caption">%s</div>' % esc(img['caption'])
                        expl_parts.append('<div class="img-item">%s<img src="%s" alt="%s"></div>' %
                                          (cap_html, esc(img['src']), esc(img.get('alt', ''))))
                        del img_map[ex_num]
            else:
                expl_parts.append('<p>%s</p>' % esc(para_stripped))
        expl_zh_html = chr(10).join(expl_parts)
    else:
        expl_zh_html = ''.join('<p>%s</p>' % p for p in paras(expl_zh))

    # 未匹配的图片放在 explanation 最上方
    unmatched_html = ''
    for img in list(unmatched):
        src = img.get('src', '')
        if src:
            cap_html = ''
            if img.get('caption'):
                cap_html = '<div class="img-caption">%s</div>' % esc(img['caption'])
            unmatched_html += '<div class="img-item">%s<img src="%s" alt="%s"></div>' % (
                cap_html, esc(src), esc(img.get('alt', '')))
    for ex_num, img in sorted(img_map.items()):
        src = img.get('src', '')
        if src:
            cap_html = ''
            if img.get('caption'):
                cap_html = '<div class="img-caption">%s</div>' % esc(img['caption'])
            unmatched_html += '<div class="img-item">%s<img src="%s" alt="%s"></div>' % (
                cap_html, esc(src), esc(img.get('alt', '')))
    if unmatched_html:
        expl_zh_html = unmatched_html + expl_zh_html

    # 向后兼容：旧单图字段
    img_html = ''
    if not images and payload.get('image'):
        img_html = '<div class="img-wrap"><img src="%s"></div>' % esc(payload['image'])

    # 使用带图片的 explanation 区块替换原来的 block('详细解释')
    expl_en_ps = ''.join('<p class="en">%s</p>' % p for p in paras(payload.get('explanationEn', ''), md=True))
    expl_block = '<div class="sec"><div class="sec-h" style="color:#0969da">详细解释 - Explanation</div><div class="zh">%s</div><div class="en-wrap">%s</div></div>' % (expl_zh_html, expl_en_ps)
    sections.append(expl_block)
    # related links — render with bilingual titles (zh / en) when available
    links_html = ''
    rl = payload.get('relatedLinks', [])
    rl_zh = zh.get('relatedLinksZh', [])  # [{href, textEn, textZh}]
    zh_map = {}
    for item in rl_zh:
        if isinstance(item, dict) and item.get('href'):
            zh_map[item['href']] = item.get('textZh', '')
    if rl:
        link_items = []
        for l in rl:
            if isinstance(l, dict):
                href = l.get('href',''); text_en = l.get('text','')
            else:
                href = str(l); text_en = ''
            text_zh = zh_map.get(href, '')
            is_ext = '【延展资源】' in text_en
            # bilingual label: 中文标题 / English Title
            if text_zh and text_en:
                label = '%s / %s' % (text_zh, text_en)
            elif text_zh:
                label = text_zh
            elif text_en:
                label = text_en
            else:
                label = ''
            mark = ' <span class="ext-tag">延展</span>' if is_ext else ''
            # show URL as plain text (IMA cannot click links; URL must be visible to copy)
            if label:
                link_items.append('<div class="link-item">%s%s<br><span class="link-url">%s</span></div>' % (esc(label), mark, esc(href)))
            else:
                link_items.append('<div class="link-item"><span class="link-url">%s</span></div>' % esc(href))
        links_html = '<div class="sec"><div class="sec-h" style="color:#0969da">相关链接 · Related Links</div><div class="links">%s</div></div>' % ''.join(link_items)

    note_html = ''
    if zh.get('note'):
        note_html = '<div class="note">译注：%s</div>' % esc(zh['note'])

    body = ''.join(sections)

    html_str = f'''<!DOCTYPE html><html lang="zh"><head><meta charset="UTF-8">
<style>
@page {{ size: 210mm 297mm; margin: 14mm 12mm; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: "Noto Sans CJK SC", "Noto Serif CJK SC", sans-serif; color: #1f2328; line-height: 1.7; }}
.card {{ border: 2px solid #e1e4e8; border-radius: 18px; overflow: hidden; }}
.card-head {{ background: linear-gradient(135deg,#1cb0f6,#0969da); color: #fff; padding: 16px 22px; }}
.card-head .progress {{ font-size: 17px; font-weight: 700; opacity: .92; }}
.card-head .topic {{ font-size: 25px; font-weight: 800; margin-top: 6px; line-height: 1.3; }}
.card-head .chapter {{ display:inline-block; font-size: 13px; background: rgba(255,255,255,.22); padding: 3px 12px; border-radius: 99px; margin-top: 8px; }}
.sec {{ padding: 14px 22px; border-bottom: 1px solid #f0f1f3; }}
.sec:last-child {{ border-bottom: none; }}
.sec-h {{ font-size: 15px; font-weight: 800; margin-bottom: 10px; letter-spacing: .5px; }}
.term-h {{ color: #cf222e; }}
.term-tbl {{ width: 100%; border-collapse: collapse; }}
.term-tbl td {{ padding: 6px 10px; border-bottom: 1px solid #f0f1f3; font-size: 16px; }}
.term-en {{ color: #8a5a00; font-weight: 600; width: 38%; white-space: nowrap; }}
.term-cn {{ color: #1f2328; }}
.zh p {{ font-size: 18px; margin-bottom: 9px; color: #1f2328; }}
.en-wrap {{ margin-top: 8px; padding-top: 8px; border-top: 1px dashed #d8dee4; }}
.en-wrap p.en {{ font-size: 15px; color: #57606a; margin-bottom: 6px; font-style: italic; }}
.img-wrap {{ padding: 8px 22px; }}
.img-item {{ margin-bottom: 10px; page-break-inside: avoid; }}
.img-item img {{ max-width: 100%; border-radius: 8px; border: 1px solid #eee; display: block; margin: 0 auto; }}
.img-caption {{ font-size: 12px; color: #57606a; margin-bottom: 3px; font-style: italic; text-align: center; }}
.links {{ }}
.link-item {{ font-size: 14px; margin-bottom: 8px; word-break: break-all; }}
.link-url {{ font-size: 13px; color: #6e7781; word-break: break-all; }}
.ext-tag {{ display:inline-block; font-size:11px; background:#8250df; color:#fff; padding:1px 6px; border-radius:4px; margin-left:4px; vertical-align: middle; }}
.note {{ padding: 12px 22px 16px; font-size: 13.5px; color: #6e7781; border-top: 1px solid #f0f1f3; background: #fafbfc; }}
.footer {{ padding: 8px 22px 14px; font-size: 12px; color: #8c959f; text-align: center; word-break: break-all; }}
</style></head><body>
<div class="card">
  <div class="card-head">
    <div class="progress">第 {idx} / {total} 张 · {esc(date_str)}</div>
    <div class="topic">{topic}</div>
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

def sanitize_filename(name):
    """清理文件名中的特殊字符"""
    import re
    # 保留中文、字母、数字、下划线，其他替换为下划线
    name = re.sub(r'[\\/:*?"<>|\s\.\，\。\！\？\「\」\（\）\(\)\【\】\[\]\、]', '_', name)
    name = re.sub(r'_+', '_', name)  # 合并多个下划线
    return name.strip('_')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--payload', required=True, help='next payload JSON path')
    ap.add_argument('--zh', required=True, help='translation JSON path')
    ap.add_argument('--out', help='output PDF path (optional, auto-generated if omitted)')
    args = ap.parse_args()
    payload = json.load(open(args.payload, encoding='utf-8'))
    zh = json.load(open(args.zh, encoding='utf-8'))
    date_str = payload.get('date') or datetime.date.today().isoformat()
    card_id = payload.get('nextId', 'card')
    
    # 自动生成带中文主题的文件名
    if not args.out:
        # 优先使用 omt_zh.json 中的 topicZh（由翻译环节生成）
        topic_zh = zh.get('topicZh', '')
        if not topic_zh:
            # 降级：从 coreIdeaZh 提取中文部分（取前8个中文字符）
            core_idea = zh.get('coreIdeaZh', '')
            import re
            zh_chars = re.findall(r'[\u4e00-\u9fa5]', core_idea[:30])
            topic_zh = ''.join(zh_chars[:8])
        if not topic_zh:
            topic_zh = card_id
        topic_safe = sanitize_filename(topic_zh)
        out_dir = '/tmp'
        args.out = f"{out_dir}/OMT_{date_str}_{card_id}_{topic_safe}.pdf"
    
    html_str = build_html(payload, zh, date_str)
    HTML(string=html_str).write_pdf(args.out)
    print(json.dumps({'ok': True, 'pdf': args.out, 'card_id': card_id, 'date': date_str,
                      'size': os.path.getsize(args.out)}, ensure_ascii=False))

if __name__ == '__main__':
    main()
