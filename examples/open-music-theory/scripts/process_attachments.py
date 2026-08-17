#!/usr/bin/env python3
"""
Process OMT relatedLinks attachments:
1. Download file links (pdf/docx/png/jpg/etc.)
2. Automatically convert PNG files to JPG (high quality, white background for transparency)
3. Skip files already embedded in PDF (base64 images in payload.images)
4. Output renamed files ready for upload to IMA

Usage:
  python3 process_attachments.py --payload /tmp/omt_payload.json --date 2026-07-26 --card-id ch01-12 --out-dir /tmp/omt_attachments
"""
import argparse
import json
import os
import subprocess
import re
from urllib.parse import urlparse
from PIL import Image

EXTENSIONS = {'.pdf', '.docx', '.xlsx', '.doc', '.pptx', '.png', '.jpg', '.jpeg', '.gif', '.webp'}
IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

def run_curl(url, out_path, referer="https://viva.pressbooks.pub/"):
    """Download file with curl, return True if successful and file looks valid."""
    cmd = [
        "curl", "-sL",
        "-A", USER_AGENT,
        "-H", "Accept: image/*,application/pdf,*/*",
        "-e", referer,
        url,
        "-o", out_path
    ]
    subprocess.run(cmd, capture_output=True, timeout=60)
    if not os.path.exists(out_path):
        return False
    # Check file type - skip HTML error pages
    result = subprocess.run(["file", out_path], capture_output=True, text=True)
    if "HTML document" in result.stdout or "ASCII text" in result.stdout:
        os.unlink(out_path)
        return False
    return True

def png_to_jpg(png_path, quality=95):
    """Convert PNG to JPG, handling transparency with white background. Returns new path."""
    img = Image.open(png_path)
    jpg_path = os.path.splitext(png_path)[0] + '.jpg'
    
    if img.mode in ('RGBA', 'LA'):
        background = Image.new('RGB', img.size, (255, 255, 255))
        mask = img.split()[-1] if img.mode == 'RGBA' else img.split()[1]
        background.paste(img, mask=mask)
        img = background
    elif img.mode != 'RGB':
        img = img.convert('RGB')
    
    img.save(jpg_path, 'JPEG', quality=quality)
    os.unlink(png_path)  # remove original PNG after conversion
    return jpg_path

def sanitize_filename(name):
    """Clean filename for IMA upload."""
    name = re.sub(r'[^\w\-\. ]', '_', name)
    name = re.sub(r'\s+', '_', name)
    return name

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--payload', required=True, help='Path to omt_payload.json')
    ap.add_argument('--date', required=True, help='Date for filename (YYYY-MM-DD)')
    ap.add_argument('--card-id', required=True, help='Card ID (e.g. ch01-12)')
    ap.add_argument('--out-dir', default='/tmp/omt_attachments', help='Output directory')
    args = ap.parse_args()
    
    os.makedirs(args.out_dir, exist_ok=True)
    
    with open(args.payload) as f:
        payload = json.load(f)
    
    # Collect already embedded image srcs to skip duplicates
    embedded_srcs = set()
    for img in payload.get('images', []):
        src = img.get('src', '')
        if src:
            embedded_srcs.add(src)
    
    processed = []
    skipped = []
    
    for link in payload.get('relatedLinks', []):
        href = link.get('href', '')
        parsed = urlparse(href)
        ext = os.path.splitext(parsed.path)[1].lower()
        
        # Only process actual files
        if ext not in EXTENSIONS:
            continue
        
        # Skip images already embedded in PDF
        if href in embedded_srcs and ext in IMAGE_EXTS:
            skipped.append(('already_embedded', href))
            continue
        
        # Get original filename
        orig_name = os.path.basename(parsed.path)
        orig_name = sanitize_filename(orig_name)
        
        print(f"Processing: {href}")
        print(f"  Original: {orig_name}")
        
        # Download
        tmp_path = os.path.join(args.out_dir, orig_name)
        if not run_curl(href, tmp_path):
            print(f"  ❌ Download failed or invalid file (likely 403/404)")
            skipped.append(('download_failed', href))
            continue
        
        # Convert PNG to JPG
        final_path = tmp_path
        if ext == '.png':
            print(f"  Converting PNG -> JPG...")
            try:
                final_path = png_to_jpg(tmp_path)
                orig_name = os.path.splitext(orig_name)[0] + '.jpg'
                print(f"  ✅ Converted: {os.path.basename(final_path)}")
            except Exception as e:
                print(f"  ❌ Conversion failed: {e}")
                skipped.append(('convert_failed', href))
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                continue
        
        # Rename to OMT standard format: OMT_<date>_<card_id>_<filename>
        final_name = f"OMT_{args.date}_{args.card_id}_{orig_name}"
        final_renamed = os.path.join(args.out_dir, final_name)
        if final_path != final_renamed:
            os.rename(final_path, final_renamed)
        
        processed.append({
            'href': href,
            'local_path': final_renamed,
            'filename': final_name,
            'converted_from_png': ext == '.png'
        })
        print(f"  ✅ Ready: {final_name}")
        print()
    
    # Output summary
    print("=" * 60)
    print(f"Processed {len(processed)} files, skipped {len(skipped)}:")
    for p in processed:
        status = " (PNG->JPG)" if p['converted_from_png'] else ""
        print(f"  ✅ {p['filename']}{status}")
    for reason, url in skipped:
        print(f"  ⏭️  Skipped ({reason}): {url}")
    
    # Output JSON for further processing
    result = {
        'date': args.date,
        'card_id': args.card_id,
        'processed': processed,
        'skipped': skipped,
        'out_dir': args.out_dir
    }
    with open(os.path.join(args.out_dir, 'attachments.json'), 'w') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"\nResult saved to {os.path.join(args.out_dir, 'attachments.json')}")

if __name__ == '__main__':
    main()
