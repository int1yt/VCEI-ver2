# 基于 CNN 和 Transformer 的网络入侵检测系统

## 项目简介

本项目实现了一种结合**卷积神经网络（CNN）**与**Transformer**的网络入侵检测模型，旨在提升对网络流量中异常行为的检测能力。通过对网络流量数据进行序列化处理，模型能够捕捉时间维度上的依赖关系，并利用 CNN 提取局部特征，从而实现对正常与异常流量的高效分类。

该模型在 CIC-IDS 等网络入侵检测数据集上进行了验证，取得了较高的准确率和召回率，适用于实时网络监控与安全防护场景。

---

## 项目背景

随着网络攻击手段的不断演进，传统基于规则的入侵检测系统（IDS）难以应对新型、隐蔽的攻击方式。近年来，深度学习技术在入侵检测领域展现出巨大潜力，尤其是 Transformer 和 CNN 在序列建模与特征提取方面的优势，为构建高效、自适应的 IDS 提供了新的思路。

本项目的目标是：

- 构建一个端到端的深度学习模型，结合 CNN 与 Transformer；
- 实现对网络流量数据的自动特征提取与分类；
- 评估模型在真实网络流量数据集上的表现。

---

## 环境要求

### 系统环境

- Python 3.7+
- 操作系统：Windows / Linux / macOS

### 依赖库

```bash
pip install torch pandas numpy scikit-learn matplotlib
```

> 推荐使用 Anaconda 或虚拟环境进行隔离安装。

---

## 数据集说明

本项目使用两个预处理后的 CSV 文件：

- `data_8000_normal.csv`：正常流量样本
- `data_8000_abnormal.csv`：异常流量样本

每个样本包含 80 个特征字段，经过预处理后，每 10 个连续样本组成一个输入序列，用于模型训练。

---

## 项目结构

```
├── data_preprocess.py          # 数据预处理与序列化
├── model.py                    # Transformer + CNN 模型定义
├── train.py                    # 模型训练脚本
├── evaluate.py                 # 模型评估与可视化
├── README.md                   # 项目说明文档
├── requirements.txt            # 依赖库列表
├── data_8000_normal.csv        # 正常流量数据
├── data_8000_abnormal.csv      # 异常流量数据
└── transformer_ids_model.pth   # 训练好的模型权重（生成）
```

---

## 数据预处理流程

1. **数据合并**：将正常与异常流量数据合并。
2. **特征筛选**：删除无关字段（如 IP、时间戳、Flow ID 等）。
3. **标签转换**：将 `BENIGN` 标签转换为 0，异常标签转换为 1。
4. **缺失值处理**：替换无穷值并删除含有缺失值的样本。
5. **标准化**：使用 `StandardScaler` 对特征进行标准化。
6. **序列化**：每 10 个样本组成一个序列，输入模型。
7. **划分数据集**：按 80%/20% 的比例划分为训练集和测试集。
8. **保存为 CSV**：生成 `train_X.csv`, `train_Y.csv`, `test_X.csv`, `test_Y.csv`。

运行方式：

```bash
python data_preprocess.py
```

---

## 模型结构

模型由以下部分组成：

- **Transformer 编码器**：捕捉序列中的全局依赖关系。
- **多尺度 CNN**：使用 3、4、5 三种卷积核提取局部特征。
- **全连接层**：将提取到的特征映射到两类（正常/异常）。

模型结构图（示意）：

```
输入序列 (10, 80)
    ↓
Transformer Encoder
    ↓
CNN (3,4,5) + MaxPooling
    ↓
Concatenate + Dropout
    ↓
Fully Connected Layer
    ↓
Softmax (2 类)
```

---

## 模型训练

- **损失函数**：交叉熵损失（CrossEntropyLoss）
- **优化器**：Adam（学习率 0.001）
- **批量大小**：512
- **训练轮数**：10

运行训练脚本：

```bash
python train.py
```

训练完成后，模型权重将保存为 `transformer_ids_model.pth`。

---

## 模型评估

评估脚本输出以下内容：

- 每一条测试样本的分类结果（正确/错误）
- 总体准确率、精确率、召回率、F1 分数
- 混淆矩阵
- ROC 曲线与 AUC
- Precision-Recall 曲线
- 错误分类样本保存为 `classification_errors.csv`

运行评估脚本：

```bash
python evaluate.py
```

---

## 可视化结果

- **ROC 曲线**：展示模型在不同阈值下的分类能力。
- **PR 曲线**：展示精确率与召回率的权衡。

---

## 错误样本分析

评估脚本将自动生成 `classification_errors.csv`，包含所有被错误分类的样本信息，便于后续分析与模型优化。

---
