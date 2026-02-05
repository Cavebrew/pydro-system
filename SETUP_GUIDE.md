# SETUP_GUIDE.md - Comprehensive Installation Guide

## Complete Setup Guide for Dual Tower Hydroponic AI System

This guide walks you through setting up the entire system from scratch.

---

## Table of Contents

1. [Hardware Setup](#hardware-setup)
2. [Raspberry Pi 5 Setup](#raspberry-pi-5-setup)
3. [Pi Zero 2W Camera Setup](#pi-zero-2w-camera-setup)
4. [ESP32-S3 Setup](#esp32-s3-setup)
5. [Testing & Validation](#testing--validation)
6. [Troubleshooting](#troubleshooting)

---

## Hardware Setup

### Tower Assembly

1. **3D Print Tower Components**
   - Download model from Printables #720081
   - Print in PETG filament (food-safe, water-resistant)
   - Assemble sections with 18x M3x6 bolts/nuts per tower

2. **Reservoir Setup**
   - Use 5-gallon buckets as base
   - Install VIVOSUN 800GPH submersible pump
   - Connect 3/8" ID x 1/2" OD clear vinyl tubing
   - Install air stones with diffusers for oxygenation

3. **LED Grow Lights**
   - Install LED ring lights per tower section
   - Connect to MOSFET controllers (controlled by ESP32)
   - Set light schedule: 6:00 AM - 10:00 PM

### Sensor Installation

**Per Tower (ESP32-S3):**
- Atlas EC Mini (I2C address 0x64) - calibrate before use
- Gen 3 pH sensor (I2C address 0x63) - calibrate before use
- DS18B20 waterproof temperature sensor (OneWire, pin 4)

**Shared (on Cool Tower ESP32):**
- DHT22 air temp/humidity sensor (pin 15)

**Wiring:**
- Ensure proper isolation boards for Atlas sensors
- Use waterproof cable glands for reservoir penetrations
- Label all cables clearly

---

## Raspberry Pi 5 Setup

### 1. Install Raspberry Pi OS

```bash
# Use Raspberry Pi Imager to flash microSD card
# Choose: Raspberry Pi OS (64-bit) - Trixie release
# Enable SSH, set hostname, WiFi, user credentials

# After first boot, update system
sudo apt update && sudo apt upgrade -y
```

### 2. Configure Network

```bash
# Set static IP (optional but recommended)
sudo nmcli con mod "Wired connection 1" ipv4.addresses 10.0.0.62/24
sudo nmcli con mod "Wired connection 1" ipv4.method manual
sudo nmcli con up "Wired connection 1"

# Verify
ip addr show
```

### 3. Install Mycodo

```bash
# Mycodo includes Mosquitto MQTT broker and monitoring tools
curl -L https://kizniche.github.io/Mycodo/install | bash

# Follow installation prompts
# Default web interface: http://10.0.0.62:8080
```

### 4. Configure MQTT Broker

```bash
# Edit Mosquitto config
sudo nano /etc/mosquitto/mosquitto.conf

# Add:
allow_anonymous false
password_file /etc/mosquitto/passwd

# Create user
sudo mosquitto_passwd -c /etc/mosquitto/passwd hydro_user
# Enter password when prompted

# Restart Mosquitto
sudo systemctl restart mosquitto
sudo systemctl status mosquitto
```

### 5. Install Python Dependencies

```bash
cd ~
git clone https://github.com/yourusername/hydroponic-ai.git "Python project"
cd "Python project"

# Install system dependencies
sudo apt install -y python3-pip python3-opencv python3-picamera2

# Install Python packages
pip3 install -r requirements.txt
```

### 6. Configure Environment

```bash
# Copy template
cp .env.template .env

# Edit configuration
nano .env

# Fill in:
# - MQTT credentials (set above)
# - Twilio credentials (from twilio.com)
# - xAI Grok API key (from x.ai)
# - WiFi credentials
```

### 7. Create Directories

```bash
mkdir -p ~/hydro_images ~/hydro_logs

# Set permissions
chmod 755 ~/hydro_images ~/hydro_logs
```

### 8. Test Installation

```bash
# Run validation script
python3 utils/quick_start.py

# Test MQTT
python3 utils/test_mqtt.py
```

### 9. Install as System Service

```bash
sudo bash utils/setup_systemd.sh

# Start service
sudo systemctl start hydro-ai-main

# Check status
sudo systemctl status hydro-ai-main

# View logs
sudo journalctl -u hydro-ai-main -f
```

---

## Pi Zero 2W Camera Setup

**Repeat for all 4 cameras (2 visible, 2 NOIR)**

### 1. Prepare SD Card

```bash
# Use Raspberry Pi Imager
# OS: Raspberry Pi OS Lite (64-bit)
# Configure:
#   - Hostname: cool-visible (or cool-noir, warm-visible, warm-noir)
#   - WiFi: SSID "12BravoP", password "$apper!2B10"
#   - Enable SSH
#   - Username: pi
```

### 2. First Boot Setup

```bash
# SSH into Pi Zero
ssh pi@cool-visible.local

# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3-pip python3-picamera2
pip3 install paho-mqtt python-dotenv
```

### 3. Enable Camera

```bash
# Enable camera interface
sudo raspi-config
# Navigate to: Interface Options > Camera > Enable

# Reboot
sudo reboot
```

### 4. Deploy Camera Script

```bash
# From your computer, copy script to Pi Zero
scp pi_zero/visible_camera.py pi@cool-visible.local:~/
# OR for NOIR:
scp pi_zero/noir_camera.py pi@cool-noir.local:~/

# Also copy .env (with MQTT credentials)
scp .env pi@cool-visible.local:~/
```

### 5. Test Camera

```bash
# On Pi Zero, test camera
libcamera-jpeg -o test.jpg

# Test script manually
python3 visible_camera.py
# (Ctrl+C to stop)
```

### 6. Setup Auto-Start

```bash
# On Pi Zero
sudo nano /etc/systemd/system/hydro-camera.service

# Paste (adjust script name):
[Unit]
Description=Hydroponic Camera Capture
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi
ExecStart=/usr/bin/python3 /home/pi/visible_camera.py
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target

# Save and enable
sudo systemctl daemon-reload
sudo systemctl enable hydro-camera
sudo systemctl start hydro-camera

# Check status
sudo systemctl status hydro-camera
```

### 7. Network File Share (Optional)

For RPi5 to access images directly:

```bash
# On Pi Zero, install Samba
sudo apt install -y samba

# Share /home/pi/hydro_images
sudo nano /etc/samba/smb.conf

# Add:
[hydro_images]
path = /home/pi/hydro_images
read only = yes
guest ok = no
valid users = pi

# Restart Samba
sudo systemctl restart smbd

# On RPi5, mount share
sudo mkdir /mnt/cool_visible
sudo mount -t cifs //cool-visible.local/hydro_images /mnt/cool_visible -o username=pi
```

---

## ESP32-S3 Setup

### 1. Install Arduino IDE

```bash
# Download from arduino.cc
# Install ESP32 board support:
# File > Preferences > Additional Board Manager URLs:
https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json

# Tools > Board > Boards Manager
# Search "ESP32" and install "esp32" by Espressif
```

### 2. Install Libraries

In Arduino IDE:
- Tools > Manage Libraries
- Install:
  - `PubSubClient` (MQTT)
  - `ArduinoJson`
  - `OneWire`
  - `DallasTemperature`
  - `DHT sensor library` (for Cool Tower only)

### 3. Flash Cool Tower ESP32

```bash
# Open: esp32/cool_tower/cool_tower.ino

# Edit WiFi/MQTT credentials (lines 17-24):
const char* ssid = "12BravoP";
const char* password = "$apper!2B10";
const char* mqtt_server = "10.0.0.62";
const char* mqtt_user = "hydro_user";
const char* mqtt_password = "YOUR_MQTT_PASSWORD";

# Select board: ESP32S3 Dev Module
# Select port: /dev/ttyUSB0 (or COM port on Windows)

# Upload sketch
# Monitor serial output (115200 baud)
```

### 4. Flash Warm Tower ESP32

```bash
# Open: esp32/warm_tower/warm_tower.ino
# Edit credentials (same as above)
# Upload sketch
```

### 5. Verify MQTT Publishing

```bash
# On RPi5, listen to topics
mosquitto_sub -h 10.0.0.62 -u hydro_user -P YOUR_PASSWORD -t '/cool_tower/#' -v
mosquitto_sub -h 10.0.0.62 -u hydro_user -P YOUR_PASSWORD -t '/warm_tower/#' -v

# You should see sensor readings every 60 seconds
```

### 6. Calibrate Sensors

**CRITICAL: Calibrate before use!**

```bash
# Run calibration utility on RPi5
python3 utils/calibration.py

# Follow prompts for pH and EC calibration
# Use calibration solutions (pH 4.0, 7.0, 10.0; EC 1413 μS/cm)
```

---

## Testing & Validation

### 1. System Health Check

```bash
# On RPi5
python3 utils/quick_start.py

# Should show all green checkmarks
```

### 2. End-to-End Test

```bash
# Start AI system
python3 rpi5/hydro_ai_main.py

# Observe logs for:
# - MQTT connections
# - Sensor readings
# - Image captures (every 4 hours during lights-on)
# - Alerts triggered
```

### 3. Test SMS Alerts

```bash
# In Python interpreter
python3
>>> from rpi5.sms_alerts import SMSAlertSystem
>>> sms = SMSAlertSystem()
>>> sms.test_connection()

# Check your phone for test message
```

### 4. Simulate Sensor Alert

```bash
# Publish out-of-range value to trigger alert
mosquitto_pub -h 10.0.0.62 -u hydro_user -P YOUR_PASSWORD \
  -t '/cool_tower/ph' -m '6.8'

# Should receive SMS alert about high pH
```

---

## Troubleshooting

### MQTT Connection Issues

```bash
# Check Mosquitto is running
sudo systemctl status mosquitto

# View logs
sudo journalctl -u mosquitto -f

# Test connection
mosquitto_pub -h 10.0.0.62 -u hydro_user -P YOUR_PASSWORD \
  -t '/test' -m 'hello'
mosquitto_sub -h 10.0.0.62 -u hydro_user -P YOUR_PASSWORD \
  -t '/test'
```

### Camera Not Working

```bash
# On Pi Zero
libcamera-hello --list-cameras

# Should show camera detected
# If not, check ribbon cable connection

# Check service logs
sudo journalctl -u hydro-camera -f
```

### Sensors Not Reading

```bash
# Check I2C devices
i2cdetect -y 1

# Should show:
# 0x63 (pH sensor)
# 0x64 (EC sensor)

# If missing, check wiring and power
```

### AI System Not Starting

```bash
# Check logs
sudo journalctl -u hydro-ai-main -f

# Common issues:
# - Missing .env file
# - Invalid MQTT credentials
# - Python dependencies not installed

# Run manual test
python3 rpi5/hydro_ai_main.py
```

### SMS Not Sending

```bash
# Verify Twilio credentials in .env
# Check account balance at twilio.com
# Test with:
python3 -c "from rpi5.sms_alerts import SMSAlertSystem; \
  sms = SMSAlertSystem(); sms.test_connection()"
```

---

## Maintenance

### Daily
- Check SMS alerts
- Visual plant inspection

### Weekly
- Top up reservoirs (50% strength mix)
- Export Mycodo logs
- Harvest mature plants

### Bi-Weekly (7-10 days)
- Full reservoir change
- Clean system components

### Monthly
- Calibrate pH and EC sensors
- Review ML model performance
- Deep clean system

---

## Next Steps

1. **Fine-tune ML Model**: Collect images of your specific plants and retrain model for 95%+ accuracy
2. **Add Dosing Pumps**: Implement automated nutrient dosing on third ESP32-S3
3. **Expand Storage**: Install M.2 NVMe drive for log backups
4. **Time-Lapse**: Enable growth tracking videos
5. **Advanced Analytics**: Use Mycodo InfluxDB data for VPD optimization

---

For questions or issues, refer to the README.md or check logs in `~/hydro_logs/`.

**System Status Dashboard**: http://10.0.0.62:8080 (Mycodo)
