# -*- coding: utf-8 -*-
"""验证「废料区定位点」方案：定位点是否全部落在废料里、是否对准刀口线。

关键结论用**逐像素扫描**给出：台签区域内的非白像素数必须为 0，
也就是成品台签上不残留任何标记。
"""

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
    print(s)


def region_has_ink(img, x0_mm, y0_mm, x1_mm, y1_mm, k):
    """区域(单位 mm)内是否存在非白像素，返回 (有无, 首个命中像素)。"""
    x0 = max(0, int(round(x0_mm * k)))
    x1 = min(img.width(), int(round(x1_mm * k)))
    y0 = max(0, int(round(y0_mm * k)))
    y1 = min(img.height(), int(round(y1_mm * k)))
    for y in range(y0, y1):
        row = bytes(img.constScanLine(y))[: img.width() * 4]
        seg = row[x0 * 4: x1 * 4]
        # 纯白像素 = 4 个 0xFF；只要有一个字节小于 255 就说明有墨
        if seg.count(255) < len(seg):
            return True, (x0, y)
    return False, None


def render(opt, names, pw=210.0, ph=297.0, dpi=200.0):
    k = dpi / 25.4
    img = QImage(int(pw * k), int(ph * k), QImage.Format.Format_RGB32)
    img.fill(QColor("white"))
    p = QPainter(img)
    core.render_page(p, names, opt, pw, ph, k, k)
    p.end()
    return img, k


def check_clean(img, k, rects, inset_mm=0.0, tag=""):
    """逐个台签扫非白像素。inset_mm>0 时只查内缩后的区域。"""
    out = []
    for i, (x0, y0, x1, y1) in enumerate(rects, 1):
        hit, at = region_has_ink(img, x0 + inset_mm, y0 + inset_mm,
                                 x1 - inset_mm, y1 - inset_mm, k)
        out.append(hit)
        log(f"    {tag}第{i}张 ({x0:.0f},{y0:.0f})-({x1:.0f},{y1:.0f})mm -> "
            f"{'有墨 ' + str(at) if hit else '完全干净 ✔'}")
    return out


def main():
    app = QApplication(sys.argv)
    fams = list(QFontDatabase.families())
    fam = next((f for f in core.CJK_PREFERRED if f in set(fams)), "Arial")
    log(f"字体 = {fam}")

    pw, ph = 210.0, 297.0
    opt = core.Options(font_family=fam, plate_w=150.0, plate_h=80.0,
                       padding_mm=4.0, layout="compact", marks="tick")
    cols, rows = core.layout_count(pw, ph, opt)
    pos = core.layout_positions(pw, ph, opt, cols, rows)
    xs, ys = core.cut_plan(pw, ph, opt, cols, rows)
    segs = core.tick_segments(pos, opt, pw, ph, cols, rows)
    plate_rects = [(x, y, x + opt.plate_w, y + opt.plate_h) for x, y in pos]

    log("")
    log(f"默认 marks = {opt.marks}    每页 {cols} 列 x {rows} 行")
    log(f"刀口线：竖切 x={xs}   横切 y={ys}   共 {len(xs)+len(ys)} 刀")
    log(f"定位点共 {len(segs)} 个：")
    for x1, y1, x2, y2 in segs:
        if abs(x1 - x2) < 1e-6:
            log(f"    ▏竖短线  x={x1:6.1f}   y {min(y1,y2):6.1f} → {max(y1,y2):6.1f}"
                f"    (中心 y={(y1+y2)/2:.1f}，对应横切 y)")
        else:
            log(f"    ▔横短线  y={y1:6.1f}   x {min(x1,x2):6.1f} → {max(x1,x2):6.1f}"
                f"    (端头 x={min(x1,x2):.1f}，对应竖切 x)")

    # ---- 检查 1：数学上每个定位点都必须在废料里 ----
    bad = [s for s in segs
           if not core._rect_is_scrap(min(s[0], s[2]), min(s[1], s[3]),
                                      max(s[0], s[2]), max(s[1], s[3]), plate_rects)]
    log("")
    log(f"检查1  定位点全部位于废料内 = {not bad}（越界 {len(bad)} 个）")

    # ---- 检查 2：定位点与刀口线的对齐误差 ----
    log("检查2  定位点与刀口线的对齐误差：")
    for x in xs:
        mine = [min(s[0], s[2]) if max(s[0], s[2]) > x else max(s[0], s[2])
                for s in segs if abs(s[1] - s[3]) < 1e-6
                and abs((min(s[0], s[2]) if max(s[0], s[2]) > x else
                         max(s[0], s[2])) - x) < 6.5]
        log(f"    竖切 x={x:g}mm ← 端头 {[round(v, 2) for v in mine]}"
            f"   最大误差 {max((abs(v - x) for v in mine), default=-1):.3f} mm")
    for y in ys:
        cys = [round((s[1] + s[3]) / 2.0, 2) for s in segs
               if abs(s[0] - s[2]) < 1e-6 and abs((s[1] + s[3]) / 2.0 - y) < 8.0]
        log(f"    横切 y={y:g}mm ← 中心 {cys}"
            f"   最大误差 {max((abs(v - y) for v in cys), default=-1):.3f} mm")

    # ---- 检查 3：像素级证明台签区域 100% 干净（故意不放文字）----
    img, k = render(opt, [])
    log("")
    log("检查3  【定位点方案】不放文字，只看标记 —— 台签区域内非白像素：")
    hits = check_clean(img, k, plate_rects)
    log(f"    结论：{sum(hits)} / {len(hits)} 张台签上有残留标记 "
        f"（期望 0）")

    img2, _ = render(opt, ["张三", "李四", "欧阳明月"])
    img2.save(os.path.join(OUT, "_mk_定位点整页.png"))

    # ---- 检查 4：对照 —— 贯通虚线方案在新绘制顺序下也不再脏台签 ----
    optg = core.Options(**opt.to_dict())
    optg.marks = "guide"
    imgg, _ = render(optg, [])
    log("")
    log("检查4  【虚线方案·对照】台签内缩 0.6mm 内非白像素：")
    check_clean(imgg, k, plate_rects, inset_mm=0.6, tag="虚线 ")
    imgg2, _ = render(optg, ["张三", "李四", "欧阳明月"])
    imgg2.save(os.path.join(OUT, "_mk_虚线整页.png"))

    # ---- 检查 5：定位点确实落在右侧废料条里 ----
    log("")
    log("检查5  右侧废料条 (150.6~210mm) 内有定位点 = "
        f"{region_has_ink(img, 150.6, 0, 210, 297, k)[0]}  ← 切完随废料丢弃")
    log("      台签区+底部废料 (0~150mm) 内无定位点 = "
        f"{not region_has_ink(img, 0, 0, 150, 297, k)[0]}")

    # ---- 检查 6：边界情况 ----
    log("")
    log("检查6  边界情况：")
    o = core.Options(**opt.to_dict())
    c, r = core.layout_count(297.0, 210.0, o)
    n = len(core.tick_segments(core.layout_positions(297.0, 210.0, o, c, r),
                               o, 297.0, 210.0, c, r))
    log(f"    A4 横向 150×80 -> {c}列x{r}行，定位点 {n} 个")

    o2 = core.Options(**opt.to_dict())
    o2.plate_w, o2.plate_h = 105.0, 99.0
    c2, r2 = core.layout_count(pw, ph, o2)
    xs2, ys2 = core.cut_plan(pw, ph, o2, c2, r2)
    n2 = len(core.tick_segments(core.layout_positions(pw, ph, o2, c2, r2),
                                o2, pw, ph, c2, r2))
    log(f"    105×99 正好铺满 A4 -> {c2}列x{r2}行，刀数 {len(xs2)+len(ys2)}，"
        f"定位点 {n2} 个（应为 0）")

    o3 = core.Options(**opt.to_dict())
    o3.layout, o3.marks = "grid", "tick"
    c3, r3 = core.layout_count(pw, ph, o3)
    n3 = len(core.tick_segments(core.layout_positions(pw, ph, o3, c3, r3),
                                o3, pw, ph, c3, r3))
    log(f"    居中排版 + 定位点 -> {c3}列x{r3}行，tick_segments={n3}"
        f"（应为 0，绘制时退回四角角标）")

    with open(os.path.join(OUT, "_mk_log.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(LOG))
    return 0


if __name__ == "__main__":
    sys.exit(main())
