# -*- coding: utf-8 -*-
"""生成「字形拉伸」示例图：3×3 矩阵，直观看到两个滑块各自的效果。

跑法：  python mkview_slider.py [输出目录]
输出：  示例-字形拉伸.png
"""
import os
import sys

from PySide6.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter, QPen
from PySide6.QtWidgets import QApplication

import core

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
TEXT = "欧阳明月"
XS = [0.70, 1.00, 1.50]
YS = [0.70, 1.00, 1.50]


def main():
    QApplication(sys.argv)                             # noqa: F841
    fams = list(QFontDatabase.families())
    fam = next((f for f in core.CJK_PREFERRED if f in fams), fams[0])

    opt0 = core.Options(font_family=fam, plate_w=150.0, plate_h=80.0,
                        marks="none", padding_mm=4.0)
    cell_w, cell_h = 352, 236
    report = []
    pad = 14
    lab_x, lab_y = 100, 30
    head = 100
    W = lab_x + len(XS) * (cell_w + pad) + pad
    H = head + lab_y + len(YS) * (cell_h + pad) + pad
    board = QImage(W, H, QImage.Format.Format_RGB32)
    board.fill(QColor("#f3f5f9"))
    p = QPainter(board)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

    f_title = QFont(fam, 21, QFont.Weight.Bold)
    f_sub = QFont(fam, 11)
    f_lab = QFont(fam, 14, QFont.Weight.Bold)
    f_tag = QFont(fam, 10)

    p.setFont(f_title)
    p.setPen(QPen(QColor("#111827")))
    p.drawText(pad + lab_x - 60, 38, "字形拉伸滑块效果（台签 150×80mm，文字「%s」）" % TEXT)
    p.setFont(f_sub)
    p.setPen(QPen(QColor("#6b7280")))
    p.drawText(pad + lab_x - 60, 62,
               "两轴都是 1.00× 时按最大铺满（正中蓝框那格）；只有单独拉一个方向，字形才会明显变化。")

    for i, ux in enumerate(XS):
        cx = lab_x + i * (cell_w + pad) + cell_w / 2
        p.setFont(f_lab)
        p.setPen(QPen(QColor("#1f2937")))
        p.drawText(int(cx - 60), head - 12, f"横向 {ux:.2f}×")
    for j, uy in enumerate(YS):
        cy = head + lab_y + j * (cell_h + pad) + cell_h / 2
        p.setFont(f_lab)
        p.setPen(QPen(QColor("#1f2937")))
        p.drawText(12, int(cy - 4), "纵向")
        p.drawText(12, int(cy + 20), f"{uy:.2f}×")

    for j, uy in enumerate(YS):
        for i, ux in enumerate(XS):
            o = core.Options(**opt0.to_dict())
            o.stretch_x, o.stretch_y = ux, uy
            k = (cell_w - 16) / o.plate_w
            tw, th = int(o.plate_w * k) + 2, int(o.plate_h * k) + 2
            img = QImage(tw, th, QImage.Format.Format_RGB32)
            img.fill(QColor("white"))
            q = QPainter(img)
            q.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            q.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
            q.translate(1, 1)
            core.draw_plate(q, 0.0, 0.0, o, TEXT, k, k)
            q.end()
            # 量一下墨迹到台签四边的最小距离，确认没被裁掉（应 ≈ 留白 4mm×k）
            gap = 1e9
            for gy in range(img.height()):
                line = bytes(img.constScanLine(gy))
                for gx in range(img.width()):
                    if line[gx * 4] < 200:
                        gap = min(gap, gx - 1, gy - 1,
                                  img.width() - 2 - gx, img.height() - 2 - gy)
            report.append(f"纵向{uy:.2f}× 横向{ux:.2f}× → 墨迹距台签边缘 "
                          f"{gap / k:.2f}mm（留白设定 {o.padding_mm:g}mm）")

            x = int(lab_x + i * (cell_w + pad) + (cell_w - tw) / 2)
            y = int(head + lab_y + j * (cell_h + pad) + (cell_h - th) / 2)
            p.drawImage(x, y, img)
            # 台签边框：默认那格用蓝色高亮
            default = abs(ux - 1.0) < 1e-9 and abs(uy - 1.0) < 1e-9
            p.setBrush(QColor(0, 0, 0, 0))
            p.setPen(QPen(QColor("#2563eb") if default else QColor("#c8cfda"),
                          2.5 if default else 1.0))
            p.drawRect(x, y, tw, th)
            if default:
                p.setFont(f_tag)
                p.setPen(QPen(QColor("#2563eb")))
                p.drawText(x + tw - 74, y - 6, "默认")
    p.end()

    path = os.path.join(OUT, "示例-字形拉伸.png")
    board.save(path)
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "_mkview_slider.txt"), "w", encoding="utf-8") as fh:
        fh.write(f"{path}\n{board.width()}x{board.height()}\n字体={fam}\n")
        fh.write("\n".join(report) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
