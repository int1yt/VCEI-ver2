# REAL-IDS Observatory（观测台前端）

通过 **SSE** 订阅 `real_ids_daemon` 的实时事件，展示 CAN/以太网数据流、**环形缓冲示意**、规则融合告警，以及 **`ml_fusion`** 中的分类结果与完整攻击链。

## 环境要求

- **Node.js 18+**（建议 LTS）
- 已编译并可运行的 **`real_ids_daemon.exe`**（或同名可执行文件）
- 浏览器使用 **Chrome / Edge** 等（需支持 `EventSource`）

## 详细运行步骤

### 步骤 1：启动 REAL-IDS 守护进程

在 **x64 Native Tools** 或已配置好 MSVC 环境的终端中（或任意能运行 exe 的目录）：

```text
cd C:\Users\Luyutong\Desktop\VCEI\REAL-IDS\cpp\build
real_ids_daemon.exe
```

默认监听 **`http://127.0.0.1:8080`**。若需改端口：

```text
set REAL_IDS_PORT=9000
real_ids_daemon.exe
```

记下你使用的 **主机与端口**（下面要写进前端的 `.env`）。

### 步骤 2（可选）：启动 ML 融合桥

若要在页面里看到 **完整攻击链**、**IntrusionDetectNet / CAN 5 类** 等 `ml_fusion` 字段：

```text
cd C:\Users\Luyutong\Desktop\VCEI\REAL-IDS\integration\ml_bridge
pip install -r requirements.txt
uvicorn server:app --host 127.0.0.1 --port 5055
```

另开终端，**在启动 daemon 前**设置：

```text
set REAL_IDS_ML_BRIDGE=http://127.0.0.1:5055
cd C:\Users\Luyutong\Desktop\VCEI\REAL-IDS\cpp\build
real_ids_daemon.exe
```

未设置 `REAL_IDS_ML_BRIDGE` 时，页面仍可看数据流与规则告警，只是没有 `ml_fusion` 块。

### 步骤 3：安装并启动前端

```text
cd C:\Users\Luyutong\Desktop\VCEI\REAL-IDS\web-dashboard
copy .env.example .env
```

用记事本编辑 **`.env`**，将地址改成与你的 daemon 一致（**不要**在 PowerShell 里敲 `VITE_REAL_IDS_URL=...`，那是 Linux/bash 写法，会报错）：

```text
VITE_REAL_IDS_URL=http://127.0.0.1:8080
```

**Vite 启动时会自动读取 `.env`**，一般无需再设环境变量。若一定要在 PowerShell 里临时指定，语法是：

```powershell
$env:VITE_REAL_IDS_URL = "http://127.0.0.1:8080"
npm run dev
```

安装依赖并开发模式启动（任选一种）：

**方式 A（推荐，绕过全局 npm 缓存 EPERM）**

```powershell
cd C:\Users\Luyutong\Desktop\VCEI\REAL-IDS\web-dashboard
powershell -ExecutionPolicy Bypass -File .\run-dev.ps1
```

脚本会把 **`npm` 缓存放到本目录下的 `.npm-cache`**，再执行 `npm install` 和 `npx vite`。

**方式 B（手动）**

```text
npm install
npm run dev
```

若出现 **`EPERM ... node_cache`**：在 PowerShell 执行  
`npm config set cache "$env:USERPROFILE\.npm-cache-vcei" --global`  
然后重试 `npm install`；或直接使用上面的 **`run-dev.ps1`**。

终端会打印本地地址（一般为 **`http://127.0.0.1:5173`**），用浏览器打开即可。

### 步骤 3b：完全不用 npm（备用）

若 Node/npm 无法使用，可用单文件 **`observatory-standalone.html`**：

```text
cd C:\Users\Luyutong\Desktop\VCEI\REAL-IDS\web-dashboard
python -m http.server 5173
```

浏览器打开 **`http://127.0.0.1:5173/observatory-standalone.html`**（页面内可改 API 地址或 URL 加 `?api=http://127.0.0.1:8080`）。

### 步骤 4：页面内操作

1. 确认左上角 **SSE 已连接**（绿点）。
2. 点击 **「启动仿真」**。
3. 点击 **「攻击: Ethernet→CAN」** 或 **「攻击: 仅 CAN」**。
4. 在右侧告警列表中点击一条告警，查看 **规则融合**、**触发 CAN**、**以太网上下文**、**分类结果** 与 **完整攻击链**（需步骤 2 时内容更全）。

### 常见问题

| 现象 | 处理 |
|------|------|
| 提示未配置 `VITE_REAL_IDS_URL` | 确认 `web-dashboard` 目录下存在 `.env` 且变量名正确 |
| SSE 一直未连接 | 确认 daemon 已启动；防火墙放行端口；`.env` 中 URL 与 daemon 一致 |
| 跨域报错 | daemon 已对 REST/SSE 设置 CORS；若仍失败，检查是否用 `https` 页访问 `http` API（混合内容被拦） |
| 没有 `ml_fusion` | 未设 `REAL_IDS_ML_BRIDGE` 或桥未启动/超时；桥或权重失败时部分字段为 `MODEL_UNAVAILABLE` |

## 生产构建（可选）

```text
npm run build
npm run preview
```

将 `dist` 静态文件挂到任意 Web 服务器即可；仍需浏览器能访问 REAL-IDS 的 HTTP/SSE 地址（或通过同源反代）。
