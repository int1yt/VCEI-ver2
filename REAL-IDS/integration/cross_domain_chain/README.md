# 跨域时序攻击链学习（Cross-Domain Chain）

本目录实现 **三阶段** 实验代码，用于在 **CAN 与以太网数据彼此独立、无共同时钟对齐** 的前提下，用 **对比学习 + MMD** 拉近隐空间，再用 **Transformer** 对 **长度为 T=10 的融合特征序列** 做 **攻击链类型** 与 **攻击阶段** 预测。

**重要：**

- **不替换、不删除** 现有独立模型：`integration/can_cnn_64x9/`（CAN CNN）、`integration/ml_bridge/`（IntrusionDetectNet、CarHack、SupCon 等）保持原样；本目录为 **跨域链** 训练代码。
- 当前 **以太网侧** 在训练对齐器时默认使用 **`synthetic_eth.py` 生成的 10×80 合成窗口**（与真实 CIC/车载流量统计一致时需自行替换为真实张量）。

### 与主流程的接入（已接线）

训练得到 `aligner_encoders.pt` 与 `graph_transformer_ids.pt` 并放入 `cross_domain_chain/artifacts/`（或通过 `CHAIN_*` 环境变量指定）后，**无需改 Daemon JSON 字段**：`real_ids_daemon` 仍向 **`POST /v1/enrich`** 发送 `ethernet_context` + `can_history`。**ml_bridge** 会：

1. 照旧跑 **单域** 以太网 IDS 与 CAN CNN（与其它后端）；  
2. 额外用 **对齐器 + GraphTransformerIDS** 生成 **`attack_chain_ml`**，并写入 **`attack_chain`** 人类可读步骤（`attack_chain_transformer`）；  
3. 在 **`fusion_attack_type`** 末尾追加 **`Attack-chain ML: scenario=…`**。

Daemon 侧已将 **CAN 历史容量设为 128**，以便 **10 个** 滑动的 64 帧窗口（约 **≥73** 帧时 `can_sliding_windows_used` 为真）。详见 `integration/ml_bridge/MODELS.md` 中 **2c** 节。

---

## 架构在做什么（对应你的三阶段）

### 第一阶段：`aligner.py` + `train_aligner.py`

- **CANEncoder**：输入单窗口 **64×8**（取自已有的 `X_train.npy` 前 8 列，与 Δt 解耦）。
- **EthernetEncoder**：输入 **10×80**（与 `ml_bridge` 中 IntrusionDetectNet 的序列宽度一致）。
- **对比损失**：`contrastive_with_class_labels` —— 在 batch 内按 **统一标签**（与 CAN 四类一致）拉近跨模态相似度，同类为正样本。
- **MMD**：对 **标签为 Normal(0)** 的 CAN / Eth 隐向量做 **RBF-MMD**，促使两域 **正常流量** 在隐空间边缘分布接近。

**产出：**

- `artifacts/aligner_encoders.pt`
- `artifacts/aligner_loss.png`（总损失、对比项、MMD 项）
- `artifacts/aligner_latent_tsne.png`（CAN / Eth 隐变量 t-SNE，颜色为统一标签）

### 第二阶段：`GraphTransformerIDS.py` + `train_chain.py`

- 输入：**(B, T, d_fused)**，默认 **T=10**，`d_fused = 2 × latent_dim`（CAN 与 Eth 隐向量拼接）。
- **位置编码** + **TransformerEncoder**（多头自注意力），在时间维上捕获 **跨时间步** 依赖（融合向量已含两域信息，协议级耦合由数据与对齐学习）。
- **双头输出：**
  - **chain_logits**：4 类攻击链场景（见下表）。
  - **stage_logits**：每个时间步对 **5 类攻击阶段** 的 logits（可转为概率分布）。

| chain 标签 | 含义（合成规则） |
|-----------|------------------|
| 0 benign | 全程正常 CAN + 正常 Eth |
| 1 eth_recon_only | 半段 Eth 异常模式，CAN 正常 |
| 2 can_attack_only | CAN 攻击类，Eth 正常 |
| 3 eth_then_can_chain | 前半 Eth 异常，后半 CAN 攻击（模拟链式） |

| stage 标签 | 含义 |
|-----------|------|
| 0–4 | normal / eth_reconnaissance / eth_anomaly / can_presurge / can_attack |

**产出：**

- `artifacts/graph_transformer_ids.pt`
- `artifacts/chain_training.png`
- `artifacts/chain_confusion_matrix.png`

### 第三阶段：`chain_generator.py`

- 从 **CAN 的 `.npy` 池** 按类别抽样 **64×8** 窗口；Eth 侧用 **合成 10×80** 或与标签一致的规则生成。
- 使用 **训练好的 aligner** 将每个时间步编码为 **concat(z_can, z_eth)**，拼成 **长度 10** 的序列。
- 随机 **噪声**：以一定概率将某步替换为「全正常」模拟真实混杂流量。
- **输出：** `artifacts/chain_dataset.pt`（含 `sequences`, `chain_labels`, `stage_labels`, `meta`）。

---

## 依赖

```text
pip install -r requirements.txt
```

（torch、numpy、scikit-learn、matplotlib、tqdm；t-SNE 使用 sklearn。）

---

## 推荐执行顺序（真实 CarHack 数据）

在仓库根目录外准备好 **`can_cnn_64x9/preprocess.py`** 生成的 `X_train.npy` / `y_train.npy`（或 `processed/` 下全部）。

```powershell
cd c:\Users\Luyutong\Desktop\VCEI\REAL-IDS\integration\cross_domain_chain

# 1) 训练对齐器（可限制样本数以加速实验）
python train_aligner.py --can-dir ..\can_cnn_64x9\processed --epochs 25 --batch-size 256 --max-samples 200000 --out .\artifacts

# 2) 生成攻击链数据集
python chain_generator.py --can-x ..\can_cnn_64x9\processed\X_train.npy --can-y ..\can_cnn_64x9\processed\y_train.npy --aligner .\artifacts\aligner_encoders.pt --n-samples 20000 --out .\artifacts\chain_dataset.pt

# 3) 训练 Transformer
python train_chain.py --dataset .\artifacts\chain_dataset.pt --epochs 40 --out .\artifacts
```

---

## 无 CarHack 预处理文件时（仅 smoke test）

```powershell
python train_aligner.py --demo-n 8000 --epochs 5 --out .\artifacts
python chain_generator.py --demo-n 5000 --aligner .\artifacts\aligner_encoders.pt --n-samples 2000 --out .\artifacts\chain_dataset.pt
python train_chain.py --dataset .\artifacts\chain_dataset.pt --epochs 15 --out .\artifacts
```

---

## 图形与文件含义速查

| 文件 | 含义 |
|------|------|
| `aligner_loss.png` | 对齐训练是否收敛；MMD 应随训练下降（正常样本分布拉近）。 |
| `aligner_latent_tsne.png` | 两域编码器是否将 **相同类别** 拉到相近区域；CAN vs Eth 点形状不同。 |
| `chain_training.png` | 链分类器训练/验证损失。 |
| `chain_confusion_matrix.png` | 四种 **链类型** 的混淆情况；链 3（跨域）通常最难。 |

---

## “识别整个攻击链”在本实现中的含义

- **独立 IDS 模型**（CAN CNN、以太网 Transformer）仍各自输出 **单域标签/置信度**。
- **本管线** 在 **离线训练** 后，可对 **一段 10 步的融合时间序列** 输出：
  1. **整条链属于哪类剧本**（例如是否出现「先以太异常再 CAN 攻击」）。
  2. **每一步处于哪一攻击阶段**（概率分布）。

中央处理器若要 **融合时序二维 ML**，建议流程：**对齐器编码 → 滑窗堆叠 10 步 → GraphTransformerIDS → 链标签 + 阶段分布**，并与现有规则引擎（时钟 skew、阈值等）**叠加决策**，而不是互相替换。

---

## 全量数据是否可行？

- **可行**：对齐器与链生成器均支持 **全量 `X_train.npy`**（`--max-samples 0` 表示不截断）。
- **注意**：`.npy` 体积大、训练慢；建议 **GPU**、适当 **batch-size**，链生成 **`--n-samples`** 可设数万～数十万（生成时间与磁盘占用线性增长）。

---

## 文件清单

| 文件 | 说明 |
|------|------|
| `aligner.py` | CANEncoder、EthernetEncoder、MMD、对比损失 |
| `synthetic_eth.py` | 合成 Eth 特征 |
| `train_aligner.py` | 对齐训练 + 可视化 |
| `GraphTransformerIDS.py` | 时序 Transformer + 链/阶段双头 |
| `chain_generator.py` | 伪联合链数据集 |
| `train_chain.py` | 链模型训练 + 可视化 |

---

## 与现有 ML 的边界（保留两套独立模型）

| 模块 | 路径 | 是否被本目录修改 |
|------|------|------------------|
| CAN 64×9 CNN | `integration/can_cnn_64x9/` | **否** |
| 以太网 IntrusionDetectNet 桥接 | `integration/ml_bridge/eth_intrusion_net.py` | **否** |
| 融合 REST | `integration/ml_bridge/server.py` | **否**（本管线未默认接入） |

后续若要将 **攻击链 Transformer** 接入 `server.py`，建议新增独立路由（例如 `/v1/enrich_chain`）并显式传入 **10 步融合特征**，避免影响现有 `/v1/enrich` 行为。
