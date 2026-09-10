"""Ideal-gas tab (thermodynamics) with quasi-static process modes."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QButtonGroup,
    QGridLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from heatlab.constants import STANDARD_ATMOSPHERE
from heatlab.models.ideal_gas import HeatExchangeModel, IdealGasModel
from heatlab.ui.common import (
    ACCENT,
    ACCENT_2,
    ButtonRow,
    ControlPanel,
    LabeledSlider,
    MetricGrid,
    MplCanvas,
    WorkbenchPanel,
    np_clamp,
    style_3d_axes,
)


class IdealGasTab(QWidget):
    """热力学专题：3D 分子热运动场景 + 3D P-V-T 相图。"""

    EXPERIMENTS: tuple[tuple[str, str], ...] = (
        ("temperature-micro", "温度微观"),
        ("pressure-micro", "压强微观"),
        ("isothermal", "等温"),
        ("isochoric", "等容"),
        ("isobaric", "等压"),
        ("heat-exchange", "两室热交换"),
        ("first-law", "第一定律"),
    )

    # 三维盒子 12 条棱（顶点索引对）
    _BOX_EDGES: tuple[tuple[int, int], ...] = (
        (0, 1), (0, 2), (1, 3), (2, 3),
        (4, 5), (4, 6), (5, 7), (6, 7),
        (0, 4), (1, 5), (2, 6), (3, 7),
    )

    def __init__(
        self,
        model: IdealGasModel,
        heat_exchange: HeatExchangeModel | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.model = model
        self.heat_exchange = heat_exchange or HeatExchangeModel(model.rng)
        self.active_experiment = "temperature-micro"
        self._applying_experiment = False
        self._divider_line = None
        self._heat_phase_line = None
        self.frame_count = 0

        # ---- 场景：3D 分子无规则热运动（体积随 T/P 变化，粒子按速率着色） ----
        self.scene_canvas = MplCanvas(self, width=5, height=5)
        self.ax_box = self.scene_canvas.figure.add_subplot(111, projection="3d")
        style_3d_axes(self.ax_box)
        self._box_line_artists: list = []
        self._draw_box_edges()
        points = self.model.display_positions
        speeds = self.model.speeds
        self.particle_scatter = self.ax_box.scatter(
            points[:, 0], points[:, 1], points[:, 2],
            s=14, c=speeds, cmap="turbo", alpha=0.9,
        )
        self.ax_box.set_box_aspect(
            (self.model.box_length, self.model.box_height, self.model.box_depth)
        )
        self.ax_box.set_xlim(0, self.model.box_length)
        self.ax_box.set_ylim(0, self.model.box_height)
        self.ax_box.set_zlim(0, self.model.box_depth)
        self.ax_box.set_xlabel("容器长度（相对量）")
        self.ax_box.set_ylabel("容器高度（相对量）")
        self.ax_box.set_zlabel("容器深度（相对量）")

        # ---- 图表：3D P-V-T 相图（给出 (P,V,T) 坐标值） ----
        self.chart_canvas = MplCanvas(self, width=5, height=5)
        self.ax_phase = self.chart_canvas.figure.add_subplot(111, projection="3d")
        style_3d_axes(self.ax_phase)
        history = np.asarray(self.model.phase_history)
        if history.size:
            self.phase_line, = self.ax_phase.plot(
                history[:, 0], history[:, 1], history[:, 2], color=ACCENT_2, linewidth=1.6
            )
            self.state_point = self.ax_phase.scatter(
                history[-1:, 0], history[-1:, 1], history[-1:, 2], s=55, c=ACCENT,
                edgecolors="#ffffff", linewidths=0.6,
            )
        else:
            self.phase_line, = self.ax_phase.plot([], [], [], color=ACCENT_2, linewidth=1.6)
            self.state_point = self.ax_phase.scatter([], [], [], s=55, c=ACCENT)
        self.theory_line, = self.ax_phase.plot(
            [], [], [], "--", color="#89d185", linewidth=1.6, alpha=0.9
        )
        self.theory_line.set_visible(False)
        self.ax_phase.set_xlabel("压强 P / atm")
        self.ax_phase.set_ylabel("体积 V / L")
        self.ax_phase.set_zlabel("绝对温度 T / K")
        self.ax_phase.set_title("压强、体积与绝对温度状态图")
        self.ax_phase.set_xlim(0.95, 2.05)
        self.ax_phase.set_zlim(270, 380)
        style_3d_axes(self.ax_phase)  # re-apply after labels/title

        # ---- 控制面板 ----
        panel = ControlPanel("热力学", lead="选择一组单变量实验；固定量由模型保持，观察分子运动、状态关系与能量读数。")
        self.process_group, self.process_buttons = self._build_experiment_buttons(panel)
        self.temperature = LabeledSlider(
            "温度", 0, 100, 20, formatter=lambda v: f"{v:.0f} °C"
        )
        self.pressure = LabeledSlider(
            "压强", 100, 200, 100, transform=lambda x: x / 100, formatter=lambda v: f"{v:.2f} atm"
        )
        self.volume = LabeledSlider(
            "相对体积 V/V₀", 20, 500, 100, transform=lambda x: x / 100, formatter=lambda v: f"{v:.2f} V₀"
        )
        self.left_temperature = LabeledSlider(
            "左室温度", 0, 100, 80, formatter=lambda v: f"{v:.0f} °C"
        )
        self.right_temperature = LabeledSlider(
            "右室温度", 0, 100, 20, formatter=lambda v: f"{v:.0f} °C"
        )
        self.barrier = "adiabatic"
        self.barrier_group = QButtonGroup(self)
        self.barrier_group.setExclusive(True)
        self.adiabatic_button = QPushButton("绝热隔板")
        self.conductive_button = QPushButton("导热隔板")
        for button in (self.adiabatic_button, self.conductive_button):
            button.setCheckable(True)
            self.barrier_group.addButton(button)
        self.adiabatic_button.setChecked(True)
        self.adiabatic_button.clicked.connect(lambda _checked=False: self._set_barrier("adiabatic"))
        self.conductive_button.clicked.connect(lambda _checked=False: self._set_barrier("conductive"))
        barrier_container = QWidget()
        barrier_layout = QGridLayout(barrier_container)
        barrier_layout.setContentsMargins(0, 0, 0, 0)
        barrier_layout.setSpacing(4)
        barrier_layout.addWidget(self.adiabatic_button, 0, 0)
        barrier_layout.addWidget(self.conductive_button, 0, 1)
        self.barrier_container = barrier_container
        self.demo_particles = LabeledSlider(
            "演示粒子数（N_demo）", 5, 100, 60, formatter=lambda v: f"{v:.0f}"
        )
        self.temperature.valueChanged.connect(self._conditions_changed)
        self.pressure.valueChanged.connect(self._conditions_changed)
        self.volume.valueChanged.connect(self._conditions_changed)
        self.left_temperature.valueChanged.connect(self._conditions_changed)
        self.right_temperature.valueChanged.connect(self._conditions_changed)
        self.demo_particles.valueChanged.connect(self._conditions_changed)
        panel.add(self.temperature)
        panel.add(self.pressure)
        panel.add(self.volume)
        panel.add(self.left_temperature)
        panel.add(self.right_temperature)
        panel.add(self.barrier_container)
        panel.add(self.demo_particles)

        # ---- 自动步进控件 ----
        sweep_container = QWidget()
        sweep_layout = QVBoxLayout(sweep_container)
        sweep_layout.setContentsMargins(0, 0, 0, 0)
        sweep_layout.setSpacing(6)

        self.sweep_target_group = QButtonGroup(self)
        self.sweep_target_group.setExclusive(True)
        self.sweep_t_btn = QPushButton("温度")
        self.sweep_p_btn = QPushButton("压强")
        target_grid = QGridLayout()
        target_grid.setContentsMargins(0, 0, 0, 0)
        target_grid.setSpacing(4)
        for column, button in enumerate((self.sweep_t_btn, self.sweep_p_btn)):
            button.setCheckable(True)
            self.sweep_target_group.addButton(button)
            target_grid.addWidget(button, 0, column)
        self.sweep_t_btn.setChecked(True)
        self.sweep_t_btn.clicked.connect(self._refresh_sweep_rate_text)
        self.sweep_p_btn.clicked.connect(self._refresh_sweep_rate_text)

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

        self.sweep_rate = LabeledSlider("速率", 1, 100, 30, formatter=self._sweep_rate_text)
        self.sweep_button = QPushButton("开始步进")
        self.sweep_button.setCheckable(True)
        self.sweep_button.clicked.connect(self._toggle_sweep)

        sweep_layout.addLayout(target_grid)
        sweep_layout.addLayout(direction_grid)
        sweep_layout.addWidget(self.sweep_rate)
        sweep_layout.addWidget(self.sweep_button)
        panel.add(sweep_container)
        self.sweep_container = sweep_container

        self.metrics = MetricGrid(
            "体积 V", "温度 T", "压强 P", "动量通量估计压强",
            "状态坐标（压强 P、体积 V、绝对温度 T）",
        )
        panel.add(self.metrics)

        self.pause_button = QPushButton("暂停")
        self.pause_button.setObjectName("primaryButton")
        self.pause_button.setCheckable(True)
        self.pause_button.clicked.connect(self._toggle_pause)
        reset_button = QPushButton("重置粒子")
        reset_button.clicked.connect(self._reset)
        resample_button = QPushButton("重采样速度")
        resample_button.clicked.connect(self.model.resample_velocities)
        panel.add(ButtonRow(self.pause_button, reset_button))
        panel.add(resample_button)
        panel.finish()

        self.workbench = WorkbenchPanel(
            panel, "分子无规则热运动（3D）", self.scene_canvas, "压强、体积与绝对温度状态图", self.chart_canvas
        )
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.workbench)

        self.timer = QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self._tick)
        self.sweep_active = False
        self._sweep_t_accum = 0.0
        self._sweep_p_accum = 0.0
        self.timer.start()
        self._set_experiment("temperature-micro", True)
        self._update_all()

    def _build_experiment_buttons(self, panel: ControlPanel) -> tuple[QButtonGroup, dict[str, QPushButton]]:
        group = QButtonGroup(self)
        group.setExclusive(True)
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(4)
        buttons: dict[str, QPushButton] = {}
        for index, (mode_id, label) in enumerate(self.EXPERIMENTS):
            button = QPushButton(label)
            button.setCheckable(True)
            button.clicked.connect(lambda checked, m=mode_id: self._set_experiment(m, checked))
            group.addButton(button)
            buttons[mode_id] = button
            grid.addWidget(button, index // 2, index % 2)
        container = QWidget()
        container.setLayout(grid)
        panel.add(container)
        buttons["temperature-micro"].setChecked(True)
        return group, buttons

    def _set_experiment(self, mode_id: str, checked: bool) -> None:
        if not checked:
            return
        self.active_experiment = mode_id
        volume_mode = mode_id in ("pressure-micro", "isothermal", "first-law")
        temperature_mode = mode_id in ("temperature-micro", "isochoric", "isobaric")
        heat_mode = mode_id == "heat-exchange"
        self.temperature.setVisible(temperature_mode)
        self.volume.setVisible(volume_mode)
        self.left_temperature.setVisible(heat_mode)
        self.right_temperature.setVisible(heat_mode)
        self.barrier_container.setVisible(heat_mode)
        self.pressure.setVisible(False)
        self.sweep_container.setVisible(False)
        self.volume.slider.setMinimum(20 if mode_id == "first-law" else 50)
        self.volume.slider.setMaximum(500 if mode_id == "first-law" else 300)
        self._apply_experiment()
        self._update_scene()
        self._update_chart()
        self._update_metrics()

    def _conditions_changed(self, _value: float) -> None:
        if self._applying_experiment:
            return
        self._apply_experiment()
        self._update_scene()
        self._update_chart()
        self._update_metrics()

    def _apply_experiment(self) -> None:
        self._applying_experiment = True
        try:
            if self.active_experiment == "heat-exchange":
                self.heat_exchange.configure(
                    barrier=self.barrier,
                    temperature_left_c=self.left_temperature.value,
                    temperature_right_c=self.right_temperature.value,
                    demo_particle_count=int(self.demo_particles.value),
                )
                return
            volume_litre = None
            if self.active_experiment in ("pressure-micro", "isothermal", "first-law"):
                reference = (
                    self.model.adiabatic_reference_volume_litre
                    if self.active_experiment == "first-law"
                    and self.model.adiabatic_reference_volume_litre > 0
                    else self.model.reference_volume_litre
                )
                volume_litre = reference * self.volume.value
            self.model.configure_experiment(
                self.active_experiment,
                temperature_c=self.temperature.value,
                pressure_atm=1.0,
                volume_litre=volume_litre,
                demo_particle_count=int(self.demo_particles.value),
            )
        finally:
            self._applying_experiment = False

    def _set_barrier(self, barrier: str) -> None:
        self.barrier = barrier
        if self.active_experiment == "heat-exchange":
            self._apply_experiment()
            self._update_scene()
            self._update_chart()
            self._update_metrics()

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
        if self.active_experiment == "heat-exchange":
            self.heat_exchange.reset()
        else:
            self.model.reset()
        self._update_all()

    # ---- 自动步进 ----
    @property
    def sweep_target(self) -> str:
        """当前步进目标变量：'temperature' 或 'pressure'。"""
        return "pressure" if self.sweep_p_btn.isChecked() else "temperature"

    @property
    def sweep_direction(self) -> int:
        """步进方向：+1 升 / -1 降。"""
        return -1 if self.sweep_down_btn.isChecked() else 1

    def _sweep_rate_text(self, value: float) -> str:
        if self.sweep_target == "pressure":
            return f"{value * 0.001:.3f} atm/s"
        return f"{value * 0.1:.1f} °C/s"

    def _refresh_sweep_rate_text(self) -> None:
        self.sweep_rate.value_label.setText(self._sweep_rate_text(self.sweep_rate.value))

    def _toggle_sweep(self, checked: bool) -> None:
        if not checked:
            self._stop_sweep()
            return
        if self.model.state.process_mode == "isochoric" and self.sweep_target == "pressure":
            self.sweep_t_btn.setChecked(True)
            self._refresh_sweep_rate_text()
        self.sweep_active = True
        self._sweep_t_accum = 0.0
        self._sweep_p_accum = 0.0
        self.sweep_button.setText("停止步进")

    def _stop_sweep(self) -> None:
        self.sweep_active = False
        self.sweep_button.setChecked(False)
        self.sweep_button.setText("开始步进")

    def _sweep_step(self) -> None:
        """每帧推进所选变量；滑条步长为整数格，用浮点累加器避免低速率卡住。"""
        if not self.sweep_active:
            return
        rate = self.sweep_rate.value
        if self.sweep_target == "temperature":
            self._sweep_t_accum += rate * 0.003 * self.sweep_direction
            steps = int(self._sweep_t_accum)
            if not steps:
                return
            self._sweep_t_accum -= steps
            new_value = self.temperature.slider.value() + steps
            self.temperature.slider.setValue(int(np_clamp(new_value, 0, 100)))
            if new_value <= 0 or new_value >= 100:
                self._stop_sweep()
        else:
            self._sweep_p_accum += rate * 0.00003 * self.sweep_direction
            steps = int(self._sweep_p_accum / 0.01)
            if not steps:
                return
            self._sweep_p_accum -= steps * 0.01
            new_value = self.pressure.slider.value() + steps
            self.pressure.slider.setValue(int(np_clamp(new_value, 100, 200)))
            if new_value <= 100 or new_value >= 200:
                self._stop_sweep()

    def _box_corners(self, width: float | None = None) -> np.ndarray:
        """返回三维盒子的 8 个顶点（按 _BOX_EDGES 索引）。"""
        length = self.model.box_length if width is None else width
        height = self.model.box_height
        depth = self.model.box_depth
        return np.array([
            [0, 0, 0], [length, 0, 0], [0, height, 0], [length, height, 0],
            [0, 0, depth], [length, 0, depth], [0, height, depth], [length, height, depth],
        ], dtype=float)

    def _draw_box_edges(self, width: float | None = None) -> None:
        corners = self._box_corners(width=width)
        for first, second in self._BOX_EDGES:
            line, = self.ax_box.plot(
                [corners[first, 0], corners[second, 0]],
                [corners[first, 1], corners[second, 1]],
                [corners[first, 2], corners[second, 2]],
                color="#3e3e42", linewidth=1.2,
            )
            self._box_line_artists.append(line)

    def _update_scene(self) -> None:
        """条件变化后重绘盒体并更新粒子着色。"""
        if self.active_experiment == "heat-exchange":
            points = self.heat_exchange.positions
            speeds = np.concatenate((self.heat_exchange.speeds_left, self.heat_exchange.speeds_right))
            width = self.heat_exchange.box_width
            for artist in self._box_line_artists:
                artist.remove()
            self._box_line_artists.clear()
            self._draw_box_edges(width=width)
            if self._divider_line is None:
                self._divider_line, = self.ax_box.plot(
                    [0.5, 0.5], [0, 1], [0, 1], color=ACCENT_2, linewidth=2.0
                )
            self._divider_line.set_color(
                ACCENT_2 if self.heat_exchange.state.barrier == "conductive" else "#89929e"
            )
            self._divider_line.set_linestyle(
                "-" if self.heat_exchange.state.barrier == "conductive" else "--"
            )
            self.ax_box.set_box_aspect((width, 1, 1))
            self.ax_box.set_xlim(0, width)
            self.ax_box.set_ylim(0, 1)
            self.ax_box.set_zlim(0, 1)
            self.particle_scatter._offsets3d = (points[:, 0], points[:, 1], points[:, 2])
            self.particle_scatter.set_array(speeds)
            self.particle_scatter.set_clim(float(speeds.min()), float(speeds.max()))
            self.ax_box.set_title(
                f"两室热交换｜左 {self.heat_exchange.state.temperature_left_c:.0f} °C，"
                f"右 {self.heat_exchange.state.temperature_right_c:.0f} °C"
            )
            self.scene_canvas.draw_idle()
            return
        if self._divider_line is not None:
            self._divider_line.remove()
            self._divider_line = None
        for artist in self._box_line_artists:
            artist.remove()
        self._box_line_artists.clear()
        self._draw_box_edges()
        self.ax_box.set_box_aspect(
            (self.model.box_length, self.model.box_height, self.model.box_depth)
        )
        self.ax_box.set_xlim(0, self.model.box_length)
        self.ax_box.set_ylim(0, self.model.box_height)
        self.ax_box.set_zlim(0, self.model.box_depth)
        x, y, z = self.model.positions.T
        self.particle_scatter._offsets3d = (x, y, z)
        self._update_particle_colors()
        self.scene_canvas.draw_idle()

    def _update_particle_colors(self) -> None:
        speeds = self.model.speeds
        self.particle_scatter.set_array(speeds)
        self.particle_scatter.set_clim(float(speeds.min()), float(speeds.max()))

    def _tick(self) -> None:
        if self.active_experiment == "heat-exchange":
            self.heat_exchange.step()
            points = self.heat_exchange.positions
            speeds = np.concatenate((self.heat_exchange.speeds_left, self.heat_exchange.speeds_right))
        else:
            self.model.step()
            points = self.model.positions
            speeds = self.model.speeds
        x, y, z = points.T
        self.particle_scatter._offsets3d = (x, y, z)
        self.particle_scatter.set_array(speeds)
        self.frame_count += 1
        if self.frame_count % 12 == 0:
            self._update_metrics()
            if self.active_experiment == "heat-exchange":
                self._update_chart()
        self._sweep_step()
        self.scene_canvas.draw_idle()

    def _update_metrics(self) -> None:
        if self.active_experiment == "heat-exchange":
            state = self.heat_exchange.state
            rows = self.metrics._rows
            labels = ("左室温度", "右室温度", "热流率", "累计传热", "模拟时间")
            values = (
                f"{state.temperature_left_c:.2f} °C",
                f"{state.temperature_right_c:.2f} °C",
                f"{self.heat_exchange.heat_rate_w:.3e} W",
                f"{self.heat_exchange.heat_transferred_j:.3e} J",
                f"{self.heat_exchange.elapsed_s:.2f} s",
            )
            for row, label in zip(rows, labels, strict=True):
                row.key_label.setText(label)
                row.set_value(values[rows.index(row)])
            self.ax_box.set_title(
                f"两室热交换｜左 {state.temperature_left_c:.0f} °C，右 {state.temperature_right_c:.0f} °C"
            )
            return
        state = self.model.state
        rows = self.metrics._rows
        if self.active_experiment == "first-law":
            labels = ("体积 V", "温度 T", "热量 Q", "内能变化 ΔU", "气体对外做功 W")
            values = (
                f"{state.volume_litre:.4f} L",
                f"{state.temperature_k:.2f} K",
                f"{self.model.heat_added_j:.3e} J",
                f"{self.model.internal_energy_j - self.model.adiabatic_initial_internal_energy_j:.3e} J",
                f"{self.model.work_by_gas_j:.3e} J",
            )
        else:
            labels = (
                "体积 V", "温度 T", "压强 P", "动量通量估计压强",
                "状态坐标（压强 P、体积 V、绝对温度 T）",
            )
            kinetic_atm = self.model.kinetic_pressure_pa() / STANDARD_ATMOSPHERE
            values = (
                f"{state.volume_litre:.4f} L",
                f"{state.temperature_k:.2f} K",
                f"{state.pressure_atm:.3f} atm",
                f"{kinetic_atm:.3f} atm",
                f"({state.pressure_atm:.2f} atm, {state.volume_litre:.3f} L, {state.temperature_k:.2f} K)",
            )
        for row, label, value in zip(rows, labels, values, strict=True):
            row.key_label.setText(label)
            row.set_value(value)
        self.ax_box.set_title(
            f"分子无规则热运动｜T={state.temperature_c:.0f} °C，P={state.pressure_atm:.2f} atm"
        )

    def _relation_coordinates(
        self,
        points: np.ndarray,
        relation: str,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        if relation == "pt":
            return points[:, 2], points[:, 0], np.zeros(len(points))
        if relation == "vt":
            return points[:, 2], points[:, 1], np.zeros(len(points))
        return points[:, 0], points[:, 1], points[:, 2]

    def _update_chart(self) -> None:
        if self.active_experiment == "heat-exchange":
            history = np.asarray(self.heat_exchange.temperature_history)
            if not history.size:
                return
            if self._heat_phase_line is None:
                self._heat_phase_line, = self.ax_phase.plot(
                    [], [], [], color=ACCENT_2, linewidth=1.6, label="左室 / 右室温度"
                )
            self.phase_line.set_visible(False)
            self.state_point.set_visible(False)
            self.theory_line.set_visible(False)
            self._heat_phase_line.set_data_3d(history[:, 0], history[:, 1], history[:, 2])
            self.ax_phase.set_xlabel("时间 t / s")
            self.ax_phase.set_ylabel("左室温度 / °C")
            self.ax_phase.set_zlabel("右室温度 / °C")
            self.ax_phase.set_title("两室温度随时间变化")
            self.ax_phase.set_xlim(float(history[:, 0].min()), max(1.0, float(history[:, 0].max())))
            self.ax_phase.set_ylim(0, 100)
            self.ax_phase.set_zlim(0, 100)
            self.chart_canvas.draw_idle()
            return
        if self._heat_phase_line is not None:
            self._heat_phase_line.set_visible(False)
        self.phase_line.set_visible(True)
        self.state_point.set_visible(True)
        history = np.asarray(self.model.phase_history)
        if not history.size:
            return
        relation = (
            "pt" if self.active_experiment in ("temperature-micro", "isochoric")
            else "vt" if self.active_experiment == "isobaric"
            else "pv"
        )
        history_x, history_y, history_z = self._relation_coordinates(history, relation)
        self.phase_line.set_data_3d(history_x, history_y, history_z)
        self.state_point._offsets3d = (history_x[-1:], history_y[-1:], history_z[-1:])
        process_line_3d = self.model.process_line_3d()
        if process_line_3d is not None:
            theory = np.column_stack(process_line_3d)
            theory_x, theory_y, theory_z = self._relation_coordinates(theory, relation)
            self.theory_line.set_data_3d(theory_x, theory_y, theory_z)
            self.theory_line.set_visible(True)
        else:
            self.theory_line.set_visible(False)
        if relation == "pt":
            self.ax_phase.set_xlabel("绝对温度 T / K")
            self.ax_phase.set_ylabel("压强 P / atm")
            self.ax_phase.set_zlabel("")
            self.ax_phase.zaxis.set_visible(False)
            self.ax_phase.set_xlim(float(history_x.min()) * 0.98, float(history_x.max()) * 1.02)
            self.ax_phase.set_ylim(max(0.001, float(history_y.min()) * 0.92), float(history_y.max()) * 1.08)
            self.ax_phase.set_zlim(-1.0, 1.0)
            self.ax_phase.view_init(elev=90, azim=-90)
            self.ax_phase.set_title("压强与绝对温度关系")
        elif relation == "vt":
            self.ax_phase.set_xlabel("绝对温度 T / K")
            self.ax_phase.set_ylabel("体积 V / L")
            self.ax_phase.set_zlabel("")
            self.ax_phase.zaxis.set_visible(False)
            self.ax_phase.set_xlim(float(history_x.min()) * 0.98, float(history_x.max()) * 1.02)
            self.ax_phase.set_ylim(max(0.001, float(history_y.min()) * 0.92), float(history_y.max()) * 1.08)
            self.ax_phase.set_zlim(-1.0, 1.0)
            self.ax_phase.view_init(elev=90, azim=-90)
            self.ax_phase.set_title("体积与绝对温度关系")
        else:
            self.ax_phase.set_xlabel("压强 P / atm")
            self.ax_phase.set_ylabel("体积 V / L")
            self.ax_phase.set_zlabel("绝对温度 T / K")
            self.ax_phase.zaxis.set_visible(True)
            self.ax_phase.set_xlim(max(0.001, float(history_x.min()) * 0.92), float(history_x.max()) * 1.08)
            self.ax_phase.set_ylim(max(0.001, float(history_y.min()) * 0.92), float(history_y.max()) * 1.08)
            self.ax_phase.set_zlim(float(history_z.min()) * 0.92, float(history_z.max()) * 1.08)
            self.ax_phase.view_init(elev=25, azim=-60)
            self.ax_phase.set_title("压强与体积状态图")
        self.chart_canvas.draw_idle()

    def _update_all(self) -> None:
        self._update_scene()
        self._update_chart()
        self._update_metrics()
        self.scene_canvas.draw_idle()
