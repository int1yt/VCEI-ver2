# REAL-IDS 使用步骤（按顺序）

**路径约定：** 工程根目录 `C:\Users\Luyutong\Desktop\VCEI`。下文凡写 `VCEI`、`REAL-IDS` 均相对该根目录。

---

## 系统总览（你要跑起来的是什么）

| 组件 | 作用 | 典型端口 |
|------|------|----------|
| **ml_bridge**（Python / FastAPI） | 加载 PyTorch：以太网 IDS、CAN 分类、**可选**跨域攻击链 Transformer；提供 **`POST /v1/enrich`** | **5055** |
| **real_ids_daemon**（C++） | 仿真或生产模式下的 CAN/以太流量、规则融合、告警；告警时 **POST** 到 ml_bridge，把返回写入 **`ml_fusion`** | **8080**（可改） |
| **web-dashboard**（可选） | 浏览器里看 SSE 流、环形缓冲、`ml_fusion`、攻击链步骤 | 5173 等 |

**数据流（有 ML 时）：** Daemon 收集 **以太网上下文** + **CAN 历史（最多 128 帧）** → 发往 `http://<桥地址>/v1/enrich` → 返回 **`fusion_attack_type`、`attack_chain`、`ethernet_ml`、`can_ml`、可选 `attack_chain_ml`** → 随告警推给前端。

**固定启动顺序：** **① ml_bridge → ② daemon → ③ 前端**（否则 daemon 连不上桥就没有完整 `ml_fusion`）。

---

## 阶段一：每台电脑只做一次

### 步骤 1 — 编译守护进程

1. 安装 **Visual Studio 2022**（含「使用 C++ 的桌面开发」）和 **Windows SDK**（缺 `crtdbg.h` 时补装 SDK）。
2. 执行：

```bat
cd /d C:\Users\Luyutong\Desktop\VCEI\REAL-IDS\cpp
configure_vs2022.bat
```

3. 记下生成的 **`real_ids_daemon.exe`** 路径（常见为 `cpp\build\` 或 `cpp\build\Release\`）。

### 步骤 2 — 配置 ml_bridge 的 Python 环境

1. 执行：

```bat
cd /d C:\Users\Luyutong\Desktop\VCEI\REAL-IDS\integration\ml_bridge
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
```

2. 以后每次用桥或训练 CarHack，都先 **`cd` 到本目录** 再 **`activate.bat`**。

---

## 阶段二：准备模型权重（需要 `ml_fusion` / 深度学习分类时做）

**顺序说明：** 先有权重文件，再在阶段三里启动 uvicorn。

**CAN 后端优先级（桥内自动选择）：** **① CAN 64×9 CNN**（若存在 `can_cnn_64x9/artifacts/best_model.pth`）→ **② CarHack** → **③ SupCon**。  
**以太网：** IntrusionDetectNet（`transformer_ids_model.pth`），缺失时用仿真标志做启发式。  
**攻击链（可选）：** 若同时存在 `cross_domain_chain/artifacts/aligner_encoders.pt` 与 `graph_transformer_ids.pt`，`/v1/enrich` 会多返回 **`attack_chain_ml`**。

### 步骤 3a — CAN：64×9 滑动窗口 CNN（可选，优先级最高）

1. 数据在 **`VCEI\CarHackData\`**（与 CarHack 相同文件名习惯）。  
2. 执行：

```bat
cd /d C:\Users\Luyutong\Desktop\VCEI\REAL-IDS\integration\can_cnn_64x9
pip install -r requirements.txt
python preprocess.py --data-root C:\Users\Luyutong\Desktop\VCEI\CarHackData --out .\processed
python train.py --data-dir .\processed --out .\artifacts --epochs 50 --batch-size 256
```

3. 生成 **`can_cnn_64x9\artifacts\best_model.pth`** 与同目录 **`preprocess_meta.json`**。  
4. 阶段四启动桥前可设（不设则默认指向上述路径）：

```bat
set CAN_CNN64_MODEL_PATH=C:\...\best_model.pth
set CAN_CNN64_META_PATH=C:\...\preprocess_meta.json
```

### 步骤 3 — CAN：CarHack（在未使用 64×9 或作为备选时推荐）

1. 确认数据在 **`VCEI\CarHackData\`**（`normal_run_data.txt`、`DoS_dataset.csv`、`Fuzzy_dataset.csv`、`gear_dataset.csv`、`RPM_dataset.csv`）。
2. 在已 **activate** 的 `ml_bridge` 目录执行：

```bat
python train_carhack.py --epochs 12
```

3. 确认生成：**`REAL-IDS\integration\ml_bridge\models\carhack_can_clf.pth`**。  
   - 若权重在别处：阶段四启动桥前执行 `set CARHACK_MODEL_PATH=完整路径\carhack_can_clf.pth`。

### 步骤 4 — 以太：IntrusionDetectNet（可选）

1. 有现成 **`transformer_ids_model.pth`** 则放到：

`VCEI\IntrusionDetectNet-CNN-Transformer-main\PycharmProjects\transformer_ids_model.pth`

或阶段四用 **`set ETH_MODEL_PATH=...`** 指向该文件。

2. 需自训时在 **`VCEI\IntrusionDetectNet-CNN-Transformer-main`** 执行：

```bat
python PycharmProjects\train.py
```

（需已备好 `PycharmProjects` 下 `train_X/Y`、`test_X/Y`；权重多在当前工作目录下的 `transformer_ids_model.pth`。）

### 步骤 5 — CAN：SupCon（仅当不用 CarHack 或 CarHack 未加载时）

1. 在 **`VCEI\backend-main\backend-main\ids\supervised-main`** 依次执行：

```bat
python train_test_split.py --data_path Data/ --car_model None --window_size 29 --strided 15 --rid 2
python train_baseline.py --data_dir Data/TFrecord_w29_s15/ --model resnet18 --save_freq 10 --window_size 29 --num_workers 8 --cosine --epochs 50 --batch_size 256 --learning_rate 0.0005 --rid 5
python train_supcon.py --data_dir Data/TFrecord_w29_s15/ --model resnet18 --save_freq 10 --window_size 29 --epochs 200 --num_workers 8 --temp 0.07 --learning_rate 0.1 --learning_rate_classifier 0.01 --cosine --epoch_start_classifier 170 --rid 3 --batch_size 512
```

2. 在 **`save\...\models\`** 找到成对的 **`ckpt_epoch_N.pth`** 与 **`ckpt_class_epoch_N.pth`**，记下文件夹路径和 **N**。  
3. 阶段四启动桥前执行：

```bat
set CAN_PRETRAINED_PATH=该models文件夹完整路径
set CAN_CKPT=N
```

### 步骤 5b — 跨域攻击链 Transformer（可选）

在已能跑通 **CAN 预处理 `.npy`** 的前提下，训练对齐器与链模型（详见 **`integration\cross_domain_chain\README.md`**）：

```bat
cd /d C:\Users\Luyutong\Desktop\VCEI\REAL-IDS\integration\cross_domain_chain
pip install -r requirements.txt
python train_aligner.py --can-dir ..\can_cnn_64x9\processed --epochs 25 --out .\artifacts
python chain_generator.py --can-x ..\can_cnn_64x9\processed\X_train.npy --can-y ..\can_cnn_64x9\processed\y_train.npy --aligner .\artifacts\aligner_encoders.pt --n-samples 20000 --out .\artifacts\chain_dataset.pt
python train_chain.py --dataset .\artifacts\chain_dataset.pt --epochs 40 --out .\artifacts
```

得到 **`artifacts\aligner_encoders.pt`** 与 **`artifacts\graph_transformer_ids.pt`**。阶段四启动桥前可设：

```bat
set CHAIN_ALIGNER_PATH=C:\...\aligner_encoders.pt
set CHAIN_GRAPH_PATH=C:\...\graph_transformer_ids.pt
```

---

## 阶段三：每次跑「桥 + daemon + 界面」（固定顺序）

### 步骤 6 — 启动 ml_bridge（必须第一个启动）

1. 打开 CMD：

```bat
cd /d C:\Users\Luyutong\Desktop\VCEI\REAL-IDS\integration\ml_bridge
.venv\Scripts\activate.bat
```

2.（可选）按阶段二设置权重路径（只设你实际部署的即可）：

```bat
set ETH_MODEL_PATH=C:\路径\transformer_ids_model.pth
set CAN_CNN64_MODEL_PATH=C:\路径\can_cnn_64x9\artifacts\best_model.pth
set CAN_CNN64_META_PATH=C:\路径\can_cnn_64x9\artifacts\preprocess_meta.json
set CARHACK_MODEL_PATH=C:\路径\carhack_can_clf.pth
set CAN_PRETRAINED_PATH=C:\路径\models
set CAN_CKPT=200
set CHAIN_ALIGNER_PATH=C:\路径\cross_domain_chain\artifacts\aligner_encoders.pt
set CHAIN_GRAPH_PATH=C:\路径\cross_domain_chain\artifacts\graph_transformer_ids.pt
set CHAIN_DT_MAX_MS=1000000
set ML_BRIDGE_CUDA=1
```

3. 启动服务：

```bat
uvicorn server:app --host 127.0.0.1 --port 5055
```

4. 浏览器打开 **`http://127.0.0.1:5055/health`**，确认 `status` 为 **`ok`**，并查看：  
   - **`can_cnn64_loaded`** / **`carhack_can_loaded`** / **`can_model_loaded`**（CAN 实际走的后端见 **`can_backend`**）  
   - **`eth_model_loaded`**  
   - **`attack_chain_loaded`**（仅当步骤 5b 权重就位时为 `true`）  
5. **不要关**本窗口；改权重后在本窗口 **`Ctrl+C`** 再重复步骤 2–3。

### 步骤 7 — 启动 real_ids_daemon（第二个启动）

**新开**一个终端。**PowerShell 必须用 `$env:`，不要用 CMD 的 `set`（否则子进程读不到）。**

CMD：

```bat
set REAL_IDS_ML_BRIDGE=http://127.0.0.1:5055
cd /d C:\Users\Luyutong\Desktop\VCEI\REAL-IDS\cpp\build
real_ids_daemon.exe
```

PowerShell：

```powershell
$env:REAL_IDS_ML_BRIDGE = "http://127.0.0.1:5055"
cd C:\Users\Luyutong\Desktop\VCEI\REAL-IDS\cpp\build
.\real_ids_daemon.exe
```

（若 exe 在 `build\Release\`，把 `cd` 改成该目录。）

或双击 **`REAL-IDS\start_daemon_with_ml_bridge.bat`**（默认桥地址同上）。

可选（启动 exe 之前）：

```bat
set REAL_IDS_PORT=8080
set REAL_IDS_MODE=simulation
```

PowerShell 等价：`$env:REAL_IDS_PORT = "8080"`、`$env:REAL_IDS_MODE = "simulation"`。

### 步骤 8 — 启动 Web 观测台（第三个启动）

1. 编辑 **`REAL-IDS\web-dashboard\.env`**：`VITE_REAL_IDS_URL=http://127.0.0.1:8080`（daemon 端口一致）。

2. 任选一种：

```powershell
cd C:\Users\Luyutong\Desktop\VCEI\REAL-IDS\web-dashboard
.\run-dev.ps1
```

或免 npm：

```bat
cd /d C:\Users\Luyutong\Desktop\VCEI\REAL-IDS\web-dashboard
python -m http.server 5173
```

浏览器打开 **`http://127.0.0.1:5173`**（Vite）或 **`http://127.0.0.1:5173/observatory-standalone.html`**（http.server）。daemon 非 8080 时在页面改 API 或用 `observatory-standalone.html?api=http://127.0.0.1:端口`。

### 步骤 9 — 仿真、看告警、看 SSE

1. 浏览器访问 **`http://127.0.0.1:8080/api/v1/health`**，确认 daemon 正常。
2. 在页面 **启动仿真 → 注入攻击**，或用 PowerShell：

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8080/api/v1/simulation/start" -Method Post
Invoke-RestMethod -Uri "http://127.0.0.1:8080/api/v1/simulation/attack" -Method Post -ContentType "application/json" -Body '{"type":"ethernet-can"}'
```

3. 告警 JSON 中应有 **`ml_fusion`**。  
   - 使用 64×9 模型时 **`can_ml.source`** 为 **`can_cnn64`**；CarHack 时为 **`carhack_cnn`**。  
   - 若启用攻击链，**`ml_fusion.attack_chain_ml`** 含 **`chain_name`、`chain_probs`、`stage_probs_per_timestep`** 等；**`attack_chain`** 步骤中会多 **`attack_chain_transformer`**。
4. 事件流：

```powershell
curl.exe -N http://127.0.0.1:8080/api/v1/stream
```

5. 结束仿真：

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8080/api/v1/simulation/stop" -Method Post
```

---

## 分支：不要机器学习（只要仿真 + API）

1. **跳过阶段二、步骤 6**。  
2. 直接 **步骤 7** 但不设置 `REAL_IDS_ML_BRIDGE`，只运行 `real_ids_daemon.exe`。  
3. 仍可做 **步骤 8–9**（界面上无 `ml_fusion` 或为空属正常）。

---

## 附录：环境变量一览

| 变量 | 何时设置 | 作用 |
|------|----------|------|
| `REAL_IDS_PORT` | 启动 daemon 前 | HTTP 端口，默认 8080 |
| `REAL_IDS_MODE` | 启动 daemon 前 | `simulation`（默认）或 `production` |
| `REAL_IDS_ML_BRIDGE` | 启动 daemon 前 | 如 `http://127.0.0.1:5055`，无则告警不含 `ml_fusion` |
| `ETH_MODEL_PATH` | 启动 uvicorn 前 | 以太 IntrusionDetectNet：`transformer_ids_model.pth` |
| `CAN_CNN64_MODEL_PATH` | 启动 uvicorn 前 | CAN 64×9 权重；不设则默认 `integration\can_cnn_64x9\artifacts\best_model.pth` |
| `CAN_CNN64_META_PATH` | 启动 uvicorn 前 | `preprocess_meta.json`（与训练时一致，用于 Δt 归一化） |
| `CARHACK_MODEL_PATH` | 启动 uvicorn 前 | CarHack 权重；不设则用 `ml_bridge\models\carhack_can_clf.pth` |
| `CAN_PRETRAINED_PATH` / `CAN_CKPT` | 启动 uvicorn 前 | SupCon（64×9 与 CarHack 均未加载时） |
| `CHAIN_ALIGNER_PATH` / `CHAIN_GRAPH_PATH` | 启动 uvicorn 前 | 跨域攻击链：对齐器与 GraphTransformer 权重 |
| `CHAIN_DT_MAX_MS` | 启动 uvicorn 前 | 无 CAN_CNN64 meta 时 CAN Δt 缩放兜底 |
| `ML_BRIDGE_CUDA` | 启动 uvicorn 前 | 设为 `1` 尝试 GPU 推理 |
| `VITE_REAL_IDS_URL` | 写入 `web-dashboard\.env` | 前端指向 daemon |

---

## 附录：全模型训练与产物（逐条命令）

以下假设 **工程根目录** 为 `C:\Users\Luyutong\Desktop\VCEI`（下文写 **`%VCEI%`**）。数据 **`CarHackData`** 位于 **`%VCEI%\CarHackData\`**（含 `normal_run_data.txt`、`DoS_dataset.csv`、`Fuzzy_dataset.csv`、`gear_dataset.csv`、`RPM_dataset.csv`）。

**说明：** 运行时 **CAN 只会有一个后端生效**（优先级：64×9 → CarHack → SupCon），但你可以**把三套 CAN 权重都训练好**放在默认路径，便于切换环境变量做对比。以太网、攻击链与 CAN **可同时生效**。

### A. 公共：安装各子项目依赖（每台机子做一次）

在已安装 **Python 3.10+** 的前提下：

```bat
cd /d C:\Users\Luyutong\Desktop\VCEI\REAL-IDS\integration\ml_bridge
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
```

```bat
cd /d C:\Users\Luyutong\Desktop\VCEI\REAL-IDS\integration\can_cnn_64x9
pip install -r requirements.txt
```

```bat
cd /d C:\Users\Luyutong\Desktop\VCEI\REAL-IDS\integration\cross_domain_chain
pip install -r requirements.txt
```

（也可只建 **一个** venv，在以上目录分别 `pip install` 合并依赖。）

---

### B. 以太网：IntrusionDetectNet（`10×80` → BENIGN/ANOMALY）

**产物路径（桥默认查找）：**  
`%VCEI%\IntrusionDetectNet-CNN-Transformer-main\PycharmProjects\transformer_ids_model.pth`

**若仓库里已有权重：** 无需训练，启动 uvicorn 前可选：

```bat
set ETH_MODEL_PATH=C:\Users\Luyutong\Desktop\VCEI\IntrusionDetectNet-CNN-Transformer-main\PycharmProjects\transformer_ids_model.pth
```

**若需在该仓库内训练**（需已按 IntrusionDetectNet 项目准备好 `train_X/Y` 等数据，见原项目 README）：

```bat
cd /d C:\Users\Luyutong\Desktop\VCEI\IntrusionDetectNet-CNN-Transformer-main
python PycharmProjects\train.py
```

训练完成后将生成的 **`transformer_ids_model.pth`** 放到 **`PycharmProjects\`** 下，或把 **`ETH_MODEL_PATH`** 指到实际文件。

---

### C. CAN：64×9 滑动窗口 CNN（4 类，优先级最高）

**目录：** `REAL-IDS\integration\can_cnn_64x9`

```bat
cd /d C:\Users\Luyutong\Desktop\VCEI\REAL-IDS\integration\can_cnn_64x9
python preprocess.py --data-root C:\Users\Luyutong\Desktop\VCEI\CarHackData --out .\processed
python train.py --data-dir .\processed --out .\artifacts --epochs 50 --batch-size 256
```

**产物：**

- `artifacts\best_model.pth`
- `artifacts\preprocess_meta.json`（含 **`dt_max_ms`**，推理必与线上一致）
- `artifacts\eval_metrics.json`、`artifacts\classification_report.txt`、`artifacts\training_curves.png`

**仅重算测试集指标（不训练）：**

```bat
python train.py --data-dir .\processed --out .\artifacts --eval-only --batch-size 512
```

**Grad-CAM 可视化（可选）：**

```bat
python explain.py --artifacts .\artifacts --data-dir .\processed --out .\analysis_result.png
```

**启动桥时（可选显式路径）：**

```bat
set CAN_CNN64_MODEL_PATH=C:\Users\Luyutong\Desktop\VCEI\REAL-IDS\integration\can_cnn_64x9\artifacts\best_model.pth
set CAN_CNN64_META_PATH=C:\Users\Luyutong\Desktop\VCEI\REAL-IDS\integration\can_cnn_64x9\artifacts\preprocess_meta.json
```

---

### D. CAN：CarHack CNN（5 类：Normal / DoS / Fuzzy / gear / RPM）

**须在已 activate 的 `ml_bridge` venv 下：**

```bat
cd /d C:\Users\Luyutong\Desktop\VCEI\REAL-IDS\integration\ml_bridge
.venv\Scripts\activate.bat
python train_carhack.py --epochs 12
```

可选调参：`--data-root`、`--stride`、`--max-windows-per-class`、`--max-lines-per-file`（见 `train_carhack.py` 注释）。

**产物：** `ml_bridge\models\carhack_can_clf.pth`

**启动桥时（若权重不在默认位置）：**

```bat
set CARHACK_MODEL_PATH=C:\Users\Luyutong\Desktop\VCEI\REAL-IDS\integration\ml_bridge\models\carhack_can_clf.pth
```

**注意：** 若 **64×9 的 `best_model.pth` 已存在且加载成功**，桥 **不会**再用 CarHack；保留 CarHack 仍可用于对比或暂时移走 64×9 权重。

---

### E. CAN：SupCon + 线性头（5 类，仅当 64×9 与 CarHack 都未加载时）

**目录：** `%VCEI%\backend-main\backend-main\ids\supervised-main`（需已按该项目准备 **`Data/`** 等）。

依次执行：

```bat
cd /d C:\Users\Luyutong\Desktop\VCEI\backend-main\backend-main\ids\supervised-main
python train_test_split.py --data_path Data/ --car_model None --window_size 29 --strided 15 --rid 2
python train_baseline.py --data_dir Data/TFrecord_w29_s15/ --model resnet18 --save_freq 10 --window_size 29 --num_workers 8 --cosine --epochs 50 --batch_size 256 --learning_rate 0.0005 --rid 5
python train_supcon.py --data_dir Data/TFrecord_w29_s15/ --model resnet18 --save_freq 10 --window_size 29 --epochs 200 --num_workers 8 --temp 0.07 --learning_rate 0.1 --learning_rate_classifier 0.01 --cosine --epoch_start_classifier 170 --rid 3 --batch_size 512
```

在输出目录 **`save\...\models\`** 中找到成对的 **`ckpt_epoch_N.pth`** 与 **`ckpt_class_epoch_N.pth`**，记下 **N**。

**启动桥前：**

```bat
set CAN_PRETRAINED_PATH=C:\完整路径\到\含_ckpt_的\models文件夹
set CAN_CKPT=200
```

（将 **`200`** 换成你的 **N**。）

---

### F. 跨域：对齐器 + 攻击链 GraphTransformer（`attack_chain_ml`）

**依赖：** 建议已完成 **C 节** 的 `can_cnn_64x9\processed\X_train.npy` / `y_train.npy`（无则可用 `--demo-n` 仅作联调，见 `cross_domain_chain/README.md`）。

```bat
cd /d C:\Users\Luyutong\Desktop\VCEI\REAL-IDS\integration\cross_domain_chain
python train_aligner.py --can-dir ..\can_cnn_64x9\processed --epochs 25 --batch-size 256 --out .\artifacts
python chain_generator.py --can-x ..\can_cnn_64x9\processed\X_train.npy --can-y ..\can_cnn_64x9\processed\y_train.npy --aligner .\artifacts\aligner_encoders.pt --n-samples 20000 --out .\artifacts\chain_dataset.pt
python train_chain.py --dataset .\artifacts\chain_dataset.pt --epochs 40 --out .\artifacts
```

**产物：**

- `artifacts\aligner_encoders.pt`、`artifacts\aligner_loss.png`、`artifacts\aligner_latent_tsne.png`
- `artifacts\chain_dataset.pt`
- `artifacts\graph_transformer_ids.pt`、`artifacts\chain_training.png`、`artifacts\chain_confusion_matrix.png`

**启动桥前：**

```bat
set CHAIN_ALIGNER_PATH=C:\Users\Luyutong\Desktop\VCEI\REAL-IDS\integration\cross_domain_chain\artifacts\aligner_encoders.pt
set CHAIN_GRAPH_PATH=C:\Users\Luyutong\Desktop\VCEI\REAL-IDS\integration\cross_domain_chain\artifacts\graph_transformer_ids.pt
```

**`CHAIN_DT_MAX_MS`：** 当没有有效的 **`CAN_CNN64_META_PATH`** / 默认 meta 时作为 CAN 时间间隔归一化兜底（默认桥内用 **1000000**）。

---

### G. 一次性启动 ml_bridge（启用你训练好的所有模型）

在 **`ml_bridge`** 目录 **activate** 后，按需 **`set`** 下面每一项（路径改成你的真实路径）：

```bat
cd /d C:\Users\Luyutong\Desktop\VCEI\REAL-IDS\integration\ml_bridge
.venv\Scripts\activate.bat

set ETH_MODEL_PATH=C:\Users\Luyutong\Desktop\VCEI\IntrusionDetectNet-CNN-Transformer-main\PycharmProjects\transformer_ids_model.pth
set CAN_CNN64_MODEL_PATH=C:\Users\Luyutong\Desktop\VCEI\REAL-IDS\integration\can_cnn_64x9\artifacts\best_model.pth
set CAN_CNN64_META_PATH=C:\Users\Luyutong\Desktop\VCEI\REAL-IDS\integration\can_cnn_64x9\artifacts\preprocess_meta.json
set CARHACK_MODEL_PATH=C:\Users\Luyutong\Desktop\VCEI\REAL-IDS\integration\ml_bridge\models\carhack_can_clf.pth
set CAN_PRETRAINED_PATH=C:\Users\Luyutong\Desktop\VCEI\backend-main\backend-main\ids\supervised-main\save\你的实验\models
set CAN_CKPT=200
set CHAIN_ALIGNER_PATH=C:\Users\Luyutong\Desktop\VCEI\REAL-IDS\integration\cross_domain_chain\artifacts\aligner_encoders.pt
set CHAIN_GRAPH_PATH=C:\Users\Luyutong\Desktop\VCEI\REAL-IDS\integration\cross_domain_chain\artifacts\graph_transformer_ids.pt
set CHAIN_DT_MAX_MS=1000000
set ML_BRIDGE_CUDA=1

uvicorn server:app --host 127.0.0.1 --port 5055
```

浏览器打开 **`http://127.0.0.1:5055/health`** 核对：

- **`eth_model_loaded`**、**`can_cnn64_loaded`**、**`carhack_can_loaded`**、**`can_model_loaded`**（SupCon）、**`attack_chain_loaded`**
- **`can_backend`**：有 64×9 时为 **`can_cnn64`**

再按上文 **阶段三** 启动 **daemon**（`REAL_IDS_ML_BRIDGE`）与 **前端**。

---

## 附录：排错

| 现象 | 处理 |
|------|------|
| 无 `ml_fusion` | 先步骤 6 再步骤 7；daemon 必须带 `REAL_IDS_ML_BRIDGE`（勿裸双击 exe）。**PowerShell 用 `$env:REAL_IDS_ML_BRIDGE = "http://127.0.0.1:5055"`，不要用 `set`** |
| 桥地址错误 | `REAL_IDS_ML_BRIDGE` 无末尾 `/`，端口与 uvicorn 一致 |
| CAN 仍 `MODEL_UNAVAILABLE` | 查 `5055/health` 的 `carhack_can_loaded`；训练步骤 3 或设 `CARHACK_MODEL_PATH`；否则检查 SupCon 与步骤 5 |
| 权重与细节 | `integration/ml_bridge/MODELS.md`；编译 `README.md`；前端 `web-dashboard/README.md` |
| 无 `attack_chain_ml` | 未训练/未放置 `cross_domain_chain/artifacts` 下两个 `.pt`，或 `/health` 里 **`attack_chain_loaded`** 为 `false`（属正常） |
| CAN 链式滑窗分辨率低 | Daemon 侧 **`can_history`** 建议 **≥73** 帧（当前环形缓冲最多 **128** 帧） |
