# CAN-CNN(64x9) 图组（全新重绘版）

本目录已删除旧版 `fig01~fig07`，并重建为统一风格的 4 张主图：具体详细、简约美观、可直接用于论文主文。

## 新图清单（重绘）

- `fig01_method_overview_redraw.tex`  
  方法总览：数据到部署的完整链路与关键约束（`dt_max_ms` 一致性）。
- `fig02_feature_and_network_redraw.tex`  
  输入与网络：64x9 特征定义 + 轻量 CNN 结构。
- `fig03_training_evidence_redraw.tex`  
  真实证据：训练曲线、混淆矩阵、类别指标、Grad-CAM（全部来自 `can_cnn_64x9`）。
- `fig04_deployment_efficiency_redraw.tex`  
  在线部署与效率：推理路径、工程约束、效率要点。

## 其它文件

- `paper_text_can_cnn_64x9.md`：论文文字描述（详细版）。
- `real-training-images/`：真实/衍生图片资源。
- `generate_can_eval_images.py`：由 `eval_metrics.json` 生成评估图。

## 编译命令

```bash
latexmk -xelatex fig01_method_overview_redraw.tex
latexmk -xelatex fig02_feature_and_network_redraw.tex
latexmk -xelatex fig03_training_evidence_redraw.tex
latexmk -xelatex fig04_deployment_efficiency_redraw.tex
```

或分别使用 `xelatex` 编译。
