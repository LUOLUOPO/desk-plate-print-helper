# -*- coding: utf-8 -*-
"""验证「贴边紧凑 + 切割线」排版：位置、切线、文字居中，全部量化检查。"""

import os
import sys

from PySide6.QtGui import QColor, QFontDatabase, QImage, QPainter
from PySide6.QtWidgets import QApplication

import core

OUT = os.path.dirname(os.path.abspath(__file__))
LOG = []


def log(*a):
    s = " ".join(str(x) for x in a)
    LOG.append(s)


def ink_bbox(img, x0, y0, x1, y1, thr=200):
    """在给定像素矩形内扫描非白像素的外接框。"""
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(img.width(), x1), min(img.height(), y1)
    bx0, by0, bx1, by1 = x1, y1, -1, -1
    for y in range(y0, y1):
        b = bytes(img.constScanLine(y))
        row = b[: img.width() * 4]
        for x in range(x0, x1):
            i = x * 4
            if row[i] < thr or row[i + 1] < thr or row[i + 2] < thr:
                if x < bx0:
                    bx0 = x
                if x > bx1:
                    bx1 = x
                if y < by0:
                    by0 = y
                if y > by1:
                    by1 = y
    if bx1 < 0:
        return None
    return bx0, by0, bx1, by1


def main():
    app = QApplication(sys.argv)
    fams = list(QFontDatabase.families())
    fam = next((f for f in core.CJK_PREFERRED if f in set(fams)), "Arial")

    opt = core.Options(font_family=fam, plate_w=150.0, plate_h=80.0,
                       padding_mm=4.0, layout="compact", marks="guide")
    pw, ph = 210.0, 297.0

    cols, rows = core.layout_count(pw, ph, opt)
    pos = core.layout_positions(pw, ph, opt, cols, rows)
    xs, ys = core.cut_plan(pw, ph, opt, cols, rows)

    log(f"字体 = {fam}")
    log(f"排版 = {opt.layout}   每页 {cols} 列 x {rows} 行")
    log(f"台签左上角坐标 (mm) = {[(round(a,2), round(b,2)) for a, b in pos]}")
    log(f"竖切线 x (mm) = {xs}")
    log(f"横切线 y (mm) = {ys}")
    log(f"总刀数 = {len(xs) + len(ys)}")

    # ---- 渲染 ----
    dpi = 200.0
    k = dpi / 25.4
    names = ["张三", "李四", "欧阳明月"]
    img = QImage(int(pw * k), int(ph * k), QImage.Format.Format_RGB32)
    img.fill(QColor("white"))
    p = QPainter(img)
    core.render_page(p, names, opt, pw, ph, k, k)
    p.end()
    img.save(os.path.join(OUT, "_v_紧凑整页.png"))

    # ---- 检查 1：切割线确实是"线"（在预期坐标上能找到非白像素）----
    for x in xs:
        px = int(x * k)
        col = ink_bbox(img, px - 2, 0, px + 3, img.height())
        log(f"检查竖切线 x={x:g}mm -> 像素 {px} 处非白范围 = {col}")

    for y in ys:
        py = int(y * k)
        row = ink_bbox(img, 0, py - 2, img.width(), py + 3)
        log(f"检查横切线 y={y:g}mm -> 像素 {py} 处非白范围 = {row}")

    # ---- 检查 2：第 1 张台签内文字墨迹是否居中 ----
    pad = opt.padding_mm
    x0, y0 = pos[0]
    box = (int((x0 + pad) * k), int((y0 + pad) * k),
           int((x0 + opt.plate_w - pad) * k), int((y0 + opt.plate_h - pad) * k))
    # 只在台签内部扫描，避开切割线
    bb = ink_bbox(img, int(x0 * k) + 3, int(y0 * k) + 3,
                  int((x0 + opt.plate_w) * k) - 3,
                  int((y0 + opt.plate_h) * k) - 3)
    if bb:
        cx_px = (bb[0] + bb[2]) / 2.0
        cy_px = (bb[1] + bb[3]) / 2.0
        want_x = (x0 + opt.plate_w / 2) * k
        want_y = (y0 + opt.plate_h / 2) * k
        log(f"第1张墨迹 bbox(px) = {bb}")
        log(f"  墨迹尺寸 = {(bb[2]-bb[0])/k:.1f} x {(bb[3]-bb[1])/k:.1f} mm"
            f"  (可用 {opt.plate_w-2*pad:.1f} x {opt.plate_h-2*pad:.1f} mm)")
        log(f"  水平偏差 = {(cx_px-want_x)/k:+.2f} mm，垂直偏差 = {(cy_px-want_y)/k:+.2f} mm")
        log(f"  左边缘距纸边 = {bb[0]/k:.1f} mm（应 >= 0）")
        log(f"  填充率 = {(bb[2]-bb[0])/k/(opt.plate_w-2*pad)*100:.1f}% x "
            f"{(bb[3]-bb[1])/k/(opt.plate_h-2*pad)*100:.1f}%")

    # ---- 检查 3：黑底白字 + 切割线的对比度 ----
    opt2 = core.Options(**opt.to_dict())
    opt2.invert = True
    img2 = QImage(int(pw * k), int(ph * k), QImage.Format.Format_RGB32)
    img2.fill(QColor("white"))
    p = QPainter(img2)
    core.render_page(p, names, opt2, pw, ph, k, k)
    p.end()
    img2.save(os.path.join(OUT, "_v_紧凑黑底.png"))

    # 检查 4：居中模式仍然可用（回归）
    opt3 = core.Options(**opt.to_dict())
    opt3.layout = "grid"
    opt3.marks = "corner"
    c2, r2 = core.layout_count(pw, ph, opt3)
    log(f"居中模式回归检查：{c2} 列 x {r2} 行，切线 = {core.cut_plan(pw, ph, opt3, c2, r2)}")
    img3 = QImage(int(pw * k), int(ph * k), QImage.Format.Format_RGB32)
    img3.fill(QColor("white"))
    p = QPainter(img3)
    core.render_page(p, names, opt3, pw, ph, k, k)
    p.end()
    img3.save(os.path.join(OUT, "_v_居中回归.png"))

    # 检查 5：内容放不下时的边界情况
    opt4 = core.Options(**opt.to_dict())
    opt4.plate_w, opt4.plate_h = 220.0, 300.0
    log(f"超大台签(220x300) -> {core.layout_count(pw, ph, opt4)}  (应为 (0, 0))")

    with open(os.path.join(OUT, "_verify_log.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(LOG))
    return 0


if __name__ == "__main__":
    sys.exit(main())
