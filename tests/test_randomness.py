import numpy as np

from heatlab.randomness import RandomManager


def test_named_stream_is_reproducible() -> None:
    a = RandomManager(1234).stream("galton").random(8)
    b = RandomManager(1234).stream("galton").random(8)
    assert np.array_equal(a, b)


def test_named_streams_are_independent() -> None:
    manager = RandomManager(1234)
    a = manager.stream("galton").random(8)
    b = manager.stream("maxwell").random(8)
    assert not np.array_equal(a, b)
