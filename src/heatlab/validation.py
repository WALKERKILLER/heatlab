"""Headless numerical and visual validation report generator."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from heatlab.models import BrownianModel, GaltonModel, IdealGasModel, MaxwellModel
from heatlab.randomness import RandomManager


def generate(output_dir: Path, seed: int = 20_260_807) -> dict[str, float | int | str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    manager = RandomManager(seed)
    results: dict[str, float | int | str] = {"seed": seed}

    # 1. Ideal gas
    gas = IdealGasModel(manager.stream("validation-ideal"))
    gas.state.particle_count = 50_000
    gas.reset()
    gas.set_conditions(60.0, 1.6)
    target_atm = gas.state.pressure_atm
    kinetic_atm = gas.kinetic_pressure_pa() / 101_325.0
    results["ideal_target_pressure_atm"] = target_atm
    results["ideal_kinetic_pressure_atm"] = kinetic_atm
    results["ideal_relative_error"] = abs(kinetic_atm - target_atm) / target_atm

    fig = plt.figure(figsize=(10, 4.5), constrained_layout=True)
    ax1 = fig.add_subplot(1, 2, 1, projection="3d")
    pts = gas.display_positions[:600]
    ax1.scatter(pts[:, 0], pts[:, 1], pts[:, 2], s=6, alpha=0.55)
    ax1.set_box_aspect((gas.box_length, gas.box_height, gas.box_depth))
    ax1.set_xlim(0, gas.box_length)
    ax1.set_ylim(0, gas.box_height)
    ax1.set_zlim(0, gas.box_depth)
    ax1.set_title("Ideal-gas particle sample (3D)")
    ax1.set_xlabel("relative length")
    ax1.set_ylabel("relative height")
    ax1.set_zlabel("relative depth")
    ax2 = fig.add_subplot(1, 2, 2, projection="3d")
    temperatures = np.linspace(273.15, 373.15, 40)
    pressures = np.linspace(1.0, 2.0, 40)
    volumes = gas.state.amount_mol * 8.31446261815324 * temperatures / (pressures * 101_325) * 1000
    ax2.plot(pressures, volumes, temperatures)
    ax2.scatter([gas.state.pressure_atm], [gas.state.volume_litre], [gas.state.temperature_k], s=45)
    ax2.set_xlabel("P / atm")
    ax2.set_ylabel("V / L")
    ax2.set_zlabel("T / K")
    ax2.set_title("P-V-T state path")
    fig.savefig(output_dir / "validation_ideal_gas.png", dpi=150)
    plt.close(fig)

    # 2. Brownian motion
    brown = BrownianModel(manager.stream("validation-brownian"))
    brown.set_parameters(0.5, 40)
    for _ in range(1_600):
        brown.step(substeps=4)
    d_hat = brown.empirical_diffusion()
    results["brownian_theoretical_D"] = brown.params.theoretical_diffusion
    results["brownian_path_D_estimate"] = d_hat
    ensemble_d = BrownianModel.ensemble_diffusion_estimate(
        manager.stream("validation-brownian-ensemble"), path_count=2_000, steps=4_000
    )
    results["brownian_ensemble_D_estimate"] = ensemble_d

    points = np.asarray(brown.path)
    lag, msd = brown.msd_curve()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.2), constrained_layout=True)
    ax1.plot(points[:, 0], points[:, 1], linewidth=0.8)
    ax1.scatter(points[-1, 0], points[-1, 1], s=35)
    ax1.set_aspect("equal", adjustable="datalim")
    ax1.set_title("Brownian trajectory")
    ax1.set_xlabel("x")
    ax1.set_ylabel("y")
    ax2.plot(lag, msd, label="time-averaged MSD")
    ax2.plot(lag, 4 * brown.params.theoretical_diffusion * lag, "--", label="4Dt")
    ax2.set_title("MSD validation")
    ax2.set_xlabel("lag time")
    ax2.set_ylabel("MSD")
    ax2.legend()
    fig.savefig(output_dir / "validation_brownian.png", dpi=150)
    plt.close(fig)

    # 3. Maxwell distribution
    maxwell_model = MaxwellModel(manager.stream("validation-maxwell"))
    maxwell_model.set_temperature(100.0)
    v, pdf = maxwell_model.distribution_curve(10_000)
    area = float(np.trapezoid(pdf, v))
    sample = maxwell_model.sampled_speeds(200_000)
    results["maxwell_pdf_area"] = area
    results["maxwell_sample_mean_mps"] = float(sample.mean())
    results["maxwell_theoretical_mean_mps"] = maxwell_model.mean_speed

    fig, ax = plt.subplots(figsize=(7.2, 4.5), constrained_layout=True)
    ax.hist(sample, bins=70, density=True, alpha=0.35, label="Monte Carlo sample")
    ax.plot(v, pdf, linewidth=2, label="theoretical PDF")
    ax.set_title("Maxwell speed distribution at 100 °C")
    ax.set_xlabel("speed / m s$^{-1}$")
    ax.set_ylabel("density")
    ax.legend()
    fig.savefig(output_dir / "validation_maxwell.png", dpi=150)
    plt.close(fig)

    # 4. Galton board
    galton = GaltonModel(manager.stream("validation-galton"))
    batch = galton.simulate(100)
    bins = np.arange(galton.params.rows + 1)
    sample_mean = float(np.average(bins, weights=batch.counts))
    sample_var = float(np.average((bins - sample_mean) ** 2, weights=batch.counts))
    results["galton_N"] = int(batch.counts.sum())
    results["galton_sample_mean"] = sample_mean
    results["galton_sample_variance"] = sample_var
    results["galton_theoretical_probability_sum"] = float(batch.theoretical.sum())

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.5), constrained_layout=True)
    y = -np.arange(galton.params.rows + 1)
    for path in batch.paths[:35]:
        ax1.plot(path, y, alpha=0.18, linewidth=0.8)
    ax1.set_title("Galton-board Monte Carlo paths")
    ax1.set_xlabel("horizontal position")
    ax1.set_ylabel("row")
    ax1.set_aspect("equal", adjustable="box")
    ax2.bar(bins, batch.probabilities, alpha=0.5, label="simulation")
    ax2.plot(bins, batch.theoretical, "o-", label="binomial theory")
    ax2.set_title("Probability vs landing bin")
    ax2.set_xlabel("k")
    ax2.set_ylabel("probability")
    ax2.legend()
    fig.savefig(output_dir / "validation_galton.png", dpi=150)
    plt.close(fig)

    (output_dir / "validation_results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("validation_output"))
    parser.add_argument("--seed", type=int, default=20_260_807)
    args = parser.parse_args()
    results = generate(args.output_dir, args.seed)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
