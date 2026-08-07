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
    _box_width: float = field(init=False, default=1.0)

    def __post_init__(self) -> None:
        self._box_width = self._display_width()
        self.positions = self._random_positions()
        self.velocities_si = self._sample_velocities()
        self._append_phase_point()

    def _display_width(self) -> float:
        ratio = (
            (self.state.temperature_k / REFERENCE_TEMPERATURE_K)
            / (self.state.pressure_pa / REFERENCE_PRESSURE_PA)
        )
        return float(np.clip(ratio, 0.45, 1.35))

    def _random_positions(self) -> np.ndarray:
        points = self.rng.random((self.state.particle_count, 2))
        points[:, 0] *= self._box_width
        return points

    def _sample_velocities(self) -> np.ndarray:
        sigma = np.sqrt(BOLTZMANN * self.state.temperature_k / self.state.molecule_mass_kg)
        values = self.rng.normal(0.0, sigma, size=(self.state.particle_count, 2))
        values -= values.mean(axis=0, keepdims=True)
        return values

    @property
    def box_width(self) -> float:
        return self._box_width

    @property
    def display_positions(self) -> np.ndarray:
        return self.positions

    @property
    def display_velocities(self) -> np.ndarray:
        thermal_rms = np.sqrt(2.0 * BOLTZMANN * self.state.temperature_k / self.state.molecule_mass_kg)
        return self.velocities_si / max(thermal_rms, np.finfo(float).tiny) * 0.52

    def set_conditions(self, temperature_c: float, pressure_atm: float) -> None:
        temperature_c = float(np.clip(temperature_c, 0.0, 100.0))
        pressure_atm = float(np.clip(pressure_atm, 1.0, 2.0))

        old_temperature = self.state.temperature_k
        old_width = self._box_width
        self.state.temperature_c = temperature_c
        self.state.pressure_atm = pressure_atm

        # Preserve velocity directions while imposing the Maxwellian T scaling.
        scale = np.sqrt(self.state.temperature_k / old_temperature)
        self.velocities_si *= scale

        self._box_width = self._display_width()
        self.positions[:, 0] *= self._box_width / old_width
        self.positions[:, 0] = np.clip(self.positions[:, 0], 0.0, self._box_width)
        self._append_phase_point()

    def step(self, dt: float = 0.020) -> None:
        if dt <= 0:
            raise ValueError("dt must be positive")
        self.positions += self.display_velocities * dt

        for axis, upper in ((0, self._box_width), (1, 1.0)):
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
        self._box_width = self._display_width()
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
