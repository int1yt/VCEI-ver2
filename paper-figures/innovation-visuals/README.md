# 创新点与效率可视化（论文增强版）

本目录用于把“训练真实产物 + 新增直观图示”组合成可直接用于论文的图组。

## 文件

- `fig01_real_training_evidence.tex`  
  汇总真实训练产物（曲线、混淆矩阵、对齐器损失、链模型训练图）。
- `fig02_innovation_points.tex`  
  创新点总览图（ClockIDS + RingBuffer + CAN-CNN 64x9 + 融合）。
- `fig03_efficiency_story.tex`  
  效率叙事图（低时延、固定内存、按需检索、在线部署友好）。
- `paper_figure_templates.tex`  
  可直接复制到论文正文的 `figure*` 模板（含建议 caption 与 label）。

## 编译

在当前目录执行：

```bash
latexmk -xelatex fig01_real_training_evidence.tex
latexmk -xelatex fig02_innovation_points.tex
latexmk -xelatex fig03_efficiency_story.tex
```

## 说明

- 这些图默认通过相对路径引用项目内真实图片（`REAL-IDS/integration/.../artifacts`）。
- 若路径变更，请同步调整 `\includegraphics{...}`。
