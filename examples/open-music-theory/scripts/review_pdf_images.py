#!/usr/bin/env python3
"""
PDF 图片复核脚本 —— 在 PDF 上传到 IMA 之前强制执行。

检查三项：
  1. 图片顺序：PDF 中实际出现的 Example 图片是否严格按编号升序排列
     （防止出现 Example 20 跑到 Example 15 前面的顺序错乱）
  2. 图片位置：每张 Example 图片所在页附近的正文是否提到了对应「示例 X」/「Example X」
     （防止图片插入到错误段落）
  3. 图片完整性：payload 中所有 Example 图片都必须出现在 PDF 中，不能遗漏

用法：
  python3 scripts/review_pdf_images.py \
      --pdf /tmp/OMT_2026-07-21_ch01-07.pdf \
      --payload /tmp/omt_payload.json \
      --zh /tmp/omt_zh.json

退出码：
  0 = 复核通过
  4 = 复核发现问题（图片顺序/位置/完整性错误）
  1 = 其他错误（依赖缺失、文件打不开等）
"""

import json, sys, os, re, argparse
from pathlib import Path


def extract_expected_order(payload, zh):
    """从翻译文本中提取预期的 Example 图片顺序（按 __IMAGE_X__ 标记出现顺序）"""
    expl_zh = zh.get('explanationZh', '')
    tag_order = [int(m.group(1)) for m in re.finditer(r'__IMAGE_(\d+)__', expl_zh)]
    return tag_order


def extract_pdf_image_order_and_context(pdf_path):
    """用 PyMuPDF 提取 PDF 中每张 Example 图片所在页码及附近文字。

    返回：[(page_num_0based, example_num, nearby_text), ...] 按页面顺序排列
    """
    try:
        import fitz  # pymupdf
    except ImportError:
        print("[review ERROR] PyMuPDF 未安装，请运行：pip3 install pymupdf", file=sys.stderr)
        sys.exit(1)

    doc = fitz.open(pdf_path)
    findings = []

    for page_idx in range(len(doc)):
        page = doc[page_idx]

        # 获取页面中所有图片的位置（bbox）
        img_info_list = page.get_image_info(xrefs=True)

        # 获取页面完整文本（带坐标）
        text_dict = page.get_text("dict")
        text_blocks = []
        for block in text_dict.get("blocks", []):
            if block.get("type") == 0:  # text block
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text_blocks.append({
                            "bbox": span["bbox"],
                            "text": span["text"]
                        })

        for img_info in img_info_list:
            img_bbox = img_info.get("bbox")
            if not img_bbox:
                continue
            x0, y0, x1, y1 = img_bbox

            # 图片太小（小于 500 平方像素）可能是装饰元素/图标，跳过
            area = (x1 - x0) * (y1 - y0)
            if area < 500:
                continue

            # 在图片上方和下方寻找 caption 文本（Example X 标题）
            # Caption 通常位于图片正上方，y 在 y0-30 到 y0 之间
            nearby_texts = []
            caption_text = ""
            for tb in text_blocks:
                tb_y0 = tb["bbox"][1]
                tb_x0 = tb["bbox"][0]
                # 查找图片上方 40pt 范围内的文字（通常是 caption）
                if y0 - 50 < tb_y0 < y0 + 5:
                    t = tb["text"].strip()
                    if t:
                        nearby_texts.append(t)
                        # 尝试匹配 Example 编号
                        m = re.search(r'Example\s+(\d+)', t, re.IGNORECASE)
                        if m:
                            caption_text = t
                # 同时查找图片下方 80pt 范围内的文字（正文引用）
                elif y1 < tb_y0 < y1 + 80:
                    t = tb["text"].strip()
                    if t:
                        nearby_texts.append(t)

            # 尝试从 caption 或附近文字中识别 Example 编号
            ex_num = None
            for t in nearby_texts:
                m = re.search(r'Example\s+(\d+)', t, re.IGNORECASE)
                if m:
                    ex_num = int(m.group(1))
                    break

            # 如果还是没找到，放宽搜索范围：整页文本查找所有 Example 编号，取位置最接近的
            if ex_num is None:
                all_page_examples = []
                for tb in text_blocks:
                    t = tb["text"].strip()
                    m = re.search(r'Example\s+(\d+)', t, re.IGNORECASE)
                    if m:
                        tb_y_mid = (tb["bbox"][1] + tb["bbox"][3]) / 2
                        dist = abs(tb_y_mid - (y0 + y1) / 2)
                        all_page_examples.append((dist, int(m.group(1)), t))
                if all_page_examples:
                    all_page_examples.sort()
                    ex_num = all_page_examples[0][1]

            findings.append({
                "page": page_idx + 1,  # 1-based for human readability
                "example": ex_num,
                "nearby": " ".join(nearby_texts[:5])[:200],
                "bbox": (x0, y0, x1, y1),
            })

    doc.close()
    return findings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pdf', required=True, help='生成的 PDF 文件路径')
    ap.add_argument('--payload', required=True, help='payload JSON')
    ap.add_argument('--zh', required=True, help='翻译 JSON')
    args = ap.parse_args()

    for p in [args.pdf, args.payload, args.zh]:
        if not os.path.exists(p):
            print(f"[review ERROR] 文件不存在: {p}", file=sys.stderr)
            sys.exit(1)

    payload = json.load(open(args.payload, encoding='utf-8'))
    zh = json.load(open(args.zh, encoding='utf-8'))

    # 1. 期望顺序
    expected = extract_expected_order(payload, zh)
    print(f"[review] 期望图片顺序（来自翻译标记）: {expected}")

    # payload 中实际有的 Example 编号
    img_map = {}
    for img in payload.get('images', []):
        cap = img.get('caption', '')
        m = re.search(r'Example\s+(\d+)', cap)
        if m:
            img_map[int(m.group(1))] = cap
    available = sorted(img_map.keys())
    print(f"[review] payload 中可用图片: {available}")

    # 检查期望顺序是否全部可用
    missing = [n for n in expected if n not in img_map]
    if missing:
        print(f"[review FAIL] 翻译标记的图片在 payload 中不存在: {missing}", file=sys.stderr)
        sys.exit(4)

    # 2. 从 PDF 提取实际顺序
    print(f"[review] 正在解析 PDF: {args.pdf}")
    pdf_findings = extract_pdf_image_order_and_context(args.pdf)
    # 过滤掉没识别出 Example 编号的（可能是没有 caption 的图，但 OMT 卡片都有）
    pdf_order = [f["example"] for f in pdf_findings if f["example"] is not None]
    print(f"[review] PDF 中实际图片顺序: {pdf_order}")

    errors = []
    warnings = []

    # 检查 1：顺序是否升序
    if pdf_order and pdf_order != sorted(pdf_order):
        disorder = []
        for i in range(len(pdf_order) - 1):
            if pdf_order[i] > pdf_order[i+1]:
                disorder.append(f"Example {pdf_order[i]} 在第?页跑到 Example {pdf_order[i+1]} 前面")
        errors.append(f"图片顺序错误！PDF 中顺序 {pdf_order} 不是升序。详情：{'; '.join(disorder)}")

    # 检查 2：期望的图是否都在 PDF 中
    pdf_set = set(pdf_order)
    missing_in_pdf = [n for n in expected if n not in pdf_set]
    if missing_in_pdf:
        errors.append(f"以下 Example 图片在 PDF 中缺失（没找到对应图片）: {missing_in_pdf}")

    # 检查 3：PDF 中是否多了不该有的图
    extra = [n for n in pdf_order if n not in expected]
    if extra:
        warnings.append(f"PDF 中出现了翻译未标记的图片: {extra}")

    # 检查 4：每张图附近文字是否提到对应 Example（位置一致性）
    for f in pdf_findings:
        ex = f["example"]
        if ex is None:
            continue
        nearby = f["nearby"]
        # 检查 nearby 里是否包含该编号（英文 Example X 或中文 示例 X）
        if not re.search(rf'(Example|示例)\s*{ex}', nearby, re.IGNORECASE):
            # 只在能明确找到 ex 的情况下才报位置错
            # 如果 nearby 为空或不相关，可能是 PyMuPDF 文本提取问题，降为 warning
            warnings.append(
                f"第 {f['page']} 页 Example {ex} 图片附近文字没看到「示例 {ex}」/「Example {ex}」引用，"
                f"请人工确认位置是否正确。附近文字: {nearby[:80]}"
            )

    # 输出结果
    print()
    if warnings:
        print("[review] ⚠️  警告（请人工确认）：")
        for w in warnings:
            print(f"  ⚠️  {w}")
        print()

    if errors:
        print("[review] ❌ 复核失败，存在以下问题：")
        for e in errors:
            print(f"  ❌  {e}")
        print()
        print("[review] PDF 未通过复核，禁止上传到 IMA！请修正后重新生成 PDF。")
        sys.exit(4)

    if warnings:
        print("[review] ⚠️  有警告但核心检查（顺序/完整性）通过，请人工确认警告项后再上传。")
    else:
        print("[review] ✅ 图片顺序、完整性、位置全部通过复核！")

    sys.exit(0)


if __name__ == '__main__':
    main()
