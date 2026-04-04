# REAL-IDS 集成测试

- **正确性**：daemon `/api/v1/*`、ml_bridge `/health` 与 `/v1/enrich`（空负载、满 CAN 窗口、`flow_sequence_10x80`）。
- **延迟**：对上述路径做多次采样，输出 mean / min / p50 / p95 / p99 / max。

## 运行

先启动 **uvicorn**（5055）与 **real_ids_daemon**（8080，且已设置 `REAL_IDS_ML_BRIDGE` 若需端到端告警）。

```bat
cd REAL-IDS\tests\integration
pip install -r requirements.txt
python run_tests.py
```

结果目录 **`results/`**（git 忽略）：

- `summary.json` — 机器可读
- `summary.txt` — 人类可读

## 参数

| 参数 | 默认 | 说明 |
|------|------|------|
| `--daemon-url` | `http://127.0.0.1:8080` | |
| `--bridge-url` | `http://127.0.0.1:5055` | |
| `--latency-iterations` | 30 | 每场景采样次数 |
| `--latency-warmup` | 5 | 预热（不计入统计） |
| `--timeout` | 60 | 单次 HTTP 超时（秒） |
| `--output` | `./results` | 报告目录 |
| `--strict` | off | 服务不可达记为 **fail**（默认 **skip**） |
| `--no-latency` | off | 只做正确性 |
| `--carhack-data` | `<VCEI>/CarHackData` | 离线评估用数据目录 |
| `--classification-windows` | 400 | 每类最多采样窗口数（越大越慢、越稳） |
| `--classification-stride` | 5 | 与 `train_carhack.py` 一致 |
| `--no-classification` | off | 不跑 **CarHack CNN 分类正确率** |
| `--skew-iterations` | 50000 | 时钟倾斜 `detect()` 微基准次数 |
| `--skew-warmup` | 5000 | 预热次数 |
| `--skew-threshold-ms` | 15.0 | 与 C++ `CanClockSkewIds` 默认一致 |
| `--no-skew-bench` | off | 不跑 **时钟倾斜算法延迟** |

**分类正确率（`classification` 段）：** 在本地用 **`integration/ml_bridge/models/carhack_can_clf.pth`** 对 CarHackData 滑窗推理，输出 overall **accuracy**、**per_class**、**confusion_matrix**。需已安装与 **`ml_bridge` 相同**的 PyTorch 等依赖（建议在 `ml_bridge` 的 venv 里跑本脚本）。**不包含**以太 IntrusionDetectNet（需自带标签数据集）。

**时钟倾斜延迟（`clock_skew` 段）：** Python 参考实现 **`clock_skew_ref.py`**，与 **`cpp/src/can_ids.cpp`** 逻辑一致；输出单次 **`detect()`** 的 **mean/p95/p99 ns**（非 HTTP、非 daemon 进程内 C++ 实测，用于算法级对比）。

退出码：存在 **fail** 时为 `1`。

## 一直 skip

1. 看 **`results/summary.txt`** 里 **`probe_daemon` / `probe_bridge`** 行，或运行 **`python run_tests.py -v`**。  
2. **`HTTP_PROXY` / `HTTPS_PROXY`**：脚本已设 **`trust_env=False`**，不再走系统代理；若仍失败，检查端口是否被其它配置占用。  
3. URL 请用 **`http://127.0.0.1:8080`**，不要用 **`http://0.0.0.0:8080`**（本机连接目标不能写 0.0.0.0）。  
4. 端口与 **`REAL_IDS_PORT`**、uvicorn **`--port`** 一致；不一致时用 **`--daemon-url`** / **`--bridge-url`**。
