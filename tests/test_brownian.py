import numpy as np

from heatlab.models.brownian import BrownianModel
from heatlab.randomness import RandomManager


def test_brownian_path_is_reproducible() -> None:
    a = BrownianModel(RandomManager(12).stream("brownian"))
    b = BrownianModel(RandomManager(12).stream("brownian"))
    for _ in range(100):
        a.step()
        b.step()
    assert np.allclose(a.path, b.path)


def test_ensemble_diffusion_converges_to_langevin_value() -> None:
    rng = RandomManager(13).stream("validation")
    estimate = BrownianModel.ensemble_diffusion_estimate(
        rng,
        path_count=2_000,
        steps=4_000,
        dt=0.005,
        mass=0.5,
        gamma=1.0,
        thermal_energy=1.0,
    )
    assert np.isclose(estimate, 1.0, rtol=0.12)
