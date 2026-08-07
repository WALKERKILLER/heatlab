import numpy as np

from heatlab.constants import GAS_CONSTANT
from heatlab.models.ideal_gas import IdealGasModel
from heatlab.randomness import RandomManager


def test_ideal_gas_law_is_satisfied() -> None:
    model = IdealGasModel(RandomManager(7).stream("ideal"))
    model.set_conditions(80.0, 1.75)
    state = model.state
    lhs = state.pressure_pa * state.volume_m3
    rhs = state.amount_mol * GAS_CONSTANT * state.temperature_k
    assert np.isclose(lhs, rhs, rtol=1e-13)


def test_display_volume_increases_with_temperature_and_decreases_with_pressure() -> None:
    model = IdealGasModel(RandomManager(8).stream("ideal"))
    model.set_conditions(0.0, 1.0)
    cold_width = model.box_width
    model.set_conditions(100.0, 1.0)
    hot_width = model.box_width
    model.set_conditions(100.0, 2.0)
    compressed_width = model.box_width
    assert hot_width > cold_width
    assert compressed_width < hot_width


def test_kinetic_pressure_matches_target_statistically() -> None:
    model = IdealGasModel(RandomManager(9).stream("ideal"))
    model.state.particle_count = 150_000
    model.reset()
    model.set_conditions(50.0, 1.4)
    estimate = model.kinetic_pressure_pa()
    assert np.isclose(estimate, model.state.pressure_pa, rtol=0.025)
