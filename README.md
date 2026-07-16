# KiwiSDR SNR Monitor

A modern Python monitor for KiwiSDR `/snr` data. It polls a KiwiSDR receiver,
keeps a durable long-term JSONL history, and displays a live Matplotlib dashboard
with per-band SNR traces, smoothing, peak labels, and legend-based visibility
controls.

## Features

- Polls `http://<kiwi>:8073/snr` on a configurable interval.
- Appends every successful response to `data/kiwi_snr_history.jsonl` for long-term logging.
- Graphs all logged history rather than only the latest snapshot.
- Supports non-interactive use for services, cron jobs, and remote hosts.
- Handles legacy log lines from older versions of this project.
- Remembers the last KiwiSDR URL in `data/last_kiwi_url.txt`.

## Installation

```bash
python -m venv venv
source venv/bin/activate        # macOS/Linux
# venv\Scripts\activate         # Windows
pip install -r requirements.txt
```

## Usage

Start polling and open the live dashboard:

```bash
python KiwiSDR_Monitor.py http://192.168.1.50:8073
```

Poll once and exit, useful for cron or testing:

```bash
python KiwiSDR_Monitor.py http://192.168.1.50:8073 --once
```

Run as a headless long-term logger without opening a graph window:

```bash
python KiwiSDR_Monitor.py http://192.168.1.50:8073 --headless --interval 60
```

Graph existing history without polling the receiver:

```bash
python KiwiSDR_Monitor.py --no-poll --log-file data/kiwi_snr_history.jsonl
```

## Command-line options

| Option | Description |
| --- | --- |
| `url` | KiwiSDR base URL. If omitted, the last saved URL is reused when polling. |
| `--log-file PATH` | JSONL history path. Default: `data/kiwi_snr_history.jsonl`. |
| `--interval SECONDS` | Polling interval. Default: `60`. |
| `--refresh-ms MS` | Dashboard refresh interval. Default: `30000`. |
| `--smooth N` | Moving-average smoothing window in samples. Default: `3`. |
| `--no-poll` | Read and graph existing history only. |
| `--once` | Poll one `/snr` snapshot, append it to the log, and exit. |
| `--headless` | Keep polling without opening a graph window. |

## Log format

Each line in the history file is JSON containing the collection time and the raw
KiwiSDR payload:

```json
{"collected_at":"2026-07-14T12:00:00+00:00","payload":[{"ts":"Tue Jul 14 12:00:00 2026","snr":[{"lo":7000,"hi":7300,"snr":34.2}]}]}
```

Because the raw payload is preserved, future tools can reprocess the data without
losing receiver-specific details.

## Notes for long-term operation

- Use `--headless` under systemd, cron, tmux, or another process supervisor.
- Back up `data/kiwi_snr_history.jsonl`; this is the long-term database.
- If the log grows very large, the dashboard plots the most recent 50,000 timestamps
  to stay responsive while preserving the full file on disk.

## License

MIT
