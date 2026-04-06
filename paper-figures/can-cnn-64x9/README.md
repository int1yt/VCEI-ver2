# CAN CNN 64x9（论文材料）

本目录提供可直接用于论文写作与制图的材料，基于 `REAL-IDS/integration/can_cnn_64x9` 的实际实现整理。

## 文件说明

- `paper_text_can_cnn_64x9.md`：可直接复制到论文中的方法描述（预处理、网络、训练、推理与复杂度）。
- `fig01_pipeline.tex`：端到端流程图（数据到部署）。
- `fig02_window_and_features.tex`：64x9 输入构造示意图。
- `fig03_network_architecture.tex`：CNN 网络结构图。
- `fig04_training_and_selection.tex`：训练与最优模型选择流程图。
- `fig05_online_inference_integration.tex`：在线推理与系统集成图。
- `fig06_complexity_profile.tex`：复杂度与实时性图。
- `fig07_real_training_evidence_can_only.tex`：仅基于 CAN-CNN(64x9) 的真实训练证据图组。
- `real-training-images/`：CAN 专用真实/衍生图片（训练曲线、混淆矩阵、类别指标、Grad-CAM 解释图）。
- `generate_can_eval_images.py`：从 `eval_metrics.json` 生成混淆矩阵与类别指标图。

## 编译

在当前目录执行（每个图独立编译）：

```bash
latexmk -xelatex fig01_pipeline.tex
latexmk -xelatex fig02_window_and_features.tex
latexmk -xelatex fig03_network_architecture.tex
latexmk -xelatex fig04_training_and_selection.tex
latexmk -xelatex fig05_online_inference_integration.tex
latexmk -xelatex fig06_complexity_profile.tex
latexmk -xelatex fig07_real_training_evidence_can_only.tex
```

或使用 `xelatex` 分别编译。
