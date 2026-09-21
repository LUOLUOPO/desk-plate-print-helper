# -*- coding: utf-8 -*-
"""离屏渲染自检：把 A4 版面渲染成 PNG / PDF，并量出文字实际墨迹范围。

用途：无法弹窗口的环境下验证排版与字号自适应是否正确。
运行：python test_render.py
"""
import os
import sys

# 默认使用系统平台插件（这样才能枚举并渲染 Windows 已安装字体）；
# 只有在显式指定时才切换到 offscreen。
_pf = os.environ.get("DESKPLATE_TEST_PLATFORM")
if _pf:
    os.environ["QT_QPA_PLATFORM"] = _pf

from PySide6.QtCore import QMarginsF, QRectF, Qt                     # noqa: E402
from PySide6.QtGui import (QColor, QFontDatabase, QImage, QPageLayout,  # noqa: E402
                           QPageSize, QPainter, QPdfWriter)
from PySide6.QtWidgets import QApplication                            # noqa: E402

import core                                                           # noqa: E402

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG = []


def log(*a):
    s = " ".join(str(x) for x in a)
    LOG.append(s)
    print(s)


def pick_font() -> str:
    fams = set(QFontDatabase.families())
    for c in core.CJK_PREFERRED:
        if c in fams:
            return c
    return QFontDatabase.families()[0] if fams else "Arial"


def render_png(path, names, opt, dpi=200, paper=(210.0, 297.0)):
    pw, ph = paper
    k = dpi / 25.4
    img = QImage(int(round(pw * k)), int(round(ph * k)), QImage.Format.Format_RGB32)
    img.setDotsPerMeterX(int(dpi / 0.0254))
    img.setDotsPerMeterY(int(dpi / 0.0254))
    img.fill(QColor("white"))
    p = QPainter(img)
    core.render_page(p, names, opt, pw, ph, k, k)
    p.end()
    img.save(path)
    return img, k


def render_pdf(path, names, opt, paper=(210.0, 297.0)):
    pw, ph = paper
    writer = QPdfWriter(path)
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Unit.Millimeter)
    writer.setResolution(300)
    k = 300 / 25.4
    p = QPainter(writer)
    core.render_page(p, names, opt, pw, ph, k, k)
    p.end()


def ink_bbox_mm(img: QImage, k, region_mm):
    """在指定 mm 区域内扫描非白像素，返回墨迹范围(mm) 以及占区域的比例。"""
    x0m, y0m, x1m, y1m = region_mm
    X0, Y0 = int(x0m * k), int(y0m * k)
    X1, Y1 = int(x1m * k), int(y1m * k)
    X0, Y0 = max(0, X0), max(0, Y0)
    X1, Y1 = min(img.width(), X1), min(img.height(), Y1)
    w = X1 - X0
    bx0, by0, bx1, by1 = 10 ** 9, 10 ** 9, -1, -1
    for y in range(Y0, Y1):
        b = bytes(img.constScanLine(y))[: img.width() * 4]
        for x in range(X0, X1):
            i = x * 4
            if b[i] < 190 or b[i + 1] < 190 or b[i + 2] < 190:
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
    r = (bx0 / k, by0 / k, bx1 / k, by1 / k)
    fill_w = (r[2] - r[0]) / (x1m - x0m) * 100
    fill_h = (r[3] - r[1]) / (y1m - y0m) * 100
    return r, fill_w, fill_h


def main():
    app = QApplication(sys.argv)
    fams = QFontDatabase.families()
    log("字体总数 =", len(fams))
    fab = pick_font()
    log("使用字体 =", fab)

    # 0) 字体度量比例自检
    from PySide6.QtGui import QFont, QFontMetricsF
    for px in (100, 400):
        f = QFont(fab); f.setPixelSize(px)
        fm = QFontMetricsF(f)
        t = fm.tightBoundingRect("张三")
        b = fm.boundingRect("张三")
        log(f"  pixelSize{px}: 墨迹框 {t.width():.1f}x{t.height():.1f} "
            f"({t.width()/px:.3f},{t.height()/px:.3f} em) | "
            f"行高框 {b.width():.1f}x{b.height():.1f} ({b.height()/px:.3f} em)")

    # 1) 版面计算
    cols, rows = core.grid_count(210, 297, 150, 80, 5, 6)
    log("150x80 在 A4 上 ->", cols, "列 x", rows, "行")

    base = core.Options(font_family=fab, plate_w=150.0, plate_h=80.0,
                        padding_mm=4.0, gap_mm=5.0, margin_mm=6.0,
                        bold=True, marks="corner")
    pos = core.grid_positions(210, 297, 150.0, 80.0, cols, rows, 5.0)
    log("台签左上角(mm) =", [f"({x:.1f},{y:.1f})" for x, y in pos])

    cases = [
        ("2字", ["张三", "李四", "王五"]),
        ("3字", ["张小三", "李四", "王五"]),
        ("6字", ["欧阳明月月月", "张三", "李四"]),
        ("9字", ["欧阳明月月月月月月", "张三", "李四"]),
        ("副标题", ["张三|销售总监", "李四|技术负责人", "王五|财务"]),
        ("全名排满", ["中国国际航空股份有限公司", "张三", "李四"]),
    ]
    for label, names in cases:
        opt = core.Options(**base.to_dict())
        img, k = render_png(os.path.join(OUT_DIR, f"_test_{label}.png"), names, opt, dpi=200)
        x, y = pos[0]
        pad = opt.padding_mm
        res = ink_bbox_mm(img, k, (x, y, x + 150.0, y + 80.0))
        if res:
            r, fw, fh = res
            log(f"[{label}] 第1张台签文字墨迹(mm) = "
                f"({r[0]:.1f},{r[1]:.1f})-({r[2]:.1f},{r[3]:.1f})  "
                f"宽{r[2]-r[0]:.1f}/142 高{r[3]-r[1]:.1f}/72  "
                f"填充率 {fw:.0f}% × {fh:.0f}%  "
                f"中心偏移 x={( (r[0]+r[2])/2 - (x+75) ):.2f} y={((r[1]+r[3])/2 - (y+40)):.2f}")

    # 2) 黑底白字
    opt3 = core.Options(**base.to_dict())
    opt3.invert = True
    render_png(os.path.join(OUT_DIR, "_test_黑底白字.png"), ["张三", "李四", "王五"], opt3, dpi=200)

    # 3) 整页效果：不同字体
    for fam in [f for f in ["黑体", "宋体", "楷体", "微软雅黑", "Arial"] if f in fams][:5]:
        o = core.Options(**base.to_dict())
        o.font_family = fam
        render_png(os.path.join(OUT_DIR, f"_test_字体_{fam}.png"),
                   ["张三|销售总监", "李四|技术负责人", "王五|财务"], o, dpi=200)

    # 4) PDF
    render_pdf(os.path.join(OUT_DIR, "_test_预览.pdf"), ["张三", "李四", "王五"], base)

    # 5) 字号自检
    log("--- 自动字号(mm 字面高 / 墨迹高) ---")
    pad = base.padding_mm
    bw = base.plate_w - 2 * pad
    bh = base.plate_h - 2 * pad
    for t in ["张三", "张小三", "张小三四", "张小三四五", "张小三四五六",
              "张小三四五六七", "张小三四五六七八九"]:
        em = core.fit_em_mm(fab, True, t, bw, bh)
        rw, rh = core.font_ratios(fab, True, t)
        log(f"  「{t}」({len(t)}字) 字面 {em:.2f}mm ≈{core.em_mm_to_pt(em):.0f}pt "
            f"-> 墨迹 {em*rw:.1f}×{em*rh:.1f} mm")

    with open(os.path.join(OUT_DIR, "_test_log.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(LOG))
    return 0


if __name__ == "__main__":
    sys.exit(main())
