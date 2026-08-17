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
| PyInstaller | Windows Web executable packaging | https://github.com/pyinstaller/pyinstaller |
| pytest / ruff / mypy | development tooling | respective upstream projects |

## Front-end (CDN, browser runtime)

| Asset | Role | Notes |
|---|---|---|
| Vue 3 | reactive UI shell | loaded from CDN in `templates/index.html` |
| Chart.js | charts (linear-axis PDF, planar families, MSD…) | loaded from CDN |
| Plotly.js (`plotly.js-dist-min@2.35.2`) | 3D P-V-T 相图（旋转/缩放/悬停） | loaded from CDN |
| KaTeX (`katex@0.16.11`) | 专题信息弹窗公式渲染 | script + CSS from CDN |

Binary redistributors should collect license/notice files from the resolved
dependency versions and review Qt licensing for their distribution method.
The Windows Web executable bundles the Python backend and local Web assets;
Vue, Chart.js, Plotly.js, and KaTeX are still fetched from their CDNs by the
browser at runtime, so a demo machine needs network access for the full UI.

## 算法/视觉参考（开源项目，仅借鉴思路，不复制源码）

| 项目 | 借鉴点 |
|---|---|
| `Yangliu20/physics-simulation` | 液体分子硬球弹性碰撞、轨迹/碰撞点可视化思路 |
| `ricbencar/galton-board-statistics` | 伽尔顿板「精确 Bernoulli 路径 + 平滑轨迹插值 + 落槽堆积」的呈现思路 |
| `clrsims/2d-brownian-motion` | 轨迹渐隐残影等视觉呈现思路 |

## Bundled font

| File | Role |
|---|---|
| `src/heatlab/web/static/fonts/DroidSansFallback.ttf` | CJK fallback for Web UI (`HeatLab CJK`) |

Confirm and comply with the upstream DroidSans / Android font licensing terms
before redistribution outside this educational project context.
