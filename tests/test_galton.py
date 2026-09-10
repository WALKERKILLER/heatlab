import numpy as np

from heatlab.models.galton import GaltonModel, GaltonParameters
from heatlab.randomness import RandomManager
from heatlab.web.app import create_app


def test_galton_is_reproducible() -> None:
    a = GaltonModel(RandomManager(31).stream("galton")).simulate(100)
    b = GaltonModel(RandomManager(31).stream("galton")).simulate(100)
    assert np.array_equal(a.paths, b.paths)
    assert np.array_equal(a.counts, b.counts)


def test_galton_large_sample_matches_binomial_moments() -> None:
    model = GaltonModel(RandomManager(32).stream("galton"))
    # Validation is allowed to call the same algorithm with a larger N than the UI cap.
    decisions = model.rng.random((200_000, model.params.rows)) < model.params.probability_right
    final_bins = decisions.sum(axis=1)
    assert np.isclose(final_bins.mean(), 6.0, atol=0.02)
    assert np.isclose(final_bins.var(), 3.0, atol=0.04)


def test_theoretical_probabilities_sum_to_one() -> None:
    batch = GaltonModel(RandomManager(33).stream("galton")).simulate(50)
    assert np.isclose(batch.theoretical.sum(), 1.0)
    assert np.isclose(batch.probabilities.sum(), 1.0)


def test_invalid_galton_parameters_are_rejected() -> None:
    with np.testing.assert_raises(ValueError):
        GaltonParameters(rows=0)
    with np.testing.assert_raises(ValueError):
        GaltonParameters(probability_right=np.nan)
    with np.testing.assert_raises(ValueError):
        GaltonParameters(particle_count=0)


def test_live_galton_endpoint_rejects_invalid_particle_count() -> None:
    client = create_app().test_client()
    assert client.post("/api/live/galton/start", json={"particle_count": 0}).status_code == 400
