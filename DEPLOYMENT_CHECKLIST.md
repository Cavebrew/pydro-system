# Deployment Checklist

Use this checklist to track your progress deploying the system.

---

## Phase 1: Preparation (On Your Mac)

- [ ] Review all documentation files
  - [ ] Read README.md
  - [ ] Read SETUP_GUIDE.md
  - [ ] Review QUICK_REFERENCE.md for commands
  
- [ ] Configure credentials
  - [ ] Copy .env.template to .env
  - [ ] Set MQTT_BROKER (10.0.0.62)
  - [ ] Set MQTT_USERNAME (pydro)
  - [ ] Set MQTT_PASSWORD (kiki053083)
  - [ ] Set TWILIO_ACCOUNT_SID (from twilio.com)
  - [ ] Set TWILIO_AUTH_TOKEN (from twilio.com)
  - [ ] Set TWILIO_FROM_PHONE (your Twilio number)
  - [ ] Set TWILIO_TO_PHONE (your personal number)
  - [ ] Set XAI_API_KEY (from x.ai)
  - [ ] Verify WiFi credentials (12BravoP / $apper!2B10)

- [ ] Purchase required items (if not already owned)
  - [ ] Twilio account with SMS credits
  - [ ] xAI Grok API access (optional but recommended)
  - [ ] pH calibration solutions (4.0, 7.0, 10.0)
  - [ ] EC calibration solution (1413 μS/cm)
  - [ ] Nutrient supplies (see README.md)

---

## Phase 2: Raspberry Pi 5 Setup

- [ ] Hardware
  - [ ] Install Raspberry Pi OS Trixie (64-bit)
  - [ ] Set hostname: rpi5-hydro
  - [ ] Configure static IP: 10.0.0.62
  - [ ] Install AI Hat 2 (if available)
  - [ ] Connect to network (Ethernet recommended)

- [ ] Software Installation
  - [ ] Update system: `sudo apt update && sudo apt upgrade -y`
  - [ ] **CRITICAL:** Install build dependencies (must do BEFORE Mycodo):
    ```bash
    sudo apt install -y python3-setuptools python3-wheel python3-dev build-essential gawk nginx git curl libopenblas-dev
    ```
  - [ ] Clean previous failed installation (if any): `sudo rm -rf /opt/Mycodo`
  - [ ] **CRITICAL:** Install Mycodo with wheels-only flag (forces use of pre-built wheels, not source):
    ```bash
    PIP_ONLY_BINARY=:all: curl -L https://kizniche.github.io/Mycodo/install | bash
    ```
  - [ ] **IMPORTANT:** After Mycodo installation, fix Python 3.13 compatibility:
    ```bash
    sudo bash -c "cd /opt/Mycodo && source env/bin/activate && pip install setuptools wheel && pip install 'SQLAlchemy>=2.0.36'"
    ```
  - [ ] Restart Mycodo services:
    ```bash
    sudo systemctl restart mycodo.service mycodoflask.service
    ```
  - [ ] Verify Mycodo is running: `curl -o /dev/null -w "%{http_code}" http://localhost` (should return 302)
  - [x] Configure Mosquitto MQTT broker
    - [x] Create user: `sudo mosquitto_passwd -c /etc/mosquitto/passwd pydro`
    - [x] Configure auth in /etc/mosquitto/mosquitto.conf
    - [x] Restart Mosquitto: `sudo systemctl restart mosquitto`
  - [x] Transfer project files (from Mac): `scp -r /tmp/pydro-system/* pi@10.0.0.62:~/pydro-system/`
  - [x] **OR if already on RPi5:** Copy files locally: `cp -r /tmp/pydro-system/* ~/pydro-system/`
  - [x] Install Python dependencies: `cd ~/pydro-system && pip3 install -r requirements.txt`

- [x] Configuration
  - [x] Copy .env to RPi5 (configured with Twilio + Grok API credentials)
  - [x] Create directories: `mkdir -p ~/hydro_images ~/hydro_logs`
  - [x] Set permissions: `chmod 755 ~/hydro_images ~/hydro_logs`

- [x] Testing
  - [x] Run validation: `python3 utils/quick_start.py` (5/5 checks PASS ✓)
  - [x] Test MQTT: `python3 utils/test_mqtt.py` (verified working with pydro/kiki053083)
  - [x] Check Mycodo dashboard: Services running (daemon + flask) on port 8080

- [x] Service Installation
  - [x] Install systemd service: `sudo systemctl enable hydro-ai-main`
  - [x] Enable auto-start: Service enabled and ready to start
  - [x] System ready (waiting for sensors before starting)

---

## Phase 3: ESP32-S3 Setup (Cool Tower)

- [ ] Hardware
  - [ ] Wire Atlas EC Mini to I2C (address 0x64)
  - [ ] Wire Gen 3 pH to I2C (address 0x63)
  - [ ] Wire DS18B20 to GPIO 4 (OneWire)
  - [ ] Wire DHT22 to GPIO 15
  - [ ] Wire MOSFET LED controller to GPIO 25 (PWM)
  - [ ] Verify all isolation boards installed

- [ ] Software
  - [ ] Install Arduino IDE
  - [ ] Install ESP32 board support
  - [ ] Install libraries: PubSubClient, ArduinoJson, OneWire, DallasTemperature, DHT
  - [ ] Open esp32/cool_tower/cool_tower.ino
  - [ ] Update WiFi credentials (lines 17-18)
  - [ ] Update MQTT credentials (lines 21-24)
  - [ ] Select board: ESP32S3 Dev Module
  - [ ] Flash firmware
  
- [ ] Testing
  - [ ] Open Serial Monitor (115200 baud)
  - [ ] Verify WiFi connection
  - [ ] Verify MQTT connection
  - [ ] Check sensor readings

- [ ] Calibration
  - [ ] Run `python3 utils/calibration.py` on RPi5
  - [ ] Calibrate pH sensor (3-point: 4.0, 7.0, 10.0)
  - [ ] Calibrate EC sensor (2-point: dry, 1413)
  - [ ] Verify readings are accurate

---

## Phase 4: ESP32-S3 Setup (Warm Tower)

- [ ] Hardware
  - [ ] Wire Atlas EC Mini to I2C (address 0x64)
  - [ ] Wire Gen 3 pH to I2C (address 0x63)
  - [ ] Wire DS18B20 to GPIO 4 (OneWire)
  - [ ] Wire MOSFET LED controller to GPIO 25 (PWM)
  - [ ] Verify all isolation boards installed

- [ ] Software
  - [ ] Open esp32/warm_tower/warm_tower.ino
  - [ ] Update WiFi credentials
  - [ ] Update MQTT credentials
  - [ ] Flash firmware

- [ ] Testing
  - [ ] Open Serial Monitor
  - [ ] Verify WiFi and MQTT connections
  - [ ] Check sensor readings

- [ ] Calibration
  - [ ] Calibrate pH sensor (3-point)
  - [ ] Calibrate EC sensor (2-point)
  - [ ] Verify accuracy

---

## Phase 5: Pi Zero 2W Setup (Cool Tower Visible)

- [ ] Hardware
  - [ ] Flash SD card with Raspberry Pi OS Lite
  - [ ] Set hostname: cool-visible
  - [ ] Configure WiFi: 12BravoP
  - [ ] Enable SSH
  - [ ] Connect Camera Module 3 (visible)

- [ ] Software
  - [ ] Boot and SSH in
  - [ ] Update system: `sudo apt update && sudo apt upgrade -y`
  - [ ] Install dependencies: `sudo apt install -y python3-picamera2`
  - [ ] Install Python packages: `pip3 install paho-mqtt python-dotenv`
  - [ ] Enable camera: `sudo raspi-config` → Interface Options → Camera

- [ ] Deployment
  - [ ] Transfer script: `scp pi_zero/visible_camera.py pi@cool-visible.local:~/`
  - [ ] Transfer .env: `scp .env pi@cool-visible.local:~/`
  - [ ] Set TOWER_NAME env var: `export TOWER_NAME=cool`

- [ ] Testing
  - [ ] Test camera: `libcamera-jpeg -o test.jpg`
  - [ ] Run script manually: `python3 visible_camera.py`
  - [ ] Verify MQTT publishing

- [ ] Auto-start
  - [ ] Create systemd service (see SETUP_GUIDE.md)
  - [ ] Enable: `sudo systemctl enable hydro-camera`
  - [ ] Start: `sudo systemctl start hydro-camera`

---

## Phase 6: Pi Zero 2W Setup (Cool Tower NOIR)

- [ ] Repeat Phase 5 steps with these changes:
  - [ ] Hostname: cool-noir
  - [ ] Script: noir_camera.py
  - [ ] Camera: Camera Module 3 NOIR
  - [ ] TOWER_NAME: cool

---

## Phase 7: Pi Zero 2W Setup (Warm Tower Visible)

- [ ] Repeat Phase 5 steps with these changes:
  - [ ] Hostname: warm-visible
  - [ ] Script: visible_camera.py
  - [ ] Camera: Camera Module 3 (visible)
  - [ ] TOWER_NAME: warm

---

## Phase 8: Pi Zero 2W Setup (Warm Tower NOIR)

- [ ] Repeat Phase 5 steps with these changes:
  - [ ] Hostname: warm-noir
  - [ ] Script: noir_camera.py
  - [ ] Camera: Camera Module 3 NOIR
  - [ ] TOWER_NAME: warm

---

## Phase 9: Final Integration

- [ ] Start all services
  - [ ] Verify all 4 Pi Zero cameras are running
  - [ ] Verify both ESP32 devices are publishing
  - [ ] Start RPi5 AI system: `sudo systemctl start hydro-ai-main`

- [ ] System Verification
  - [ ] Check MQTT topics: `mosquitto_sub -h 10.0.0.62 -u pydro -P kiki053083 -t '#' -v`
  - [ ] Verify sensor data flowing (every 60s)
  - [ ] Verify camera metadata publishing (every 4h during lights-on)
  - [ ] Check logs: `sudo journalctl -u hydro-ai-main -f`

- [ ] Test Alerts
  - [ ] Trigger test alert: publish out-of-range pH value
  - [ ] Verify SMS received
  - [ ] Check SMS format and content

- [ ] Mycodo Configuration
  - [ ] Access dashboard: http://10.0.0.62:8080
  - [ ] Add MQTT inputs for all sensor topics
  - [ ] Configure graphs and dashboards
  - [ ] Enable InfluxDB data logging
  - [ ] Set up email notifications (optional)

---

## Phase 10: Hydroponic System Preparation

- [ ] Tower Assembly
  - [ ] 3D print tower components (PETG)
  - [ ] Assemble with M3x6 bolts/nuts
  - [ ] Install in growing area

- [ ] Plumbing
  - [ ] Install VIVOSUN 800GPH pumps in reservoirs
  - [ ] Connect 3/8" ID tubing
  - [ ] Install air stones with diffusers
  - [ ] Test for leaks

- [ ] Lighting
  - [ ] Install LED ring lights
  - [ ] Connect to MOSFET controllers
  - [ ] Test PWM dimming (0-100%)
  - [ ] Set schedule: 6:00 AM - 10:00 PM

- [ ] Reservoir Preparation
  - [ ] Clean 5-gallon buckets
  - [ ] Fill with RO or dechlorinated water
  - [ ] Mix nutrients per recipes (see README.md)
  - [ ] Adjust pH to 5.8-6.2
  - [ ] Verify target EC (Cool: 1.2-1.8, Warm: 1.5-2.0)
  - [ ] Wait 60 minutes, add Hydroguard

---

## Phase 11: Plant Installation

- [ ] Cool Tower (Lettuce/Dill)
  - [ ] Prepare rockwool cubes or jiffy pots
  - [ ] Transplant seedlings
  - [ ] Verify water flow to roots
  - [ ] Start pump (24/7 or ebb-and-flow)

- [ ] Warm Tower (Basil/Oregano)
  - [ ] Prepare rockwool cubes or jiffy pots
  - [ ] Transplant seedlings
  - [ ] Verify water flow
  - [ ] Start pump

---

## Phase 12: Monitoring & Optimization

- [ ] Week 1 Observations
  - [ ] Monitor SMS alerts daily
  - [ ] Check pH/EC daily (manual verification)
  - [ ] Adjust nutrient mix if needed
  - [ ] Observe plant health visually

- [ ] Week 2 Optimizations
  - [ ] Fine-tune EC/pH thresholds based on plant response
  - [ ] Adjust camera capture frequency if needed
  - [ ] Review Mycodo graphs for trends
  - [ ] Top up reservoirs (50% strength)

- [ ] Week 3-4 Analysis
  - [ ] Export Mycodo CSV data
  - [ ] Analyze EC/pH trends
  - [ ] Review ML model predictions vs. actual issues
  - [ ] Collect images for model retraining

---

## Ongoing Maintenance

### Daily
- [ ] Review SMS alerts
- [ ] Visual plant inspection
- [ ] Check system logs for errors

### Weekly
- [ ] Top up reservoirs (50% strength mix)
- [ ] Export Mycodo data
- [ ] Harvest mature plants
- [ ] Trim as needed

### Bi-Weekly (7-10 days)
- [ ] Full reservoir change
- [ ] Clean reservoir and pump
- [ ] Inspect tubing for algae/blockages

### Monthly
- [ ] Calibrate pH and EC sensors
- [ ] Deep clean entire system
- [ ] Review ML model performance
- [ ] Update thresholds based on data
- [ ] Backup all logs and images

---

## Success Metrics

System is fully operational when:
- ✅ All sensors publish data every 60 seconds
- ✅ All cameras capture images every 4 hours
- ✅ AI system analyzes and sends alerts
- ✅ LEDs adjust automatically for heat stress
- ✅ Nutrient recommendations are actionable
- ✅ Plants show healthy growth
- ✅ No critical alerts for >24 hours
- ✅ First successful harvest!

---

## Troubleshooting Quick Links

- System won't start: See SETUP_GUIDE.md → Troubleshooting
- MQTT issues: Run `python3 utils/test_mqtt.py`
- Sensor problems: Run `python3 utils/calibration.py`
- SMS not working: Check Twilio credentials in .env
- Cameras not capturing: Check systemd service status

---

**Current Phase**: _____ (Mark your current phase)

**Started**: __________ (Date)

**Completed**: __________ (Date)

**Notes**: 
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________

---

Good luck! 🌱 You've got this!
