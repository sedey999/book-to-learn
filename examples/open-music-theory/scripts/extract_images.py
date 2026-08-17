#!/usr/bin/env python3
"""
从 pressbooks.pub 页面提取所有 Example 图片，更新 items.json 添加多图字段。
用法：
  python3 extract_images.py --card ch01-02        # 单张卡片
  python3 extract_images.py --start 0 --end 10    # 批量
  python3 extract_images.py                       # 全部
  python3 extract_images.py --force               # 强制重跑
"""

import json, os, sys, re, time, hashlib, base64, urllib.request, urllib.error
from pathlib import Path
from urllib.parse import urljoin

# 硬编码精确映射表（优先使用，修复模糊匹配错配问题）
sys.path.insert(0, str(Path(__file__).parent))
from card_slug_map import CARD_SLUG_MAP

SKILL_DIR = Path(__file__).parent.parent
ITEMS_PATH = SKILL_DIR / 'items.json'
ITEMS_NEW_PATH = SKILL_DIR / 'items_new.json'
CACHE_DIR = SKILL_DIR / '.img_cache'
CACHE_DIR.mkdir(exist_ok=True)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://viva.pressbooks.pub/',
}

# 卡片的 chapter slug -> pressbooks URL 映射
SLUG_MAP = {
    "notation-of-notes-clefs-and-ledger-lines": "https://viva.pressbooks.pub/openmusictheory/chapter/notation-of-notes-clefs-and-ledger-lines/",
    "clefs": "https://viva.pressbooks.pub/openmusictheory/chapter/clefs/",
    "the-keyboard-and-grand-staff": "https://viva.pressbooks.pub/openmusictheory/chapter/the-keyboard-and-grand-staff/",
    "half-and-whole-steps": "https://viva.pressbooks.pub/openmusictheory/chapter/half-and-whole-steps/",
    "major-scales": "https://viva.pressbooks.pub/openmusictheory/chapter/major-scales/",
    "minor-scales": "https://viva.pressbooks.pub/openmusictheory/chapter/minor-scales/",
    "other-aspects-of-notation": "https://viva.pressbooks.pub/openmusictheory/chapter/other-aspects-of-notation/",
    "basic-notation": "https://viva.pressbooks.pub/openmusictheory/chapter/basic-notation/",
    "rhythmic-rest-values": "https://viva.pressbooks.pub/openmusictheory/chapter/rhythmic-rest-values/",
    "simple-meter-and-time-signatures": "https://viva.pressbooks.pub/openmusictheory/chapter/simple-meter-and-time-signatures/",
    "compound-meters-and-time-signatures": "https://viva.pressbooks.pub/openmusictheory/chapter/compound-meters-and-time-signatures/",
    "meter": "https://viva.pressbooks.pub/openmusictheory/chapter/meter/",
    "other-rhythmic-essentials": "https://viva.pressbooks.pub/openmusictheory/chapter/other-rhythmic-essentials/",
    "swing-rhythms": "https://viva.pressbooks.pub/openmusictheory/chapter/swing-rhythms/",
    "intervals": "https://viva.pressbooks.pub/openmusictheory/chapter/intervals/",
    "intervals-and-dyads": "https://viva.pressbooks.pub/openmusictheory/chapter/intervals-and-dyads/",
    "chord-symbols": "https://viva.pressbooks.pub/openmusictheory/chapter/chord-symbols/",
    "seventh-chords": "https://viva.pressbooks.pub/openmusictheory/chapter/seventh-chords/",
    "inversion-and-figured-bass": "https://viva.pressbooks.pub/openmusictheory/chapter/inversion-and-figured-bass/",
    "roman-numerals": "https://viva.pressbooks.pub/openmusictheory/chapter/roman-numerals/",
    "intro-to-harmony": "https://viva.pressbooks.pub/openmusictheory/chapter/intro-to-harmony/",
    "species-counterpoint": "https://viva.pressbooks.pub/openmusictheory/chapter/species-counterpoint/",
    "first-species-counterpoint": "https://viva.pressbooks.pub/openmusictheory/chapter/first-species-counterpoint/",
    "second-species-counterpoint": "https://viva.pressbooks.pub/openmusictheory/chapter/second-species-counterpoint/",
    "fourth-species-counterpoint": "https://viva.pressbooks.pub/openmusictheory/chapter/fourth-species-counterpoint/",
    "gradus-ad-parnassum-exercises": "https://viva.pressbooks.pub/openmusictheory/chapter/gradus-ad-parnassum-exercises/",
    "introduction-and-core-principles": "https://viva.pressbooks.pub/openmusictheory/chapter/introduction-and-core-principles/",
    "formal-sections-in-general": "https://viva.pressbooks.pub/openmusictheory/chapter/formal-sections-in-general/",
    "phrase-archetypes-unique-forms": "https://viva.pressbooks.pub/openmusictheory/chapter/phrase-archetypes-unique-forms/",
    "melody-and-phrasing": "https://viva.pressbooks.pub/openmusictheory/chapter/melody-and-phrasing/",
    "aaba-form": "https://viva.pressbooks.pub/openmusictheory/chapter/aaba-form/",
    "aaba-and-strophic-form": "https://viva.pressbooks.pub/openmusictheory/chapter/aaba-and-strophic-form/",
    "verse-chorus-form": "https://viva.pressbooks.pub/openmusictheory/chapter/verse-chorus-form/",
    "sonata-form": "https://viva.pressbooks.pub/openmusictheory/chapter/sonata-form/",
    "rondo": "https://viva.pressbooks.pub/openmusictheory/chapter/rondo/",
    "ground-bass": "https://viva.pressbooks.pub/openmusictheory/chapter/ground-bass/",
    "foundational-concepts": "https://viva.pressbooks.pub/openmusictheory/chapter/foundational-concepts/",
    "cadential-64": "https://viva.pressbooks.pub/openmusictheory/chapter/cadential-64/",
    "strong-predominants": "https://viva.pressbooks.pub/openmusictheory/chapter/strong-predominants/",
    "64-chords-as-prolongations": "https://viva.pressbooks.pub/openmusictheory/chapter/64-chords-as-prolongations/",
    "leading-tone-chord": "https://viva.pressbooks.pub/openmusictheory/chapter/leading-tone-chord/",
    "inverted-v7s": "https://viva.pressbooks.pub/openmusictheory/chapter/inverted-v7s/",
    "common-tone-chords": "https://viva.pressbooks.pub/openmusictheory/chapter/common-tone-chords/",
    "tonicization": "https://viva.pressbooks.pub/openmusictheory/chapter/tonicization/",
    "extended-tonicization-and-modulation-to-closely-related-keys": "https://viva.pressbooks.pub/openmusictheory/chapter/extended-tonicization-and-modulation-to-closely-related-keys/",
    "modal-mixture": "https://viva.pressbooks.pub/openmusictheory/chapter/modal-mixture/",
    "neo-riemannian-triadic-progressions": "https://viva.pressbooks.pub/openmusictheory/chapter/neo-riemannian-triadic-progressions/",
    "augmented-sixth-chords": "https://viva.pressbooks.pub/openmusictheory/chapter/augmented-sixth-chords/",
    "substitutions": "https://viva.pressbooks.pub/openmusictheory/chapter/substitutions/",
    "diatonic-modes": "https://viva.pressbooks.pub/openmusictheory/chapter/diatonic-modes/",
    "the-diatonic-modes": "https://viva.pressbooks.pub/openmusictheory/chapter/the-diatonic-modes/",
    "collections": "https://viva.pressbooks.pub/openmusictheory/chapter/collections/",
    "analyzing-with-collections-scales-and-modes": "https://viva.pressbooks.pub/openmusictheory/chapter/analyzing-with-collections-scales-and-modes/",
    "post-tonal-triadic-progressions": "https://viva.pressbooks.pub/openmusictheory/chapter/post-tonal-triadic-progressions/",
    "chord-scale-theory": "https://viva.pressbooks.pub/openmusictheory/chapter/chord-scale-theory/",
    "pop-rock-schemas": "https://viva.pressbooks.pub/openmusictheory/chapter/pop-rock-schemas/",
    "pop-rock-schemata": "https://viva.pressbooks.pub/openmusictheory/chapter/pop-rock-schemata/",
    "blues-based-schemas": "https://viva.pressbooks.pub/openmusictheory/chapter/blues-based-schemas/",
    "blues-harmony": "https://viva.pressbooks.pub/openmusictheory/chapter/blues-harmony/",
    "4-chord-schemas": "https://viva.pressbooks.pub/openmusictheory/chapter/4-chord-schemas/",
    "modal-schemas": "https://viva.pressbooks.pub/openmusictheory/chapter/modal-schemas/",
    "galant-schemas-summary": "https://viva.pressbooks.pub/openmusictheory/chapter/galant-schemas-summary/",
    "classical-schemas": "https://viva.pressbooks.pub/openmusictheory/chapter/classical-schemas/",
    "ii-v-i": "https://viva.pressbooks.pub/openmusictheory/chapter/ii-v-i/",
    "jazz-embellishing-chords": "https://viva.pressbooks.pub/openmusictheory/chapter/jazz-embellishing-chords/",
    "jazz-voicings": "https://viva.pressbooks.pub/openmusictheory/chapter/jazz-voicings/",
    "lead-sheet-symbols": "https://viva.pressbooks.pub/openmusictheory/chapter/lead-sheet-symbols/",
    "pitch-and-pitch-class": "https://viva.pressbooks.pub/openmusictheory/chapter/pitch-and-pitch-class/",
    "intervals-in-integer-notation": "https://viva.pressbooks.pub/openmusictheory/chapter/intervals-in-integer-notation/",
    "pc-sets-normal-order-and-transformations": "https://viva.pressbooks.pub/openmusictheory/chapter/pc-sets-normal-order-and-transformations/",
    "interval-class-vectors": "https://viva.pressbooks.pub/openmusictheory/chapter/interval-class-vectors/",
    "naming-convention": "https://viva.pressbooks.pub/openmusictheory/chapter/naming-convention/",
    "naming-conventions-for-rows": "https://viva.pressbooks.pub/openmusictheory/chapter/naming-conventions-for-rows/",
    "basics-of-twelve-tone-theory": "https://viva.pressbooks.pub/openmusictheory/chapter/basics-of-twelve-tone-theory/",
    "row-properties": "https://viva.pressbooks.pub/openmusictheory/chapter/row-properties/",
    "twelve-tone-analysis-examples-webern-op-21-and-24": "https://viva.pressbooks.pub/openmusictheory/chapter/twelve-tone-analysis-examples-webern-op-21-and-24/",
    "high-baroque-fugal-exposition": "https://viva.pressbooks.pub/openmusictheory/chapter/high-baroque-fugal-exposition/",
    "16th-century-contrapuntal-style": "https://viva.pressbooks.pub/openmusictheory/chapter/16th-century-contrapuntal-style/",
    "core-principles-of-orchestration": "https://viva.pressbooks.pub/openmusictheory/chapter/core-principles-of-orchestration/",
    "intro-to-diatonic-modes-and-the-chromatic-scale": "https://viva.pressbooks.pub/openmusictheory/chapter/intro-to-diatonic-modes-and-the-chromatic-scale/",
    "rhythm-and-meter-in-pop-music": "https://viva.pressbooks.pub/openmusictheory/chapter/rhythm-and-meter-in-pop-music/",
    "endings-1": "https://viva.pressbooks.pub/openmusictheory/chapter/endings-1/",
    "strengthening-endings-with-v7": "https://viva.pressbooks.pub/openmusictheory/chapter/strengthening-endings-with-v7/",
    "strengthening-authentic-cadences-with-v7": "https://viva.pressbooks.pub/openmusictheory/chapter/strengthening-authentic-cadences-with-v7/",
    "strengthening-endings-with-strong-predominants": "https://viva.pressbooks.pub/openmusictheory/chapter/strengthening-endings-with-strong-predominants/",
    "subtle-colour-changes": "https://viva.pressbooks.pub/openmusictheory/chapter/subtle-colour-changes/",
}

# 卡片 ID -> 手动映射（针对没有 relatedLinks 的卡片）
MANUAL_MAP = {
    "ch01-01": "introduction-and-core-principles",
    "ch01-07": "other-aspects-of-notation",
    "ch01-19": "inversion-and-figured-bass",
    "ch01-21": "intro-to-harmony",
    "ch01-23": "intro-to-diatonic-modes-and-the-chromatic-scale",
    "ch01-24": "intro-to-diatonic-modes-and-the-chromatic-scale",
    "ch02-07": "gradus-ad-parnassum-exercises",
    "ch02-12": "galant-schemas-summary",
    "ch02-13": "galant-schemas-summary",
    "ch03-04": "phrase-archetypes-unique-forms",
    "ch04-01": "intro-to-harmony",
    "ch04-11": "intro-to-harmony",
    "ch04-15": "extended-tonicization-and-modulation-to-closely-related-keys",
    "ch05-06": "extended-tonicization-and-modulation-to-closely-related-keys",
    "ch05-07": "extended-tonicization-and-modulation-to-closely-related-keys",
    "ch05-09": "neo-riemannian-triadic-progressions",
    "ch05-10": "neo-riemannian-triadic-progressions",
    "ch05-11": "neo-riemannian-triadic-progressions",
    "ch05-12": "neo-riemannian-triadic-progressions",
    "ch05-13": "neo-riemannian-triadic-progressions",
    "ch05-14": "neo-riemannian-triadic-progressions",
    "ch07-01": "rhythm-and-meter-in-pop-music",
    "ch07-07": "blues-based-schemas",
    "ch07-08": "4-chord-schemas",
    "ch07-12": "pop-rock-schemas",
    "ch08-01": "pitch-and-pitch-class",
    "ch08-02": "intervals-in-integer-notation",
    "ch08-03": "pc-sets-normal-order-and-transformations",
    "ch10-01": "core-principles-of-orchestration",
}


CHAPTER_BASE = "https://viva.pressbooks.pub/openmusictheory/chapter/"

def get_chapter_url(item):
    """获取卡片对应的 pressbooks 章节 URL
    
    使用硬编码精确映射表 CARD_SLUG_MAP 作为唯一可信来源，
    避免之前的模糊匹配导致大量卡片错配到错误页面。
    """
    cid = item['id']

    # 1. 硬编码精确映射（唯一权威来源）
    if cid in CARD_SLUG_MAP:
        return CHAPTER_BASE + CARD_SLUG_MAP[cid] + "/"

    # 2. fallback: 从 relatedLinks 中找第一个 chapter 链接（仅在硬编码缺失时）
    for l in item.get('relatedLinks', []):
        h = l.get('href', '')
        m = re.search(r'openmusictheory/chapter/([^/#]+)', h)
        if m:
            return h if h.endswith('/') else h + '/'

    print(f"  [WARN] {cid}: 未配置硬编码映射且 relatedLinks 无章节链接")
    return None


def fetch_page(url):
    """获取 pressbooks 页面 HTML"""
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        print(f"  [ERROR] 抓取页面失败: {e}")
        return None


def _normalize_caption(text):
    """清理 HTML 标签和实体，标准化 caption 文本。"""
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&nbsp;', ' ').replace('&#160;', ' ')
    text = text.replace('&amp;', '&').replace('&quot;', '"').replace('&#039;', "'")
    return text.strip()


def extract_images_from_html(html):
    """从 HTML 提取所有 figure 图片、非 figure 图片、MuseScore 乐谱。"""
    images = []

    # 1. 找 <figure> 标签中的图片
    figures = re.findall(r'<figure[^>]*>(.*?)</figure>', html, re.DOTALL)
    for fig in figures:
        cap_match = re.search(r'<figcaption[^>]*>(.*?)</figcaption>', fig, re.DOTALL)
        caption = ''
        if cap_match:
            caption = _normalize_caption(cap_match.group(1))

        img_match = re.search(r'<img[^>]+src="([^"]+)"', fig)
        if img_match:
            src = img_match.group(1)
            if 'logo' in src.lower() or 'cc-by' in src.lower() or 'buckram' in src:
                continue
            alt_m = re.search(r'alt="([^"]*)"', fig)
            images.append({
                'src': src,
                'caption': caption,
                'alt': alt_m.group(1) if alt_m else ''
            })

    # 2. 处理不在 <figure> 内的 <img>（pressbooks 经常直接用 <p><img></p>）
    handled_urls = set()
    for img in images:
        handled_urls.add(img['src'].split('?')[0])  # 忽略 query string 差异

    # 找到所有未被 figure 包裹的 img
    # 先移除所有 figure 块，避免重复匹配
    html_no_figures = re.sub(r'<figure[^>]*>.*?</figure>', '', html, flags=re.DOTALL)
    non_figure_imgs = re.finditer(r'<img[^>]+src="([^"]+)"[^>]*>', html_no_figures)
    for m in non_figure_imgs:
        src = m.group(1)
        if 'logo' in src.lower() or 'cc-by' in src.lower() or 'buckram' in src:
            continue
        src_clean = src.split('?')[0]
        if src_clean in handled_urls:
            continue
        handled_urls.add(src_clean)

        # 从 img 标签附近查找 caption（向前查找 example-caption-name）
        pos = m.start()
        ctx_before = html_no_figures[max(0, pos-800):pos]
        ctx_after = html_no_figures[pos:pos+800]

        caption = ''
        # 优先在图片后面查找 example-caption-name
        cap_m = re.search(r'class="example-caption-name"[^>]*>(Example[^<]*)', ctx_after)
        if cap_m:
            caption = _normalize_caption(cap_m.group(1))
        else:
            # 在图片前面查找
            cap_m = re.search(r'class="example-caption-name"[^>]*>(Example[^<]*)', ctx_before)
            if cap_m:
                caption = _normalize_caption(cap_m.group(1))
            else:
                # 尝试在附近文本中找 Example N
                ex_m = re.search(r'Example\s+(?:&nbsp;)?(\d+)[^<]{0,100}', ctx_before + ctx_after)
                if ex_m:
                    caption = _normalize_caption(ex_m.group(0))

        alt_m = re.search(r'alt="([^"]*)"', m.group(0))
        images.append({
            'src': src,
            'caption': caption,
            'alt': alt_m.group(1) if alt_m else ''
        })
        print(f"    [INFO] 非 figure 图片: {caption[:60]}")

    # 3. 收集 MuseScore iframe
    # 同时收集无法转为静态图的媒体链接（MuseScore 截图失败 / YouTube）
    media_links = []

    musescore_iframes = re.findall(
        r'<iframe[^>]+src="(https://musescore\.com/[^"]+)"[^>]*>', html
    )
    for iframe_url in musescore_iframes:
        # 从 iframe URL 提取 score ID
        score_m = re.search(r'/scores/(\d+)', iframe_url)
        score_id = score_m.group(1) if score_m else ''

        # 从 iframe 附近 HTML 查找 Example 编号和 caption
        iframe_pos = html.find(iframe_url)
        p_start = html.rfind('<p ', 0, iframe_pos)
        if p_start == -1:
            p_start = html.rfind('<p>', 0, iframe_pos)
        if p_start == -1:
            p_start = max(0, iframe_pos - 200)
        ctx = html[p_start:p_start + 2000]

        ex_m = re.search(
            r'class="example-caption-name"[^>]*>(Example\s*(?:&nbsp;)?\d+\.?[^<]*)',
            ctx
        )
        example_num = 0
        caption_text = ''
        if ex_m:
            caption_text = _normalize_caption(ex_m.group(1))
            num_m = re.search(r'Example\s+(\d+)', caption_text)
            if num_m:
                example_num = int(num_m.group(1))

        # 生成用户可访问的页面 URL（去掉 /embed 后缀）
        page_url = re.sub(r'/embed/?$', '', iframe_url)

        # 占位，实际数据由 Playwright 填充
        images.append({
            'src': f'__MUSESCORE_{score_id}__',
            'caption': caption_text or f'Example {example_num}. MuseScore score.',
            'alt': f'MuseScore score {score_id}',
            '_musescore_score_id': score_id,
            '_musescore_example': example_num,
            '_musescore_page_url': page_url,
        })
        # 同时记录为 mediaLink（即使截图成功也保留链接作为备选）
        media_links.append({
            'example': example_num,
            'type': 'musescore',
            'url': page_url,
            'caption': caption_text or f'Example {example_num}. MuseScore score.',
            'score_id': score_id,
        })
        print(f"    [INFO] MuseScore iframe: score={score_id} Example={example_num}")

    # 4. 收集 YouTube iframe
    youtube_iframes = re.findall(
        r'<iframe[^>]+src="(https://www\.youtube\.com/embed/[^"]+)"[^>]*>', html
    )
    for iframe_url in youtube_iframes:
        iframe_pos = html.find(iframe_url)
        p_start = html.rfind('<p ', 0, iframe_pos)
        if p_start == -1:
            p_start = html.rfind('<p>', 0, iframe_pos)
        if p_start == -1:
            p_start = max(0, iframe_pos - 200)
        ctx = html[p_start:p_start + 2000]

        ex_m = re.search(
            r'class="example-caption-name"[^>]*>(Example\s*(?:&nbsp;)?\d+\.?[^<]*)',
            ctx
        )
        example_num = 0
        caption_text = ''
        if ex_m:
            caption_text = _normalize_caption(ex_m.group(1))
            num_m = re.search(r'Example\s+(\d+)', caption_text)
            if num_m:
                example_num = int(num_m.group(1))

        # 转为可点击的 YouTube 观看链接
        vid_m = re.search(r'/embed/([^?]+)', iframe_url)
        watch_url = f'https://www.youtube.com/watch?v={vid_m.group(1)}' if vid_m else iframe_url

        media_links.append({
            'example': example_num,
            'type': 'youtube',
            'url': watch_url,
            'caption': caption_text or f'Example {example_num}. YouTube video.',
        })
        print(f"    [INFO] YouTube iframe: Example={example_num} url={watch_url}")

    return images, media_links


def _fetch_musescore_as_image(iframe_url, html):
    """从 MuseScore iframe 获取乐谱的静态 PNG 图片。

    策略：直接访问 musescore.com 的 embed 页面获取 score hash，
    然后带浏览器级 HTTP headers（Sec-Fetch-*、Referer 等）下载 SVG，
    用 cairosvg 转为 PNG。这些 headers 能通过 Cloudflare 的图片资源校验。
    失败时返回 None。
    """
    import subprocess

    # 从 iframe URL 提取 score ID
    score_m = re.search(r'/scores/(\d+)', iframe_url)
    if not score_m:
        return None
    score_id = score_m.group(1)

    UA = ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
          '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    embed_url = f'https://musescore.com/user/32728834/scores/{score_id}/embed'

    try:
        # Step 1: 获取 embed HTML，提取 score hash
        r1 = subprocess.run([
            'curl', '-sL', '--http2', '--max-time', '20',
            '-H', f'User-Agent: {UA}',
            '-H', 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            '-H', 'Accept-Language: en-US,en;q=0.9',
            '-H', 'Sec-Fetch-Dest: iframe',
            '-H', 'Sec-Fetch-Mode: navigate',
            '-H', 'Sec-Fetch-Site: cross-site',
            embed_url,
        ], capture_output=True, timeout=25)
        embed_html = r1.stdout.decode('utf-8', errors='replace')

        hash_m = re.search(r'scoredata/g/([a-f0-9]+)/', embed_html)
        if not hash_m:
            print(f'    [WARN] MuseScore {score_id}: hash not found in embed page')
            return None
        score_hash = hash_m.group(1)

        # Step 2: 下载 SVG（带图片请求 headers 通过 Cloudflare）
        svg_url = (f'https://musescore.com/static/musescore/scoredata/g/'
                   f'{score_hash}/score_0.svg')
        r2 = subprocess.run([
            'curl', '-sL', '--http2', '--max-time', '20',
            '-H', f'User-Agent: {UA}',
            '-H', 'Accept: image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
            '-H', 'Accept-Language: en-US,en;q=0.9',
            '-H', 'Sec-Fetch-Dest: image',
            '-H', 'Sec-Fetch-Mode: no-cors',
            '-H', 'Sec-Fetch-Site: same-origin',
            '-H', f'Referer: {embed_url}',
            svg_url,
        ], capture_output=True, timeout=25)

        svg_data = r2.stdout
        if not svg_data or b'<svg' not in svg_data[:500]:
            print(f'    [WARN] MuseScore {score_id}: SVG download failed '
                  f'(size={len(svg_data)})')
            return None

        # Step 3: SVG → PNG
        try:
            import cairosvg
            png_data = cairosvg.svg2png(bytestring=svg_data, output_width=1024)
        except ImportError:
            import base64
            b64 = base64.b64encode(svg_data).decode('ascii')
            return {
                'src': f'data:image/svg+xml;base64,{b64}',
                'caption': f'Example (MuseScore {score_id})',
                'alt': f'MuseScore score {score_id}',
            }

        # 从 HTML 上下文找 caption
        iframe_m = re.search(re.escape(iframe_url), html)
        caption = f'Example (MuseScore {score_id})'
        if iframe_m:
            ctx = html[max(0, iframe_m.start() - 500):iframe_m.end() + 500]
            ex_m = re.search(r'Example\s*(?:&nbsp;)?(\d+)[^<]*', ctx)
            if ex_m:
                caption = f'Example {ex_m.group(1)}. MuseScore score.'

        import base64
        b64 = base64.b64encode(png_data).decode('ascii')
        return {
            'src': f'data:image/png;base64,{b64}',
            'caption': caption,
            'alt': caption,
        }
    except Exception as e:
        print(f'    [WARN] MuseScore {score_id}: {e}')
        return None


def get_original_url(url):
    """WordPress 会生成带尺寸后缀的缩略图（如 -300x38.png），去掉后缀得到原图 URL。
    例如：.../foo-300x38.png -> .../foo.png
    """
    # 匹配 -WxH 后缀（在扩展名前面）
    m = re.match(r'^(.+)-(\d+)x(\d+)(\.\w+)$', url)
    if m:
        orig = m.group(1) + m.group(4)
        return orig
    return url


def download_image(url):
    """下载图片并返回 base64 data URL。
    
    优先尝试下载原图（去掉 WordPress 缩略图尺寸后缀 -300x38.png）。
    如果原图失败则降级到缩略图 URL。
    """
    # 尝试先下载原图（去掉缩略图尺寸后缀）
    url_orig = get_original_url(url)
    # 使用原图 URL 作为缓存 key（避免缩略图缓存被误用为原图）
    cache_key = hashlib.md5(url_orig.encode()).hexdigest()[:16]
    cache_path = CACHE_DIR / cache_key

    if cache_path.exists():
        with open(cache_path, 'rb') as f:
            img_data = f.read()
    else:
        def _try(req_url):
            try:
                req = urllib.request.Request(req_url, headers=HEADERS)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return resp.read()
            except Exception:
                return None

        img_data = None
        # 先尝试原图（如果 URL 与缩略图不同）
        if url_orig != url:
            img_data = _try(url_orig)
            if img_data:
                url = url_orig  # 记录实际下载的是原图
        # 原图失败则用缩略图
        if img_data is None:
            img_data = _try(url)

        if img_data is None:
            print(f"    [ERROR] 下载图片失败（原图和缩略图都不行）")
            return None

        # 验证是真正的图片
        is_valid = (img_data[:4] == b'\x89PNG' or
                    img_data[:2] == b'\xff\xd8' or
                    img_data[:4] == b'GIF8' or
                    img_data[:4] == b'RIFF')
        if not is_valid:
            print(f"    [WARN] 返回内容不是图片格式，跳过")
            return None

        with open(cache_path, 'wb') as f:
            f.write(img_data)

    # 检测 MIME
    if img_data[:4] == b'\x89PNG':
        mime = 'image/png'
    elif img_data[:2] == b'\xff\xd8':
        mime = 'image/jpeg'
    elif img_data[:4] == b'GIF8':
        mime = 'image/gif'
    elif img_data[:4] == b'RIFF':
        mime = 'image/webp'
    else:
        mime = 'image/png'

    b64 = base64.b64encode(img_data).decode('ascii')
    return f'data:{mime};base64,{b64}'


def _capture_musescore_via_playwright(url):
    """通过 Playwright 加载 pressbooks 页面，捕获所有 MuseScore 乐谱并转 PNG。
    
    返回 dict: {score_id: {example, png_base64, caption}}
    """
    sys.path.insert(0, str(Path(__file__).parent))
    try:
        from capture_musescore import capture_musescore_for_url
    except ImportError as e:
        print(f"    [WARN] capture_musescore module not available: {e}")
        return {}
    
    results = capture_musescore_for_url(url, headless=True)
    out = {}
    for r in results:
        # png_base64 already includes data URI prefix
        b64_data = r['png_base64'].split(',', 1)[1] if ',' in r['png_base64'] else r['png_base64']
        out[r['score_id']] = {
            'example': r['example'],
            'png_base64': b64_data,
            'caption': r['caption'],
        }
        print(f"    [INFO] MuseScore score {r['score_id']} (Example {r['example']}): captured as PNG")
    return out


def process_card(item, force=False):
    """处理一张卡片"""
    cid = item['id']

    # 如果已有 images 字段且不为空，跳过
    if 'images' in item and item['images'] and not force:
        print(f"  [SKIP] {cid}: 已有 {len(item['images'])} 张图片")
        return item

    page_url = get_chapter_url(item)
    if not page_url:
        print(f"  [SKIP] {cid}: 找不到章节 URL")
        return item

    print(f"  [FETCH] {cid}: {page_url}")
    html = fetch_page(page_url)
    if not html:
        print(f"  [FAIL] {cid}: 页面抓取失败")
        return item

    imgs, media_links = extract_images_from_html(html)
    if not imgs and not media_links:
        print(f"  [INFO] {cid}: 未找到图片或媒体链接")
        item['images'] = []
        item['mediaLinks'] = []
        return item

    # 检查是否有 MuseScore iframe 需要抓取
    has_musescore = any(img.get('_musescore_score_id') for img in imgs)
    if has_musescore:
        print(f"  [MUSESCORE] 检测到 MuseScore 乐谱，使用 curl 直接抓取 SVG→PNG...")

    print(f"  [INFO] {cid}: 找到 {len(imgs)} 个图片元素, {len(media_links)} 个媒体链接")

    # 记录截图成功的 score_id，用于从 mediaLinks 中标记
    captured_scores = set()
    image_data = []
    for i, img_info in enumerate(imgs):
        # 处理 MuseScore 乐谱（通过 curl 直接抓取 SVG 并转 PNG）
        if img_info.get('_musescore_score_id'):
            score_id = img_info['_musescore_score_id']
            iframe_url = img_info.get('_musescore_page_url', page_url)
            result = _fetch_musescore_as_image(iframe_url, html)
            if result:
                captured_scores.add(score_id)
                image_data.append({
                    'src': result['src'],
                    'caption': img_info.get('caption') or result.get('caption', ''),
                    'alt': result.get('alt', ''),
                })
                print(f"    [{i+1}/{len(imgs)}] MuseScore {score_id}: OK (SVG→PNG)")
            else:
                print(f"    [{i+1}/{len(imgs)}] MuseScore {score_id}: FAIL (将使用链接)")
            continue

        src = img_info['src']
        if not src.startswith('http'):
            src = urljoin(page_url, src)

        print(f"    [{i+1}/{len(imgs)}] {src[:70]}...", end=' ')
        data_url = download_image(src)
        if data_url:
            image_data.append({
                'src': data_url,
                'caption': img_info.get('caption', ''),
                'alt': img_info.get('alt', '')
            })
            print("OK")
        else:
            print("FAIL")

        time.sleep(0.3)

    # 更新 mediaLinks：截图成功的 MuseScore 标记 captured=True
    for ml in media_links:
        if ml.get('type') == 'musescore' and ml.get('score_id') in captured_scores:
            ml['captured'] = True
        else:
            ml['captured'] = False

    item['images'] = image_data
    item['mediaLinks'] = media_links
    print(f"  [OK] {cid}: 成功获取 {len(image_data)} 张图片, {len(media_links)} 个媒体链接")
    return item


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', type=int)
    parser.add_argument('--end', type=int)
    parser.add_argument('--card')
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()

    items = json.load(open(ITEMS_PATH, encoding='utf-8'))

    if args.card:
        items_to_process = [item for item in items if item['id'] == args.card]
        if not items_to_process:
            print(f"未找到卡片 {args.card}")
            return
    elif args.start is not None or args.end is not None:
        start = args.start or 0
        end = args.end or len(items)
        items_to_process = items[start:end]
    else:
        items_to_process = items

    print(f"将处理 {len(items_to_process)} 张卡片")

    for i, item in enumerate(items_to_process):
        cid = item['id']
        print(f"\n[{i+1}/{len(items_to_process)}] {cid}: {item['topic']}")
        process_card(item, force=args.force)

    with open(ITEMS_NEW_PATH, 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 完成！结果保存到 {ITEMS_NEW_PATH}")


if __name__ == '__main__':
    main()
