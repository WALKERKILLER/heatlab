"""Equal-mass elastic scattering for the dilute gas demonstration particles."""

import numpy as np


def scatter_gas_particles(positions: np.ndarray, velocities: np.ndarray) -> None:
    """Exchange the approaching pair's normal velocity, conserving energy and momentum."""
    # shortcut: discrete contact sampling is illustrative, use event-driven collisions to measure rates.
    dimensions = positions.shape[1]
    first, second = np.triu_indices(len(positions), 1)
    displacements = positions[first] - positions[second]
    distances_squared = np.sum(displacements**2, axis=1)
    contacts = (distances_squared > 0.0) & (distances_squared < 0.04**2)
    for i, j in zip(first[contacts], second[contacts], strict=True):
        normal = positions[i] - positions[j]
        normal /= np.linalg.norm(normal)
        approach = np.dot(velocities[i, :dimensions] - velocities[j, :dimensions], normal)
        if approach < 0.0:
            impulse = approach * normal
            velocities[i, :dimensions] -= impulse
            velocities[j, :dimensions] += impulse
