# REAL-IDS 代码结构说明

本文说明 **`REAL-IDS/`** 仓库内主要源码与配置的职责及相互关系。第三方头文件（`httplib.h`、`json.hpp`）为上游单文件发行版，此处只说明**在本项目中的用途**，不展开其内部实现。

---

## 整体数据流（概念）

```
仿真或实车 CAN/以太帧
        ↓
  IdsEngine（C++ 静态库 real_ids）
   ├─ CanClockSkewIds：按 CAN ID 学习间隔，检测时间偏移
   ├─ EthRingBuffer：时间窗内以太帧环形缓冲
   └─ CentralProcessor：融合规则 → Alert
        ↓
real_ids_daemon（可选）HTTP/SSE 对外；告警时 POST → ml_bridge
        ↓
ml_bridge：IntrusionDetectNet / CarHack CNN / SupCon → ml_fusion JSON
        ↓
web-dashboard：EventSource 订阅 SSE，展示告警与攻击链
```

---

## 目录树（源码与配置）

```
REAL-IDS/
├── cpp/
│   ├── CMakeLists.txt          # 生成静态库 real_ids + 可执行文件 real_ids_daemon
│   ├── configure_vs2022.bat    # Windows：vcvars + NMake 一键配置/编译（常用）
│   ├── include/real_ids/       # 公共头文件（库对外 API）
│   ├── src/                    # 库实现 .cpp
│   ├── daemon/                 # 仅可执行文件使用的入口与 SSE 广播
│   └── third_party/            #  vendored 单文件依赖
├── integration/ml_bridge/      # FastAPI：深度学习融合桥
├── web-dashboard/              # Vite + React 观测台（及免构建 HTML）
├── tests/integration/          # Python：HTTP 集成测试 + 离线指标
├── docs/                       # 本说明与文档索引
├── README.md                   # 项目总 README
├── USAGE.md                    # 命令步骤速查
└── start_daemon_with_ml_bridge.bat
```

---

## `cpp/` — C++ 核心库与守护进程

### 构建系统

| 文件 | 作用 |
|------|------|
| **`CMakeLists.txt`** | 定义目标：`real_ids`（静态库）、`real_ids_daemon`（链接 `real_ids` + 线程库 + Windows 下 `ws2_32`）。 |
| **`configure_vs2022.bat`** | 在无 VS 开发者 PATH 时调用 `vcvars64`，用 NMake 配置/编译，避免「找不到编译器」。 |

### 库公共接口 `include/real_ids/`

| 文件 | 作用 |
|------|------|
| **`types.hpp`** | 核心数据结构：`CanPacket`、`EthernetPacket`、`Alert`（含 `classification`、`ethernet_context` 等），全库与 daemon JSON 对齐的基础类型。 |
| **`time_source.hpp`** | 抽象时钟 `TimeSource` / 默认 `SystemTimeSource`（`now_ms()`），量产可换为 gPTP/PHC 对齐时间。 |
| **`ingress.hpp`** | 量产接入点接口：`ICanIngress`、`IEthIngress`（`try_pop`），与仿真无关，供实车线程喂帧。 |
| **`can_ids.hpp`** | `CanClockSkewIds`：按 CAN ID 维护到达间隔的指数滑动估计，用**与期望到达时刻的偏差**是否超过阈值判定异常（时钟倾斜/突发时序）。 |
| **`eth_buffer.hpp`** | `EthRingBuffer`：按时间戳索引的以太网帧环形缓冲，供融合阶段取「CAN 时刻附近」的以太上下文。 |
| **`central_processor.hpp`** | `CentralProcessor`：根据引擎模式（仿真对齐 / 量产）组合 CAN IDS 结果、以太缓冲与标志位，生成**分类字符串与置信度**，并组装 `Alert`。 |
| **`engine.hpp`** | `IdsEngine`：门面类；持有 `CanClockSkewIds`、`EthRingBuffer`、`CentralProcessor`、`EngineMode`，串行化 `train`/`ingest_can`/`ingest_eth`，通过回调发出 CAN/以太/告警事件。 |

### 库实现 `src/`

| 文件 | 作用 |
|------|------|
| **`can_ids.cpp`** | `CanClockSkewIds::train` / `detect`：首帧建基线，后续用 EMA 更新平均间隔；`detect` 中计算 `skew` 并与 `skew_threshold_ms` 比较。 |
| **`eth_buffer.cpp`** | 环形缓冲插入、按时间窗查询、容量与淘汰策略。 |
| **`central_processor.cpp`** | 规则融合逻辑（仿真下可与 `synthetic_attack_flag` 组合；量产侧侧重 CAN 时序异常文案）。 |
| **`engine.cpp`** | `IdsEngine` 构造、模式切换、`ingest_*` 与训练阶段切换、`set_callbacks` 等。 |

### 守护进程 `daemon/`

| 文件 | 作用 |
|------|------|
| **`main.cpp`** | **HTTP 服务器**（`httplib`）：`/api/v1/health`、`/api/v1/stats`、仿真 `start`/`stop`/`attack`、**SSE** `/api/v1/stream`；后台线程产生仿真 CAN/以太流量；维护最近 CAN 历史供 ML 桥 `POST /v1/enrich`；读环境变量 `REAL_IDS_PORT`、`REAL_IDS_MODE`、`REAL_IDS_ML_BRIDGE`。 |
| **`broadcast_hub.hpp`** | SSE 多订阅者广播：每连接一个 `SseSubscriber` 队列，`publish` 推送一行 JSON 字符串。 |

### 第三方 `third_party/`

| 文件 | 作用 |
|------|------|
| **`httplib.h`** | 单文件 HTTP 服务端/客户端；daemon 用作服务器，并向 `REAL_IDS_ML_BRIDGE` 发客户端 `POST`。上游项目维护，**勿当业务代码修改**；升级时替换整文件。 |
| **`nlohmann/json.hpp`** | JSON 序列化/解析，与告警和 ML 请求体对接。 |

---

## `integration/ml_bridge/` — Python 融合服务

| 文件 | 作用 |
|------|------|
| **`server.py`** | FastAPI 应用：`GET /health`（模型是否加载）、`POST /v1/enrich`（接收 daemon 发来的分类名、以太上下文、CAN 历史）；**优先 CarHack CNN**，否则 SupCon；以太走 IntrusionDetectNet 或启发式；输出 `fusion_attack_type`、`attack_chain`、`ethernet_ml`、`can_ml`。 |
| **`features.py`** | 将 JSON 列表转为模型输入：`eth_packets_to_sequence_10x80`、`can_packets_to_matrix_29x29`。 |
| **`eth_intrusion_net.py`** | 加载 `TransformerClassifier` 权重，对 `(10,80)` 推理 BENIGN/ANOMALY。 |
| **`can_supcon_infer.py`** | 从 `backend-main/.../supervised-main` 导入 `load_model`，对 `(29,29)` 做 5 类推理。 |
| **`chain_builder.py`** | 根据 ML 与规则结果生成人类可读 **`attack_chain`** 步骤列表。 |
| **`carhack_io.py`** | 解析 `CarHackData` 的 txt/csv 为统一 packet 字典。 |
| **`carhack_model.py`** | `CarHackCanCNN` 小网络定义。 |
| **`carhack_infer.py`** | 加载 `models/carhack_can_clf.pth`，`predict_matrix`。 |
| **`train_carhack.py`** | 从 CarHackData 滑窗训练并写出权重。 |
| **`requirements.txt`** | Python 依赖；`MODELS.md` 描述权重与环境变量。 |

---

## `web-dashboard/` — 前端观测台

| 文件 | 作用 |
|------|------|
| **`package.json` / `vite.config.ts` / `tsconfig.json`** | npm 脚本、Vite 与 TypeScript 配置。 |
| **`index.html`** | Vite 入口 HTML。 |
| **`src/main.tsx`** | React 挂载根节点。 |
| **`src/App.tsx`** | 主界面：连接 daemon SSE、展示事件/告警/**`ml_fusion`**（若存在）。 |
| **`src/index.css`** | 全局样式。 |
| **`src/vite-env.d.ts`** | Vite 类型声明。 |
| **`observatory-standalone.html`** | 无 npm 构建时单文件页面，静态服务器打开即可。 |
| **`.env` / `.env.example`** | `VITE_REAL_IDS_URL` 指向 daemon 基地址。 |

---

## `tests/integration/` — 集成测试与离线指标

| 文件 | 作用 |
|------|------|
| **`run_tests.py`** | 主入口：探测 daemon/ml_bridge、正确性用例、HTTP 延迟统计；可选 CarHack 离线准确率与时钟倾斜 Python 参考实现的纳秒级微基准；写 `results/summary.json|txt`。 |
| **`reporting.py`** | 汇总报告结构体与 JSON/文本写出。 |
| **`metrics_ml.py`** | 调用 `train_carhack.collect_windows` + `CarHackCanInfer` 算准确率/混淆矩阵；调用 `clock_skew_ref` 输出延迟统计。 |
| **`clock_skew_ref.py`** | 与 `cpp/src/can_ids.cpp` 行为一致的 Python 参考，用于微基准而非替代生产 C++。 |
| **`requirements.txt`** | 测试脚本依赖（如 `httpx`）。 |

---

## 仓库根目录其它文件

| 文件 | 作用 |
|------|------|
| **`README.md`** | 项目介绍、构建、REST/SSE 说明、量产接入指引。 |
| **`USAGE.md`** | 分阶段命令（编译、模型、桥、daemon、前端）。 |
| **`start_daemon_with_ml_bridge.bat`** | 设置 `REAL_IDS_ML_BRIDGE` 后启动 `real_ids_daemon.exe`（路径按仓库约定）。 |

---

## 模块依赖关系（库内部）

```
types.hpp
    ↑
time_source.hpp, can_ids.hpp, eth_buffer.hpp, central_processor.hpp
    ↑
engine.hpp
    ↑
engine.cpp + 各 src/*.cpp
```

`daemon/main.cpp` **仅链接** `real_ids`，并额外包含 `broadcast_hub.hpp` 与 `httplib`，不修改 `IdsEngine` 内部算法。

---

## 与仓库外目录的约定关系（非本文件夹内代码）

- **`VCEI/IntrusionDetectNet-CNN-Transformer-main/`**：以太网模型训练与默认 `transformer_ids_model.pth` 路径（由 `server.py` 默认解析）。
- **`VCEI/backend-main/.../supervised-main/`**：CAN SupCon 训练与 `test_model.load_model`；由 `can_supcon_infer.py` 动态加入 `sys.path`。
- **`VCEI/CarHackData/`**：CarHack 训练/测试默认数据根（`carhack_io.default_carhack_data_root`）。

以上路径在部署时可由环境变量覆盖，详见 `integration/ml_bridge/MODELS.md`。
