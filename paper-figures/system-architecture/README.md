# 系统架构图（论文用）

本目录仅新增论文绘图文件，不影响项目已有代码。

## 文件

- `real_ids_architecture.tex`：真实植入系统与对应 ML 模块的系统架构图（TikZ）。

## 编译方式

在当前目录执行：

```bash
latexmk -xelatex real_ids_architecture.tex
```

或使用：

```bash
xelatex real_ids_architecture.tex
```

编译后得到 `real_ids_architecture.pdf`。
