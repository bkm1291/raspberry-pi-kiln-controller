import os
import time
import board
import digitalio
import busio
import adafruit_max31855
import RPi.GPIO as GPIO
from flask import Flask, request, jsonify

app = Flask(__name__)

# GPIO pin assignments
SSR_PIN = 27       # CH2 on relay (for SSR trigger)
FAN_PIN = 17       # CH1 on relay (for cooling fan)

GPIO.setmode(GPIO.BCM)
GPIO.setup(SSR_PIN, GPIO.OUT)
GPIO.setup(FAN_PIN, GPIO.OUT)
GPIO.output(SSR_PIN, GPIO.LOW)
GPIO.output(FAN_PIN, GPIO.LOW)

# SPI setup for MAX31855
spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
cs = digitalio.DigitalInOut(board.D5)
thermocouple = adafruit_max31855.MAX31855(spi, cs)

# Kiln control variables
set_temp = 1000  # degrees F
start_time = None
log_data = []

def c_to_f(c):
    return c * 9.0 / 5.0 + 32.0

def get_cpu_temp():
    raw = os.popen("vcgencmd measure_temp").readline()
    return float(raw.replace("temp=", "").replace("'C\n", ""))

def handle_fan():
    cpu_temp = get_cpu_temp()
    if cpu_temp >= 60:
        GPIO.output(FAN_PIN, GPIO.HIGH)
    elif cpu_temp <= 50:
        GPIO.output(FAN_PIN, GPIO.LOW)

def kiln_loop():
    global start_time
    while True:
        temp_c = thermocouple.temperature
        temp_f = c_to_f(temp_c)
        handle_fan()

        if start_time:
            elapsed = time.time() - start_time
            if temp_f < set_temp:
                GPIO.output(SSR_PIN, GPIO.HIGH)
            else:
                GPIO.output(SSR_PIN, GPIO.LOW)
            log_data.append((elapsed, temp_f))
        else:
            GPIO.output(SSR_PIN, GPIO.LOW)

        time.sleep(5)

@app.route("/")
def index():
    return jsonify({
        "status": "online",
        "current_temp_f": c_to_f(thermocouple.temperature)
    })

@app.route("/start", methods=["POST"])
def start():
    global set_temp, start_time
    set_temp = float(request.form.get("set_temp", 1000))
    start_time = time.time()
    return jsonify({"status": "firing started", "set_temp": set_temp})

@app.route("/stop", methods=["POST"])
def stop():
    global start_time
    start_time = None
    GPIO.output(SSR_PIN, GPIO.LOW)
    return jsonify({"status": "firing stopped"})

@app.route("/log")
def log():
    return jsonify(log_data)

if __name__ == "__main__":
    import threading
    thread = threading.Thread(target=kiln_loop)
    thread.daemon = True
    thread.start()
    app.run(host="0.0.0.0", port=5000)
