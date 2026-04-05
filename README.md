# VCEI 工作区

本目录 **`VCEI`**（Vehicle / Cybersecurity / Experiment Integration 等含义均可）是**桌面上的车载入侵检测与深度学习实验**相关代码与数据的聚合根目录，**不局限于** `REAL-IDS` 单项目。

各子目录的职责、代码关系与数据流见 **`[CODE_GUIDE.md](CODE_GUIDE.md)`**（单独成篇，按模块说明「每个代码在做什么」）。

---

## 子项目一览

| 目录 | 说明 |
|------|------|
| **[REAL-IDS/](REAL-IDS/)** | 可部署的 **C++17 车载 IDS 核心**（CAN 时钟倾斜 + 以太环形缓冲融合）、**`real_ids_daemon`**（HTTP/SSE）、**Python ml_bridge**（IntrusionDetectNet / CarHack / SupCon）、**Web 观测台**与集成测试。 |
| **[IntrusionDetectNet-CNN-Transformer-main/](IntrusionDetectNet-CNN-Transformer-main/)** | **以太网流量** CNN+Transformer 二分类（BENIGN/ANOMALY），训练与 `transformer_ids_model.pth`；由 `REAL-IDS/integration/ml_bridge` 按路径加载。 |
| **[backend-main/](backend-main/)** | **Django** 后端示例（如 `ids/read_csv`）；**CAN 监督学习** 代码在 **`backend-main/ids/supervised-main`**（SupCon 等），供 ml_bridge 的 SupCon 推理分支使用。 |
| **[CarHackData/](CarHackData/)** | **Car Hacking Dataset** 风格 CAN 日志（Normal / DoS / Fuzzy / gear / RPM），供 `train_carhack.py` 训练与测试脚本评估。 |
| **[autoids_-can-&-ethernet-intrusion-detection-system/](autoids_-can-&-ethernet-intrusion-detection-system/)** | 与 **autoids** 相关的 **Node/前端** 参考实现（含 CAN/以太仿真与展示逻辑）；`REAL-IDS` 的仿真与 API 形态与之对齐。子目录另有 README。 |
| **[MachineLearningCVE/](MachineLearningCVE/)** | **CIC/ISCX 等** 网络流量 CSV 切片，多用于传统/ML 入侵检测实验（与以太网 IDS 论文数据管线相关）。 |
| **`.vscode/`** | 编辑器/工作区配置（可选）。 |
| **`.bevel/`** | 本地工具链相关（可忽略，不参与业务构建）。 |

---

## 推荐阅读顺序

1. **`CODE_GUIDE.md`** — 各模块代码职责与依赖关系（**总览说明，独立文档**）。  
2. **`REAL-IDS/USAGE.md`** — 从编译到 daemon、ml_bridge、前端的**命令步骤**。  
3. **`REAL-IDS/README.md`** — REAL-IDS 子项目内的 API、构建与接入说明。  
4. **`REAL-IDS/docs/CODE_STRUCTURE.md`** — 仅 **`REAL-IDS/`** 仓库内部的文件级结构。

---

## 典型联调链路（概念）

```
CarHackData / IntrusionDetectNet 权重 / supervised-main 权重
        ↓
REAL-IDS：ml_bridge（5055）← daemon（8080）← 浏览器 / 观测台
        ↑
        可选：autoids 参考实现、MachineLearningCVE 等数据与论文仓库
```

---

## 文档索引

| 文档 | 内容 |
|------|------|
| **`CODE_GUIDE.md`**（本目录） | **全工作区**各代码目录的作用与关系 |
| **`REAL-IDS/docs/CODE_STRUCTURE.md`** | 仅 REAL-IDS 仓库内源码文件说明 |

若本目录下尚未克隆某子项目，对应表格中的路径可能不存在，以你本机为准。
