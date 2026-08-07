"""Monte-Carlo Galton-board model with an exact binomial reference."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.random import Generator
from scipy.stats import binom


@dataclass(slots=True)
class GaltonParameters:
    rows: int = 12
    probability_right: float = 0.5
    particle_count: int = 50


@dataclass(slots=True)
class GaltonBatch:
    paths: np.ndarray
    final_bins: np.ndarray
    counts: np.ndarray
    probabilities: np.ndarray
    theoretical: np.ndarray


@dataclass(slots=True)
class GaltonModel:
    rng: Generator
    params: GaltonParameters = field(default_factory=GaltonParameters)

    def simulate(self, particle_count: int | None = None) -> GaltonBatch:
        count = self.params.particle_count if particle_count is None else int(particle_count)
        count = int(np.clip(count, 1, 100))
        rows = self.params.rows
        p = self.params.probability_right

        decisions = self.rng.random((count, rows)) < p
        # Horizontal coordinate after each row: left=-1, right=+1.
        steps = np.where(decisions, 1, -1)
        paths = np.column_stack((np.zeros(count, dtype=int), np.cumsum(steps, axis=1)))
        final_bins = decisions.sum(axis=1)
        counts = np.bincount(final_bins, minlength=rows + 1)
        probabilities = counts / count
        bins = np.arange(rows + 1)
        theoretical = binom.pmf(bins, rows, p)
        return GaltonBatch(paths, final_bins, counts, probabilities, theoretical)

    def reset(self) -> None:
        # State lives in the named RNG stream and the latest UI batch.
        return None
