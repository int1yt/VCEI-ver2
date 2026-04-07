# 数据集分析目录

本目录用于集中分析论文使用的数据集分布，并自动生成可直接写入论文“数据集”小节的文本。

## 输入数据

- `CarHackData/DoS_dataset.csv`
- `CarHackData/Fuzzy_dataset.csv`
- `CarHackData/gear_dataset.csv`
- `CarHackData/RPM_dataset.csv`
- `IntrusionDetectNet-CNN-Transformer-main/PycharmProjects/data_8000_normal.csv`
- `IntrusionDetectNet-CNN-Transformer-main/PycharmProjects/data_8000_abnormal.csv`

## 使用方式

```bash
python paper-figures/dataset-analysis/analyze_datasets.py
```

## 输出文件

- `dataset_stats.json`：结构化统计结果（可复用到作图或表格）。
- `dataset_section.md`：可直接粘贴到论文“数据集”板块的文字与表格。
