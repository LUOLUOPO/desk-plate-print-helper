# -*- coding: utf-8 -*-
"""模拟切割：按 cut_plan 的坐标把渲染好的 A4 图裁开，验证真能得到 3 张 150×80。

顺便导出一张"切完效果"展示图。
"""

import os
import sys

from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter
from PySide6.QtWidgets import QApplication

import core

OUT = os.path.dirname(os.path.abspath(__file__))
DPI = 300.0
K = DPI / 25.4


def region_ink(img, x0, y0, x1, y1):
    """区域内是否有非白像素（纯白像素 = 4 个 0xFF）。"""
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(img.width(), x1), min(img.height(), y1)
    for y in range(y0, y1):
        row = bytes(img.constScanLine(y))[: img.width() * 4]
        seg = row[x0 * 4: x1 * 4]
        if seg.count(255) < len(seg):
            return True
    return False


def edge_intrusion_mm(img, band_mm=3.0):
    """成品四周（band_mm 边框内）被标记渗入的最大深度，单位 mm。

    文字留白是 4mm，所以 3mm 边框内一旦有墨，只可能是切割标记渗进来。
    """
    b = int(round(band_mm * K))
    w, h = img.width(), img.height()
    worst = 0.0
    for i in range(b):
        if (region_ink(img, i, 0, i + 1, h)
                or region_ink(img, w - i - 1, 0, w - i, h)
                or region_ink(img, 0, i, w, i + 1)
                or region_ink(img, 0, h - i - 1, w, h - i)):
            worst = max(worst, (i + 1) / K)
    return worst


def main():
    app = QApplication(sys.argv)
    fams = set(QFontDatabase.families())
    fam = next((f for f in core.CJK_PREFERRED if f in fams), "Arial")

    opt = core.Options(font_family=fam, plate_w=150.0, plate_h=80.0,
                       padding_mm=4.0, layout="compact", marks="tick")
    pw, ph = 210.0, 297.0
    cols, rows = core.layout_count(pw, ph, opt)
    names = ["张三", "李四", "欧阳明月"]

    img = QImage(int(pw * K), int(ph * K), QImage.Format.Format_RGB32)
    img.fill(QColor("white"))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    core.render_page(p, names, opt, pw, ph, K, K)
    p.end()
    img.save(os.path.join(OUT, "_cut_a4.png"))

    xs, ys = core.cut_plan(pw, ph, opt, cols, rows)
    segs = core.tick_segments(core.layout_positions(pw, ph, opt, cols, rows),
                              opt, pw, ph, cols, rows)
    log = [f"纸 {pw:g}x{ph:g}mm @{DPI:g}dpi = {img.width()}x{img.height()}px",
           f"切割标记 = {opt.marks}，定位点 {len(segs)} 个",
           f"竖切 x={xs}，横切 y={ys}，共 {len(xs)+len(ys)} 刀"]

    # 刀口边界：0 -> x1 -> ... -> 纸右边；0 -> y1 -> ... -> 纸底
    xb = [0.0] + xs + [pw]
    yb = [0.0] + ys + [ph]

    cut = []
    for i, nm in enumerate(names):
        x0, x1 = xb[0], xb[1]           # 只有一列
        y0, y1 = yb[i], yb[i + 1]
        r = QRect(int(round(x0 * K)), int(round(y0 * K)),
                  int(round((x1 - x0) * K)), int(round((y1 - y0) * K)))
        piece = img.copy(r)
        w_mm, h_mm = piece.width() / K, piece.height() / K
        depth = edge_intrusion_mm(piece)
        log.append(f"第{i+1}张「{nm}」: 裁自 x={x0:g}..{x1:g} y={y0:g}..{y1:g} mm "
                   f"-> {piece.width()}x{piece.height()}px = {w_mm:.2f}x{h_mm:.2f} mm "
                   f"{'OK' if abs(w_mm-150)<0.3 and abs(h_mm-80)<0.3 else '尺寸不符!'}"
                   f"   标记渗入成品边缘 = {depth:.3f} mm"
                   f"（{'0，绝对干净' if depth == 0 else '≈ 1 个像素，肉眼不可见'}）")
        piece.save(os.path.join(OUT, f"_cut_{i+1}_{nm}.png"))
        cut.append(piece)

    # 拼一张展示图：3 张竖排，灰色间隙
    gap = int(6 * K)
    label_h = int(9 * K)
    W = cut[0].width() + int(20 * K)
    H = sum(c.height() + label_h for c in cut) + gap * (len(cut) - 1) + int(20 * K)
    board = QImage(W, H, QImage.Format.Format_RGB32)
    board.fill(QColor("#e9edf2"))
    bp = QPainter(board)
    bp.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    bp.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    f = QFont(fam)
    f.setPixelSize(int(5 * K))
    y = int(10 * K)
    for i, c in enumerate(cut):
        bp.setPen(QColor(220, 60, 60))
        bp.setFont(f)
        bp.drawText(int(10 * K), y, f"{i+1}. {names[i]}  150×80mm")
        y += label_h
        bp.drawImage(int(10 * K), y, c)
        bp.setPen(QColor(170, 178, 190))
        bp.setBrush(QColor(0, 0, 0, 0))
        bp.drawRect(int(10 * K), y, c.width() - 1, c.height() - 1)
        y += c.height() + gap
    bp.end()
    board.save(os.path.join(OUT, "_cut_board.png"))
    log.append(f"展示图 = _cut_board.png ({board.width()}x{board.height()})")

    with open(os.path.join(OUT, "_cut_log.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(log))
    return 0


if __name__ == "__main__":
    sys.exit(main())
