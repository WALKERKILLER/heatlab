# Third-party notices

HeatLab depends on third-party packages and assets that retain their own licenses.
This file is an engineering inventory, not a substitute for the license text
shipped by each dependency.

## Python packages

| Package | Role | Project |
|---|---|---|
| NumPy | arrays and random number generation | https://github.com/numpy/numpy |
| SciPy | Maxwell and binomial reference distributions | https://github.com/scipy/scipy |
| Matplotlib | scientific plots (desktop) | https://github.com/matplotlib/matplotlib |
| PySide6 / Qt for Python | desktop GUI | https://doc.qt.io/qtforpython-6/ |
| Flask | browser UI HTTP API | https://github.com/pallets/flask |
| pytest / ruff / mypy | development tooling | respective upstream projects |

## Front-end (CDN, browser runtime)

| Asset | Role | Notes |
|---|---|---|
| Vue 3 | reactive UI shell | loaded from CDN in `templates/index.html` |
| Chart.js | charts | loaded from CDN |

Binary redistributors should collect license/notice files from the resolved
dependency versions and review Qt licensing for their distribution method.

## Bundled font

| File | Role |
|---|---|
| `src/heatlab/web/static/fonts/DroidSansFallback.ttf` | CJK fallback for Web UI (`HeatLab CJK`) |

Confirm and comply with the upstream DroidSans / Android font licensing terms
before redistribution outside this educational project context.
