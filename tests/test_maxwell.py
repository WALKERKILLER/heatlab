import numpy as np

from heatlab.models.maxwell import MaxwellModel, MaxwellState, _reflect_unit_interval
from heatlab.randomness import RandomManager


def test_maxwell_pdf_normalizes_to_one() -> None:
    model = MaxwellModel(RandomManager(21).stream("maxwell"))
    velocity, density = model.distribution_curve(points=20_000)
    area = np.trapezoid(density, velocity)
    assert np.isclose(area, 1.0, rtol=2e-4)


def test_sample_mean_matches_theory() -> None:
    model = MaxwellModel(RandomManager(22).stream("maxwell"))
    model.set_temperature(100.0)
    sample = model.sampled_speeds(200_000)
    assert np.isclose(sample.mean(), model.mean_speed, rtol=0.006)


def test_characteristic_speed_order() -> None:
    model = MaxwellModel(RandomManager(23).stream("maxwell"))
    assert model.most_probable_speed < model.mean_speed < model.rms_speed


def test_component_pdf_normalizes_to_one() -> None:
    model = MaxwellModel(RandomManager(24).stream("maxwell"))
    velocity, density = model.component_curve(points=20_000)
    area = np.trapezoid(density, velocity)
    assert np.isclose(area, 1.0, rtol=2e-4)


def test_sampled_components_match_gaussian_moments() -> None:
    model = MaxwellModel(RandomManager(25).stream("maxwell"))
    model.set_temperature(100.0)
    sample = model.sampled_components(200_000)
    assert np.isclose(sample.mean(), 0.0, atol=3.0)
    assert np.isclose(sample.var(), model.state.scale**2, rtol=0.01)


def test_large_time_step_reflection_keeps_particles_in_box() -> None:
    model = MaxwellModel(RandomManager(26).stream("maxwell"))
    model.step(dt=2.0)
    assert np.all(model.positions >= 0.0)
    assert np.all(model.positions <= 1.0)


def test_wall_reflection_reverses_the_crossing_velocity_not_the_folded_position() -> None:
    positions = np.array([[-0.2, 0.5], [1.2, 0.5], [2.2, 0.5], [-1.2, 0.5]])
    velocities = np.array([[-3., 4., 5.], [3., 4., 5.], [3., 4., 5.], [-3., 4., 5.]])
    energy = np.sum(velocities**2)
    _reflect_unit_interval(positions, velocities, 0)
    assert np.allclose(positions[:, 0], [0.2, 0.8, 0.2, 0.8])
    assert np.allclose(velocities[:, 0], [3., -3., 3., -3.])
    assert np.sum(velocities**2) == energy


def test_long_running_gas_does_not_accumulate_at_corners() -> None:
    model = MaxwellModel(RandomManager(29).stream("wall-equilibrium"))
    energy = np.sum(model.velocities_si**2)
    samples = []
    for step in range(2000):
        model.step()
        if step >= 1000 and step % 10 == 0:
            samples.append(model.positions.copy())
    positions = np.concatenate(samples)
    assert np.allclose(positions.mean(axis=0), [0.5, 0.5], atol=0.04)
    corners = np.all((positions < 0.08) | (positions > 0.92), axis=1)
    assert corners.mean() < 0.05
    assert np.isclose(np.sum(model.velocities_si**2), energy, rtol=1e-12)


def test_wall_reflection_reverses_velocity_component() -> None:
    """回归：反射掩码必须基于越界前的坐标计算。

    曾经 ``raw = positions[:, axis]`` 是视图，位置写回折叠坐标后掩码读到
    的是折叠后的值，速度几乎永不反转：粒子被反复折回边界薄层，最终全部
    卡死在四角。
    """
    model = MaxwellModel(
        RandomManager(28).stream("maxwell"), MaxwellState(particle_count=1)
    )
    model.positions = np.array([[0.98, 0.5]])
    model.velocities_si = np.array([[500.0, 0.0, 0.0]])
    model.step()
    assert model.velocities_si[0, 0] < 0.0
    position_after_bounce = float(model.positions[0, 0])
    assert 0.0 <= position_after_bounce <= 1.0
    model.step()
    assert model.positions[0, 0] < position_after_bounce


def test_particles_spread_instead_of_sticking_to_corners() -> None:
    """回归：长时间运行后粒子应近似均匀分布，而不是聚集在四角。"""
    model = MaxwellModel(RandomManager(29).stream("maxwell"))
    for _ in range(2_000):
        model.step()
    points = model.positions
    interior = (
        (points[:, 0] > 0.25)
        & (points[:, 0] < 0.75)
        & (points[:, 1] > 0.25)
        & (points[:, 1] < 0.75)
    )
    assert float(np.mean(interior)) > 0.10


def test_invalid_temperature_and_time_step_are_rejected() -> None:
    model = MaxwellModel(RandomManager(27).stream("maxwell"))
    with np.testing.assert_raises(ValueError):
        model.set_temperature(np.inf)
    with np.testing.assert_raises(ValueError):
        model.step(dt=0.0)


def test_animation_heating_and_axes_use_a_fixed_reference_scale() -> None:
    model = MaxwellModel(RandomManager(28).stream("heating"))
    model.set_temperature(0)
    cold = model.display_velocities.copy()
    limits = (model.fixed_speed_limit, model.fixed_component_limit)
    model.set_temperature(100)
    assert np.allclose(model.display_velocities, cold * np.sqrt(373.15 / 273.15))
    assert (model.fixed_speed_limit, model.fixed_component_limit) == limits
