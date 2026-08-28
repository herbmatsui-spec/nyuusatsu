#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
開発者用: スキャンPDF生成ツール (Step 27)
pip install pillow reportlab
"""

import os
import sys
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def generate_scanned_pdf(
    output_path: str,
    text_lines: list[str],
    dpi: int = 300,
) -> None:
    """スキャン風PDFを生成"""
    # A4 at 300 DPI
    width, height = 2480, 3508
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    # フォント選定 (OSごとに探す)
    font_paths = [
        r"C:\Windows\Fonts\msgothic.ttc",
        r"C:\Windows\Fonts\arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    font = None
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                font = ImageFont.truetype(fp, size=80)
                break
            except Exception:
                continue
    if font is None:
        font = ImageFont.load_default()

    # テキスト描画
    y = 200
    for line in text_lines:
        draw.text((200, y), line, fill="black", font=font)
        y += 120

    # 一時画像保存 → PDF変換
    base_name = os.path.splitext(os.path.basename(output_path))[0]
    temp_img = f"_temp_{base_name}.png"
    img.save(temp_img, dpi=(dpi, dpi))

    c = canvas.Canvas(output_path, pagesize=A4)
    c.drawImage(temp_img, 0, 0, width=595, height=842)
    c.save()

    os.remove(temp_img)
    print(f"生成完了: {output_path}")


if __name__ == "__main__":
    # 出力先
    out = "tests/test_scanned.pdf"
    if len(sys.argv) > 1:
        out = sys.argv[1]

    text_lines = [
        "入札公告書",
        "",
        "件名: ○○市下水道管布設工事",
        "",
        "予算金額: 15,000,000円",
        "工期: 2026年10月1日 〜 2027年3月31日",
        "",
        "参加資格: 建設業法に基づく管工事業の許可を有する者",
    ]
    generate_scanned_pdf(out, text_lines)