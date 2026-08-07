"""Deterministic, named pseudo-random streams for reproducible simulations."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib

import numpy as np
from numpy.random import Generator, SeedSequence


def _name_words(name: str) -> list[int]:
    """Convert a stream name to stable 32-bit seed words.

    Python's built-in ``hash`` is deliberately process-randomized, so it must
    not be used for reproducible simulation streams.
    """

    digest = hashlib.blake2s(name.encode("utf-8"), digest_size=16).digest()
    return [int.from_bytes(digest[i : i + 4], "little") for i in range(0, 16, 4)]


@dataclass(slots=True)
class RandomManager:
    """Factory for independent RNG streams derived from one project seed."""

    seed: int

    def stream(self, name: str) -> Generator:
        if self.seed < 0:
            raise ValueError("seed must be non-negative")
        sequence = SeedSequence([self.seed, *_name_words(name)])
        return np.random.default_rng(sequence)
