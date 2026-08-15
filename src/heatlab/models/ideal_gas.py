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


@dataclass(slots=True)
class IdealGasState:
    temperature_c: float = 20.0
    pressure_atm: float = 1.0
    amount_mol: float = 1.0e-3
    particle_count: int = 180
    molecule_mass_kg: float = NITROGEN_MOLECULE_MASS_KG
    # 准静态过程模式："free" 自由 | "isothermal" 等温 | "isobaric" 等压 | "isochoric" 等容
    process_mode: str = "free"

    @property
    def temperature_k(self) -> float:
        return self.temperature_c + CELSIUS_OFFSET

    @property
    def pressure_pa(self) -> float:
        return self.pressure_atm * STANDARD_ATMOSPHERE

    @property
    def volume_m3(self) -> float:
        return self.amount_mol * GAS_CONSTANT * self.temperature_k / self.pressure_pa

    @property
    def volume_litre(self) -> float:
        return self.volume_m3 * 1_000.0

    @property
    def molecule_count_physical(self) -> float:
        return self.amount_mol * AVOGADRO


@dataclass(slots=True)
class IdealGasModel:
    rng: Generator
    state: IdealGasState = field(default_factory=IdealGasState)
    positions: np.ndarray = field(init=False)
    velocities_si: np.ndarray = field(init=False)
    phase_history: list[tuple[float, float, float]] = field(default_factory=list)
    _box_length: float = field(init=False, default=1.0)
    _locked_temperature_c: float = field(init=False, default=20.0)
    _locked_pressure_atm: float = field(init=False, default=1.0)
    _locked_volume_m3: float = field(init=False, default=0.0)

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
        temperature_c, pressure_atm = self._apply_process_constraints(temperature_c, pressure_atm)

        old_temperature = self.state.temperature_k
        old_length = self._box_length
        self.state.temperature_c = temperature_c
        self.state.pressure_atm = pressure_atm

        # Preserve velocity directions while imposing the Maxwellian T scaling.
        scale = np.sqrt(self.state.temperature_k / old_temperature)
        self.velocities_si *= scale

        self._box_length = self._display_length()
        self.positions[:, 0] *= self._box_length / old_length
        self.positions[:, 0] = np.clip(self.positions[:, 0], 0.0, self._box_length)
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

    def process_line(self) -> tuple[np.ndarray, np.ndarray] | None:
        """当前过程模式对应的理论线；自由模式返回 None。"""
        if self.state.process_mode == "isothermal":
            return self.isotherm_line()
        if self.state.process_mode == "isobaric":
            return self.isobar_line()
        if self.state.process_mode == "isochoric":
            return self.isochore_line()
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
        if dt <= 0:
            raise ValueError("dt must be positive")
        self.positions += self.display_velocities * dt

        for axis, upper in ((0, self._box_length), (1, 1.0), (2, 1.0)):
            low_mask = self.positions[:, axis] < 0.0
            if np.any(low_mask):
                self.positions[low_mask, axis] *= -1.0
                self.velocities_si[low_mask, axis] *= -1.0

            high_mask = self.positions[:, axis] > upper
            if np.any(high_mask):
                self.positions[high_mask, axis] = 2.0 * upper - self.positions[high_mask, axis]
                self.velocities_si[high_mask, axis] *= -1.0

    def kinetic_pressure_pa(self) -> float:
        """Estimate pressure from the microscopic momentum-flux relation.

        For an isotropic ideal gas, ``P = N m <v_x^2> / V``.  The displayed
        particles are Monte-Carlo samples representing the physical molecules.
        """

        mean_vx2 = float(np.mean(self.velocities_si[:, 0] ** 2))
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
