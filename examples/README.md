# Examples

## validation/

由 `python -m heatlab.validation` 生成的**样例**输出（入库便于 README 展示与对照）：

| 文件 | 内容 |
|---|---|
| `validation_ideal_gas.png` | 理想气体验证图 |
| `validation_brownian.png` | 布朗运动 / MSD |
| `validation_maxwell.png` | 麦克斯韦分布 |
| `validation_galton.png` | 伽尔顿板 |
| `validation_montage.png` | 拼图总览 |
| `font_smoke_cjk.png` | 中文字体冒烟 |
| `validation_results.json` | 数值摘要 |

本地重新生成请输出到仓库根目录的 `validation_output/`（已在 `.gitignore` 中忽略）：

```bash
./.venv/bin/python -m heatlab.validation --output-dir validation_output
```
