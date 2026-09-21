# -*- coding: utf-8 -*-
"""生成几张用于肉眼确认的局部放大图。"""

import os
import sys

from PySide6.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter, QPen
from PySide6.QtWidgets import QApplication

import core

OUT = os.path.dirname(os.path.abspath(__file__))
K = 200 / 25.4


def crop(img, x0_mm, y0_mm, x1_mm, y1_mm, scale=1.0, label=""):
    r = (int(x0_mm * K), int(y0_mm * K),
         int(x1_mm * K), int(y1_mm * K))
    c = img.copy(r[0], r[1], r[2] - r[0], r[3] - r[1])
    if scale != 1.0:
        c = c.scaled(int(c.width() * scale), int(c.height() * scale))
    if label:
        pad = 26
        out = QImage(c.width(), c.height() + pad, QImage.Format.Format_RGB32)
        out.fill(QColor("#eef2f7"))
        p = QPainter(out)
        f = QFont(); f.setPixelSize(16); p.setFont(f)
        p.setPen(QColor("#1f2937"))
        p.drawText(8, 18, label)
        p.drawImage(0, pad, c)
        p.end()
        return out
    return c


def main():
    app = QApplication(sys.argv)
    fams = set(QFontDatabase.families())
    fam = next((f for f in core.CJK_PREFERRED if f in fams), "Arial")

    pw, ph = 210.0, 297.0
    names = ["张三", "李四", "欧阳明月"]

    def render(mk):
        o = core.Options(font_family=fam, plate_w=150.0, plate_h=80.0,
                         padding_mm=4.0, layout="compact", marks=mk)
        img = QImage(int(pw * K), int(ph * K), QImage.Format.Format_RGB32)
        img.fill(QColor("white"))
        p = QPainter(img)
        core.render_page(p, names, o, pw, ph, K, K)
        p.end()
        return img

    tick = render("tick")
    guide = render("guide")

    tick.scaledToWidth(520).save(os.path.join(OUT, "_mk_view_page.png"))

    # 左上角：竖切定位点（端头 x=150, y=8）
    crop(tick, 128, 0, 178, 26, 3.0,
         "定位点方案 · 竖切线顶端：短线端头正好落在 150mm 刀口上").save(
        os.path.join(OUT, "_mk_view_v.png"))

    # 中部：横切定位点（跨在 y=80 上）
    crop(tick, 146, 62, 210, 98, 2.0,
         "定位点方案 · 横切线：两个短线跨在 80mm 刀口上（右侧废料区）").save(
        os.path.join(OUT, "_mk_view_h.png"))

    crop(guide, 128, 0, 178, 26, 3.0,
         "对照 · 贯通虚线（线压在台签边缘上）").save(
        os.path.join(OUT, "_mk_view_g.png"))

    with open(os.path.join(OUT, "_mk_views.txt"), "w", encoding="utf-8") as fh:
        fh.write("ok\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
