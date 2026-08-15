"""Galton-board Monte-Carlo tab: peg-board scene + probability chart."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

from heatlab.models.galton import GaltonBatch, GaltonModel
from heatlab.ui.common import (
    ACCENT,
    ACCENT_3,
    ControlPanel,
    LabeledSlider,
    MetricGrid,
    MplCanvas,
    WorkbenchPanel,
    style_axes,
    style_legend,
)

_MARBLE_FACE = "#5aa0f0"
_MARBLE_EDGE = "#2f5f9e"
_MARBLE_HIGHLIGHT = "#d6ecff"
_PEG_FACE = "#b6c2d4"
_PEG_EDGE = "#5a6577"
_SLOT_DIVIDER = "#aa966e"


class GaltonTab(QWidget):
    def __init__(self, model: GaltonModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.model = model
        self.batch: GaltonBatch | None = None
        self.animation_row = 0

        # ---- 场景：钉板 + 狭槽 + 粒子下落 ----
        self.scene_canvas = MplCanvas(self, width=5, height=5)
        self.ax_board = self.scene_canvas.figure.add_subplot(111)
        style_axes(self.ax_board, grid=False)
        self._draw_pegs_and_slots()
        self.particle_scatter = self.ax_board.scatter([], [], s=40, c=_MARBLE_FACE,
                                                      edgecolors=_MARBLE_EDGE, zorder=4)
        self.particle_highlight = self.ax_board.scatter([], [], s=12, c=_MARBLE_HIGHLIGHT,
                                                        edgecolors="none", zorder=5)
        self.bin_scatter: list = []
        self.trail_lines: list = []

        # ---- 图表：槽位概率分布 ----
        self.chart_canvas = MplCanvas(self, width=5, height=5)
        self.ax_hist = self.chart_canvas.figure.add_subplot(111)
        style_axes(self.ax_hist)
        bins = np.arange(self.model.params.rows + 1)
        self.bars = self.ax_hist.bar(bins, np.zeros_like(bins, dtype=float), color=ACCENT_3, alpha=0.55)
        self.theory_line, = self.ax_hist.plot(
            bins, np.zeros_like(bins, dtype=float), "o-", color=ACCENT, label="二项分布理论"
        )
        self.ax_hist.set_xlabel("落入位置 k（向右次数）")
        self.ax_hist.set_ylabel("概率")
        self.ax_hist.set_ylim(0, 0.35)
        style_legend(self.ax_hist.legend(loc="upper right"))

        # ---- 控制面板 ----
        panel = ControlPanel("伽尔顿板", lead="粒子逐层下落，槽位分布逼近二项分布（蒙特卡洛）。")
        self.particle_count = LabeledSlider(
            "粒子数 N", 1, 100, 50, formatter=lambda v: f"{int(v)}"
        )
        panel.add(self.particle_count)
        self.run_button = QPushButton("投放粒子")
        self.run_button.setObjectName("primaryButton")
        self.run_button.clicked.connect(self.start_drop)
        panel.add(self.run_button)

        self.metrics = MetricGrid("样本数", "均值", "方差", "层")
        panel.add(self.metrics)
        panel.finish()

        self.workbench = WorkbenchPanel(
            panel, "伽尔顿板下落", self.scene_canvas, "槽位概率分布", self.chart_canvas
        )
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.workbench)

        self.timer = QTimer(self)
        self.timer.setInterval(90)
        self.timer.timeout.connect(self._animate)
        self.start_drop()

    def _draw_pegs_and_slots(self) -> None:
        """金属铁钉 + 底部狭槽分隔板（对齐 Web 端的主流 bean machine 视觉）。"""

        rows = self.model.params.rows
        peg_x: list[float] = []
        peg_y: list[float] = []
        for row in range(rows):
            xs = np.arange(-row, row + 1, 2)
            peg_x.extend(xs.tolist())
            peg_y.extend((-np.ones_like(xs) * (row + 0.5)).tolist())
        self.ax_board.scatter(peg_x, peg_y, s=42, c=_PEG_FACE, edgecolors=_PEG_EDGE,
                              linewidths=0.6, zorder=3)
        # 顶部漏斗示意
        self.ax_board.plot([-2.4, 0.0, 2.4], [1.0, 0.25, 1.0], color=_PEG_EDGE, linewidth=1.5)
        # 底部狭槽分隔板
        for k in range(rows + 1):
            x = -rows + k * 2.0
            self.ax_board.plot([x, x], [-rows - 0.15, -rows - 2.1], color=_SLOT_DIVIDER,
                               linewidth=1.6, zorder=3)
        self.ax_board.set_xlim(-rows - 1.2, rows + 1.2)
        self.ax_board.set_ylim(-rows - 2.2, 1.2)
        self.ax_board.set_aspect("equal", adjustable="box")
        self.ax_board.set_title("粒子下落路径")
        self.ax_board.set_xlabel("水平位置")
        self.ax_board.set_ylabel("钉板层数")

    def start_drop(self) -> None:
        self.batch = self.model.simulate(int(self.particle_count.value))
        self.animation_row = 0
        for line in self.trail_lines:
            line.remove()
        self.trail_lines.clear()
        for scatter in self.bin_scatter:
            scatter.remove()
        self.bin_scatter.clear()
        start = np.column_stack((np.zeros(len(self.batch.paths)), np.zeros(len(self.batch.paths))))
        self.particle_scatter.set_offsets(start)
        self.particle_highlight.set_offsets(start)
        self.run_button.setEnabled(False)
        self.metrics.set_values({"样本数": "正在投放……"})
        self.timer.start()

    def set_animation_paused(self, paused: bool) -> None:
        if paused:
            self.timer.stop()
        elif self.batch is not None and self.animation_row <= self.model.params.rows:
            self.timer.start()

    def _animate(self) -> None:
        assert self.batch is not None
        rows = self.model.params.rows
        row = min(self.animation_row, rows)
        x = self.batch.paths[:, row]
        y = -np.full_like(x, row, dtype=float)
        offsets = np.column_stack((x, y))
        self.particle_scatter.set_offsets(offsets)
        self.particle_highlight.set_offsets(offsets + np.array([0.28, 0.28]))
        self.animation_row += 1
        if self.animation_row > rows:
            self.timer.stop()
            self._finish_batch()
        self.scene_canvas.draw_idle()

    def _finish_batch(self) -> None:
        assert self.batch is not None
        rows = self.model.params.rows
        y = -np.arange(rows + 1)
        for path in self.batch.paths:
            line, = self.ax_board.plot(path, y, color=ACCENT_3, alpha=0.10, linewidth=0.8)
            self.trail_lines.append(line)
        # 狭槽内 hexagonal 堆积粒子（对齐开源 bean machine 的落槽呈现）
        ball_r = 0.28
        slot_bottom = -rows - 1.9
        for k in range(rows + 1):
            count = int(self.batch.counts[k])
            placed = 0
            layer = 0
            while placed < count:
                row_count = min(3, count - placed)
                x_offset = (3 - row_count) / 2
                for j in range(row_count):
                    bx = (-rows + k * 2.0) + (j + x_offset - 1.0) * ball_r * 1.7
                    by = slot_bottom + layer * ball_r * 1.5
                    scatter = self.ax_board.scatter(
                        [bx], [by], s=26, c=_MARBLE_FACE, edgecolors=_MARBLE_EDGE,
                        linewidths=0.5, zorder=4,
                    )
                    self.bin_scatter.append(scatter)
                    hl = self.ax_board.scatter(
                        [bx + 0.12], [by + 0.12], s=7, c=_MARBLE_HIGHLIGHT,
                        edgecolors="none", zorder=5,
                    )
                    self.bin_scatter.append(hl)
                placed += row_count
                layer += 1
                if layer > 30:
                    break
        for patch, probability in zip(self.bars, self.batch.probabilities, strict=True):
            patch.set_height(float(probability))
        bins = np.arange(rows + 1)
        self.theory_line.set_data(bins, self.batch.theoretical)
        ymax = max(0.12, float(max(self.batch.probabilities.max(), self.batch.theoretical.max())) * 1.25)
        self.ax_hist.set_ylim(0, ymax)
        sample_mean = float(np.average(bins, weights=self.batch.counts))
        sample_var = float(np.average((bins - sample_mean) ** 2, weights=self.batch.counts))
        self.metrics.set_values({
            "样本数": str(int(self.batch.counts.sum())),
            "均值": f"{sample_mean:.3f}（理论 6.000）",
            "方差": f"{sample_var:.3f}（理论 3.000）",
            "层": f"{rows} / {rows}",
        })
        self.run_button.setEnabled(True)
        self.chart_canvas.draw_idle()
