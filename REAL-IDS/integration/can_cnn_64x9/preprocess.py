r"""
Load CarHack-style CAN CSV/TXT → sliding windows 64×9 → .npy + preprocess_meta.json

CSV columns: Timestamp, CAN ID, DLC, Data0..Data7 (hex). TXT: CarHack normal_run_data format.

Labels (4 classes): Normal, DoS, Fuzzy, Spoofing
  - gear_dataset + RPM_dataset → Spoofing (in-vehicle spoofing / RPM anomaly bucket)

Usage:
  cd REAL-IDS/integration/can_cnn_64x9
  python preprocess.py --data-root ../../../CarHackData --out ./processed
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sklearn.model_selection import train_test_split
from tqdm import tqdm

WINDOW = 64
STRIDE = 32

_RE_TXT = re.compile(
    r"Timestamp:\s*([0-9.]+).*?ID:\s*([0-9a-fA-F]+).*?DLC:\s*(\d+)\s+((?:[0-9a-fA-F]{2}\s*)+)",
    re.IGNORECASE | re.DOTALL,
)

# filename fragment -> semantic label name
FILE_TO_LABEL: List[Tuple[str, str]] = [
    ("normal_run_data", "Normal"),
    ("DoS_dataset", "DoS"),
    ("Fuzzy_dataset", "Fuzzy"),
    ("gear_dataset", "Spoofing"),
    ("RPM_dataset", "Spoofing"),
]

CLASS_NAMES = ["Normal", "DoS", "Fuzzy", "Spoofing"]


def _parse_csv_line(line: str) -> Optional[Tuple[float, List[int]]]:
    line = line.strip()
    if not line:
        return None
    parts = line.split(",")
    if len(parts) < 4:
        return None
    try:
        ts = float(parts[0])
        dlc = int(parts[2])
    except (ValueError, IndexError):
        return None
    need = 3 + dlc
    if len(parts) < need:
        return None
    bytes_hex = [parts[3 + i].strip() for i in range(dlc)]
    data8 = [0] * 8
    for i in range(min(8, len(bytes_hex))):
        try:
            data8[i] = int(bytes_hex[i], 16) & 0xFF
        except ValueError:
            data8[i] = 0
    return ts, data8


def _parse_txt_line(line: str) -> Optional[Tuple[float, List[int]]]:
    m = _RE_TXT.search(line)
    if not m:
        return None
    ts_s, _cid, dlc_s, data_s = m.groups()
    dlc = int(dlc_s)
    hexes = [h for h in data_s.split() if h]
    data8 = [0] * 8
    for i in range(min(8, dlc, len(hexes))):
        try:
            data8[i] = int(hexes[i], 16) & 0xFF
        except ValueError:
            data8[i] = 0
    return float(ts_s), data8


def _label_for_path(path: Path) -> Optional[str]:
    stem = path.stem.lower()
    name = path.name
    for key, lab in FILE_TO_LABEL:
        if key.lower() in name.lower() or key.lower() in stem:
            return lab
    return None


def _file_rows(path: Path) -> List[Tuple[float, List[int]]]:
    rows: List[Tuple[float, List[int]]] = []
    is_txt = path.suffix.lower() == ".txt"
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            p = _parse_txt_line(line) if is_txt else _parse_csv_line(line)
            if p:
                rows.append(p)
    rows.sort(key=lambda x: x[0])
    return rows


def _windows_from_rows(rows: List[Tuple[float, List[int]]], label_id: int) -> Tuple[List[np.ndarray], List[int]]:
    xs: List[np.ndarray] = []
    ys: List[int] = []
    n = len(rows)
    if n < WINDOW:
        return xs, ys
    for start in range(0, n - WINDOW + 1, STRIDE):
        chunk = rows[start : start + WINDOW]
        mat = np.zeros((WINDOW, 8), dtype=np.float32)
        dt_raw = np.zeros(WINDOW, dtype=np.float32)
        for i, (ts, data8) in enumerate(chunk):
            mat[i] = np.array(data8, dtype=np.float32) / 255.0
            if i == 0:
                dt_raw[i] = 0.0
            else:
                # inter-arrival in milliseconds (timestamps are seconds in CarHack)
                dt_raw[i] = float((chunk[i][0] - chunk[i - 1][0]) * 1000.0)
        xs.append(np.column_stack([mat, dt_raw.reshape(-1, 1)]))  # 64×9, dt not normalized yet
        ys.append(label_id)
    return xs, ys


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "processed")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    root = args.data_root
    if root is None:
        root = Path(__file__).resolve().parents[3] / "CarHackData"
    out = args.out
    out.mkdir(parents=True, exist_ok=True)

    label_to_id = {n: i for i, n in enumerate(CLASS_NAMES)}
    all_X: List[np.ndarray] = []
    all_y: List[int] = []

    files = sorted(root.iterdir()) if root.is_dir() else []
    for path in tqdm(files, desc="files"):
        if not path.is_file() or path.suffix.lower() not in (".csv", ".txt"):
            continue
        lab_name = _label_for_path(path)
        if lab_name is None:
            continue
        lid = label_to_id[lab_name]
        rows = _file_rows(path)
        wx, wy = _windows_from_rows(rows, lid)
        all_X.extend(wx)
        all_y.extend(wy)

    if not all_X:
        raise SystemExit(f"No windows collected from {root}")

    X = np.stack(all_X, axis=0).astype(np.float32)
    y = np.array(all_y, dtype=np.int64)

    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, test_size=0.3, random_state=args.seed, stratify=y
    )
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=0.5, random_state=args.seed, stratify=y_temp
    )

    # Normalize ΔT column (index 8) using training set only
    dt_max = float(X_train[:, :, 8].max()) + 1e-6
    for arr in (X_train, X_val, X_test):
        arr[:, :, 8] = np.clip(arr[:, :, 8] / dt_max, 0.0, 1.0)

    np.save(out / "X_train.npy", X_train)
    np.save(out / "y_train.npy", y_train)
    np.save(out / "X_val.npy", X_val)
    np.save(out / "y_val.npy", y_val)
    np.save(out / "X_test.npy", X_test)
    np.save(out / "y_test.npy", y_test)

    meta = {
        "dt_max_ms": dt_max,
        "class_names": CLASS_NAMES,
        "window_size": WINDOW,
        "stride": STRIDE,
        "n_train": int(len(y_train)),
        "n_val": int(len(y_val)),
        "n_test": int(len(y_test)),
        "data_root": str(root.resolve()),
    }
    (out / "preprocess_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"Saved to {out}: shapes X_train={X_train.shape}, dt_max_ms={dt_max:.6f}")


if __name__ == "__main__":
    main()
