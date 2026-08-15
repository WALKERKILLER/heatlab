"""Brownian motion: visible liquid molecules striking one pollen grain.

The source brief asks for "many liquid molecules striking a pollen grain",
producing Brownian motion.  This module couples two approaches found in
mature open-source simulations:

* a visible layer of liquid molecules under Ornstein-Uhlenbeck thermal motion:
  their speeds keep a 2-D Maxwell-Boltzmann distribution, they bounce off the
  container walls and elastically off the pollen grain, and their hits are
  counted for the collision highlight; and
* Langevin dynamics for the pollen grain itself (random aggregate kicks +
  Stokes-like drag), so the long-time diffusion coefficient D = theta / gamma
  stays well defined and the MSD curve remains linear.

The two UI parameters are physically meaningful here:

* ``mass_ratio`` (m / m0): heavier grains barely move per kick and diffuse
  more slowly (their radius also grows, mimicking mass proportional to area);
* ``molecule_count`` n: more molecules make the liquid denser and the
  aggregate kick more Gaussian (1 molecule visibly "pushes" the grain).

All values are explicit dimensionless units (the brief gives no physical scale).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.random import Generator

# Container is the unit square [0, 1] x [0, 1].
_BOX_LOW = 0.0
_BOX_HIGH = 1.0

# Liquid molecules: light, small, thermally agitated.
_LIQUID_MASS = 0.02
_LIQUID_RADIUS = 0.012
_LIQUID_RELAXATION = 12.0  # OU rate: how fast a molecule forgets its velocity

# Pollen grain: heavy, big, driven by Langevin dynamics.
_POLLEN_MASS_BASE = 1.0
_POLLEN_RADIUS_MIN = 0.050
_POLLEN_RADIUS_MAX = 0.115
_DRAG_BASE = 0.5  # Stokes-like drag coefficient

# Thermal energy of the liquid bath; fixes the molecular speed scale.
_THERMAL_ENERGY = 0.02
_LIQUID_SPEED_SIGMA = np.sqrt(_THERMAL_ENERGY / _LIQUID_MASS)  # ~1.0


@dataclass(slots=True)
class BrownianParameters:
    mass_ratio: float = 0.50
    molecule_count: int = 40
    dt: float = 0.005
    theta: float = _THERMAL_ENERGY

    @property
    def effective_mass(self) -> float:
        # The brief writes 0..m0; a literal zero makes dv/dt singular, so the
        # UI maps its lower endpoint to 0.05 m0 and states this explicitly.
        return _POLLEN_MASS_BASE * max(0.05, self.mass_ratio)

    @property
    def pollen_radius(self) -> float:
        # Heavier grain = larger (mass ~ area in 2-D), which also means a
        # larger collision cross-section and more drag.
        mass = max(0.05, self.mass_ratio)
        return _POLLEN_RADIUS_MIN + (_POLLEN_RADIUS_MAX - _POLLEN_RADIUS_MIN) * mass

    @property
    def gamma(self) -> float:
        # Stokes-like drag grows with molecule density and grain size.
        return _DRAG_BASE * self.molecule_count * (self.pollen_radius + _LIQUID_RADIUS)

    @property
    def theoretical_diffusion(self) -> float:
        # Einstein relation in 2-D: D = theta / gamma.
        return self.theta / self.gamma


@dataclass(slots=True)
class BrownianModel:
    rng: Generator
    params: BrownianParameters = field(default_factory=BrownianParameters)
    position: np.ndarray = field(init=False)
    velocity: np.ndarray = field(init=False)
    path: list[np.ndarray] = field(init=False)
    times: list[float] = field(init=False)
    elapsed: float = field(init=False, default=0.0)
    # Liquid-molecule layer (the "many molecules" the brief describes).
    liquid_positions: np.ndarray = field(init=False)
    liquid_velocities: np.ndarray = field(init=False)
    collision_count: int = field(init=False, default=0)
    # Pollen-surface contact points (for the collision highlight + distribution).
    recent_collisions: list[np.ndarray] = field(init=False)
    liquid_collision_count: int = field(init=False, default=0)

    def __post_init__(self) -> None:
        self.reset()

    def set_parameters(self, mass_ratio: float, molecule_count: int) -> None:
        self.params.mass_ratio = float(np.clip(mass_ratio, 0.05, 1.0))
        self.params.molecule_count = int(np.clip(molecule_count, 1, 100))
        self._ensure_liquid_count()

    @property
    def liquid_speeds(self) -> np.ndarray:
        return np.linalg.norm(self.liquid_velocities, axis=1)

    @property
    def liquid_speed_sigma(self) -> float:
        # sqrt(theta / m_liquid): the scale of the 2-D Maxwell-Boltzmann law.
        return float(_LIQUID_SPEED_SIGMA)

    def _ensure_liquid_count(self) -> None:
        count = self.params.molecule_count
        if self.liquid_positions is None or len(self.liquid_positions) != count:
            self._spawn_liquids()

    def _spawn_liquids(self) -> None:
        count = self.params.molecule_count
        radius = self.params.pollen_radius
        positions = []
        while len(positions) < count:
            point = self.rng.uniform(_BOX_LOW, _BOX_HIGH, size=2)
            # Keep molecules out of the grain (it sits at the container centre).
            if np.linalg.norm(point - np.array([0.5, 0.5])) > radius + _LIQUID_RADIUS + 0.02:
                positions.append(point)
        self.liquid_positions = np.asarray(positions, dtype=float)
        # Gaussian thermal velocities: v ~ N(0, sigma^2 I).
        self.liquid_velocities = _LIQUID_SPEED_SIGMA * self.rng.standard_normal((count, 2))

    def _finite_collision_kick(self) -> np.ndarray:
        """Return a variance-normalized sum of random molecular impacts.

        More molecules make the aggregate kick more nearly Gaussian, while the
        1/sqrt(N) normalization keeps the thermal energy constant rather than
        incorrectly raising temperature with the UI particle count.
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
        theta = self.params.theta
        dt = self.params.dt
        relaxation = _LIQUID_RELAXATION
        speed_sigma = _LIQUID_SPEED_SIGMA
        rng = self.rng

        for _ in range(substeps):
            # 1) Liquid molecules: Ornstein-Uhlenbeck thermal motion + walls.
            velocities = self.liquid_velocities
            velocities += (
                -relaxation * velocities * dt
                + np.sqrt(2.0 * relaxation * speed_sigma * speed_sigma * dt)
                * rng.standard_normal(velocities.shape)
            )
            # Guard the rare high-speed tail so the explicit collision step
            # stays stable (speed distribution keeps its Maxwell shape).
            speeds = np.linalg.norm(velocities, axis=1)
            over_speed = speeds > 3.0 * speed_sigma
            if over_speed.any():
                velocities[over_speed] *= (3.0 * speed_sigma / speeds[over_speed])[:, None]
            self.liquid_positions += velocities * dt
            self._bounce_liquids()
            # 1b) Liquid molecules bounce off each other (hard-sphere elastic
            # collisions, following the open-source hard-sphere model): the
            # liquid reads as a dense, colliding fluid rather than ghost dots.
            self._collide_liquids()

            # 2) Pollen grain: Langevin equation dv/dt = -gamma/m v + noise/m.
            kick = self._finite_collision_kick()
            self.velocity += (
                -(gamma / m) * self.velocity * dt
                + (np.sqrt(2.0 * gamma * theta * dt) / m) * kick
            )
            self.position += self.velocity * dt
            self._bounce_pollen()

            # 3) Liquid molecules strike the grain (elastic bounce + highlight).
            self._collide_with_pollen()

            self.elapsed += dt

        self.path.append(self.position.copy())
        self.times.append(self.elapsed)
        if len(self.path) > 4_000:
            del self.path[:1_000]
            del self.times[:1_000]

    def _bounce_liquids(self) -> None:
        positions = self.liquid_positions
        velocities = self.liquid_velocities
        radius = _LIQUID_RADIUS
        for axis in (0, 1):
            below = positions[:, axis] < _BOX_LOW + radius
            above = positions[:, axis] > _BOX_HIGH - radius
            positions[below, axis] = 2.0 * (_BOX_LOW + radius) - positions[below, axis]
            positions[above, axis] = 2.0 * (_BOX_HIGH - radius) - positions[above, axis]
            velocities[below, axis] = -velocities[below, axis]
            velocities[above, axis] = -velocities[above, axis]

    def _collide_liquids(self, iterations: int = 2) -> None:
        """Hard-sphere elastic collisions between liquid molecules.

        Adopts the hard-sphere model used by open-source brownian simulations
        (e.g. Yangliu20/physics-simulation): equal-mass elastic collisions that
        swap the normal velocity component, plus positional separation so
        molecules never overlap.  The whole pair sweep is vectorised, which
        keeps the O(n^2) detection cheap for n <= 100.
        """

        positions = self.liquid_positions
        velocities = self.liquid_velocities
        count = len(positions)
        if count < 2:
            return
        min_dist = 2.0 * _LIQUID_RADIUS
        min_dist_sq = min_dist * min_dist

        for _ in range(max(1, iterations)):
            delta = positions[:, None, :] - positions[None, :, :]  # (n, n, 2)
            dist_sq = np.einsum("ijk,ijk->ij", delta, delta)       # (n, n)
            np.fill_diagonal(dist_sq, np.inf)
            i_idx, j_idx = np.nonzero(np.triu(dist_sq < min_dist_sq, 1))
            if len(i_idx) == 0:
                break
            dist = np.sqrt(dist_sq[i_idx, j_idx])
            normal = delta[i_idx, j_idx] / dist[:, None]
            # Equal-mass elastic collision: only approaching pairs interact.
            rel_normal = np.einsum("ij,ij->i", velocities[i_idx] - velocities[j_idx], normal)
            approaching = rel_normal < 0.0
            if not approaching.any():
                break
            i_idx, j_idx = i_idx[approaching], j_idx[approaching]
            normal, rel_normal = normal[approaching], rel_normal[approaching]
            velocities[i_idx] -= rel_normal[:, None] * normal
            velocities[j_idx] += rel_normal[:, None] * normal
            # Push the overlapping pair apart by half the penetration each.
            penetration = (min_dist - dist[approaching]) * 0.5
            positions[i_idx] -= penetration[:, None] * normal
            positions[j_idx] += penetration[:, None] * normal
            self.liquid_collision_count += len(i_idx)

    def _bounce_pollen(self) -> None:
        radius = self.params.pollen_radius
        if self.position[0] < _BOX_LOW + radius:
            self.position[0] = 2.0 * (_BOX_LOW + radius) - self.position[0]
            self.velocity[0] = -abs(self.velocity[0])
        elif self.position[0] > _BOX_HIGH - radius:
            self.position[0] = 2.0 * (_BOX_HIGH - radius) - self.position[0]
            self.velocity[0] = -abs(self.velocity[0])
        if self.position[1] < _BOX_LOW + radius:
            self.position[1] = 2.0 * (_BOX_LOW + radius) - self.position[1]
            self.velocity[1] = -abs(self.velocity[1])
        elif self.position[1] > _BOX_HIGH - radius:
            self.position[1] = 2.0 * (_BOX_HIGH - radius) - self.position[1]
            self.velocity[1] = -abs(self.velocity[1])

    def _collide_with_pollen(self) -> None:
        count = self.params.molecule_count
        radius_sum = self.params.pollen_radius + _LIQUID_RADIUS
        radius_sum_sq = radius_sum * radius_sum
        pollen = self.position
        for i in range(count):
            delta = self.liquid_positions[i] - pollen
            distance_sq = float(delta @ delta)
            if distance_sq >= radius_sum_sq or distance_sq < 1.0e-12:
                continue
            distance = np.sqrt(distance_sq)
            normal = delta / distance
            # Elastic bounce of the light molecule off the (heavy) grain.
            relative_normal = float(self.liquid_velocities[i] @ normal)
            if relative_normal < 0.0:
                self.liquid_velocities[i] -= 2.0 * relative_normal * normal
            self.liquid_positions[i] = pollen + normal * radius_sum
            self.collision_count += 1
            # Record the contact point ON the grain surface so the highlight
            # lands exactly where the molecule struck (mainstream visual).
            self.recent_collisions.append((pollen + normal * radius_sum).copy())
        if len(self.recent_collisions) > 16:
            del self.recent_collisions[:-16]

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
        self.position = np.array([0.5, 0.5], dtype=float)
        self.velocity = np.zeros(2, dtype=float)
        self.path = [self.position.copy()]
        self.times = [0.0]
        self.elapsed = 0.0
        self.collision_count = 0
        self.liquid_collision_count = 0
        self.recent_collisions = []
        self.liquid_positions = np.empty((0, 2), dtype=float)
        self.liquid_velocities = np.empty((0, 2), dtype=float)
        self._ensure_liquid_count()

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
