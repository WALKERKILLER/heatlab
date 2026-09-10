"""In-memory live simulation sessions for HeatLab Web."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from typing import Any
from uuid import uuid4

import numpy as np
from scipy.stats import binom

from heatlab.constants import DEFAULT_SEED, STANDARD_ATMOSPHERE
from heatlab.models import (
    BrownianModel,
    GaltonModel,
    HeatExchangeModel,
    IdealGasModel,
    MaxwellModel,
)
from heatlab.randomness import RandomManager


def _to_list(values: np.ndarray | list[Any], *, limit: int | None = None) -> list[Any]:
    data = np.asarray(values, dtype=float)
    if limit is not None and len(data) > limit:
        data = data[-limit:]
    return data.tolist()


def _liquid_speed_distribution_payload(
    speeds: np.ndarray, sigma: float, bins: int = 30
) -> dict[str, Any]:
    """2-D Maxwell-Boltzmann histogram (f(v)=v/σ²·exp(-v²/2σ²)) for liquids."""

    if len(speeds) == 0 or sigma <= 0.0:
        return {"speed_hist_v": [], "speed_hist_f": [], "speed_theory_v": [], "speed_theory_f": []}
    # Keep the 1–100 UI range useful: a single molecule still has a valid
    # speed sample, so use a fixed positive range instead of dropping it.
    upper = max(3.0 * sigma, float(np.max(speeds)) * 1.1)
    hist_counts, bin_edges = np.histogram(speeds, bins=bins, range=(0.0, upper), density=True)
    bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])
    theory_v = np.linspace(0.0, float(bin_edges[-1]), 120)
    theory_f = (theory_v / sigma**2) * np.exp(-(theory_v**2) / (2.0 * sigma**2))
    return {
        "speed_hist_v": _to_list(bin_centers),
        "speed_hist_f": _to_list(hist_counts),
        "speed_theory_v": _to_list(theory_v),
        "speed_theory_f": _to_list(theory_f),
    }


@dataclass
class LiveSession:
    """One browser client owns one multi-topic simulation session."""

    seed: int
    session_id: str = field(default_factory=lambda: uuid4().hex)
    ideal: IdealGasModel = field(init=False)
    heat_exchange: HeatExchangeModel = field(init=False)
    ideal_experiment_mode: str = field(default="free", init=False)
    brownian: BrownianModel = field(init=False)
    maxwell: MaxwellModel = field(init=False)
    galton: GaltonModel = field(init=False)
    galton_batch: Any = field(default=None, init=False)
    galton_row: int = field(default=0, init=False)
    galton_finished: bool = field(default=True, init=False)
    lock: Lock = field(default_factory=Lock, repr=False)
    # 理想气体相图几何缓存：粒子每帧 step 时宏观状态不变，
    # 避免每帧重算 PV=nRT 曲面 / 等值线族 / 过程线这些大数组。
    _ideal_geometry_signature: str = field(default="", init=False)
    _ideal_process_line: Any = field(default=None, init=False)
    _ideal_process_line_3d: Any = field(default=None, init=False)
    _ideal_surface: Any = field(default=None, init=False)
    _ideal_planar: Any = field(default=None, init=False)

    def __post_init__(self) -> None:
        self.reset(self.seed)

    def reset(self, seed: int | None = None) -> None:
        if seed is not None:
            self.seed = int(seed)
        manager = RandomManager(self.seed)
        self.ideal = IdealGasModel(manager.stream("ideal-gas"))
        self.heat_exchange = HeatExchangeModel(manager.stream("ideal-gas-heat-exchange"))
        self.ideal_experiment_mode = "free"
        self.brownian = BrownianModel(manager.stream("brownian"))
        self.maxwell = MaxwellModel(manager.stream("maxwell"))
        self.galton = GaltonModel(manager.stream("galton"))
        self.galton_batch = None
        self.galton_row = 0
        self.galton_finished = True
        self._ideal_geometry_signature = ""
        self._ideal_process_line = None
        self._ideal_process_line_3d = None
        self._ideal_surface = None
        self._ideal_planar = None

    # ---- ideal gas ----
    def set_ideal(
        self,
        temperature_c: float | None,
        pressure_atm: float,
        process_mode: str | None = None,
        *,
        experiment_mode: str | None = None,
        volume_litre: float | None = None,
        demo_particle_count: int | None = None,
        barrier: str | None = None,
        temperature_left_c: float | None = None,
        temperature_right_c: float | None = None,
    ) -> None:
        mode = experiment_mode or process_mode or self.ideal_experiment_mode
        if mode == "heat-exchange":
            self.heat_exchange.configure(
                barrier=barrier,
                temperature_left_c=temperature_left_c,
                temperature_right_c=temperature_right_c,
                demo_particle_count=demo_particle_count,
            )
            self.ideal.experiment_mode = "heat-exchange"
            self.ideal.work_by_gas_j = 0.0
            self.ideal.heat_added_j = 0.0
            self.ideal_experiment_mode = mode
            return
        self.ideal_experiment_mode = mode
        if mode in IdealGasModel.SINGLE_EXPERIMENTS:
            self.ideal.configure_experiment(
                mode,
                temperature_c=temperature_c,
                pressure_atm=pressure_atm,
                volume_litre=volume_litre,
                demo_particle_count=demo_particle_count,
            )
        else:
            if process_mode is not None and process_mode != self.ideal.state.process_mode:
                self.ideal.set_process_mode(process_mode)
            self.ideal.set_conditions(
                self.ideal.state.temperature_c if temperature_c is None else temperature_c,
                pressure_atm,
            )

    def step_ideal(self, steps: int = 1) -> dict[str, Any]:
        for _ in range(max(1, steps)):
            if self.ideal_experiment_mode == "heat-exchange":
                self.heat_exchange.step()
            else:
                self.ideal.step()
        return self.snapshot_ideal()

    def snapshot_ideal(self) -> dict[str, Any]:
        if self.ideal_experiment_mode == "heat-exchange":
            return self._snapshot_heat_exchange()
        state = self.ideal.state
        history = np.asarray(self.ideal.phase_history, dtype=float)
        kinetic_atm = float(self.ideal.kinetic_pressure_pa() / STANDARD_ATMOSPHERE)
        # 相图几何（曲面/等值线族/过程线）只随宏观状态变化：
        # 粒子每帧 step 时状态不变 → 直接复用缓存，避免每帧重算大数组。
        signature = (
            f"{self.ideal_experiment_mode}|{state.process_mode}|{state.temperature_c:.1f}|"
            f"{state.pressure_atm:.3f}|{state.volume_litre:.4f}"
        )
        if signature != self._ideal_geometry_signature:
            self._ideal_geometry_signature = signature
            self._ideal_process_line = self.ideal.process_line()
            self._ideal_process_line_3d = self.ideal.process_line_3d()
            self._ideal_surface = self.ideal.pvt_surface()
            self._ideal_planar = self.ideal.planar_families()
        process_line = self._ideal_process_line
        process_line_3d = self._ideal_process_line_3d
        surface_p, surface_v, surface_t = self._ideal_surface
        planar = self._ideal_planar
        is_energy_mode = self.ideal_experiment_mode in ("adiabatic", "first-law")
        delta_u = self.ideal.internal_energy_j - self.ideal.adiabatic_initial_internal_energy_j
        heat_added_j = self.ideal.heat_added_j if is_energy_mode else 0.0
        work_by_gas_j = self.ideal.work_by_gas_j if is_energy_mode else 0.0
        observables = {
            "pressure_pa": state.pressure_pa,
            "pressure_atm": state.pressure_atm,
            "volume_m3": state.volume_m3,
            "volume_litre": state.volume_litre,
            "temperature_k": state.temperature_k,
            "mean_translational_kinetic_energy_j": state.mean_translational_kinetic_energy_j,
            "mean_speed_mps": self.ideal.mean_speed_mps,
            "rms_speed_mps": self.ideal.rms_speed_mps,
            "kinetic_pressure_pa": self.ideal.kinetic_pressure_pa(),
            "kinetic_pressure_atm": kinetic_atm,
            "internal_energy_j": self.ideal.internal_energy_j,
            "heat_added_j": heat_added_j,
            "work_by_gas_j": work_by_gas_j,
            "delta_internal_energy_j": delta_u if is_energy_mode else 0.0,
            "first_law_residual_j": (
                heat_added_j - delta_u - work_by_gas_j
                if is_energy_mode
                else 0.0
            ),
        }
        return {
            "experiment_mode": self.ideal_experiment_mode,
            "temperature_c": state.temperature_c,
            "pressure_atm": state.pressure_atm,
            "temperature_k": state.temperature_k,
            "volume_litre": state.volume_litre,
            "reference_volume_litre": self.ideal.reference_volume_litre,
            "adiabatic_reference_volume_litre": self.ideal.adiabatic_reference_volume_litre,
            "box_width": self.ideal.box_width,
            "box_length": self.ideal.box_length,
            "box_height": self.ideal.box_height,
            "box_depth": self.ideal.box_depth,
            "kinetic_pressure_atm": kinetic_atm,
            "positions": _to_list(self.ideal.display_positions),
            "speeds": _to_list(self.ideal.speeds),
            # Macroscopic PV=nRT path (grows when user moves sliders)
            "phase_history": _to_list(history),
            "process_mode": state.process_mode,
            "observables": observables,
            "scene": {
                "kind": "single-chamber",
                "positions": _to_list(self.ideal.display_positions),
                "speeds": _to_list(self.ideal.speeds),
                "box": [self.ideal.box_length, self.ideal.box_height, self.ideal.box_depth],
            },
            "chart": {
                "kind": {
                    "temperature-micro": "p-t",
                    "pressure-micro": "p-v",
                    "isothermal": "p-v",
                    "isochoric": "p-t",
                    "isobaric": "v-t",
                    "adiabatic": "p-v",
                    "first-law": "p-v",
                }.get(self.ideal_experiment_mode, "p-v"),
                "current": [state.pressure_atm, state.volume_litre, state.temperature_k],
            },
            # Current-mode theoretical line in (P, V); None in free mode
            "process_line": (
                {"points": _to_list(np.column_stack(process_line))}
                if process_line is not None
                else None
            ),
            # Current-mode theoretical line in (P, V, T) for the P-V-T phase diagram
            "process_line_3d": (
                {"points": _to_list(np.column_stack(process_line_3d))}
                if process_line_3d is not None
                else None
            ),
            # Full PV=nRT surface mesh (P / atm, V / L, T / K) for the phase diagram
            "pvt_surface": {
                "x": _to_list(surface_p),
                "y": _to_list(surface_v),
                "z": _to_list(surface_t),
            },
            # 大学物理热力学平面图数据（P-V 等温族 / P-T 等容族 / V-T 等压族）
            "planar": planar,
        }

    def _snapshot_heat_exchange(self) -> dict[str, Any]:
        model = self.heat_exchange
        state = model.state
        left_pressure_atm = state.pressure_left_pa / STANDARD_ATMOSPHERE
        right_pressure_atm = state.pressure_right_pa / STANDARD_ATMOSPHERE
        history = np.asarray(model.temperature_history, dtype=float)
        left = {
            "temperature_c": state.temperature_left_c,
            "temperature_k": state.temperature_left_k,
            "pressure_pa": state.pressure_left_pa,
            "pressure_atm": left_pressure_atm,
            "volume_litre": state.volume_each_m3 * 1_000.0,
            "internal_energy_j": state.internal_energy_left_j,
            "positions": _to_list(model.positions_left),
            "speeds": _to_list(model.speeds_left),
        }
        right = {
            "temperature_c": state.temperature_right_c,
            "temperature_k": state.temperature_right_k,
            "pressure_pa": state.pressure_right_pa,
            "pressure_atm": right_pressure_atm,
            "volume_litre": state.volume_each_m3 * 1_000.0,
            "internal_energy_j": state.internal_energy_right_j,
            "positions": _to_list(model.positions_right),
            "speeds": _to_list(model.speeds_right),
        }
        return {
            "experiment_mode": "heat-exchange",
            "process_mode": "heat-exchange",
            "temperature_c": (state.temperature_left_c + state.temperature_right_c) / 2.0,
            "temperature_k": (state.temperature_left_k + state.temperature_right_k) / 2.0,
            "pressure_atm": (left_pressure_atm + right_pressure_atm) / 2.0,
            "volume_litre": 2.0 * state.volume_each_m3 * 1_000.0,
            "box_width": model.box_width,
            "box_length": model.box_width,
            "box_height": model.box_height,
            "box_depth": model.box_depth,
            "kinetic_pressure_atm": (
                model.kinetic_pressure_left_pa() + model.kinetic_pressure_right_pa()
            ) / (2.0 * STANDARD_ATMOSPHERE),
            "positions": _to_list(model.positions),
            "speeds": _to_list(np.concatenate((model.speeds_left, model.speeds_right))),
            "phase_history": [],
            "process_line": None,
            "process_line_3d": None,
            "pvt_surface": {"x": [], "y": [], "z": []},
            "planar": {"pv": [], "pt": [], "vt": []},
            "observables": {
                "temperature_left_c": state.temperature_left_c,
                "temperature_right_c": state.temperature_right_c,
                "temperature_left_k": state.temperature_left_k,
                "temperature_right_k": state.temperature_right_k,
                "pressure_left_pa": state.pressure_left_pa,
                "pressure_right_pa": state.pressure_right_pa,
                "pressure_left_atm": left_pressure_atm,
                "pressure_right_atm": right_pressure_atm,
                "mean_pressure_atm": (left_pressure_atm + right_pressure_atm) / 2.0,
                "kinetic_pressure_left_atm": model.kinetic_pressure_left_pa() / STANDARD_ATMOSPHERE,
                "kinetic_pressure_right_atm": model.kinetic_pressure_right_pa() / STANDARD_ATMOSPHERE,
                "volume_each_m3": state.volume_each_m3,
                "heat_rate_w": model.heat_rate_w,
                "heat_transferred_j": model.heat_transferred_j,
                "internal_energy_left_j": state.internal_energy_left_j,
                "internal_energy_right_j": state.internal_energy_right_j,
                "internal_energy_total_j": state.internal_energy_left_j + state.internal_energy_right_j,
            },
            "scene": {
                "kind": "two-chamber",
                "divider": state.barrier,
                "divider_x": 0.5,
                "left": left,
                "right": right,
                "box": [model.box_width, model.box_height, model.box_depth],
            },
            "chart": {
                "kind": "temperature-time",
                "points": _to_list(history),
            },
            "chambers": {"left": left, "right": right},
            "barrier": state.barrier,
            "elapsed_s": model.elapsed_s,
        }

    # ---- brownian ----
    def set_brownian(self, mass_ratio: float, molecule_count: int) -> None:
        self.brownian.set_parameters(mass_ratio, molecule_count)

    def step_brownian(self, steps: int = 1) -> dict[str, Any]:
        for _ in range(max(1, steps)):
            self.brownian.step(substeps=4)
        return self.snapshot_brownian()

    def reset_brownian(self) -> dict[str, Any]:
        self.brownian.reset()
        return self.snapshot_brownian()

    def snapshot_brownian(self) -> dict[str, Any]:
        path = np.asarray(self.brownian.path, dtype=float)
        lag, msd = self.brownian.msd_curve()
        d_hat = self.brownian.empirical_diffusion()
        liquid_speeds = np.asarray(self.brownian.liquid_speeds, dtype=float)
        return {
            "mass_ratio": self.brownian.params.mass_ratio,
            "molecule_count": self.brownian.params.molecule_count,
            "elapsed": self.brownian.elapsed,
            "theoretical_D": self.brownian.params.theoretical_diffusion,
            "empirical_D": None if np.isnan(d_hat) else float(d_hat),
            "path": _to_list(path, limit=2_000),
            # 液体粒子层：位置 / 速度 / 速率（前端画热运动场景、速度分布与方向箭头）
            "liquid_positions": _to_list(self.brownian.liquid_positions),
            "liquid_velocities": _to_list(self.brownian.liquid_velocities),
            "liquid_speeds": _to_list(liquid_speeds),
            "liquid_sigma": self.brownian.liquid_speed_sigma,
            "liquid_collision_count": self.brownian.liquid_collision_count,
            # 花粉粒子：位置 / 速度 / 半径（前端画大颗粒与方向箭头）
            "pollen_position": _to_list(self.brownian.position),
            "pollen_velocity": _to_list(self.brownian.velocity),
            "pollen_radius": self.brownian.params.pollen_radius,
            "collision_count": self.brownian.collision_count,
            "recent_collisions": _to_list(np.asarray(self.brownian.recent_collisions)),
            "msd_lag": _to_list(lag),
            "msd": _to_list(msd),
            # 液体速率分布直方图 + 2-D 麦克斯韦理论曲线
            **(_liquid_speed_distribution_payload(liquid_speeds, self.brownian.liquid_speed_sigma)),
        }

    # ---- maxwell ----
    def set_maxwell(self, temperature_c: float) -> None:
        self.maxwell.set_temperature(temperature_c)

    def step_maxwell(self, steps: int = 1) -> dict[str, Any]:
        for _ in range(max(1, steps)):
            self.maxwell.step()
        return self.snapshot_maxwell(include_histogram=False)

    def reset_maxwell(self) -> dict[str, Any]:
        self.maxwell.reset()
        return self.snapshot_maxwell(include_histogram=True)

    def snapshot_maxwell(self, *, include_histogram: bool = True) -> dict[str, Any]:
        velocity, density = self.maxwell.distribution_curve()
        comp_velocity, comp_density = self.maxwell.component_curve()
        payload: dict[str, Any] = {
            "temperature_c": self.maxwell.state.temperature_c,
            "most_probable_speed": self.maxwell.most_probable_speed,
            "mean_speed": self.maxwell.mean_speed,
            "rms_speed": self.maxwell.rms_speed,
            "positions": _to_list(self.maxwell.positions),
            "speeds": _to_list(self.maxwell.speeds),
            "pdf_v": _to_list(velocity),
            "pdf_f": _to_list(density),
            "component_pdf_v": _to_list(comp_velocity),
            "component_pdf_f": _to_list(comp_density),
            # y 轴固定上限（0 °C 峰值）：温度升高时曲线右移、峰值变矮，
            # 避免坐标轴自动缩放造成“变形”观感。
            "y_max_fixed": self.maxwell.fixed_pdf_peak,
            "component_y_max_fixed": self.maxwell.fixed_component_peak,
        }
        if include_histogram:
            samples = self.maxwell.sampled_speeds(3_000)
            hist_counts, bin_edges = np.histogram(samples, bins=36, density=True)
            bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])
            payload["hist_v"] = _to_list(bin_centers)
            payload["hist_f"] = _to_list(hist_counts)

            comp_samples = self.maxwell.sampled_components(3_000)
            comp_counts, comp_edges = np.histogram(comp_samples, bins=44, density=True)
            comp_centers = 0.5 * (comp_edges[:-1] + comp_edges[1:])
            payload["component_hist_v"] = _to_list(comp_centers)
            payload["component_hist_f"] = _to_list(comp_counts)
        return payload

    # ---- galton ----
    def start_galton(self, particle_count: int) -> dict[str, Any]:
        self.galton_batch = self.galton.simulate(particle_count)
        self.galton_row = 0
        self.galton_finished = False
        return self.snapshot_galton()

    def step_galton(self, steps: int = 1) -> dict[str, Any]:
        if self.galton_batch is None:
            self.start_galton(50)
        rows = self.galton.params.rows
        self.galton_row = min(rows, self.galton_row + max(1, steps))
        if self.galton_row >= rows:
            self.galton_finished = True
        return self.snapshot_galton()

    def snapshot_galton(self) -> dict[str, Any]:
        rows = self.galton.params.rows
        bins = list(range(rows + 1))
        if self.galton_batch is None:
            return {
                "rows": rows,
                "particle_count": 0,
                "bins": bins,
                "counts": [0] * (rows + 1),
                "probabilities": [0.0] * (rows + 1),
                "theoretical": _to_list(binom.pmf(np.arange(rows + 1), rows, 0.5)),
                "paths": [],
                "row": 0,
                "finished": True,
                "particle_xy": [],
                "path_prefixes": [],
                "sample_mean": 0.0,
                "sample_variance": 0.0,
            }

        batch = self.galton_batch
        row = min(self.galton_row, rows)
        # 每粒子的当前动画行路径：从顶部漏斗落到当前行（含当前行钉）
        path_prefixes = batch.paths[:, : row + 1]
        # 粒子当前坐标：仍在动 → 当前动画行；全部完成 → 停在各自狭槽内
        if self.galton_finished:
            particle_xy = [[float(x), float(-rows)] for x in batch.paths[:, -1]]
        else:
            particle_xy = [[float(x), float(-row)] for x in batch.paths[:, row]]

        sample_mean = float(np.average(bins, weights=batch.counts)) if batch.counts.sum() else 0.0
        sample_var = (
            float(np.average((np.asarray(bins) - sample_mean) ** 2, weights=batch.counts))
            if batch.counts.sum()
            else 0.0
        )
        return {
            "rows": rows,
            "particle_count": int(batch.counts.sum()),
            "bins": bins,
            "counts": _to_list(batch.counts),
            "probabilities": _to_list(batch.probabilities),
            "theoretical": _to_list(batch.theoretical),
            "paths": _to_list(batch.paths, limit=60),
            "row": row,
            "finished": self.galton_finished,
            "particle_xy": _to_list(np.asarray(particle_xy, dtype=float)),
            "path_prefixes": _to_list(path_prefixes),
            "sample_mean": sample_mean,
            "sample_variance": sample_var,
        }


class SessionStore:
    """Thread-safe store of live sessions (single-process Flask)."""

    def __init__(self) -> None:
        self._sessions: dict[str, LiveSession] = {}
        self._lock = Lock()

    def create(self, seed: int = DEFAULT_SEED) -> LiveSession:
        session = LiveSession(seed=seed)
        with self._lock:
            self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> LiveSession | None:
        with self._lock:
            return self._sessions.get(session_id)

    def get_or_create(self, session_id: str | None, seed: int = DEFAULT_SEED) -> LiveSession:
        if session_id:
            existing = self.get(session_id)
            if existing is not None:
                return existing
        return self.create(seed)


STORE = SessionStore()
