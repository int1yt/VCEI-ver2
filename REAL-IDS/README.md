# REAL-IDS

可部署的 **C++17** 车载 IDS 核心（CAN 时钟偏移检测 + 以太网环形缓冲关联），并附带 **`real_ids_daemon`**：用 **HTTP + SSE（Server-Sent Events）** 向 IDS 大屏推送与原版 autoids 模拟器兼容的事件形态。

## 构建

需要 **CMake 3.16+** 与 **C++17** 编译器（MSVC、GCC、Clang 均可）。

**注意：** `CMakeLists.txt` 在仓库的 **`REAL-IDS/cpp`** 下，不是在 `VCEI` 根目录。应先：

```bash
cd REAL-IDS/cpp
cmake -B build
cmake --build build --config Release
```

### Windows：`No CMAKE_CXX_COMPILER could be found`

在 **普通 PowerShell / CMD** 里直接运行上面的命令时，环境变量里**没有 MSVC**（没有 `cl.exe`），CMake 就找不到 C++ 编译器；后面 `MSBUILD ... ALL_BUILD.vcxproj 不存在` 是因为**配置阶段已经失败**，没有生成工程。

任选其一即可：

1. **推荐（已装好 CMake 时）**  
   在资源管理器中进入 `REAL-IDS\cpp`，双击（或在 CMD 里运行）**`configure_vs2022.bat`**。  
   脚本会先执行 `vcvars64.bat`，再用 **NMake** 生成并编译，不依赖“VS 开发者命令行”里手动敲命令。

2. **用开始菜单里的 VS 环境**  
   打开 **“Developer PowerShell for VS 2022”** 或 **“x64 Native Tools Command Prompt for VS 2022”**，再执行：
   ```text
   cd 桌面\VCEI\REAL-IDS\cpp
   cmake -B build -G "NMake Makefiles" -DCMAKE_BUILD_TYPE=Release
   cmake --build build
   ```
   （若坚持用 `Visual Studio 17 2022` 生成器仍报错，可优先用上面的 **NMake** 两行。）

3. **用 Visual Studio 图形界面**  
   **文件 → 打开 → 文件夹** → 选 `REAL-IDS\cpp`，由 VS 内置 CMake 配置并生成（无需在错误目录执行 `cmake`）。

若编译阶段报错 **找不到 `crtdbg.h`**：打开 **Visual Studio Installer** → 修改本机 VS → 勾选 **Windows 10/11 SDK**（以及“使用 C++ 的桌面开发”工作负载）→ 安装后重试。

**已用 `configure_vs2022.bat`（NMake）编过以后，不要在普通 PowerShell 里再单独执行 `cmake -B build`。** 当前 `build` 里的生成器是 **NMake**，依赖 `nmake.exe` 在 PATH 中（只有运行过 `vcvars64.bat` 的终端才有）。若出现 `nmake '-?' ... no such file or directory`，请继续用 **`configure_vs2022.bat`** 重新配置/编译，或打开 **“x64 Native Tools Command Prompt for VS 2022”** 再执行 cmake。

### Windows：`cmake` 不是内部或外部命令

说明 **CMake 未安装**或**未加入 PATH**。任选其一：

1. **用 winget 安装（推荐）**  
   在 **新的** PowerShell 或 CMD 中执行：
   ```text
   winget install -e --id Kitware.CMake
   ```
   安装完成后**关掉终端再打开**，再执行 `cmake -B build`。

2. **不装 CMake，用 Visual Studio 打开 CMake 工程**  
   启动 Visual Studio → **打开本地文件夹** → 选择 `REAL-IDS\cpp`。VS 会用内置 CMake 配置/生成，在菜单里选 **生成** 即可。

3. **不装 CMake，直接调用 MSVC（批处理）**  
   在已安装 **“使用 C++ 的桌面开发”** 和 **Windows SDK** 的前提下，双击或在 `cpp` 目录执行：
   ```text
   build_msvc.bat
   ```
   成功时生成 `cpp\build\real_ids_daemon.exe`。  
   若报错找不到 `crtdbg.h`、`io.h` 等，请打开 **Visual Studio Installer**，给本机 VS 勾选 **Windows 10/11 SDK**，安装后重试。

产物：

- 静态库 `real_ids`：可单独链接进网关固件 / Linux 可执行文件。
- `real_ids_daemon`：带仿真流量与 API 的演示进程（默认端口 **8080**）。

### 依赖（已随仓库提供）

- `cpp/third_party/httplib.h`（MIT）
- `cpp/third_party/nlohmann/json.hpp`（MIT）

## 运行

```bash
# 可选：端口（默认 8080）
set REAL_IDS_PORT=8080
# 可选：simulation 与 autoids 一致；production 仅按 CAN 异常告警（不依赖 synthetic 标记）
set REAL_IDS_MODE=simulation
real_ids_daemon
```

Linux/macOS 使用 `export REAL_IDS_MODE=production` 等形式。

## 大屏 / 外部系统接口

所有 JSON 接口均带 **CORS**（`Access-Control-Allow-Origin: *`），便于浏览器大屏跨域访问。

### REST（控制与静态指标）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` 或 `/api/v1/health` | 存活探测 |
| GET | `/api/stats` 或 `/api/v1/stats` | 与 autoids 类似的演示指标；`v1` 多返回 `subscribers`（SSE 客户端数） |
| POST | `/api/simulation/start`、`/api/v1/simulation/start` | 启动仿真流量 |
| POST | `/api/simulation/stop`、`/api/v1/simulation/stop` | 停止仿真并清空待注入计数 |
| POST | `/api/simulation/attack`、`/api/v1/simulation/attack` | JSON body：`{"type":"ethernet-can"}` 或 `{"type":"can-internal"}`（与 autoids 按钮一致） |

### SSE 实时事件（推荐大屏使用）

**GET** `/api/v1/stream`  

- `Content-Type: text/event-stream`
- 每条消息为 **一行 JSON**，外层格式：

```json
{"event":"<名称>","payload":{...}}
```

| `event` | `payload` 说明 |
|---------|----------------|
| `can-packet` | 与 autoids 一致：`id`, `timestamp`, `data`, `isAttack` |
| `eth-packet` | `id`, `timestamp`, `srcIp`, `dstIp`, `protocol`, `length`, `isAttack` |
| `alert` | `id`, `timestamp`, `canPacket`, `ethernetContext[]`, `classification`, `confidence` |
| `status` | `{ "running": true/false }` |
| `attack_launched` | `{ "type": "ethernet-can" \| "can-internal" }` |

约 **25 秒**无事件时会发送 SSE 注释行 `: keepalive`，用于穿透部分代理。

### 浏览器示例（EventSource）

```javascript
const es = new EventSource('http://127.0.0.1:8080/api/v1/stream');
es.onmessage = (e) => {
  const msg = JSON.parse(e.data);
  if (msg.event === 'alert') {
    console.log('ALERT', msg.payload);
  }
};
```

若大屏与 daemon 不同源，请确保通过 **https** 或允许的 **http** 源访问；生产环境建议反代（Nginx）并限制来源。

## 接入真实总线

仿真由 `daemon/main.cpp` 中的线程产生；**量产路径**为：

1. 链接静态库 **`real_ids`**。
2. 实现 `ICanIngress` / `IEthIngress`（见 `include/real_ids/ingress.hpp`），在收帧线程中调用 `IdsEngine::ingest_can` / `ingest_eth`。
3. 设置 `REAL_IDS_MODE=production` 或代码中构造 `EngineMode::Production`：按 **CAN 时序异常** 告警，融合分类不依赖注入用的 `synthetic_attack_flag`。（当前 `EthernetPacket::synthetic_attack_flag` 仅为仿真占位；实车需在以太侧接入真实异常判定后再写入或扩展字段。）
4. 用 `SystemTimeSource` 或自实现 `TimeSource` 对接 gPTP/PHC。

`IdsEngine::set_callbacks` 可把告警送到你的日志、IPC 或再转发给本 daemon 同构的 SSE 层（需自行桥接）。
