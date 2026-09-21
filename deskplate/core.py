# -*- coding: utf-8 -*-
"""台签排版核心。

约定：
  * 所有几何量单位为毫米(mm)；
  * 绘制时由调用方给出 mm -> 设备像素 的比例 kx / ky，因此**预览与打印
    共用同一段绘制代码**，所见即所得；
  * 字号内部统一用"字面高度 em(mm)"表示，避开 pt/dpi 换算的坑，
    展示给用户时再折算成 pt。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Sequence, Tuple

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPen

# ---------------------------------------------------------------- 常量

MM_PER_PT = 25.4 / 72.0

PAPER_PRESETS: Dict[str, Tuple[float, float]] = {
    "A4 纵向 (210×297)": (210.0, 297.0),
    "A4 横向 (297×210)": (297.0, 210.0),
    "A3 纵向 (297×420)": (297.0, 420.0),
    "A3 横向 (420×297)": (420.0, 297.0),
}

# 常见中文字体，按优先级排列，按钮/默认值会用到
CJK_PREFERRED = [
    "微软雅黑", "Microsoft YaHei", "黑体", "SimHei", "思源黑体", "Source Han Sans SC",
    "等线", "DengXian", "仿宋", "FangSong", "楷体", "KaiTi", "宋体", "SimSun",
    "华文中宋", "STZhongsong", "隶书", "LiSu", "幼圆", "YouYuan",
    "华文楷体", "STKaiti", "华文琥珀", "STHupo", "方正粗黑宋简体",
]

# 最多折成几行（实际由几何算出，这里只是上限，防止极端输入）
MAX_WRAP_LINES = 6

# 「拉伸铺满」模式：每段一行，行高均分，整行横向拉伸到撑满可用宽度。
STRETCH_ROW_FILL = 0.90   # 行墨迹高 = 行槽高 × 该系数（剩下的当行间隙）
STRETCH_MIN = 0.45        # 横向压缩下限：再窄就不像字了，改用缩字号保宽度
STRETCH_MAX = 2.60        # 横向拉伸上限：短内容的字本来就不该被拉成大胖子

# 手动「字形拉伸」滑块：乘在自动铺满结果之上的额外倍率，1.00 = 不动
STRETCH_X_RANGE = (0.40, 2.50)   # 横向（左右）
STRETCH_Y_RANGE = (0.40, 2.50)   # 纵向（上下）
SX_ABS_MIN = 0.10                # 横向缩放绝对下限（只防病态输入）
SX_ABS_MAX = 8.00                # 横向缩放绝对上限


# ---------------------------------------------------------------- 参数

@dataclass
class Options:
    """一份排版/打印方案。"""

    # 纸张
    paper: str = "A4 纵向 (210×297)"
    # 台签尺寸
    plate_w: float = 150.0
    plate_h: float = 80.0
    gap_mm: float = 5.0          # 台签间距（紧凑模式下忽略，恒为 0）
    margin_mm: float = 6.0       # 距纸张边缘的边距（紧凑模式下忽略，恒为 0）
    padding_mm: float = 4.0      # 文字与台签边缘的留白
    # compact = 从纸张左上角开始紧贴排列，只需在右侧/下方下刀
    # grid    = 整块版心在纸上居中，四周留白
    layout: str = "compact"

    # 字体
    font_family: str = ""
    bold: bool = True
    auto_size: bool = True
    manual_pt: float = 120.0
    invert: bool = False         # 黑底白字

    # 字多的时候怎么"铺满"台签
    #   stretch = 每段（`|` 分段）独占一行，**横向拉伸**把整行撑满，永不折行
    #             —— 老工具的效果：字多字少都是一行，整张台签铺满
    #   wrap    = 按内容自动折行，保持字形不变形，取最大字号
    #   plain   = 不折行不拉伸，按宽度等比适配（字最小，特殊场合用）
    fit_mode: str = "stretch"
    auto_wrap: bool = True       # 兼容旧配置，读入时映射到 fit_mode
    line_pitch: float = 1.05     # 行距 = 字面高度 × 该倍数（1.0 = 紧贴）

    # 手动字形拉伸：乘在"自动铺满"结果之上的额外倍率
    #   横向 stretch_x > 1 → 更宽更扁；< 1 → 更瘦（两侧留白）
    #   纵向 stretch_y > 1 → 更高更瘦；< 1 → 更扁（上下留白）
    #   两者都是 1.00 时与原来完全一致（宽、高都撑满）
    stretch_x: float = 1.0
    stretch_y: float = 1.0

    # 切割标记
    #   tick  = 废料区定位点（推荐，成品上不留任何印刷痕迹）
    #   guide = 贯通整页的浅灰虚线
    #   corner= 四角角标   box = 整圈边框   none = 不打印
    marks: str = "tick"
    mark_len_mm: float = 2.5
    mark_offset_mm: float = 0.6  # 标记与台签边缘的间距
    mark_width_mm: float = 0.25  # 标记线宽
    tick_len_mm: float = 6.0     # 定位点长度
    tick_width_mm: float = 0.35  # 定位点线宽
    tick_inset_mm: float = 8.0   # 定位点距纸张边缘的距离（避开打印机不可打印区）

    # 打印
    printer: str = ""
    copies: int = 1
    repeat: int = 1              # 每个名字重复打印几张
    subtitle_ratio: float = 0.55  # 副标题最大字号 = 主标题 × 该比例

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Options":
        opt = cls()
        for k, v in (d or {}).items():
            if hasattr(opt, k):
                try:
                    setattr(opt, k, v)
                except Exception:
                    pass
        return opt


# ---------------------------------------------------------------- 版面计算

def grid_count(page_w: float, page_h: float, item_w: float, item_h: float,
               gap: float = 5.0, margin: float = 6.0) -> Tuple[int, int]:
    """一页能排下几列几行。"""
    if min(page_w, page_h, item_w, item_h) <= 0:
        return 0, 0
    avail_w = page_w - 2 * margin
    avail_h = page_h - 2 * margin
    if avail_w < item_w or avail_h < item_h:
        return 0, 0
    cols = int(math.floor((avail_w + gap + 1e-9) / (item_w + gap)))
    rows = int(math.floor((avail_h + gap + 1e-9) / (item_h + gap)))
    return max(0, cols), max(0, rows)


def grid_positions(page_w: float, page_h: float, item_w: float, item_h: float,
                   cols: int, rows: int, gap: float = 5.0) -> List[Tuple[float, float]]:
    """整块版心在纸上居中，返回每个台签左上角的 (x, y)。"""
    total_w = cols * item_w + max(0, cols - 1) * gap
    total_h = rows * item_h + max(0, rows - 1) * gap
    x0 = (page_w - total_w) / 2.0
    y0 = (page_h - total_h) / 2.0
    out: List[Tuple[float, float]] = []
    for r in range(rows):
        for c in range(cols):
            out.append((x0 + c * (item_w + gap), y0 + r * (item_h + gap)))
    return out


def compact_count(page_w: float, page_h: float,
                  item_w: float, item_h: float) -> Tuple[int, int]:
    """紧贴排版能放下几列几行（不留边距、不留间距）。"""
    if min(page_w, page_h, item_w, item_h) <= 0:
        return 0, 0
    cols = int(math.floor(page_w / item_w + 1e-9))
    rows = int(math.floor(page_h / item_h + 1e-9))
    return max(0, cols), max(0, rows)


def compact_positions(item_w: float, item_h: float,
                      cols: int, rows: int) -> List[Tuple[float, float]]:
    """从纸张左上角 (0,0) 开始逐行铺排。"""
    out: List[Tuple[float, float]] = []
    for r in range(rows):
        for c in range(cols):
            out.append((c * item_w, r * item_h))
    return out


def layout_count(page_w: float, page_h: float, opt: "Options") -> Tuple[int, int]:
    """按当前排版方式算出每页的列数/行数。"""
    if opt.layout == "compact":
        return compact_count(page_w, page_h, opt.plate_w, opt.plate_h)
    return grid_count(page_w, page_h, opt.plate_w, opt.plate_h,
                      opt.gap_mm, opt.margin_mm)


def layout_positions(page_w: float, page_h: float, opt: "Options",
                     cols: int, rows: int) -> List[Tuple[float, float]]:
    """按当前排版方式算出每张台签左上角的 (x, y)，单位为 mm。"""
    if opt.layout == "compact":
        return compact_positions(opt.plate_w, opt.plate_h, cols, rows)
    return grid_positions(page_w, page_h, opt.plate_w, opt.plate_h,
                          cols, rows, opt.gap_mm)


def cut_plan(page_w: float, page_h: float, opt: "Options",
             cols: int, rows: int) -> Tuple[List[float], List[float]]:
    """算出实际需要下刀的切割线位置。

    返回 (竖线 x 列表, 横线 y 列表)，单位 mm。贴在纸张边缘的那一刀
    不需要切（纸边本身就是断口），所以会被自动排除。
    """
    if opt.layout != "compact":
        return [], []
    xs = [i * opt.plate_w for i in range(1, cols + 1)
          if i * opt.plate_w < page_w - 0.5]
    ys = [j * opt.plate_h for j in range(1, rows + 1)
          if j * opt.plate_h < page_h - 0.5]
    return xs, ys


def paginate(names: Sequence[str], per_page: int, repeat: int = 1) -> List[List[str]]:
    """把名字切成每页 per_page 个；repeat 为每个名字重复的份数。"""
    seq: List[str] = []
    for n in names:
        seq.extend([n] * max(1, int(repeat)))
    if not seq:
        return [[]]
    per = max(1, per_page)
    return [seq[i:i + per] for i in range(0, len(seq), per)]


def parse_names(text: str) -> List[str]:
    return [ln.strip() for ln in (text or "").splitlines() if ln.strip()]


def split_rows(text: str) -> List[str]:
    """把一张台签的内容切成若干"行"。

    用 `|`（或全角 `｜`）分隔：第一段是主标题，后面的都是副标题行。
    例：``张三|销售总监|华东大区`` → ``['张三', '销售总监', '华东大区']``
    """
    t = (text or "").replace("｜", "|").strip()
    if not t:
        return [""]
    rows = [s.strip() for s in t.split("|")]
    rows = [r for r in rows if r]
    return rows or [t]


def split_text(text: str) -> Tuple[str, str]:
    """兼容旧接口：返回 (主标题, 副标题)。"""
    rows = split_rows(text)
    if not rows:
        return "", ""
    if len(rows) == 1:
        return rows[0], ""
    return rows[0], "|".join(rows[1:])


# ---------------------------------------------------------------- 字号自适应

_REF_PX = 512                       # 参考渲染高度，用于取字体比例
_ratio_cache: Dict[Tuple[str, bool, str], Tuple[float, float]] = {}

# 定位点端头与刀口线之间留的安全距离（mm），避免像素取整时探进成品
TICK_CLEARANCE = 0.3


def _ink_rect(fm: QFontMetricsF, text: str) -> QRectF:
    """取文字**真实笔画**的外接框（相对基线原点），拿不到就退回行高框。

    用墨迹框而不是行高框，是为了让字真正"顶满"台签——行高框通常比墨迹
    高出 30% 以上（含上下留白），按行高框排版会让字明显偏小。
    """
    try:
        r = fm.tightBoundingRect(text)
        if r.isValid() and r.width() > 0.5 and r.height() > 0.5:
            return r
    except Exception:
        pass
    return fm.boundingRect(text)


def font_ratios(family: str, bold: bool, text: str) -> Tuple[float, float]:
    """返回 (墨迹宽/em, 墨迹高/em) 的无量纲比例，与设备无关。"""
    key = (family, bold, text)
    v = _ratio_cache.get(key)
    if v is None:
        f = QFont(family)
        f.setBold(bool(bold))
        f.setPixelSize(_REF_PX)
        fm = QFontMetricsF(f)
        br = _ink_rect(fm, text)
        v = (max(br.width(), 1.0) / _REF_PX, max(br.height(), 1.0) / _REF_PX)
        if len(_ratio_cache) > 4000:
            _ratio_cache.clear()
        _ratio_cache[key] = v
    return v


def fit_em_mm(family: str, bold: bool, text: str,
              avail_w_mm: float, avail_h_mm: float,
              safety: float = 0.985, max_em_mm: float | None = None) -> float:
    """在给定方框内求出能放下的最大字面高度(mm)——**单行**，不做折行。"""
    if not text or avail_w_mm <= 0 or avail_h_mm <= 0:
        return 0.0
    rw, rh = font_ratios(family, bold, text)
    em = min(avail_w_mm / rw, avail_h_mm / rh) * safety
    if max_em_mm is not None:
        em = min(em, max_em_mm)
    return max(0.5, em)


def em_mm_to_pt(em_mm: float) -> float:
    return em_mm / MM_PER_PT


def pt_to_em_mm(pt: float) -> float:
    return pt * MM_PER_PT


# ---------------------------------------------------------------- 多行折行排版

# 中文避头尾规则：这些标点不能出现在行首 / 行尾
_NO_LINE_START = set("、。，．·・；：？！）〕］｝〉》」』】〗〞,.;:!?)]}%‰℃…—～·")
_NO_LINE_END = set("（〔［｛〈《「『【〖‘“([{")
_ASCII_WORD = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
                  "0123456789._-@/'\"+&")


def _cuts_word(text: str, i: int) -> bool:
    """在 i 处断行会不会把一个西文单词/数字串劈成两半。"""
    if i <= 0 or i >= len(text):
        return False
    return text[i - 1] in _ASCII_WORD and text[i] in _ASCII_WORD


def _polish_cuts(text: str, cuts: Sequence[int]) -> List[int]:
    """把"理想均分断点"微调成合法断点（避头尾、不劈西文单词）。"""
    n = len(text)
    out: List[int] = []
    prev = 0
    for raw in cuts:
        c = max(prev + 1, min(int(raw), n - 1))
        guard = 0
        while c < n - 1 and (text[c] in _NO_LINE_START or _cuts_word(text, c)) and guard < 8:
            c += 1
            guard += 1
        guard = 0
        while c > prev + 1 and text[c - 1] in _NO_LINE_END and guard < 8:
            c -= 1
            guard += 1
        if c <= prev:
            c = min(n - 1, prev + 1)
        out.append(c)
        prev = c
    return out


def _split_balanced(text: str, k: int) -> List[str]:
    """把 text 尽量**等长**地劈成 k 行（含避头尾修正）。

    等长很重要：每行长度接近时，整块才能同时把宽度和高度填满，
    不会出现"最后一行只剩一个字"的难看情况。
    """
    n = len(text)
    if k <= 1:
        return [text] if text else []
    if k >= n:
        return list(text)
    base, extra = divmod(n, k)
    ideal: List[int] = []
    pos = 0
    for j in range(k - 1):
        pos += base + (1 if j < extra else 0)
        ideal.append(pos)
    lines: List[str] = []
    prev = 0
    for c in _polish_cuts(text, ideal):
        lines.append(text[prev:c])
        prev = c
    lines.append(text[prev:])
    return [ln for ln in lines if ln]


@dataclass
class TextBlock:
    """一段已经排好版的多行文字（几何量单位 mm）。"""

    lines: List[str] = field(default_factory=list)
    em_mm: float = 0.0           # 字面高度
    pitch_mm: float = 0.0        # 相邻两行的基线距离
    width_mm: float = 0.0        # 最宽一行的墨迹宽（**已含**横向拉伸）
    height_mm: float = 0.0       # 整块墨迹高（**已含**纵向拉伸）
    sx: float = 1.0              # 横向缩放倍率
    sy: float = 1.0              # 纵向缩放倍率

    @property
    def count(self) -> int:
        return len(self.lines)


def _block_shape(family: str, bold: bool, lines: Sequence[str],
                 pitch: float) -> Tuple[float, float, float]:
    """返回 (最宽行的 宽/em, 最高行的 高/em, 整块高/em)。"""
    rw = rh = 0.0
    for ln in lines:
        a, b = font_ratios(family, bold, ln)
        rw = max(rw, a)
        rh = max(rh, b)
    total = rh + max(0, len(lines) - 1) * pitch
    return max(rw, 1e-6), max(rh, 1e-6), max(total, 1e-6)


def fit_block(family: str, bold: bool, text: str,
              box_w_mm: float, box_h_mm: float, *,
              allow_wrap: bool = True, max_lines: int = MAX_WRAP_LINES,
              pitch: float = 1.05, safety: float = 0.985,
              max_em_mm: float | None = None,
              prefer_fill: float = 0.96,
              sx: float = 1.0, sy: float = 1.0) -> TextBlock:
    """把一段文字排进方框，返回"字最大、同时尽量铺满"的多行结果。

    `sx / sy` 是手动字形拉伸倍率：内部等效于把方框先缩成
    (box_w/sx, box_h/sy) 来求字号，绘制时再整体放大回来，
    所以拉伸后依然不会溢出方框；两者都是 1.0 时结果与原来完全一致。


    做法：分别试 1 行、2 行 …… n 行，每行都按**等长**劈分，算出各自的
    最大可能字号，然后
      1. 先在字号最大的几个候选里（≥ 最优字号 × prefer_fill）挑覆盖面积
         最大的——避免"字只大千分之几，却白白多折一行"；
      2. 面积相同时行数少的优先。
    例：8 个字在 142×72mm 里，单行只有 19mm，折成 4+4 两行能到 35mm。
    """
    text = (text or "").strip()
    if not text or box_w_mm <= 0 or box_h_mm <= 0:
        return TextBlock()
    sx = max(0.05, float(sx or 1.0))
    sy = max(0.05, float(sy or 1.0))
    eff_w = box_w_mm / sx       # 等效方框：拉伸后正好填回原方框
    eff_h = box_h_mm / sy

    kmax = min(max_lines, len(text)) if allow_wrap else 1
    cands: List[TextBlock] = []
    for k in range(1, kmax + 1):
        lines = _split_balanced(text, k)
        if not lines:
            continue
        rw, rh, a = _block_shape(family, bold, lines, pitch)
        em = min(eff_w / rw, eff_h / a) * safety
        if max_em_mm is not None:
            em = min(em, max_em_mm)
        if em <= 0:
            continue
        cands.append(TextBlock(list(lines), em, em * pitch,
                               em * rw * sx, em * a * sy, sx, sy))
    if not cands:
        return TextBlock()

    best_em = max(c.em_mm for c in cands)
    ok = [c for c in cands if c.em_mm >= best_em * prefer_fill]
    return max(ok, key=lambda c: (c.width_mm * c.height_mm, -c.count, c.em_mm))


def fixed_block(family: str, bold: bool, lines: Sequence[str],
                em_mm: float, pitch: float = 1.05,
                sx: float = 1.0, sy: float = 1.0,
                box_w_mm: float = 0.0, box_h_mm: float = 0.0) -> TextBlock:
    """按指定字号生成文字块（手动字号模式用，不做折行）。

    给了方框尺寸时会顺带保证拉伸后不溢出——手动字号本来就可能超出，
    加上拉伸更容易出界，所以这里统一收一下。
    """
    rows = [ln for ln in lines if ln]
    if not rows or em_mm <= 0:
        return TextBlock()
    sx = max(0.05, float(sx or 1.0))
    sy = max(0.05, float(sy or 1.0))
    rw, rh, a = _block_shape(family, bold, rows, pitch)
    em = em_mm
    if box_w_mm > 0 and rw * sx > 1e-9:
        em = min(em, box_w_mm / (rw * sx))
    if box_h_mm > 0 and a * sy > 1e-9:
        em = min(em, box_h_mm / (a * sy))
    return TextBlock(list(rows), em, em * pitch,
                     em * rw * sx, em * a * sy, sx, sy)


@dataclass
class StretchRow:
    """「拉伸铺满」模式里的一行：一行文字 + 它自己的横向缩放比例。"""

    text: str = ""
    em_mm: float = 0.0        # 等比基准字号（字面高）
    sx: float = 1.0           # 横向缩放：>1 拉宽，<1 压窄，用于把整行撑满宽度
    sy: float = 1.0           # 纵向缩放：手动滑块给的额外纵向拉伸
    cy_mm: float = 0.0        # 该行墨迹中心相对"可用方框顶部"的偏移
    width_mm: float = 0.0     # 拉伸后的墨迹宽（已含 sx）
    height_mm: float = 0.0    # 墨迹高（已含 sy）

    @property
    def capped(self) -> bool:
        """是否被拉伸/压缩上下限挡住了（没能真正撑满宽度）。"""
        return self.sx >= STRETCH_MAX - 1e-6


@dataclass
class PlateText:
    """一张台签的完整文字排版结果。

    两种形态二选一：
      · `rows` 非空 → 「拉伸铺满」模式，每段一行，每行自带横向缩放；
      · 否则        → 「折行铺满」模式，主标题块 +（可选）副标题块。
    """

    main: TextBlock = field(default_factory=TextBlock)
    subs: TextBlock = field(default_factory=TextBlock)
    gap_mm: float = 0.0
    rows: List[StretchRow] = field(default_factory=list)
    box_h_mm: float = 0.0     # 拉伸模式下的可用方框高（用于定位与自检）

    @property
    def stretched(self) -> bool:
        return bool(self.rows)

    @property
    def height_mm(self) -> float:
        if self.rows:
            return self.box_h_mm
        h = self.main.height_mm
        if self.subs.lines:
            h += self.gap_mm + self.subs.height_mm
        return h

    @property
    def em_mm(self) -> float:
        """代表字号：拉伸模式取最高那一行，折行模式取主标题。"""
        if self.rows:
            return max((r.em_mm for r in self.rows), default=0.0)
        return self.main.em_mm

    @property
    def line_count(self) -> int:
        if self.rows:
            return len(self.rows)
        return self.main.count + self.subs.count


def stretch_plate_text(family: str, bold: bool, text: str,
                       box_w_mm: float, box_h_mm: float,
                       ux: float = 1.0, uy: float = 1.0
                       ) -> List[StretchRow]:
    """「拉伸铺满」排版：每个 `|` 分段独占一行，永不折行。

    算法（对齐用户老工具的效果）：
      1. 行数 N = 段数，可用高度按 N 等分，**每行一样高**；
      2. 每行先用"行槽高"定出字号，再把整行**横向拉伸**到撑满可用宽度；
      3. 拉伸/压缩超过上下限时收住（`STRETCH_MIN/MAX`）——
         压得太狠时反过来缩小字号保住"撑满整宽"，拉得太狠时允许两侧留白；
      4. 最后再乘手动滑块 `ux`（横向）/ `uy`（纵向）。

    手动拉伸的两个方向各有各的效果，且**永远不溢出方框**：
      · `ux > 1` 想更宽 —— 宽度已经撑满了，于是改为压低字号 → 字更扁更宽；
      · `ux < 1` 想更瘦 —— 宽度按比例收窄，两侧留白，高度不变 → 字更瘦；
      · `uy > 1` 想更高 —— 高度已经顶到行槽了，于是改为压小字号 → 字更瘦更高；
      · `uy < 1` 想更矮 —— 高度按比例压低，上下留白，宽度仍撑满 → 字更扁。
    `ux = uy = 1.0` 时与不拉伸的结果逐毫米一致。
    """
    rows = [r for r in split_rows(text) if r.strip()]
    if not rows or box_w_mm <= 0 or box_h_mm <= 0:
        return []

    n = len(rows)
    slot = box_h_mm / n                    # 每行的行槽高
    ink_h = slot * STRETCH_ROW_FILL        # 行槽里实际用来放字的高度

    out: List[StretchRow] = []
    for i, t in enumerate(rows):
        rw, rh = font_ratios(family, bold, t)
        em = ink_h / rh                     # 先按行槽高定字号
        nat_w = em * rw                     # 该字号下这行天然有多宽
        auto_sx = (box_w_mm / nat_w) if nat_w > 1e-9 else 1.0
        if auto_sx < STRETCH_MIN:
            auto_sx = STRETCH_MIN           # 压得太狠：缩字号，保住"撑满整宽"
        elif auto_sx > STRETCH_MAX:
            auto_sx = STRETCH_MAX           # 拉得太狠：收住，两侧各留一点白
        sx = max(SX_ABS_MIN, min(SX_ABS_MAX, auto_sx * ux))
        # 兜底：横竖都不许溢出（墨迹宽 ≤ 可用宽，墨迹高 ≤ 行槽墨迹高）
        lim = em
        if rw * sx > 1e-9:
            lim = min(lim, box_w_mm / (rw * sx))
        if rh * uy > 1e-9:
            lim = min(lim, ink_h / (rh * uy))
        em = max(0.5, lim)
        out.append(StretchRow(
            text=t,
            em_mm=em,
            sx=sx,
            sy=uy,
            cy_mm=slot * (i + 0.5),
            width_mm=em * rw * sx,
            height_mm=em * rh * uy,
        ))
    return out


def stretch_pair(opt: "Options") -> Tuple[float, float]:
    """取手动拉伸倍率（横向, 纵向），并夹到滑块允许的范围内。

    1.00 / 1.00 表示"不动"，排版结果与不加拉伸时完全一致。
    """
    ux = float(getattr(opt, "stretch_x", 1.0) or 1.0)
    uy = float(getattr(opt, "stretch_y", 1.0) or 1.0)
    ux = max(STRETCH_X_RANGE[0], min(STRETCH_X_RANGE[1], ux))
    uy = max(STRETCH_Y_RANGE[0], min(STRETCH_Y_RANGE[1], uy))
    return ux, uy


def fit_mode_of(opt: "Options") -> str:
    """取填充方式，兼容旧配置里的 `auto_wrap` 布尔值。"""
    m = str(getattr(opt, "fit_mode", "") or "").strip().lower()
    if m in ("stretch", "wrap", "plain"):
        return m
    return "wrap" if getattr(opt, "auto_wrap", True) else "plain"


def layout_plate_text(family: str, bold: bool, text: str,
                      box_w_mm: float, box_h_mm: float,
                      opt: "Options") -> PlateText:
    """把一张台签的内容排进可用方框，按 `fit_mode` 分派：

    · **stretch**（默认，老工具效果）：每个 `|` 分段独占一行，行高均分，
      整行横向拉伸撑满宽度——字多字少都是一行，整张台签铺满；
    · **wrap**：自动折行，字形等比不变形，取能排下的最大字号；
    · **plain**：单行等比适配（仅按宽度定字号）。

    折行模式下若有副标题，按联立约束求解：主标题的字号要同时满足
      · 自身不超过可用宽度；
      · 与副标题（= 主标题 × subtitle_ratio）加起来不超过可用高度。
    """
    if box_w_mm <= 0 or box_h_mm <= 0:
        return PlateText()

    mode = fit_mode_of(opt)
    ux, uy = stretch_pair(opt)
    rows = split_rows(text)
    main_text = rows[0] if rows else ""
    sub_rows = [r for r in rows[1:]]
    pitch = max(0.8, float(opt.line_pitch))
    ratio = max(0.15, min(1.0, float(opt.subtitle_ratio)))

    # ---- 拉伸铺满：不折行，每段一行 ----
    if mode == "stretch" and opt.auto_size:
        st = stretch_plate_text(family, bold, text, box_w_mm, box_h_mm, ux, uy)
        if st:
            return PlateText(rows=st, box_h_mm=box_h_mm)

    allow_wrap = (mode == "wrap")

    # 手动字号：不折行，按给定字号直接排
    if not opt.auto_size:
        em = pt_to_em_mm(opt.manual_pt)
        return PlateText(
            fixed_block(family, bold, [main_text], em, pitch, ux, uy,
                        box_w_mm, box_h_mm),
            fixed_block(family, bold, sub_rows, em * ratio, pitch, ux, uy,
                        box_w_mm, box_h_mm),
            box_h_mm * 0.06 if sub_rows else 0.0)

    if not sub_rows:
        return PlateText(fit_block(family, bold, main_text, box_w_mm, box_h_mm,
                                   allow_wrap=allow_wrap, pitch=pitch,
                                   sx=ux, sy=uy))

    rw_s, rh_s, a_s = _block_shape(family, bold, sub_rows, pitch)
    gap = box_h_mm * 0.06
    # 等效方框：在这里求出的字号，拉伸后正好填回真实方框
    eff_w = box_w_mm / ux
    eff_h = box_h_mm / uy - gap
    kmax = min(MAX_WRAP_LINES, len(main_text)) if allow_wrap else 1
    best: PlateText | None = None
    for k in range(1, kmax + 1):
        lines = _split_balanced(main_text, k)
        if not lines:
            continue
        rw_m, rh_m, a_m = _block_shape(family, bold, lines, pitch)
        sub_em_limit = eff_w / rw_s          # 副标题被宽度卡住的字号
        em = min(eff_w / rw_m,
                 eff_h / (a_m + a_s * ratio)) * 0.985
        if em * ratio > sub_em_limit:
            # 副标题已顶到宽度上限，主标题按剩下的高度排队
            em = min(eff_w / rw_m,
                     (eff_h - a_s * sub_em_limit) / a_m) * 0.985
        if em <= 0:
            continue
        em_sub = min(em * ratio, sub_em_limit)
        cand = PlateText(
            TextBlock(list(lines), em, em * pitch,
                      em * rw_m * ux, em * a_m * uy, ux, uy),
            TextBlock(list(sub_rows), em_sub, em_sub * pitch,
                      em_sub * rw_s * ux, em_sub * a_s * uy, ux, uy),
            gap)
        if best is None or cand.main.em_mm > best.main.em_mm + 1e-9:
            best = cand
    return best if best is not None else PlateText()


# ---------------------------------------------------------------- 绘制

def make_font(family: str, bold: bool, em_px: float) -> QFont:
    f = QFont(family)
    f.setBold(bool(bold))
    f.setPixelSize(max(1, int(round(em_px))))
    f.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    f.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    return f


def draw_block_centered(painter: QPainter, block: TextBlock,
                        cx_mm: float, cy_mm: float,
                        kx: float, ky: float,
                        family: str, bold: bool, color: QColor) -> None:
    """把一个多行文字块整体居中。

    竖直方向按**整块墨迹**（首行顶端到末行底端）居中，而不是按行高框，
    这样上下留白才真正对称；水平方向每行各自居中。

    若 `block` 带手动拉伸倍率（sx / sy），这里用 `painter.scale` 做非等比
    缩放；因为字号是按"等效缩小后的方框"算出来的，放大回来正好不溢出。
    """
    if not block.lines or block.em_mm <= 0:
        return
    f = make_font(family, bold, block.em_mm * ky)
    fm = QFontMetricsF(f)
    pitch_px = block.pitch_mm * ky
    inks = [_ink_rect(fm, ln) for ln in block.lines]

    y_min = min(i * pitch_px + r.y() for i, r in enumerate(inks))
    y_max = max(i * pitch_px + r.y() + r.height() for i, r in enumerate(inks))

    painter.save()
    painter.translate(cx_mm * kx, cy_mm * ky)
    if abs(block.sx - 1.0) > 1e-6 or abs(block.sy - 1.0) > 1e-6:
        painter.scale(block.sx, block.sy)
    painter.setFont(f)
    painter.setPen(QPen(color))
    base0 = -(y_min + y_max) / 2.0
    for i, ln in enumerate(block.lines):
        r = inks[i]
        painter.drawText(QPointF(-(r.x() + r.width() / 2.0),
                                 base0 + i * pitch_px), ln)
    painter.restore()


def draw_text_centered(painter: QPainter, text: str, cx_mm: float, cy_mm: float,
                       box_w_mm: float, box_h_mm: float,
                       kx: float, ky: float,
                       family: str, bold: bool, em_mm: float, color: QColor) -> None:
    """单行文字按"墨迹外框"精确居中（保留给外部调用）。"""
    if not text or em_mm <= 0:
        return
    draw_block_centered(painter,
                        TextBlock([text], em_mm, em_mm, 0.0, 0.0),
                        cx_mm, cy_mm, kx, ky, family, bold, color)


def draw_stretch_rows(painter: QPainter, rows: Sequence[StretchRow],
                      bx_mm: float, by_mm: float, bw_mm: float,
                      kx: float, ky: float,
                      family: str, bold: bool, color: QColor) -> None:
    """画「拉伸铺满」的每一行：每行在方框里**左右撑满、行槽内竖直居中**。

    横向用 `painter.scale(sx, sy)` 做**非等比缩放**——这正是老工具那种
    "字多就压窄、字少就拉宽，总之把整行塞满"的效果，`sy` 则是手动滑块
    叠加上去的纵向拉伸。每行的墨迹中心严格落在自己行槽的中心。
    """
    if not rows:
        return
    cx_px = (bx_mm + bw_mm / 2.0) * kx
    painter.setPen(QPen(color))
    for row in rows:
        if not row.text or row.em_mm <= 0:
            continue
        f = make_font(family, bold, row.em_mm * ky)
        fm = QFontMetricsF(f)
        br = _ink_rect(fm, row.text)
        painter.save()
        painter.translate(cx_px, (by_mm + row.cy_mm) * ky)
        painter.scale(row.sx, row.sy)
        painter.setFont(f)
        # 局部坐标：让墨迹中心正好落在原点（= 行槽中心）
        painter.drawText(QPointF(-(br.x() + br.width() / 2.0),
                                 -(br.y() + br.height() / 2.0)), row.text)
        painter.restore()


def draw_plate_text(painter: QPainter, pt: PlateText,
                    bx_mm: float, by_mm: float, bw_mm: float, bh_mm: float,
                    kx: float, ky: float,
                    family: str, bold: bool, color: QColor) -> None:
    """把排版结果画进台签的可用方框。

    拉伸模式：行槽已经在方框里均分好，直接按方框定位；
    折行模式：整组内容在方框里**竖直居中**。
    """
    if pt.rows:
        draw_stretch_rows(painter, pt.rows, bx_mm, by_mm, bw_mm,
                          kx, ky, family, bold, color)
        return
    total = pt.height_mm
    if total <= 0:
        return
    top = by_mm + (bh_mm - total) / 2.0
    cx = bx_mm + bw_mm / 2.0
    h_main = pt.main.height_mm
    if pt.main.lines:
        draw_block_centered(painter, pt.main, cx, top + h_main / 2.0,
                            kx, ky, family, bold, color)
    if pt.subs.lines:
        cy_sub = top + h_main + pt.gap_mm + pt.subs.height_mm / 2.0
        draw_block_centered(painter, pt.subs, cx, cy_sub,
                            kx, ky, family, bold, color)


def _line(painter: QPainter, x1: float, y1: float, x2: float, y2: float,
          kx: float, ky: float) -> None:
    painter.drawLine(QPointF(x1 * kx, y1 * ky), QPointF(x2 * kx, y2 * ky))


def draw_corner_marks(painter: QPainter, x: float, y: float, w: float, h: float,
                      opt: Options, kx: float, ky: float, color: QColor) -> None:
    """在台签四个角的外侧画 L 形裁切角标（切纸时把角标切掉即可）。

    角标长度会自动收缩，避免相邻两张台签的角标在间距里打架。
    """
    o = opt.mark_offset_mm
    L = opt.mark_len_mm
    if opt.gap_mm > 0:
        L = min(L, max(0.8, opt.gap_mm / 2.0 - o - 0.4))
    lx, rx = x - o, x + w + o
    ty, by = y - o, y + h + o

    pen = QPen(color)
    pen.setWidthF(max(1.0, opt.mark_width_mm * kx))
    pen.setCapStyle(Qt.PenCapStyle.FlatCap)
    painter.setPen(pen)

    for cx_, cy_ in ((lx, ty), (rx, ty), (lx, by), (rx, by)):
        sx = 1 if cx_ == lx else -1     # 水平方向：向外
        sy = 1 if cy_ == ty else -1     # 垂直方向：向外
        _line(painter, cx_, cy_, cx_ + sx * L, cy_, kx, ky)
        _line(painter, cx_, cy_, cx_, cy_ + sy * L, kx, ky)


def draw_guide_lines(painter: QPainter, opt: Options,
                     page_w: float, page_h: float,
                     cols: int, rows: int,
                     kx: float, ky: float) -> None:
    """沿"下刀位置"画贯通整页的细虚线。

    切纸器沿着这条线切下去，线会被一分为二，留在台签边缘的只有不到
    0.1mm 的灰痕，肉眼基本看不出来；而边角料那一半随废纸一起丢掉。

    位置其实就是台签的右边界与下边界——包括最后一张台签右下角那条
    "切掉边角料"的分界线，所以画出来的线数量 == 实际下刀次数。
    """
    pen = QPen(QColor(146, 154, 168))
    lw_mm = 0.18
    px = max(1.0, lw_mm * kx)
    pen.setWidthF(px)
    pen.setCapStyle(Qt.PenCapStyle.FlatCap)
    pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
    pen.setStyle(Qt.PenStyle.CustomDashLine)
    # setDashPattern 的单位是"线宽的倍数"
    pen.setDashPattern([2.0 / lw_mm, 1.3 / lw_mm])
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    if opt.layout == "compact":
        xs, ys = cut_plan(page_w, page_h, opt, cols, rows)
        for x in xs:
            _line(painter, x, 0.0, x, page_h, kx, ky)
        for y in ys:
            _line(painter, 0.0, y, page_w, y, kx, ky)
        return

    # 居中排版没有"一刀到底"的切法，退化成每张台签一圈细边线
    for x, y in layout_positions(page_w, page_h, opt, cols, rows):
        painter.drawRect(QRectF(x * kx, y * ky,
                                opt.plate_w * kx, opt.plate_h * ky))


def _rect_is_scrap(x0: float, y0: float, x1: float, y1: float,
                   plates: Sequence[Tuple[float, float, float, float]],
                   eps: float = 0.05) -> bool:
    """矩形是否完全落在所有台签之外——也就是"会被切掉的废料"上。"""
    for px0, py0, px1, py1 in plates:
        if (x0 < px1 - eps and x1 > px0 + eps
                and y0 < py1 - eps and y1 > py0 + eps):
            return False
    return True


def tick_segments(pos: Sequence[Tuple[float, float]], opt: Options,
                  page_w: float, page_h: float, cols: int, rows: int
                  ) -> List[Tuple[float, float, float, float]]:
    """算出所有"废料区定位点"的线段 (x1, y1, x2, y2)，单位 mm。

    竖切线的两个定位点从刀口线向废料侧伸出，**端头正好落在刀口上**，
    分处纸张上下两端，两点连线即下刀线；横切线的定位点画成短竖线
    **跨在**刀口线上，中心即刀口高度。返回的每一段都保证完全位于会被
    切掉的废料里。
    """
    if opt.layout != "compact":
        return []
    xs, ys = cut_plan(page_w, page_h, opt, cols, rows)
    if not xs and not ys:
        return []

    plates = [(x, y, x + opt.plate_w, y + opt.plate_h) for x, y in pos]
    L = max(3.0, opt.tick_len_mm)
    half = L / 2.0
    w = opt.tick_width_mm / 2.0
    inset = opt.tick_inset_mm
    right_edge = max(x + opt.plate_w for x, _ in pos)
    out: List[Tuple[float, float, float, float]] = []

    # ---- 竖切线：端头式定位点，上下各一个 ----
    for x in xs:
        to_right = x + L <= page_w
        to_left = x - L >= 0.0
        if not (to_right or to_left):
            continue
        row_centers: List[float] = []
        for _, py in pos:
            cy = py + opt.plate_h / 2.0
            if all(abs(cy - v) > 1.0 for v in row_centers):
                row_centers.append(cy)
        picked: List[float] = []
        for cy in [inset, page_h - inset] + row_centers:
            if cy < 0.0 or cy > page_h:
                continue
            if any(abs(cy - p) < 6.0 for p in picked):
                continue
            if len(picked) >= 2:
                break
            # 起点从刀口线往废料侧退 TICK_CLEARANCE：刀口线本身在像素取整时
            # 会来回浮动，紧贴会让端头探进成品半个到一个像素。0.3mm 远小于
            # 手切的定位精度，对"端头即刀口"的判断没有实际影响。
            x1, x2 = (x + TICK_CLEARANCE, x + L) if to_right \
                else (x - L, x - TICK_CLEARANCE)
            if _rect_is_scrap(x1, cy - w, x2, cy + w, plates):
                out.append((x1, cy, x2, cy))
                picked.append(cy)

    # ---- 横切线：跨越式定位点，右侧废料里各两个 ----
    for y in ys:
        picked_x: List[float] = []
        for cx in (right_edge + 5.0, page_w - inset):
            if cx - w < 0.0 or cx + w > page_w:
                continue
            if any(abs(cx - p) < 8.0 for p in picked_x):
                continue
            if len(picked_x) >= 2:
                break
            if _rect_is_scrap(cx - w, y - half, cx + w, y + half, plates):
                out.append((cx, y - half, cx, y + half))
                picked_x.append(cx)

    return out


def draw_tick_marks(painter: QPainter, pos: Sequence[Tuple[float, float]],
                    opt: Options, page_w: float, page_h: float,
                    cols: int, rows: int, kx: float, ky: float) -> None:
    """在**废料区**画极短的实线定位点。

    与贯通虚线相比的好处：定位点整体落在会被切掉的那部分纸上，成品台签
    上不会留下任何印刷痕迹——哪怕刀走得偏一点也不会。
    """
    if opt.layout != "compact":
        # 居中排版四周本来就有留白，直接退回四角角标
        for x, y in pos:
            draw_corner_marks(painter, x, y, opt.plate_w, opt.plate_h,
                              opt, kx, ky, QColor(0, 0, 0))
        return

    segs = tick_segments(pos, opt, page_w, page_h, cols, rows)
    if not segs:
        return

    pen = QPen(QColor(126, 134, 150))
    pen.setWidthF(max(1.0, opt.tick_width_mm * kx))
    pen.setCapStyle(Qt.PenCapStyle.FlatCap)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    for x1, y1, x2, y2 in segs:
        _line(painter, x1, y1, x2, y2, kx, ky)


def plate_ink_box(x: float, y: float, opt: Options, text: str
                  ) -> Tuple[float, float, float, float]:
    """算出某张台签里文字的实际墨迹外接框 (x0, y0, x1, y1)，单位 mm。

    仅用于自检：拿它和渲染出的像素去比对，验证"铺满"和"居中"。
    """
    w, h = opt.plate_w, opt.plate_h
    pad = min(opt.padding_mm, w / 4.0, h / 4.0)
    bx, by = x + pad, y + pad
    bw, bh = w - 2 * pad, h - 2 * pad
    pt = layout_plate_text(opt.font_family, opt.bold, text, bw, bh, opt)
    if pt.rows:
        cx = bx + bw / 2.0
        w = max((r.width_mm for r in pt.rows), default=0.0)
        y0 = by + min(r.cy_mm - r.height_mm / 2.0 for r in pt.rows)
        y1 = by + max(r.cy_mm + r.height_mm / 2.0 for r in pt.rows)
        if w <= 0:
            return (cx, by + bh / 2, cx, by + bh / 2)
        return (cx - w / 2.0, y0, cx + w / 2.0, y1)
    total = pt.height_mm
    if total <= 0:
        return (bx + bw / 2, by + bh / 2, bx + bw / 2, by + bh / 2)
    top = by + (bh - total) / 2.0
    cx = bx + bw / 2.0
    x0 = cx - pt.main.width_mm / 2.0
    x1 = cx + pt.main.width_mm / 2.0
    for b in (pt.subs,):
        if b.lines:
            x0 = min(x0, cx - b.width_mm / 2.0)
            x1 = max(x1, cx + b.width_mm / 2.0)
    return (x0, top, x1, top + total)


def draw_plate(painter: QPainter, x: float, y: float, opt: Options, text: str,
               kx: float, ky: float,
               report: list | None = None) -> float:
    """画一张台签，返回主标题实际用到的字面高度(mm)。"""
    w, h = opt.plate_w, opt.plate_h
    invert = bool(opt.invert)
    fg = QColor(255, 255, 255) if invert else QColor(0, 0, 0)

    if invert:
        painter.fillRect(QRectF(x * kx, y * ky, w * kx, h * ky), QColor(0, 0, 0))
    elif opt.marks in ("guide", "box"):
        # 白底必须在"标记之后、文字之前"补上：标记压在台签范围内的部分
        # 会被遮掉，成品边缘就只剩刀口切掉的那半边。
        painter.fillRect(QRectF(x * kx, y * ky, w * kx, h * ky),
                         QColor(255, 255, 255))

    if opt.marks == "box":
        pen = QPen(fg)
        pen.setWidthF(max(1.0, opt.mark_width_mm * kx))
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(x * kx, y * ky, w * kx, h * ky))

    pad = min(opt.padding_mm, w / 4.0, h / 4.0)
    bx, by = x + pad, y + pad
    bw, bh = w - 2 * pad, h - 2 * pad

    pt = layout_plate_text(opt.font_family, opt.bold, text, bw, bh, opt)
    draw_plate_text(painter, pt, bx, by, bw, bh, kx, ky,
                    opt.font_family, opt.bold, fg)
    used_em = pt.em_mm

    if opt.marks == "corner":
        # 角标画在台签外侧的留白区域，必须始终用黑色，否则黑底模式下看不见
        draw_corner_marks(painter, x, y, w, h, opt, kx, ky, QColor(0, 0, 0))

    if report is not None:
        report.append(used_em)
    return used_em


def render_page(painter: QPainter, names: Sequence[str], opt: Options,
                page_w: float, page_h: float, kx: float, ky: float,
                report: list | None = None) -> None:
    """把一页内容画到 painter 上（painter 已按 kx/ky 换算成毫米坐标系）。"""
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

    cols, rows = layout_count(page_w, page_h, opt)
    if cols == 0 or rows == 0:
        return

    pos = layout_positions(page_w, page_h, opt, cols, rows)

    # 标记先画：虚线落在台签范围内的部分会被随后的台签白底遮住，
    # 定位点则本来就整条位于废料里。
    if opt.marks == "guide":
        draw_guide_lines(painter, opt, page_w, page_h, cols, rows, kx, ky)
    elif opt.marks == "tick":
        draw_tick_marks(painter, pos, opt, page_w, page_h, cols, rows, kx, ky)

    for i, name in enumerate(names):
        if i >= len(pos):
            break
        px, py = pos[i]
        draw_plate(painter, px, py, opt, name, kx, ky, report)
