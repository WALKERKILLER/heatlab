"""Brownian-motion tab: liquid-molecule scene + pollen trajectory + MSD chart."""

from __future__ import annotations

import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QCheckBox, QPushButton, QVBoxLayout, QWidget

from heatlab.models.brownian import BrownianModel
from heatlab.ui.common import (
    ACCENT,
    ACCENT_2,
    ButtonRow,
    ControlPanel,
    LabeledSlider,
    MetricGrid,
    MplCanvas,
    WorkbenchPanel,
    style_axes,
    style_legend,
)

# 花粉粒子的金黄色调（对齐 Web 端的主流物理视觉）
_POLLEN_FACE = "#f5c56b"
_POLLEN_EDGE = "#c8873a"
# 花粉轨迹的基础色（蓝），逐段 alpha 控制渐隐
_PATH_RGB = (94, 186, 255)


class BrownianTab(QWidget):
    def __init__(self, model: BrownianModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.model = model
        self.frame_count = 0
        self.show_arrow = True
        self.show_vector = True
        self.trail_fade = False

        # ---- 场景：液体分子热运动 + 花粉粒子轨迹 ----
        self.scene_canvas = MplCanvas(self, width=5, height=5)
        self.ax_path = self.scene_canvas.figure.add_subplot(111)
        style_axes(self.ax_path, grid=False)
        # 液体分子层：小圆点（数量 n 直接可见）
        self.liquid_points = self.ax_path.scatter(
            [], [], s=10, c=ACCENT, alpha=0.75, zorder=2, edgecolors="none"
        )
        # 液体分子速度方向短线（可开关，对齐 Web 的速度矢量）
        self.liquid_vectors = LineCollection([], colors=ACCENT, alpha=0.5, linewidths=1.2, zorder=3)
        self.ax_path.add_collection(self.liquid_vectors)
        # 碰撞高亮：花粉表面的撞击点（对齐 Web 的绿色发光点）
        self.collision_points = self.ax_path.scatter(
            [], [], s=16, c="#d2ffd2", alpha=0.9, edgecolors="none", zorder=3
        )
        # 花粉轨迹：默认完整保留；开启「轨迹渐隐」后逐段 alpha 递减
        self.path_segments = LineCollection(
            [], linewidths=1.2, colors=[(*_PATH_RGB, 0.55)], zorder=4, capstyle="round"
        )
        self.ax_path.add_collection(self.path_segments)
        # 花粉粒子：金色大圆
        self.pollen_point = self.ax_path.scatter(
            [0.5], [0.5], s=180, c=_POLLEN_FACE, edgecolors=_POLLEN_EDGE,
            linewidths=1.2, zorder=5,
        )
        # 花粉下一步方向箭头（可开关，从花粉边缘指向速度方向）
        self.direction_arrow = FancyArrowPatch(
            (0.5, 0.5), (0.5, 0.5),
            arrowstyle="-|>", mutation_scale=12,
            color="#dcffaa", linewidth=2.0, zorder=6, visible=False,
        )
        self.ax_path.add_patch(self.direction_arrow)
        self.ax_path.set_title("花粉粒子运动轨迹")
        self.ax_path.set_xlabel("x（无量纲）")
        self.ax_path.set_ylabel("y（无量纲）")
        self.ax_path.set_xlim(-0.02, 1.02)
        self.ax_path.set_ylim(-0.02, 1.02)
        self.ax_path.set_aspect("equal")
        # 图注：说明每种元素分别代表什么（对齐 Web 端图例）
        legend_handles = [
            Line2D([], [], marker="o", linestyle="none", markerfacecolor=ACCENT,
                   markeredgecolor="none", markersize=6, label="液体分子"),
            Line2D([], [], color=_PATH_RGB, linewidth=2, label="花粉轨迹"),
            Line2D([], [], marker="o", linestyle="none", markerfacecolor=_POLLEN_FACE,
                   markeredgecolor=_POLLEN_EDGE, markersize=9, label="花粉粒子"),
            Line2D([], [], marker="o", linestyle="none", markerfacecolor="#d2ffd2",
                   markeredgecolor="none", markersize=6, label="碰撞高亮"),
            Line2D([], [], color="#dcffaa", linewidth=2.5, label="运动方向"),
        ]
        self.path_legend = self.ax_path.legend(
            handles=legend_handles, loc="upper left", ncols=2, fontsize=8,
            handlelength=1.4, borderpad=0.6, columnspacing=0.8,
        )
        style_legend(self.path_legend)
        for text_artist in self.path_legend.get_texts():
            text_artist.set_fontsize(8)

        # ---- 图表：均方位移 MSD ----
        self.chart_canvas = MplCanvas(self, width=5, height=5)
        self.ax_msd = self.chart_canvas.figure.add_subplot(111)
        style_axes(self.ax_msd)
        self.msd_line, = self.ax_msd.plot([], [], color=ACCENT, linewidth=1.8, label="时间平均 MSD")
        self.theory_line, = self.ax_msd.plot([], [], "--", color=ACCENT_2, linewidth=1.3, label="4Dt")
        self.ax_msd.set_title("均方位移与扩散常数")
        self.ax_msd.set_xlabel("滞后时间")
        self.ax_msd.set_ylabel("MSD")
        style_legend(self.ax_msd.legend(loc="upper left"))

        # ---- 控制面板 ----
        panel = ControlPanel("布朗运动", lead="花粉受液体分子随机碰撞，绘制轨迹并估计扩散常数。")
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

        self.arrow_check = QCheckBox("轨迹方向箭头")
        self.arrow_check.setChecked(True)
        self.arrow_check.toggled.connect(self._toggle_arrow)
        self.vector_check = QCheckBox("液体速度矢量")
        self.vector_check.setChecked(True)
        self.vector_check.toggled.connect(self._toggle_vector)
        self.fade_check = QCheckBox("轨迹渐隐")
        self.fade_check.setChecked(False)
        self.fade_check.toggled.connect(self._toggle_fade)
        panel.add(self.arrow_check)
        panel.add(self.vector_check)
        panel.add(self.fade_check)

        self.metrics = MetricGrid("理论 D", "估计 D", "花粉碰撞", "液体碰撞", "时长")
        panel.add(self.metrics)

        self.pause_button = QPushButton("暂停")
        self.pause_button.setObjectName("primaryButton")
        self.pause_button.setCheckable(True)
        self.pause_button.clicked.connect(self._toggle_pause)
        reset_button = QPushButton("清空轨迹")
        reset_button.clicked.connect(self._reset)
        panel.add(ButtonRow(self.pause_button, reset_button))
        panel.finish()

        self.workbench = WorkbenchPanel(
            panel, "花粉粒子运动轨迹", self.scene_canvas, "均方位移 MSD", self.chart_canvas
        )
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.workbench)

        self.timer = QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self._tick)
        self.timer.start()
        self._update_plot(full=True)

    def _parameters_changed(self, _value: float) -> None:
        self.model.set_parameters(self.mass.value, int(self.molecules.value))
        self._update_metrics()

    def _toggle_arrow(self, checked: bool) -> None:
        self.show_arrow = checked

    def _toggle_vector(self, checked: bool) -> None:
        self.show_vector = checked

    def _toggle_fade(self, checked: bool) -> None:
        self.trail_fade = checked
        self._update_plot(full=False)

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
        self._update_plot(full=True)

    def _tick(self) -> None:
        self.model.step(substeps=4)
        self.frame_count += 1
        self._update_plot(full=self.frame_count % 12 == 0)

    def _update_plot(self, *, full: bool) -> None:
        # 液体分子层 + 速度矢量
        self.liquid_points.set_offsets(self.model.liquid_positions)
        if self.show_vector:
            segments = self._vector_segments()
            self.liquid_vectors.set_segments(segments)
            self.liquid_vectors.set_visible(bool(segments))
        else:
            self.liquid_vectors.set_visible(False)

        # 花粉轨迹：默认完整保留；开启渐隐后旧段暗淡 → 新段鲜亮
        points = np.asarray(self.model.path)
        if len(points) > 1:
            segments = [
                (tuple(points[i]), tuple(points[i + 1])) for i in range(len(points) - 1)
            ]
            self.path_segments.set_segments(segments)
            if self.trail_fade:
                alphas = np.linspace(0.12, 0.9, len(segments))
                self.path_segments.set_color([(*_PATH_RGB, float(a)) for a in alphas])
                self.path_segments.set_linewidths(np.linspace(0.6, 1.6, len(segments)))
            else:
                self.path_segments.set_color([(*_PATH_RGB, 0.55)])
                self.path_segments.set_linewidths(1.2)
            self.path_segments.set_visible(True)
        else:
            self.path_segments.set_visible(False)

        # 碰撞高亮点：花粉表面最近的撞击位置
        recent_collisions = np.asarray(self.model.recent_collisions)
        if len(recent_collisions):
            self.collision_points.set_offsets(recent_collisions)
            self.collision_points.set_visible(True)
        else:
            self.collision_points.set_visible(False)

        # 花粉粒子
        pollen = self.model.position
        self.pollen_point.set_offsets(pollen[None, :])
        radius = self.model.params.pollen_radius
        # 面积点：让粒子直径约占盒子宽度的 5%，避免盖住轨迹
        size = 160 + 320 * (radius - 0.05) / 0.065
        self.pollen_point.set_sizes([size])

        # 方向箭头（从花粉表面向外延伸，指向速度方向）
        self.direction_arrow.set_visible(self.show_arrow)
        if self.show_arrow:
            velocity = self.model.velocity
            speed = float(np.linalg.norm(velocity))
            if speed > 1e-6:
                direction = velocity / speed
                # 起点在球表面外（1.1×半径），杆长随速率增长，清晰伸出球体
                start = pollen + direction * radius * 1.1
                length = min(0.22, 0.03 + speed * 0.15)
                tip = start + direction * length
                self.direction_arrow.set_positions(start, tip)
                self.direction_arrow.set_visible(True)
            else:
                self.direction_arrow.set_visible(False)

        self.scene_canvas.draw_idle()

        if full:
            lag, msd = self.model.msd_curve()
            self.msd_line.set_data(lag, msd)
            if len(lag):
                theory = 4.0 * self.model.params.theoretical_diffusion * lag
                self.theory_line.set_data(lag, theory)
                self.ax_msd.relim()
                self.ax_msd.autoscale_view()
            self._update_metrics()
        self.chart_canvas.draw_idle()

    def _vector_segments(self) -> list[tuple[tuple[float, float], tuple[float, float]]]:
        """液体分子速度方向的短线段（对齐 Web 端的速度矢量呈现）。"""

        positions = self.model.liquid_positions
        velocities = self.model.liquid_velocities
        segments = []
        for position, velocity in zip(positions, velocities, strict=True):
            speed = float(np.linalg.norm(velocity))
            if speed < 1e-6:
                continue
            direction = velocity / speed
            length = 0.008 + min(0.02, speed * 0.012)
            tail = position - direction * length
            segments.append((tuple(tail), tuple(position)))
        return segments

    def _update_metrics(self) -> None:
        d_hat = self.model.empirical_diffusion()
        d_text = "采样不足" if np.isnan(d_hat) else f"{d_hat:.3f}"
        self.metrics.set_values({
            "理论 D": f"{self.model.params.theoretical_diffusion:.3f}",
            "估计 D": d_text,
            "花粉碰撞": str(self.model.collision_count),
            "液体碰撞": str(self.model.liquid_collision_count),
            "时长": f"{self.model.elapsed:.2f}",
        })
