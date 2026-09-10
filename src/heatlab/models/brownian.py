"""Brownian motion: explicit liquid molecules striking one pollen grain.

The source brief asks for "many liquid molecules striking a pollen grain",
producing Brownian motion.  This module uses a small explicit-solvent model:

* liquid molecules receive Ornstein-Uhlenbeck thermalization, keep a 2-D
  Maxwell-Boltzmann speed scale, and elastically collide with the walls and
  each other; and
* a pollen grain changes momentum only when a liquid molecule actually
  contacts it.  The collision is a two-body elastic collision, so a single
  molecule cannot apply a random force while it is elsewhere in the box.

The analytic ``theta / gamma`` value remains a continuum Langevin reference
for the MSD chart.  It is not used as an additional force in the explicit
collision trajectory, which avoids double-counting the solvent fluctuations.

The two UI parameters are physically meaningful here:

* ``mass_ratio`` (m / m0): heavier grains receive a smaller velocity change per
  collision and diffuse
  more slowly (their radius also grows, mimicking mass proportional to area);
* ``molecule_count`` n: more molecules make the liquid denser and collisions
  more frequent; n=1 is intentionally a sparse, intermittent bath.

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

# Pollen grain: heavy, big, moved by explicit solvent collisions.
_POLLEN_MASS_BASE = 1.0
_POLLEN_RADIUS_MIN = 0.050
_POLLEN_RADIUS_MAX = 0.115
_DRAG_BASE = 0.5  # Continuum reference drag coefficient.

# Thermal energy of the liquid bath; fixes the molecular speed scale.
_THERMAL_ENERGY = 0.02
_LIQUID_SPEED_SIGMA = np.sqrt(_THERMAL_ENERGY / _LIQUID_MASS)  # ~1.0


@dataclass(slots=True)
class BrownianParameters:
    mass_ratio: float = 0.50
    molecule_count: int = 40
    dt: float = 0.005
    theta: float = _THERMAL_ENERGY

    def __post_init__(self) -> None:
        if not np.isfinite(self.mass_ratio) or not 0.05 <= self.mass_ratio <= 1.0:
            raise ValueError("mass_ratio must be finite and within [0.05, 1.0]")
        if not isinstance(self.molecule_count, (int, np.integer)) or not 1 <= self.molecule_count <= 100:
            raise ValueError("molecule_count must be an integer within [1, 100]")
        if not np.isfinite(self.dt) or self.dt <= 0.0:
            raise ValueError("dt must be finite and positive")
        if not np.isfinite(self.theta) or self.theta <= 0.0:
            raise ValueError("theta must be finite and positive")

    @property
    def effective_mass(self) -> float:
        # The brief writes 0..m0; a literal zero makes the collision impulse
        # singular, so the UI maps its lower endpoint to 0.05 m0 explicitly.
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
        if not np.isfinite(mass_ratio):
            raise ValueError("mass_ratio must be finite")
        if not isinstance(molecule_count, (int, np.integer)):
            raise ValueError("molecule_count must be an integer")
        next_mass = float(np.clip(mass_ratio, 0.05, 1.0))
        next_count = int(np.clip(molecule_count, 1, 100))
        changed = (
            not np.isclose(next_mass, self.params.mass_ratio)
            or next_count != self.params.molecule_count
        )
        self.params.mass_ratio = next_mass
        self.params.molecule_count = next_count
        if changed:
            # A new density or grain mass is a new experiment. Do not mix its
            # path and MSD with samples collected under the old condition.
            self.reset()
        else:
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

    def step(self, substeps: int = 4) -> None:
        if substeps < 1:
            raise ValueError("substeps must be >= 1")
        dt = self.params.dt
        relaxation = _LIQUID_RELAXATION
        speed_sigma = _LIQUID_SPEED_SIGMA
        rng = self.rng

        for _ in range(substeps):
            # 1) Liquid molecules: Ornstein-Uhlenbeck thermal motion + walls.
            velocities = self.liquid_velocities
            # Exact Ornstein-Uhlenbeck update. Unlike Euler-Maruyama plus a
            # speed cap, this preserves the Maxwell-Boltzmann stationary
            # variance and keeps the rare high-speed tail physically valid.
            decay = np.exp(-relaxation * dt)
            noise_scale = speed_sigma * np.sqrt(-np.expm1(-2.0 * relaxation * dt))
            velocities[:] = (
                decay * velocities
                + noise_scale * rng.standard_normal(velocities.shape)
            )
            self.liquid_positions += velocities * dt
            self._bounce_liquids()
            # 1b) Liquid molecules bounce off each other (hard-sphere elastic
            # collisions, following the open-source hard-sphere model): the
            # liquid reads as a dense, colliding fluid rather than ghost dots.
            self._collide_liquids()

            # 2) Pollen grain: no independent random kick.  In this explicit
            # solvent model, its momentum changes only in a real molecule
            # contact below; otherwise one visible molecule must not create a
            # spatially nonlocal force.
            self.position += self.velocity * dt
            self._bounce_pollen()

            # 3) Liquid molecules strike the grain (two-body elastic collision
            # + highlight).  A second pass settles contacts created by the
            # first collision response.
            self._collide_with_pollen()
            self._collide_liquids()
            self._collide_with_pollen()
            self._bounce_pollen()

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

    def _collide_liquids(self, iterations: int = 16) -> None:
        """Hard-sphere elastic collisions between liquid molecules.

        Adopts the hard-sphere model used by open-source brownian simulations
        (e.g. Yangliu20/physics-simulation): equal-mass elastic collisions that
        swap the normal velocity component, plus positional separation.  The
        whole pair sweep is vectorised, and the extra projection passes ensure
        dense scenes settle below the hard-sphere overlap tolerance instead of
        carrying a small penetration into the next time step.
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
            normal = np.zeros((len(dist), 2), dtype=float)
            nonzero = dist > 1.0e-12
            normal[nonzero] = delta[i_idx[nonzero], j_idx[nonzero]] / dist[nonzero, None]
            # Deterministic fallback for the rare exact co-location case.
            normal[~nonzero, 0] = 1.0
            # Equal-mass elastic collision: only approaching pairs interact.
            rel_normal = np.einsum("ij,ij->i", velocities[i_idx] - velocities[j_idx], normal)
            approaching = rel_normal < 0.0
            if approaching.any():
                approaching_i = i_idx[approaching]
                approaching_j = j_idx[approaching]
                approaching_normal = normal[approaching]
                approaching_rel = rel_normal[approaching]
                velocities[approaching_i] -= approaching_rel[:, None] * approaching_normal
                velocities[approaching_j] += approaching_rel[:, None] * approaching_normal
            # Push the overlapping pair apart by half the penetration each.
            penetration = (min_dist - dist) * 0.5
            positions[i_idx] += penetration[:, None] * normal
            positions[j_idx] -= penetration[:, None] * normal
            self.liquid_collision_count += int(approaching.sum())

    def _bounce_pollen(self) -> None:
        radius = self.params.pollen_radius
        if self.position[0] < _BOX_LOW + radius:
            self.position[0] = 2.0 * (_BOX_LOW + radius) - self.position[0]
            self.velocity[0] = abs(self.velocity[0])
        elif self.position[0] > _BOX_HIGH - radius:
            self.position[0] = 2.0 * (_BOX_HIGH - radius) - self.position[0]
            self.velocity[0] = -abs(self.velocity[0])
        if self.position[1] < _BOX_LOW + radius:
            self.position[1] = 2.0 * (_BOX_LOW + radius) - self.position[1]
            self.velocity[1] = abs(self.velocity[1])
        elif self.position[1] > _BOX_HIGH - radius:
            self.position[1] = 2.0 * (_BOX_HIGH - radius) - self.position[1]
            self.velocity[1] = -abs(self.velocity[1])

    def _collide_with_pollen(self) -> None:
        radius_sum = self.params.pollen_radius + _LIQUID_RADIUS
        radius_sum_sq = radius_sum * radius_sum
        liquid_mass = _LIQUID_MASS
        pollen_mass = self.params.effective_mass
        liquid_share = pollen_mass / (liquid_mass + pollen_mass)
        pollen_share = liquid_mass / (liquid_mass + pollen_mass)
        for i, liquid_position in enumerate(self.liquid_positions):
            delta = liquid_position - self.position
            distance_sq = float(delta @ delta)
            if distance_sq >= radius_sum_sq:
                continue
            distance = np.sqrt(distance_sq)
            # Exact co-location has no unique contact normal.  Keep the
            # fallback deterministic; normal overlaps are prevented at spawn
            # time and by positional separation below.
            normal = delta / distance if distance > 1.0e-12 else np.array([1.0, 0.0])
            relative_normal = float((self.liquid_velocities[i] - self.velocity) @ normal)
            if relative_normal < 0.0:
                # Equal-and-opposite impulse for a 1-D normal elastic impact:
                # J = -2 v_rel,n / (1/m_liquid + 1/m_pollen).
                impulse = -2.0 * relative_normal / (1.0 / liquid_mass + 1.0 / pollen_mass)
                self.liquid_velocities[i] += (impulse / liquid_mass) * normal
                self.velocity -= (impulse / pollen_mass) * normal
                self.collision_count += 1
                # Record the contact point ON the grain surface so the
                # highlight lands exactly where the molecule struck.
                self.recent_collisions.append((self.position + normal * self.params.pollen_radius).copy())
            # Separate the pair without pinning the pollen.  The heavier grain
            # moves less, preserving the center of mass of the overlap.
            penetration = radius_sum - distance
            self.liquid_positions[i] += normal * (penetration * liquid_share)
            self.position -= normal * (penetration * pollen_share)
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
