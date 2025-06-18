#!/usr/bin/env python3
"""
KiwiSDR SNR Logger + Real-Time Graph
• 5-column inline legend
• Compact buttons (All On, All Off, Refresh)
• Peak-dB annotations & background polling + logging
• Subplots adjusted to left=0.048, bottom=0.30, right=0.976, top=0.88, wspace=0.207, hspace=0.19
"""

import os, sys, json, time, threading, requests
from datetime import datetime, timezone
from collections import defaultdict

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.dates import AutoDateLocator, ConciseDateFormatter
from matplotlib.widgets import Button
import tzlocal  # pip install tzlocal

# ────────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ────────────────────────────────────────────────────────────────────────────────

BASE_DIR       = os.path.dirname(__file__)
LOG_FILE_PATH  = os.path.join(BASE_DIR, "KiwiSDR_SNR_latest.log")
LAST_URL_FILE  = os.path.join(BASE_DIR, "last_kiwi_url.txt")
TS_FORMAT      = "%a %b %d %H:%M:%S %Y"
POLL_INTERVAL  = 60       # seconds
REFRESH_MS     = 30_000   # ms
SMOOTH_WINDOW  = 3        # moving-average window

BAND_NAMES = {
    "136-138 Hz":    "2200 m", "472-479 Hz":  "630 m",   "530-1602 Hz": "MW",
    "1800-2000 Hz":  "160 m",  "3500-3900 Hz":"80 m",    "5250-5450 Hz":"60 m",
    "7000-7300 Hz":  "40 m",   "10100-10157 Hz":"30 m",  "14000-14350 Hz":"20 m",
    "18068-18168 Hz":"17 m",   "21000-21450 Hz":"15 m",  "24890-24990 Hz":"12 m",
    "28000-29700 Hz":"10 m",
}

latest_snapshots = []  # in-memory cache of the most recent /snr JSON

# ────────────────────────────────────────────────────────────────────────────────
# POLLER THREAD
# ────────────────────────────────────────────────────────────────────────────────

def _ensure_log():
    os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)
    open(LOG_FILE_PATH, "a").close()

def _poller(kiwi_url):
    _ensure_log()
    endpoint = kiwi_url.rstrip("/") + "/snr"
    print(f"Polling {endpoint} every {POLL_INTERVAL}s…")
    global latest_snapshots
    while True:
        try:
            resp = requests.get(endpoint, timeout=10)
            resp.raise_for_status()
            arr = resp.json()
            ts0 = datetime.now(timezone.utc).isoformat()
            with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
                f.write(f"{ts0} {json.dumps(arr, separators=(',',':'))}\n")
            latest_snapshots = arr
        except Exception as e:
            print(f"[{datetime.now(timezone.utc).isoformat()}] POLL ERROR: {e}")
        time.sleep(POLL_INTERVAL)

# ────────────────────────────────────────────────────────────────────────────────
# READ DATA (in-memory or fallback to last log line)
# ────────────────────────────────────────────────────────────────────────────────

def read_data():
    arr = list(latest_snapshots)
    if not arr and os.path.exists(LOG_FILE_PATH):
        last = None
        with open(LOG_FILE_PATH, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if line.strip():
                    last = line.strip()
        if last:
            try:
                s = last.index("[")
                e = last.rindex("]") + 1
                arr = json.loads(last[s:e])
            except:
                arr = []
    if not arr:
        return [], {}, []

    tz = tzlocal.get_localzone()
    times = []
    snr_by_band = defaultdict(list)
    seen = set()

    for snap in arr:
        dt = datetime.strptime(snap["ts"], TS_FORMAT) \
                   .replace(tzinfo=timezone.utc) \
                   .astimezone(tz)
        times.append(dt)
        this = {f"{b['lo']}-{b['hi']} Hz": b["snr"] for b in snap["snr"]}
        new = set(this) - seen
        for lbl in new:
            snr_by_band[lbl] = [np.nan] * (len(times)-1)
        for lbl in seen | set(this):
            snr_by_band[lbl].append(this.get(lbl, np.nan))
        seen |= set(this)

    for lbl in seen:
        if len(snr_by_band[lbl]) < len(times):
            pad = len(times) - len(snr_by_band[lbl])
            snr_by_band[lbl] += [np.nan]*pad

    def keyfn(lbl):
        lo,_ = lbl.split()[0].split("-")
        return int(lo)
    bands = sorted(seen, key=keyfn)
    return times, snr_by_band, bands

# ────────────────────────────────────────────────────────────────────────────────
# HELPERS
# ────────────────────────────────────────────────────────────────────────────────

def hz_to_label(raw):
    k = raw.replace(" Hz", " kHz")
    nm = BAND_NAMES.get(raw)
    return f"{k} ({nm})" if nm else k

def smooth(y):
    return np.convolve(y, np.ones(SMOOTH_WINDOW)/SMOOTH_WINDOW, mode="same")

# ────────────────────────────────────────────────────────────────────────────────
# MAIN
# ────────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Prompt for KiwiSDR URL
    default = None
    if os.path.exists(LAST_URL_FILE):
        try:
            default = open(LAST_URL_FILE, "r", encoding="utf-8").read().strip()
        except:
            pass
    prompt = "KiwiSDR base URL"
    if default:
        prompt += f" [{default}]"
    prompt += ": "
    ui = input(prompt).strip().rstrip("/")
    if not ui and not default:
        print("No URL; exiting.")
        sys.exit(1)
    kiwi_url = ui or default
    with open(LAST_URL_FILE, "w", encoding="utf-8") as f:
        f.write(kiwi_url)

    # Start polling thread
    threading.Thread(target=_poller, args=(kiwi_url,), daemon=True).start()

    # Initial read
    times, snr_by_band, bands = read_data()
    labels = [hz_to_label(b) for b in bands]

    # Build figure
    fig, ax = plt.subplots(figsize=(12,6))
    plt.subplots_adjust(
        left=0.048, bottom=0.30,
        right=0.976, top=0.88,
        wspace=0.207, hspace=0.19
    )

    # Plot each band + setup peak annotations
    lines, annots = [], {}
    for b,lbl in zip(bands,labels):
        arr = np.array(snr_by_band[b], dtype=float)
        ln, = ax.plot(times, smooth(arr), label=lbl)
        lines.append(ln)
        txt = ax.text(0,0,"", ha="center", va="bottom",
                      fontsize="x-small", backgroundcolor="white",
                      visible=False, transform=ax.transData)
        annots[b] = txt

    # Inline 5-column legend under the axes
    leg = fig.legend(
        loc="lower center",
        bbox_to_anchor=(0.5, 0.16),
        ncol=5,
        fontsize="x-small",
        frameon=False
    )
    leg_lines = leg.get_lines()
    leg_texts = leg.get_texts()
    base      = [t.get_text() for t in leg_texts]
    for t in leg_texts:
        t.set_text(" [x] " + t.get_text())

    mapping = dict(zip(leg_lines, lines))
    def on_pick(evt):
        ln  = mapping[evt.artist]
        vis = not ln.get_visible()
        ln.set_visible(vis)
        idx = leg_lines.index(evt.artist)
        leg_texts[idx].set_text(f"{' [x] ' if vis else ' [ ] '}{base[idx]}")
        leg_lines[idx].set_alpha(1.0 if vis else 0.2)
        if not vis:
            annots[bands[idx]].set_visible(False)
        fig.canvas.draw()

    for L in leg_lines:
        L.set_picker(True)
    fig.canvas.mpl_connect("pick_event", on_pick)

    # Instruction directly below legend
    fig.text(
        0.5, 0.11,
        "Click on the coloured line to toggle that band on/off",
        ha="center", fontsize="x-small"
    )

    # Buttons: All On, All Off, Refresh (small, left of legend)
    bw, bh = 0.08, 0.035
    ax_on     = fig.add_axes([0.06, 0.05, bw, bh])
    ax_off    = fig.add_axes([0.16, 0.05, bw, bh])
    ax_refresh= fig.add_axes([0.26, 0.05, bw, bh])
    btn_on    = Button(ax_on,      "All On")
    btn_off   = Button(ax_off,     "All Off")
    btn_refresh = Button(ax_refresh, "Refresh")
    for btn in (btn_on, btn_off, btn_refresh):
        btn.label.set_fontsize("x-small")

    def all_on(evt):
        for i, ln in enumerate(lines):
            if not ln.get_visible():
                on_pick(type("E", (), {"artist": leg_lines[i]}))
        fig.canvas.draw()

    def all_off(evt):
        for i, ln in enumerate(lines):
            if ln.get_visible():
                on_pick(type("E", (), {"artist": leg_lines[i]}))
        fig.canvas.draw()

    def manual_refresh(evt):
        update(None)
        fig.canvas.draw()

    btn_on.on_clicked(all_on)
    btn_off.on_clicked(all_off)
    btn_refresh.on_clicked(manual_refresh)

    # Axes formatting
    ax.set_title("KiwiSDR SNR (Real-Time)")
    ax.set_xlabel("Time")
    ax.set_ylabel("SNR (dB)")
    locator   = AutoDateLocator()
    formatter = ConciseDateFormatter(locator)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)
    ax.grid(True, linestyle="--", alpha=0.3)

    # Update loop with peak annotations
    def update(frame):
        times, snrdata, _ = read_data()
        for b, ln in zip(bands, lines):
            ysm = smooth(np.array(snrdata.get(b,[]), dtype=float))
            ln.set_data(times, ysm)
            txt = annots[b]
            if ln.get_visible() and ysm.size:
                idx = int(np.nanargmax(ysm))
                txt.set_position((times[idx], ysm[idx]))
                txt.set_text(f"{ysm[idx]:.0f} dB")
                txt.set_visible(True)
            else:
                txt.set_visible(False)
        if times:
            ax.set_xlim(times[0], times[-1])
        ax.relim(); ax.autoscale_view()
        return lines + list(annots.values())

    ani = animation.FuncAnimation(fig, update,
                                  interval=REFRESH_MS, blit=False)

    plt.show()
