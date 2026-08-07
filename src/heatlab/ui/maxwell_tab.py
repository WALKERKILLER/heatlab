"""Maxwell speed-distribution tab."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from heatlab.models.maxwell import MaxwellModel
from heatlab.ui.common import (
    ACCENT,
    ACCENT_3,
    ButtonRow,
    ControlPanel,
    LabeledSlider,
    MplCanvas,
    style_axes,
)


class MaxwellTab(QWidget):
    def __init__(self, model: MaxwellModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.model = model

        self.canvas = MplCanvas(self, width=10, height=5.8)
        self.ax_box, self.ax_dist = self.canvas.figure.subplots(1, 2)
        style_axes(self.ax_box, grid=False)
        style_axes(self.ax_dist)
        speeds = self.model.speeds
        self.particles = self.ax_box.scatter(
            self.model.positions[:, 0], self.model.positions[:, 1], s=22, c=speeds, cmap="plasma"
        )
        self.ax_box.set_xlim(0, 1)
        self.ax_box.set_ylim(0, 1)
        self.ax_box.set_aspect("equal", adjustable="box")
        self.ax_box.set_xlabel("固定体积容器")
        self.ax_box.set_ylabel("相对位置")

        velocity, density = self.model.distribution_curve()
        self.pdf_line, = self.ax_dist.plot(velocity, density, color=ACCENT, linewidth=2.0, label="理论 f(v)")
        self.hist_patches = None
        self.ax_dist.set_xlabel("速率 v / (m·s⁻¹)")
        self.ax_dist.set_ylabel("概率密度 f(v)")
        self.ax_dist.legend(loc="upper right")

        panel = ControlPanel("麦克斯韦速率分布")
        self.temperature = LabeledSlider(
            "温度 T", 0, 100, 20, formatter=lambda v: f"{v:.0f} °C"
        )
        self.temperature.valueChanged.connect(self._temperature_changed)
        panel.add(self.temperature)
        self.metrics = QLabel()
        self.metrics.setWordWrap(True)
        self.metrics.setObjectName("metricText")
        panel.add(self.metrics)

        self.pause_button = QPushButton("暂停")
        self.pause_button.setCheckable(True)
        self.pause_button.clicked.connect(self._toggle_pause)
        reset_button = QPushButton("重新采样")
        reset_button.clicked.connect(self._reset)
        panel.add(ButtonRow(self.pause_button, reset_button))
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
        self._update_distribution()

    def _temperature_changed(self, value: float) -> None:
        self.model.set_temperature(value)
        self._update_distribution()

    def _toggle_pause(self, paused: bool) -> None:
        if paused:
            self.timer.stop()
            self.pause_button.setText("继续")
        else:
            self.timer.start()
            self.pause_button.setText("暂停")

    def _reset(self) -> None:
        self.model.reset()
        self._update_distribution()

    def _tick(self) -> None:
        self.model.step()
        self.particles.set_offsets(self.model.positions)
        speeds = self.model.speeds
        self.particles.set_array(speeds)
        self.particles.set_clim(float(speeds.min()), float(speeds.max()))
        self.canvas.draw_idle()

    def _update_distribution(self) -> None:
        velocity, density = self.model.distribution_curve()
        self.pdf_line.set_data(velocity, density)
        sampled = self.model.sampled_speeds(10_000)
        # Remove the previous histogram artists before drawing the new density.
        for patch in list(self.ax_dist.patches):
            patch.remove()
        self.ax_dist.hist(
            sampled,
            bins=42,
            density=True,
            alpha=0.28,
            color=ACCENT_3,
            label="随机样本",
        )
        self.ax_dist.relim()
        self.ax_dist.autoscale_view()
        self.ax_dist.legend(loc="upper right")
        self.ax_box.set_title(f"固定体积内分子运动｜T={self.model.state.temperature_c:.0f} °C")
        self.metrics.setText(
            f"最概然速率：{self.model.most_probable_speed:.1f} m/s\n"
            f"平均速率：{self.model.mean_speed:.1f} m/s\n"
            f"方均根速率：{self.model.rms_speed:.1f} m/s"
        )
        self.canvas.draw_idle()
