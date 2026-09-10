import numpy as np

from heatlab.models.brownian import BrownianModel
from heatlab.randomness import RandomManager
from heatlab.web.services import brownian_snapshot


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


def test_single_liquid_molecule_does_not_push_without_contact() -> None:
    model = BrownianModel(RandomManager(12).stream("brownian"))
    model.set_parameters(0.5, 1)
    model.liquid_positions[0] = [0.1, 0.1]
    model.liquid_velocities[0] = [0.0, 0.0]
    model.step(substeps=1)
    assert model.collision_count == 0
    assert np.allclose(model.position, [0.5, 0.5])
    assert np.allclose(model.path[-1], [0.5, 0.5])


def test_pollen_collision_exchanges_momentum_and_energy() -> None:
    model = BrownianModel(RandomManager(12).stream("brownian"))
    model.set_parameters(0.5, 1)
    radius_sum = model.params.pollen_radius + 0.012
    model.liquid_positions[0] = [0.5 + radius_sum - 0.001, 0.5]
    model.liquid_velocities[0] = [-1.0, 0.0]
    model.velocity = np.zeros(2)
    liquid_mass = 0.02
    pollen_mass = model.params.effective_mass
    momentum_before = liquid_mass * model.liquid_velocities[0] + pollen_mass * model.velocity
    energy_before = 0.5 * liquid_mass * np.sum(model.liquid_velocities[0] ** 2)
    model._collide_with_pollen()
    momentum_after = liquid_mass * model.liquid_velocities[0] + pollen_mass * model.velocity
    energy_after = (
        0.5 * liquid_mass * np.sum(model.liquid_velocities[0] ** 2)
        + 0.5 * pollen_mass * np.sum(model.velocity ** 2)
    )
    assert model.collision_count == 1
    assert np.allclose(momentum_after, momentum_before)
    assert np.isclose(energy_after, energy_before)
    assert np.linalg.norm(model.liquid_positions[0] - model.position) >= radius_sum - 1e-9


def test_pollen_wall_reflection_points_inward() -> None:
    model = BrownianModel(RandomManager(12).stream("brownian"))
    radius = model.params.pollen_radius
    model.position = np.array([radius - 0.01, 0.5])
    model.velocity = np.array([-1.0, 0.0])
    model._bounce_pollen()
    assert model.velocity[0] > 0.0
    assert model.position[0] >= radius


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


def test_dense_liquid_molecules_do_not_overlap_each_other() -> None:
    model = BrownianModel(RandomManager(14).stream("brownian"))
    model.set_parameters(0.5, 100)
    for _ in range(80):
        model.step()
    delta = model.liquid_positions[:, None, :] - model.liquid_positions[None, :, :]
    distances = np.sqrt(np.einsum("ijk,ijk->ij", delta, delta))
    distances[np.diag_indices_from(distances)] = np.inf
    assert np.all(distances >= 2.0 * 0.012 - 1e-9)


def test_dense_liquid_separation_is_stable_across_repeated_runs() -> None:
    for seed in range(10):
        model = BrownianModel(RandomManager(seed).stream("brownian"))
        model.set_parameters(0.5, 100)
        for _ in range(20):
            model.step()
        delta = model.liquid_positions[:, None, :] - model.liquid_positions[None, :, :]
        distances = np.sqrt(np.einsum("ijk,ijk->ij", delta, delta))
        distances[np.diag_indices_from(distances)] = np.inf
        assert distances.min() >= 2.0 * 0.012 - 1e-9


def test_single_liquid_molecule_keeps_speed_distribution_visible() -> None:
    payload = brownian_snapshot(seed=12, mass_ratio=0.05, molecule_count=1, steps=1)
    assert payload["speed_hist_v"]
    assert np.all(np.isfinite(payload["speed_hist_f"]))


def test_parameter_change_starts_a_fresh_diffusion_sample() -> None:
    model = BrownianModel(RandomManager(15).stream("brownian"))
    model.step()
    model.set_parameters(0.8, 1)
    assert model.elapsed == 0.0
    assert len(model.path) == 1
    assert model.collision_count == 0
    assert model.liquid_collision_count == 0


def test_non_finite_mass_ratio_is_rejected() -> None:
    model = BrownianModel(RandomManager(16).stream("brownian"))
    with np.testing.assert_raises(ValueError):
        model.set_parameters(np.nan, 40)


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
