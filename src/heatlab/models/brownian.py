"""Dimensionless Langevin Brownian-motion model.

The source brief does not provide fluid viscosity, particle radius, temperature,
or a physical mass scale.  This module therefore uses explicit dimensionless
units.  It remains physically structured: fluctuation and damping obey the
Langevin relation, and the long-time diffusion coefficient is D = theta/gamma.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.random import Generator


@dataclass(slots=True)
class BrownianParameters:
    mass_ratio: float = 0.50
    molecule_count: int = 40
    gamma: float = 1.0
    thermal_energy: float = 1.0
    dt: float = 0.005

    @property
    def effective_mass(self) -> float:
        # The document writes 0..m0. A literal zero makes dv/dt singular, so
        # the UI maps its lower endpoint to 0.05 m0 and states this explicitly.
        return max(0.05, self.mass_ratio)

    @property
    def theoretical_diffusion(self) -> float:
        return self.thermal_energy / self.gamma


@dataclass(slots=True)
class BrownianModel:
    rng: Generator
    params: BrownianParameters = field(default_factory=BrownianParameters)
    position: np.ndarray = field(init=False)
    velocity: np.ndarray = field(init=False)
    path: list[np.ndarray] = field(init=False)
    times: list[float] = field(init=False)
    elapsed: float = field(init=False, default=0.0)

    def __post_init__(self) -> None:
        self.reset()

    def set_parameters(self, mass_ratio: float, molecule_count: int) -> None:
        self.params.mass_ratio = float(np.clip(mass_ratio, 0.05, 1.0))
        self.params.molecule_count = int(np.clip(molecule_count, 1, 100))

    def _finite_collision_kick(self) -> np.ndarray:
        """Return a variance-normalized sum of random molecular impacts.

        More molecules make the aggregate kick more nearly Gaussian, while the
        1/sqrt(N) normalization keeps thermal energy constant rather than
        incorrectly increasing temperature with the UI particle count.
        """

        count = self.params.molecule_count
        angles = self.rng.uniform(0.0, 2.0 * np.pi, size=count)
        unit_vectors = np.column_stack((np.cos(angles), np.sin(angles)))
        return np.sqrt(2.0) * unit_vectors.sum(axis=0) / np.sqrt(count)

    def step(self, substeps: int = 4) -> None:
        if substeps < 1:
            raise ValueError("substeps must be >= 1")
        m = self.params.effective_mass
        gamma = self.params.gamma
        theta = self.params.thermal_energy
        dt = self.params.dt

        for _ in range(substeps):
            kick = self._finite_collision_kick()
            self.velocity += (
                -(gamma / m) * self.velocity * dt
                + (np.sqrt(2.0 * gamma * theta * dt) / m) * kick
            )
            self.position += self.velocity * dt
            self.elapsed += dt

        self.path.append(self.position.copy())
        self.times.append(self.elapsed)
        if len(self.path) > 4_000:
            del self.path[:1_000]
            del self.times[:1_000]

    def msd_curve(self) -> tuple[np.ndarray, np.ndarray]:
        """Return lag time and time-averaged mean-square displacement."""

        points = np.asarray(self.path, dtype=float)
        if len(points) < 12:
            return np.empty(0), np.empty(0)
        max_lag = min(len(points) // 4, 250)
        if max_lag < 2:
            return np.empty(0), np.empty(0)
        lags = np.unique(np.geomspace(1, max_lag, 32).astype(int))
        msd = np.array(
            [np.mean(np.sum((points[lag:] - points[:-lag]) ** 2, axis=1)) for lag in lags]
        )
        mean_sample_interval = self.elapsed / max(1, len(self.path) - 1)
        return lags * mean_sample_interval, msd

    def empirical_diffusion(self) -> float:
        """Estimate D from the slope of a time-averaged MSD curve in 2-D."""

        lag_times, msd = self.msd_curve()
        if len(lag_times) < 10:
            return float("nan")
        start = max(2, len(lag_times) // 3)
        slope, _ = np.polyfit(lag_times[start:], msd[start:], 1)
        return max(0.0, float(slope / 4.0))

    def reset(self) -> None:
        self.position = np.zeros(2, dtype=float)
        self.velocity = np.zeros(2, dtype=float)
        self.path = [self.position.copy()]
        self.times = [0.0]
        self.elapsed = 0.0

    @staticmethod
    def ensemble_diffusion_estimate(
        rng: Generator,
        *,
        path_count: int = 2_000,
        steps: int = 4_000,
        dt: float = 0.005,
        mass: float = 0.5,
        gamma: float = 1.0,
        thermal_energy: float = 1.0,
    ) -> float:
        """Vectorized validation helper using Gaussian Langevin noise."""

        positions = np.zeros((path_count, 2), dtype=float)
        velocities = np.zeros_like(positions)
        for _ in range(steps):
            noise = rng.standard_normal(size=positions.shape)
            velocities += (
                -(gamma / mass) * velocities * dt
                + np.sqrt(2.0 * gamma * thermal_energy * dt) / mass * noise
            )
            positions += velocities * dt
        total_time = steps * dt
        return float(np.mean(np.sum(positions**2, axis=1)) / (4.0 * total_time))
