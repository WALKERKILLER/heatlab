"""Flask application factory and CLI for HeatLab Web."""

from __future__ import annotations

import argparse
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from heatlab.constants import DEFAULT_SEED
from heatlab.web import services
from heatlab.web.sessions import STORE


def create_app() -> Flask:
    package_dir = Path(__file__).resolve().parent
    app = Flask(
        __name__,
        template_folder=str(package_dir / "templates"),
        static_folder=str(package_dir / "static"),
        static_url_path="/static",
    )

    @app.get("/")
    def index():
        return render_template("index.html", default_seed=DEFAULT_SEED)

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "app": "heatlab-web", "mode": "live"})

    # ---- session lifecycle ----
    @app.post("/api/session")
    def create_session():
        payload = request.get_json(silent=True) or {}
        seed = int(payload.get("seed", request.args.get("seed", DEFAULT_SEED)))
        session = STORE.create(seed=seed)
        return jsonify({"session_id": session.session_id, "seed": session.seed})

    @app.post("/api/session/reset")
    def reset_session():
        payload = request.get_json(silent=True) or {}
        session_id = payload.get("session_id") or request.args.get("session_id")
        seed = int(payload.get("seed", DEFAULT_SEED))
        session = STORE.get_or_create(session_id, seed=seed)
        with session.lock:
            session.reset(seed)
        return jsonify({"session_id": session.session_id, "seed": session.seed})

    def _session_from_request():
        payload = request.get_json(silent=True) or {}
        session_id = (
            payload.get("session_id")
            or request.args.get("session_id")
            or request.headers.get("X-Session-Id")
        )
        seed = int(payload.get("seed", request.args.get("seed", DEFAULT_SEED)))
        return STORE.get_or_create(session_id, seed=seed), payload

    # ---- live ideal gas ----
    @app.post("/api/live/ideal-gas/set")
    def live_ideal_set():
        session, payload = _session_from_request()
        with session.lock:
            session.set_ideal(
                float(payload.get("temperature_c", 20.0)),
                float(payload.get("pressure_atm", 1.0)),
            )
            data = session.snapshot_ideal()
        return jsonify({"session_id": session.session_id, "data": data})

    @app.post("/api/live/ideal-gas/step")
    def live_ideal_step():
        session, payload = _session_from_request()
        steps = int(payload.get("steps", 1))
        with session.lock:
            data = session.step_ideal(steps)
        return jsonify({"session_id": session.session_id, "data": data})

    # ---- live brownian ----
    @app.post("/api/live/brownian/set")
    def live_brownian_set():
        session, payload = _session_from_request()
        with session.lock:
            session.set_brownian(
                float(payload.get("mass_ratio", 0.5)),
                int(payload.get("molecule_count", 40)),
            )
            data = session.snapshot_brownian()
        return jsonify({"session_id": session.session_id, "data": data})

    @app.post("/api/live/brownian/step")
    def live_brownian_step():
        session, payload = _session_from_request()
        steps = int(payload.get("steps", 1))
        with session.lock:
            data = session.step_brownian(steps)
        return jsonify({"session_id": session.session_id, "data": data})

    @app.post("/api/live/brownian/reset")
    def live_brownian_reset():
        session, payload = _session_from_request()
        with session.lock:
            data = session.reset_brownian()
        return jsonify({"session_id": session.session_id, "data": data})

    # ---- live maxwell ----
    @app.post("/api/live/maxwell/set")
    def live_maxwell_set():
        session, payload = _session_from_request()
        with session.lock:
            session.set_maxwell(float(payload.get("temperature_c", 20.0)))
            data = session.snapshot_maxwell(include_histogram=True)
        return jsonify({"session_id": session.session_id, "data": data})

    @app.post("/api/live/maxwell/step")
    def live_maxwell_step():
        session, payload = _session_from_request()
        steps = int(payload.get("steps", 1))
        with session.lock:
            data = session.step_maxwell(steps)
        return jsonify({"session_id": session.session_id, "data": data})

    @app.post("/api/live/maxwell/reset")
    def live_maxwell_reset():
        session, payload = _session_from_request()
        with session.lock:
            data = session.reset_maxwell()
        return jsonify({"session_id": session.session_id, "data": data})

    # ---- live galton ----
    @app.post("/api/live/galton/start")
    def live_galton_start():
        session, payload = _session_from_request()
        count = int(payload.get("particle_count", 50))
        with session.lock:
            data = session.start_galton(count)
        return jsonify({"session_id": session.session_id, "data": data})

    @app.post("/api/live/galton/step")
    def live_galton_step():
        session, payload = _session_from_request()
        steps = int(payload.get("steps", 1))
        with session.lock:
            data = session.step_galton(steps)
        return jsonify({"session_id": session.session_id, "data": data})

    # ---- legacy snapshot APIs (still useful for tests) ----
    @app.get("/api/ideal-gas")
    def api_ideal_gas():
        payload = services.ideal_gas_snapshot(
            seed=request.args.get("seed", default=DEFAULT_SEED, type=int),
            temperature_c=request.args.get("temperature_c", default=20.0, type=float),
            pressure_atm=request.args.get("pressure_atm", default=1.0, type=float),
            steps=request.args.get("steps", default=40, type=int),
        )
        return jsonify(payload)

    @app.get("/api/brownian")
    def api_brownian():
        payload = services.brownian_snapshot(
            seed=request.args.get("seed", default=DEFAULT_SEED, type=int),
            mass_ratio=request.args.get("mass_ratio", default=0.5, type=float),
            molecule_count=request.args.get("molecule_count", default=40, type=int),
            steps=request.args.get("steps", default=400, type=int),
        )
        return jsonify(payload)

    @app.get("/api/maxwell")
    def api_maxwell():
        payload = services.maxwell_snapshot(
            seed=request.args.get("seed", default=DEFAULT_SEED, type=int),
            temperature_c=request.args.get("temperature_c", default=20.0, type=float),
            sample_count=request.args.get("sample_count", default=8_000, type=int),
            steps=request.args.get("steps", default=30, type=int),
        )
        return jsonify(payload)

    @app.get("/api/galton")
    def api_galton():
        payload = services.galton_snapshot(
            seed=request.args.get("seed", default=DEFAULT_SEED, type=int),
            particle_count=request.args.get("particle_count", default=50, type=int),
        )
        return jsonify(payload)

    return app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="heatlab-web", description="HeatLab browser UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args(argv)
    app = create_app()
    # threaded=True so concurrent step polls from the browser do not block
    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
