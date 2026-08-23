#!/usr/bin/env python3
"""
通过 Playwright 加载 pressbooks 页面，捕获 MuseScore 乐谱 SVG 并转换为 PNG。

MuseScore 的 Cloudflare 会拦截服务器端请求（curl/headless browser），
但在 pressbooks 页面内作为 iframe 加载时，乐谱以 SVG 格式通过浏览器网络请求正常加载。

本脚本使用持久化浏览器上下文（避免 CF 检测），慢速滚动触发 lazy-loaded iframes，
监听网络响应中的 score_0.svg，再通过 cairosvg 转为 PNG base64。

用法（命令行）：
  python3 capture_musescore.py <pressbooks_url>

用法（作为模块）：
  from capture_musescore import capture_musescore_for_url
  results = capture_musescore_for_url(url)
  # results = [{"example": 1, "score_id": "26439799", "png_base64": "..."}, ...]

依赖：
  pip install playwright cairosvg curl_cffi
  playwright install chromium
"""

import json
import sys
import re
import base64
import time
from pathlib import Path


def _capture_with_persistent_browser(url, headless=True, scroll_delay=1.0, wait_after_scroll=8000):
    """使用持久化浏览器上下文捕获 MuseScore SVG。
    
    返回 list of dict: example, score_id, svg_hash, svg_bytes
    """
    from playwright.sync_api import sync_playwright
    
    user_data_dir = str(Path.home() / '.cache' / 'omt-ms-browser')
    Path(user_data_dir).mkdir(parents=True, exist_ok=True)
    
    results = []
    seen_hashes = set()
    
    with sync_playwright() as p:
        # Use persistent context - looks more like a real browser
        context = p.chromium.launch_persistent_context(
            user_data_dir,
            headless=headless,
            viewport={'width': 1280, 'height': 900},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                       'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            locale='en-US',
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-features=IsolateOrigins,site-per-process',
            ],
        )
        
        # Remove webdriver detection
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            window.chrome = { runtime: {} };
        """)
        
        page = context.new_page()
        
        # Collect SVG responses
        svg_buffers = {}  # hash -> bytes
        
        def handle_response(response):
            resp_url = response.url
            if 'score_0.svg' in resp_url and 'musescore' in resp_url:
                m = re.search(r'/scoredata/g/([a-f0-9]+)/score_0\.svg', resp_url)
                if m:
                    h = m.group(1)
                    if h not in svg_buffers:
                        try:
                            body = response.body()
                            if b'<svg' in body[:200]:
                                svg_buffers[h] = body
                                print(f"    [SVG] {h[:12]}... ({len(body)} bytes)", file=sys.stderr)
                        except Exception:
                            pass
        
        page.on('response', handle_response)
        
        print(f"  [browser] Loading {url}...", file=sys.stderr)
        try:
            page.goto(url, timeout=60000, wait_until='domcontentloaded')
        except Exception as e:
            print(f"  [browser] Load warning: {e}", file=sys.stderr)
        
        # Wait for initial JS
        page.wait_for_timeout(5000)
        
        # Get page height
        page_height = page.evaluate('document.body.scrollHeight')
        print(f"  [browser] Page height: {page_height}px", file=sys.stderr)
        
        # Slow scroll to trigger each lazy iframe (human-like)
        step = 400
        for y in range(0, min(page_height + 500, 20000), step):
            page.evaluate(f'window.scrollTo({{top: {y}, behavior: "smooth"}})')
            page.wait_for_timeout(int(scroll_delay * 1000))
        
        # Final wait for all remaining loads
        page.wait_for_timeout(wait_after_scroll)
        
        # Map iframes to Example numbers and score hashes
        iframe_data = page.evaluate("""
            () => {
                const iframes = document.querySelectorAll('iframe[src*="musescore"]');
                const out = [];
                for (const iframe of iframes) {
                    const src = iframe.src;
                    const scoreIdMatch = src.match(/\\/scores\\/(\\d+)/);
                    const scoreId = scoreIdMatch ? scoreIdMatch[1] : '';

                    let exampleNum = null;
                    // Look for caption after iframe
                    let el = iframe.nextElementSibling;
                    for (let i = 0; i < 5 && el; i++) {
                        const capName = el.querySelector ? el.querySelector('.example-caption-name') : null;
                        if (capName) {
                            const text = capName.textContent.trim();
                            const m = text.match(/Example\\s+(\\d+)/);
                            if (m) { exampleNum = parseInt(m[1]); break; }
                        }
                        el = el.nextElementSibling;
                    }
                    // Look before iframe
                    if (exampleNum === null) {
                        let prev = iframe.previousElementSibling;
                        for (let i = 0; i < 5 && prev; i++) {
                            const m = (prev.textContent || '').match(/Example\\s+(\\d+)/);
                            if (m) { exampleNum = parseInt(m[1]); break; }
                            prev = prev.previousElementSibling;
                        }
                    }
                    out.push({scoreId, exampleNum, src: src});
                }
                return out;
            }
        """)
        
        # Get hash from each iframe's internal img
        for frame in page.frames:
            if 'musescore' not in frame.url:
                continue
            score_m = re.search(r'/scores/(\d+)', frame.url)
            score_id = score_m.group(1) if score_m else ''
            try:
                img_src = frame.evaluate("""
                    () => {
                        const img = document.querySelector('img[src*="score_0"]');
                        return img ? img.src : '';
                    }
                """)
                if img_src:
                    hash_m = re.search(r'/scoredata/g/([a-f0-9]+)/score_0\.(svg|png)', img_src)
                    if hash_m:
                        svg_hash = hash_m.group(1)
                        if svg_hash in svg_buffers and svg_hash not in seen_hashes:
                            seen_hashes.add(svg_hash)
                            # Find example number
                            example_num = 0
                            for d in iframe_data:
                                if d['scoreId'] == score_id:
                                    example_num = d.get('exampleNum') or 0
                                    break
                            results.append({
                                'example': example_num,
                                'score_id': score_id,
                                'svg_hash': svg_hash,
                                'svg_bytes': svg_buffers[svg_hash],
                            })
            except Exception:
                pass
        
        context.close()
    
    return results


def svg_to_png_base64(svg_bytes, scale=2):
    """将 SVG 字节转换为 PNG base64 字符串。"""
    try:
        import cairosvg
        png_data = cairosvg.svg2png(bytestring=svg_bytes, scale=scale)
        return base64.b64encode(png_data).decode('ascii')
    except ImportError:
        print("ERROR: cairosvg not installed. Run: pip install cairosvg", file=sys.stderr)
        return None
    except Exception as e:
        print(f"ERROR converting SVG to PNG: {e}", file=sys.stderr)
        return None


def capture_musescore_for_url(url, headless=True):
    """主入口：捕获指定 pressbooks 页面上的所有 MuseScore 乐谱。
    
    返回 list of dict:
      - example: Example 编号
      - score_id: MuseScore score ID  
      - png_base64: PNG 图片的 base64 编码（data URI 前缀已包含）
      - caption: 描述文本
    """
    results_raw = _capture_with_persistent_browser(url, headless=headless)
    
    output = []
    for r in results_raw:
        png_b64 = svg_to_png_base64(r['svg_bytes'], scale=2)
        if png_b64:
            output.append({
                'example': r['example'],
                'score_id': r['score_id'],
                'png_base64': f'data:image/png;base64,{png_b64}',
                'caption': f"Example {r['example']}. MuseScore score." if r['example'] else f"MuseScore score ({r['score_id']})",
            })
    
    return output


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <pressbooks_url>", file=sys.stderr)
        sys.exit(1)
    
    url = sys.argv[1]
    headless = '--headed' not in sys.argv
    
    results = capture_musescore_for_url(url, headless=headless)
    
    # Output summary to stderr, JSON to stdout
    print(f"\nCaptured {len(results)} scores:", file=sys.stderr)
    for r in results:
        png_size = len(base64.b64decode(r['png_base64'].split(',')[1]))
        print(f"  Example {r['example']} (score {r['score_id']}): {png_size} bytes PNG", file=sys.stderr)
    
    # Output JSON (without base64 data for stdout summary)
    summary = [{'example': r['example'], 'score_id': r['score_id'], 
                'png_size': len(base64.b64decode(r['png_base64'].split(',')[1]))}
               for r in results]
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
