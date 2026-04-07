# CAN+以太网二维时序 ML（论文图文包）

本目录面向论文写作，聚焦“CAN 与以太网联合二维时序学习”。

## 内容

- `paper_text_can_eth_2d_temporal_ml.md`：详细方法叙述（可直接复制到论文）。
- `fig01_joint_method_overview.tex`：联合方法总览图（对齐 + 链建模）。
- `fig02_2d_temporal_fusion.tex`：二维时序构造细节图（T=10 融合序列）。
- `fig03_real_training_evidence.tex`：真实训练证据图（对齐器 + 链模型）。
- `fig04_online_enrich_deployment.tex`：在线 `/v1/enrich` 接入与输出图。
- `real-training-images/`：真实训练图（来自 `cross_domain_chain/artifacts`）。

## 最关键 4 张（建议主文）

- `fig01_joint_method_overview.tex`
- `fig02_2d_temporal_fusion.tex`
- `fig03_real_training_evidence.tex`
- `fig04_online_enrich_deployment.tex`

## 编译

```bash
latexmk -xelatex fig01_joint_method_overview.tex
latexmk -xelatex fig02_2d_temporal_fusion.tex
latexmk -xelatex fig03_real_training_evidence.tex
latexmk -xelatex fig04_online_enrich_deployment.tex
```
