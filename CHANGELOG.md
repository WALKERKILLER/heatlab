# Changelog

本文件遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Fixed
- 桌面 Matplotlib 图注/图例/坐标轴在深色背景下使用浅色文字，避免黑字看不清

### Planned
- Web 会话可换 Redis 以支持多进程部署
- 可选 WebSocket 推流，降低高频 step 轮询
- 桌面与 Web 统一可调动画步长

## [0.1.0] - 2026-08-08

### Added
- 四个热学专题数值模型：理想气体、布朗运动、麦克斯韦分布、伽尔顿板
- 桌面 GUI：合并窗口（`heatlab`）与四专题独立入口
- 浏览器实时实验台：Flask 会话引擎 + Vue 3 CDN + Canvas / Chart.js
- 全局种子派生的可复现随机流
- Web 工业扁平工作台 UI（Dark+ 风格）与 lab-console 顶栏（brand plate + 命令托盘 + 运行簇）
- 内置中文字体 `HeatLab CJK`（DroidSansFallback）
- 单元测试、数值验证脚本与示例输出图
- MIT 许可证与第三方声明

[Unreleased]: https://github.com/WALKERKILLER/heatlab/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/WALKERKILLER/heatlab/releases/tag/v0.1.0
