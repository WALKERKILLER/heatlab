"""Brownian-motion tab."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from heatlab.models.brownian import BrownianModel
from heatlab.ui.common import (
    ACCENT,
    ACCENT_2,
    ButtonRow,
    ControlPanel,
    LabeledSlider,
    MplCanvas,
    style_axes,
)


class BrownianTab(QWidget):
    def __init__(self, model: BrownianModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.model = model
        self.frame_count = 0

        self.canvas = MplCanvas(self, width=10, height=5.8)
        self.ax_path, self.ax_msd = self.canvas.figure.subplots(1, 2)
        style_axes(self.ax_path)
        style_axes(self.ax_msd)
        self.path_line, = self.ax_path.plot([0.0], [0.0], color=ACCENT, linewidth=1.2)
        self.current_point = self.ax_path.scatter([0.0], [0.0], s=60, c=ACCENT_2, zorder=4)
        self.msd_line, = self.ax_msd.plot([], [], color=ACCENT, linewidth=1.8, label="时间平均 MSD")
        self.theory_line, = self.ax_msd.plot([], [], "--", color=ACCENT_2, linewidth=1.3, label="4Dt")
        self.ax_path.set_title("花粉粒子运动轨迹")
        self.ax_path.set_xlabel("x（无量纲）")
        self.ax_path.set_ylabel("y（无量纲）")
        self.ax_path.set_aspect("equal", adjustable="datalim")
        self.ax_msd.set_title("均方位移与扩散常数")
        self.ax_msd.set_xlabel("滞后时间")
        self.ax_msd.set_ylabel("MSD")
        self.ax_msd.legend(loc="upper left")

        panel = ControlPanel("布朗运动")
        self.mass = LabeledSlider(
            "花粉粒子质量 m/m₀",
            5,
            100,
            50,
            transform=lambda x: x / 100,
            formatter=lambda v: f"{v:.2f}",
        )
        self.molecules = LabeledSlider(
            "液体分子数", 1, 100, 40, formatter=lambda v: f"{int(v)}"
        )
        self.mass.valueChanged.connect(self._parameters_changed)
        self.molecules.valueChanged.connect(self._parameters_changed)
        panel.add(self.mass)
        panel.add(self.molecules)

        self.metrics = QLabel()
        self.metrics.setWordWrap(True)
        self.metrics.setObjectName("metricText")
        panel.add(self.metrics)

        self.pause_button = QPushButton("暂停")
        self.pause_button.setCheckable(True)
        self.pause_button.clicked.connect(self._toggle_pause)
        reset_button = QPushButton("清空轨迹")
        reset_button.clicked.connect(self._reset)
        panel.add(ButtonRow(self.pause_button, reset_button))
        panel.finish()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        panel.setFixedWidth(300)
        layout.addWidget(panel)
        layout.addWidget(self.canvas, 1)

        self.timer = QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self._tick)
        self.timer.start()
        self._update_plot(full=True)

    def _parameters_changed(self, _value: float) -> None:
        self.model.set_parameters(self.mass.value, int(self.molecules.value))
        self._update_metrics()

    def _toggle_pause(self, paused: bool) -> None:
        if paused:
            self.timer.stop()
            self.pause_button.setText("继续")
        else:
            self.timer.start()
            self.pause_button.setText("暂停")

    def _reset(self) -> None:
        self.model.reset()
        self._update_plot(full=True)

    def _tick(self) -> None:
        self.model.step(substeps=4)
        self.frame_count += 1
        self._update_plot(full=self.frame_count % 12 == 0)

    def _update_plot(self, *, full: bool) -> None:
        points = np.asarray(self.model.path)
        self.path_line.set_data(points[:, 0], points[:, 1])
        self.current_point.set_offsets(points[-1:])
        if len(points) > 2:
            xmin, ymin = points.min(axis=0)
            xmax, ymax = points.max(axis=0)
            span = max(xmax - xmin, ymax - ymin, 1.0)
            margin = 0.12 * span
            self.ax_path.set_xlim(xmin - margin, xmax + margin)
            self.ax_path.set_ylim(ymin - margin, ymax + margin)

        if full:
            lag, msd = self.model.msd_curve()
            self.msd_line.set_data(lag, msd)
            if len(lag):
                theory = 4.0 * self.model.params.theoretical_diffusion * lag
                self.theory_line.set_data(lag, theory)
                self.ax_msd.relim()
                self.ax_msd.autoscale_view()
            self._update_metrics()
        self.canvas.draw_idle()

    def _update_metrics(self) -> None:
        d_hat = self.model.empirical_diffusion()
        d_text = "采样不足" if np.isnan(d_hat) else f"{d_hat:.3f}"
        self.metrics.setText(
            f"理论长时扩散常数 D=Θ/γ：{self.model.params.theoretical_diffusion:.3f}\n"
            f"轨迹估计 D：{d_text}\n"
            f"累计时间：{self.model.elapsed:.2f}"
        )
