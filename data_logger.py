import serial
import time
import csv
import os
import re

# ── Configuration ────────────────────────────────────────────────────────────
SERIAL_PORT = '/dev/ttyACM0'   # change to /dev/ttyUSB0 if needed
BAUD_RATE = 9600
LOG_FILE = 'data/readings.csv'
REFERENCE_IRRADIANCE = 1000.0  # W/m² (standard test condition)
MAX_RETRIES = 10
RETRY_DELAY = 10               # seconds between reconnect attempts
# ─────────────────────────────────────────────────────────────────────────────

os.makedirs('data', exist_ok=True)

if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, 'w', newline='') as f:
        csv.writer(f).writerow(['timestamp', 'irradiance_w_m2', 'efficiency_pct'])
    print(f"Created log file: {LOG_FILE}")


def extract_irradiance(line):
    """
    Parse a numeric irradiance value from an Arduino serial line.
    Handles bare floats ("850.23"), labelled values ("Irradiance: 850.23"),
    and multi-value lines ("ADC: 512, Irradiance: 850.23") by taking the last
    significant number.
    """
    line = line.strip()
    try:
        return float(line)
    except ValueError:
        pass

    numbers = re.findall(r'-?\d+\.?\d*', line)
    significant = [float(n) for n in numbers if abs(float(n)) > 0.01]
    if significant:
        return significant[-1]
    if numbers:
        return float(numbers[-1])
    return None


def run():
    retries = 0
    while retries < MAX_RETRIES:
        try:
            print(f"Connecting to {SERIAL_PORT} at {BAUD_RATE} baud …")
            ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
            print(f"Connected. Logging to {LOG_FILE}")
            retries = 0
            time.sleep(2)  # let Arduino reset after serial open

            with open(LOG_FILE, 'a', newline='') as f:
                writer = csv.writer(f)
                while True:
                    if ser.in_waiting > 0:
                        raw = ser.readline().decode('utf-8', errors='ignore').strip()
                        if not raw:
                            continue

                        irradiance = extract_irradiance(raw)
                        if irradiance is None:
                            print(f"  [skip] could not parse: '{raw}'")
                            continue

                        if not (0 <= irradiance <= 1500):
                            print(f"  [skip] out-of-range value: {irradiance} W/m²")
                            continue

                        ts = time.strftime('%Y-%m-%d %H:%M:%S')
                        efficiency = (irradiance / REFERENCE_IRRADIANCE) * 100
                        writer.writerow([ts, irradiance, efficiency])
                        f.flush()
                        print(f"[{ts}]  {irradiance:.2f} W/m²  |  {efficiency:.1f}%")

                    time.sleep(0.01)

        except serial.SerialException as e:
            retries += 1
            print(f"Serial error: {e}  (retry {retries}/{MAX_RETRIES} in {RETRY_DELAY}s)")
            time.sleep(RETRY_DELAY)

        except KeyboardInterrupt:
            print("\nStopped by user.")
            break

        except Exception as e:
            print(f"Unexpected error: {e}")
            break

    if retries >= MAX_RETRIES:
        print("Max retries reached. Exiting.")

    try:
        if 'ser' in locals() and ser.is_open:
            ser.close()
    except Exception:
        pass


if __name__ == '__main__':
    run()
