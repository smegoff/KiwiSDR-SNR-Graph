
A pair of Python scripts to:

1. **Continuously poll a KiwiSDR** for SNR (Signal-to-Noise Ratio) statistics via its public `/snr` endpoint and append each snapshot (timestamp + per-band SNR values) to a log file.
    
2. **Read that log file** (or a “latest snapshot” file) and plot SNR over time for all frequency bands, in your local timezone, with moving-average smoothing, peak annotations, and a midnight-clamped x-axis.
    

---

## 📁 Repository Contents

```
.
├── data/
│   └── kiwi_snr_history.log        # (auto-created) rolling log of SNR snapshots
│
├── KiwiSDR_Graph.py                # “graph only” script: reads a “latest” JSON line and plots it
├── KiwiSDR_SNR.py              # continuous polling/logger script: appends to history log
├── README.md                       # this file
└── requirements.txt                # Python dependencies
```

> **Note:** After you run `log_kiwidsr_snr.py`, a new file  
> `data/kiwi_snr_history.log` (inside the `data/` folder) will be created and continuously updated.  
> You can either plot from that history file or, if you prefer a single “latest snapshot” approach, use `KiwiSDR_Graph.py` with a separate `KiwiSDR_SNR_latest.log` file (see the comments inside that script).

---

## 📋 Requirements

Both scripts assume you have:

- Python 3.7+ (tested on 3.10+)
    
- A working KiwiSDR with access to its `/snr` endpoint (e.g. `http://<KIWI_IP>:8073/snr`).
    

### Python Dependencies

Install the required packages with:

```
pip install -r requirements.txt
```

Contents of **requirements.txt**:

```
requests
numpy
matplotlib
tzlocal
```

---

## 🔧 Script 1: `log_kiwidsr_snr.py`

Continuously polls `<KIWI_BASE_URL>/snr` every 60 seconds (by default), parses the JSON response, and appends a line to the history log:

```
<UTC_ISO_TIMESTAMP> <JSON-dump of snapshot>
```

### Key Features

- Remembers the last KiwiSDR URL you entered (in `last_kiwi_url.txt`) and offers it as a default prompt.
    
- Creates (if needed) a folder called `data/` and a log file named `kiwi_snr_history.log`.
    
- Skips blank or invalid (non-JSON) responses without crashing.
    
- Uses UTC timestamps for uniformity.
    

### Usage

```
python log_kiwidsr_snr.py
```

1. You will be prompted:
    
    ```
    Enter your KiwiSDR base URL (e.g. http://192.168.1.50:8073) [http://last-used-url]:
    ```
    
2. If you type nothing and press Enter, it will reuse the last-saved URL. Otherwise, paste (or type) your new KiwiSDR base URL (e.g. `http://192.168.10.238:8073`) and press Enter.
    
3. The script will print:
    
    ```
    Initialized log at <repo_root>/data/kiwi_snr_history.log
    Starting KiwiSDR SNR logger (poll every 60s)…
    ```
    
4. It will then run indefinitely. Each successful poll & parse writes one line to `data/kiwi_snr_history.log`. Any fetch/parsing errors are printed but do not stop the loop.
    
5. To stop logging and proceed to plotting, press `Ctrl+C`.
    

---

## 📊 Script 2: `KiwiSDR_Graph.py`

Reads the log file (either the single-line “latest snapshot” approach or the full `kiwi_snr_history.log`), parses all timestamps and SNR values, then generates a Matplotlib plot:

- **X-axis**: local time in `HH:MM`, clamped from midnight of the first sample date to the last sample.
    
- **Y-axis**: SNR (dB) for each band.
    
- **Smoothing**: a small moving average (window size configurable).
    
- **Annotations**: show the dB value at each band’s peak point.
    
- **Legend**: placed below the plot, one column per two bands by default.
    
- **Grid**: dashed gridlines for readability.
    
- **Tick intervals**: every 30 minutes.
    

There are two modes:

1. **Graph “Latest Snapshot” Only**  
    If you maintain a separate file called `KiwiSDR_SNR_latest.log` (each line is a single JSON array of band snapshots), the script will:
    
    - Read **only** the **last non-empty line**.
        
    - Parse that JSON array (the “snapshot history”).
        
    - Plot **all bands over time** according to that array.
        
    
    In this mode:
    
    ```
    LOG_FILE_PATH = os.path.join(os.path.dirname(__file__),
                                 "KiwiSDR_SNR_latest.log")
    ```
    
    must point to your single-line file.
    
2. **Graph Full History**  
    If you just ran `log_kiwidsr_snr.py` and want to plot the entire `data/kiwi_snr_history.log` content, call:
    
    ```
    python KiwiSDR_Graph.py --history
    ```
    
    In that case, the script will look for `data/kiwi_snr_history.log` in the same folder and plot **all** snapshots it finds.
    

### Usage Examples

#### A. Plotting from “latest snapshot” file

1. Copy your single-line JSON file into the same folder as `KiwiSDR_Graph.py` and name it `KiwiSDR_SNR_latest.log`.
    
2. Make sure the first lines of `KiwiSDR_Graph.py` point to:
    
    ```
    LOG_FILE_PATH = os.path.join(os.path.dirname(__file__),
                                 "KiwiSDR_SNR_latest.log")
    ```
    
3. Run:
    
    ```
    python KiwiSDR_Graph.py
    ```
    
4. A Matplotlib window will appear showing all bands’ smoothed SNR over time for that single “snapshot history.”
    

#### B. Plotting from full history log

1. After running `log_kiwidsr_snr.py` (and pressing Ctrl+C), you should have a file:
    
    ```
    data/kiwi_snr_history.log
    ```
    
    with many lines like:
    
    ```
    {"ts":"Thu May 22 19:31:52 2025","snr":[{"lo":0,"hi":1800,"snr":5.2},…]}
    {"ts":"Thu May 22 19:32:52 2025","snr":[…]}
    ...
    ```
    
2. Edit the top of `KiwiSDR_Graph.py` so that it reads:
    
    ```
    LOG_FILE_PATH = os.path.join(os.path.dirname(__file__),
                                 "data/kiwi_snr_history.log")
    ```
    
3. Run:
    
    ```
    python KiwiSDR_Graph.py --history
    ```
    
4. A plot window will appear showing every band’s smoothed SNR over time, from midnight of the first logged date through the last snapshot.
    

---

## ⚙️ Configuration

Inside each script you can tweak:

- **Polling interval** (`POLL_INTERVAL` in `log_kiwidsr_snr.py`).
    
- **Log‐file location** (`LOG_FILE` or `LOG_DIR`).
    
- **Smoothing window** (`SMOOTH_WINDOW` in `KiwiSDR_Graph.py`).
    
- **Matplotlib figure size**, colors, fonts, etc.
    

All date–time parsing is done with `tzlocal` so that X-axis labels reflect your machine’s local timezone. If you’d rather force UTC, replace:

```
local_tz = tzlocal.get_localzone()
```

with:

```
from datetime import timezone
local_tz = timezone.utc
```

---

## ⚠️ Troubleshooting

- **“Extra data…”**  
    Make sure your log file contains exactly one JSON object per line, each of the form:
    
    ```
    {"ts":"Thu May 22 19:31:52 2025","snr":[{"lo":0,"hi":1800,"snr":5.2}, …]}
    ```
    
    If you have a “single‐line” array of snapshots, be sure you set `LOG_FILE_PATH` to that file and that it starts with `[` and ends with `]`.
    
- **Time labels are off by your timezone**  
    Confirm that `tzlocal` is installed and that your system’s local timezone is detected correctly. If necessary, hardcode `local_tz = timezone.utc` and adjust `DateFormatter`.
    
- **Plot window opens but is blank**  
    Check that `history = load_history()` returns a non-empty list. Inspect your log file for valid JSON lines. You can manually open `data/kiwi_snr_history.log` and verify that each line is parseable, with `"ts"` and `"snr"` keys.
    
- **Plot starts at a non-midnight timestamp**  
    The script explicitly clamps X-axis to midnight of the first snapshot’s date. If your first snapshot’s `ts` is, e.g., `"Thu May 22 00:12:34 2025"`, the “midnight” clamp is `2025-05-22 00:00:00`. If you see something else, double-check that `dt.replace(hour=0,minute=0,…)` logic is intact.
    

---

## 📝 License

This project is provided under the MIT License (or your preferred license). Feel free to copy, modify, and distribute as needed.

---

## 🙏 Acknowledgments

- Inspired by community requests for KiwiSDR SNR monitoring.
    
- Uses:
    
    - [requests](https://pypi.org/project/requests/) for HTTP polling
        
    - [matplotlib](https://matplotlib.org/) for plotting
        
    - [numpy](https://numpy.org/) for smoothing
        
    - [tzlocal](https://pypi.org/project/tzlocal/) for local‐timezone support
        

Enjoy tracking and visualizing your KiwiSDR’s SNR performance! 🚀
