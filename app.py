from flask import Flask, render_template, Response, jsonify
import serial
import time
import csv
import threading
import os
import re

app = Flask(__name__)

# Configuration
SERIAL_PORT = '/dev/ttyACM0'  # Change to /dev/ttyUSB0 if needed
BAUD_RATE = 9600
LOG_FILE = 'data/readings.csv'
REFERENCE_IRRADIANCE = 1000.0  # W/m² (for efficiency calc)

# Global variable for latest reading
latest_reading = {"irradiance": 0.0, "efficiency": 0.0, "timestamp": ""}

# Create data directory if it doesn't exist
os.makedirs('data', exist_ok=True)

# Initialize CSV file with headers if it doesn't exist
if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['timestamp', 'irradiance', 'efficiency'])
    print(f"✓ Created new log file: {LOG_FILE}")


def extract_number(line):
    """
    Extract numeric value from various Arduino output formats.
    Handles cases like:
    - "850.23"
    - "Irradiance: 850.23"
    - "Value=850.23"
    - "850.23 W/m2"
    - "ADC: 512, Irradiance: 850.23"
    """
    # Remove any whitespace
    line = line.strip()
    
    # Try direct conversion first (fastest path)
    try:
        return float(line)
    except ValueError:
        pass
    
    # Try to find any floating point or integer number in the string
    # This regex finds numbers like: 123, 123.45, -123.45, .45
    numbers = re.findall(r'-?\d+\.?\d*', line)
    
    if numbers:
        # If multiple numbers found, look for the largest one (likely the irradiance value)
        # Filter out very small numbers that might be labels or indices
        valid_numbers = [float(n) for n in numbers if float(n) > 0.01 or float(n) < -0.01]
        if valid_numbers:
            # Return the last valid number (common pattern: "ADC: 512, Irradiance: 850.23")
            return valid_numbers[-1]
        elif numbers:
            return float(numbers[-1])
    
    return None


def read_serial():
    """
    Read data from Arduino via serial port with robust error handling
    """
    global latest_reading
    
    print("\n" + "="*60)
    print("SERIAL READER THREAD STARTING")
    print("="*60)
    
    retry_count = 0
    max_retries = 5
    
    while retry_count < max_retries:
        try:
            print(f"\n[{time.strftime('%H:%M:%S')}] Attempting to connect to {SERIAL_PORT}...")
            ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
            print(f"✓ Successfully connected to {SERIAL_PORT} at {BAUD_RATE} baud")
            print(f"✓ Serial port is open: {ser.is_open}")
            print(f"✓ Logging data to: {LOG_FILE}")
            print("\n" + "-"*60)
            print("WAITING FOR DATA FROM ARDUINO...")
            print("-"*60 + "\n")
            
            time.sleep(2)  # Wait for Arduino to reset after serial connection
            
            line_count = 0
            error_count = 0
            
            with open(LOG_FILE, 'a', newline='') as f:
                writer = csv.writer(f)
                
                while True:
                    if ser.in_waiting > 0:
                        try:
                            # Read line from serial
                            line = ser.readline().decode('utf-8', errors='ignore').strip()
                            
                            if line:
                                line_count += 1
                                timestamp_str = time.strftime('%Y-%m-%d %H:%M:%S')
                                
                                # Print raw data (first 100 lines, then every 10th)
                                if line_count <= 100 or line_count % 10 == 0:
                                    print(f"[{timestamp_str}] Raw: '{line}'")
                                
                                # Extract numeric value
                                irradiance = extract_number(line)
                                
                                if irradiance is not None:
                                    # Sanity check: irradiance should be between 0 and 1500 W/m²
                                    if 0 <= irradiance <= 1500:
                                        efficiency = (irradiance / REFERENCE_IRRADIANCE) * 100
                                        
                                        latest_reading = {
                                            "irradiance": irradiance,
                                            "efficiency": efficiency,
                                            "timestamp": timestamp_str
                                        }
                                        
                                        # Write to CSV
                                        writer.writerow([timestamp_str, irradiance, efficiency])
                                        f.flush()
                                        
                                        # Print parsed data (first 100 lines, then every 10th)
                                        if line_count <= 100 or line_count % 10 == 0:
                                            print(f"  ✓ Parsed: {irradiance:.2f} W/m² | Efficiency: {efficiency:.1f}%")
                                        
                                        # Reset error count on successful read
                                        error_count = 0
                                    else:
                                        print(f"  ⚠ Warning: Value out of range: {irradiance} W/m² (expected 0-1500)")
                                else:
                                    error_count += 1
                                    if error_count <= 10:  # Only show first 10 errors
                                        print(f"  ✗ Could not extract number from: '{line}'")
                                    elif error_count == 11:
                                        print(f"  ... (suppressing further parsing errors)")
                        
                        except UnicodeDecodeError as e:
                            print(f"  ✗ Unicode decode error: {e}")
                        except Exception as e:
                            print(f"  ✗ Error processing line: {e}")
                    
                    time.sleep(0.01)  # Small delay to prevent CPU hogging
                    
        except serial.SerialException as e:
            retry_count += 1
            print(f"\n✗ Serial Error: {e}")
            print(f"Retry {retry_count}/{max_retries} in 5 seconds...")
            print("\nTroubleshooting tips:")
            print("1. Check Arduino connection: ls -l /dev/tty*")
            print("2. Try different port: /dev/ttyUSB0 or /dev/ttyACM0")
            print("3. Check permissions: sudo usermod -a -G dialout $USER")
            print("4. Verify baud rate matches Arduino code")
            print("5. Make sure no other program is using the serial port")
            
            if retry_count < max_retries:
                time.sleep(5)
            else:
                print("\n✗ Max retries reached. Serial reader thread stopping.")
                return
        
        except KeyboardInterrupt:
            print("\n\n✗ Serial reader stopped by user")
            break
        
        except Exception as e:
            print(f"\n✗ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            break
    
    # Clean up
    try:
        if 'ser' in locals() and ser.is_open:
            ser.close()
            print("✓ Serial port closed")
    except:
        pass


@app.route('/')
def index():
    """Render main dashboard page"""
    return render_template('index.html')


@app.route('/data_stream')
def data_stream():
    """
    Server-Sent Events endpoint for real-time data streaming
    """
    def generate():
        last_sent = None
        while True:
            # Only send if data has changed
            if latest_reading != last_sent:
                data = f"data: {latest_reading}\n\n"
                yield data
                last_sent = latest_reading.copy()
            time.sleep(1)
    
    return Response(generate(), mimetype='text/event-stream')


@app.route('/get_logged_data')
def get_logged_data():
    """
    Return all logged data from CSV file
    """
    try:
        with open(LOG_FILE, 'r') as f:
            reader = csv.reader(f)
            rows = list(reader)
            # Skip header row if it exists
            if rows and rows[0][0] == 'timestamp':
                rows = rows[1:]
        return jsonify(rows)
    except FileNotFoundError:
        return jsonify([])
    except Exception as e:
        print(f"Error reading log file: {e}")
        return jsonify([])


@app.route('/status')
def status():
    """
    System status endpoint for debugging
    """
    return jsonify({
        "serial_port": SERIAL_PORT,
        "baud_rate": BAUD_RATE,
        "latest_reading": latest_reading,
        "log_file": LOG_FILE,
        "log_file_exists": os.path.exists(LOG_FILE)
    })


if __name__ == "__main__":
    print("\n" + "="*60)
    print("PYRANOMETER DASHBOARD SERVER")
    print("="*60)
    print(f"Serial Port: {SERIAL_PORT}")
    print(f"Baud Rate: {BAUD_RATE}")
    print(f"Log File: {LOG_FILE}")
    print(f"Server: http://0.0.0.0:5000")
    print("="*60 + "\n")
    
    # Start serial reader thread
    serial_thread = threading.Thread(target=read_serial, daemon=True)
    serial_thread.start()
    
    # Start Flask server
    app.run(host='0.0.0.0', port=5000, debug=False)