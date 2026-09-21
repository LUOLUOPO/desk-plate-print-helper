# -*- coding: utf-8 -*-
"""GUI 冒烟测试（离屏）：确认拉伸滑块与状态/配置/预览的联动都正常。

跑法：  python smoke_gui.py
输出：  _gui_smoke.txt
"""
import os
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="deskplate_cfg_")

from PySide6.QtWidgets import QApplication          # noqa: E402
from PySide6.QtGui import QFontDatabase             # noqa: E402

import app as A                                     # noqa: E402
import core                                         # noqa: E402

OUT = []


def log(*a):
    OUT.append(" ".join(str(x) for x in a))


def main():
    q = QApplication(sys.argv)                      # noqa: F841
    w = A.MainWindow()
    log(f"字体数 = {len(QFontDatabase.families())}  打印机数 = {len(w._printer_names)}")
    log(f"滑块量程 横 {w.sl_x.minimum()}~{w.sl_x.maximum()}  "
        f"纵 {w.sl_y.minimum()}~{w.sl_y.maximum()}（100 = 1.00×）")
    log(f"初始：滑块 {w.sl_x.value()}/{w.sl_y.value()}  "
        f"按钮 {w.btn_x.text()}/{w.btn_y.text()}")
    log(f"初始提示：{w.stretch_tip.text()}")

    w.names_edit.setPlainText("张三\n李四\n慕容雪见·兰|编制质控单位|专家组长")
    ok = True

    for ux, uy, tag in ((100, 100, "不拉伸"),
                        (160, 100, "横向放大"),
                        (60, 100, "横向收窄"),
                        (100, 160, "纵向放大"),
                        (100, 60, "纵向压低"),
                        (160, 160, "横纵同步放大"),
                        (60, 60, "横纵同步收窄")):
        w.sl_x.setValue(ux)
        w.sl_y.setValue(uy)
        w.refresh()
        o = w.state.opt
        if abs(o.stretch_x - ux / 100.0) > 1e-9 or abs(o.stretch_y - uy / 100.0) > 1e-9:
            log(f"✗ 状态未同步：{o.stretch_x}/{o.stretch_y}")
            ok = False
        # 几何核对：预览用的排版结果不许溢出可用方框
        pad = min(o.padding_mm, o.plate_w / 4.0, o.plate_h / 4.0)
        bw, bh = o.plate_w - 2 * pad, o.plate_h - 2 * pad
        pt = core.layout_plate_text(o.font_family, o.bold, "慕容雪见·兰|编制质控单位|专家组长",
                                    bw, bh, o)
        wmax = max(r.width_mm for r in pt.rows)
        hmax = max(r.height_mm for r in pt.rows)
        over = wmax > bw + 0.02 or hmax > bh + 0.02
        if over:
            ok = False
        log(f"[{tag}] 滑块 {ux}/{uy} → 按钮 {w.btn_x.text()}/{w.btn_y.text()}  "
            f"opt {o.stretch_x:.2f}/{o.stretch_y:.2f}  "
            f"示例墨迹 {wmax:.2f}×{hmax:.2f}mm ≤ {bw:.0f}×{bh:.0f}mm "
            f"{'✗ 溢出' if over else 'OK'}")
        log(f"     提示：{w.stretch_tip.text()}")
        log(f"     顶栏：{w.info_label.text()}")

    w.preview.grab()
    log(f"预览渲染 OK，控件尺寸 {w.preview.width()}×{w.preview.height()}")

    # 点数字按钮复位
    w.btn_x.click()
    w.refresh()
    log(f"点「{w.btn_x.text()}」复位后：滑块 {w.sl_x.value()}  "
        f"opt.stretch_x = {w.state.opt.stretch_x:.2f}  "
        f"{'OK' if w.sl_x.value() == 100 else '✗'}")

    # 配置往返
    w.sl_x.setValue(135)
    w.sl_y.setValue(75)
    w.refresh()
    d = w.state.opt.to_dict()
    log(f"存盘字典含 stretch_x/y = {d.get('stretch_x')}/{d.get('stretch_y')}")
    w.sl_x.setValue(100)
    w.sl_y.setValue(100)
    w._apply_config(d)
    log(f"读回配置后 滑块 {w.sl_x.value()}/{w.sl_y.value()}  "
        f"{'OK' if (w.sl_x.value(), w.sl_y.value()) == (135, 75) else '✗'}")

    # 旧配置（没有 stretch 字段）必须回落成 1.00×
    old = {"font_family": "微软雅黑", "fit_mode": "stretch", "layout": "compact"}
    w._apply_config(old)
    log(f"旧配置读入后 滑块 {w.sl_x.value()}/{w.sl_y.value()}  "
        f"{'OK' if (w.sl_x.value(), w.sl_y.value()) == (100, 100) else '✗'}")

    # 极端值：夹到量程
    w._apply_config({"stretch_x": 9.9, "stretch_y": 0.01})
    log(f"越界配置 9.9/0.01 → 滑块 {w.sl_x.value()}/{w.sl_y.value()}  "
        f"{'OK' if (w.sl_x.value(), w.sl_y.value()) == (w.sl_x.maximum(), w.sl_x.minimum()) else '✗'}")

    log("")
    log(f"冒烟测试：{'全部通过 ✓' if ok else '有异常 ✗'}")
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "_gui_smoke.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
