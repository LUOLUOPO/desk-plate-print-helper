# -*- coding: utf-8 -*-
"""生成"拉伸铺满 vs 自动折行"的对比图，用来直观确认"字多也不折行、整行撑满"。

输出： _view_排版对比.png （可直接作为交付示例图）
"""
import os
import sys

from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter, QPen
from PySide6.QtWidgets import QApplication

import core

OUT = os.path.dirname(os.path.abspath(__file__))
DPI = 200.0
K = DPI / 25.4
PLATE_W, PLATE_H = 150.0, 80.0

CASES = [
    "慕容雪见·兰|编制质控单位|专家组长",
    "张小三四五六七八九",
    "中国国际航空股份有限公司",
]
COLS = [("拉伸铺满（新版默认，每段一行）", "stretch"),
        ("自动折行铺满（可选，保持字形）", "wrap")]


def plate_image(fam, name, mode, marks="tick"):
    """渲染一整页，把第 1 张台签抠出来。"""
    opt = core.Options(font_family=fam, plate_w=PLATE_W, plate_h=PLATE_H,
                       fit_mode=mode, marks=marks)
    img = QImage(int(210 * K), int(297 * K), QImage.Format.Format_RGB32)
    img.setDotsPerMeterX(int(DPI / 0.0254))
    img.setDotsPerMeterY(int(DPI / 0.0254))
    img.fill(QColor("white"))
    p = QPainter(img)
    core.render_page(p, [name], opt, 210.0, 297.0, K, K)
    p.end()
    return img.copy(QRect(0, 0, int(PLATE_W * K), int(PLATE_H * K))), opt


def caption(opt, name, mode):
    bw = PLATE_W - 2 * opt.padding_mm
    bh = PLATE_H - 2 * opt.padding_mm
    pt = core.layout_plate_text(opt.font_family, opt.bold, name, bw, bh, opt)
    if pt.rows:
        s = [r.sx for r in pt.rows]
        return (f"{len(pt.rows)} 段 → {len(pt.rows)} 行（不折行） · "
                f"字面高 {pt.em_mm:.1f}mm · 横向 ×{min(s):.2f}~{max(s):.2f}")
    w = pt.main.width_mm / bw * 100.0
    return (f"{pt.main.count} 行 {pt.main.lines} · "
            f"字面高 {pt.main.em_mm:.1f}mm · 铺满宽 {w:.0f}%")


def main():
    QApplication(sys.argv)
    fams = list(QFontDatabase.families())
    fam = next((f for f in core.CJK_PREFERRED if f in fams), fams[0])

    pw, ph = int(PLATE_W * K), int(PLATE_H * K)
    pad_x, pad_y, gap = 40, 30, 30
    title_h, cap_h = 46, 74
    board_w = pad_x * 2 + pw * len(COLS) + gap * (len(COLS) - 1)
    board_h = pad_y * 2 + title_h + (ph + cap_h + gap) * len(CASES)
    board = QImage(board_w, board_h, QImage.Format.Format_RGB32)
    board.fill(QColor("#e9edf3"))

    p = QPainter(board)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    f_title = QFont(fam, 26, QFont.Weight.Bold)
    f_cap = QFont(fam, 19)
    f_cap.setBold(True)

    p.setFont(f_title)
    for c, (label, _mode) in enumerate(COLS):
        p.setPen(QPen(QColor("#0f766e") if c == 0 else QColor("#9a3412")))
        p.drawText(pad_x + c * (pw + gap) + 6, pad_y + 32, label)

    for i, name in enumerate(CASES):
        y = pad_y + title_h + i * (ph + cap_h + gap)
        for c, (_label, mode) in enumerate(COLS):
            x = pad_x + c * (pw + gap)
            im, opt = plate_image(fam, name, mode)
            p.drawImage(x, y, im)
            p.setPen(QPen(QColor("#94a3b8"), 1))
            p.drawRect(x, y, pw - 1, ph - 1)
            p.setFont(f_cap)
            p.setPen(QPen(QColor("#0f766e") if c == 0 else QColor("#9a3412")))
            p.drawText(x + 4, y + ph + 30, caption(opt, name, mode))
    p.end()

    board.scaledToWidth(1100).save(os.path.join(OUT, "_view_排版对比.png"))
    print("ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
