# -*- coding: utf-8 -*-
"""把自检图裁成便于查看的小图。"""
import os
import sys

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QImage, QPainter, QColor
from PySide6.QtWidgets import QApplication

D = os.path.dirname(os.path.abspath(__file__))
app = QApplication(sys.argv)

K = 200 / 25.4          # 与 test_render 一致
PAD = 3.0               # 裁切时多留一点边


def mm_rect(x0, y0, x1, y1):
    return QRect(int(x0 * K), int(y0 * K), int((x1 - x0) * K), int((y1 - y0) * K))


def crop(src, dst, rect, out_w):
    img = QImage(os.path.join(D, src))
    if img.isNull():
        print("miss", src)
        return
    c = img.copy(rect)
    c = c.scaledToWidth(out_w, Qt.TransformationMode.SmoothTransformation)
    c.save(os.path.join(D, dst))
    print("ok", dst, c.width(), c.height())


def shrink(src, dst, out_w=620):
    img = QImage(os.path.join(D, src))
    if img.isNull():
        print("miss", src)
        return
    c = img.scaledToWidth(out_w, Qt.TransformationMode.SmoothTransformation)
    c.save(os.path.join(D, dst))
    print("ok", dst, c.width(), c.height())


# 整页缩略
shrink("_test_2字.png", "_view_整页.png", 560)

# 第一张台签放大：台签 (30,23.5)-(180,103.5)
p1 = mm_rect(30 - PAD, 23.5 - PAD, 180 + PAD, 103.5 + PAD)
for name in ["2字", "3字", "6字", "9字", "副标题", "全名排满"]:
    crop(f"_test_{name}.png", f"_view_{name}.png", p1, 1100)

for fam in ["黑体", "宋体", "楷体", "微软雅黑"]:
    fn = f"_test_字体_{fam}.png"
    if os.path.exists(os.path.join(D, fn)):
        crop(fn, f"_view_字体_{fam}.png", p1, 1000)

crop("_test_黑底白字.png", "_view_黑底白字.png", p1, 1000)

# 拼接对比图：三个不同字数的台签竖排
names = ["2字", "3字", "6字", "全名排满"]
crops = []
for n in names:
    im = QImage(os.path.join(D, f"_view_{n}.png"))
    if not im.isNull():
        crops.append(im)
if crops:
    w = max(c.width() for c in crops)
    h = sum(c.height() for c in crops) + 8 * (len(crops) - 1)
    out = QImage(w, h, QImage.Format.Format_RGB32)
    out.fill(QColor("#888888"))
    p = QPainter(out)
    y = 0
    for c in crops:
        p.drawImage(0, y, c)
        y += c.height() + 8
    p.end()
    out.save(os.path.join(D, "_view_字数对比.png"))
    print("ok _view_字数对比.png", w, h)
