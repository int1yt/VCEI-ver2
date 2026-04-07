from __future__ import annotations

import csv
import json
import math
import random
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import median
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = Path(__file__).resolve().parent


@dataclass
class CarHackStats:
    name: str
    path: Path
    rows: int
    unique_ids: int
    timestamp_min: float | None
    timestamp_max: float | None
    dt_min_ms: float | None
    dt_median_ms: float | None
    dt_p95_ms: float | None
    dt_max_ms: float | None
    top_ids: list[tuple[str, int]]
    dlc_distribution: dict[str, int]


def percentile(sorted_values: list[float], q: float) -> float | None:
    if not sorted_values:
        return None
    if q <= 0:
        return sorted_values[0]
    if q >= 1:
        return sorted_values[-1]
    pos = (len(sorted_values) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return sorted_values[lo]
    frac = pos - lo
    return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac


def analyze_carhack_file(path: Path) -> CarHackStats:
    id_counter: Counter[str] = Counter()
    dlc_counter: Counter[str] = Counter()
    dt_reservoir: list[float] = []
    dt_count = 0
    reservoir_size = 200000
    last_ts: float | None = None
    ts_min: float | None = None
    ts_max: float | None = None
    rows = 0

    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 3:
                continue
            rows += 1
            try:
                ts = float(row[0].strip())
            except ValueError:
                continue
            can_id = row[1].strip().lower()
            dlc = row[2].strip()

            id_counter[can_id] += 1
            dlc_counter[dlc] += 1

            if ts_min is None or ts < ts_min:
                ts_min = ts
            if ts_max is None or ts > ts_max:
                ts_max = ts

            if last_ts is not None:
                dt_ms = max((ts - last_ts) * 1000.0, 0.0)
                dt_count += 1
                if len(dt_reservoir) < reservoir_size:
                    dt_reservoir.append(dt_ms)
                else:
                    # Reservoir sampling for stable quantile estimates with bounded memory.
                    j = random.randint(0, dt_count - 1)
                    if j < reservoir_size:
                        dt_reservoir[j] = dt_ms
            last_ts = ts

    dt_reservoir.sort()
    return CarHackStats(
        name=path.stem,
        path=path,
        rows=rows,
        unique_ids=len(id_counter),
        timestamp_min=ts_min,
        timestamp_max=ts_max,
        dt_min_ms=dt_reservoir[0] if dt_reservoir else None,
        dt_median_ms=median(dt_reservoir) if dt_reservoir else None,
        dt_p95_ms=percentile(dt_reservoir, 0.95),
        dt_max_ms=dt_reservoir[-1] if dt_reservoir else None,
        top_ids=id_counter.most_common(10),
        dlc_distribution=dict(sorted(dlc_counter.items(), key=lambda x: x[0])),
    )


def analyze_feature_csv(path: Path) -> dict:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, skipinitialspace=True)
        labels: Counter[str] = Counter()
        protocols: Counter[str] = Counter()
        flow_duration = []
        for row in reader:
            if not row:
                continue
            label = (row.get("Label") or "").strip()
            protocol = (row.get("Protocol") or "").strip()
            if label:
                labels[label] += 1
            if protocol:
                protocols[protocol] += 1
            try:
                flow_duration.append(float((row.get("Flow Duration") or "0").strip()))
            except ValueError:
                pass

    flow_duration.sort()
    total = sum(labels.values())
    return {
        "file": str(path.relative_to(ROOT)),
        "rows": total,
        "label_distribution": dict(labels),
        "protocol_distribution": dict(protocols),
        "flow_duration_min": flow_duration[0] if flow_duration else None,
        "flow_duration_median": median(flow_duration) if flow_duration else None,
        "flow_duration_p95": percentile(flow_duration, 0.95),
        "flow_duration_max": flow_duration[-1] if flow_duration else None,
    }


def ts_to_text(ts: float | None) -> str:
    if ts is None:
        return "-"
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def num_text(v: float | int | None, digits: int = 3) -> str:
    if v is None:
        return "-"
    if isinstance(v, int):
        return f"{v:,}"
    return f"{v:,.{digits}f}"


def generate_figures(carhack_stats: list[CarHackStats], feature_stats: list[dict]) -> list[str]:
    fig_dir = OUT_DIR / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    generated: list[str] = []

    # Figure 1: CarHack sample counts
    plt.figure(figsize=(8, 4.6))
    names = [s.name.replace("_dataset", "") for s in carhack_stats]
    counts = [s.rows for s in carhack_stats]
    bars = plt.bar(names, counts, color=["#4c78a8", "#f58518", "#54a24b", "#e45756"])
    plt.title("CarHackData Subset Sample Counts")
    plt.ylabel("Rows")
    plt.grid(axis="y", linestyle="--", alpha=0.3)
    for b, c in zip(bars, counts):
        plt.text(b.get_x() + b.get_width() / 2, b.get_height(), f"{c/1e6:.2f}M", ha="center", va="bottom", fontsize=9)
    plt.tight_layout()
    p1 = fig_dir / "fig01_carhack_rows.png"
    plt.savefig(p1, dpi=160)
    plt.close()
    generated.append(p1.relative_to(OUT_DIR).as_posix())

    # Figure 2: CarHack unique CAN IDs
    plt.figure(figsize=(8, 4.6))
    id_counts = [s.unique_ids for s in carhack_stats]
    bars = plt.bar(names, id_counts, color=["#72b7b2", "#b279a2", "#ff9da6", "#9d755d"])
    plt.title("CarHackData Unique CAN IDs")
    plt.ylabel("Unique CAN IDs")
    plt.grid(axis="y", linestyle="--", alpha=0.3)
    for b, c in zip(bars, id_counts):
        plt.text(b.get_x() + b.get_width() / 2, b.get_height(), f"{c}", ha="center", va="bottom", fontsize=9)
    plt.tight_layout()
    p2 = fig_dir / "fig02_carhack_unique_ids.png"
    plt.savefig(p2, dpi=160)
    plt.close()
    generated.append(p2.relative_to(OUT_DIR).as_posix())

    # Figure 3: data_8000 label distributions
    plt.figure(figsize=(9, 4.8))
    ax1 = plt.subplot(1, 2, 1)
    normal_labels = feature_stats[0]["label_distribution"]
    ax1.pie(normal_labels.values(), labels=normal_labels.keys(), autopct="%1.1f%%", startangle=90)
    ax1.set_title("data_8000_normal Labels")
    ax2 = plt.subplot(1, 2, 2)
    abnormal_labels = feature_stats[1]["label_distribution"]
    ax2.pie(abnormal_labels.values(), labels=abnormal_labels.keys(), autopct="%1.1f%%", startangle=90)
    ax2.set_title("data_8000_abnormal Labels")
    plt.tight_layout()
    p3 = fig_dir / "fig03_data8000_label_distribution.png"
    plt.savefig(p3, dpi=160)
    plt.close()
    generated.append(p3.relative_to(OUT_DIR).as_posix())

    # Figure 4: data_8000 protocol distributions
    plt.figure(figsize=(9, 4.8))
    keys = sorted(set(feature_stats[0]["protocol_distribution"].keys()) | set(feature_stats[1]["protocol_distribution"].keys()))
    normal_vals = [feature_stats[0]["protocol_distribution"].get(k, 0) for k in keys]
    abnormal_vals = [feature_stats[1]["protocol_distribution"].get(k, 0) for k in keys]
    x = list(range(len(keys)))
    width = 0.38
    plt.bar([i - width / 2 for i in x], normal_vals, width=width, label="normal")
    plt.bar([i + width / 2 for i in x], abnormal_vals, width=width, label="abnormal")
    plt.xticks(x, keys)
    plt.title("data_8000 Protocol Distribution")
    plt.xlabel("Protocol")
    plt.ylabel("Rows")
    plt.grid(axis="y", linestyle="--", alpha=0.3)
    plt.legend()
    plt.tight_layout()
    p4 = fig_dir / "fig04_data8000_protocol_distribution.png"
    plt.savefig(p4, dpi=160)
    plt.close()
    generated.append(p4.relative_to(OUT_DIR).as_posix())

    return generated


def write_markdown(carhack_stats: list[CarHackStats], feature_stats: list[dict], figure_paths: list[str]) -> None:
    md_path = OUT_DIR / "dataset_section.md"
    lines: list[str] = []
    lines.append("# 数据集章节（可直接用于论文）")
    lines.append("")
    lines.append("## 1. 数据来源与组成")
    lines.append("")
    lines.append("- **CarHackData**：包含 `DoS`、`Fuzzy`、`gear`、`RPM` 四个原始 CAN 报文序列文件。")
    lines.append("- **流特征子集**：`data_8000_normal.csv` 与 `data_8000_abnormal.csv`，用于构建带标签的特征级分类样本。")
    lines.append("")
    lines.append("## 2. CarHackData 统计概览")
    lines.append("")
    lines.append("| 子集 | 样本行数 | 唯一 CAN ID 数 | 起止时间 | dt中位数(ms) | dt P95(ms) | dt最大(ms) |")
    lines.append("|---|---:|---:|---|---:|---:|---:|")
    for s in carhack_stats:
        tspan = f"{ts_to_text(s.timestamp_min)} ~ {ts_to_text(s.timestamp_max)}"
        lines.append(
            f"| {s.name} | {s.rows:,} | {s.unique_ids} | {tspan} | "
            f"{num_text(s.dt_median_ms)} | {num_text(s.dt_p95_ms)} | {num_text(s.dt_max_ms)} |"
        )
    lines.append("")
    lines.append("### 2.1 各子集高频 CAN ID（Top10）")
    lines.append("")
    for s in carhack_stats:
        lines.append(f"**{s.name}**")
        lines.append("")
        for can_id, cnt in s.top_ids:
            lines.append(f"- `{can_id}`: {cnt:,}")
        lines.append("")
    lines.append("### 2.2 DLC 分布")
    lines.append("")
    for s in carhack_stats:
        dlc_text = ", ".join([f"DLC={k}: {v:,}" for k, v in s.dlc_distribution.items()])
        lines.append(f"- **{s.name}**：{dlc_text}")
    lines.append("")
    lines.append("## 3. 流特征数据（data_8000）统计")
    lines.append("")
    for fs in feature_stats:
        lines.append(f"### 3.{feature_stats.index(fs)+1} `{Path(fs['file']).name}`")
        lines.append("")
        lines.append(f"- 样本总数：{fs['rows']:,}")
        lines.append(f"- 标签分布：{json.dumps(fs['label_distribution'], ensure_ascii=False)}")
        lines.append(f"- 协议分布：{json.dumps(fs['protocol_distribution'], ensure_ascii=False)}")
        lines.append(
            "- Flow Duration 统计："
            f"min={num_text(fs['flow_duration_min'])}, "
            f"median={num_text(fs['flow_duration_median'])}, "
            f"p95={num_text(fs['flow_duration_p95'])}, "
            f"max={num_text(fs['flow_duration_max'])}"
        )
        lines.append("")
    lines.append("## 4. 论文可直接引用文字（数据集小节）")
    lines.append("")
    lines.append(
        "本文实验使用两类数据源：其一为 CarHackData 原始 CAN 报文数据，覆盖 DoS、Fuzzy、"
        "gear 与 RPM 场景；其二为流特征级数据子集 `data_8000_normal.csv` 与 "
        "`data_8000_abnormal.csv`。在 CarHackData 中，各子集均包含百万级报文行，且呈现出稳定的 "
        "CAN ID 与 DLC 结构分布；在 data_8000 子集中，正常数据与异常数据在标签、协议与流持续时间统计上"
        "存在明显差异。该双源数据配置同时支持“原始报文级时序建模”和“特征级监督分类”两类任务，能够为"
        "车载入侵检测模型提供从底层报文行为到上层流量语义的互补证据。"
    )
    lines.append("")
    lines.append("## 5. 图片与文字介绍（可直接用于论文）")
    lines.append("")
    lines.append("### 图1：CarHackData子集样本量")
    lines.append("")
    lines.append(f"![CarHackData子集样本量]({figure_paths[0]})")
    lines.append("")
    lines.append("该图展示了 CarHackData 四个子集的样本规模，均达到百万量级，说明该数据源能够支撑高覆盖度的时序学习与鲁棒性评估。")
    lines.append("")
    lines.append("### 图2：CarHackData唯一CAN ID数量")
    lines.append("")
    lines.append(f"![CarHackData唯一CAN ID数量]({figure_paths[1]})")
    lines.append("")
    lines.append("该图体现了不同攻击子集的 ID 空间复杂度差异，其中 Fuzzy 子集的 ID 多样性明显更高，适合评估模型在高扰动注入场景下的泛化能力。")
    lines.append("")
    lines.append("### 图3：data_8000标签分布")
    lines.append("")
    lines.append(f"![data_8000标签分布]({figure_paths[2]})")
    lines.append("")
    lines.append("该图显示 normal 子集为纯 BENIGN 样本，而 abnormal 子集由 slowloris 与 Slowhttptest 构成，反映了本实验在正常/异常两端具有明确监督信号。")
    lines.append("")
    lines.append("### 图4：data_8000协议分布对比")
    lines.append("")
    lines.append(f"![data_8000协议分布对比]({figure_paths[3]})")
    lines.append("")
    lines.append("该图反映 normal 子集中同时包含 TCP/UDP（少量协议0），abnormal 子集以 TCP 为主，说明异常流量在协议层呈现更集中模式。")
    lines.append("")
    lines.append("## 6. 复现实验")
    lines.append("")
    lines.append("```bash")
    lines.append("python paper-figures/dataset-analysis/analyze_datasets.py")
    lines.append("```")
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    carhack_files = [
        ROOT / "CarHackData/DoS_dataset.csv",
        ROOT / "CarHackData/Fuzzy_dataset.csv",
        ROOT / "CarHackData/gear_dataset.csv",
        ROOT / "CarHackData/RPM_dataset.csv",
    ]
    feature_files = [
        ROOT / "IntrusionDetectNet-CNN-Transformer-main/PycharmProjects/data_8000_normal.csv",
        ROOT / "IntrusionDetectNet-CNN-Transformer-main/PycharmProjects/data_8000_abnormal.csv",
    ]

    carhack_stats = [analyze_carhack_file(p) for p in carhack_files]
    feature_stats = [analyze_feature_csv(p) for p in feature_files]

    output = {
        "carhack": [
            {
                "name": s.name,
                "file": str(s.path.relative_to(ROOT)),
                "rows": s.rows,
                "unique_ids": s.unique_ids,
                "timestamp_min": s.timestamp_min,
                "timestamp_max": s.timestamp_max,
                "dt_min_ms": s.dt_min_ms,
                "dt_median_ms": s.dt_median_ms,
                "dt_p95_ms": s.dt_p95_ms,
                "dt_max_ms": s.dt_max_ms,
                "top_ids": s.top_ids,
                "dlc_distribution": s.dlc_distribution,
            }
            for s in carhack_stats
        ],
        "data_8000": feature_stats,
    }

    json_path = OUT_DIR / "dataset_stats.json"
    json_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    figure_paths = generate_figures(carhack_stats, feature_stats)
    write_markdown(carhack_stats, feature_stats, figure_paths)
    print(f"[OK] Wrote: {json_path}")
    print(f"[OK] Wrote: {OUT_DIR / 'dataset_section.md'}")
    print(f"[OK] Wrote figures: {', '.join(figure_paths)}")


if __name__ == "__main__":
    main()
