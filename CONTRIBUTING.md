# 贡献指南

感谢你愿意改进 HeatLab！本指南说明如何本地开发、提交变更与开 PR。

## 行为准则

参与本项目即表示你同意遵守 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。

## 开发环境

需要 **Python 3.11+**（推荐 3.12）与 [uv](https://github.com/astral-sh/uv)（或 pip）。

```bash
git clone https://github.com/WALKERKILLER/heatlab.git
cd heatlab

uv venv --python 3.12
uv pip install -e ".[dev]"
# 或: python -m venv .venv && .venv/bin/pip install -e ".[dev]"
```

## 常用命令

```bash
# 测试
./.venv/bin/python -m pytest

# 语法编译检查
./.venv/bin/python -m compileall -q src tests

# 代码风格（可选）
./.venv/bin/ruff check src tests

# 桌面版
./.venv/bin/heatlab

# Web 实时版
./.venv/bin/heatlab-web --host 127.0.0.1 --port 8765

# 数值验证图（写入本地 validation_output/，该目录不入库）
./.venv/bin/python -m heatlab.validation --output-dir validation_output
```

## 分支与提交

1. 从 `main` 开分支：`feature/...`、`fix/...` 或 `docs/...`
2. 保持改动聚焦；一次 PR 只做一类事
3. 提交信息用现在时、说清**为什么**，例如：`fix: freeze run-meter bars when paused`
4. 涉及物理模型时，请在 PR 说明可复现种子与预期数值行为

## Pull Request 检查清单

- [ ] `pytest` 通过
- [ ] 新增公共 API / CLI 已更新 README 或 `docs/`
- [ ] UI 文案为简体中文（与现有界面一致）
- [ ] 未提交 `.venv/`、密钥、本机绝对路径或 `validation_output/` 运行产物
- [ ] 大二进制文件有必要说明（字体 / 示意图除外）

## 代码结构提示

| 路径 | 职责 |
|---|---|
| `src/heatlab/models/` | 纯数值模型（尽量无 GUI 依赖） |
| `src/heatlab/ui/` | PySide6 桌面界面 |
| `src/heatlab/web/` | Flask API + 模板与静态资源 |
| `tests/` | pytest 用例 |
| `docs/` | 架构、工作文档、任务原文 |

模型变更优先补测试；Web 前端改动请自测四专题切换与暂停/重置。

## 安全问题

请勿在公开 Issue 中披露未修复漏洞。见 [SECURITY.md](SECURITY.md)。

## 许可

贡献内容默认按本仓库 [MIT License](LICENSE) 授权。
