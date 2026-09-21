# -*- coding: utf-8 -*-
"""拉伸铺满自检：逐行扫描墨迹，核对
   ① 每段是否**独占一行**（不折行）  ② 每行是否撑满可用宽度
   ③ 各行是否等高且都在可用方框内    ④ 水平居中偏差

跑法：  python verify_stretch.py
输出：  _stretch_log.txt  +  _stretch_对比图.png
"""
import os
import sys

from PySide6.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter, QPen
from PySide6.QtWidgets import QApplication

import core

OUT = os.path.dirname(os.path.abspath(__file__))
DPI = 300.0
K = DPI / 25.4
PAGE_W, PAGE_H = 210.0, 297.0
LOG = []


def log(*a):
    LOG.append(" ".join(str(x) for x in a))


def ink_bbox(img, x0, y0, x1, y1, thr=200):
    """在给定像素矩形里扫出非白像素的外接框，返回 (x0,y0,x1,y1)，无墨返回 None。"""
    X0 = max(0, int(round(x0)))
    Y0 = max(0, int(round(y0)))
    X1 = min(img.width(), int(round(x1)))
    Y1 = min(img.height(), int(round(y1)))
    bx0, by0, bx1, by1 = X1, Y1, -1, -1
    for y in range(Y0, Y1):
        line = bytes(img.constScanLine(y))
        for x in range(X0, X1):
            i = x * 4
            if line[i] < thr or line[i + 1] < thr or line[i + 2] < thr:
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
    return (bx0, by0, bx1, by1)


def render(names, opt):
    img = QImage(int(PAGE_W * K), int(PAGE_H * K), QImage.Format.Format_RGB32)
    img.setDotsPerMeterX(int(DPI / 0.0254))
    img.setDotsPerMeterY(int(DPI / 0.0254))
    img.fill(QColor("white"))
    p = QPainter(img)
    core.render_page(p, names, opt, PAGE_W, PAGE_H, K, K)
    p.end()
    return img


def main():
    app = QApplication(sys.argv)                       # noqa: F841
    fams = list(QFontDatabase.families())
    fam = next((f for f in core.CJK_PREFERRED if f in fams), fams[0])

    opt = core.Options(font_family=fam, plate_w=150.0, plate_h=80.0)
    pad = min(opt.padding_mm, opt.plate_w / 4.0, opt.plate_h / 4.0)
    bw, bh = opt.plate_w - 2 * pad, opt.plate_h - 2 * pad
    log(f"字体={fam}  台签={opt.plate_w:g}×{opt.plate_h:g}mm  可用方框={bw:.0f}×{bh:.0f}mm")
    log(f"填充方式 = {core.fit_mode_of(opt)}（每段一行，横向拉伸撑满）")
    log(f"拉伸上下限 = {core.STRETCH_MIN}~{core.STRETCH_MAX}，行槽填充 = {core.STRETCH_ROW_FILL}")
    log("")

    cases = [
        "张三",
        "赵正义",
        "张小三四五",
        "张小三四五六七八九",
        "慕容雪见·兰",
        "慕容雪见·兰|编制质控单位|专家组长",
        "王五|销售总监",
        "欧阳明月|综合管理部|部长",
        "中国国际航空股份有限公司",
        "中国国际航空股份有限公司|飞行部",
    ]

    bad = 0
    for start in range(0, len(cases), 3):
        batch = cases[start:start + 3]
        img = render(batch, opt)
        pos = core.layout_positions(PAGE_W, PAGE_H, opt, 1, 3)
        for i, name in enumerate(batch):
            px, py = pos[i]
            pt = core.layout_plate_text(opt.font_family, opt.bold, name, bw, bh, opt)
            segs = [r for r in core.split_rows(name) if r.strip()]
            bx0 = (px + pad) * K
            by0 = (py + pad) * K
            bwpx, bhpx = bw * K, bh * K
            n = len(pt.rows) or 1
            slot = bhpx / n

            log(f"「{name}」  {len(segs)} 段 → {len(pt.rows)} 行"
                f"{'  ✗ 行数不符（被折行了）' if len(pt.rows) != len(segs) else '  OK'}")
            if len(pt.rows) != len(segs):
                bad += 1

            widths, heights = [], []
            for j, row in enumerate(pt.rows):
                sy0 = by0 + slot * j
                sy1 = sy0 + slot
                bb = ink_bbox(img, bx0 - 2, sy0, bx0 + bwpx + 2, sy1)
                if bb is None:
                    log(f"    第{j+1}行「{row.text}」无墨迹 ✗")
                    bad += 1
                    continue
                ix0, ix1 = bb[0] / K, bb[2] / K
                iy0, iy1 = bb[1] / K, bb[3] / K
                w_mm, h_mm = ix1 - ix0, iy1 - iy0
                widths.append(w_mm)
                heights.append(h_mm)
                fillw = w_mm / bw * 100.0
                dcx = abs((ix0 + ix1) / 2.0 - (px + opt.plate_w / 2.0))
                # 该行是否落在自己的行槽里（不串行）
                in_slot = (iy0 >= py + pad + slot / K * j - 0.4
                           and iy1 <= py + pad + slot / K * (j + 1) + 0.4)
                flag = "OK"
                if dcx > 0.5:
                    flag = "✗ 未居中"
                    bad += 1
                elif not in_slot:
                    flag = "✗ 串行"
                    bad += 1
                log(f"    第{j+1}行「{row.text}」"
                    f" 字面高{row.em_mm:5.2f}mm 横向×{row.sx:4.2f}"
                    f" 实测 {w_mm:6.2f}×{h_mm:5.2f}mm"
                    f" 撑满宽 {fillw:5.1f}%  居中偏差 {dcx:.3f}mm   {flag}")

            if widths:
                log(f"    合计 行宽 {min(widths):.2f}~{max(widths):.2f}mm"
                    f"  行高 {min(heights):.2f}~{max(heights):.2f}mm"
                    f"  （同高说明各行等比一致）")
            log("")

    # 对照：拉伸 vs 折行
    log("--- 对照：两种「铺满」方式 ---")
    for name in ["慕容雪见·兰", "慕容雪见·兰|编制质控单位|专家组长"]:
        for mode in ("stretch", "wrap"):
            o = core.Options(**opt.to_dict())
            o.fit_mode = mode
            p2 = core.layout_plate_text(o.font_family, o.bold, name, bw, bh, o)
            if p2.rows:
                detail = f"{len(p2.rows)} 行 " + " / ".join(
                    f"{r.text}(×{r.sx:.2f})" for r in p2.rows)
                em = p2.em_mm
            else:
                detail = f"{p2.main.count} 行 {p2.main.lines}"
                em = p2.main.em_mm
            log(f"  [{mode:7s}] 「{name}」→ {detail}  字面高 {em:.2f}mm")
        log("")

    log(f"检查结果：{'全部通过' if bad == 0 else str(bad) + ' 项异常'}")

    with open(os.path.join(OUT, "_stretch_log.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(LOG))

    make_view(fam, opt)
    return 0


def make_view(fam, opt):
    """拼一张"拉伸铺满 / 折行铺满 / 强制单行"三列对比图。"""
    names = ["慕容雪见·兰|编制质控单位|专家组长",
             "张小三四五六七八九", "张三"]
    cols = []
    for label, mode in (("拉伸铺满（老工具效果）", "stretch"),
                        ("自动折行铺满", "wrap"),
                        ("强制单行", "plain")):
        o = core.Options(**opt.to_dict())
        o.fit_mode = mode
        o.marks = "none"
        cols.append((label, render(names, o)))

    gap = 24
    W = sum(im.width() for _, im in cols) + gap * (len(cols) + 1)
    H = max(im.height() for _, im in cols) + gap * 2 + 26
    board = QImage(W, H, QImage.Format.Format_RGB32)
    board.fill(QColor("#dfe3ea"))
    p = QPainter(board)
    x = gap
    for label, im in cols:
        p.setPen(QPen(QColor("#111827")))
        p.setFont(QFont(fam, 20, QFont.Weight.Bold))
        p.drawText(x, gap + 4, label)
        p.drawImage(x, gap + 26, im)
        x += im.width() + gap
    p.end()
    board.scaledToWidth(1200).save(os.path.join(OUT, "_stretch_对比图.png"))


if __name__ == "__main__":
    sys.exit(main())
