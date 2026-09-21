# -*- coding: utf-8 -*-
"""生成应用图标 app.ico（多尺寸）。"""
import os
import sys

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QFont, QFontDatabase, QImage,
                           QLinearGradient, QPainter, QPen)
from PySide6.QtWidgets import QApplication

D = os.path.dirname(os.path.abspath(__file__))
app = QApplication(sys.argv)


def pick_font():
    fams = set(QFontDatabase.families())
    for c in ["微软雅黑", "Microsoft YaHei", "等线", "黑体", "SimHei"]:
        if c in fams:
            return c
    return "Arial"


FAM = pick_font()
SIZE = 256
img = QImage(SIZE, SIZE, QImage.Format.Format_ARGB32)
img.fill(Qt.GlobalColor.transparent)
p = QPainter(img)
p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

# 圆角背景
g = QLinearGradient(0, 0, 0, SIZE)
g.setColorAt(0.0, QColor("#3b82f6"))
g.setColorAt(1.0, QColor("#1d4ed8"))
p.setPen(Qt.PenStyle.NoPen)
p.setBrush(QBrush(g))
p.drawRoundedRect(QRectF(8, 8, SIZE - 16, SIZE - 16), 46, 46)

# 白色台签卡片（15:8）
cw, ch = 176, 94
cx, cy = (SIZE - cw) / 2, (SIZE - ch) / 2
p.setBrush(QColor(255, 255, 255))
p.setPen(Qt.PenStyle.NoPen)
p.drawRoundedRect(QRectF(cx, cy, cw, ch), 10, 10)

# 台签上的"台"字
f = QFont(FAM)
f.setBold(True)
f.setPixelSize(int(ch * 0.78))
p.setFont(f)
p.setPen(QPen(QColor("#1d4ed8")))
p.drawText(QRectF(cx, cy, cw, ch), Qt.AlignmentFlag.AlignCenter, "台")

# 四角裁切角标（画在卡片外侧）
pen = QPen(QColor(255, 255, 255, 200))
pen.setWidthF(4.0)
pen.setCapStyle(Qt.PenCapStyle.FlatCap)
p.setPen(pen)
o, L = 5.0, 18.0
for mx, my in ((cx - o, cy - o), (cx + cw + o, cy - o),
               (cx - o, cy + ch + o), (cx + cw + o, cy + ch + o)):
    sx = 1 if mx < cx else -1
    sy = 1 if my < cy else -1
    p.drawLine(int(mx), int(my), int(mx + sx * L), int(my))
    p.drawLine(int(mx), int(my), int(mx), int(my + sy * L))
p.end()

out = os.path.join(D, "app.ico")
ok = img.save(out, "ICO")
print("ICO save:", ok, out)
if not ok:
    png = os.path.join(D, "app.png")
    img.save(png, "PNG")
    print("PNG fallback:", png)
