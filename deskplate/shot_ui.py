# -*- coding: utf-8 -*-
"""截一张界面图（真实渲染，含字体），用于展示字形拉伸滑块。

跑法：  python shot_ui.py [输出png]
"""
import os
import sys
import tempfile

os.environ["APPDATA"] = tempfile.mkdtemp(prefix="deskplate_shot_")

from PySide6.QtCore import QTimer                      # noqa: E402
from PySide6.QtGui import QFont, QFontDatabase         # noqa: E402
from PySide6.QtWidgets import QApplication             # noqa: E402

import app as A                                        # noqa: E402

OUT = (sys.argv[1] if len(sys.argv) > 1
       else os.path.join(os.path.dirname(os.path.abspath(__file__)), "_界面截图.png"))


def main():
    q = QApplication(sys.argv)
    fams = set(QFontDatabase.families())
    for cand in ["微软雅黑", "Microsoft YaHei", "等线", "黑体", "SimHei"]:
        if cand in fams:
            q.setFont(QFont(cand, 9))
            break
    q.setStyleSheet(A.QSS)

    w = A.MainWindow()
    w.resize(1240, 860)
    w.names_edit.setPlainText(
        "张三\n李四\n王五|销售总监\n慕容雪见·兰|编制质控单位|专家组长")
    w.show()
    q.processEvents()

    w.sl_x.setValue(140)      # 1.40×
    w.sl_y.setValue(90)       # 0.90×
    w.refresh()
    q.processEvents()
    q.processEvents()

    def shoot():
        img = w.grab()
        img.save(OUT)
        with open(os.path.join(os.path.dirname(os.path.abspath(OUT)) if OUT.startswith("/")
                               else os.path.dirname(os.path.abspath(__file__)),
                               "_shot_ui.txt"), "w", encoding="utf-8") as fh:
            fh.write(f"{OUT}\n{img.width()}x{img.height()}\n"
                     f"滑块 {w.sl_x.value()}/{w.sl_y.value()}\n"
                     f"提示 {w.stretch_tip.text()}\n"
                     f"顶栏 {w.info_label.text()}\n")
        q.quit()

    QTimer.singleShot(900, shoot)
    return q.exec()


if __name__ == "__main__":
    sys.exit(main())
