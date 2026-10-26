"""Terminal progress for VaayuDrishti's background downloads (read-only: only reads logs and lists files).

    .venv/bin/python scripts/progress.py            # print once
    .venv/bin/python scripts/progress.py --watch 5  # refresh every 5 s (Ctrl+C to stop; downloads keep running)

Shows each expected TIGGE file (from data/events.yaml) with its ECDS queue state or download bar, and the
ERA5 climate download.
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import events  # noqa: E402
from pipeline.fetch_tigge import requests_for  # noqa: E402

LOGS = ROOT / "logs"
TIGGE_LOGS = [LOGS / "fetch-tigge.log", LOGS / "fetch-tigge-michaung.log"]
ERA5_LOG = LOGS / "fetch-era5.log"
ERA5_DIR = ROOT / "data" / "raw" / "era5" / "tp24_00z"
WIDTH = 30
GREEN, AMBER, CYAN, DIM, BOLD, RESET = (("\033[32m", "\033[33m", "\033[36m", "\033[2m", "\033[1m", "\033[0m")
                                        if sys.stdout.isatty() else ("",) * 6)
TS = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)")
TQDM = re.compile(r"(\d+)%\|[^|]*\|\s*([\d.]+[kMG]?)/([\d.]+[kMG]?)")


def bar(frac: float, colour: str) -> str:
    n = int(round(max(0.0, min(1.0, frac)) * WIDTH))
    return f"{colour}{'█' * n}{DIM}{'░' * (WIDTH - n)}{RESET}"


def ago(ts: str | None) -> str:
    if not ts:
        return ""
    m = int((datetime.now() - datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")).total_seconds() // 60)
    return f"{m // 60} h {m % 60:02d} min" if m >= 60 else f"{m} min"


def tigge_states() -> dict[str, dict]:
    """Latest state per target file, from both downloader logs."""
    out: dict[str, dict] = {}
    for log in TIGGE_LOGS:
        if not log.exists():
            continue
        cur = None
        for raw in log.read_text(errors="replace").replace("\r", "\n").splitlines():
            ts = TS.match(raw)
            if m := re.search(r"requesting (\S+\.grib)", raw):
                cur = m.group(1)
                out[cur] = {"state": "submitted", "since": ts.group(1) if ts else None}
            elif cur and (m := re.search(r"Request ID is (\S+)", raw)):
                out[cur]["id"] = m.group(1)
            elif cur and (m := re.search(r"status has been updated to (\w+)", raw)):
                out[cur].update(state=m.group(1), since=ts.group(1) if ts else out[cur]["since"])
            elif cur and "Downloading " in raw:
                out[cur]["state"] = "downloading"
            elif cur and (m := TQDM.search(raw)):
                out[cur].update(state="downloading", pct=int(m.group(1)), done=m.group(2), total=m.group(3))
            elif m := re.search(r"saved (\S+\.grib)", raw):
                out.setdefault(m.group(1), {})["state"] = "saved"
            elif cur and re.search(r"Traceback|Error|failed", raw):
                out[cur]["state"] = "error"
    return out


def render() -> str:
    lines = [f"{BOLD}VaayuDrishti downloads{RESET}  {DIM}{datetime.now():%H:%M:%S}{RESET}", ""]
    states = tigge_states()
    rows, n_done = [], 0
    for ev in events.load_events():
        if ev.ensemble_source != "tigge":
            continue
        for path, _ in requests_for(ev, "ecmwf"):
            name = f"{ev.id}/{path.name}"
            st = states.get(str(path), {})
            if path.exists() and st.get("state") in (None, "saved"):
                n_done += 1
                rows.append(f"  {name:<36} {bar(1, GREEN)} {GREEN}done{RESET} {path.stat().st_size / 1e6:.1f} MB")
            elif st.get("state") == "downloading":
                pct = st.get("pct", 0)
                rows.append(f"  {name:<36} {bar(pct / 100, CYAN)} {CYAN}{pct}%{RESET} {st.get('done', '')}/{st.get('total', '')}")
            elif st.get("state") in ("accepted", "submitted"):
                rows.append(f"  {name:<36} {bar(0, AMBER)} {AMBER}queued at ECDS {ago(st.get('since'))}{RESET} {DIM}{st.get('id', '')[:8]}{RESET}")
            elif st.get("state") == "running":
                rows.append(f"  {name:<36} {bar(0.05, CYAN)} {CYAN}ECDS preparing {ago(st.get('since'))}{RESET}")
            elif st.get("state") == "error":
                rows.append(f"  {name:<36} {bar(0, AMBER)} {AMBER}error: see the log{RESET}")
            else:
                rows.append(f"  {name:<36} {bar(0, DIM)} {DIM}not submitted yet{RESET}")
    total = len(rows)
    lines.append(f"{BOLD}TIGGE{RESET}  {n_done}/{total} files  {bar(n_done / max(total, 1), GREEN)}")
    lines += rows

    lines.append("")
    have = len(list(ERA5_DIR.glob("*.npy"))) if ERA5_DIR.exists() else 0
    need = None
    if ERA5_LOG.exists():
        text = ERA5_LOG.read_text(errors="replace")
        m = re.findall(r"(\d+) days needed", text)
        need = int(m[-1]) if m else None
        failed = "failed after retries" in text
    else:
        failed = False
    if need:
        state = f"{AMBER}some days failed: rerun python -m pipeline.fetch_era5{RESET}" if failed else (f"{GREEN}done{RESET}" if have >= need else "")
        lines.append(f"{BOLD}ERA5 climate{RESET}  {bar(have / need, GREEN if have >= need else CYAN)} {have}/{need} days ({100 * have / need:.0f}%) {state}")
    else:
        lines.append(f"{BOLD}ERA5 climate{RESET}  {have} days saved")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--watch", type=float, metavar="SECONDS", help="refresh every SECONDS")
    args = ap.parse_args()
    if not args.watch:
        print(render())
        return
    try:
        while True:
            sys.stdout.write("\033[H\033[2J" + render() + f"\n\n{DIM}refreshing every {args.watch:g} s · Ctrl+C to stop (downloads keep running){RESET}\n")
            sys.stdout.flush()
            time.sleep(args.watch)
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()
