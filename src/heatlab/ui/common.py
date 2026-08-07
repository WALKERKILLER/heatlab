"""Shared Qt and Matplotlib widgets."""

from __future__ import annotations

import os
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
    QVBoxLayout,
    QWidget,
)


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

BG = "#0b0f14"
PANEL = "#111821"
GRID = "#263241"
TEXT = "#dbe7f3"
MUTED = "#8ea1b5"
ACCENT = "#43d7c5"
ACCENT_2 = "#ff6b7a"
ACCENT_3 = "#65a7ff"

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
    def __init__(self, parent: QWidget | None = None, *, width: float = 9, height: float = 5):
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

    def _emit_value(self, raw: int) -> None:
        value = self._transform(raw)
        self.value_label.setText(self._formatter(value))
        self.valueChanged.emit(value)


class ControlPanel(QFrame):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("controlPanel")
        self.layout_box = QVBoxLayout(self)
        self.layout_box.setContentsMargins(18, 18, 18, 18)
        self.layout_box.setSpacing(15)
        heading = QLabel(title)
        heading.setObjectName("panelHeading")
        self.layout_box.addWidget(heading)

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
