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


def test_liquid_molecules_stay_in_box() -> None:
    model = BrownianModel(RandomManager(12).stream("brownian"))
    for _ in range(60):
        model.step()
    positions = np.asarray(model.liquid_positions)
    assert np.all(positions >= 0.0 - 1e-9)
    assert np.all(positions <= 1.0 + 1e-9)


def test_liquid_molecules_do_not_overlap_pollen() -> None:
    model = BrownianModel(RandomManager(12).stream("brownian"))
    for _ in range(40):
        model.step()
    radius_sum = model.params.pollen_radius + 0.012
    for liquid in model.liquid_positions:
        assert np.linalg.norm(liquid - model.position) >= radius_sum - 1e-9


def test_hard_sphere_collisions_trigger() -> None:
    model = BrownianModel(RandomManager(12).stream("brownian"))
    model.set_parameters(0.5, 100)
    for _ in range(80):
        model.step()
    assert model.liquid_collision_count > 0
    # Equal-mass elastic collisions conserve total kinetic energy, so the
    # speed distribution should stay roughly Maxwell-shaped (mean ~ sigma).
    speeds = np.asarray(model.liquid_speeds)
    assert np.isclose(speeds.mean(), model.liquid_speed_sigma, rtol=0.3)


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
