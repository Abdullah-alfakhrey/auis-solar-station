# AUIS Solar Station — Pyranometer Data Logger

Reads irradiance data from an Arduino-connected pyranometer via serial, saves it to a local CSV, and emails a weekly report automatically.

## Branches

| Branch | Contents |
|---|---|
| `main` | Headless data logger + weekly email sender (this branch) |
| `web-dashboard` | Full Flask server with live Chart.js dashboard |

---

## RPi Setup (one-time)

### 1. Install dependencies

```bash
pip3 install pyserial
```

### 2. Clone the repo

```bash
cd /home/pi
git clone https://github.com/Abdullah-alfakhrey/auis-solar-station.git
cd auis-solar-station
```

### 3. Create your credentials file

```bash
cp config.env.example config.env
nano config.env
```

Fill in:
- `GMAIL_SENDER` — your Gmail address
- `GMAIL_APP_PASSWORD` — a Gmail App Password (see instructions inside the file)
- `RECIPIENT_EMAIL` — where to send the weekly report (can be the same address)

`config.env` is `.gitignore`d so it is never committed or pushed.

### 4. Fix serial port permissions (if needed)

```bash
sudo usermod -a -G dialout $USER
# then log out and back in
```

Check which port your Arduino is on:
```bash
ls /dev/tty*
# usually /dev/ttyACM0 or /dev/ttyUSB0
```

Edit `SERIAL_PORT` in `data_logger.py` if it differs from `/dev/ttyACM0`.

### 5. Test both scripts manually

```bash
# Start the logger (Ctrl+C to stop)
python3 data_logger.py

# Send a test email (needs at least one row in data/)
python3 send_weekly_report.py
```

---

## Running automatically on boot

Use `cron` — no extra software needed.

```bash
crontab -e
```

Add these two lines:

```
# Start the data logger at boot (restarts automatically on serial errors)
@reboot sleep 30 && python3 /home/pi/auis-solar-station/data_logger.py >> /home/pi/auis-solar-station/data/logger.log 2>&1

# Send the weekly CSV report every Monday at 08:00
0 8 * * 1 python3 /home/pi/auis-solar-station/send_weekly_report.py >> /home/pi/auis-solar-station/data/email.log 2>&1
```

Save and exit. The logger starts 30 seconds after boot (to let the serial device initialise), and the report goes out every Monday morning.

---

## File structure

```
auis-solar-station/
├── data_logger.py          # serial → CSV (no web server)
├── send_weekly_report.py   # emails last 7 days of data
├── config.env.example      # credential template (safe to commit)
├── config.env              # your real credentials (gitignored)
├── .gitignore
├── README.md
└── data/                   # gitignored — lives only on the RPi
    ├── readings.csv
    ├── logger.log
    └── email.log
```

---

## CSV format

```
timestamp,irradiance_w_m2,efficiency_pct
2025-10-26 12:14:24,850.23,85.0
```

- `irradiance_w_m2` — solar irradiance in W/m²
- `efficiency_pct` — percentage of the 1000 W/m² reference irradiance
