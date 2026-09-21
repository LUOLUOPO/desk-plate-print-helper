# -*- coding: utf-8 -*-
"""折行铺满自检：渲染整页，逐像素扫描每张台签的文字墨迹，核对
   ① 是否还留大量空白  ② 是否溢出可用方框  ③ 竖直居中偏差

跑法：  python verify_wrap.py
输出：  _wrap_log.txt  +  _wrap_对比图.png
"""
import os
import sys

from PySide6.QtGui import QColor, QFontDatabase, QImage, QPainter
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
    opt.fit_mode = "wrap"          # 本脚本专测折行模式
    pad = min(opt.padding_mm, opt.plate_w / 4.0, opt.plate_h / 4.0)
    bw, bh = opt.plate_w - 2 * pad, opt.plate_h - 2 * pad
    log(f"字体={fam}  台签={opt.plate_w:g}×{opt.plate_h:g}mm  可用方框={bw:.0f}×{bh:.0f}mm")
    log(f"填充方式={core.fit_mode_of(opt)}  行距={opt.line_pitch}  副标题比例={opt.subtitle_ratio}")
    log("")

    cases = [
        "张三",
        "赵正义",
        "张小三四五",
        "张小三四五六七八九",
        "慕容雪见·兰",
        "欧阳明月月月月月月娜",
        "中国国际航空股份有限公司",
        "王五|销售总监",
        "慕容雪见·兰|编制质控单位|专家组长",
    ]

    # 一页 3 张，分批渲染
    bad = 0
    all_rows = []
    for start in range(0, len(cases), 3):
        batch = cases[start:start + 3]
        img = render(batch, opt)
        pos = core.layout_positions(PAGE_W, PAGE_H, opt, 1, 3)
        for i, name in enumerate(batch):
            px, py = pos[i]
            box = (px * K, py * K, (px + opt.plate_w) * K, (py + opt.plate_h) * K)
            bb = ink_bbox(img, *box)
            exp = core.plate_ink_box(px, py, opt, name)     # mm
            pt = core.layout_plate_text(opt.font_family, opt.bold, name, bw, bh, opt)
            if bb is None:
                log(f"✗ 「{name}」整张台签无墨迹")
                bad += 1
                continue
            ix0, iy0, ix1, iy1 = (bb[0] / K, bb[1] / K, bb[2] / K, bb[3] / K)
            w_mm, h_mm = ix1 - ix0, iy1 - iy0
            # 期望值（墨迹框，单位 mm → 台签内绝对坐标）
            ex0, ey0, ex1, ey1 = exp
            dw, dh = abs(w_mm - (ex1 - ex0)), abs(h_mm - (ey1 - ey0))
            dcx = abs((ix0 + ix1) / 2.0 - (px + opt.plate_w / 2.0))
            dcy = abs((iy0 + iy1) / 2.0 - (py + opt.plate_h / 2.0))

            # 是否溢出可用方框
            ax0, ay0 = px + pad, py + pad
            ax1, ay1 = px + opt.plate_w - pad, py + opt.plate_h - pad
            over = (ix0 < ax0 - 0.35 or ix1 > ax1 + 0.35
                    or iy0 < ay0 - 0.35 or iy1 > ay1 + 0.35)
            fw, fh = w_mm / bw * 100.0, h_mm / bh * 100.0
            row = (f"「{name}」\n"
                   f"   排版 = {pt.main.count} 行 {pt.main.lines if pt.main.count > 1 else ''}"
                   f" 字面高 {pt.main.em_mm:.2f}mm ≈ {core.em_mm_to_pt(pt.main.em_mm):.0f}pt\n"
                   f"   实测墨迹 {w_mm:.2f}×{h_mm:.2f}mm  铺满 {fw:.0f}%×{fh:.0f}%\n"
                   f"   与计算值偏差 宽{dw:.2f} 高{dh:.2f}mm  居中偏差 x{dcx:.2f} y{dcy:.2f}mm"
                   f"   {'✗ 溢出可用区!' if over else 'OK'}")
            if over or dh > 0.6 or dcy > 0.6:
                bad += 1
            all_rows.append(row)
            log(row)
        log("")

    # 关掉自动折行做对照
    log("--- 对照：关闭自动折行（强制单行等比）---")
    o2 = core.Options(**opt.to_dict())
    o2.fit_mode = "plain"
    for name in ["慕容雪见·兰", "中国国际航空股份有限公司"]:
        b1 = core.fit_block(fam, True, name, bw, bh, allow_wrap=True, pitch=opt.line_pitch)
        b2 = core.fit_block(fam, True, name, bw, bh, allow_wrap=False, pitch=opt.line_pitch)
        log(f"  「{name}」折行 {b1.count}行/{b1.em_mm:.2f}mm/sdf  vs 单行 {b2.em_mm:.2f}mm"
            .replace("/sdf", "")
            + f"  → 放大 {b1.em_mm / b2.em_mm:.2f} 倍，"
              f"高度占用 {b1.height_mm / bh * 100:.0f}% vs {b2.height_mm / bh * 100:.0f}%")

    log("")
    log(f"检查结果：{'全部通过' if bad == 0 else str(bad) + ' 项异常'}")

    with open(os.path.join(OUT, "_wrap_log.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(LOG))

    # 出一张对比图：上=折行铺满，下=强制单行
    make_view(fam, opt)
    return 0


def make_view(fam, opt):
    """拼一张"折行 vs 单行"对比图，方便肉眼确认。"""
    names = ["慕容雪见·兰", "欧阳明月月月娜娜", "中国国际航空股份有限公司"]
    rows = []
    for mode, label in (("wrap", "自动折行铺满"), ("plain", "强制单行（等比，字小）")):
        o = core.Options(**opt.to_dict())
        o.fit_mode = mode
        o.marks = "none"
        img = render(names, o)
        rows.append((label, img))

    gap = 26
    W = rows[0][1].width() + 40
    H = sum(im.height() for _, im in rows) + gap * 3
    board = QImage(W, H, QImage.Format.Format_RGB32)
    board.fill(QColor("#dfe3ea"))
    p = QPainter(board)
    from PySide6.QtGui import QFont, QPen
    p.setPen(QPen(QColor("#111827")))
    y = gap
    for label, im in rows:
        p.setFont(QFont(fam, 22, QFont.Weight.Bold))
        p.drawText(20, y - 6, label)
        p.drawImage(20, y, im)
        y += im.height() + gap
    p.end()
    board.scaledToWidth(560).save(os.path.join(OUT, "_wrap_对比图.png"))


if __name__ == "__main__":
    sys.exit(main())
