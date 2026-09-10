"""Ideal-gas molecular-motion model for the thermodynamics tab."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.random import Generator

from heatlab.constants import (
    AVOGADRO,
    BOLTZMANN,
    CELSIUS_OFFSET,
    GAS_CONSTANT,
    NITROGEN_MOLECULE_MASS_KG,
    REFERENCE_PRESSURE_PA,
    REFERENCE_TEMPERATURE_K,
    STANDARD_ATMOSPHERE,
)


def _reflect_axis(
    positions: np.ndarray,
    velocities: np.ndarray,
    axis: int,
    low: float,
    high: float,
) -> None:
    """Reflect an axis robustly, including more than one wall crossing per step."""
    width = high - low
    raw = positions[:, axis]
    travel = raw - low
    folded = np.mod(travel, 2.0 * width)
    positions[:, axis] = np.where(
        folded <= width,
        low + folded,
        high - (folded - width),
    )
    crossed_odd_times = np.mod(np.floor(travel / width), 2.0) != 0.0
    velocities[crossed_odd_times, axis] *= -1.0


@dataclass(slots=True)
class IdealGasState:
    temperature_c: float = 20.0
    amount_mol: float = 1.0e-3
    # ``volume_m3`` is the independent geometric state. Pressure is derived
    # from the ideal-gas law so a process cannot leave T, p and V inconsistent.
    volume_m3: float | None = None
    particle_count: int = 180
    molecule_mass_kg: float = NITROGEN_MOLECULE_MASS_KG
    # 准静态过程模式："free" 自由 | "isothermal" 等温 | "isobaric" 等压 | "isochoric" 等容
    process_mode: str = "free"

    def __post_init__(self) -> None:
        if not np.isfinite(self.temperature_c) or self.temperature_c <= -CELSIUS_OFFSET:
            raise ValueError("temperature_c must be finite and above absolute zero")
        if not np.isfinite(self.amount_mol) or self.amount_mol <= 0.0:
            raise ValueError("amount_mol must be finite and positive")
        if not np.isfinite(self.molecule_mass_kg) or self.molecule_mass_kg <= 0.0:
            raise ValueError("molecule_mass_kg must be finite and positive")
        if not isinstance(self.particle_count, (int, np.integer)) or self.particle_count <= 0:
            raise ValueError("particle_count must be a positive integer")
        if self.volume_m3 is None:
            self.volume_m3 = (
                self.amount_mol * GAS_CONSTANT * (self.temperature_c + CELSIUS_OFFSET)
                / STANDARD_ATMOSPHERE
            )
        if not np.isfinite(self.volume_m3) or self.volume_m3 <= 0.0:
            raise ValueError("volume_m3 must be finite and positive")

    @property
    def temperature_k(self) -> float:
        return self.temperature_c + CELSIUS_OFFSET

    @property
    def pressure_pa(self) -> float:
        return self.amount_mol * GAS_CONSTANT * self.temperature_k / self.volume_m3

    @property
    def pressure_atm(self) -> float:
        return self.pressure_pa / STANDARD_ATMOSPHERE

    @property
    def volume_litre(self) -> float:
        return self.volume_m3 * 1_000.0

    @property
    def molecule_count_physical(self) -> float:
        return self.amount_mol * AVOGADRO

    @property
    def mean_translational_kinetic_energy_j(self) -> float:
        """平均平动动能；不等同于双原子气体的总内能。"""
        return 1.5 * BOLTZMANN * self.temperature_k


@dataclass(slots=True)
class IdealGasModel:
    SINGLE_EXPERIMENTS = {
        "free",
        "temperature-micro",
        "pressure-micro",
        "isothermal",
        "isochoric",
        "isobaric",
        "adiabatic",
        "first-law",
    }
    ADIABATIC_GAMMA = 1.4  # 当前模型按氮气/双原子理想气体近似

    rng: Generator
    state: IdealGasState = field(default_factory=IdealGasState)
    # New document-facing modes share this single particle model. ``free``
    # and the old process names remain valid for backwards compatibility.
    experiment_mode: str = "free"
    positions: np.ndarray = field(init=False)
    velocities_si: np.ndarray = field(init=False)
    phase_history: list[tuple[float, float, float]] = field(default_factory=list)
    _box_length: float = field(init=False, default=1.0)
    _locked_temperature_c: float = field(init=False, default=20.0)
    _locked_pressure_atm: float = field(init=False, default=1.0)
    _locked_volume_m3: float = field(init=False, default=0.0)
    _adiabatic_initial_temperature_k: float = field(init=False, default=0.0)
    _adiabatic_initial_volume_m3: float = field(init=False, default=0.0)
    _adiabatic_initial_internal_energy_j: float = field(init=False, default=0.0)
    work_by_gas_j: float = field(init=False, default=0.0)
    heat_added_j: float = field(init=False, default=0.0)

    def __post_init__(self) -> None:
        self._box_length = self._display_length()
        self._locked_temperature_c = self.state.temperature_c
        self._locked_pressure_atm = self.state.pressure_atm
        self._locked_volume_m3 = self.state.volume_m3
        self.positions = self._random_positions()
        self.velocities_si = self._sample_velocities()
        self._append_phase_point()

    def _display_length(self) -> float:
        # 显示体积 ∝ T/P，长度方向随状态方程缩放，高度与深度固定为 1.0。
        ratio = (
            (self.state.temperature_k / REFERENCE_TEMPERATURE_K)
            / (self.state.pressure_pa / REFERENCE_PRESSURE_PA)
        )
        return float(np.clip(ratio, 0.45, 1.6))

    def _random_positions(self) -> np.ndarray:
        points = self.rng.random((self.state.particle_count, 3))
        points[:, 0] *= self._box_length
        return points

    def _sample_velocities(self) -> np.ndarray:
        sigma = np.sqrt(BOLTZMANN * self.state.temperature_k / self.state.molecule_mass_kg)
        values = self.rng.normal(0.0, sigma, size=(self.state.particle_count, 3))
        values -= values.mean(axis=0, keepdims=True)
        return values

    @property
    def box_length(self) -> float:
        return self._box_length

    @property
    def box_width(self) -> float:
        """兼容别名：长度方向的显示尺寸。"""
        return self._box_length

    @property
    def box_height(self) -> float:
        return 1.0

    @property
    def box_depth(self) -> float:
        return 1.0

    @property
    def display_positions(self) -> np.ndarray:
        return self.positions

    @property
    def speeds(self) -> np.ndarray:
        """各粒子三维速率（m/s），用于按速率着色。"""
        return np.linalg.norm(self.velocities_si, axis=1)

    @property
    def display_velocities(self) -> np.ndarray:
        thermal_rms = np.sqrt(3.0 * BOLTZMANN * self.state.temperature_k / self.state.molecule_mass_kg)
        # 显示速度系数 1.5：让粒子以热速率尺度活跃运动（真实气体观感），
        # 而非 0.5 的“慢漂移”。仅影响可视化，不改变物理状态。
        return self.velocities_si / max(thermal_rms, np.finfo(float).tiny) * 1.5

    @property
    def internal_energy_j(self) -> float:
        """氮气双原子近似的总内能，U=n C_v T。"""
        cv_molar = GAS_CONSTANT / (self.ADIABATIC_GAMMA - 1.0)
        return self.state.amount_mol * cv_molar * self.state.temperature_k

    @property
    def mean_speed_mps(self) -> float:
        """Maxwell 速率分布的理论平均速率。"""
        return float(np.sqrt(8.0 * BOLTZMANN * self.state.temperature_k
                             / (np.pi * self.state.molecule_mass_kg)))

    @property
    def rms_speed_mps(self) -> float:
        return float(np.sqrt(3.0 * BOLTZMANN * self.state.temperature_k
                             / self.state.molecule_mass_kg))

    @property
    def adiabatic_reference_volume_litre(self) -> float:
        return self._adiabatic_initial_volume_m3 * 1_000.0

    @property
    def adiabatic_initial_internal_energy_j(self) -> float:
        return self._adiabatic_initial_internal_energy_j

    @property
    def reference_volume_litre(self) -> float:
        """V₀ used by the document's volume sliders (20 °C, 1 atm)."""
        return (
            self.state.amount_mol * GAS_CONSTANT * REFERENCE_TEMPERATURE_K
            / REFERENCE_PRESSURE_PA
            * 1_000.0
        )

    def configure_experiment(
        self,
        mode: str,
        *,
        temperature_c: float | None = None,
        pressure_atm: float | None = None,
        volume_litre: float | None = None,
        demo_particle_count: int | None = None,
    ) -> None:
        """切换文档中的实验模式，并只应用该模式的独立控制量。"""
        if mode not in self.SINGLE_EXPERIMENTS:
            raise ValueError(f"unknown experiment mode: {mode}")
        for name, value in (
            ("temperature_c", temperature_c),
            ("pressure_atm", pressure_atm),
            ("volume_litre", volume_litre),
        ):
            if value is not None and not np.isfinite(value):
                raise ValueError(f"{name} must be finite")
        if temperature_c is not None and temperature_c <= -CELSIUS_OFFSET:
            raise ValueError("temperature_c must be above absolute zero")
        if demo_particle_count is not None:
            count = int(np.clip(demo_particle_count, 5, 100))
            if count != self.state.particle_count:
                self.state.particle_count = count
                self.reset()

        entering = mode != self.experiment_mode
        if entering:
            self.experiment_mode = mode
            process_mode = {
                "temperature-micro": "isochoric",
                "pressure-micro": "isothermal",
                "first-law": "adiabatic",
            }.get(mode, mode)
            if process_mode in ("free", "isothermal", "isobaric", "isochoric"):
                self.set_process_mode(process_mode)
            else:
                self.state.process_mode = process_mode
            self._locked_temperature_c = self.state.temperature_c
            self._locked_pressure_atm = self.state.pressure_atm
            self._locked_volume_m3 = self.state.volume_m3
            if mode in ("adiabatic", "first-law"):
                self._adiabatic_initial_temperature_k = self.state.temperature_k
                self._adiabatic_initial_volume_m3 = self.state.volume_m3
                self._adiabatic_initial_internal_energy_j = self.internal_energy_j
                self.work_by_gas_j = 0.0
                self.heat_added_j = 0.0
            else:
                self.work_by_gas_j = 0.0
                self.heat_added_j = 0.0

        if mode in ("temperature-micro", "isochoric"):
            self.set_temperature_at_fixed_volume(
                self.state.temperature_c if temperature_c is None else temperature_c
            )
        elif mode in ("pressure-micro", "isothermal"):
            if temperature_c is not None:
                self.set_temperature_at_fixed_volume(temperature_c)
                self._locked_temperature_c = self.state.temperature_c
            self.set_volume(
                self.state.volume_litre if volume_litre is None else volume_litre,
                keep_temperature=True,
            )
        elif mode == "isobaric":
            if pressure_atm is not None:
                self._locked_pressure_atm = float(np.clip(pressure_atm, 0.25, 4.0))
            self.set_temperature_at_fixed_pressure(
                self.state.temperature_c if temperature_c is None else temperature_c
            )
        elif mode in ("adiabatic", "first-law"):
            self.set_adiabatic_volume(
                self.state.volume_litre if volume_litre is None else volume_litre
            )
        else:
            self.set_conditions(
                self.state.temperature_c if temperature_c is None else temperature_c,
                self.state.pressure_atm if pressure_atm is None else pressure_atm,
            )

    def set_temperature_at_fixed_volume(self, temperature_c: float) -> None:
        if not np.isfinite(temperature_c):
            raise ValueError("temperature_c must be finite")
        old_temperature = self.state.temperature_k
        self.state.temperature_c = float(np.clip(temperature_c, 0.0, 100.0))
        self.state.volume_m3 = self._locked_volume_m3
        self._rescale_velocities(old_temperature)
        self._sync_display_length()
        self._append_phase_point()

    def set_temperature_at_fixed_pressure(self, temperature_c: float) -> None:
        if not np.isfinite(temperature_c):
            raise ValueError("temperature_c must be finite")
        old_temperature = self.state.temperature_k
        self.state.temperature_c = float(np.clip(temperature_c, 0.0, 100.0))
        self.state.volume_m3 = (
            self.state.amount_mol * GAS_CONSTANT * self.state.temperature_k
            / (self._locked_pressure_atm * STANDARD_ATMOSPHERE)
        )
        self._rescale_velocities(old_temperature)
        self._sync_display_length()
        self._append_phase_point()

    def set_volume(self, volume_litre: float, *, keep_temperature: bool = True) -> None:
        if not np.isfinite(volume_litre) or volume_litre <= 0.0:
            raise ValueError("volume_litre must be finite and positive")
        old_temperature = self.state.temperature_k
        old_length = self._box_length
        volume_m3 = float(np.clip(volume_litre, 1.0e-9, 1.0e6)) / 1_000.0
        old_pressure_pa = self.state.pressure_pa
        self.state.volume_m3 = volume_m3
        if not keep_temperature:
            self.state.temperature_c = float(np.clip(
                old_pressure_pa * volume_m3 / (self.state.amount_mol * GAS_CONSTANT)
                - CELSIUS_OFFSET,
                0.0,
                100.0,
            ))
        self._rescale_velocities(old_temperature)
        self._sync_display_length(old_length=old_length)
        self._append_phase_point()

    def set_adiabatic_volume(self, volume_litre: float) -> None:
        if not np.isfinite(volume_litre) or volume_litre <= 0.0:
            raise ValueError("volume_litre must be finite and positive")
        if self._adiabatic_initial_volume_m3 <= 0.0:
            self._adiabatic_initial_volume_m3 = self.state.volume_m3
            self._adiabatic_initial_temperature_k = self.state.temperature_k
            self._adiabatic_initial_internal_energy_j = self.internal_energy_j
        old_temperature = self.state.temperature_k
        old_length = self._box_length
        volume_m3 = float(np.clip(volume_litre, 1.0e-9, 1.0e6)) / 1_000.0
        temperature_k = self._adiabatic_initial_temperature_k * (
            self._adiabatic_initial_volume_m3 / volume_m3
        ) ** (self.ADIABATIC_GAMMA - 1.0)
        self.state.volume_m3 = volume_m3
        self.state.temperature_c = float(temperature_k - CELSIUS_OFFSET)
        self._rescale_velocities(old_temperature)
        self._sync_display_length(old_length=old_length)
        self.heat_added_j = 0.0
        self.work_by_gas_j = self._adiabatic_initial_internal_energy_j - self.internal_energy_j
        self._append_phase_point()

    def _rescale_velocities(self, old_temperature_k: float) -> None:
        scale = np.sqrt(self.state.temperature_k / old_temperature_k)
        self.velocities_si *= scale

    def _sync_display_length(self, *, old_length: float | None = None) -> None:
        previous = self._box_length if old_length is None else old_length
        self._box_length = self._display_length()
        self.positions[:, 0] *= self._box_length / previous
        self.positions[:, 0] = np.clip(self.positions[:, 0], 0.0, self._box_length)

    def set_process_mode(self, mode: str) -> None:
        """切换准静态过程模式，并锁定当前 T/P/V 作为该模式的约束锚点。"""
        valid = ("free", "isothermal", "isobaric", "isochoric")
        if mode not in valid:
            raise ValueError(f"unknown process mode: {mode}")
        self.state.process_mode = mode
        self._locked_temperature_c = self.state.temperature_c
        self._locked_pressure_atm = self.state.pressure_atm
        self._locked_volume_m3 = self.state.volume_m3

    def _apply_process_constraints(self, temperature_c: float, pressure_atm: float) -> tuple[float, float]:
        """按当前过程模式把用户请求的 (T, P) 投影到约束空间。

        - 等温：温度锁定在等温线温度；拖动 T 滑条视为更换等温线，拖动 P 执行压缩/膨胀。
        - 等压：压强锁定在等压线压强；拖动 P 视为更换等压线，拖动 T 加热/冷却。
        - 等容：体积锁定；温度驱动压强 P = nRT/V。
        """
        mode = self.state.process_mode
        if mode == "isothermal":
            if abs(float(temperature_c) - self.state.temperature_c) > 1e-9:
                self._locked_temperature_c = float(np.clip(temperature_c, 0.0, 100.0))
            temperature_c = self._locked_temperature_c
            pressure_atm = float(np.clip(pressure_atm, 1.0, 2.0))
        elif mode == "isobaric":
            if abs(float(pressure_atm) - self.state.pressure_atm) > 1e-9:
                self._locked_pressure_atm = float(np.clip(pressure_atm, 1.0, 2.0))
            pressure_atm = self._locked_pressure_atm
            temperature_c = float(np.clip(temperature_c, 0.0, 100.0))
        elif mode == "isochoric":
            temperature_c = float(np.clip(temperature_c, 0.0, 100.0))
            temperature_k = temperature_c + CELSIUS_OFFSET
            volume_m3 = self._locked_volume_m3
            pressure_atm = (
                self.state.amount_mol * GAS_CONSTANT * temperature_k / volume_m3 / STANDARD_ATMOSPHERE
            )
        else:
            temperature_c = float(np.clip(temperature_c, 0.0, 100.0))
            pressure_atm = float(np.clip(pressure_atm, 1.0, 2.0))
        return temperature_c, pressure_atm

    def set_conditions(self, temperature_c: float, pressure_atm: float) -> None:
        if not np.isfinite(temperature_c) or not np.isfinite(pressure_atm):
            raise ValueError("temperature_c and pressure_atm must be finite")
        temperature_c, pressure_atm = self._apply_process_constraints(temperature_c, pressure_atm)

        old_temperature = self.state.temperature_k
        old_length = self._box_length
        self.state.temperature_c = temperature_c
        if self.state.process_mode == "isochoric":
            self.state.volume_m3 = self._locked_volume_m3
        elif self.state.process_mode == "isobaric":
            self.state.volume_m3 = (
                self.state.amount_mol * GAS_CONSTANT * self.state.temperature_k
                / (self._locked_pressure_atm * STANDARD_ATMOSPHERE)
            )
        else:
            self.state.volume_m3 = (
                self.state.amount_mol * GAS_CONSTANT * self.state.temperature_k
                / (pressure_atm * STANDARD_ATMOSPHERE)
            )

        self._rescale_velocities(old_temperature)
        self._sync_display_length(old_length=old_length)
        self._append_phase_point()

    def isotherm_line(self, points: int = 200) -> tuple[np.ndarray, np.ndarray]:
        """等温线的 (P, V) 理论曲线：PV = nRT。"""
        pressures = np.linspace(1.0, 2.0, points)
        volumes = (
            self.state.amount_mol
            * GAS_CONSTANT
            * self.state.temperature_k
            / (pressures * STANDARD_ATMOSPHERE)
            * 1_000.0
        )
        return pressures, volumes

    def isobar_line(self, points: int = 200) -> tuple[np.ndarray, np.ndarray]:
        """等压线的 (P, V) 理论曲线：P-V 图上为水平线，T 取 0–100 °C。"""
        temperatures_k = np.linspace(CELSIUS_OFFSET, CELSIUS_OFFSET + 100.0, points)
        volumes = (
            self.state.amount_mol
            * GAS_CONSTANT
            * temperatures_k
            / (self.state.pressure_pa)
            * 1_000.0
        )
        return np.full_like(temperatures_k, self.state.pressure_atm), volumes

    def isochore_line(self, points: int = 200) -> tuple[np.ndarray, np.ndarray]:
        """等容线的 (P, V) 理论曲线：P-V 图上为竖直线。"""
        pressures = np.linspace(1.0, 2.0, points)
        return pressures, np.full_like(pressures, self.state.volume_litre)

    def adiabatic_line(self, points: int = 200) -> tuple[np.ndarray, np.ndarray]:
        """准静态绝热线的 (P, V) 理论曲线。"""
        volume_m3 = np.linspace(
            self._adiabatic_initial_volume_m3 / 5.0,
            self._adiabatic_initial_volume_m3 * 5.0,
            points,
        )
        pressure_pa = (
            self.state.amount_mol
            * GAS_CONSTANT
            * self._adiabatic_initial_temperature_k
            * (self._adiabatic_initial_volume_m3 / volume_m3) ** (self.ADIABATIC_GAMMA - 1.0)
            / volume_m3
        )
        return pressure_pa / STANDARD_ATMOSPHERE, volume_m3 * 1_000.0

    def process_line(self) -> tuple[np.ndarray, np.ndarray] | None:
        """当前过程模式对应的理论线；自由模式返回 None。"""
        if self.state.process_mode == "isothermal":
            return self.isotherm_line()
        if self.state.process_mode == "isobaric":
            return self.isobar_line()
        if self.state.process_mode == "isochoric":
            return self.isochore_line()
        if self.state.process_mode == "adiabatic":
            return self.adiabatic_line()
        return None

    def process_line_3d(self, points: int = 120) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
        """当前过程模式对应的 3D 理论线（P, V, T 三元组），用于 P-V-T 相图。"""
        mode = self.state.process_mode
        if mode == "isothermal":
            pressures = np.linspace(1.0, 2.0, points)
            volumes = (
                self.state.amount_mol
                * GAS_CONSTANT
                * self.state.temperature_k
                / (pressures * STANDARD_ATMOSPHERE)
                * 1_000.0
            )
            temperatures = np.full_like(pressures, self.state.temperature_k)
            return pressures, volumes, temperatures
        if mode == "isobaric":
            temperatures = np.linspace(CELSIUS_OFFSET, CELSIUS_OFFSET + 100.0, points)
            volumes = (
                self.state.amount_mol
                * GAS_CONSTANT
                * temperatures
                / self.state.pressure_pa
                * 1_000.0
            )
            pressures = np.full_like(temperatures, self.state.pressure_atm)
            return pressures, volumes, temperatures
        if mode == "isochoric":
            pressures = np.linspace(1.0, 2.0, points)
            volumes = np.full_like(pressures, self.state.volume_litre)
            temperatures = (
                pressures
                * STANDARD_ATMOSPHERE
                * (volumes / 1_000.0)
                / (self.state.amount_mol * GAS_CONSTANT)
            )
            return pressures, volumes, temperatures
        if mode == "adiabatic":
            volumes = np.linspace(
                self._adiabatic_initial_volume_m3 / 5.0,
                self._adiabatic_initial_volume_m3 * 5.0,
                points,
            )
            temperatures = self._adiabatic_initial_temperature_k * (
                self._adiabatic_initial_volume_m3 / volumes
            ) ** (self.ADIABATIC_GAMMA - 1.0)
            pressures = (
                self.state.amount_mol * GAS_CONSTANT * temperatures / volumes
                / STANDARD_ATMOSPHERE
            )
            return pressures, volumes * 1_000.0, temperatures
        return None

    def pvt_surface(
        self,
        volume_points: int = 20,
        temperature_points: int = 20,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """生成 P-V-T 曲面网格点（P / atm, V / L, T / K）。

        借鉴 MIT 开源项目 chicolucio/ideal_gases 的网格画法：
        对 (V, T) 做 meshgrid，再用 PV=nRT 逐点计算 P。
        """
        vmin = self.state.volume_litre * 0.35
        vmax = self.state.volume_litre * 2.2
        volumes = np.linspace(vmin, vmax, volume_points)  # L
        temperatures = np.linspace(CELSIUS_OFFSET, CELSIUS_OFFSET + 100.0, temperature_points)  # K
        volume_matrix, temperature_matrix = np.meshgrid(volumes, temperatures)
        pressure_pa = (
            self.state.amount_mol
            * GAS_CONSTANT
            * temperature_matrix
            / (volume_matrix / 1_000.0)
        )
        pressure_atm = pressure_pa / STANDARD_ATMOSPHERE
        return pressure_atm, volume_matrix, temperature_matrix

    def planar_families(self, points: int = 120) -> dict[str, list[dict[str, list[float]]]]:
        """大学物理热力学平面图所需的等值线族数据。

        - ``pv``：P-V 图等温线族（0–100 °C 取 5 条）
        - ``pt``：P-T 图等容线族（当前体积的 0.6/0.9/1.2/1.6 倍）
        - ``vt``：V-T 图等压线族（1.0/1.3/1.6/1.9 atm）
        """
        n = self.state.amount_mol
        pressures = np.linspace(0.9, 2.1, points)
        temperatures_k = np.linspace(CELSIUS_OFFSET, CELSIUS_OFFSET + 100.0, points)

        pv_isotherms: list[dict[str, list[float]]] = []
        for tk in np.linspace(CELSIUS_OFFSET, CELSIUS_OFFSET + 100.0, 5):
            volumes = n * GAS_CONSTANT * tk / (pressures * STANDARD_ATMOSPHERE) * 1_000.0
            pv_isotherms.append({
                "T": float(tk),
                "P": pressures.tolist(),
                "V": volumes.tolist(),
            })

        pt_isochores: list[dict[str, list[float]]] = []
        v_ref = self.state.volume_litre
        for factor in (0.6, 0.9, 1.2, 1.6):
            volume_l = v_ref * factor
            ps = n * GAS_CONSTANT * temperatures_k / (volume_l / 1_000.0) / STANDARD_ATMOSPHERE
            pt_isochores.append({
                "V": float(volume_l),
                "T": temperatures_k.tolist(),
                "P": ps.tolist(),
            })

        vt_isobars: list[dict[str, list[float]]] = []
        for p_atm in (1.0, 1.3, 1.6, 1.9):
            volumes = n * GAS_CONSTANT * temperatures_k / (p_atm * STANDARD_ATMOSPHERE) * 1_000.0
            vt_isobars.append({
                "P": float(p_atm),
                "T": temperatures_k.tolist(),
                "V": volumes.tolist(),
            })

        return {"pv": pv_isotherms, "pt": pt_isochores, "vt": vt_isobars}

    def step(self, dt: float = 0.020) -> None:
        if not np.isfinite(dt) or dt <= 0:
            raise ValueError("dt must be finite and positive")
        self.positions += self.display_velocities * dt

        for axis, upper in ((0, self._box_length), (1, 1.0), (2, 1.0)):
            _reflect_axis(self.positions, self.velocities_si, axis, 0.0, upper)

    def kinetic_pressure_pa(self) -> float:
        """Estimate pressure from the microscopic momentum-flux relation.

        For an isotropic ideal gas, ``P = N m <v_x^2> / V``.  The displayed
        particles are Monte-Carlo samples representing the physical molecules.
        """

        sample_count = self.velocities_si.shape[0]
        if sample_count <= 1:
            return 0.0
        # Velocities are centered to keep the displayed gas at zero net
        # momentum. Correct the finite-sample variance (N-1 denominator) so
        # the pressure estimate remains unbiased for the target temperature.
        mean_vx2 = float(np.mean(self.velocities_si[:, 0] ** 2))
        mean_vx2 *= sample_count / (sample_count - 1)
        return (
            self.state.molecule_count_physical
            * self.state.molecule_mass_kg
            * mean_vx2
            / self.state.volume_m3
        )

    def resample_velocities(self) -> None:
        self.velocities_si = self._sample_velocities()

    def reset(self) -> None:
        self._box_length = self._display_length()
        self.positions = self._random_positions()
        self.velocities_si = self._sample_velocities()
        self.phase_history.clear()
        self._append_phase_point()

    def _append_phase_point(self) -> None:
        point = (self.state.pressure_atm, self.state.volume_litre, self.state.temperature_k)
        if not self.phase_history or not np.allclose(self.phase_history[-1], point):
            self.phase_history.append(point)
            if len(self.phase_history) > 240:
                del self.phase_history[:-240]


@dataclass(slots=True)
class HeatExchangeState:
    """Two equal-volume gas chambers separated by one idealized divider."""

    temperature_left_c: float = 80.0
    temperature_right_c: float = 20.0
    amount_mol: float = 1.0e-3
    volume_each_m3: float | None = None
    particle_count: int = 60
    molecule_mass_kg: float = NITROGEN_MOLECULE_MASS_KG
    barrier: str = "adiabatic"

    def __post_init__(self) -> None:
        if not np.isfinite(self.temperature_left_c) or self.temperature_left_c <= -CELSIUS_OFFSET:
            raise ValueError("temperature_left_c must be finite and above absolute zero")
        if not np.isfinite(self.temperature_right_c) or self.temperature_right_c <= -CELSIUS_OFFSET:
            raise ValueError("temperature_right_c must be finite and above absolute zero")
        if not np.isfinite(self.amount_mol) or self.amount_mol <= 0.0:
            raise ValueError("amount_mol must be finite and positive")
        if not np.isfinite(self.molecule_mass_kg) or self.molecule_mass_kg <= 0.0:
            raise ValueError("molecule_mass_kg must be finite and positive")
        if not isinstance(self.particle_count, (int, np.integer)) or self.particle_count <= 0:
            raise ValueError("particle_count must be a positive integer")
        if self.volume_each_m3 is None:
            mean_temperature_k = (
                self.temperature_left_c + self.temperature_right_c
            ) / 2.0 + CELSIUS_OFFSET
            self.volume_each_m3 = (
                self.amount_mol * GAS_CONSTANT * mean_temperature_k / STANDARD_ATMOSPHERE
            )
        if not np.isfinite(self.volume_each_m3) or self.volume_each_m3 <= 0.0:
            raise ValueError("volume_each_m3 must be finite and positive")
        if self.barrier not in ("adiabatic", "conductive"):
            raise ValueError("barrier must be 'adiabatic' or 'conductive'")

    @property
    def temperature_left_k(self) -> float:
        return self.temperature_left_c + CELSIUS_OFFSET

    @property
    def temperature_right_k(self) -> float:
        return self.temperature_right_c + CELSIUS_OFFSET

    @property
    def molecule_count_physical(self) -> float:
        """Physical molecule count represented by either equal chamber."""
        return self.amount_mol * AVOGADRO

    @property
    def pressure_left_pa(self) -> float:
        return self.amount_mol * GAS_CONSTANT * self.temperature_left_k / self.volume_each_m3

    @property
    def pressure_right_pa(self) -> float:
        return self.amount_mol * GAS_CONSTANT * self.temperature_right_k / self.volume_each_m3

    @property
    def internal_energy_left_j(self) -> float:
        cv_molar = GAS_CONSTANT / (IdealGasModel.ADIABATIC_GAMMA - 1.0)
        return self.amount_mol * cv_molar * self.temperature_left_k

    @property
    def internal_energy_right_j(self) -> float:
        cv_molar = GAS_CONSTANT / (IdealGasModel.ADIABATIC_GAMMA - 1.0)
        return self.amount_mol * cv_molar * self.temperature_right_k


@dataclass(slots=True)
class HeatExchangeModel:
    """Microscopic display plus energy-balanced heat exchange between chambers.

    The divider is the only thermal link. Gas particles remain in their own
    chamber, so the model shows heat transfer without silently modelling gas
    mixing. The fixed conductance is a classroom approximation; energy is
    transferred explicitly between the two internal energies and is capped at
    equilibrium each step.
    """

    rng: Generator
    state: HeatExchangeState = field(default_factory=HeatExchangeState)
    thermal_conductance_w_per_k: float = 0.01
    positions_left: np.ndarray = field(init=False)
    positions_right: np.ndarray = field(init=False)
    velocities_left_si: np.ndarray = field(init=False)
    velocities_right_si: np.ndarray = field(init=False)
    elapsed_s: float = field(default=0.0, init=False)
    heat_transferred_j: float = field(default=0.0, init=False)
    temperature_history: list[tuple[float, float, float]] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        if not np.isfinite(self.thermal_conductance_w_per_k) or self.thermal_conductance_w_per_k < 0.0:
            raise ValueError("thermal_conductance_w_per_k must be finite and non-negative")
        self.positions_left = self._random_positions(0.5)
        self.positions_right = self._random_positions(0.5, x_offset=0.5)
        self.velocities_left_si = self._sample_velocities(self.state.temperature_left_k)
        self.velocities_right_si = self._sample_velocities(self.state.temperature_right_k)
        self._append_temperature_point()

    def _random_positions(self, width: float, *, x_offset: float = 0.0) -> np.ndarray:
        points = self.rng.random((self.state.particle_count, 3))
        points[:, 0] = x_offset + points[:, 0] * width
        return points

    def _sample_velocities(self, temperature_k: float) -> np.ndarray:
        sigma = np.sqrt(BOLTZMANN * temperature_k / self.state.molecule_mass_kg)
        values = self.rng.normal(0.0, sigma, size=(self.state.particle_count, 3))
        values -= values.mean(axis=0, keepdims=True)
        return values

    @property
    def positions(self) -> np.ndarray:
        return np.vstack((self.positions_left, self.positions_right))

    @property
    def speeds_left(self) -> np.ndarray:
        return np.linalg.norm(self.velocities_left_si, axis=1)

    @property
    def speeds_right(self) -> np.ndarray:
        return np.linalg.norm(self.velocities_right_si, axis=1)

    def kinetic_pressure_left_pa(self) -> float:
        """Momentum-flux estimate from the displayed left-chamber sample."""
        sample_count = self.velocities_left_si.shape[0]
        if sample_count <= 1:
            return 0.0
        mean_vx2 = float(np.mean(self.velocities_left_si[:, 0] ** 2))
        mean_vx2 *= sample_count / (sample_count - 1)
        return self.state.molecule_count_physical * self.state.molecule_mass_kg * mean_vx2 / self.state.volume_each_m3

    def kinetic_pressure_right_pa(self) -> float:
        """Momentum-flux estimate from the displayed right-chamber sample."""
        sample_count = self.velocities_right_si.shape[0]
        if sample_count <= 1:
            return 0.0
        mean_vx2 = float(np.mean(self.velocities_right_si[:, 0] ** 2))
        mean_vx2 *= sample_count / (sample_count - 1)
        return self.state.molecule_count_physical * self.state.molecule_mass_kg * mean_vx2 / self.state.volume_each_m3

    @property
    def box_width(self) -> float:
        return 1.0

    @property
    def box_height(self) -> float:
        return 1.0

    @property
    def box_depth(self) -> float:
        return 1.0

    @property
    def heat_rate_w(self) -> float:
        if self.state.barrier != "conductive":
            return 0.0
        return self.thermal_conductance_w_per_k * (
            self.state.temperature_left_k - self.state.temperature_right_k
        )

    def configure(
        self,
        *,
        barrier: str | None = None,
        temperature_left_c: float | None = None,
        temperature_right_c: float | None = None,
        demo_particle_count: int | None = None,
    ) -> None:
        for name, value in (
            ("temperature_left_c", temperature_left_c),
            ("temperature_right_c", temperature_right_c),
        ):
            if value is not None and not np.isfinite(value):
                raise ValueError(f"{name} must be finite")
        if temperature_left_c is not None and temperature_left_c <= -CELSIUS_OFFSET:
            raise ValueError("temperature_left_c must be above absolute zero")
        if temperature_right_c is not None and temperature_right_c <= -CELSIUS_OFFSET:
            raise ValueError("temperature_right_c must be above absolute zero")
        if barrier is not None:
            if barrier not in ("adiabatic", "conductive"):
                raise ValueError("barrier must be 'adiabatic' or 'conductive'")
            self.state.barrier = barrier
        if temperature_left_c is not None:
            self.state.temperature_left_c = float(np.clip(temperature_left_c, 0.0, 100.0))
        if temperature_right_c is not None:
            self.state.temperature_right_c = float(np.clip(temperature_right_c, 0.0, 100.0))
        if demo_particle_count is not None:
            self.state.particle_count = int(np.clip(demo_particle_count, 5, 100))
        self.reset()

    def _rescale_velocities(
        self,
        values: np.ndarray,
        old_temperature_k: float,
        new_temperature_k: float,
    ) -> None:
        values *= np.sqrt(new_temperature_k / old_temperature_k)

    def _move_chamber_particles(
        self,
        positions: np.ndarray,
        velocities: np.ndarray,
        temperature_k: float,
        x_min: float,
        x_max: float,
        dt: float,
    ) -> None:
        thermal_rms = np.sqrt(
            3.0 * BOLTZMANN * temperature_k / self.state.molecule_mass_kg
        )
        positions += velocities / max(thermal_rms, np.finfo(float).tiny) * 1.5 * dt
        for axis, low, high in ((0, x_min, x_max), (1, 0.0, 1.0), (2, 0.0, 1.0)):
            _reflect_axis(positions, velocities, axis, low, high)

    def step(self, dt: float = 0.020) -> None:
        if not np.isfinite(dt) or dt <= 0.0:
            raise ValueError("dt must be finite and positive")
        old_left_k = self.state.temperature_left_k
        old_right_k = self.state.temperature_right_k
        if self.state.barrier == "conductive":
            cv_total = self.state.amount_mol * GAS_CONSTANT / (IdealGasModel.ADIABATIC_GAMMA - 1.0)
            left_energy = cv_total * old_left_k
            right_energy = cv_total * old_right_k
            requested_transfer = self.heat_rate_w * dt
            maximum_without_crossing = 0.5 * abs(left_energy - right_energy)
            transfer = float(
                np.sign(requested_transfer)
                * min(abs(requested_transfer), maximum_without_crossing)
            )
            left_energy -= transfer
            right_energy += transfer
            self.state.temperature_left_c = left_energy / cv_total - CELSIUS_OFFSET
            self.state.temperature_right_c = right_energy / cv_total - CELSIUS_OFFSET
            self.heat_transferred_j += transfer
            self._rescale_velocities(
                self.velocities_left_si, old_left_k, self.state.temperature_left_k
            )
            self._rescale_velocities(
                self.velocities_right_si, old_right_k, self.state.temperature_right_k
            )
        self._move_chamber_particles(
            self.positions_left,
            self.velocities_left_si,
            self.state.temperature_left_k,
            0.0,
            0.5,
            dt,
        )
        self._move_chamber_particles(
            self.positions_right,
            self.velocities_right_si,
            self.state.temperature_right_k,
            0.5,
            1.0,
            dt,
        )
        self.elapsed_s += dt
        self._append_temperature_point()

    def reset(self) -> None:
        self.positions_left = self._random_positions(0.5)
        self.positions_right = self._random_positions(0.5, x_offset=0.5)
        self.velocities_left_si = self._sample_velocities(self.state.temperature_left_k)
        self.velocities_right_si = self._sample_velocities(self.state.temperature_right_k)
        self.elapsed_s = 0.0
        self.heat_transferred_j = 0.0
        self.temperature_history.clear()
        self._append_temperature_point()

    def _append_temperature_point(self) -> None:
        point = (
            self.elapsed_s,
            self.state.temperature_left_c,
            self.state.temperature_right_c,
        )
        if not self.temperature_history or not np.allclose(self.temperature_history[-1], point):
            self.temperature_history.append(point)
            if len(self.temperature_history) > 240:
                del self.temperature_history[:-240]
