"""Parse CarHackData CSV / normal_run_data.txt into REAL-IDS-style CAN dicts."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

# Order must match training labels and chain_builder.CAN_CLASS_NAMES
CARHACK_CLASS_NAMES: List[str] = ["Normal", "DoS", "Fuzzy", "gear", "RPM"]

CARHACK_FILES: List[Tuple[str, int]] = [
    ("normal_run_data.txt", 0),
    ("DoS_dataset.csv", 1),
    ("Fuzzy_dataset.csv", 2),
    ("gear_dataset.csv", 3),
    ("RPM_dataset.csv", 4),
]

_RE_TXT = re.compile(
    r"Timestamp:\s*([0-9.]+).*?ID:\s*([0-9a-fA-F]+).*?DLC:\s*(\d+)\s+((?:[0-9a-fA-F]{2}\s*)+)",
    re.IGNORECASE | re.DOTALL,
)


def parse_csv_line(line: str) -> Optional[Tuple[float, str, int, List[str]]]:
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    parts = line.split(",")
    if len(parts) < 4:
        return None
    try:
        ts = float(parts[0])
        can_id = parts[1].strip()
        dlc = int(parts[2])
    except (ValueError, IndexError):
        return None
    need = 3 + dlc
    if len(parts) < need:
        return None
    data_bytes = [parts[3 + i].strip().lower() for i in range(dlc)]
    return ts, can_id, dlc, data_bytes


def parse_txt_line(line: str) -> Optional[Tuple[float, str, int, List[str]]]:
    m = _RE_TXT.search(line)
    if not m:
        return None
    ts_s, cid, dlc_s, data_s = m.groups()
    dlc = int(dlc_s)
    hexes = [h.lower() for h in data_s.split() if h]
    if len(hexes) < dlc:
        return None
    hexes = hexes[:dlc]
    return float(ts_s), cid.strip(), dlc, hexes


def packet_dict(
    ts: float,
    can_id: str,
    data_hexes: List[str],
) -> Dict[str, Any]:
    cid = can_id if can_id.lower().startswith("0x") else "0x" + can_id
    data = "".join(f"{int(h, 16):02x}" for h in data_hexes)
    return {"id": cid, "data": data, "timestamp": ts}


def iter_packets_from_file(path: Path, max_lines: int = 0) -> Iterator[Dict[str, Any]]:
    """Yield packet dicts; max_lines 0 = no limit (careful on huge files)."""
    is_txt = path.suffix.lower() == ".txt"
    n = 0
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if max_lines and n >= max_lines:
                break
            parsed = parse_txt_line(line) if is_txt else parse_csv_line(line)
            if not parsed:
                continue
            ts, cid, _dlc, hexes = parsed
            try:
                yield packet_dict(ts, cid, hexes)
            except ValueError:
                continue
            n += 1


def default_carhack_data_root() -> Path:
    # ml_bridge -> integration -> REAL-IDS -> VCEI
    return Path(__file__).resolve().parents[3] / "CarHackData"
