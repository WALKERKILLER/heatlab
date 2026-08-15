import numpy as np

from heatlab.models.maxwell import MaxwellModel
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

