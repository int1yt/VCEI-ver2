# 让深度学习分类生效（告别 MODEL_UNAVAILABLE）

当前输出里 **`MODEL_UNAVAILABLE` / `source: stub`** 表示 **对应 PyTorch 权重没有成功加载**。桥接仍会生成 **攻击链** 和 **REAL-IDS 规则文案**；要出现 **BENIGN/ANOMALY** 与 **DoS/Fuzzy/…**，需要按下面放置文件并设置环境变量。

---

## 1. IntrusionDetectNet（以太网二分类）

1. 在 **`IntrusionDetectNet-CNN-Transformer-main/PycharmProjects/`** 下按原项目流程训练，生成 **`transformer_ids_model.pth`**（与 `evaluate.py` 里 `torch.load` 一致）。  
2. 或把已有权重复制到上述路径。  
3. 若文件在别处，启动 uvicorn **之前**设置：

```text
set ETH_MODEL_PATH=C:\完整路径\transformer_ids_model.pth
```

4. 重启 **ml_bridge** 和 **daemon**（桥在进程内缓存模型单例，改路径后必须重启 uvicorn）。

**注意：** 推理输入为 **`(10, 80)`** 且应与训练时 **StandardScaler** 一致；当前从 REAL-IDS 仿真拼的 10×80 为占位，仅便于联调，与论文数据不一致时准确率无意义。

---

## 2. CAN 5 类（优先：CarHackData CNN）

桥会**先**尝试加载 **`integration/ml_bridge/models/carhack_can_clf.pth`**（可用环境变量 **`CARHACK_MODEL_PATH`** 覆盖）。若该文件存在且加载成功，CAN 分类使用 **CarHackData** 上训练的 CNN，**不再**走下面的 SupCon。

**训练（在 `integration/ml_bridge` 下，已激活 venv）：**

```text
python train_carhack.py --epochs 12
```

数据默认读 **`VCEI/CarHackData/`**（`normal_run_data.txt`、`DoS_dataset.csv`、`Fuzzy_dataset.csv`、`gear_dataset.csv`、`RPM_dataset.csv`）。可调 `--max-windows-per-class`、`--stride`、`--data-root`。

训练完成后重启 uvicorn；`/health` 中应 **`carhack_can_loaded: true`**，`can_backend` 为 **`carhack_cnn`**。

---

## 2b. CAN 5 类（备选：backend supervised-main SupCon）

**仅当** 未加载 CarHack 权重时，才使用 SupCon 检查点。

1. 在 **`backend-main/backend-main/ids/supervised-main/`** 按 README 训练 SupCon + 分类头，得到保存目录，其中需包含例如：  
   - `ckpt_epoch_200.pth`（或你训练的 epoch）  
   - `ckpt_class_epoch_200.pth`  
2. 启动桥之前设置（**目录**不是单个文件）：

```text
set CAN_PRETRAINED_PATH=C:\完整路径\到\models 目录
set CAN_CKPT=200
```

`CAN_CKPT` 必须与文件名里的 epoch 数字一致。

3. 重启 uvicorn。

若加载失败，控制台会出现 `[CanSupconInfer] load failed: ...`（依赖、路径、CUDA 等）。

---

## 3. 自检

浏览器或 curl：

```text
http://127.0.0.1:5055/health
```

应看到 **`eth_model_loaded`** 按需为 `true`；CAN 若走 CarHack：**`carhack_can_loaded: true`**；若走 SupCon：**`can_model_loaded: true`**（`/health` 里 **`can_backend`** 会标明当前后端）。

---

## 4. 未加载模型时的行为（仿真友好）

若仍未配置权重，桥会对 **REAL-IDS 仿真里的 `isAttack` / `synthetic_attack_flag`** 做 **启发式** 以太/CAN 提示（`source: heuristic_real_ids_flags`），**不是** IntrusionDetectNet 或 SupCon 的真实输出；便于大屏演示，勿当作实车判定依据。
