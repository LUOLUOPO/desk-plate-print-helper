# -*- coding: utf-8 -*-
"""生成交付目录里的示例图（定位点版 A4 / 切割线版 A4 / 裁好的 3 张）。

示例姓名一律用虚构姓名，公开仓库不出现真人姓名。
用法： python mkview_deliver.py <输出目录>
"""
import os
import sys

from PySide6.QtGui import QColor, QFontDatabase, QImage, QPainter
from PySide6.QtWidgets import QApplication

import core

K = 200 / 25.4
PW, PH = 210.0, 297.0
NAMES = ["张三", "李四", "欧阳明月"]


def render(marks, fam):
    o = core.Options(font_family=fam, plate_w=150.0, plate_h=80.0,
                     padding_mm=4.0, layout="compact", marks=marks)
    img = QImage(int(PW * K), int(PH * K), QImage.Format.Format_RGB32)
    img.fill(QColor("white"))
    p = QPainter(img)
    core.render_page(p, NAMES, o, PW, PH, K, K)
    p.end()
    return img


def mm(x0, y0, x1, y1):
    return (int(x0 * K), int(y0 * K), int((x1 - x0) * K), int((y1 - y0) * K))


def main():
    outdir = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    os.makedirs(outdir, exist_ok=True)
    app = QApplication(sys.argv)
    fams = set(QFontDatabase.families())
    fam = next((f for f in core.CJK_PREFERRED if f in fams), "Arial")

    tick = render("tick", fam)
    guide = render("guide", fam)

    tick.scaledToWidth(900).save(os.path.join(outdir, "示例-打印在A4上的样子.png"))
    guide.scaledToWidth(900).save(os.path.join(outdir, "示例-切割线版A4.png"))

    # 按刀口真裁一遍：竖切 x=150，横切 y=80/160/240
    pieces = []
    for i in range(3):
        y0 = i * 80.0
        r = mm(0, y0, 150, y0 + 80)
        pieces.append(tick.copy(*r))
    cuts = [c.scaledToWidth(700) for c in pieces]
    w = max(c.width() for c in cuts)
    h = sum(c.height() for c in cuts) + 12 * (len(cuts) - 1)
    board = QImage(w, h, QImage.Format.Format_RGB32)
    board.fill(QColor("#d8dde5"))
    p = QPainter(board)
    y = 0
    for c in cuts:
        p.drawImage(0, y, c)
        y += c.height() + 12
    p.end()
    board.save(os.path.join(outdir, "示例-切完的3张台签.png"))

    for n in ("示例-打印在A4上的样子.png", "示例-切割线版A4.png", "示例-切完的3张台签.png"):
        fp = os.path.join(outdir, n)
        print("ok %s  %d bytes" % (n, os.path.getsize(fp)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
