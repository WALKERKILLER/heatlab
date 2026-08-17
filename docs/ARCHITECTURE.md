# HeatLab 架构说明

## 仓库布局

```text
repo1/                         # GitHub 仓库根（本目录）
├── src/heatlab/               # 可安装 Python 包
│   ├── models/                # 纯数值模型（ideal_gas / brownian / maxwell / galton）
│   ├── ui/                    # PySide6 桌面界面
│   ├── web/                   # Flask API + templates + static + 一键启动器
│   ├── randomness.py          # 全局种子 → 命名随机流
│   ├── constants.py           # 默认种子等常量
│   ├── validation.py          # 离线数值验证与出图
│   └── app.py                 # 桌面 CLI 入口
├── tests/                     # pytest
├── docs/                      # 设计与任务文档
├── assets/                    # 参考 UI / 示意截图
├── examples/validation/       # 已生成的验证样例（入库）
├── .github/                   # CI、Issue / PR 模板
├── pyproject.toml             # 包元数据与入口脚本
├── requirements.txt           # 运行依赖（pip 友好镜像）
├── requirements-dev.txt       # 开发依赖
├── LICENSE                    # MIT
└── README.md                  # 产品说明书
```

## 分层

```text
┌─────────────────────────────────────────────┐
│  UI 层                                       │
│  desktop: heatlab.ui.* (PySide6)             │
│  web:     heatlab.web (Flask + Vue CDN)      │
└──────────────────┬──────────────────────────┘
                   │ 调用
┌──────────────────▼──────────────────────────┐
│  会话 / 服务（仅 Web）                        │
│  sessions.STORE + services.step/set          │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  模型层 heatlab.models.*                     │
│  无 GUI；可单测；由 seed 派生 Generator       │
└─────────────────────────────────────────────┘
```

## Windows Web 一键演示版

发布工作流不再打包旧版 PySide6 窗口，而是以 `src/heatlab/web/launcher.py` 为
PyInstaller 入口：

1. 启动器创建与开发版相同的 Flask `create_app()`；
2. 使用 Werkzeug `make_server` 绑定 `127.0.0.1`，默认端口为 `8765`，被占用时自动向后寻找空闲端口；
3. 服务绑定成功后调用系统默认浏览器打开本地地址；
4. GitHub Actions 以 `--onefile --windowed` 构建 `HeatLab-Web.exe`，并显式收集 `web/templates` 与 `web/static`；
5. 构建任务通过 `/api/health`、首页和 `/static/app.css` 冒烟检查后，产出 `HeatLab-Web-win64.zip`。

该 exe 是“浏览器界面 + 本地 Python 后端”的封装，不是第二套 UI。浏览器端的 Vue、Chart.js、Plotly 与 KaTeX 仍从 CDN 加载，离线发布若有需求应另行本地化这些静态依赖。

## Web 实时回路

1. `POST /api/session` 创建内存会话  
2. 浏览器 `requestAnimationFrame` 循环  
3. `POST /api/live/<topic>/step` 推进一帧并返回粒子/轨迹  
4. Canvas / Chart.js / Plotly 重绘  
5. 暂停只停前端步进；「应用并重置」重建会话  

### Web 渲染与性能策略

- **3D P-V-T 相图**用 Plotly（可旋转 + 滚轮缩放 + 悬停坐标）；服务端对相图几何（PV=nRT 曲面 / 等值线族 / 过程线）做**签名缓存**，粒子 step 时宏观状态不变 → 直接复用，避免每帧重算大数组。
- 3D 相图 + 平面图渲染**节流到每 4 帧**，粒子场景保持每帧更新。
- 麦克斯韦直方图采样 3000 点；温度步进每 3 帧刷新一次。
- 图表（3D 相图与每个平面图）右上角有**放大弹窗**，弹窗内保留图注/坐标轴/Plotly 工具栏。
- 默认**不自动播放**：进入专题为静态初始画面，点「继续」/「投放粒子」手动触发；首次进入专题弹出 **KaTeX** 实验说明弹窗。

## 桌面 UI 主题

- 工作台为深色工业扁平风格（`heatlab.ui.style.APP_STYLE`）。
- Matplotlib 画布在 `heatlab.ui.common` 中统一设置浅色图注：`text.color` / `legend.labelcolor` / 轴标签与标题，避免默认黑字落在深色底上不可读。
- 图例创建后经 `style_legend()` 再刷一遍文字色（纯白 11pt）；3D 轴用 `style_3d_axes()`。
- 中文字体优先常规字重的 Droid Sans Fallback，拉丁字符由 DejaVu Sans 逐字形回退补齐。

## 设计约束

- **可复现**：同一版本 + 同一种子 + 同一参数 → 同一随机结果  
- **模型与界面分离**：改 UI 不应改写物理公式  
- **本地优先**：默认 `127.0.0.1`；开发服务器不适合裸奔公网  
- **显示与物理分离**：理想气体粒子箱是按 `T/P` 缩放并限幅的相对显示体积；物理体积仍由 `PV=nRT` 计算，不能从画面边长反推真实三维尺寸
- **Web 优先演示**：Windows 发布产物优先提供 Web + 后端 exe，PySide6 入口保留为旧源码对照

详见工作文档 `HeatLab_代码工作文档.md`。
