"""
Weekly CSV report sender.
Reads credentials from config.env in the same directory, extracts the last
7 days of readings.csv, and emails the excerpt as an attachment.

Run manually:   python3 send_weekly_report.py
Cron (Mondays 08:00):  0 8 * * 1  python3 /home/pi/auis-solar-station/send_weekly_report.py
"""

import csv
import os
import smtplib
import sys
from datetime import datetime, timedelta
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / 'config.env'
LOG_FILE = BASE_DIR / 'data' / 'readings.csv'
# ─────────────────────────────────────────────────────────────────────────────


def load_config():
    if not CONFIG_FILE.exists():
        sys.exit(f"ERROR: {CONFIG_FILE} not found. Copy config.env.example and fill in your values.")

    config = {}
    with open(CONFIG_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, val = line.partition('=')
                config[key.strip()] = val.strip()

    required = ('GMAIL_SENDER', 'GMAIL_APP_PASSWORD', 'RECIPIENT_EMAIL')
    missing = [k for k in required if not config.get(k)]
    if missing:
        sys.exit(f"ERROR: Missing keys in config.env: {', '.join(missing)}")

    return config


def extract_last_7_days(log_file):
    """Return CSV rows from the past 7 days as a list of lists (header included)."""
    cutoff = datetime.now() - timedelta(days=7)
    rows = [['timestamp', 'irradiance_w_m2', 'efficiency_pct']]

    if not log_file.exists():
        return rows

    with open(log_file, newline='') as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            if not row:
                continue
            try:
                ts = datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
                if ts >= cutoff:
                    rows.append(row)
            except (ValueError, IndexError):
                continue

    return rows


def build_csv_bytes(rows):
    import io
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    return buf.getvalue().encode('utf-8')


def send_email(config, csv_bytes, row_count):
    sender = config['GMAIL_SENDER'].strip()
    password = ''.join(config['GMAIL_APP_PASSWORD'].split())

    recipient_text = config['RECIPIENT_EMAIL']
    recipients = [email.strip() for email in str(recipient_text).split(',') if email.strip()]

    if not recipients:
        raise ValueError("No recipient email address configured")

    week_end = datetime.now().strftime('%Y-%m-%d')
    week_start = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    subject = f"AUIS Solar Station - Weekly Report {week_start} to {week_end}"

    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = ', '.join(recipients)
    msg['Subject'] = subject

    body = (
        f"Weekly pyranometer report from the AUIS Solar Station.\n\n"
        f"Period : {week_start} to {week_end}\n"
        f"Rows   : {row_count} readings\n\n"
        f"The CSV file is attached.\n"
    )
    msg.attach(MIMEText(body, 'plain'))

    attachment = MIMEBase('application', 'octet-stream')
    attachment.set_payload(csv_bytes)
    encoders.encode_base64(attachment)
    filename = f"solar_readings_{week_start}_{week_end}.csv"
    attachment.add_header('Content-Disposition', f'attachment; filename="{filename}"')
    msg.attach(attachment)

    print("Connecting to smtp.gmail.com:587 ...")
    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, recipients, msg.as_string())

    print(f"Email sent to {', '.join(recipients)} ({row_count} rows attached)")


def main():
    config = load_config()
    rows = extract_last_7_days(LOG_FILE)
    data_rows = rows[1:]  # exclude header

    if not data_rows:
        print("No data in the last 7 days — email not sent.")
        return

    csv_bytes = build_csv_bytes(rows)
    send_email(config, csv_bytes, len(data_rows))


if __name__ == '__main__':
    main()
