"""Maxwell speed-distribution tab: molecule scene + f(v) & v_x component charts."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QButtonGroup, QGridLayout, QPushButton, QVBoxLayout, QWidget

from heatlab.models.maxwell import MaxwellModel
from heatlab.ui.common import (
    ACCENT,
    ACCENT_2,
    ACCENT_3,
    ButtonRow,
    ControlPanel,
    LabeledSlider,
    MetricGrid,
    MplCanvas,
    WorkbenchPanel,
    np_clamp,
    style_axes,
    style_legend,
)


class MaxwellTab(QWidget):
    def __init__(self, model: MaxwellModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.model = model

        # ---- 场景：固定体积中的分子运动 ----
        self.scene_canvas = MplCanvas(self, width=5, height=5)
        self.ax_box = self.scene_canvas.figure.add_subplot(111)
        style_axes(self.ax_box, grid=False)
        speeds = self.model.speeds
        self.particles = self.ax_box.scatter(
            self.model.positions[:, 0], self.model.positions[:, 1],
            s=22, c=speeds, cmap="plasma",
        )
        self.ax_box.set_xlim(0, 1)
        self.ax_box.set_ylim(0, 1)
        self.ax_box.set_aspect("equal", adjustable="box")
        self.ax_box.set_xlabel("固定体积容器")
        self.ax_box.set_ylabel("相对位置")

        # ---- 图表：速率分布 + 水平分量分布（双图） ----
        self.chart_canvas = MplCanvas(self, width=5, height=5)
        self.ax_dist, self.ax_component = self.chart_canvas.figure.subplots(1, 2)
        style_axes(self.ax_dist)
        style_axes(self.ax_component)

        velocity, density = self.model.distribution_curve()
        self.pdf_line, = self.ax_dist.plot(
            velocity, density, color=ACCENT, linewidth=2.0, label="理论 f(v)"
        )
        self.ax_dist.set_xlabel(r"速率 $v$ / (m·s$^{-1}$)")
        self.ax_dist.set_ylabel("概率密度 f(v)")
        self.ax_dist.set_title("速率分布 f(v)")
        style_legend(self.ax_dist.legend(loc="upper right"))

        comp_velocity, comp_density = self.model.component_curve()
        self.comp_pdf_line, = self.ax_component.plot(
            comp_velocity, comp_density, color=ACCENT_2, linewidth=2.0, label="理论高斯"
        )
        self.ax_component.set_xlabel(r"水平分量 $v_x$ / (m·s$^{-1}$)")
        self.ax_component.set_ylabel("概率密度 f(v_x)")
        self.ax_component.set_title("水平速度分量分布")

        # ---- 控制面板 ----
        panel = ControlPanel("麦克斯韦速率分布", lead="对照速率 f(v) 与水平速度分量 v_x 的理论分布与样本。")
        self.temperature = LabeledSlider(
            "温度 T", 0, 100, 20, formatter=lambda v: f"{v:.0f} °C"
        )
        self.temperature.valueChanged.connect(self._temperature_changed)
        panel.add(self.temperature)

        # ---- 自动步进（目标固定为温度） ----
        sweep_container = QWidget()
        sweep_layout = QVBoxLayout(sweep_container)
        sweep_layout.setContentsMargins(0, 0, 0, 0)
        sweep_layout.setSpacing(6)

        self.sweep_direction_group = QButtonGroup(self)
        self.sweep_direction_group.setExclusive(True)
        self.sweep_up_btn = QPushButton("升")
        self.sweep_down_btn = QPushButton("降")
        direction_grid = QGridLayout()
        direction_grid.setContentsMargins(0, 0, 0, 0)
        direction_grid.setSpacing(4)
        for column, button in enumerate((self.sweep_up_btn, self.sweep_down_btn)):
            button.setCheckable(True)
            self.sweep_direction_group.addButton(button)
            direction_grid.addWidget(button, 0, column)
        self.sweep_up_btn.setChecked(True)

        self.sweep_rate = LabeledSlider("速率", 1, 100, 50, formatter=lambda v: f"{v * 0.1:.1f} °C/s")
        self.sweep_button = QPushButton("开始步进")
        self.sweep_button.setCheckable(True)
        self.sweep_button.clicked.connect(self._toggle_sweep)

        sweep_layout.addLayout(direction_grid)
        sweep_layout.addWidget(self.sweep_rate)
        sweep_layout.addWidget(self.sweep_button)
        panel.add(sweep_container)

        self.metrics = MetricGrid("最概然", "平均", "均方根")
        panel.add(self.metrics)

        self.pause_button = QPushButton("暂停")
        self.pause_button.setObjectName("primaryButton")
        self.pause_button.setCheckable(True)
        self.pause_button.clicked.connect(self._toggle_pause)
        reset_button = QPushButton("重新采样")
        reset_button.clicked.connect(self._reset)
        panel.add(ButtonRow(self.pause_button, reset_button))
        panel.finish()

        self.workbench = WorkbenchPanel(
            panel, "固定体积中的分子运动", self.scene_canvas,
            "速率 f(v) 与水平分量 v_x 分布", self.chart_canvas,
        )
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.workbench)

        self.timer = QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self._tick)
        self.sweep_active = False
        self._sweep_accum = 0.0
        self.timer.start()
        self._update_distribution()

    def _temperature_changed(self, value: float) -> None:
        self.model.set_temperature(value)
        self._update_distribution()

    # ---- 自动步进 ----
    @property
    def sweep_direction(self) -> int:
        return -1 if self.sweep_down_btn.isChecked() else 1

    def _toggle_sweep(self, checked: bool) -> None:
        if not checked:
            self._stop_sweep()
            return
        self.sweep_active = True
        self._sweep_accum = 0.0
        self.sweep_button.setText("停止步进")

    def _stop_sweep(self) -> None:
        self.sweep_active = False
        self.sweep_button.setChecked(False)
        self.sweep_button.setText("开始步进")

    def _sweep_step(self) -> None:
        if not self.sweep_active:
            return
        self._sweep_accum += self.sweep_rate.value * 0.003 * self.sweep_direction
        steps = int(self._sweep_accum)
        if not steps:
            return
        self._sweep_accum -= steps
        new_value = self.temperature.slider.value() + steps
        self.temperature.slider.setValue(int(np_clamp(new_value, 0, 100)))
        if new_value <= 0 or new_value >= 100:
            self._stop_sweep()

    def _toggle_pause(self, paused: bool) -> None:
        if paused:
            self.timer.stop()
            self.pause_button.setText("继续")
        else:
            self.timer.start()
            self.pause_button.setText("暂停")

    def set_animation_paused(self, paused: bool) -> None:
        self.pause_button.setChecked(paused)
        self._toggle_pause(paused)

    def _reset(self) -> None:
        self.model.reset()
        self._update_distribution()

    def _tick(self) -> None:
        self.model.step()
        self.particles.set_offsets(self.model.positions)
        speeds = self.model.speeds
        self.particles.set_array(speeds)
        self.particles.set_clim(float(speeds.min()), float(speeds.max()))
        self._sweep_step()
        self.scene_canvas.draw_idle()

    def _update_distribution(self) -> None:
        # 速率 f(v)：理论曲线 + 随机样本直方图
        velocity, density = self.model.distribution_curve()
        self.pdf_line.set_data(velocity, density)
        for patch in list(self.ax_dist.patches):
            patch.remove()
        self.ax_dist.hist(
            self.model.sampled_speeds(10_000),
            bins=42,
            density=True,
            alpha=0.28,
            color=ACCENT_3,
            label="随机样本",
        )
        self.ax_dist.relim()
        self.ax_dist.autoscale_view()
        style_legend(self.ax_dist.legend(loc="upper right"))

        # 水平分量 v_x：高斯理论曲线 + 样本直方图（文档要求的"几率~水平速度曲线"）
        comp_velocity, comp_density = self.model.component_curve()
        self.comp_pdf_line.set_data(comp_velocity, comp_density)
        for patch in list(self.ax_component.patches):
            patch.remove()
        self.ax_component.hist(
            self.model.sampled_components(10_000),
            bins=44,
            density=True,
            alpha=0.28,
            color=ACCENT,
            label="v_x 样本",
        )
        self.ax_component.relim()
        self.ax_component.autoscale_view()
        style_legend(self.ax_component.legend(loc="upper right"))

        self.ax_box.set_title(f"固定体积内分子运动｜T={self.model.state.temperature_c:.0f} °C")
        self.metrics.set_values({
            "最概然": f"{self.model.most_probable_speed:.1f} m/s",
            "平均": f"{self.model.mean_speed:.1f} m/s",
            "均方根": f"{self.model.rms_speed:.1f} m/s",
        })
        self.chart_canvas.draw_idle()
