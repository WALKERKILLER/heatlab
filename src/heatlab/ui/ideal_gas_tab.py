"""Ideal-gas tab."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from heatlab.models.ideal_gas import IdealGasModel
from heatlab.ui.common import (
    ACCENT,
    ACCENT_2,
    BG,
    GRID,
    MUTED,
    ButtonRow,
    ControlPanel,
    LabeledSlider,
    MplCanvas,
    style_axes,
)


class IdealGasTab(QWidget):
    def __init__(self, model: IdealGasModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.model = model
        self.frame_count = 0

        self.canvas = MplCanvas(self, width=10, height=5.8)
        grid = self.canvas.figure.add_gridspec(1, 2, width_ratios=[1.25, 1.0])
        self.ax_box = self.canvas.figure.add_subplot(grid[0, 0])
        self.ax_phase = self.canvas.figure.add_subplot(grid[0, 1], projection="3d")
        style_axes(self.ax_box, grid=False)
        self.ax_phase.set_facecolor(BG)
        self.ax_phase.tick_params(colors=MUTED)
        for axis in (self.ax_phase.xaxis, self.ax_phase.yaxis, self.ax_phase.zaxis):
            axis.label.set_color("#dbe7f3")
            axis.pane.set_facecolor(BG)
            axis.pane.set_edgecolor(GRID)
        self.ax_phase.grid(True, color=GRID, alpha=0.35)

        points = self.model.display_positions
        self.particle_scatter = self.ax_box.scatter(
            points[:, 0], points[:, 1], s=22, c=ACCENT_2, edgecolors="none", alpha=0.88
        )
        self.ax_box.set_xlim(0, self.model.box_width)
        self.ax_box.set_ylim(0, 1)
        self.ax_box.set_aspect("equal", adjustable="box")
        self.ax_box.set_xlabel("容器长度（相对量）")
        self.ax_box.set_ylabel("容器高度（相对量）")

        history = np.asarray(self.model.phase_history)
        self.phase_line, = self.ax_phase.plot(
            history[:, 0], history[:, 1], history[:, 2], color=ACCENT, linewidth=1.8
        )
        self.phase_point = self.ax_phase.scatter(
            history[-1:, 0], history[-1:, 1], history[-1:, 2], s=55, c=ACCENT_2
        )
        self.ax_phase.set_xlabel("P / atm")
        self.ax_phase.set_ylabel("V / L")
        self.ax_phase.set_zlabel("T / K")
        self.ax_phase.set_title("P-V-T 状态轨迹")

        panel = ControlPanel("理想气体")
        self.temperature = LabeledSlider(
            "温度 T", 0, 100, 20, formatter=lambda v: f"{v:.0f} °C"
        )
        self.pressure = LabeledSlider(
            "压强 P", 100, 200, 100, transform=lambda x: x / 100, formatter=lambda v: f"{v:.2f} atm"
        )
        self.temperature.valueChanged.connect(self._conditions_changed)
        self.pressure.valueChanged.connect(self._conditions_changed)
        panel.add(self.temperature)
        panel.add(self.pressure)

        self.metrics = QLabel()
        self.metrics.setWordWrap(True)
        self.metrics.setObjectName("metricText")
        panel.add(self.metrics)

        self.pause_button = QPushButton("暂停")
        self.pause_button.setCheckable(True)
        self.pause_button.clicked.connect(self._toggle_pause)
        reset_button = QPushButton("重置粒子")
        reset_button.clicked.connect(self._reset)
        resample_button = QPushButton("重采样速度")
        resample_button.clicked.connect(self.model.resample_velocities)
        panel.add(ButtonRow(self.pause_button, reset_button))
        panel.add(resample_button)
        panel.finish()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        panel.setFixedWidth(290)
        layout.addWidget(panel)
        layout.addWidget(self.canvas, 1)

        self.timer = QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self._tick)
        self.timer.start()
        self._update_all()

    def _conditions_changed(self, _value: float) -> None:
        self.model.set_conditions(self.temperature.value, self.pressure.value)
        self._update_phase()
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
        self._update_all()

    def _tick(self) -> None:
        self.model.step()
        self.particle_scatter.set_offsets(self.model.display_positions)
        self.ax_box.set_xlim(0, self.model.box_width)
        self.frame_count += 1
        if self.frame_count % 12 == 0:
            self._update_metrics()
        self.canvas.draw_idle()

    def _update_metrics(self) -> None:
        state = self.model.state
        kinetic_atm = self.model.kinetic_pressure_pa() / 101_325.0
        self.metrics.setText(
            f"PV=nRT 计算体积：{state.volume_litre:.3f} L\n"
            f"当前坐标：(P={state.pressure_atm:.2f} atm, V={state.volume_litre:.3f} L, "
            f"T={state.temperature_k:.2f} K)\n"
            f"由 N·m·<vₓ²>/V 估计压强：{kinetic_atm:.3f} atm"
        )
        self.ax_box.set_title(
            f"分子无规则热运动｜T={state.temperature_c:.0f} °C，P={state.pressure_atm:.2f} atm"
        )

    def _update_phase(self) -> None:
        history = np.asarray(self.model.phase_history)
        self.phase_line.set_data_3d(history[:, 0], history[:, 1], history[:, 2])
        self.phase_point._offsets3d = (history[-1:, 0], history[-1:, 1], history[-1:, 2])
        self.ax_phase.set_xlim(0.95, 2.05)
        vmin = max(0.001, history[:, 1].min() * 0.92)
        vmax = history[:, 1].max() * 1.08
        self.ax_phase.set_ylim(vmin, vmax)
        self.ax_phase.set_zlim(270, 380)

    def _update_all(self) -> None:
        self.particle_scatter.set_offsets(self.model.display_positions)
        self.ax_box.set_xlim(0, self.model.box_width)
        self._update_phase()
        self._update_metrics()
        self.canvas.draw_idle()
