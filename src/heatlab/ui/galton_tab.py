"""Galton-board Monte-Carlo tab."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from heatlab.models.galton import GaltonBatch, GaltonModel
from heatlab.ui.common import (
    ACCENT,
    ACCENT_2,
    ACCENT_3,
    ControlPanel,
    LabeledSlider,
    MplCanvas,
    style_axes,
    style_legend,
)


class GaltonTab(QWidget):
    def __init__(self, model: GaltonModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.model = model
        self.batch: GaltonBatch | None = None
        self.animation_row = 0

        self.canvas = MplCanvas(self, width=10, height=5.8)
        self.ax_board, self.ax_hist = self.canvas.figure.subplots(1, 2, width_ratios=[1.1, 1.0])
        style_axes(self.ax_board, grid=False)
        style_axes(self.ax_hist)
        self._draw_pegs()
        self.particle_scatter = self.ax_board.scatter([], [], s=24, c=ACCENT_2, zorder=4)
        self.trail_lines: list = []
        bins = np.arange(self.model.params.rows + 1)
        self.bars = self.ax_hist.bar(bins, np.zeros_like(bins, dtype=float), color=ACCENT_3, alpha=0.55)
        self.theory_line, = self.ax_hist.plot(bins, np.zeros_like(bins, dtype=float), "o-", color=ACCENT, label="二项分布理论")
        self.ax_hist.set_xlabel("落入位置 k（向右次数）")
        self.ax_hist.set_ylabel("概率")
        self.ax_hist.set_ylim(0, 0.35)
        style_legend(self.ax_hist.legend(loc="upper right"))

        panel = ControlPanel("伽尔顿板")
        self.particle_count = LabeledSlider(
            "粒子数 N", 1, 100, 50, formatter=lambda v: f"{int(v)}"
        )
        panel.add(self.particle_count)
        self.run_button = QPushButton("投放粒子")
        self.run_button.clicked.connect(self.start_drop)
        panel.add(self.run_button)
        self.metrics = QLabel()
        self.metrics.setWordWrap(True)
        self.metrics.setObjectName("metricText")
        panel.add(self.metrics)
        panel.finish()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        panel.setFixedWidth(290)
        layout.addWidget(panel)
        layout.addWidget(self.canvas, 1)

        self.timer = QTimer(self)
        self.timer.setInterval(90)
        self.timer.timeout.connect(self._animate)
        self.start_drop()

    def _draw_pegs(self) -> None:
        rows = self.model.params.rows
        peg_x: list[float] = []
        peg_y: list[float] = []
        for row in range(rows):
            xs = np.arange(-row, row + 1, 2)
            peg_x.extend(xs.tolist())
            peg_y.extend((-np.ones_like(xs) * (row + 0.5)).tolist())
        self.ax_board.scatter(peg_x, peg_y, s=15, c="#8ea1b5", alpha=0.75)
        self.ax_board.set_xlim(-rows - 1, rows + 1)
        self.ax_board.set_ylim(-rows - 1.2, 1.0)
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
        self.particle_scatter.set_offsets(np.column_stack((np.zeros(len(self.batch.paths)), np.zeros(len(self.batch.paths)))))
        self.run_button.setEnabled(False)
        self.metrics.setText("正在投放……")
        self.timer.start()

    def _animate(self) -> None:
        assert self.batch is not None
        rows = self.model.params.rows
        row = min(self.animation_row, rows)
        x = self.batch.paths[:, row]
        y = -np.full_like(x, row, dtype=float)
        self.particle_scatter.set_offsets(np.column_stack((x, y)))
        self.animation_row += 1
        if self.animation_row > rows:
            self.timer.stop()
            self._finish_batch()
        self.canvas.draw_idle()

    def _finish_batch(self) -> None:
        assert self.batch is not None
        rows = self.model.params.rows
        y = -np.arange(rows + 1)
        # Limit trail drawing cost while still showing all paths for N<=100.
        for path in self.batch.paths:
            line, = self.ax_board.plot(path, y, color=ACCENT_3, alpha=0.10, linewidth=0.8)
            self.trail_lines.append(line)
        for patch, probability in zip(self.bars, self.batch.probabilities, strict=True):
            patch.set_height(float(probability))
        bins = np.arange(rows + 1)
        self.theory_line.set_data(bins, self.batch.theoretical)
        ymax = max(0.12, float(max(self.batch.probabilities.max(), self.batch.theoretical.max())) * 1.25)
        self.ax_hist.set_ylim(0, ymax)
        sample_mean = float(np.average(bins, weights=self.batch.counts))
        sample_var = float(np.average((bins - sample_mean) ** 2, weights=self.batch.counts))
        self.metrics.setText(
            f"样本数：{self.batch.counts.sum()}\n"
            f"样本均值：{sample_mean:.3f}（理论 6.000）\n"
            f"样本方差：{sample_var:.3f}（理论 3.000）"
        )
        self.run_button.setEnabled(True)
        self.canvas.draw_idle()
