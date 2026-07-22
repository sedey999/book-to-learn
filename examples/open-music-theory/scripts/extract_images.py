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


def extract_images_from_html(html):
    """从 HTML 提取所有 figure 中的图片 + MuseScore iframe 嵌入的乐谱"""
    images = []

    # 找 <figure> 标签
    figures = re.findall(r'<figure[^>]*>(.*?)</figure>', html, re.DOTALL)
    for fig in figures:
        cap_match = re.search(r'<figcaption[^>]*>(.*?)</figcaption>', fig, re.DOTALL)
        caption = ''
        if cap_match:
            caption = re.sub(r'<[^>]+>', '', cap_match.group(1)).strip()

        img_match = re.search(r'<img[^>]+src="([^"]+)"', fig)
        if img_match:
            src = img_match.group(1)
            if 'logo' in src.lower() or 'cc-by' in src.lower() or 'buckram' in src:
                continue
            alt = re.search(r'alt="([^"]*)"', fig)
            images.append({
                'src': src,
                'caption': caption,
                'alt': alt.group(1) if alt else ''
            })

    # 处理不在 <figure> 内的 <img>（pressbooks 经常直接放 img）
    # 找到所有 img，排除 logo/cover，通过上下文寻找 Example caption
    handled_urls = set()
    for img in images:
        handled_urls.add(img['src'])

    # 收集页面中所有 iframe（MuseScore / YouTube）
    iframes = re.findall(r'<iframe[^>]+src="([^"]+)"[^>]*>', html)
    for iframe_url in iframes:
        if 'musescore.com' in iframe_url:
            # MuseScore 交互式乐谱 → 尝试通过 web archive 获取静态 SVG
            ms_img = _fetch_musescore_as_image(iframe_url, html)
            if ms_img:
                images.append(ms_img)
                print(f"    [INFO] MuseScore 乐谱已转为静态图片")
        # YouTube iframe 跳过（无静态图片）

    return images


def _fetch_musescore_as_image(iframe_url, html):
    """尝试从 MuseScore iframe 获取乐谱的静态 PNG 图片。
    
    MuseScore 被 Cloudflare 保护，直接访问被 403。
    策略：通过 web.archive.org 的缓存获取 SVG 乐谱，转换为 PNG。
    失败时返回 None。
    """
    import subprocess, tempfile, gzip as gzip_mod
    
    # 从 iframe URL 提取 score ID
    # 格式: https://musescore.com/user/XXX/scores/YYY/embed 或 .../scores/YYY/s/CODE/embed
    score_m = re.search(r'/scores/(\d+)', iframe_url)
    if not score_m:
        return None
    score_id = score_m.group(1)
    
    # 先通过 web archive 获取 embed HTML，从中提取 score hash
    try:
        embed_url = f'https://web.archive.org/web/2024/https://musescore.com/user/32728834/scores/{score_id}/embed'
        result = subprocess.run(['curl', '-sL', '--max-time', '20', embed_url],
                                capture_output=True, timeout=25)
        embed_html = result.stdout.decode('utf-8', errors='replace')
        
        # 从 embed HTML 中提取 score hash (image_path)
        hash_m = re.search(r'scoredata/g/([a-f0-9]+)/', embed_html)
        if not hash_m:
            return None
        score_hash = hash_m.group(1)
        
        svg_url = f'https://musescore.com/static/musescore/scoredata/g/{score_hash}/score_0.svg'
        
        # 尝试从 web archive 下载 SVG（尝试多个年份）
        svg_data = None
        for year in ['2025', '2024', '2023', '2022']:
            archive_url = f'https://web.archive.org/web/{year}id_/{svg_url}'
            r = subprocess.run(['curl', '-sL', '--max-time', '20', archive_url],
                               capture_output=True, timeout=25)
            if r.returncode == 0 and len(r.stdout) > 500:
                # Check if it's SVG (not HTML)
                if b'<svg' in r.stdout[:200]:
                    svg_data = r.stdout
                    break
                # Might be gzip compressed
                try:
                    decompressed = gzip_mod.decompress(r.stdout)
                    if b'<svg' in decompressed[:200]:
                        svg_data = decompressed
                        break
                except:
                    pass
        
        if not svg_data:
            # Trigger a fresh save
            subprocess.run(['curl', '-sL', '--max-time', '60',
                           f'https://web.archive.org/save/{svg_url}'],
                          capture_output=True, timeout=65)
            import time
            time.sleep(15)
            r = subprocess.run(['curl', '-sL', '--max-time', '20',
                               f'https://web.archive.org/web/2025id_/{svg_url}'],
                              capture_output=True, timeout=25)
            if r.returncode == 0 and len(r.stdout) > 500:
                if b'<svg' in r.stdout[:200]:
                    svg_data = r.stdout
                else:
                    try:
                        svg_data = gzip_mod.decompress(r.stdout)
                    except:
                        pass
        
        if not svg_data or b'<svg' not in svg_data[:500]:
            return None
        
        # Convert SVG to PNG using cairosvg
        try:
            import cairosvg
            import io
            png_data = cairosvg.svg2png(bytestring=svg_data, output_width=1024)
        except ImportError:
            # Fallback: return SVG directly (weasyprint supports SVG in <img>)
            import base64
            b64 = base64.b64encode(svg_data).decode('ascii')
            return {
                'src': f'data:image/svg+xml;base64,{b64}',
                'caption': f'MuseScore score (ID {score_id})',
                'alt': f'MuseScore score {score_id}',
            }
        
        # Find caption from surrounding HTML
        # Look for Example N text near the iframe
        iframe_m = re.search(re.escape(iframe_url), html)
        caption = f'Example (MuseScore {score_id})'
        if iframe_m:
            ctx = html[max(0,iframe_m.start()-500):iframe_m.end()+500]
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
        print(f"    [WARN] MuseScore 处理失败: {e}")
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


def process_card(item, force=False):
    """处理一张卡片"""
    cid = item['id']

    # 如果已有 images 字段且不为空，跳过
    if 'images' in item and item['images'] and not force:
        print(f"  [SKIP] {cid}: 已有 {len(item['images'])} 张图片")
        return item

    url = get_chapter_url(item)
    if not url:
        print(f"  [SKIP] {cid}: 找不到章节 URL")
        return item

    print(f"  [FETCH] {cid}: {url}")
    html = fetch_page(url)
    if not html:
        print(f"  [FAIL] {cid}: 页面抓取失败")
        return item

    imgs = extract_images_from_html(html)
    if not imgs:
        print(f"  [INFO] {cid}: 未找到图片")
        item['images'] = []
        return item

    print(f"  [INFO] {cid}: 找到 {len(imgs)} 张图片")

    image_data = []
    for i, img_info in enumerate(imgs):
        src = img_info['src']
        if not src.startswith('http'):
            src = urljoin(url, src)

        print(f"    [{i+1}/{len(imgs)}] {src[:70]}...", end=' ')
        data_url = download_image(src)
        if data_url:
            image_data.append({
                'src': data_url,
                'caption': img_info['caption'],
                'alt': img_info['alt']
            })
            print("OK")
        else:
            print("FAIL")

        time.sleep(0.3)

    item['images'] = image_data
    print(f"  [OK] {cid}: 成功获取 {len(image_data)}/{len(imgs)} 张图片")
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
