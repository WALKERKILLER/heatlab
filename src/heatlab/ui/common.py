"""Shared Qt and Matplotlib widgets (VS Code Dark+ workbench chrome)."""

from __future__ import annotations

import sys
import warnings
from collections.abc import Callable
from pathlib import Path

import matplotlib as mpl
from matplotlib import font_manager as _font_manager
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from heatlab.constants import DEFAULT_SEED
from heatlab.ui.style import STATUS_ERROR, STATUS_LIVE, STATUS_PAUSED


def _candidate_font_paths() -> list[Path]:
    """Return font files bundled with the app, then system fallbacks.

    The bundled Droid Sans Fallback ships with the project (and inside the
    PyInstaller bundle on Windows), so the desktop app never depends on the
    host system having a CJK font installed.
    """
    candidates: list[Path] = []
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        bundle_root = Path(sys._MEIPASS)
        candidates.append(bundle_root / "heatlab" / "web" / "static" / "fonts" / "DroidSansFallback.ttf")
        candidates.append(bundle_root / "src" / "heatlab" / "web" / "static" / "fonts" / "DroidSansFallback.ttf")
    candidates.append(Path(__file__).resolve().parent.parent / "web" / "static" / "fonts" / "DroidSansFallback.ttf")
    candidates.extend(
        [
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"),
        ]
    )
    return [path for path in candidates if path.exists()]


# matplotlib's font cache does not index every TTC face, so register the
# bundled/system CJK faces explicitly. The first registered font wins.
for _font_path in _candidate_font_paths():
    try:
        _font_manager.fontManager.addfont(str(_font_path))
    except Exception:
        continue

# Per-glyph fallback intentionally splits CJK (Droid/Noto) and Latin (DejaVu);
# the resulting "Glyph missing" notices are expected noise, not errors.
warnings.filterwarnings("ignore", message=r"Glyph .* missing from font", category=UserWarning)

# Matplotlib picks the FIRST existing family and then does NOT fall back per
# glyph, so the chosen font must cover CJK + Latin together. Order matters:
# Windows ships Microsoft YaHei/SimHei; Linux ships Noto (registered above);
# the bundled Droid Sans Fallback covers CJK as a last resort; DejaVu must
# stay last (Latin-only, would render CJK as tofu boxes if chosen first).
mpl.rcParams["font.sans-serif"] = [
    "Microsoft YaHei",
    "SimHei",
    "Noto Sans CJK SC",
    "Noto Sans CJK JP",
    "Droid Sans Fallback",
    "AR PL UMing CN",
    "DejaVu Sans",
]
mpl.rcParams["axes.unicode_minus"] = False

# VS Code Dark+ 表面色
BG = "#1e1e1e"
PANEL = "#252526"
GRID = "#3e3e42"
TEXT = "#cccccc"
MUTED = "#9d9d9d"
ACCENT = "#3794ff"
ACCENT_2 = "#dcdcaa"
ACCENT_3 = "#c586c0"

# Matplotlib defaults to near-black text; force light copy on the dark canvas so
# titles, axis labels, tick labels, and legend entries stay readable.
mpl.rcParams.update(
    {
        "text.color": TEXT,
        "axes.labelcolor": TEXT,
        "axes.titlecolor": TEXT,
        "axes.edgecolor": GRID,
        "axes.facecolor": BG,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "figure.facecolor": BG,
        "figure.edgecolor": BG,
        "savefig.facecolor": BG,
        "grid.color": GRID,
        "legend.facecolor": PANEL,
        "legend.edgecolor": GRID,
        "legend.labelcolor": TEXT,
        "legend.framealpha": 0.92,
    }
)


class MplCanvas(FigureCanvasQTAgg):
    def __init__(self, parent: QWidget | None = None, *, width: float = 5, height: float = 5):
        figure = Figure(figsize=(width, height), tight_layout=True)
        figure.patch.set_facecolor(BG)
        super().__init__(figure)
        self.setParent(parent)


def style_axes(axis, *, grid: bool = True) -> None:
    axis.set_facecolor(BG)
    axis.tick_params(colors=MUTED)
    axis.xaxis.label.set_color(TEXT)
    axis.yaxis.label.set_color(TEXT)
    axis.title.set_color(TEXT)
    for spine in axis.spines.values():
        spine.set_color(GRID)
    if grid:
        axis.grid(True, color=GRID, alpha=0.5, linewidth=0.7)
    legend = axis.get_legend()
    if legend is not None:
        style_legend(legend)


def style_legend(legend) -> None:
    """Keep legend labels readable on the dark figure background."""
    if legend is None:
        return
    legend.get_frame().set_facecolor(PANEL)
    legend.get_frame().set_edgecolor(GRID)
    legend.get_frame().set_alpha(0.92)
    for text_artist in legend.get_texts():
        text_artist.set_color("#ffffff")
        text_artist.set_fontsize(11)
    title_artist = legend.get_title()
    if title_artist is not None:
        title_artist.set_color("#ffffff")


def style_3d_axes(axis) -> None:
    """Apply the same light-on-dark treatment to a Matplotlib 3D axes."""
    axis.set_facecolor(BG)
    axis.tick_params(colors=MUTED)
    axis.title.set_color(TEXT)
    for axis_plane in (axis.xaxis, axis.yaxis, axis.zaxis):
        axis_plane.label.set_color(TEXT)
        axis_plane.pane.set_facecolor(BG)
        axis_plane.pane.set_edgecolor(GRID)
    axis.grid(True, color=GRID, alpha=0.35)


class LabeledSlider(QWidget):
    valueChanged = Signal(float)

    def __init__(
        self,
        title: str,
        minimum: int,
        maximum: int,
        value: int,
        *,
        transform: Callable[[int], float] = float,
        formatter: Callable[[float], str] = lambda x: f"{x:g}",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._transform = transform
        self._formatter = formatter

        title_label = QLabel(title)
        self.value_label = QLabel()
        self.value_label.setObjectName("valueLabel")
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(minimum, maximum)
        self.slider.setValue(value)
        self.slider.setTracking(True)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.addWidget(title_label)
        top.addStretch(1)
        top.addWidget(self.value_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addLayout(top)
        layout.addWidget(self.slider)

        self.slider.valueChanged.connect(self._emit_value)
        self._emit_value(value)

    @property
    def value(self) -> float:
        return self._transform(self.slider.value())

    def set_value(self, value: float) -> None:
        """Set the raw slider position from a transformed value (no signal loop)."""
        raw = self.slider.minimum() + round(
            (value - self._transform(self.slider.minimum()))
            / max(self._transform(self.slider.maximum()) - self._transform(self.slider.minimum()), 1e-9)
            * (self.slider.maximum() - self.slider.minimum())
        )
        raw = int(np_clamp(raw, self.slider.minimum(), self.slider.maximum()))
        if raw != self.slider.value():
            self.slider.blockSignals(True)
            self.slider.setValue(raw)
            self.slider.blockSignals(False)
            self.value_label.setText(self._formatter(self._transform(raw)))

    def _emit_value(self, raw: int) -> None:
        value = self._transform(raw)
        self.value_label.setText(self._formatter(value))
        self.valueChanged.emit(value)


def np_clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


class ControlPanel(QFrame):
    def __init__(self, title: str, lead: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("controlPanel")
        self.layout_box = QVBoxLayout(self)
        self.layout_box.setContentsMargins(16, 14, 16, 14)
        self.layout_box.setSpacing(12)
        kicker = QLabel("参数")
        kicker.setObjectName("panelKicker")
        heading = QLabel(title)
        heading.setObjectName("panelHeading")
        self.layout_box.addWidget(kicker)
        self.layout_box.addWidget(heading)
        if lead:
            lead_label = QLabel(lead)
            lead_label.setObjectName("panelLead")
            lead_label.setWordWrap(True)
            self.layout_box.addWidget(lead_label)

    def add(self, widget: QWidget) -> None:
        self.layout_box.addWidget(widget)

    def finish(self) -> None:
        self.layout_box.addStretch(1)


class ButtonRow(QWidget):
    def __init__(self, *buttons: QPushButton, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        for button in buttons:
            layout.addWidget(button)


class MetricRow(QWidget):
    """一行只读指标（对齐 Web 的 metric-item：键左值右）。"""

    def __init__(self, key: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.key_label = QLabel(key)
        self.key_label.setObjectName("metricKey")
        self.value_label = QLabel("—")
        self.value_label.setObjectName("metricValue")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(10)
        layout.addWidget(self.key_label)
        layout.addStretch(1)
        layout.addWidget(self.value_label)

    def set_value(self, text: str) -> None:
        self.value_label.setText(text)


class MetricGrid(QFrame):
    """对齐 Web metrics 属性网格的只读指标卡片。"""

    def __init__(self, *keys: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("metricGrid")
        self._rows: list[MetricRow] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        for key in keys:
            row = MetricRow(key)
            self._rows.append(row)
            layout.addWidget(row)

    def set_values(self, values: dict[str, str] | None) -> None:
        for row in self._rows:
            text = values.get(row.key_label.text()) if values else "—"
            row.set_value(text if text is not None else "—")


class PanelCard(QFrame):
    """带标题栏 chrome 的场景 / 图表卡片（对齐 Web 的 stage-card）。"""

    def __init__(self, title: str, badge: str, content: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sceneCard" if badge == "场景" else "chartCard")

        chrome = QWidget()
        chrome.setObjectName("cardChrome")
        chrome_layout = QHBoxLayout(chrome)
        chrome_layout.setContentsMargins(10, 4, 10, 4)
        chrome_layout.setSpacing(8)
        title_label = QLabel(title)
        title_label.setObjectName("cardTitle")
        badge_label = QLabel(badge)
        badge_label.setObjectName("cardBadge")
        chrome_layout.addWidget(title_label)
        chrome_layout.addStretch(1)
        chrome_layout.addWidget(badge_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(chrome)
        layout.addWidget(content, 1)


class WorkbenchPanel(QWidget):
    """「参数 | 场景 | 图表」三栏工作台，对齐 Web 的 layout。"""

    def __init__(
        self,
        control: QWidget,
        scene_title: str,
        scene: QWidget,
        chart_title: str,
        chart: QWidget,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        control.setFixedWidth(300)
        layout.addWidget(control)
        layout.addWidget(PanelCard(scene_title, "场景", scene), 1)
        layout.addWidget(PanelCard(chart_title, "图表", chart), 1)


class TopBar(QWidget):
    """VS Code 风格顶栏：品牌 + 命令托盘（种子）+ 运行簇（状态与暂停）。"""

    seedApplied = Signal(int)
    pauseToggled = Signal(bool)

    def __init__(self, default_seed: int = DEFAULT_SEED, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("topBar")
        self.setFixedHeight(46)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 7, 14, 7)
        layout.setSpacing(12)
        layout.addWidget(self._build_brand())
        layout.addStretch(1)
        layout.addWidget(self._build_command_tray(default_seed))
        layout.addWidget(self._build_run_cluster())

    def _build_brand(self) -> QWidget:
        brand = QWidget()
        brand_layout = QHBoxLayout(brand)
        brand_layout.setContentsMargins(0, 0, 0, 0)
        brand_layout.setSpacing(8)

        mark = QLabel("热")
        mark.setFixedSize(28, 28)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setStyleSheet(
            "background:#2a2a2e;color:#ff9f43;border:1px solid rgba(255,107,61,80%);"
            "border-radius:8px;font-size:14px;font-weight:700;"
        )

        copy = QWidget()
        copy_layout = QVBoxLayout(copy)
        copy_layout.setContentsMargins(0, 0, 0, 0)
        copy_layout.setSpacing(1)
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(6)
        name = QLabel("HeatLab")
        name.setObjectName("brandName")
        divider = QLabel("·")
        divider.setObjectName("brandDivider")
        product = QLabel("WORKBENCH")
        product.setObjectName("brandProduct")
        title_row.addWidget(name)
        title_row.addWidget(divider)
        title_row.addWidget(product)
        title_row.addStretch(1)
        sub = QLabel("热学科学计算 · 实时实验台")
        sub.setObjectName("brandSub")
        copy_layout.addLayout(title_row)
        copy_layout.addWidget(sub)

        brand_layout.addWidget(mark)
        brand_layout.addWidget(copy)
        return brand

    def _build_command_tray(self, default_seed: int) -> QWidget:
        self.command_tray = QWidget()
        self.command_tray.setObjectName("commandTray")
        layout = QHBoxLayout(self.command_tray)
        layout.setContentsMargins(8, 4, 6, 4)
        layout.setSpacing(6)

        seed_label = QLabel("种子")
        seed_label.setObjectName("trayLabel")
        self.seed_spin = QSpinBox()
        self.seed_spin.setObjectName("seedSpin")
        self.seed_spin.setRange(0, 2_147_483_647)
        self.seed_spin.setValue(default_seed)
        apply_button = QPushButton("应用并重置")
        apply_button.setObjectName("applyButton")
        apply_button.clicked.connect(lambda: self.seedApplied.emit(self.seed_spin.value()))

        layout.addWidget(seed_label)
        layout.addWidget(self.seed_spin)
        layout.addWidget(apply_button)
        return self.command_tray

    def _build_run_cluster(self) -> QWidget:
        self.run_cluster = QWidget()
        self.run_cluster.setObjectName("runCluster")
        layout = QHBoxLayout(self.run_cluster)
        layout.setContentsMargins(10, 4, 6, 4)
        layout.setSpacing(8)

        meter = QWidget()
        meter_layout = QVBoxLayout(meter)
        meter_layout.setContentsMargins(0, 0, 0, 0)
        meter_layout.setSpacing(1)
        kicker = QLabel("SESSION")
        kicker.setObjectName("runKicker")
        self.run_state = QLabel("实时中")
        self.run_state.setObjectName("runState")
        meter_layout.addWidget(kicker)
        meter_layout.addWidget(self.run_state)

        self.pause_button = QPushButton("暂停")
        self.pause_button.setObjectName("transportButton")
        self.pause_button.setCheckable(True)
        self.pause_button.clicked.connect(self._on_pause_toggled)

        layout.addWidget(meter)
        layout.addWidget(self.pause_button)
        return self.run_cluster

    def _on_pause_toggled(self, paused: bool) -> None:
        self.pause_button.setText("继续" if paused else "暂停")
        self.set_state(STATUS_PAUSED if paused else STATUS_LIVE)
        self.pauseToggled.emit(paused)

    def set_state(self, state: str) -> None:
        """更新运行簇状态：live / paused / error。"""
        self.run_cluster.setProperty("paused", "true" if state == STATUS_PAUSED else "false")
        self.run_cluster.setProperty("error", "true" if state == STATUS_ERROR else "false")
        if state == STATUS_PAUSED:
            self.run_state.setText("已暂停")
        elif state == STATUS_ERROR:
            self.run_state.setText("故障")
        else:
            self.run_state.setText("实时中")
        self._repolish(self.run_cluster)

    def seed_value(self) -> int:
        return self.seed_spin.value()

    def set_pause_button(self, paused: bool) -> None:
        self.pause_button.blockSignals(True)
        self.pause_button.setChecked(paused)
        self.pause_button.setText("继续" if paused else "暂停")
        self.pause_button.blockSignals(False)

    @staticmethod
    def _repolish(widget: QWidget) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)


class StatusBar(QWidget):
    """底部状态栏：状态 + 当前专题 + 种子 + 运行态。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("statusBar")
        self.setFixedHeight(26)

        self.state_label = QLabel("动画实时运行中")
        self.state_label.setObjectName("statusItem")
        self.topic_label = QLabel("")
        self.topic_label.setObjectName("statusItem")
        self.seed_label = QLabel("")
        self.seed_label.setObjectName("statusMono")
        self.run_label = QLabel("实时")
        self.run_label.setObjectName("statusMono")

        left = QHBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(12)
        dot = QLabel("●")
        dot.setObjectName("statusItem")
        left.addWidget(dot)
        left.addWidget(self.state_label)
        left.addWidget(self.topic_label)
        left.addStretch(1)

        right = QHBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(16)
        right.addWidget(self.seed_label)
        right.addWidget(self.run_label)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 3, 12, 3)
        layout.addLayout(left)
        layout.addLayout(right)

    def set_state(self, state: str, text: str) -> None:
        self.state_label.setText(text)
        self.setProperty("paused", "true" if state == STATUS_PAUSED else "false")
        self.setProperty("error", "true" if state == STATUS_ERROR else "false")
        self._repolish(self)

    def set_topic(self, text: str) -> None:
        self.topic_label.setText(text)

    def set_seed(self, seed: int) -> None:
        self.seed_label.setText(f"种子 {seed}")

    def set_running(self, paused: bool) -> None:
        self.run_label.setText("已暂停" if paused else "实时")

    @staticmethod
    def _repolish(widget: QWidget) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)
