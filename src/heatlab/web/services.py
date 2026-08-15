"""JSON-friendly service layer wrapping HeatLab numerical models."""

from __future__ import annotations

from typing import Any

import numpy as np

from heatlab.constants import DEFAULT_SEED, STANDARD_ATMOSPHERE
from heatlab.models import BrownianModel, GaltonModel, IdealGasModel, MaxwellModel
from heatlab.randomness import RandomManager


def _array_to_list(values: np.ndarray, *, limit: int | None = None) -> list[Any]:
    data = np.asarray(values, dtype=float)
    if limit is not None and len(data) > limit:
        data = data[:limit]
    return data.tolist()


def ideal_gas_snapshot(
    *,
    seed: int = DEFAULT_SEED,
    temperature_c: float = 20.0,
    pressure_atm: float = 1.0,
    steps: int = 40,
) -> dict[str, Any]:
    model = IdealGasModel(RandomManager(seed).stream("ideal-gas"))
    model.set_conditions(temperature_c, pressure_atm)
    for _ in range(max(0, steps)):
        model.step()
    state = model.state
    history = np.asarray(model.phase_history, dtype=float)
    process_line = model.process_line()
    process_line_3d = model.process_line_3d()
    surface_p, surface_v, surface_t = model.pvt_surface()
    return {
        "temperature_c": state.temperature_c,
        "pressure_atm": state.pressure_atm,
        "temperature_k": state.temperature_k,
        "volume_litre": state.volume_litre,
        "box_width": model.box_width,
        "box_length": model.box_length,
        "box_height": model.box_height,
        "box_depth": model.box_depth,
        "kinetic_pressure_atm": model.kinetic_pressure_pa() / STANDARD_ATMOSPHERE,
        "positions": _array_to_list(model.display_positions),
        "speeds": _array_to_list(model.speeds),
        "phase_history": _array_to_list(history),
        "process_mode": state.process_mode,
        "process_line": (
            {"points": _array_to_list(np.column_stack(process_line))}
            if process_line is not None
            else None
        ),
        "process_line_3d": (
            {"points": _array_to_list(np.column_stack(process_line_3d))}
            if process_line_3d is not None
            else None
        ),
        "pvt_surface": {
            "x": _array_to_list(surface_p),
            "y": _array_to_list(surface_v),
            "z": _array_to_list(surface_t),
        },
        "planar": model.planar_families(),
    }


def brownian_snapshot(
    *,
    seed: int = DEFAULT_SEED,
    mass_ratio: float = 0.5,
    molecule_count: int = 40,
    steps: int = 400,
) -> dict[str, Any]:
    model = BrownianModel(RandomManager(seed).stream("brownian"))
    model.set_parameters(mass_ratio, molecule_count)
    for _ in range(max(1, steps)):
        model.step(substeps=4)
    path = np.asarray(model.path, dtype=float)
    lag, msd = model.msd_curve()
    d_hat = model.empirical_diffusion()
    return {
        "mass_ratio": model.params.mass_ratio,
        "molecule_count": model.params.molecule_count,
        "elapsed": model.elapsed,
        "theoretical_D": model.params.theoretical_diffusion,
        "empirical_D": None if np.isnan(d_hat) else float(d_hat),
        "path": _array_to_list(path, limit=2_500),
        # 液体粒子层：位置 / 速率（前端画热运动场景与速度分布）
        "liquid_positions": _array_to_list(model.liquid_positions),
        "liquid_speeds": _array_to_list(model.liquid_speeds),
        "liquid_sigma": model.liquid_speed_sigma,
        # 花粉粒子：位置 / 速度 / 半径（前端画大颗粒与方向箭头）
        "pollen_position": _array_to_list(model.position),
        "pollen_velocity": _array_to_list(model.velocity),
        "pollen_radius": model.params.pollen_radius,
        "collision_count": model.collision_count,
        "recent_collisions": _array_to_list(np.asarray(model.recent_collisions)),
        "msd_lag": _array_to_list(lag),
        "msd": _array_to_list(msd),
        # 液体速率分布直方图 + 2-D 麦克斯韦理论曲线
        **(_liquid_speed_distribution(model.liquid_speeds, model.liquid_speed_sigma)),
    }


def _liquid_speed_distribution(
    speeds: np.ndarray, sigma: float, bins: int = 30
) -> dict[str, Any]:
    """2-D Maxwell-Boltzmann histogram (f(v)=v/σ²·exp(-v²/2σ²)) for liquids."""

    if len(speeds) < 4 or sigma <= 0.0:
        return {"speed_hist_v": [], "speed_hist_f": [], "speed_theory_v": [], "speed_theory_f": []}
    hist_counts, bin_edges = np.histogram(speeds, bins=bins, density=True)
    bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])
    theory_v = np.linspace(0.0, float(bin_edges[-1]), 120)
    theory_f = (theory_v / sigma**2) * np.exp(-(theory_v**2) / (2.0 * sigma**2))
    return {
        "speed_hist_v": _array_to_list(bin_centers),
        "speed_hist_f": _array_to_list(hist_counts),
        "speed_theory_v": _array_to_list(theory_v),
        "speed_theory_f": _array_to_list(theory_f),
    }


def maxwell_snapshot(
    *,
    seed: int = DEFAULT_SEED,
    temperature_c: float = 20.0,
    sample_count: int = 8_000,
    steps: int = 30,
) -> dict[str, Any]:
    model = MaxwellModel(RandomManager(seed).stream("maxwell"))
    model.set_temperature(temperature_c)
    for _ in range(max(0, steps)):
        model.step()
    velocity, density = model.distribution_curve()
    comp_velocity, comp_density = model.component_curve()
    samples = model.sampled_speeds(sample_count)
    hist_counts, bin_edges = np.histogram(samples, bins=42, density=True)
    bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])
    comp_samples = model.sampled_components(sample_count)
    comp_counts, comp_edges = np.histogram(comp_samples, bins=44, density=True)
    comp_centers = 0.5 * (comp_edges[:-1] + comp_edges[1:])
    return {
        "temperature_c": model.state.temperature_c,
        "most_probable_speed": model.most_probable_speed,
        "mean_speed": model.mean_speed,
        "rms_speed": model.rms_speed,
        "positions": _array_to_list(model.positions),
        "speeds": _array_to_list(model.speeds),
        "pdf_v": _array_to_list(velocity),
        "pdf_f": _array_to_list(density),
        "hist_v": _array_to_list(bin_centers),
        "hist_f": _array_to_list(hist_counts),
        "component_pdf_v": _array_to_list(comp_velocity),
        "component_pdf_f": _array_to_list(comp_density),
        "component_hist_v": _array_to_list(comp_centers),
        "component_hist_f": _array_to_list(comp_counts),
    }


def galton_snapshot(
    *,
    seed: int = DEFAULT_SEED,
    particle_count: int = 50,
) -> dict[str, Any]:
    model = GaltonModel(RandomManager(seed).stream("galton"))
    batch = model.simulate(particle_count)
    rows = model.params.rows
    bins = list(range(rows + 1))
    return {
        "rows": rows,
        "particle_count": int(batch.counts.sum()),
        "bins": bins,
        "counts": _array_to_list(batch.counts),
        "probabilities": _array_to_list(batch.probabilities),
        "theoretical": _array_to_list(batch.theoretical),
        "paths": _array_to_list(batch.paths),
        "sample_mean": float(np.average(bins, weights=batch.counts)),
        "sample_variance": float(
            np.average((np.asarray(bins) - np.average(bins, weights=batch.counts)) ** 2, weights=batch.counts)
        ),
    }
