# HeatLab · 热学科学计算可视化

[![CI](https://github.com/WALKERKILLER/heatlab/actions/workflows/ci.yml/badge.svg)](https://github.com/WALKERKILLER/heatlab/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.1.0-green.svg)](CHANGELOG.md)

> 交互式热学科学计算实验台：理想气体 · 布朗运动 · 麦克斯韦速率分布 · 伽尔顿板
> 提供 **浏览器实时版**、**Windows Web 一键演示版（推荐）** 与旧版 PySide6 源码入口。

> [!IMPORTANT]
> ## 🖥️ 强烈推荐使用 Web 端
> 旧桌面版（PySide6）功能较为基础，仅用于源码对照；**所有完整交互体验都集中在浏览器实时版**：3D P-V-T 相图（旋转/缩放/悬停）、P-V / P-T / V-T 平面图、首次进入专题的实验说明（KaTeX 公式）、图表全屏放大、自动步进与采样等。
>
> 启动方式（只需 Python 环境）：
>
> ```bash
> ./.venv/bin/heatlab-web        # 或 Windows: .venv\Scripts\heatlab-web.exe
> # 浏览器打开 http://127.0.0.1:8765
> ```
>
> **不想安装 Python？** 下载 GitHub Actions 构建的 `HeatLab-Web-win64.zip`，解压后双击 `HeatLab-Web.exe`；它会自动启动本地 Flask 后端并打开默认浏览器。演示版前端仍从 CDN 加载 Vue、Chart.js、Plotly 与 KaTeX，因此演示电脑需要联网。

![Validation montage](examples/validation/validation_montage.png)

---

## 目录

- [功能](#功能)
- [仓库结构](#仓库结构)
- [环境要求](#环境要求)
- [安装](#安装)
- [快速开始](#快速开始)
- [Web 实时机制](#web-实时机制)
- [API 摘要](#api-摘要)
- [测试与验证](#测试与验证)
- [物理建模边界](#物理建模边界)
- [文档](#文档)
- [贡献](#贡献)
- [许可证](#许可证)
- [引用](#引用)

## 功能

| 专题 | 内容 |
|---|---|
| **热力学 / 理想气体** | `PV=nRT`、**3D 分子热运动动画**（体积随 T/P 缩放、粒子按速率着色）、**3D P-V-T 相图**（给出 `(P,V,T)` 坐标值）+ **P-V / P-T / V-T 平面图**、等温/等压/等容准静态过程模式与理论过程线 |
| **布朗运动** | 有惯性 Langevin、液体分子间硬球弹性碰撞、轨迹与 MSD / 扩散常数；花粉碰撞点高亮、方向箭头/速度矢量/轨迹渐隐开关 |
| **麦克斯韦速率分布** | 理论 PDF + 蒙特卡洛直方图 + 粒子动画；**速率 f(v) 与水平速度分量 v_x 高斯分布双图对照**（线性轴、y 上限固定） |
| **伽尔顿板** | 蒙特卡洛下落路径（漏斗 → 钉板 → 狭槽 hexagonal 堆积）与二项分布对照 |

三种使用方式：

1. **Windows Web 一键演示版（推荐）** — 下载 `HeatLab-Web-win64.zip`，解压后双击 `HeatLab-Web.exe`
2. **浏览器实时版** — `heatlab-web` → <http://127.0.0.1:8765>，源码开发与本地调试入口
3. **旧版 PySide6 桌面版** — `heatlab` / `heatlab-ideal-gas` 等，仅保留用于源码对照，不再作为主要演示入口

桌面版与 Web 版共享同一套模型层与 VS Code Dark+ 工作台视觉：顶栏（品牌 + 种子命令托盘 + 运行簇）、专题 Tab、三栏「参数 | 场景 | 图表」、底部状态栏。桌面 Matplotlib 图例/图注在深色主题下强制浅色文字并优先常规字重中文字体，避免黑字或细体字不可读。

Web 端新增交互特性：

- **默认不自动播放**：进入任一专题都保持静态初始画面，点「继续」或「投放粒子」等按钮手动触发动画
- **专题信息弹窗**：首次进入每个专题时弹出说明面板，包含按任务文档编写的**实验说明 + 使用教程**，公式用 **KaTeX** 渲染
- **全屏查看**：3D 相图与每个平面图右上角有放大按钮，弹窗内保留图注、坐标轴与 Plotly 工具栏

### Windows Web 一键演示版（推荐）

这是给课堂演示和他人体验准备的 **Web + Flask 后端打包版**，不是重新制作一套简陋的 PySide6 窗口：

1. 从 GitHub Actions 的 [build-windows workflow](.github/workflows/build-windows.yml) 下载 `HeatLab-Web-win64` artifact；发布 `v*` tag 后也会自动附加 `HeatLab-Web-win64.zip`。
2. 解压 `HeatLab-Web-win64.zip`。
3. 双击 `HeatLab-Web.exe`，程序会启动本地服务并打开默认浏览器。
4. 浏览器访问地址默认是 `http://127.0.0.1:8765`；如果端口被占用，启动器会自动尝试附近端口。

该 exe 已包含 Python、Flask 后端、模型和 Web 模板/静态资源，不需要额外安装 Python。Vue、Chart.js、Plotly、KaTeX 仍从 CDN 加载，因此首次演示需要联网。关闭浏览器不会自动结束后端进程；演示结束后请退出 `HeatLab-Web.exe`，或在任务管理器中结束该进程。

### 旧版 PySide6 桌面版（不推荐）

源码仍保留 `heatlab`、`heatlab-ideal-gas` 等入口，便于数值模型和桌面代码对照，但其界面与功能落后于 Web 版，Windows 发布工作流已不再打包它。完整交互（3D 相图、平面图、放大弹窗、专题说明）请使用上面的 Web 入口。

## 仓库结构

```text
.
├── src/heatlab/           # 主包
│   ├── models/            # 数值模型（无 GUI）
│   ├── ui/                # 桌面界面
│   ├── web/               # Flask + 模板/静态资源/字体
│   ├── app.py             # 桌面 CLI
│   ├── randomness.py      # 可复现随机流
│   └── validation.py      # 离线验证出图
├── tests/                 # pytest
├── docs/                  # 架构与工作文档、任务原文
├── assets/                # 参考示意图
├── examples/validation/   # 入库的验证样例图
├── .github/               # CI · Issue/PR 模板
├── pyproject.toml         # 包装与入口脚本
├── requirements.txt       # 运行依赖
├── requirements-dev.txt   # 开发依赖
├── LICENSE                # MIT
├── CHANGELOG.md
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── SECURITY.md
├── CITATION.cff
└── THIRD_PARTY_NOTICES.md
```

更细的分层与数据流见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

## 环境要求

- Python **3.11 – 3.13**（推荐 3.12）
- 依赖：NumPy、SciPy、Matplotlib、PySide6、Flask（见 `pyproject.toml`）
- 推荐 [uv](https://github.com/astral-sh/uv) 管理虚拟环境

## 安装

```bash
git clone https://github.com/WALKERKILLER/heatlab.git
cd heatlab

# 推荐
uv venv --python 3.12
uv pip install -e ".[dev]"

# 或使用 pip
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

仅运行依赖：

```bash
pip install -r requirements.txt
pip install -e .
```

## 快速开始

> **给别人演示时优先使用 Windows Web 一键演示版**；开发者本地则使用 Python 浏览器实时版。PySide6 桌面版仅保留为旧源码入口。

### Windows Web 一键演示版（推荐）

```text
下载 HeatLab-Web-win64.zip → 解压 → 双击 HeatLab-Web.exe
```

程序会自动启动内置 Flask 后端并打开默认浏览器，不需要安装 Python。演示电脑需要联网加载 CDN 前端依赖；退出时请关闭 `HeatLab-Web.exe`。

### 浏览器实时版（开发/本地调试）

```bash
./.venv/bin/heatlab-web
# 默认 http://127.0.0.1:8765

./.venv/bin/heatlab-web --host 127.0.0.1 --port 8765
```

打开浏览器后：

- 顶部 **命令托盘**：改种子 →「应用并重置」
- **运行簇**：会话状态（实时中 / 已暂停 / 故障）+ 暂停/继续
- 下方四个专题 Tab；三栏：参数 | 场景 Canvas | 图表
- 首次进入每个专题会弹出**实验说明 + 使用教程**（公式用 KaTeX 渲染），点「开始实验」进入

> 开发服务器仅供本机实验；公网部署请换 WSGI 并阅读 [SECURITY.md](SECURITY.md)。

### 旧版 PySide6 桌面版（不推荐）

```bash
./.venv/bin/heatlab                  # 四专题合并窗口
./.venv/bin/heatlab --topic ideal-gas
./.venv/bin/heatlab-brownian --seed 42
```

| 命令 | 说明 |
|---|---|
| `heatlab` | 合并窗口 / 可用 `--topic` |
| `heatlab-ideal-gas` | 理想气体 |
| `heatlab-brownian` | 布朗运动 |
| `heatlab-maxwell` | 麦克斯韦 |
| `heatlab-galton` | 伽尔顿板 |

> 桌面版只保留基础交互（滑条 + 图表），缺少 Web 端的 3D 相图、平面图、放大弹窗、专题说明等高级功能。

## Web 实时机制

1. `POST /api/session` 创建服务端会话（每标签页一份状态）
2. 前端 `requestAnimationFrame` 循环（约 30 FPS；伽尔顿稍慢）
3. 每帧 `POST /api/live/<topic>/step` 推进模型并返回数据
4. Canvas 重绘场景；Chart.js 刷新曲线/直方图
5. 暂停停止步进；重置按新种子重建会话

Windows 一键演示版使用 `heatlab.web.launcher` 启动同一个 Flask 应用：先绑定本机回环地址，再打开默认浏览器；如果默认端口被占用，会在附近端口中选择空闲端口。

热力学相图为 **P-V-T 相图**（对齐任务文档「PV-T 相图：给出 (P,V,T) 坐标值」）：

- **设定路径 (PV=nRT)**：宏观状态点的 3D 轨迹  
- **当前状态**：当前 (P, V, T) 状态点，图上与参数区均标注三元组坐标值  
- **理论过程线**：等温/等压/等容模式下叠加对应 3D 理论线（虚线）

麦克斯韦图表区为双图：**速率分布 f(v)** 与 **水平速度分量 v_x 高斯分布**，均含理论曲线与蒙特卡洛样本直方图。

界面为 VS Code 风格工业扁平工作台 + lab-console 顶栏（brand plate、命令托盘、运行簇）。可用性：键盘 Tab、label、`aria-live` 状态栏、跳过链接、`prefers-reduced-motion`、内置 `HeatLab CJK` 字体。

## API 摘要

| 路径 | 说明 |
|---|---|
| `GET /api/health` | 健康检查（`mode=live`） |
| `POST /api/session` | 创建实时会话 |
| `POST /api/session/reset` | 按种子重置 |
| `POST /api/live/ideal-gas/set` · `/step` | 理想气体；`set` 支持 `process_mode`（`free`/`isothermal`/`isobaric`/`isochoric`） |
| `POST /api/live/brownian/set` · `/step` · `/reset` | 布朗运动 |
| `POST /api/live/maxwell/set` · `/step` · `/reset` | 麦克斯韦（载荷含 `component_*` 分量分布） |
| `POST /api/live/galton/start` · `/step` | 伽尔顿板 |
| `GET /api/ideal-gas` 等 | 一次性快照（兼容） |

## 测试与验证

```bash
./.venv/bin/python -m compileall -q src tests
./.venv/bin/python -m pytest
./.venv/bin/ruff check src tests

# 重新生成验证图（输出到本地 validation_output/，不入库）
./.venv/bin/python -m heatlab.validation --output-dir validation_output
```

入库样例见 [examples/validation/](examples/validation/)。

**随机复现**：`numpy.random.Generator`，由全局种子派生四个命名流。默认种子 `42`。相同版本 + 种子 + 参数 → 可复现。

## 物理建模边界

- **理想气体**：视觉粒子忽略相互作用；T 控速度尺度，P/T 经状态方程决定 V；显示速度系数 1.5（仅影响观感，不改变物理状态）。透明粒子箱是**相对显示体积**：长度按 T/P 缩放并限制在 `0.45–1.60`，高度/深度固定为显示单位，不能理解为真实容器的三维绝对尺寸；物理体积以 `V=nRT/P` 读数为准。
- **布朗运动**：原文缺黏度等 SI 参数 → 无量纲 Langevin；质量滑条下限 `0.05 m₀`。液体分子层采用 **Ornstein-Uhlenbeck 热运动 + 硬球弹性碰撞**（借鉴开源硬球模型，如 `Yangliu20/physics-simulation` 的粒子弹性碰撞与轨迹/碰撞点可视化思路）  
- **麦克斯韦**：默认氮气分子质量，温度 0–100 °C；显示速度系数 1.5，粒子活跃运动  
- **伽尔顿板**：固定 12 层、`p=0.5`；UI 粒子数 1–100  

## 文档

| 链接 | 内容 |
|---|---|
| [docs/README.md](docs/README.md) | 文档索引 |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 架构 |
| [docs/HeatLab_代码工作文档.md](docs/HeatLab_代码工作文档.md) | 详细设计与验收 |
| [CHANGELOG.md](CHANGELOG.md) | 版本记录 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 如何贡献 |
| [SECURITY.md](SECURITY.md) | 安全披露 |

## 贡献

欢迎 Issue 与 PR。请先读 [CONTRIBUTING.md](CONTRIBUTING.md) 与 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。

## 许可证

本项目以 [MIT License](LICENSE) 发布。第三方依赖见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

内置字体 `DroidSansFallback.ttf` 用于 Web 中文显示，请遵守其上游许可条款。

## 引用

若本软件对你的教学或研究有帮助，可使用 [CITATION.cff](CITATION.cff)：

```bibtex
@software{HeatLab2026,
  title  = {HeatLab: Thermal Physics Scientific Computing Lab},
  author = {{HeatLab project team}},
  year   = {2026},
  version = {0.1.0},
  license = {MIT}
}
```

---

**仓库地址**：<https://github.com/WALKERKILLER/heatlab>
