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
    # 机制：翻译中的 __IMAGE_X__ 标记按段落顺序处理；存在的图就地插入，不存在的标警告；
    #       payload 里有但翻译没标记的图（漏标），按 Example 编号升序放在 explanation 末尾
    images = payload.get('images', [])
    img_map = {}  # example_num -> img dict
    for img in images:
        caption = img.get('caption', '')
        m = re.search(r'Example\s+(\d+)', caption)
        if m:
            ex_num = int(m.group(1))
            img_map[ex_num] = img

    # 收集翻译中标记的所有图号
    expl_zh = zh.get('explanationZh', '')
    tagged_nums = set()
    for tm in re.finditer(r'__IMAGE_(\d+)__', expl_zh):
        tagged_nums.add(int(tm.group(1)))

    # ========== 严格校验（strict validation）==========
    # 规则：
    #   1. 翻译标记的 __IMAGE_X__ 必须全部在 payload 图片中存在（防止翻译幻觉标了不存在的图）
    #   2. payload 中所有图片必须全部被翻译标记（防止漏标）
    #   3. 标记出现顺序必须与 Example 编号升序一致（防止 20 跑到 15 前面）
    #   4. 图片插入位置的上下文文字必须提到对应 Example 编号（防止标记位置错位）
    import sys as _sys
    validation_errors = []
    validation_warnings = []

    missing_tags = []  # 翻译标了但 payload 没有的图号
    untagged_imgs = []  # payload 有但翻译没标的图号
    for n in tagged_nums:
        if n not in img_map:
            missing_tags.append(n)
    for n in img_map:
        if n not in tagged_nums:
            untagged_imgs.append(n)
    if missing_tags:
        validation_errors.append(
            f'翻译标记了不存在的 Example 图片号: {sorted(missing_tags)}。'
            f'payload 中只有 Example {sorted(img_map.keys())}。'
            f'请在翻译中删除这些错误的 __IMAGE_X__ 标记（原文可能只是文字引用，并无对应配图）。'
        )
    if untagged_imgs:
        validation_errors.append(
            f'payload 有 {len(untagged_imgs)} 张 Example 图片但翻译未标记: {sorted(untagged_imgs)}。'
            f'请在翻译 explanationZh 的对应段落末尾添加 __IMAGE_X__ 标记。'
        )

    # 检查标记顺序是否按 Example 编号升序排列
    tag_order = [int(m.group(1)) for m in re.finditer(r'__IMAGE_(\d+)__', expl_zh)]
    if tag_order and tag_order != sorted(tag_order):
        # 找出具体哪些位置顺序错乱
        disorder_pairs = []
        for i in range(len(tag_order)-1):
            if tag_order[i] > tag_order[i+1]:
                disorder_pairs.append(f'Example {tag_order[i]} 在 Example {tag_order[i+1]} 前面')
        validation_errors.append(
            f'图片标记顺序错误！出现顺序 {tag_order} 不是升序排列。\n'
            f'  错乱详情：{"; ".join(disorder_pairs)}\n'
            f'  图片必须按照 Example 1→2→3… 的编号顺序依次出现，编号大的不能排在编号小的前面。\n'
            f'  请检查 explanationZh 中各 __IMAGE_X__ 标记的位置是否和原文 Example 出现顺序一致。'
        )

    # 检查标记位置上下文是否提到了对应 Example（防止标记放在错误段落）
    if not validation_errors:
        paras_with_tags = []
        for para in expl_zh.split(chr(10)):
            p = para.strip()
            if not p:
                continue
            for tm in re.finditer(r'__IMAGE_(\d+)__', p):
                ex_num = int(tm.group(1))
                para_clean = re.sub(r'__IMAGE_\d+__', '', p)
                # 检查段落中是否提到了 "示例 X" 或 "Example X"
                if not re.search(rf'(示例|Example)\s*{ex_num}', para_clean, re.IGNORECASE):
                    validation_warnings.append(
                        f'__IMAGE_{ex_num}__ 标记所在的段落没有提到「示例 {ex_num}」或 "Example {ex_num}"，'
                        f'可能插入位置不正确。段落内容（前60字）：{para_clean[:60]}'
                    )
                paras_with_tags.append((ex_num, para_clean[:60]))

    # 输出
    for w in validation_warnings:
        print(f'[gen_card_pdf WARN] {w}', file=_sys.stderr)
    if validation_errors:
        print('[gen_card_pdf ERROR] ===== 图片标记校验失败，PDF 生成中止 =====', file=_sys.stderr)
        for e in validation_errors:
            print(f'[gen_card_pdf ERROR] {e}', file=_sys.stderr)
        print('[gen_card_pdf ERROR] =============================================', file=_sys.stderr)
        _sys.exit(3)  # 特殊退出码 3 = 图片校验失败（区别于 1=一般错误, 2=IMA 密钥失效）

    # 保存图片插入顺序信息供后续复核脚本使用（写到 PDF 的 HTML 注释里不够好，改为返回）
    # 这里 tag_order 是严格升序（上面已校验）
    expected_image_order = tag_order if tag_order else sorted(img_map.keys())

    # 处理 explanationZh 中的 __IMAGE_X__ 标记
    # 经过上面校验后，所有标记都存在且顺序升序，可以安全地按顺序插入
    if '__IMAGE_' in expl_zh:
        expl_parts = []
        for para in expl_zh.split(chr(10)):
            para_stripped = para.strip()
            if not para_stripped:
                continue
            if '__IMAGE_' in para_stripped:
                # 使用 re.split 处理同一段落中可能存在的多个标记
                parts = re.split(r'(__IMAGE_\d+__)', para_stripped)
                for part in parts:
                    m = re.match(r'__IMAGE_(\d+)__', part)
                    if m:
                        ex_num = int(m.group(1))
                        if ex_num in img_map:
                            img = img_map[ex_num]
                            cap_html = ''
                            if img.get('caption'):
                                cap_html = '<div class="img-caption">%s</div>' % esc(img['caption'])
                            expl_parts.append('<div class="img-item" data-example="%d">%s<img src="%s" alt="%s"></div>' %
                                              (ex_num, cap_html, esc(img['src']), esc(img.get('alt', ''))))
                            img_map[ex_num] = None
                    else:
                        text = part.strip()
                        if text:
                            expl_parts.append('<p>%s</p>' % esc(text))
            else:
                expl_parts.append('<p>%s</p>' % esc(para_stripped))
        expl_zh_html = chr(10).join(expl_parts)
    else:
        expl_parts = []
        for para in expl_zh.split(chr(10)):
            para_stripped = para.strip()
            if para_stripped:
                expl_parts.append('<p>%s</p>' % esc(para_stripped))
        expl_zh_html = chr(10).join(expl_parts)

    # 校验已经保证所有图片都被标记了，不需要追加逻辑
    # （如果走到这里说明 untagged_imgs 为空，上面已经 sys.exit 了）

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
