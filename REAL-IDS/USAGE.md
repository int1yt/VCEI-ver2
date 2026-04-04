# REAL-IDS 使用步骤（按顺序）

**路径约定：** 工程根目录 `C:\Users\Luyutong\Desktop\VCEI`。下文凡写 `VCEI`、`REAL-IDS` 均相对该根目录。

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

**顺序说明：** 先有权重文件，再在阶段三里启动 uvicorn；CAN 优先使用 CarHack，没有 CarHack 再用 SupCon。

### 步骤 3 — CAN：CarHack（推荐）

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

---

## 阶段三：每次跑「桥 + daemon + 界面」（固定顺序）

### 步骤 6 — 启动 ml_bridge（必须第一个启动）

1. 打开 CMD：

```bat
cd /d C:\Users\Luyutong\Desktop\VCEI\REAL-IDS\integration\ml_bridge
.venv\Scripts\activate.bat
```

2.（可选）按阶段二设置权重路径：

```bat
set ETH_MODEL_PATH=C:\路径\transformer_ids_model.pth
set CARHACK_MODEL_PATH=C:\路径\carhack_can_clf.pth
set CAN_PRETRAINED_PATH=C:\路径\models
set CAN_CKPT=200
set ML_BRIDGE_CUDA=1
```

3. 启动服务：

```bat
uvicorn server:app --host 127.0.0.1 --port 5055
```

4. 浏览器打开 **`http://127.0.0.1:5055/health`**，确认 `status` 为 **`ok`**，并查看 **`carhack_can_loaded` / `eth_model_loaded` / `can_model_loaded`** 是否符合预期。  
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
powershell -ExecutionPolicy Bypass -File .\run-dev.ps1
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

3. 告警 JSON 中应有 **`ml_fusion`**；CarHack 生效时 **`can_ml.source`** 为 **`carhack_cnn`**。
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
| `ETH_MODEL_PATH` | 启动 uvicorn 前 | 以太模型 `.pth` |
| `CARHACK_MODEL_PATH` | 启动 uvicorn 前 | CarHack 权重；不设则用 `ml_bridge\models\carhack_can_clf.pth` |
| `CAN_PRETRAINED_PATH` / `CAN_CKPT` | 启动 uvicorn 前 | SupCon（CarHack 未加载时） |
| `ML_BRIDGE_CUDA` | 启动 uvicorn 前 | 设为 `1` 尝试 GPU 推理 |
| `VITE_REAL_IDS_URL` | 写入 `web-dashboard\.env` | 前端指向 daemon |

---

## 附录：排错

| 现象 | 处理 |
|------|------|
| 无 `ml_fusion` | 先步骤 6 再步骤 7；daemon 必须带 `REAL_IDS_ML_BRIDGE`（勿裸双击 exe）。**PowerShell 用 `$env:REAL_IDS_ML_BRIDGE = "http://127.0.0.1:5055"`，不要用 `set`** |
| 桥地址错误 | `REAL_IDS_ML_BRIDGE` 无末尾 `/`，端口与 uvicorn 一致 |
| CAN 仍 `MODEL_UNAVAILABLE` | 查 `5055/health` 的 `carhack_can_loaded`；训练步骤 3 或设 `CARHACK_MODEL_PATH`；否则检查 SupCon 与步骤 5 |
| 权重与细节 | `integration/ml_bridge/MODELS.md`；编译 `README.md`；前端 `web-dashboard/README.md` |
