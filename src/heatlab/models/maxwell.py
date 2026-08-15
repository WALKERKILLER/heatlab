"""Maxwell-Boltzmann molecular-speed distribution and particle animation."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.random import Generator
from scipy.stats import maxwell, norm

from heatlab.constants import BOLTZMANN, CELSIUS_OFFSET, NITROGEN_MOLECULE_MASS_KG


@dataclass(slots=True)
class MaxwellState:
    temperature_c: float = 20.0
    molecule_mass_kg: float = NITROGEN_MOLECULE_MASS_KG
    particle_count: int = 180

    @property
    def temperature_k(self) -> float:
        return self.temperature_c + CELSIUS_OFFSET

    @property
    def scale(self) -> float:
        return float(np.sqrt(BOLTZMANN * self.temperature_k / self.molecule_mass_kg))


@dataclass(slots=True)
class MaxwellModel:
    rng: Generator
    state: MaxwellState = field(default_factory=MaxwellState)
    positions: np.ndarray = field(init=False)
    velocities_si: np.ndarray = field(init=False)

    def __post_init__(self) -> None:
        self.positions = self.rng.random((self.state.particle_count, 2))
        self.velocities_si = self._sample_velocity_components(self.state.particle_count)

    def _sample_velocity_components(self, count: int) -> np.ndarray:
        return self.rng.normal(0.0, self.state.scale, size=(count, 3))

    def set_temperature(self, temperature_c: float) -> None:
        old_k = self.state.temperature_k
        self.state.temperature_c = float(np.clip(temperature_c, 0.0, 100.0))
        self.velocities_si *= np.sqrt(self.state.temperature_k / old_k)

    @property
    def speeds(self) -> np.ndarray:
        return np.linalg.norm(self.velocities_si, axis=1)

    @property
    def display_velocities(self) -> np.ndarray:
        rms = self.rms_speed
        # 显示速度系数 1.5：让粒子以热速率尺度活跃运动（真实气体观感），
        # 而非 0.55 的“慢漂移”。仅影响可视化，不改变物理状态。
        return self.velocities_si[:, :2] / max(rms, np.finfo(float).tiny) * 1.5

    def step(self, dt: float = 0.020) -> None:
        self.positions += self.display_velocities * dt
        for axis in (0, 1):
            low = self.positions[:, axis] < 0.0
            high = self.positions[:, axis] > 1.0
            if np.any(low):
                self.positions[low, axis] *= -1.0
                self.velocities_si[low, axis] *= -1.0
            if np.any(high):
                self.positions[high, axis] = 2.0 - self.positions[high, axis]
                self.velocities_si[high, axis] *= -1.0

    def distribution_curve(self, points: int = 500) -> tuple[np.ndarray, np.ndarray]:
        vmax = maxwell.ppf(0.999999, scale=self.state.scale)
        velocity = np.linspace(0.0, vmax, points)
        density = maxwell.pdf(velocity, scale=self.state.scale)
        return velocity, density

    def sampled_speeds(self, count: int = 12_000) -> np.ndarray:
        components = self._sample_velocity_components(count)
        return np.linalg.norm(components, axis=1)

    def component_curve(self, points: int = 500) -> tuple[np.ndarray, np.ndarray]:
        """水平速度分量 v_x 的理论高斯分布曲线（σ = √(kT/m)）。"""
        vmax = 4.0 * self.state.scale
        velocity = np.linspace(-vmax, vmax, points)
        density = norm.pdf(velocity, scale=self.state.scale)
        return velocity, density

    def sampled_components(self, count: int = 12_000) -> np.ndarray:
        """从水平速度分量分布中采样 v_x（与动画粒子同源的高斯噪声）。"""
        return self.rng.normal(0.0, self.state.scale, size=count)

    @property
    def most_probable_speed(self) -> float:
        return float(np.sqrt(2.0) * self.state.scale)

    @property
    def mean_speed(self) -> float:
        return float(2.0 * np.sqrt(2.0 / np.pi) * self.state.scale)

    @property
    def rms_speed(self) -> float:
        return float(np.sqrt(3.0) * self.state.scale)

    @property
    def fixed_pdf_peak(self) -> float:
        """速率分布 f(v) 的 y 轴固定上限。

        温度最低（0 °C）时分布最窄、峰值最高（面积恒为 1），
        用该峰值作为 y 轴上限，温度升高时曲线右移且峰值变矮，
        视觉与物理一致（不再随坐标轴自动缩放而“变形”）。
        """
        coldest_scale = np.sqrt(BOLTZMANN * CELSIUS_OFFSET / self.state.molecule_mass_kg)
        return float(4.0 / (coldest_scale * np.e * np.sqrt(2.0 * np.pi)))

    @property
    def fixed_component_peak(self) -> float:
        """水平分量 v_x 高斯分布的 y 轴固定上限（0 °C 时 σ 最小、峰值最高）。"""
        coldest_scale = np.sqrt(BOLTZMANN * CELSIUS_OFFSET / self.state.molecule_mass_kg)
        return float(1.0 / (coldest_scale * np.sqrt(2.0 * np.pi)))

    def reset(self) -> None:
        self.positions = self.rng.random((self.state.particle_count, 2))
        self.velocities_si = self._sample_velocity_components(self.state.particle_count)
