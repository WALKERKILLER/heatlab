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
from heatlab.models.ideal_gas import IdealGasModel
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

    PROCESS_MODES: tuple[tuple[str, str], ...] = (
        ("free", "自由"),
        ("isothermal", "等温"),
        ("isobaric", "等压"),
        ("isochoric", "等容"),
    )

    # 三维盒子 12 条棱（顶点索引对）
    _BOX_EDGES: tuple[tuple[int, int], ...] = (
        (0, 1), (0, 2), (1, 3), (2, 3),
        (4, 5), (4, 6), (5, 7), (6, 7),
        (0, 4), (1, 5), (2, 6), (3, 7),
    )

    def __init__(self, model: IdealGasModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.model = model
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
        self.ax_phase.set_xlabel("P / atm")
        self.ax_phase.set_ylabel("V / L")
        self.ax_phase.set_zlabel("T / K")
        self.ax_phase.set_title("P-V-T 相图")
        self.ax_phase.set_xlim(0.95, 2.05)
        self.ax_phase.set_zlim(270, 380)
        style_3d_axes(self.ax_phase)  # re-apply after labels/title

        # ---- 控制面板 ----
        panel = ControlPanel("热力学", lead="调 T/P 或切换等温/等压/等容过程，观察 3D 分子运动与 P-V 状态轨迹。")
        self.process_group, self.process_buttons = self._build_process_buttons(panel)
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

        self.metrics = MetricGrid("体积 V", "温度 T", "设定 P", "动能论 P", "状态坐标 (P,V,T)")
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
            panel, "分子无规则热运动（3D）", self.scene_canvas, "P-V-T 相图", self.chart_canvas
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
        self._update_all()

    def _build_process_buttons(self, panel: ControlPanel) -> tuple[QButtonGroup, dict[str, QPushButton]]:
        group = QButtonGroup(self)
        group.setExclusive(True)
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(4)
        buttons: dict[str, QPushButton] = {}
        for column, (mode_id, label) in enumerate(self.PROCESS_MODES):
            button = QPushButton(label)
            button.setCheckable(True)
            button.clicked.connect(lambda checked, m=mode_id: self._set_process_mode(m, checked))
            group.addButton(button)
            buttons[mode_id] = button
            grid.addWidget(button, 0, column)
        container = QWidget()
        container.setLayout(grid)
        panel.add(container)
        buttons["free"].setChecked(True)
        return group, buttons

    def _set_process_mode(self, mode_id: str, checked: bool) -> None:
        if not checked:
            return
        self.model.set_process_mode(mode_id)
        self.pressure.slider.setEnabled(mode_id != "isochoric")
        self.sweep_p_btn.setEnabled(mode_id != "isochoric")
        if mode_id == "isochoric":
            self.pressure.set_value(self.model.state.pressure_atm)
            if self.sweep_target == "pressure":
                self.sweep_t_btn.setChecked(True)
                self._refresh_sweep_rate_text()
        self._update_scene()
        self._update_chart()
        self._update_metrics()

    def _conditions_changed(self, _value: float) -> None:
        self.model.set_conditions(self.temperature.value, self.pressure.value)
        if self.model.state.process_mode == "isochoric":
            self.pressure.set_value(self.model.state.pressure_atm)
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

    def _box_corners(self) -> np.ndarray:
        """返回三维盒子的 8 个顶点（按 _BOX_EDGES 索引）。"""
        length = self.model.box_length
        height = self.model.box_height
        depth = self.model.box_depth
        return np.array([
            [0, 0, 0], [length, 0, 0], [0, height, 0], [length, height, 0],
            [0, 0, depth], [length, 0, depth], [0, height, depth], [length, height, depth],
        ], dtype=float)

    def _draw_box_edges(self) -> None:
        corners = self._box_corners()
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
        self.model.step()
        x, y, z = self.model.positions.T
        self.particle_scatter._offsets3d = (x, y, z)
        self._update_particle_colors()
        self.frame_count += 1
        if self.frame_count % 12 == 0:
            self._update_metrics()
        self._sweep_step()
        self.scene_canvas.draw_idle()

    def _update_metrics(self) -> None:
        state = self.model.state
        kinetic_atm = self.model.kinetic_pressure_pa() / STANDARD_ATMOSPHERE
        self.metrics.set_values({
            "体积 V": f"{state.volume_litre:.4f} L",
            "温度 T": f"{state.temperature_k:.2f} K",
            "设定 P": f"{state.pressure_atm:.3f} atm",
            "动能论 P": f"{kinetic_atm:.3f} atm",
            "状态坐标 (P,V,T)": (
                f"({state.pressure_atm:.2f} atm, {state.volume_litre:.3f} L, "
                f"{state.temperature_k:.2f} K)"
            ),
        })
        self.ax_box.set_title(
            f"分子无规则热运动｜T={state.temperature_c:.0f} °C，P={state.pressure_atm:.2f} atm"
        )

    def _update_chart(self) -> None:
        history = np.asarray(self.model.phase_history)
        if not history.size:
            return
        self.phase_line.set_data_3d(history[:, 0], history[:, 1], history[:, 2])
        self.state_point._offsets3d = (
            history[-1:, 0], history[-1:, 1], history[-1:, 2],
        )
        process_line_3d = self.model.process_line_3d()
        if process_line_3d is not None:
            pressures, volumes, temperatures = process_line_3d
            self.theory_line.set_data_3d(pressures, volumes, temperatures)
            self.theory_line.set_visible(True)
        else:
            self.theory_line.set_visible(False)
        self.ax_phase.set_xlim(0.95, 2.05)
        vmin = max(0.001, float(history[:, 1].min()) * 0.92)
        vmax = float(history[:, 1].max()) * 1.08
        self.ax_phase.set_ylim(vmin, vmax)
        self.ax_phase.set_zlim(270, 380)
        self.chart_canvas.draw_idle()

    def _update_all(self) -> None:
        self._update_scene()
        self._update_chart()
        self._update_metrics()
        self.scene_canvas.draw_idle()
