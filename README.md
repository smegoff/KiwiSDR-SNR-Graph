# KiwiSDR SNR Graph

A combined logger & real-time graph for KiwiSDR SNR data.  
Polls your KiwiSDR’s `/snr` endpoint every minute, logs the raw JSON to a file, and displays an interactive, live-updating Matplotlib dashboard with per-band SNR curves, click-to-toggle legend entries, peak-dB annotations, and “All On/All Off” controls.

---

## 📋 Prerequisites

- **Python** ≥ 3.7  
- **pip** (Python package installer)

---

## ⚙️ Installation

1. **Clone or download** this repository:  
   ```bash
   git clone https://github.com/smegoff/KiwiSDR-SNR-Graph.git
   cd KiwiSDR-SNR-Graph
2. Create a virtual environment (recommended):
python -m venv venv
source venv/bin/activate        # macOS/Linux
venv\Scripts\activate           # Windows

3. Install the Python dependencies:
pip install requests numpy matplotlib tzlocal

🚀 Usage

    Run the monitor script:

python KiwiSDR_Monitor.py

Enter your KiwiSDR base URL when prompted, for example:

    KiwiSDR base URL [http://192.168.1.50:8073]:

        Press Enter to accept the default (saved from last run), or paste a new URL.

    The script will:

        Spawn a background thread polling /snr every 60 seconds.

        Append each JSON snapshot to KiwiSDR_SNR_latest.log.

        Open a Matplotlib window showing:

            Live-updating SNR vs. time curves per band.

            Click on a legend entry to toggle that band on/off.

            Peak-dB annotations appear only on visible bands.

            All On / All Off buttons for bulk toggling.

            An instruction line below the legend:
            “Click on the coloured line to toggle that band on/off.”

🔧 Configuration

    Polling interval: Adjust POLL_INTERVAL (in seconds) at the top of KiwiSDR_Monitor.py.

    Graph refresh rate: Adjust REFRESH_MS (in milliseconds) at the top of the script.

    Smoothing window: Modify SMOOTH_WINDOW (samples) to change moving-average smoothing.

    Layout: Tweak the plt.subplots_adjust(...) parameters in the plotting section to adjust margins and spacing.

📝 License

MIT © Your Name
Feel free to fork and contribute back!

