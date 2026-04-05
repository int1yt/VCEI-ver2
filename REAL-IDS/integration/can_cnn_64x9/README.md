# CAN 64×9 滑动窗口 CNN — 使用说明与结果解读

本文档说明 **数据预处理 → 训练 → 可视化 → 与 REAL-IDS 联调** 的完整流程，并解释当前产出图形的含义，以及 **本次改动对整体系统的影响**。

---

## 一、这次修改会影响整个系统的使用吗？

**总体结论：默认兼容；在启用 64×9 权重时 CAN 行为会升级，其余路径保持原逻辑。**

| 组件 | 影响说明 |
|------|-----------|
| **ML Bridge（`server.py`）** | CAN 推理优先级变为：**① 64×9 CNN**（若 `artifacts/best_model.pth` 存在且加载成功）→ **② CarHack 29×29 CNN** → **③ SupCon**。若你**没有**放置 64×9 权重，行为与改之前一致（仍走 CarHack / SupCon）。 |
| **Daemon（`main.cpp`）** | `can_history` 容量由 **29 增至 64**，便于凑满模型需要的 64 帧窗口。API 字段未改，仍用 `timestamp`（毫秒）。仅多保留若干条历史，内存与 JSON 体积略增，一般可忽略。 |
| **以太网 IDS** | **无变化**，仍用 IntrusionDetectNet / 启发式逻辑。 |
| **融合与攻击链** | 当 64×9 模型生效时，`can_ml.source` 为 `can_cnn64`，`can_class_names` 为 4 类（Normal / DoS / Fuzzy / Spoofing），与原先 5 类（含 gear、RPM）的 CarHack 标签不同；**仅当使用该后端时**前端展示的分类名会随之变化。 |

**如何“完全回到旧 CAN 行为”：** 不部署 `best_model.pth`，或设置 `CAN_CNN64_MODEL_PATH` 指向不存在路径，并重启 ml_bridge。

---

## 二、方法概述：四阶段在仓库里对应什么？

| 阶段 | 脚本 / 文件 | 作用 |
|------|----------------|------|
| 1. 预处理 | `preprocess.py` | 读取 CarHack 风格 CSV/TXT，滑动窗口 **64**、步长 **32**，每条报文 8 字节 → 列 0–7；**与前一条的时间间隔 Δt（毫秒）**经训练集 `dt_max_ms` 归一化后记为第 9 列 → 张量形状 **(64, 9)**。标签 4 类：Normal、DoS、Fuzzy、Spoofing（gear、RPM 数据并入 Spoofing）。 |
| 2. 模型 | `model.py` | `CAN_CNN`：3 个 Conv+BN+ReLU+MaxPool，AdaptiveAvgPool，Dropout(0.5)，全连接；与 **CrossEntropyLoss** 配套（输出 logits，无 Softmax）。 |
| 3. 训练与评估 | `train.py` | Adam、ReduceLROnPlateau、保存 `best_model.pth`、`eval_metrics.json`、`classification_report.txt`、`training_curves.png`；测试集 **分批推理** 避免内存溢出。 |
| 4. 可解释性 | `explain.py` | 加载最佳权重，从测试集每类抽样，对 **conv3** 做 **Grad-CAM**，保存 `analysis_result.png`。 |

依赖见同目录 `requirements.txt`（numpy、torch、tqdm、scikit-learn、matplotlib）。

---

## 三、详细使用步骤

### 3.1 环境准备

```powershell
cd c:\Users\Luyutong\Desktop\VCEI\REAL-IDS\integration\can_cnn_64x9
pip install -r requirements.txt
```

建议使用 **Python 3.10+**；有 **NVIDIA GPU** 时可显著缩短训练时间（PyTorch CUDA 版）。

### 3.2 第一阶段：预处理（全量数据默认即“全部文件”）

默认数据根目录为仓库上级的 `CarHackData`（含 `normal_run_data.txt`、`DoS_dataset.csv`、`Fuzzy_dataset.csv`、`gear_dataset.csv`、`RPM_dataset.csv`）。**目录下所有匹配的 .csv / .txt 都会参与**，即已是“全量 CarHack 提供的文件”。

```powershell
python preprocess.py --data-root "c:\Users\Luyutong\Desktop\VCEI\CarHackData" --out .\processed
```

产出：

- `processed/X_train.npy`、`y_train.npy`（及 val / test）
- `processed/preprocess_meta.json`（**`dt_max_ms`**、类别名、样本数量等）

**注意：** 全量预处理会生成 **数十万级** 窗口，`.npy` 体积大（数 GB 级可能），磁盘与内存需充足。

### 3.3 第二阶段：训练

```powershell
python train.py --data-dir .\processed --out .\artifacts --epochs 50 --batch-size 256
```

- 默认 **50 epoch、batch 128**；数据量大时可把 **batch-size** 提到 256/512（在显存/内存允许时）。
- 训练开始会把 `preprocess_meta.json` **复制到 `artifacts/`**，供推理与 ml_bridge 使用。

**仅重新计算测试指标（不训练）：**

```powershell
python train.py --data-dir .\processed --out .\artifacts --eval-only --batch-size 512
```

### 3.4 第三阶段：可视化（Grad-CAM）

```powershell
python explain.py --artifacts .\artifacts --data-dir .\processed --out .\analysis_result.png
```

---

## 四、当前得到的成果（数据含义）

以下数值来自某次在 **全量预处理数据** 上、**仅训练约 3 个 epoch** 的 checkpoint 经 `--eval-only` 得到的测试集结果（**完整 50 epoch 通常会更好**，需以你本地 `eval_metrics.json` 为准）。

- **测试集规模：** 约 **82 304** 个窗口（70/15/15 划分后的 test）。
- **整体准确率（Accuracy）：** 约 **80.6%**
- **宏平均精确率 / 召回 / F1：** 约 **0.81 / 0.83 / 0.82**

**按类大致含义：**

- **Normal：** 在该次评估中接近 **完美分离**（precision/recall ≈ 1），即正常窗口很少被误判为攻击。
- **DoS / Fuzzy：** 精确率约 **0.63–0.65**，说明与 **Spoofing 或其它攻击类** 仍有一定混淆（混淆矩阵中非对角元素较多属预期，可继续训练或调模型）。
- **Spoofing：** 精确率很高（约 **0.97**），召回约 **0.83**，部分样本被标成 DoS/Fuzzy。

**混淆矩阵怎么读：**  
`eval_metrics.json` 里 `confusion_matrix` 的行是 **真实标签**，列是 **预测标签**，顺序与 `class_names` 一致：`["Normal", "DoS", "Fuzzy", "Spoofing"]`。例如 DoS 行中 Fuzzy、Spoofing 列的数字越大，说明 DoS 越常被错分成这两类。

**`preprocess_meta.json` 中的 `dt_max_ms`：**  
训练集 Δt 列的全局缩放上限；**线上 ml_bridge 必须用同一值** 对实时 Δt 做归一化，否则第 9 列分布漂移，准确率会下降。

---

## 五、图形含义：`training_curves.png` 与 `analysis_result.png`

### 5.1 `artifacts/training_curves.png`

- **左图 Loss：** 训练损失与验证损失随 epoch 变化。验证损失持续低于训练或长期不降，可能有过拟合或需调学习率（已接 **ReduceLROnPlateau**）。
- **右图 Val accuracy：** 验证集分类准确率。若曲线已平稳，可提前停止或减小学习率以节省时间。

### 5.2 `analysis_result.png`（Grad-CAM）

- **左列：** 单个 **64×9** “灰度图”——行 = 时间顺序上的 64 条 CAN，列 0–7 为数据字节（归一化到 [0,1]），第 9 列为归一化后的 **Δt**。
- **右列：** 在同一张图上叠加 **热力图（jet）**：颜色越亮表示 **conv3 特征对当前预测类别越敏感的区域**（时间行 + 特征列）。用于对比 **DoS vs Fuzzy** 等时，可看模型更关注 **载荷字节** 还是 **时间间隔列**。

Grad-CAM 是解释性工具，**不保证与人类直觉完全一致**，但能辅助判断模型是否过度依赖某一列（例如只看 Δt）。

---

## 六、ML 在 REAL-IDS 中的使用方法（联调）

1. 完成训练，确认存在：  
   `integration/can_cnn_64x9/artifacts/best_model.pth`  
   与同目录 `preprocess_meta.json`（`train.py` 已复制）。
2. 启动 ml_bridge（与往常一样 `uvicorn`）。默认会解析上述路径；也可显式设置：
   ```text
   set CAN_CNN64_MODEL_PATH=c:\...\best_model.pth
   set CAN_CNN64_META_PATH=c:\...\preprocess_meta.json
   ```
3. 访问 `GET /health`：应看到 **`can_cnn64_loaded: true`**，`**can_backend**` 为 **`can_cnn64`**。
4. Daemon 已向 fusion 提供 **至少 64 条** `can_history`（当前 `k_can_hist_cap = 64`）。每条需含 **`data`（十六进制载荷）** 与 **`timestamp`（毫秒）**。
5. 调用 `POST /v1/enrich` 时，响应中 **`can_ml`** 含 `class_id`、`class_name`、`confidence`、`class_probs`；**`can_class_names`** 与 4 类顺序一致。

更通用的模型放置说明见：`integration/ml_bridge/MODELS.md`。

---

## 七、“跑完所有数据”可行吗？应如何操作？

**可行。** 当前设计里：

1. **预处理**  
   `--data-root` 指向的文件夹内 **所有** 符合命名的 `.csv`/`.txt` 都会读入并滑窗，**已是全量文件级覆盖**。无需再勾选“子集”，除非你自己删减文件。

2. **训练**  
   使用 **全部** `X_train.npy` 训练即“全量训练样本”。命令即上一节的 `train.py`（建议 `--epochs 50` 或更多，按验证曲线决定）。

3. **资源与时间**  
   - 样本量在 **数十万级** 时，CPU 上单次 epoch 可能 **数十分钟级**；**GPU** 强烈建议。  
   - 磁盘：预留 **数 GB** 给 `processed/*.npy`。  
   - 内存：训练脚本按 batch 加载，**测试评估已分批**；若训练仍 OOM，**减小 `--batch-size`**。

4. **推荐操作顺序（全量流水线）**

```powershell
cd c:\Users\Luyutong\Desktop\VCEI\REAL-IDS\integration\can_cnn_64x9

# 1) 全量预处理（耗时与磁盘取决于数据量）
python preprocess.py --data-root "c:\Users\Luyutong\Desktop\VCEI\CarHackData" --out .\processed

# 2) 全量训练（按机器调整 batch-size 与 epochs）
python train.py --data-dir .\processed --out .\artifacts --epochs 50 --batch-size 256

# 3) 可选：仅重算测试指标
python train.py --data-dir .\processed --out .\artifacts --eval-only --batch-size 512

# 4) 可解释性图
python explain.py --artifacts .\artifacts --data-dir .\processed

# 5) 重启 ml_bridge，检查 /health 与 /v1/enrich
```

完成 **2** 后，**`artifacts/eval_metrics.json`** 与 **`classification_report.txt`** 即为当前模型在 **全量划分测试集** 上的正式指标。

---

## 八、文件索引

| 路径 | 说明 |
|------|------|
| `preprocess.py` | CSV/TXT → `.npy` + `preprocess_meta.json` |
| `model.py` | `CAN_CNN` 定义 |
| `train.py` | 训练、曲线、指标、`best_model.pth` |
| `explain.py` | Grad-CAM → `analysis_result.png` |
| `processed/` | 预处理输出（可很大） |
| `artifacts/` | 权重、指标、曲线、`preprocess_meta.json` 副本 |
| `../ml_bridge/can_cnn64_infer.py` | 桥接侧加载与推理 |
| `../ml_bridge/features.py` | `can_packets_to_matrix_64x9` 实时特征 |

如有新版本权重，只需替换 `artifacts/best_model.pth` 并保证 **`preprocess_meta.json` 与训练时一致**，然后重启 ml_bridge。
