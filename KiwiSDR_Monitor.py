#!/usr/bin/env python3
"""
KiwiSDR SNR Monitor

A small, self-contained KiwiSDR monitor with durable JSONL logging and a
live Matplotlib dashboard. It polls a KiwiSDR `/snr` endpoint, appends each
successful response to a long-term history file, and plots all logged samples
instead of only the most recent response.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

import matplotlib.animation as animation
import matplotlib.pyplot as plt
import numpy as np
import tzlocal
from matplotlib.dates import AutoDateLocator, ConciseDateFormatter
from matplotlib.widgets import Button

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DEFAULT_LOG_FILE = DATA_DIR / "kiwi_snr_history.jsonl"
LAST_URL_FILE = DATA_DIR / "last_kiwi_url.txt"
LEGACY_LAST_URL_FILE = BASE_DIR / "last_kiwi_url.txt"

POLL_INTERVAL = 60
REFRESH_MS = 30_000
SMOOTH_WINDOW = 3
REQUEST_TIMEOUT = 10
MAX_PLOT_POINTS = 50_000

KIWI_TS_FORMAT = "%a %b %d %H:%M:%S %Y"

BAND_NAMES = {
    "136-138": "2200 m",
    "472-479": "630 m",
    "530-1602": "MW",
    "1800-2000": "160 m",
    "3500-3900": "80 m",
    "5250-5450": "60 m",
    "7000-7300": "40 m",
    "10100-10157": "30 m",
    "14000-14350": "20 m",
    "18068-18168": "17 m",
    "21000-21450": "15 m",
    "24890-24990": "12 m",
    "28000-29700": "10 m",
}

_stop_event = threading.Event()


@dataclass(frozen=True)
class Sample:
    timestamp: datetime
    band: str
    snr: float


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalise_url(url: str) -> str:
    url = url.strip().rstrip("/")
    if not url:
        raise ValueError("KiwiSDR URL is empty")
    if "://" not in url:
        url = "http://" + url
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"Invalid KiwiSDR URL: {url}")
    return url


def load_saved_url() -> str | None:
    for path in (LAST_URL_FILE, LEGACY_LAST_URL_FILE):
        try:
            value = path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            continue
        if value:
            return value
    return None


def save_url(url: str) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LAST_URL_FILE.write_text(url + "\n", encoding="utf-8")


def coerce_datetime(value: Any, fallback: datetime | None = None) -> datetime:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        text = value.strip()
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            try:
                dt = datetime.strptime(text, KIWI_TS_FORMAT).replace(tzinfo=timezone.utc)
            except ValueError:
                dt = fallback or utc_now()
    else:
        dt = fallback or utc_now()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def append_log(log_file: Path, payload: Any, collected_at: datetime | None = None) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "collected_at": (collected_at or utc_now()).isoformat(),
        "payload": payload,
    }
    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, separators=(",", ":")) + "\n")


def iter_payload_records(log_file: Path) -> Iterable[tuple[datetime, Any]]:
    if not log_file.exists():
        return
    with log_file.open("r", encoding="utf-8", errors="ignore") as handle:
        for line_no, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                record = json.loads(text)
                if isinstance(record, dict) and "payload" in record:
                    yield coerce_datetime(record.get("collected_at")), record["payload"]
                else:
                    yield utc_now(), record
                continue
            except json.JSONDecodeError:
                pass

            # Legacy format: "<timestamp> <raw /snr JSON>".
            try:
                first_json = min(i for i in (text.find("{"), text.find("[")) if i >= 0)
                yield coerce_datetime(text[:first_json].strip()), json.loads(text[first_json:])
            except (ValueError, json.JSONDecodeError) as exc:
                print(f"Skipping malformed log line {line_no} in {log_file}: {exc}", file=sys.stderr)


def extract_samples(payload: Any, collected_at: datetime) -> list[Sample]:
    samples: list[Sample] = []
    snapshots = payload if isinstance(payload, list) else [payload]
    for snapshot in snapshots:
        if not isinstance(snapshot, dict):
            continue
        timestamp = coerce_datetime(snapshot.get("ts") or snapshot.get("time"), collected_at)
        bands = snapshot.get("snr") or snapshot.get("bands") or []
        if isinstance(bands, dict):
            bands = [dict(value, band=key) if isinstance(value, dict) else {"band": key, "snr": value} for key, value in bands.items()]
        for band in bands:
            if not isinstance(band, dict) or "snr" not in band:
                continue
            try:
                snr = float(band["snr"])
            except (TypeError, ValueError):
                continue
            if "lo" in band and "hi" in band:
                label = f"{int(float(band['lo']))}-{int(float(band['hi']))}"
            else:
                label = str(band.get("band") or band.get("name") or "unknown")
            samples.append(Sample(timestamp=timestamp, band=label, snr=snr))
    return samples


def read_history(log_file: Path) -> tuple[list[datetime], dict[str, list[float]], list[str]]:
    rows: dict[datetime, dict[str, float]] = defaultdict(dict)
    bands_seen: set[str] = set()
    for collected_at, payload in iter_payload_records(log_file) or []:
        for sample in extract_samples(payload, collected_at):
            rows[sample.timestamp][sample.band] = sample.snr
            bands_seen.add(sample.band)

    times = sorted(rows)
    if len(times) > MAX_PLOT_POINTS:
        times = times[-MAX_PLOT_POINTS:]
    bands = sorted(bands_seen, key=band_sort_key)
    snr_by_band = {band: [rows[ts].get(band, np.nan) for ts in times] for band in bands}
    return times, snr_by_band, bands


def band_sort_key(label: str) -> tuple[int, str]:
    try:
        return int(float(label.split("-")[0])), label
    except (ValueError, IndexError):
        return sys.maxsize, label


def band_display_label(raw: str) -> str:
    name = BAND_NAMES.get(raw)
    label = f"{raw} kHz" if "-" in raw else raw
    return f"{label} ({name})" if name else label


def smooth(values: np.ndarray, window: int) -> np.ndarray:
    if window <= 1 or values.size < 3:
        return values
    valid = np.isfinite(values)
    if not valid.any():
        return values
    filled = np.where(valid, values, 0.0)
    weights = np.convolve(valid.astype(float), np.ones(window), mode="same")
    summed = np.convolve(filled, np.ones(window), mode="same")
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(weights > 0, summed / weights, np.nan)


def poller(kiwi_url: str, log_file: Path, interval: int) -> None:
    import requests

    endpoint = kiwi_url.rstrip("/") + "/snr"
    print(f"Polling {endpoint} every {interval}s; logging to {log_file}")
    while not _stop_event.is_set():
        try:
            response = requests.get(endpoint, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            payload = response.json()
            append_log(log_file, payload)
        except json.JSONDecodeError as exc:
            print(f"[{utc_now().isoformat()}] invalid JSON from {endpoint}: {exc}", file=sys.stderr)
        except Exception as exc:
            print(f"[{utc_now().isoformat()}] polling error: {exc}", file=sys.stderr)
        _stop_event.wait(interval)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Poll and graph KiwiSDR /snr long-term history.")
    parser.add_argument("url", nargs="?", help="KiwiSDR base URL, e.g. http://192.168.1.50:8073")
    parser.add_argument("--log-file", type=Path, default=DEFAULT_LOG_FILE, help="JSONL history log path")
    parser.add_argument("--interval", type=int, default=POLL_INTERVAL, help="Polling interval in seconds")
    parser.add_argument("--refresh-ms", type=int, default=REFRESH_MS, help="Graph refresh interval in milliseconds")
    parser.add_argument("--smooth", type=int, default=SMOOTH_WINDOW, help="Moving average window in samples")
    parser.add_argument("--no-poll", action="store_true", help="Only graph existing history; do not poll /snr")
    parser.add_argument("--once", action="store_true", help="Poll once, append to the log, and exit")
    parser.add_argument("--headless", action="store_true", help="Disable graph window; useful with --once or service logging")
    return parser


def resolve_url(args: argparse.Namespace) -> str | None:
    url = args.url or load_saved_url()
    if not url and not args.no_poll:
        if sys.stdin.isatty():
            url = input("KiwiSDR base URL: ").strip()
        else:
            raise SystemExit("A KiwiSDR URL is required unless --no-poll is used.")
    if url:
        url = normalise_url(url)
        save_url(url)
    return url


def run_once(kiwi_url: str, log_file: Path) -> None:
    import requests

    endpoint = kiwi_url.rstrip("/") + "/snr"
    response = requests.get(endpoint, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    append_log(log_file, response.json())
    print(f"Logged one /snr snapshot from {endpoint} to {log_file}")


def run_dashboard(log_file: Path, refresh_ms: int, smooth_window: int) -> None:
    visible: dict[str, bool] = defaultdict(lambda: True)
    fig, ax = plt.subplots(figsize=(13, 7))
    plt.subplots_adjust(left=0.07, bottom=0.30, right=0.98, top=0.90)
    locator = AutoDateLocator()
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(ConciseDateFormatter(locator))
    ax.set_title("KiwiSDR SNR Monitor")
    ax.set_xlabel("Time")
    ax.set_ylabel("SNR (dB)")
    ax.grid(True, linestyle="--", alpha=0.3)
    status = fig.text(0.5, 0.94, "", ha="center", fontsize="small")
    hint = fig.text(0.5, 0.08, "Click legend entries to toggle bands", ha="center", fontsize="x-small")
    lines: dict[str, Any] = {}
    annots: dict[str, Any] = {}
    legend = None

    def redraw_legend(bands: list[str]) -> None:
        nonlocal legend
        if legend:
            legend.remove()
        handles = [lines[band] for band in bands]
        legend = fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 0.12), ncol=5, fontsize="x-small", frameon=False)
        for text, band in zip(legend.get_texts(), bands):
            text.set_text(("[x] " if visible[band] else "[ ] ") + band_display_label(band))
            text.set_picker(True)
            text._kiwi_band = band

    def update(_frame: Any = None) -> list[Any]:
        times, snr_by_band, bands = read_history(log_file)
        changed = set(bands) != set(lines)
        for band in bands:
            if band not in lines:
                line, = ax.plot([], [], label=band_display_label(band))
                lines[band] = line
                annots[band] = ax.text(0, 0, "", ha="center", va="bottom", fontsize="x-small", backgroundcolor="white", visible=False)
            y = smooth(np.asarray(snr_by_band.get(band, []), dtype=float), smooth_window)
            lines[band].set_data(times, y)
            lines[band].set_visible(visible[band])
            finite = np.isfinite(y)
            if visible[band] and times and finite.any():
                idx = int(np.nanargmax(y))
                annots[band].set_position((times[idx], y[idx]))
                annots[band].set_text(f"{y[idx]:.0f} dB")
                annots[band].set_visible(True)
            else:
                annots[band].set_visible(False)
        if changed:
            redraw_legend(bands)
        if times:
            ax.set_xlim(times[0], times[-1])
            status.set_text(f"{len(times)} logged timestamps from {times[0].astimezone(tzlocal.get_localzone()):%Y-%m-%d %H:%M} to {times[-1].astimezone(tzlocal.get_localzone()):%Y-%m-%d %H:%M}")
        else:
            status.set_text(f"Waiting for SNR data in {log_file}")
        ax.relim()
        ax.autoscale_view()
        return list(lines.values()) + list(annots.values())

    def on_pick(event: Any) -> None:
        band = getattr(event.artist, "_kiwi_band", None)
        if not band:
            return
        visible[band] = not visible[band]
        update()
        fig.canvas.draw_idle()

    def set_all(value: bool) -> None:
        for band in lines:
            visible[band] = value
        update()
        fig.canvas.draw_idle()

    fig.canvas.mpl_connect("pick_event", on_pick)
    buttons = [
        Button(fig.add_axes([0.06, 0.03, 0.08, 0.035]), "All On"),
        Button(fig.add_axes([0.16, 0.03, 0.08, 0.035]), "All Off"),
        Button(fig.add_axes([0.26, 0.03, 0.08, 0.035]), "Refresh"),
    ]
    buttons[0].on_clicked(lambda _event: set_all(True))
    buttons[1].on_clicked(lambda _event: set_all(False))
    buttons[2].on_clicked(lambda _event: (update(), fig.canvas.draw_idle()))
    update()
    fig._kiwi_buttons = buttons
    fig._kiwi_animation = animation.FuncAnimation(
        fig, update, interval=refresh_ms, blit=False, cache_frame_data=False
    )
    plt.show()
    _ = hint


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    args.log_file = args.log_file.expanduser().resolve()
    kiwi_url = resolve_url(args)

    if args.once:
        if not kiwi_url:
            raise SystemExit("--once requires a KiwiSDR URL")
        run_once(kiwi_url, args.log_file)
        return 0

    if kiwi_url and not args.no_poll:
        threading.Thread(target=poller, args=(kiwi_url, args.log_file, max(1, args.interval)), daemon=True).start()

    if args.headless:
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            _stop_event.set()
            return 0

    run_dashboard(args.log_file, max(250, args.refresh_ms), max(1, args.smooth))
    _stop_event.set()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
