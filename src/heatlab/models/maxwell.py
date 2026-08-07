"""Maxwell-Boltzmann molecular-speed distribution and particle animation."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.random import Generator
from scipy.stats import maxwell

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
        return self.velocities_si[:, :2] / max(rms, np.finfo(float).tiny) * 0.55

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

    @property
    def most_probable_speed(self) -> float:
        return float(np.sqrt(2.0) * self.state.scale)

    @property
    def mean_speed(self) -> float:
        return float(2.0 * np.sqrt(2.0 / np.pi) * self.state.scale)

    @property
    def rms_speed(self) -> float:
        return float(np.sqrt(3.0) * self.state.scale)

    def reset(self) -> None:
        self.positions = self.rng.random((self.state.particle_count, 2))
        self.velocities_si = self._sample_velocity_components(self.state.particle_count)
