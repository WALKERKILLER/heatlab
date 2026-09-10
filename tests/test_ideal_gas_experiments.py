import numpy as np

from heatlab.constants import GAS_CONSTANT
from heatlab.models import HeatExchangeModel, IdealGasModel, IdealGasState
from heatlab.randomness import RandomManager
from heatlab.web.app import create_app
from heatlab.web.sessions import LiveSession


def test_micro_and_process_modes_expose_one_independent_control() -> None:
    model = IdealGasModel(RandomManager(21).stream("ideal"))

    model.configure_experiment("temperature-micro", temperature_c=80.0)
    fixed_volume = model.state.volume_m3
    assert np.isclose(model.state.pressure_pa * fixed_volume, model.state.amount_mol * GAS_CONSTANT * model.state.temperature_k)

    model.configure_experiment("pressure-micro", volume_litre=model.state.volume_litre * 2.0)
    assert np.isclose(model.state.temperature_c, 80.0)
    assert np.isclose(model.state.volume_litre, fixed_volume * 2_000.0)

    model.configure_experiment("isobaric", temperature_c=60.0, pressure_atm=1.0)
    assert np.isclose(model.state.pressure_atm, 1.0)
    model.configure_experiment("isochoric", temperature_c=40.0)
    fixed_volume = model.state.volume_m3
    model.configure_experiment("isochoric", temperature_c=90.0)
    assert np.isclose(model.state.volume_m3, fixed_volume)


def test_isothermal_and_adiabatic_paths_use_their_documented_invariants() -> None:
    model = IdealGasModel(RandomManager(22).stream("ideal"))
    model.configure_experiment("isothermal", temperature_c=50.0, volume_litre=20.0)
    initial_pv = model.state.pressure_pa * model.state.volume_m3
    model.configure_experiment("isothermal", volume_litre=40.0)
    assert np.isclose(model.state.pressure_pa * model.state.volume_m3, initial_pv)

    model.configure_experiment("first-law", volume_litre=model.state.volume_litre)
    initial_volume = model.state.volume_m3
    initial_temperature = model.state.temperature_k
    model.configure_experiment("first-law", volume_litre=initial_volume * 1_000.0 * 1.8)
    assert np.isclose(model.heat_added_j, 0.0)
    assert np.isclose(
        model.internal_energy_j - model.adiabatic_initial_internal_energy_j + model.work_by_gas_j,
        0.0,
        atol=1e-14,
    )
    assert model.state.temperature_k < initial_temperature
    pressures, volumes = model.adiabatic_line()
    assert np.allclose(pressures * volumes**model.ADIABATIC_GAMMA, pressures[0] * volumes[0]**model.ADIABATIC_GAMMA)


def test_heat_exchange_is_energy_balanced_and_particles_stay_in_chambers() -> None:
    model = HeatExchangeModel(RandomManager(23).stream("heat"))
    model.configure(barrier="conductive", temperature_left_c=80.0, temperature_right_c=20.0)
    assert model.kinetic_pressure_left_pa() > 0.0
    assert model.kinetic_pressure_right_pa() > 0.0
    initial_energy = model.state.internal_energy_left_j + model.state.internal_energy_right_j
    for _ in range(1_000):
        model.step()
    final_energy = model.state.internal_energy_left_j + model.state.internal_energy_right_j
    assert np.isclose(final_energy, initial_energy, rtol=1e-12)
    assert 20.0 < model.state.temperature_right_c < model.state.temperature_left_c < 80.0
    assert model.state.temperature_left_c - model.state.temperature_right_c < 1.0e-3
    assert np.all(model.positions_left[:, 0] <= 0.5)
    assert np.all(model.positions_right[:, 0] >= 0.5)

    model.configure(barrier="adiabatic", temperature_left_c=80.0, temperature_right_c=20.0)
    for _ in range(100):
        model.step()
    assert np.isclose(model.state.temperature_left_c, 80.0)
    assert np.isclose(model.state.temperature_right_c, 20.0)
    assert np.isclose(model.heat_transferred_j, 0.0)


def test_centered_finite_particle_pressure_estimate_is_unbiased() -> None:
    ratios = []
    for seed in range(40):
        model = IdealGasModel(RandomManager(seed).stream("pressure-sample"))
        model.configure_experiment(
            "pressure-micro",
            volume_litre=model.reference_volume_litre,
            demo_particle_count=5,
        )
        ratios.append(model.kinetic_pressure_pa() / model.state.pressure_pa)
    assert np.isclose(np.mean(ratios), 1.0, atol=0.12)


def test_session_does_not_leak_first_law_energy_into_isothermal_mode() -> None:
    session = LiveSession(24)
    reference = session.ideal.reference_volume_litre
    session.set_ideal(20.0, 1.0, experiment_mode="first-law", volume_litre=reference * 2.0)
    assert session.snapshot_ideal()["observables"]["work_by_gas_j"] > 0.0

    previous_temperature = session.ideal.state.temperature_c
    session.set_ideal(None, 1.0, experiment_mode="isothermal", volume_litre=session.ideal.state.volume_litre)
    snapshot = session.snapshot_ideal()
    assert np.isclose(session.ideal.state.temperature_c, previous_temperature)
    assert snapshot["observables"]["work_by_gas_j"] == 0.0
    assert snapshot["observables"]["heat_added_j"] == 0.0


def test_switching_through_heat_exchange_starts_a_fresh_adiabatic_anchor() -> None:
    session = LiveSession(25)
    reference = session.ideal.reference_volume_litre
    session.set_ideal(20.0, 1.0, experiment_mode="first-law", volume_litre=reference * 2.0)
    session.set_ideal(20.0, 1.0, experiment_mode="heat-exchange")
    current_volume = session.ideal.state.volume_litre
    session.set_ideal(None, 1.0, experiment_mode="first-law", volume_litre=current_volume)
    snapshot = session.snapshot_ideal()
    assert np.isclose(snapshot["observables"]["work_by_gas_j"], 0.0, atol=1.0e-14)
    assert np.isclose(snapshot["observables"]["delta_internal_energy_j"], 0.0, atol=1.0e-14)


def test_reflection_keeps_particles_inside_for_large_time_steps() -> None:
    model = IdealGasModel(RandomManager(26).stream("large-step"))
    model.step(dt=2.0)
    assert np.all(model.positions >= 0.0)
    assert np.all(model.positions[:, 0] <= model.box_length)
    assert np.all(model.positions[:, 1] <= model.box_height)
    assert np.all(model.positions[:, 2] <= model.box_depth)


def test_invalid_physical_inputs_are_rejected() -> None:
    with np.testing.assert_raises(ValueError):
        IdealGasModel(RandomManager(27).stream("invalid"), state=IdealGasState(amount_mol=0.0))
    with np.testing.assert_raises(ValueError):
        HeatExchangeModel(RandomManager(28).stream("invalid"), thermal_conductance_w_per_k=-1.0)
    with np.testing.assert_raises(ValueError):
        IdealGasModel(RandomManager(29).stream("invalid")).step(dt=0.0)
    with np.testing.assert_raises(ValueError):
        HeatExchangeModel(RandomManager(30).stream("invalid")).step(dt=np.nan)


def test_live_heat_exchange_endpoint_returns_a_valid_snapshot() -> None:
    client = create_app().test_client()
    response = client.post(
        "/api/live/ideal-gas/set",
        json={"experiment_mode": "heat-exchange", "barrier": "conductive"},
    )
    assert response.status_code == 200
    payload = response.get_json()
    session_id = payload["session_id"]
    snapshot = payload["data"]
    assert snapshot["scene"]["divider"] == "conductive"
    assert snapshot["observables"]["kinetic_pressure_left_atm"] > 0.0
    step_response = client.post(
        "/api/live/ideal-gas/step",
        json={"session_id": session_id, "steps": 1},
    )
    assert step_response.status_code == 200


def test_live_parameter_endpoints_reject_non_finite_inputs() -> None:
    client = create_app().test_client()
    assert client.post("/api/live/maxwell/set", json={"temperature_c": float("nan")}).status_code == 400
    assert client.post("/api/live/brownian/set", json={"mass_ratio": float("nan")}).status_code == 400
