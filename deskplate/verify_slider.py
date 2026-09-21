# -*- coding: utf-8 -*-
"""手动「字形拉伸」滑块自检。

要回答三件事：
  ① 1.00×/1.00× 时，排版结果必须和加滑块之前**逐毫米一致**（不许回归）；
  ② 滑块推到量程两端（0.40 ~ 2.50）时，字**永远不溢出台签可用方框**；
  ③ 拉伸方向符合直觉：横向拉 → 更宽更扁，纵向拉 → 更高更瘦。

跑法：  python verify_slider.py
输出：  _slider_log.txt  +  _slider_矩阵.png
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
BAD = []


def log(*a):
    LOG.append(" ".join(str(x) for x in a))


def bad(msg):
    BAD.append(msg)
    log("    ✗ " + msg)


def ink_bbox(img, x0, y0, x1, y1, thr=200):
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


# ----------------------------------------------------------- ① 全量程几何扫描

def scan_geometry(fam, bw, bh):
    """在所有 (fit_mode × 文本 × 滑块组合) 上检查"不溢出"。"""
    log("=== ① 全量程几何扫描（只算不画，覆盖滑块每一档）===")
    texts = ["张三", "赵正义", "张小三四五六七八九",
             "慕容雪见·兰", "王五|销售总监",
             "慕容雪见·兰|编制质控单位|专家组长",
             "中国国际航空股份有限公司|飞行部"]
    grid = []
    v = 0.40
    while v <= 2.501:
        grid.append(round(v, 2))
        v += 0.05
    log(f"  滑块取值 {grid[0]:.2f} ~ {grid[-1]:.2f}，共 {len(grid)} 档，"
        f"两轴组合 {len(grid) * len(grid)} 组 × {len(texts)} 条文本 × 3 种填充方式")
    worst_w = worst_h = 0.0
    n_case = 0
    for mode in ("stretch", "wrap", "plain"):
        for t in texts:
            for ux in grid:
                for uy in grid:
                    o = core.Options(font_family=fam, fit_mode=mode,
                                     stretch_x=ux, stretch_y=uy)
                    pt = core.layout_plate_text(fam, True, t, bw, bh, o)
                    n_case += 1
                    if pt.rows:
                        n = len(pt.rows)
                        slot = bh / n
                        cap_h = slot * core.STRETCH_ROW_FILL
                        for r in pt.rows:
                            if r.width_mm > bw + 0.02:
                                bad(f"[{mode}] {t} x{ux:.2f}/y{uy:.2f} "
                                    f"宽 {r.width_mm:.2f} > 可用 {bw:.2f}")
                                return
                            if r.height_mm > cap_h + 0.02:
                                bad(f"[{mode}] {t} x{ux:.2f}/y{uy:.2f} "
                                    f"高 {r.height_mm:.2f} > 行槽 {cap_h:.2f}")
                                return
                            top = r.cy_mm - r.height_mm / 2.0
                            bot = r.cy_mm + r.height_mm / 2.0
                            if top < -0.02 or bot > bh + 0.02:
                                bad(f"[{mode}] {t} x{ux:.2f}/y{uy:.2f} "
                                    f"越出行槽 [{top:.2f},{bot:.2f}]")
                                return
                            worst_w = max(worst_w, r.width_mm / bw)
                            worst_h = max(worst_h, r.height_mm / cap_h)
                    else:
                        for b in (pt.main, pt.subs):
                            if not b.lines:
                                continue
                            if b.width_mm > bw + 0.02:
                                bad(f"[{mode}] {t} x{ux:.2f}/y{uy:.2f} "
                                    f"宽 {b.width_mm:.2f} > 可用 {bw:.2f}")
                                return
                            if b.height_mm > bh + 0.02:
                                bad(f"[{mode}] {t} x{ux:.2f}/y{uy:.2f} "
                                    f"高 {b.height_mm:.2f} > 可用 {bh:.2f}")
                                return
                            worst_w = max(worst_w, b.width_mm / bw)
                            worst_h = max(worst_h, b.height_mm / bh)
    log(f"  共检查 {n_case} 组：全部不溢出；"
        f"最宽占可用宽 {worst_w * 100:.2f}%，最高占可用高 {worst_h * 100:.2f}%")
    log("")


# ----------------------------------------------------------- ② 无回归

def check_no_regression(fam, bw, bh):
    """1.00×/1.00× 必须和"没有滑块"时一模一样。"""
    log("=== ② 无回归：滑块归 1.00× 时与旧逻辑逐毫米一致 ===")
    texts = ["张三", "赵正义", "张小三四五六七八九", "慕容雪见·兰",
             "王五|销售总监", "慕容雪见·兰|编制质控单位|专家组长"]
    for mode in ("stretch", "wrap", "plain"):
        for t in texts:
            o_old = core.Options(font_family=fam, fit_mode=mode)
            o_new = core.Options(font_family=fam, fit_mode=mode,
                                 stretch_x=1.0, stretch_y=1.0)
            a = core.layout_plate_text(fam, True, t, bw, bh, o_old)
            b = core.layout_plate_text(fam, True, t, bw, bh, o_new)
            if a.rows:
                sa = [(r.text, round(r.em_mm, 6), round(r.sx, 6),
                       round(r.sy, 6), round(r.width_mm, 6), round(r.height_mm, 6))
                      for r in a.rows]
                sb = [(r.text, round(r.em_mm, 6), round(r.sx, 6),
                       round(r.sy, 6), round(r.width_mm, 6), round(r.height_mm, 6))
                      for r in b.rows]
                if sa != sb:
                    bad(f"[{mode}] 「{t}」拉伸模式结果不一致")
                elif sa:
                    w = max(r[4] for r in sa)
                    log(f"  [{mode:7s}] 「{t}」{len(sa)} 行，"
                        f"宽 {w:.2f}/{bw:.0f}mm（{w / bw * 100:.0f}%），"
                        f"字面高 {max(r[1] for r in sa):.2f}mm  一致 ✓")
            else:
                for tag, ba, bb in (("主", a.main, b.main), ("副", a.subs, b.subs)):
                    if (round(ba.em_mm, 6), round(ba.width_mm, 6),
                            round(ba.height_mm, 6)) != \
                       (round(bb.em_mm, 6), round(bb.width_mm, 6),
                            round(bb.height_mm, 6)):
                        bad(f"[{mode}] 「{t}」{tag}标题结果不一致")
                if a.main.lines:
                    log(f"  [{mode:7s}] 「{t}」{a.main.count} 行，"
                        f"字面高 {a.main.em_mm:.2f}mm，"
                        f"铺满 {a.main.width_mm / bw * 100:.0f}%×"
                        f"{a.height_mm / bh * 100:.0f}%  一致 ✓")
            # 纵向缩放必须恒为 1（1.00× 时不许有任何纵向变形）
            for r in b.rows:
                if abs(r.sy - 1.0) > 1e-9:
                    bad(f"[{mode}] 「{t}」1.00× 时 sy={r.sy}")
            for blk in (b.main, b.subs):
                if blk.lines and (abs(blk.sx - 1.0) > 1e-9
                                  or abs(blk.sy - 1.0) > 1e-9):
                    bad(f"[{mode}] 「{t}」1.00× 时 sx/sy={blk.sx}/{blk.sy}")
    log("")


# ----------------------------------------------------------- ③ 方向是否符合直觉

def check_direction(fam, bw, bh):
    log("=== ③ 方向检查：横向拉 → 更扁更宽；纵向拉 → 更瘦更高 ===")
    for t in ["张三", "张小三四五六七八九", "慕容雪见·兰"]:
        base = core.layout_plate_text(
            fam, True, t, bw, bh, core.Options(font_family=fam))
        r0 = base.rows[0]
        log(f"  「{t}」基准（1.00×）：字面高 {r0.em_mm:.2f}mm "
            f"横向 ×{r0.sx:.2f}  墨迹 {r0.width_mm:.1f}×{r0.height_mm:.1f}mm")
        for tag, ux, uy in (("横向 0.60×", 0.60, 1.00), ("横向 1.60×", 1.60, 1.00),
                            ("纵向 0.60×", 1.00, 0.60), ("纵向 1.60×", 1.00, 1.60)):
            o = core.Options(font_family=fam, stretch_x=ux, stretch_y=uy)
            pt = core.layout_plate_text(fam, True, t, bw, bh, o)
            r = pt.rows[0]
            log(f"      {tag}：字面高 {r.em_mm:5.2f}mm 横向×{r.sx:4.2f} "
                f"纵向×{r.sy:4.2f}  墨迹 {r.width_mm:6.2f}×{r.height_mm:5.2f}mm"
                f"  宽高比 {r.width_mm / max(r.height_mm, 1e-6):5.2f}")
        # 断言方向
        a = core.layout_plate_text(fam, True, t, bw, bh,
                                   core.Options(font_family=fam, stretch_x=1.6))
        b = core.layout_plate_text(fam, True, t, bw, bh,
                                   core.Options(font_family=fam, stretch_x=0.6))
        if not (a.rows[0].width_mm / a.rows[0].height_mm
                > b.rows[0].width_mm / b.rows[0].height_mm):
            bad(f"「{t}」横向滑块方向不对")
        a = core.layout_plate_text(fam, True, t, bw, bh,
                                   core.Options(font_family=fam, stretch_y=1.6))
        b = core.layout_plate_text(fam, True, t, bw, bh,
                                   core.Options(font_family=fam, stretch_y=0.6))
        if not (a.rows[0].width_mm / a.rows[0].height_mm
                < b.rows[0].width_mm / b.rows[0].height_mm):
            bad(f"「{t}」纵向滑块方向不对")
    log("")


# ----------------------------------------------------------- ④ 渲染实测

def check_render(fam, bw, bh):
    """离屏渲染 → 逐像素扫墨迹框，验证"算出来的"和"画出来的"一致且不越界。"""
    log("=== ④ 渲染实测：逐像素扫墨迹框 ===")
    cases = [
        ("张三", 1.00, 1.00), ("张三", 1.60, 1.00), ("张三", 0.60, 1.00),
        ("张三", 1.00, 1.60), ("张三", 1.00, 0.60),
        ("张小三四五六七八九", 1.00, 1.00), ("张小三四五六七八九", 2.00, 0.60),
        ("张小三四五六七八九", 0.50, 1.80),
        ("慕容雪见·兰|编制质控单位|专家组长", 1.00, 1.00),
        ("慕容雪见·兰|编制质控单位|专家组长", 1.50, 1.20),
        ("慕容雪见·兰|编制质控单位|专家组长", 0.70, 0.70),
    ]
    opt = core.Options(font_family=fam)
    pad = min(opt.padding_mm, opt.plate_w / 4.0, opt.plate_h / 4.0)
    pos = core.layout_positions(PAGE_W, PAGE_H, opt, 1, 3)
    for start in range(0, len(cases), 3):
        batch = cases[start:start + 3]
        imgs = {}
        for gi, (t, ux, uy) in enumerate(batch):
            o = core.Options(**opt.to_dict())
            o.stretch_x, o.stretch_y = ux, uy
            o.marks = "none"
            imgs[gi] = render([t] * 3, o)
        for gi, (t, ux, uy) in enumerate(batch):
            o = core.Options(**opt.to_dict())
            o.stretch_x, o.stretch_y = ux, uy
            o.marks = "none"
            pt = core.layout_plate_text(fam, True, t, bw, bh, o)
            img = imgs[gi]
            px, py = pos[0]
            bx0, by0 = (px + pad) * K, (py + pad) * K
            bb = ink_bbox(img, bx0 - 3, by0 - 3,
                          bx0 + bw * K + 3, by0 + bh * K + 3)
            if bb is None:
                bad(f"「{t}」x{ux}/y{uy} 没画出墨迹")
                continue
            ix0, iy0, ix1, iy1 = bb[0] / K, bb[1] / K, bb[2] / K, bb[3] / K
            w_mm, h_mm = ix1 - ix0, iy1 - iy0
            exp_w = max(r.width_mm for r in pt.rows)
            # 多行时整块墨迹高 = 最顶行顶 → 最底行底（不是单行高）
            y_top = min(r.cy_mm - r.height_mm / 2.0 for r in pt.rows)
            y_bot = max(r.cy_mm + r.height_mm / 2.0 for r in pt.rows)
            exp_h = y_bot - y_top
            dcx = abs((ix0 + ix1) / 2.0 - (px + opt.plate_w / 2.0))
            over = (ix0 < px + pad - 0.3 or ix1 > px + pad + bw + 0.3
                    or iy0 < py + pad - 0.3 or iy1 > py + pad + bh + 0.3)
            dw, dh = w_mm - exp_w, h_mm - exp_h
            flag = "OK"
            if over:
                flag = "✗ 越出可用方框"
                bad(f"「{t}」x{ux:.2f}/y{uy:.2f} 墨迹越界")
            elif abs(dw) > 0.6 or abs(dh) > 0.6:
                flag = f"✗ 与计算值不符 Δ{dw:+.2f}/{dh:+.2f}"
                bad(f"「{t}」x{ux:.2f}/y{uy:.2f} 实测与计算不符")
            elif dcx > 0.4:
                flag = "✗ 未居中"
                bad(f"「{t}」x{ux:.2f}/y{uy:.2f} 未居中")
            log(f"  「{t}」x{ux:.2f}/y{uy:.2f}："
                f"计算 {exp_w:6.2f}×{exp_h:5.2f}mm  实测 {w_mm:6.2f}×{h_mm:5.2f}mm"
                f"（Δ{dw:+.2f}/{dh:+.2f}）  居中偏差 {dcx:.2f}mm  {flag}")
    log("")


# ----------------------------------------------------------- ⑤ 出图

def make_matrix(fam, opt):
    """画一张"横向 × 纵向"的拉伸矩阵图，直观看到形变方向。"""
    vals = [0.60, 0.80, 1.00, 1.30, 1.70]
    t = "张小三四五"
    cell_w, cell_h = 300, 170
    pad = 10
    lab = 34
    W = lab + len(vals) * (cell_w + pad) + pad
    H = lab + len(vals) * (cell_h + pad) + pad
    board = QImage(W, H, QImage.Format.Format_RGB32)
    board.fill(QColor("#eef1f5"))
    p = QPainter(board)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    f = QFont(fam, 16, QFont.Weight.Bold)
    p.setFont(f)
    p.setPen(QPen(QColor("#374151")))
    for j, uy in enumerate(vals):
        p.drawText(6, lab + j * (cell_h + pad) + cell_h / 2 + 6, f"纵 {uy:.2f}×")
    for i, ux in enumerate(vals):
        p.drawText(lab + i * (cell_w + pad) + cell_w / 2 - 40, 22, f"横 {ux:.2f}×")
    for j, uy in enumerate(vals):
        for i, ux in enumerate(vals):
            o = core.Options(**opt.to_dict())
            o.stretch_x, o.stretch_y = ux, uy
            o.marks = "none"
            o.plate_w, o.plate_h = 150.0, 80.0
            o.padding_mm = 4.0
            k = (cell_w - 8) / o.plate_w
            img = QImage(int(o.plate_w * k) + 4, int(o.plate_h * k) + 4,
                         QImage.Format.Format_RGB32)
            img.fill(QColor("white"))
            q = QPainter(img)
            q.translate(2, 2)
            core.draw_plate(q, 0.0, 0.0, o, t, k, k)
            q.end()
            x = lab + i * (cell_w + pad) + pad // 2
            y = lab + j * (cell_h + pad) + pad // 2 + (cell_h - img.height()) // 2
            p.drawImage(x, y, img)
    p.end()
    board.save(os.path.join(OUT, "_slider_矩阵.png"))
    log(f"矩阵图 _slider_矩阵.png（{board.width()}×{board.height()}）已生成")


def main():
    app = QApplication(sys.argv)                       # noqa: F841
    fams = list(QFontDatabase.families())
    fam = next((f for f in core.CJK_PREFERRED if f in fams), fams[0])

    opt = core.Options(font_family=fam, plate_w=150.0, plate_h=80.0)
    pad = min(opt.padding_mm, opt.plate_w / 4.0, opt.plate_h / 4.0)
    bw, bh = opt.plate_w - 2 * pad, opt.plate_h - 2 * pad
    log(f"字体={fam}  台签 {opt.plate_w:g}×{opt.plate_h:g}mm  "
        f"可用方框 {bw:.0f}×{bh:.0f}mm")
    log(f"滑块量程  横向 {core.STRETCH_X_RANGE}  纵向 {core.STRETCH_Y_RANGE}")
    log("")

    check_no_regression(fam, bw, bh)
    scan_geometry(fam, bw, bh)
    check_direction(fam, bw, bh)
    check_render(fam, bw, bh)
    make_matrix(fam, opt)

    log("")
    log(f"最终结果：{'全部通过 ✓' if not BAD else str(len(BAD)) + ' 项异常 ✗'}")
    for m in BAD:
        log("   - " + m)

    with open(os.path.join(OUT, "_slider_log.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(LOG))
    return 0


if __name__ == "__main__":
    sys.exit(main())
