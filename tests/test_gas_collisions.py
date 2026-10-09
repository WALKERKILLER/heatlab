import numpy as np
import pytest

from heatlab.models.collisions import scatter_gas_particles


@pytest.mark.parametrize("dimensions", [2, 3])
def test_elastic_scattering_changes_individual_speeds_and_conserves_totals(dimensions: int) -> None:
    positions = np.zeros((2, dimensions))
    positions[1, 0] = 0.03
    velocities = np.array([[2.0, 1.0, 0.4], [-1.0, 0.0, -0.2]])
    before = velocities.copy()
    scatter_gas_particles(positions, velocities)
    assert np.allclose(velocities.sum(axis=0), before.sum(axis=0))
    assert np.isclose(np.sum(velocities**2), np.sum(before**2))
    assert not np.allclose(np.linalg.norm(velocities, axis=1), np.linalg.norm(before, axis=1))
    after = velocities.copy()
    scatter_gas_particles(positions, velocities)
    assert np.allclose(velocities, after)  # Separating particles must not scatter again.


def test_no_contact_does_not_change_velocity() -> None:
    positions = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 0.0]])
    velocities = np.array([[2.0, 0.0], [-1.0, 0.0], [0.0, 1.0]])
    before = velocities.copy()
    scatter_gas_particles(positions, velocities)
    assert np.array_equal(velocities, before)
