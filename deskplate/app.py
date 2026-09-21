# -*- coding: utf-8 -*-
"""台签打印助手 —— 主程序（PySide6 / Qt6）

功能：把任意字数的姓名以最大字号居中排版到 15×8cm 台签上，A4 纸一次多张，
      切割标记可选（废料区定位点 / 贯通虚线 / 角标），直接调用 Windows 打印机输出。
"""

from __future__ import annotations

import json
import os
import sys

from PySide6.QtCore import QMarginsF, QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import (QColor, QFont, QFontDatabase, QIcon, QPageLayout,
                           QPageSize, QPainter, QPen)
from PySide6.QtPrintSupport import QPrinter, QPrinterInfo, QPrintDialog
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QCompleter,
                               QDialog, QDoubleSpinBox, QFileDialog, QFrame,
                               QGridLayout, QGroupBox, QHBoxLayout, QLabel,
                               QMainWindow, QMessageBox, QPlainTextEdit,
                               QPushButton, QRadioButton, QScrollArea, QSizePolicy,
                               QSlider, QSpinBox, QSplitter, QToolButton,
                               QVBoxLayout, QWidget)

import core

APP_NAME = "台签打印助手"
ORG_NAME = "DeskPlate"

# "切割标记"下拉框的顺序 <-> core.Options.marks 取值
MARKS_ORDER = ["tick", "guide", "corner", "box", "none"]
FIT_MODES = ["stretch", "wrap", "plain"]
# 拉伸滑块右侧那个"当前倍率"按钮的样式（点一下复位到 1.00×）
STRETCH_BTN_QSS = "QToolButton{padding:2px 2px;}"

MARKS_LABEL = {
    "tick": "废料定位点",
    "guide": "定位虚线",
    "corner": "四角角标",
    "box": "整圈边框",
    "none": "不打印标记",
}


# ------------------------------------------------------------------ 配置

def config_path() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, ORG_NAME)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "config.json")


def load_config() -> dict:
    try:
        with open(config_path(), "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def save_config(d: dict) -> None:
    try:
        with open(config_path(), "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ------------------------------------------------------------------ 状态

class State:
    """界面与绘制共用的数据。"""

    def __init__(self) -> None:
        self.opt = core.Options()
        self.names: list[str] = []
        self.pages: list[list[str]] = [[]]
        self.page_idx = 0
        self.cols = 1
        self.rows = 3

    # -- 纸张
    def page_size(self) -> tuple[float, float]:
        return core.PAPER_PRESETS.get(self.opt.paper, (210.0, 297.0))

    def rebuild(self) -> None:
        pw, ph = self.page_size()
        self.cols, self.rows = core.layout_count(pw, ph, self.opt)
        per = max(1, self.cols * self.rows)
        self.pages = core.paginate(self.names, per, self.opt.repeat)
        self.page_idx = max(0, min(self.page_idx, len(self.pages) - 1))

    def cut_lines(self) -> tuple[list[float], list[float]]:
        pw, ph = self.page_size()
        return core.cut_plan(pw, ph, self.opt, self.cols, self.rows)

    def current_items(self) -> list[str]:
        if not self.pages:
            return []
        return self.pages[min(self.page_idx, len(self.pages) - 1)]


# ------------------------------------------------------------------ 预览控件

class PreviewWidget(QWidget):
    def __init__(self, state: State) -> None:
        super().__init__()
        self.state = state
        self.setMinimumSize(420, 520)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.fillRect(self.rect(), QColor("#eef1f5"))

        pw, ph = self.state.page_size()
        W, H = self.width(), self.height()
        m = 20.0
        k = min((W - 2 * m) / pw, (H - 2 * m) / ph)
        if k <= 0:
            return
        ox = (W - pw * k) / 2.0
        oy = (H - ph * k) / 2.0

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(60, 70, 90, 30))
        p.drawRect(QRectF(ox + 2.5, oy + 3.5, pw * k, ph * k))
        p.setBrush(QColor("#ffffff"))
        p.setPen(QPen(QColor("#c2c9d4"), 1))
        p.drawRect(QRectF(ox, oy, pw * k, ph * k))

        p.translate(ox, oy)
        core.render_page(p, self.state.current_items(), self.state.opt, pw, ph, k, k)


# ------------------------------------------------------------------ 主窗口

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.state = State()
        self._loading = False
        self.setWindowTitle(APP_NAME)
        self.resize(1180, 800)

        # 刷新定时器要先建好：_build_ui() 里同步控件的初始状态时就会用到
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(180)
        self._refresh_timer.timeout.connect(self.refresh)

        self._build_ui()
        self._load()

        self.refresh()

    # -------------------------------------------------- 界面搭建
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter)

        # ---------- 左侧设置
        left = QWidget()
        left.setMinimumWidth(360)
        left.setMaximumWidth(520)
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 6, 0)
        lv.setSpacing(10)

        lv.addWidget(self._group_content())
        lv.addWidget(self._group_font())
        lv.addWidget(self._group_size())
        lv.addWidget(self._group_print())
        lv.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidget(left)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(380)
        scroll.setMaximumWidth(560)
        splitter.addWidget(scroll)

        # ---------- 右侧预览
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(8)

        head = QHBoxLayout()
        title = QLabel("打印预览")
        title.setStyleSheet("font-size:15px;font-weight:600;color:#1f2937;")
        head.addWidget(title)
        head.addStretch(1)
        self.info_label = QLabel("")
        self.info_label.setStyleSheet("color:#5b6472;")
        head.addWidget(self.info_label)
        rv.addLayout(head)

        self.preview = PreviewWidget(self.state)
        rv.addWidget(self.preview, 1)

        nav = QHBoxLayout()
        self.btn_prev = QToolButton()
        self.btn_prev.setText("◀ 上一页")
        self.btn_prev.clicked.connect(lambda: self.goto_page(-1))
        self.btn_next = QToolButton()
        self.btn_next.setText("下一页 ▶")
        self.btn_next.clicked.connect(lambda: self.goto_page(1))
        self.page_label = QLabel("第 1 / 1 页")
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_label.setMinimumWidth(90)

        nav.addStretch(1)
        nav.addWidget(self.btn_prev)
        nav.addWidget(self.page_label)
        nav.addWidget(self.btn_next)
        nav.addStretch(1)
        rv.addLayout(nav)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([430, 750])

        self.statusBar().showMessage("就绪")

    # ---------- 分组：内容
    def _group_content(self) -> QGroupBox:
        g = QGroupBox("① 台签内容")
        v = QVBoxLayout(g)
        self.names_edit = QPlainTextEdit()
        self.names_edit.setPlaceholderText("一行一个名字，例如：\n张三\n李四\n王五|销售总监")
        self.names_edit.setFixedHeight(120)
        self.names_edit.textChanged.connect(self._schedule_refresh)
        v.addWidget(self.names_edit)
        tip = QLabel("一行一个名字。想再挂单位/职务，写「张三|销售总监」，竖线后每段各占一行、"
                     "各自撑满整宽（不折行）。\n"
                     "字多的名字默认也是<b>一行</b>——程序把整行横向撑满，不会拆成两行。")
        tip.setWordWrap(True)
        tip.setStyleSheet("color:#6b7280;font-size:12px;")
        v.addWidget(tip)
        return g

    # ---------- 分组：字体
    def _group_font(self) -> QGroupBox:
        g = QGroupBox("② 字体")
        v = QVBoxLayout(g)

        self.font_combo = QComboBox()
        self.font_combo.setEditable(True)
        self.font_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.font_combo.setMinimumHeight(30)
        comp = self.font_combo.completer()
        comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        comp.setFilterMode(Qt.MatchFlag.MatchContains)
        comp.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.font_combo.view().setMinimumWidth(340)
        v.addWidget(self.font_combo)

        self._fill_fonts()

        quick = QHBoxLayout()
        quick.setSpacing(6)
        self._quick_btns = []
        for name in ["微软雅黑", "黑体", "宋体", "楷体", "等线", "仿宋"]:
            b = QPushButton(name)
            b.setFixedHeight(26)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, n=name: self._pick_quick_font(n))
            quick.addWidget(b)
            self._quick_btns.append((name, b))
        quick.addStretch(1)
        v.addLayout(quick)

        row = QHBoxLayout()
        self.chk_bold = QCheckBox("加粗")
        self.chk_bold.setChecked(True)
        self.chk_bold.toggled.connect(self._schedule_refresh)
        self.chk_invert = QCheckBox("黑底白字")
        self.chk_invert.toggled.connect(self._schedule_refresh)
        row.addWidget(self.chk_bold)
        row.addWidget(self.chk_invert)
        row.addStretch(1)
        v.addLayout(row)

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        self.rb_auto = QRadioButton("自动最大字号")
        self.rb_auto.setChecked(True)
        self.rb_auto.toggled.connect(self._schedule_refresh)
        self.rb_manual = QRadioButton("指定字号")
        self.rb_manual.toggled.connect(self._schedule_refresh)
        self.sp_pt = QDoubleSpinBox()
        self.sp_pt.setRange(6, 500)
        self.sp_pt.setValue(120)
        self.sp_pt.setSingleStep(5)
        self.sp_pt.setSuffix(" pt")
        self.sp_pt.setFixedWidth(100)
        self.sp_pt.valueChanged.connect(self._schedule_refresh)
        grid.addWidget(self.rb_auto, 0, 0, 1, 3)
        grid.addWidget(self.rb_manual, 1, 0)
        grid.addWidget(self.sp_pt, 1, 1)
        grid.setColumnStretch(2, 1)
        v.addLayout(grid)

        # ---- 字形拉伸滑块 ----
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("color:#e5e7eb;")
        v.addWidget(line)

        head = QLabel("字形拉伸　<b>1.00×</b> = 自动铺满不动，往左变瘦、往右变胖")
        head.setWordWrap(True)
        head.setStyleSheet("color:#6b7280;font-size:12px;")
        v.addWidget(head)

        gs = QGridLayout()
        gs.setHorizontalSpacing(8)
        gs.setVerticalSpacing(4)
        self.sl_x = self._stretch_slider()
        self.sl_y = self._stretch_slider()
        self.btn_x = self._stretch_value_btn("横向 ↔", self.sl_x)
        self.btn_y = self._stretch_value_btn("纵向 ↕", self.sl_y)
        gs.addWidget(QLabel("横向 ↔"), 0, 0)
        gs.addWidget(self.sl_x, 0, 1)
        gs.addWidget(self.btn_x, 0, 2)
        gs.addWidget(QLabel("纵向 ↕"), 1, 0)
        gs.addWidget(self.sl_y, 1, 1)
        gs.addWidget(self.btn_y, 1, 2)
        gs.setColumnStretch(1, 1)
        v.addLayout(gs)

        self.stretch_tip = QLabel("")
        self.stretch_tip.setWordWrap(True)
        self.stretch_tip.setStyleSheet("color:#0f766e;font-size:12px;")
        v.addWidget(self.stretch_tip)

        self.font_combo.currentTextChanged.connect(self._on_font_changed)
        self._update_quick_buttons()
        self._on_stretch_changed()
        return g

    # ---------- 字形拉伸滑块 ----------
    def _stretch_slider(self) -> QSlider:
        """滑块用"百分数"存值：100 = 1.00×。范围对应 core 里定义的量程。"""
        sl = QSlider(Qt.Orientation.Horizontal)
        lo = int(round(core.STRETCH_X_RANGE[0] * 100))
        hi = int(round(core.STRETCH_X_RANGE[1] * 100))
        sl.setRange(lo, hi)
        sl.setValue(100)
        sl.setSingleStep(1)
        sl.setPageStep(5)
        sl.setFixedHeight(24)
        sl.setToolTip(f"可调范围 {lo / 100:.2f}× ~ {hi / 100:.2f}×，"
                      "方向键可微调，点右侧数字复位")
        sl.valueChanged.connect(self._on_stretch_changed)
        return sl

    @staticmethod
    def _slider_from_ratio(sl: QSlider, v: float) -> int:
        """倍率 -> 滑块整数值（100 = 1.00×），夹到滑块量程内。"""
        try:
            n = int(round(float(v) * 100))
        except (TypeError, ValueError):
            n = 100
        return max(sl.minimum(), min(sl.maximum(), n))

    def _stretch_value_btn(self, tip: str, sl: QSlider) -> QToolButton:
        """显示当前倍率的按钮，点一下复位到 1.00×。"""
        b = QToolButton()
        b.setFixedWidth(72)
        b.setFixedHeight(24)
        b.setStyleSheet(STRETCH_BTN_QSS)
        b.setText("1.00×")
        b.setToolTip(f"{tip}：当前拉伸倍率，点击复位到 1.00×")
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.clicked.connect(lambda _=False, s=sl: s.setValue(100))
        return b

    def _on_stretch_changed(self, *_) -> None:
        ux, uy = self.sl_x.value() / 100.0, self.sl_y.value() / 100.0
        self.btn_x.setText(f"{ux:.2f}×")
        self.btn_y.setText(f"{uy:.2f}×")
        for b, u in ((self.btn_x, ux), (self.btn_y, uy)):
            b.setStyleSheet(STRETCH_BTN_QSS + (
                "color:#2563eb;font-weight:600;" if abs(u - 1.0) > 1e-6
                else "color:#6b7280;"))
        self._update_stretch_tip()
        self._schedule_refresh()

    def _update_stretch_tip(self) -> None:
        ux, uy = self.sl_x.value() / 100.0, self.sl_y.value() / 100.0
        if abs(ux - 1.0) < 1e-6 and abs(uy - 1.0) < 1e-6:
            self.stretch_tip.setText("当前未做额外拉伸，宽高都按最大铺满。")
            return
        if abs(ux - uy) < 0.02:
            msg = ("横纵同步收窄 → 整块字等比例缩小、四周留白。"
                   if ux < 1.0 else
                   "横纵同步放大时两者会互相抵消（本来已撑满），外观几乎不变——"
                   "想让字形真的变化，请只拉一个方向。")
            self.stretch_tip.setText(msg)
            return
        parts = []
        if abs(ux - 1.0) > 1e-6:
            parts.append("横向放大 → 字变扁变宽" if ux > 1.0
                         else "横向收窄 → 字变瘦（两侧留白）")
        if abs(uy - 1.0) > 1e-6:
            parts.append("纵向放大 → 字变瘦变高" if uy > 1.0
                         else "纵向压低 → 字变扁（上下留白）")
        self.stretch_tip.setText("；".join(parts) + "。字号会自动让步，绝不溢出台签。")

    def _fill_fonts(self) -> None:
        fams = [f for f in QFontDatabase.families() if not f.startswith("@")]
        fams = sorted(set(fams), key=lambda s: s.lower())
        head = [f for f in core.CJK_PREFERRED if f in fams]
        rest = [f for f in fams if f not in head]
        self.font_combo.blockSignals(True)
        self.font_combo.clear()
        self.font_combo.addItems(head + rest)
        self.font_combo.blockSignals(False)
        self._font_head = head

    def _pick_quick_font(self, name: str) -> None:
        if name in [self.font_combo.itemText(i) for i in range(self.font_combo.count())]:
            self.font_combo.setCurrentText(name)
        else:
            QMessageBox.information(self, "提示", f"本机没有安装字体「{name}」。")

    def _update_quick_buttons(self) -> None:
        installed = {self.font_combo.itemText(i) for i in range(self.font_combo.count())}
        for name, btn in self._quick_btns:
            btn.setEnabled(name in installed)

    def _on_font_changed(self, text: str) -> None:
        if self._loading:
            return
        f = QFont(text, 11)
        self.font_combo.setFont(f)
        self._schedule_refresh()

    # ---------- 分组：尺寸
    def _group_size(self) -> QGroupBox:
        g = QGroupBox("③ 台签尺寸与排版")
        grid = QGridLayout(g)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)

        self.cmb_layout = QComboBox()
        self.cmb_layout.addItems(["贴边紧凑（省纸 · 少切几刀）",
                                  "整页居中（四周留白）"])
        self.cmb_layout.currentIndexChanged.connect(self._on_layout_changed)
        grid.addWidget(QLabel("排版方式"), 0, 0)
        grid.addWidget(self.cmb_layout, 0, 1, 1, 4)

        self.sp_w = self._mm_spin(150.0, 20, 400)
        self.sp_h = self._mm_spin(80.0, 20, 400)
        btn_swap = QPushButton("⇄ 互换")
        btn_swap.setFixedWidth(72)
        btn_swap.clicked.connect(self._swap_wh)

        grid.addWidget(QLabel("台签宽"), 1, 0)
        grid.addWidget(self.sp_w, 1, 1)
        grid.addWidget(QLabel("台签高"), 1, 2)
        grid.addWidget(self.sp_h, 1, 3)
        grid.addWidget(btn_swap, 1, 4)

        self.sp_pad = self._mm_spin(4.0, 0, 40)
        self.sp_gap = self._mm_spin(5.0, 0, 60)
        self.sp_margin = self._mm_spin(6.0, 0, 40)
        grid.addWidget(QLabel("文字留白"), 2, 0)
        grid.addWidget(self.sp_pad, 2, 1)
        grid.addWidget(QLabel("台签间距"), 2, 2)
        grid.addWidget(self.sp_gap, 2, 3)

        grid.addWidget(QLabel("纸张边距"), 3, 0)
        grid.addWidget(self.sp_margin, 3, 1)
        self.cmb_marks = QComboBox()
        self.cmb_marks.addItems(["废料定位点（推荐）", "定位虚线（贯通整页）",
                                 "四角角标", "整圈边框", "不打印任何标记"])
        self.cmb_marks.currentIndexChanged.connect(self._schedule_refresh)
        grid.addWidget(QLabel("切割标记"), 3, 2)
        grid.addWidget(self.cmb_marks, 3, 3)

        self.cmb_fit = QComboBox()
        self.cmb_fit.addItems([
            "拉伸铺满：每段一行，横向撑满整宽（推荐）",
            "自动折行铺满：保持字形，取最大字号",
            "单行等比：只按宽度适配，可能偏小",
        ])
        self.cmb_fit.currentIndexChanged.connect(self._on_fit_changed)
        grid.addWidget(QLabel("字多时"), 4, 0)
        grid.addWidget(self.cmb_fit, 4, 1, 1, 4)

        self.sp_pitch = self._ratio_spin(1.05, 0.90, 2.00)
        self.sp_subratio = self._ratio_spin(0.55, 0.30, 1.00)
        self.lbl_pitch = QLabel("行距")
        self.lbl_subratio = QLabel("副标题字号")
        grid.addWidget(self.lbl_pitch, 5, 0)
        grid.addWidget(self.sp_pitch, 5, 1)
        grid.addWidget(self.lbl_subratio, 5, 2)
        grid.addWidget(self.sp_subratio, 5, 3)

        self.cmb_paper = QComboBox()
        self.cmb_paper.addItems(list(core.PAPER_PRESETS.keys()))
        self.cmb_paper.currentIndexChanged.connect(self._schedule_refresh)
        grid.addWidget(QLabel("纸张"), 6, 0)
        grid.addWidget(self.cmb_paper, 6, 1, 1, 4)

        self.count_label = QLabel("")
        self.count_label.setWordWrap(True)
        self.count_label.setStyleSheet("color:#2563eb;")
        grid.addWidget(self.count_label, 7, 0, 1, 5)

        self.cut_label = QLabel("")
        self.cut_label.setWordWrap(True)
        self.cut_label.setStyleSheet("color:#0f766e;font-size:12px;")
        grid.addWidget(self.cut_label, 8, 0, 1, 5)

        grid.setColumnStretch(4, 1)
        return g

    def _on_layout_changed(self, *_) -> None:
        """贴边紧凑时，"台签间距/纸张边距"由程序固定为 0，控件置灰。"""
        compact = self.cmb_layout.currentIndex() == 0
        self.sp_gap.setEnabled(not compact)
        self.sp_margin.setEnabled(not compact)
        self._schedule_refresh()

    def _on_fit_changed(self, *_) -> None:
        """行距/副标题字号只在"自动折行"模式下有意义，其它模式置灰。"""
        wrap = self.cmb_fit.currentIndex() == 1
        self.lbl_pitch.setEnabled(wrap)
        self.lbl_subratio.setEnabled(wrap)
        self.sp_pitch.setEnabled(wrap)
        self.sp_subratio.setEnabled(wrap)
        self._schedule_refresh()

    def _mm_spin(self, val: float, lo: float, hi: float) -> QDoubleSpinBox:
        s = QDoubleSpinBox()
        s.setRange(lo, hi)
        s.setValue(val)
        s.setDecimals(1)
        s.setSingleStep(1.0)
        s.setSuffix(" mm")
        s.valueChanged.connect(self._schedule_refresh)
        return s

    def _ratio_spin(self, val: float, lo: float, hi: float) -> QDoubleSpinBox:
        """倍数型参数（行距 / 副标题比例）。"""
        s = QDoubleSpinBox()
        s.setRange(lo, hi)
        s.setValue(val)
        s.setDecimals(2)
        s.setSingleStep(0.05)
        s.setSuffix(" 倍")
        s.valueChanged.connect(self._schedule_refresh)
        return s

    def _swap_wh(self) -> None:
        w, h = self.sp_w.value(), self.sp_h.value()
        self.sp_w.setValue(h)
        self.sp_h.setValue(w)

    # ---------- 分组：打印
    def _group_print(self) -> QGroupBox:
        g = QGroupBox("④ 打印")
        grid = QGridLayout(g)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)

        self.cmb_printer = QComboBox()
        self._printer_names = []
        self._reload_printers()
        grid.addWidget(QLabel("打印机"), 0, 0)
        grid.addWidget(self.cmb_printer, 0, 1, 1, 3)

        self.sp_copies = QSpinBox()
        self.sp_copies.setRange(1, 99)
        self.sp_copies.setValue(1)
        self.sp_copies.valueChanged.connect(self._schedule_refresh)
        self.sp_repeat = QSpinBox()
        self.sp_repeat.setRange(1, 20)
        self.sp_repeat.setValue(1)
        self.sp_repeat.valueChanged.connect(self._schedule_refresh)
        grid.addWidget(QLabel("整份份数"), 1, 0)
        grid.addWidget(self.sp_copies, 1, 1)
        grid.addWidget(QLabel("每名字张数"), 1, 2)
        grid.addWidget(self.sp_repeat, 1, 3)

        row = QHBoxLayout()
        self.btn_print = QPushButton("🖨  打印")
        self.btn_print.setFixedHeight(36)
        self.btn_print.setStyleSheet(
            "QPushButton{background:#2563eb;color:#fff;border:none;border-radius:6px;"
            "font-size:14px;font-weight:600;}"
            "QPushButton:hover{background:#1d4ed8;}"
            "QPushButton:pressed{background:#1e40af;}")
        self.btn_print.clicked.connect(self.do_print)
        btn_pdf = QPushButton("导出 PDF")
        btn_pdf.setFixedHeight(36)
        btn_pdf.clicked.connect(self.export_pdf)
        btn_reset = QPushButton("恢复默认")
        btn_reset.setFixedHeight(36)
        btn_reset.clicked.connect(self.reset_defaults)
        row.addWidget(self.btn_print, 3)
        row.addWidget(btn_pdf, 2)
        row.addWidget(btn_reset, 2)

        wrap = QVBoxLayout()
        wrap.addLayout(row)
        grid.addLayout(wrap, 2, 0, 1, 4)
        grid.setColumnStretch(3, 1)
        return g

    def _reload_printers(self) -> None:
        self.cmb_printer.clear()
        names = [p.printerName() for p in QPrinterInfo.availablePrinters()]
        self._printer_names = names
        if names:
            self.cmb_printer.addItems(names)
            try:
                default = QPrinterInfo.defaultPrinter().printerName()
                if default in names:
                    self.cmb_printer.setCurrentText(default)
            except Exception:
                pass
        else:
            self.cmb_printer.addItem("（未检测到打印机）")
        self.cmb_printer.setEnabled(bool(names))

    # -------------------------------------------------- 刷新
    def _schedule_refresh(self, *_) -> None:
        if self._loading:
            return
        self._refresh_timer.start()

    def _sync_state_from_ui(self) -> None:
        o = self.state.opt
        o.paper = self.cmb_paper.currentText()
        o.plate_w = self.sp_w.value()
        o.plate_h = self.sp_h.value()
        o.layout = "compact" if self.cmb_layout.currentIndex() == 0 else "grid"
        # 紧凑模式下这两个值不参与计算，但仍然保留用户填的数，便于切回居中模式
        o.gap_mm = self.sp_gap.value()
        o.margin_mm = self.sp_margin.value()
        o.padding_mm = self.sp_pad.value()
        o.font_family = self.font_combo.currentText().strip() or "微软雅黑"
        o.bold = self.chk_bold.isChecked()
        o.invert = self.chk_invert.isChecked()
        o.auto_size = self.rb_auto.isChecked()
        o.manual_pt = self.sp_pt.value()
        fi = max(0, min(self.cmb_fit.currentIndex(), len(FIT_MODES) - 1))
        o.fit_mode = FIT_MODES[fi]
        o.auto_wrap = (o.fit_mode == "wrap")     # 兼容旧版本配置字段
        o.line_pitch = self.sp_pitch.value()
        o.subtitle_ratio = self.sp_subratio.value()
        o.stretch_x = self.sl_x.value() / 100.0
        o.stretch_y = self.sl_y.value() / 100.0
        i = max(0, min(self.cmb_marks.currentIndex(), len(MARKS_ORDER) - 1))
        o.marks = MARKS_ORDER[i]
        o.printer = self.cmb_printer.currentText() if self._printer_names else ""
        o.copies = self.sp_copies.value()
        o.repeat = self.sp_repeat.value()
        self.state.names = core.parse_names(self.names_edit.toPlainText())

    def refresh(self) -> None:
        self._sync_state_from_ui()
        st = self.state
        st.rebuild()

        if st.cols == 0 or st.rows == 0:
            self.count_label.setText("⚠ 台签尺寸放不进这张纸，请调小尺寸或改用更大的纸。")
            self.count_label.setStyleSheet("color:#dc2626;font-weight:600;")
            self.cut_label.setText("")
        else:
            n = 1 if not st.names else len(st.pages)
            mode = "贴边" if st.opt.layout == "compact" else "居中"
            self.count_label.setText(
                f"每张纸可排 {st.cols} 列 × {st.rows} 行 = {st.cols*st.rows} 张台签"
                f"（{mode}），共 {n} 页")
            self.count_label.setStyleSheet("color:#2563eb;")
            self.cut_label.setText(self._cut_hint(st))

        # 自动字号提示
        if st.names:
            rep: list = []
            pw, ph = st.page_size()
            opt = st.opt
            pad = min(opt.padding_mm, opt.plate_w / 4.0, opt.plate_h / 4.0)
            bw = opt.plate_w - 2 * pad
            bh = opt.plate_h - 2 * pad
            pt = core.layout_plate_text(opt.font_family, opt.bold,
                                        st.names[0], bw, bh, opt)
            em = pt.em_mm
            fill_h = pt.height_mm / bh * 100.0 if bh else 0.0
            ux, uy = core.stretch_pair(opt)
            stag = ""
            if abs(ux - 1.0) > 1e-6 or abs(uy - 1.0) > 1e-6:
                stag = f"，拉伸 横{ux:.2f}×/纵{uy:.2f}×"
            if pt.rows:
                # 拉伸铺满：每段一行，横向撑满，所以宽度填充率恒为满宽
                w_max = max(r.width_mm for r in pt.rows)
                y0 = min(r.cy_mm - r.height_mm / 2.0 for r in pt.rows)
                y1 = max(r.cy_mm + r.height_mm / 2.0 for r in pt.rows)
                vfill = (y1 - y0) / bh * 100.0 if bh else 0.0
                s = [r.sx for r in pt.rows]
                self.info_label.setText(
                    f"示例「{st.names[0]}」：{len(pt.rows)} 段 → 每段一行（不折行），"
                    f"字面高 {em:.1f} mm，铺满 "
                    f"{w_max / bw * 100 if bw else 0:.0f}% × {vfill:.0f}%"
                    f"，横向缩放 {min(s):.2f}~{max(s):.2f}×{stag}")
            else:
                fill_w = pt.main.width_mm / bw * 100.0 if bw else 0.0
                line_info = (f"{pt.main.count} 行" if pt.main.count > 1 else "1 行")
                self.info_label.setText(
                    f"示例「{st.names[0]}」：{line_info}，字面高 {em:.1f} mm"
                    f"（≈{core.em_mm_to_pt(em):.0f} pt），"
                    f"铺满 {fill_w:.0f}% × {fill_h:.0f}%{stag}")
        else:
            self.info_label.setText("请在左侧输入名字")

        self.page_label.setText(f"第 {st.page_idx + 1} / {len(st.pages)} 页")
        self.btn_prev.setEnabled(st.page_idx > 0)
        self.btn_next.setEnabled(st.page_idx < len(st.pages) - 1)
        self.preview.update()

    @staticmethod
    def _cut_hint(st: State) -> str:
        """用一句话说清"这叠纸该怎么下刀"。"""
        opt = st.opt
        size = f"{opt.plate_w:g}×{opt.plate_h:g} mm"
        if opt.layout != "compact":
            return "✂ 居中排版：四周都是边角料，需沿每张台签的四条边分别裁切。"

        xs, ys = st.cut_lines()
        if not xs and not ys:
            return f"✂ 台签正好铺满整张纸，无需裁切，直接沿纸边取用即可。"

        parts = []
        if xs:
            parts.append("在距左边 " + " / ".join(f"{x:.0f}" for x in xs) + " mm 处竖切")
        if ys:
            parts.append("在距上边 " + " / ".join(f"{y:.0f}" for y in ys) + " mm 处横切")
        tip = (f"✂ 共 {len(xs) + len(ys)} 刀：" + "，".join(parts)
               + f"。切完丢掉右侧和下方的边角料，得到 {size} 台签。")
        tip += {
            "tick": "　废料区每条刀口印 2 个定位点，对齐后下刀，标记随废料一起丢掉。",
            "guide": "　沿浅灰虚线切，线被刀口一分为二。",
            "none": "　未印任何标记，请用尺量取后再切。",
        }.get(opt.marks, "")
        if opt.padding_mm < 5.0:
            tip += "　若纸边出现打不出的白边，把「文字留白」调到 5 mm 以上。"
        return tip

    def goto_page(self, delta: int) -> None:
        self.state.page_idx += delta
        self.state.page_idx = max(0, min(self.state.page_idx, len(self.state.pages) - 1))
        self.page_label.setText(
            f"第 {self.state.page_idx + 1} / {len(self.state.pages)} 页")
        self.btn_prev.setEnabled(self.state.page_idx > 0)
        self.btn_next.setEnabled(self.state.page_idx < len(self.state.pages) - 1)
        self.preview.update()

    # -------------------------------------------------- 打印 / 导出
    def do_print(self) -> None:
        self.refresh()
        st = self.state
        if not st.names:
            QMessageBox.information(self, "提示", "请先在左侧输入要打印的名字。")
            return
        if st.cols == 0 or st.rows == 0:
            QMessageBox.warning(self, "无法排版", "台签尺寸放不进当前纸张，请调整后重试。")
            return
        if not self._printer_names:
            QMessageBox.warning(self, "没有打印机", "系统里没有检测到打印机。")
            return

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setPrinterName(st.opt.printer or self._printer_names[0])
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        printer.setPageOrientation(
            QPageLayout.Orientation.Landscape if "横向" in st.opt.paper
            else QPageLayout.Orientation.Portrait)
        printer.setFullPage(True)
        printer.setCopyCount(max(1, st.opt.copies))

        dlg = QPrintDialog(printer, self)
        dlg.setWindowTitle("打印台签")
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        # 以打印对话框里最终确定的纸张为准
        sz = printer.pageLayout().pageSize().size(QPageSize.Unit.Millimeter)
        pw, ph = float(sz.width()), float(sz.height())
        actual_pages = core.paginate(st.names, max(1, st.cols * st.rows), st.opt.repeat)

        painter = QPainter()
        if not painter.begin(printer):
            QMessageBox.critical(self, "打印失败", "无法连接打印机，请检查打印机状态。")
            return
        try:
            kx, ky = self._device_scale(painter, printer, pw, ph)
            for i, page in enumerate(actual_pages):
                if i > 0:
                    printer.newPage()
                core.render_page(painter, page, st.opt, pw, ph, kx, ky)
        except Exception as exc:                       # noqa: BLE001
            painter.end()
            QMessageBox.critical(self, "打印失败", f"打印过程中出错：\n{exc}")
            return
        painter.end()
        self.statusBar().showMessage(
            f"已发送 {len(actual_pages)} 页到「{printer.printerName()}」", 8000)

    @staticmethod
    def _device_scale(painter: QPainter, printer: QPrinter,
                      pw_mm: float, ph_mm: float) -> tuple[float, float]:
        """求 mm -> 设备像素 的比例。

        两个独立来源取较小值：驱动上报的 DPI，以及"设备像素尺寸 ÷ 纸张毫米
        尺寸"。正常情况下二者一致（fullPage 生效）；万一某台驱动把"可打印
        区域"当成整页上报，取小值也能保证版面不会超出纸张。
        """
        kx, ky = printer.logicalDpiX() / 25.4, printer.logicalDpiY() / 25.4
        dev = painter.device()
        dw, dh = float(dev.width()), float(dev.height())
        if dw > 0 and dh > 0 and pw_mm > 0 and ph_mm > 0:
            dkx, dky = dw / pw_mm, dh / ph_mm
            if 2.0 <= dkx <= 95.0:
                kx = min(kx, dkx)
            if 2.0 <= dky <= 95.0:
                ky = min(ky, dky)
        return kx, ky

    def export_pdf(self) -> None:
        self.refresh()
        st = self.state
        if not st.names:
            QMessageBox.information(self, "提示", "请先在左侧输入要打印的名字。")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出 PDF", os.path.join(os.path.expanduser("~"), "台签.pdf"),
            "PDF 文件 (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"

        pw, ph = st.page_size()
        writer = QPdfWriter(path)
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        writer.setPageOrientation(
            QPageLayout.Orientation.Landscape if "横向" in st.opt.paper
            else QPageLayout.Orientation.Portrait)
        writer.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Unit.Millimeter)
        writer.setResolution(300)

        k = 300 / 25.4
        painter = QPainter(writer)
        try:
            for i, page in enumerate(st.pages):
                if i > 0:
                    writer.newPage()
                core.render_page(painter, page, st.opt, pw, ph, k, k)
        finally:
            painter.end()
        self.statusBar().showMessage(f"已导出：{path}", 8000)

    # -------------------------------------------------- 配置存取
    def reset_defaults(self) -> None:
        d = core.Options().to_dict()
        self._apply_config(d)
        self.refresh()

    def _apply_config(self, d: dict) -> None:
        self._loading = True
        try:
            o = core.Options.from_dict(d)
            self.cmb_paper.setCurrentText(
                o.paper if o.paper in core.PAPER_PRESETS else list(core.PAPER_PRESETS)[0])
            self.sp_w.setValue(o.plate_w)
            self.sp_h.setValue(o.plate_h)
            self.sp_gap.setValue(o.gap_mm)
            self.sp_margin.setValue(o.margin_mm)
            self.sp_pad.setValue(o.padding_mm)
            if o.font_family:
                idx = self.font_combo.findText(o.font_family)
                if idx >= 0:
                    self.font_combo.setCurrentIndex(idx)
                else:
                    self.font_combo.setCurrentText(o.font_family)
            self.chk_bold.setChecked(bool(o.bold))
            self.chk_invert.setChecked(bool(o.invert))
            self.rb_auto.setChecked(bool(o.auto_size))
            self.rb_manual.setChecked(not bool(o.auto_size))
            self.sp_pt.setValue(o.manual_pt)
            self.cmb_fit.setCurrentIndex(
                FIT_MODES.index(core.fit_mode_of(o))
                if core.fit_mode_of(o) in FIT_MODES else 0)
            self.sp_pitch.setValue(o.line_pitch)
            self.sp_subratio.setValue(o.subtitle_ratio)
            self.sl_x.setValue(self._slider_from_ratio(self.sl_x, o.stretch_x))
            self.sl_y.setValue(self._slider_from_ratio(self.sl_y, o.stretch_y))
            self.cmb_layout.setCurrentIndex(0 if o.layout == "compact" else 1)
            self.cmb_marks.setCurrentIndex(
                MARKS_ORDER.index(o.marks) if o.marks in MARKS_ORDER else 0)
            self.sp_copies.setValue(int(o.copies))
            self.sp_repeat.setValue(int(o.repeat))
            if o.printer and o.printer in self._printer_names:
                self.cmb_printer.setCurrentText(o.printer)
            self._on_layout_changed()
            self._on_fit_changed()
            self._on_stretch_changed()
        finally:
            self._loading = False

    def _load(self) -> None:
        cfg = load_config()
        d = cfg.get("options", {})
        if not d:
            # 首次运行：挑一个本机存在的中文字体
            installed = {self.font_combo.itemText(i) for i in range(self.font_combo.count())}
            for cand in core.CJK_PREFERRED:
                if cand in installed:
                    d = {"font_family": cand}
                    break
        elif "layout" not in d:
            # 老版本配置：升级为"贴边紧凑 + 废料定位点"，正好对应最省刀的切法
            d["layout"] = "compact"
            d["marks"] = "tick"
        elif d.get("layout") == "compact" and d.get("marks") in (None, ""):
            # 老配置没存过 marks：默认用废料区定位点（下拉框里可切回虚线）
            d["marks"] = "tick"
        if "fit_mode" not in d:
            # 更老的配置只有 auto_wrap 布尔值。新默认是"拉伸铺满"（每段一行、
            # 横向撑满），正好对上用户原来那套工具的效果，所以老配置统一升到它。
            d["fit_mode"] = "stretch"
        self._apply_config(d)
        self.names_edit.setPlainText(cfg.get("names", "张三\n李四\n王五|销售总监"))
        self._update_quick_buttons()

    def closeEvent(self, event) -> None:  # noqa: N802
        save_config({
            "options": self.state.opt.to_dict(),
            "names": self.names_edit.toPlainText(),
        })
        super().closeEvent(event)


# ------------------------------------------------------------------ 入口

QSS = """
QGroupBox{border:1px solid #d8dee7;border-radius:8px;margin-top:10px;
          padding:12px 10px 10px 10px;background:#ffffff;font-weight:600;}
QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 5px;color:#374151;}
QComboBox,QDoubleSpinBox,QSpinBox,QPlainTextEdit{border:1px solid #cfd6e0;
    border-radius:6px;padding:3px 6px;background:#fff;min-height:22px;}
QComboBox:focus,QDoubleSpinBox:focus,QSpinBox:focus,QPlainTextEdit:focus{border-color:#2563eb;}
QPushButton{border:1px solid #cfd6e0;border-radius:6px;padding:3px 10px;background:#f8fafc;}
QPushButton:hover{background:#eef2f7;}
QPushButton:disabled{color:#b6bcc6;}
QToolButton{border:1px solid #cfd6e0;border-radius:6px;padding:4px 12px;background:#fff;}
QToolButton:hover{background:#eef2f7;}
QToolButton:disabled{color:#b6bcc6;}
QLabel{color:#374151;}
QRadioButton,QCheckBox{color:#374151;}
"""


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    # 界面字体：优先用一款本机存在的中文字体
    fams = set(QFontDatabase.families())
    for cand in ["微软雅黑", "Microsoft YaHei", "等线", "黑体", "SimHei"]:
        if cand in fams:
            app.setFont(QFont(cand, 9))
            break
    app.setStyleSheet(QSS)

    w = MainWindow()
    w.show()
    return app.exec()


# ------------------------------------------------------------------ 打包自检

def selftest() -> int:
    """--selftest：在打包后的独立 exe 里验证字体/打印机/渲染是否正常。

    结果写到 selftest.log，并渲染一张 sample.png 便于直观检查。
    """
    from PySide6.QtGui import QImage

    if getattr(sys, "frozen", False):
        base = os.path.dirname(os.path.abspath(sys.executable))
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    out_dir = base
    if "--out" in sys.argv:
        i = sys.argv.index("--out")
        if i + 1 < len(sys.argv):
            out_dir = sys.argv[i + 1]
    os.makedirs(out_dir, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv)
    lines = []
    lines.append(f"frozen = {getattr(sys, 'frozen', False)}")
    lines.append(f"executable = {sys.executable}")

    fams = list(QFontDatabase.families())
    lines.append(f"字体总数 = {len(fams)}")
    cjk = [c for c in core.CJK_PREFERRED if c in set(fams)]
    lines.append(f"中文字体 = {cjk}")

    prn = [p.printerName() for p in QPrinterInfo.availablePrinters()]
    lines.append(f"打印机 = {prn}")
    try:
        lines.append(f"默认打印机 = {QPrinterInfo.defaultPrinter().printerName()}")
    except Exception as exc:                                  # noqa: BLE001
        lines.append(f"默认打印机 = <{exc}>")

    fam = cjk[0] if cjk else (fams[0] if fams else "Arial")
    opt = core.Options(font_family=fam, plate_w=150.0, plate_h=80.0)
    cols, rows = core.layout_count(210, 297, opt)
    lines.append(f"字体={fam}  排版={opt.layout}  A4 每页 = "
                 f"{cols}列 x {rows}行 = {cols*rows} 张")
    xs, ys = core.cut_plan(210, 297, opt, cols, rows)
    lines.append(f"切割标记={opt.marks}  竖切线 x={xs}  横切线 y={ys}  "
                 f"共 {len(xs)+len(ys)} 刀")
    pos = core.layout_positions(210.0, 297.0, opt, cols, rows)
    segs = core.tick_segments(pos, opt, 210.0, 297.0, cols, rows)
    lines.append(f"废料区定位点 = {len(segs)} 个")
    for x1, y1, x2, y2 in segs:
        lines.append(f"    ({x1:.1f},{y1:.1f}) -> ({x2:.1f},{y2:.1f})")
    pad = min(opt.padding_mm, opt.plate_w / 4.0, opt.plate_h / 4.0)
    bw, bh = opt.plate_w - 2 * pad, opt.plate_h - 2 * pad
    lines.append(f"填充方式 = {core.fit_mode_of(opt)}"
                 f"（可用方框 {bw:.0f}×{bh:.0f} mm，"
                 f"横向缩放上下限 {core.STRETCH_MIN}~{core.STRETCH_MAX}）")

    lines.append("--- 拉伸铺满自检：每段一行，整行撑满宽度 ---")
    for t in ["张三", "赵正义", "张小三四五", "张小三四五六七八九",
              "慕容雪见·兰", "慕容雪见·兰|编制质控单位|专家组长",
              "中国国际航空股份有限公司"]:
        pt = core.layout_plate_text(fam, True, t, bw, bh, opt)
        segs_n = len([s for s in core.split_rows(t) if s.strip()])
        ok = "OK" if len(pt.rows) == segs_n else "✗ 行数不符"
        lines.append(f"  「{t}」({segs_n}段) -> {len(pt.rows)} 行  {ok}")
        for r in pt.rows:
            lines.append(f"      {r.text:<14s} 字面高 {r.em_mm:6.2f} mm"
                         f"  横向 ×{r.sx:.2f}  实测宽 {r.width_mm:6.2f} mm"
                         f"  ({r.width_mm / bw * 100:.0f}% 宽)")

    o_wrap = core.Options(**opt.to_dict())
    o_wrap.fit_mode = "wrap"
    lines.append("--- 对照：自动折行铺满（fit_mode=wrap）---")
    for t in ["张小三四五六七八九", "慕容雪见·兰", "中国国际航空股份有限公司"]:
        blk = core.fit_block(fam, True, t, bw, bh, allow_wrap=True,
                             pitch=o_wrap.line_pitch)
        one = core.fit_block(fam, True, t, bw, bh, allow_wrap=False,
                             pitch=o_wrap.line_pitch)
        fw = blk.width_mm / bw * 100.0
        fh = blk.height_mm / bh * 100.0
        gain = blk.em_mm / one.em_mm if one.em_mm else 1.0
        lines.append(
            f"  「{t}」({len(t)}字) -> {blk.count} 行 {blk.lines if blk.count > 1 else ''}"
            f" 字面高 {blk.em_mm:.2f} mm ≈ {core.em_mm_to_pt(blk.em_mm):.0f} pt"
            f"  铺满 {fw:.0f}%×{fh:.0f}%"
            f"  比单行 {one.em_mm:.2f} mm 大 {gain:.2f} 倍")
    lines.append("--- 带副标题（拉伸模式，各段等权）---")
    for t in ["王五|销售总监", "慕容雪见·兰|编制质控单位|专家组长"]:
        pt = core.layout_plate_text(fam, True, t, bw, bh, opt)
        lines.append(f"  「{t}」→ {len(pt.rows)} 行，"
                     f"整组铺满高 {pt.height_mm / bh * 100:.0f}%，"
                     f"字面高 {pt.em_mm:.2f} mm")

    lines.append("--- 手动字形拉伸滑块（叠在自动铺满之上，永远不溢出）---")
    for t in ["张三", "张小三四五六七八九"]:
        for ux, uy in ((1.0, 1.0), (1.60, 1.00), (0.60, 1.00),
                       (1.00, 1.60), (1.00, 0.60)):
            o3 = core.Options(**opt.to_dict())
            o3.stretch_x, o3.stretch_y = ux, uy
            p3 = core.layout_plate_text(fam, True, t, bw, bh, o3)
            if not p3.rows:
                continue
            r = p3.rows[0]
            ok = (r.width_mm <= bw + 0.02 and r.height_mm <= bh + 0.02)
            lines.append(
                f"  「{t}」横{ux:.2f}× 纵{uy:.2f}× → 墨迹 "
                f"{r.width_mm:6.2f}×{r.height_mm:5.2f} mm"
                f"  宽高比 {r.width_mm / max(r.height_mm, 1e-6):5.2f}"
                f"  {'OK' if ok else '✗ 溢出可用方框'}")

    dpi = 200.0
    k = dpi / 25.4
    for tag, mk in (("定位点", "tick"), ("虚线", "guide")):
        o2 = core.Options(**opt.to_dict())
        o2.marks = mk
        img = QImage(int(210 * k), int(297 * k), QImage.Format.Format_RGB32)
        img.setDotsPerMeterX(int(dpi / 0.0254))
        img.setDotsPerMeterY(int(dpi / 0.0254))
        img.fill(QColor("white"))
        p = QPainter(img)
        core.render_page(p, ["张三", "李四", "欧阳明月"], o2, 210.0, 297.0, k, k)
        p.end()
        png = os.path.join(out_dir, f"selftest_sample_{mk}.png")
        lines.append(f"渲染样例[{tag}] = {png} -> {img.save(png)}")

    # 长名字样张：专门用来肉眼确认"字多也铺满，且不折行"
    img = QImage(int(210 * k), int(297 * k), QImage.Format.Format_RGB32)
    img.setDotsPerMeterX(int(dpi / 0.0254))
    img.setDotsPerMeterY(int(dpi / 0.0254))
    img.fill(QColor("white"))
    p = QPainter(img)
    core.render_page(p, ["慕容雪见·兰", "慕容雪见·兰|编制质控单位|专家组长",
                         "张小三四五六七八九"],
                     opt, 210.0, 297.0, k, k)
    p.end()
    png = os.path.join(out_dir, "selftest_sample_stretch.png")
    lines.append(f"渲染样例[拉伸铺满] = {png} -> {img.save(png)}")

    txt = "\n".join(lines)
    with open(os.path.join(out_dir, "selftest.log"), "w", encoding="utf-8") as fh:
        fh.write(txt)
    try:
        print(txt)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    sys.exit(main())
