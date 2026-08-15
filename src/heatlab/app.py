"""HeatLab executable entry point.

Examples
--------
heatlab
heatlab --topic all
heatlab --topic ideal-gas
heatlab --topic brownian
heatlab --topic maxwell
heatlab --topic galton
"""

from __future__ import annotations

import argparse
import sys

from heatlab.constants import DEFAULT_SEED
from heatlab.ui.topic_window import TOPIC_SPECS


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="heatlab",
        description="HeatLab desktop scientific-computing visualizations",
    )
    parser.add_argument(
        "--topic",
        choices=["all", *sorted(TOPIC_SPECS.keys())],
        default="all",
        help="all=四专题合并窗口；其余为单专题独立窗口",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help=f"随机种子（默认 {DEFAULT_SEED}）",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    try:
        from PySide6.QtWidgets import QApplication
    except ModuleNotFoundError as exc:
        if exc.name != "PySide6":
            raise
        print(
            "HeatLab GUI requires PySide6. Install project dependencies first, "
            "then run heatlab again.",
            file=sys.stderr,
        )
        return 2

    app = QApplication(sys.argv)
    app.setApplicationName("HeatLab")
    app.setOrganizationName("HeatLab")

    if args.topic == "all":
        from heatlab.ui.main_window import MainWindow

        window = MainWindow()
        if args.seed != DEFAULT_SEED:
            window.top_bar.seed_spin.setValue(args.seed)
            window.rebuild_tabs(args.seed)
    else:
        from heatlab.ui.topic_window import TopicWindow

        window = TopicWindow(args.topic, seed=args.seed)

    window.show()
    return app.exec()


def main_ideal_gas() -> int:
    return main(["--topic", "ideal-gas"])


def main_brownian() -> int:
    return main(["--topic", "brownian"])


def main_maxwell() -> int:
    return main(["--topic", "maxwell"])


def main_galton() -> int:
    return main(["--topic", "galton"])


if __name__ == "__main__":
    raise SystemExit(main())
