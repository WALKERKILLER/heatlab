"""In-memory live simulation sessions for HeatLab Web."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from typing import Any
from uuid import uuid4

import numpy as np
from scipy.stats import binom

from heatlab.constants import DEFAULT_SEED, STANDARD_ATMOSPHERE
from heatlab.models import BrownianModel, GaltonModel, IdealGasModel, MaxwellModel
from heatlab.randomness import RandomManager


def _to_list(values: np.ndarray | list[Any], *, limit: int | None = None) -> list[Any]:
    data = np.asarray(values, dtype=float)
    if limit is not None and len(data) > limit:
        data = data[-limit:]
    return data.tolist()


@dataclass
class LiveSession:
    """One browser client owns one multi-topic simulation session."""

    seed: int
    session_id: str = field(default_factory=lambda: uuid4().hex)
    ideal: IdealGasModel = field(init=False)
    brownian: BrownianModel = field(init=False)
    maxwell: MaxwellModel = field(init=False)
    galton: GaltonModel = field(init=False)
    galton_batch: Any = field(default=None, init=False)
    galton_row: int = field(default=0, init=False)
    galton_finished: bool = field(default=True, init=False)
    ideal_kinetic_trail: list = field(default_factory=list, init=False)
    lock: Lock = field(default_factory=Lock, repr=False)

    def __post_init__(self) -> None:
        self.reset(self.seed)

    def reset(self, seed: int | None = None) -> None:
        if seed is not None:
            self.seed = int(seed)
        manager = RandomManager(self.seed)
        self.ideal = IdealGasModel(manager.stream("ideal-gas"))
        self.brownian = BrownianModel(manager.stream("brownian"))
        self.maxwell = MaxwellModel(manager.stream("maxwell"))
        self.galton = GaltonModel(manager.stream("galton"))
        self.galton_batch = None
        self.galton_row = 0
        self.galton_finished = True
        self.ideal_kinetic_trail = []

    # ---- ideal gas ----
    def set_ideal(self, temperature_c: float, pressure_atm: float) -> None:
        self.ideal.set_conditions(temperature_c, pressure_atm)
        # Macroscopic path changes only when T/P change; keep kinetic trail continuous.
        self._record_ideal_kinetic_point()

    def step_ideal(self, steps: int = 1) -> dict[str, Any]:
        for _ in range(max(1, steps)):
            self.ideal.step()
            self._record_ideal_kinetic_point()
        return self.snapshot_ideal()

    def _record_ideal_kinetic_point(self) -> None:
        """Append a live kinetic (P, V) sample so the chart moves every frame."""
        kinetic_atm = float(self.ideal.kinetic_pressure_pa() / STANDARD_ATMOSPHERE)
        volume = float(self.ideal.state.volume_litre)
        temperature_k = float(self.ideal.state.temperature_k)
        self.ideal_kinetic_trail.append([kinetic_atm, volume, temperature_k])
        if len(self.ideal_kinetic_trail) > 180:
            del self.ideal_kinetic_trail[:-180]

    def snapshot_ideal(self) -> dict[str, Any]:
        state = self.ideal.state
        history = np.asarray(self.ideal.phase_history, dtype=float)
        kinetic_atm = float(self.ideal.kinetic_pressure_pa() / STANDARD_ATMOSPHERE)
        if not self.ideal_kinetic_trail:
            self._record_ideal_kinetic_point()
        return {
            "temperature_c": state.temperature_c,
            "pressure_atm": state.pressure_atm,
            "temperature_k": state.temperature_k,
            "volume_litre": state.volume_litre,
            "box_width": self.ideal.box_width,
            "kinetic_pressure_atm": kinetic_atm,
            "positions": _to_list(self.ideal.display_positions),
            # Macroscopic PV=nRT path (grows when user moves sliders)
            "phase_history": _to_list(history),
            # Live kinetic estimates (moves every simulation step)
            "kinetic_trail": list(self.ideal_kinetic_trail),
            "live_point": [kinetic_atm, float(state.volume_litre), float(state.temperature_k)],
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
        return {
            "mass_ratio": self.brownian.params.mass_ratio,
            "molecule_count": self.brownian.params.molecule_count,
            "elapsed": self.brownian.elapsed,
            "theoretical_D": self.brownian.params.theoretical_diffusion,
            "empirical_D": None if np.isnan(d_hat) else float(d_hat),
            "path": _to_list(path, limit=2_000),
            "position": _to_list(self.brownian.position),
            "msd_lag": _to_list(lag),
            "msd": _to_list(msd),
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
        payload: dict[str, Any] = {
            "temperature_c": self.maxwell.state.temperature_c,
            "most_probable_speed": self.maxwell.most_probable_speed,
            "mean_speed": self.maxwell.mean_speed,
            "rms_speed": self.maxwell.rms_speed,
            "positions": _to_list(self.maxwell.positions),
            "speeds": _to_list(self.maxwell.speeds),
            "pdf_v": _to_list(velocity),
            "pdf_f": _to_list(density),
        }
        if include_histogram:
            samples = self.maxwell.sampled_speeds(6_000)
            hist_counts, bin_edges = np.histogram(samples, bins=36, density=True)
            bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])
            payload["hist_v"] = _to_list(bin_centers)
            payload["hist_f"] = _to_list(hist_counts)
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
                "sample_mean": 0.0,
                "sample_variance": 0.0,
            }

        batch = self.galton_batch
        row = min(self.galton_row, rows)
        # Current particle positions at animation row
        x = batch.paths[:, row]
        y = np.full_like(x, -row, dtype=float)
        particle_xy = np.column_stack((x, y))

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
            "particle_xy": _to_list(particle_xy),
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
