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


def test_isothermal_process_preserves_temperature() -> None:
    model = IdealGasModel(RandomManager(10).stream("ideal"))
    model.set_process_mode("isothermal")
    model.set_conditions(50.0, 1.0)
    model.set_conditions(50.0, 1.5)
    assert np.isclose(model.state.temperature_k, 50.0 + 273.15)
    assert model.state.pressure_atm == 1.5


def test_isobaric_process_preserves_pressure() -> None:
    model = IdealGasModel(RandomManager(11).stream("ideal"))
    model.set_process_mode("isobaric")
    model.set_conditions(30.0, 1.4)
    model.set_conditions(80.0, 1.4)
    assert np.isclose(model.state.pressure_atm, 1.4)


def test_isochoric_process_preserves_volume() -> None:
    model = IdealGasModel(RandomManager(12).stream("ideal"))
    model.set_conditions(20.0, 1.0)
    initial_volume = model.state.volume_litre
    model.set_process_mode("isochoric")
    model.set_conditions(60.0, 1.0)
    assert np.isclose(model.state.volume_litre, initial_volume)
    assert model.state.pressure_atm > 1.0


def test_isotherm_theory_line_satisfies_pv_const() -> None:
    model = IdealGasModel(RandomManager(13).stream("ideal"))
    model.set_conditions(80.0, 1.5)
    pressures, volumes = model.isotherm_line()
    products = pressures * volumes
    assert np.allclose(products, products[0], rtol=1e-9)


def test_positions_are_three_dimensional() -> None:
    model = IdealGasModel(RandomManager(14).stream("ideal"))
    assert model.positions.shape[1] == 3
    assert model.velocities_si.shape[1] == 3
    assert model.box_height == 1.0
    assert model.box_depth == 1.0
    assert model.speeds.shape[0] == model.state.particle_count


def test_three_dimensional_step_keeps_particles_inside_box() -> None:
    model = IdealGasModel(RandomManager(15).stream("ideal"))
    for _ in range(200):
        model.step()
    positions = model.positions
    assert positions[:, 0].min() >= 0.0
    assert positions[:, 0].max() <= model.box_length
    assert positions[:, 1].min() >= 0.0
    assert positions[:, 1].max() <= model.box_height
    assert positions[:, 2].min() >= 0.0
    assert positions[:, 2].max() <= model.box_depth


def test_process_line_3d_isotherms_have_constant_temperature() -> None:
    model = IdealGasModel(RandomManager(16).stream("ideal"))
    model.set_process_mode("isothermal")
    pressures, volumes, temperatures = model.process_line_3d()
    assert pressures.shape == volumes.shape == temperatures.shape
    assert np.allclose(temperatures, model.state.temperature_k, rtol=1e-9)
    products = pressures * volumes
    assert np.allclose(products, products[0], rtol=1e-9)


def test_process_line_3d_free_mode_returns_none() -> None:
    model = IdealGasModel(RandomManager(17).stream("ideal"))
    assert model.process_line_3d() is None


def test_pvt_surface_follows_ideal_gas_law() -> None:
    model = IdealGasModel(RandomManager(18).stream("ideal"))
    pressures, volumes, temperatures = model.pvt_surface()
    assert pressures.shape == volumes.shape == temperatures.shape
    # 每个网格点都应满足 PV = nRT（单位：P atm、V L、T K）
    lhs = pressures * (volumes / 1_000.0) * 101_325.0
    rhs = model.state.amount_mol * GAS_CONSTANT * temperatures
    assert np.allclose(lhs, rhs, rtol=1e-9)
