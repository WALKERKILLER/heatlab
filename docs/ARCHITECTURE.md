# HeatLab 架构说明

## 仓库布局

```text
repo1/                         # GitHub 仓库根（本目录）
├── src/heatlab/               # 可安装 Python 包
│   ├── models/                # 纯数值模型（ideal_gas / brownian / maxwell / galton）
│   ├── ui/                    # PySide6 桌面界面
│   ├── web/                   # Flask API + templates + static
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

## Web 实时回路

1. `POST /api/session` 创建内存会话  
2. 浏览器 `requestAnimationFrame` 循环  
3. `POST /api/live/<topic>/step` 推进一帧并返回粒子/轨迹  
4. Canvas / Chart.js 重绘  
5. 暂停只停前端步进；「应用并重置」重建会话  


## 桌面 UI 主题

- 工作台为深色工业扁平风格（`heatlab.ui.style.APP_STYLE`）。
- Matplotlib 画布在 `heatlab.ui.common` 中统一设置浅色图注：`text.color` / `legend.labelcolor` / 轴标签与标题，避免默认黑字落在深色底上不可读。
- 图例创建后经 `style_legend()` 再刷一遍文字色（纯白 11pt）；3D 轴用 `style_3d_axes()`。
- 中文字体优先常规字重的 Droid Sans Fallback，拉丁字符由 DejaVu Sans 逐字形回退补齐。

## 设计约束

- **可复现**：同一版本 + 同一种子 + 同一参数 → 同一随机结果  
- **模型与界面分离**：改 UI 不应改写物理公式  
- **本地优先**：默认 `127.0.0.1`；开发服务器不适合裸奔公网  

详见工作文档 `HeatLab_代码工作文档.md`。
