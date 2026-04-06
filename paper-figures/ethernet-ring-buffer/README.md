# 以太网环形存储（论文材料）

本目录提供可直接用于论文写作与制图的材料，基于 `REAL-IDS` 中 `EthRingBuffer` 的实际实现逻辑整理。

## 文件说明

- `paper_text_ethernet_ring_buffer.md`：可直接复制到论文中的方法描述（含符号、流程、复杂度与工程讨论）。
- `fig01_architecture.tex`：模块位置图（CAN ClockIDS + 以太网环形存储 + 中央处理器）。
- `fig02_ring_push_overwrite.tex`：写入与覆盖机制图。
- `fig03_time_window_query.tex`：时间窗检索图。
- `fig04_alert_association_flow.tex`：告警关联流程图。
- `fig05_complexity_and_latency.tex`：复杂度与时延路径图。

## 编译

在当前目录执行（每个图独立编译）：

```bash
latexmk -xelatex fig01_architecture.tex
latexmk -xelatex fig02_ring_push_overwrite.tex
latexmk -xelatex fig03_time_window_query.tex
latexmk -xelatex fig04_alert_association_flow.tex
latexmk -xelatex fig05_complexity_and_latency.tex
```

或使用 `xelatex` 分别编译。
