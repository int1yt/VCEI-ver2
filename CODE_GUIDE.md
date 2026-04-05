# VCEI 代码说明（各模块职责）

本文独立于 **`REAL-IDS/README.md`**，说明 **`VCEI` 工作区根目录下各子文件夹**中的代码**起什么作用**、**如何与 REAL-IDS 配合**。不逐行解释第三方库内部实现。

---

## 1. `REAL-IDS/`

**作用：** 本工作区的**主工程**：车载 IDS **算法内核（C++）**、对外 **守护进程**、**深度学习融合桥（Python）**、**观测台前端**与**自动化测试**。

| 部分 | 职责 |
|------|------|
| **`cpp/`** | 静态库 **`real_ids`**：`CanClockSkewIds`（按 CAN ID 学习到达间隔并检测时间偏移）、`EthRingBuffer`、`CentralProcessor` 融合、`IdsEngine` 门面；**`real_ids_daemon`** 提供 HTTP/SSE 与仿真。 |
| **`integration/ml_bridge/`** | **FastAPI**：对告警上下文做以太/CAN 深度学习推理，输出 `ml_fusion`（含 `attack_chain`）。优先 **CarHack** 权重，其次 **SupCon**，以太侧 **IntrusionDetectNet**。 |
| **`web-dashboard/`** | **Vite + React** 大屏（或单文件 HTML），订阅 daemon 的 SSE，展示告警与 ML 结果。 |
| **`tests/integration/`** | **httpx** 集成测试、离线 **CarHack 准确率**、**时钟倾斜算法** Python 参考实现的微基准。 |
| **`docs/`** | 仅描述 **REAL-IDS 仓库内部**文件结构，见 `CODE_STRUCTURE.md`。 |

**依赖工作区其它目录：** 默认从 **`../IntrusionDetectNet-.../PycharmProjects/transformer_ids_model.pth`**、**`../backend-main/.../supervised-main`**、**`../CarHackData`** 等路径解析（可用环境变量覆盖）。详见 **`REAL-IDS/integration/ml_bridge/MODELS.md`**。

---

## 2. `IntrusionDetectNet-CNN-Transformer-main/`

**作用：** **以太网侧**入侵检测的 **PyTorch 研究/训练工程**（CNN + Transformer，对流量序列做二分类：正常/异常）。

| 典型内容 | 说明 |
|----------|------|
| **`PycharmProjects/train.py`** 等 | 训练脚本，产出 **`transformer_ids_model.pth`**（或项目根目录下同名文件，取决于运行时的当前工作目录）。 |
| **数据** | 与 **CIC-IDS** 等网络流量格式相关；与车载 CAN 无关。 |

**与 REAL-IDS 的关系：** **`ml_bridge/eth_intrusion_net.py`** 加载该权重，对 **10×80** 特征序列做推理；REAL-IDS 仿真里拼的以太特征为占位时，**数值分布与论文训练不一致**，需量产时对齐预处理。

---

## 3. `backend-main/`

**作用：** **Django Web 后端**工程；其中 **`ids`** 应用下挂有**多块 IDS 相关代码**。

| 路径 | 职责 |
|------|------|
| **`backend-main/ids/views.py`** | 示例接口 **`read_csv`**：读 CSV 返回 JSON，**不包含** PyTorch 在线推理。 |
| **`backend-main/ids/supervised-main/`** | **CAN 5 类** 监督学习（SupCon + 迁移等）：训练脚本、`test_model.load_model`；**`ml_bridge/can_supcon_infer.py`** 通过 `sys.path` 导入并加载 **`ckpt_epoch_*.pth`**。 |
| **`backend-main/ids/unsupervised-main/`** 等 | 其它论文/实验代码，与 REAL-IDS 默认**无直接运行时依赖**。 |

**与 REAL-IDS 的关系：** CAN 的 **SupCon 分支**依赖此目录下的 **权重与 Python 模块**；CarHack 分支**不依赖** Django 服务是否启动。

---

## 4. `CarHackData/`

**作用：** **车载 CAN 日志数据**（多文件：Normal 文本、各攻击类型 CSV），作为 **`train_carhack.py`** 的默认训练/评估数据源。

| 文件 | 标签含义（与 CarHack 训练脚本一致） |
|------|--------------------------------------|
| `normal_run_data.txt` | Normal |
| `DoS_dataset.csv` / `Fuzzy_dataset.csv` / `gear_dataset.csv` / `RPM_dataset.csv` | 对应攻击类型 |

**与 REAL-IDS 的关系：** 训练得到 **`ml_bridge/models/carhack_can_clf.pth`** 后，**同一套滑窗 + 矩阵特征** 用于离线测试与在线推理。

---

## 5. `autoids_-can-&-ethernet-intrusion-detection-system/`

**作用：** **参考实现**——与 **autoids** 产品/论文一致风格的 **CAN + 以太** 入侵检测**演示**（Node/前端等）。**`REAL-IDS` 的 daemon** 在仿真模式、SSE 事件形态、部分 API 路径上**与之对齐**，便于对比与迁移。

| 说明 |
|------|
| 子目录内 **README** 可能描述上游模板（如本地运行说明）；**业务逻辑**以 **`server.ts` 等源码**为准。 |

**与 REAL-IDS 的关系：** 非强制依赖；不启动该目录服务也可单独运行 REAL-IDS 全栈。

---

## 6. `MachineLearningCVE/`

**作用：** 存放 **CIC/ISCX 等** 公开数据集的 **CSV 切片**（按工作日/攻击类型划分），用于**通用网络入侵检测**机器学习实验。

**与 REAL-IDS 的关系：** **数据资源**；若要把以太网 IDS 与论文完全一致，需在特征工程阶段与 **IntrusionDetectNet** 训练管线对齐。默认 **ml_bridge 不直接读取本目录**。

---

## 7. 工具与配置目录（可选）

| 目录 | 作用 |
|------|------|
| **`.vscode/`** | VS Code 工作区设置、调试配置等。 |
| **`.bevel/`** | 本地辅助工具，**不参与** REAL-IDS 构建与运行。 |

---

## 8. 依赖关系简图

```
                    ┌─────────────────────────────────────┐
                    │           REAL-IDS（主入口）           │
                    │  daemon ←→ ml_bridge ←→ web-dashboard │
                    └───────────────┬─────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        ▼                           ▼                           ▼
IntrusionDetectNet-...      backend-main/ids/              CarHackData/
(以太 .pth)                 supervised-main               (CAN 数据)
                            (SupCon .pth)                      │
                                                               ▼
                                                    train_carhack → carhack_can_clf.pth

autoids_...（参考）        MachineLearningCVE/（数据集）
MachineLearningCVE 不直接进 ml_bridge 默认路径
```

---

## 9. 文档与 README 分工

| 文档 | 范围 |
|------|------|
| **`VCEI/README.md`** | 工作区总览与子目录索引。 |
| **本文 `VCEI/CODE_GUIDE.md`** | **各目录代码职责**（全工作区）。 |
| **`REAL-IDS/docs/CODE_STRUCTURE.md`** | **仅 REAL-IDS 仓库内**文件级说明。 |
| **`REAL-IDS/USAGE.md`** | 可执行命令与启动顺序。 |
