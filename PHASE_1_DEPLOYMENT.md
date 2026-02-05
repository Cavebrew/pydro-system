# Pydro Phase 1 Deployment Checklist

Complete pre-deployment verification for your dual tower hydroponic AI system.

---

## 🔧 Hardware Checklist

### Raspberry Pi 5 (Master Controller)
- [X] RPi5 16GB with 500GB NVMe SSD installed
- [X] AI Hat 2 installed and recognized
- [X] Assigned static IP: 10.0.0.62
- [X] Connected to network switch/router
- [X] Power supply connected (USB-C 5V/5A)

### ESP32 Controllers
- [ ] Cool Tower ESP32-S3 at IP 10.0.0.63
- [ ] Warm Tower ESP32-S3 at IP 10.0.0.64
- [ ] Dosing Pump ESP32 flashed and powered
- [ ] All ESP32s connect to WiFi: "12BravoP"

### Pi Zero 2W Cameras (4 units)
- [ ] Cool Visible Camera (IP: 10.0.0.65)
- [ ] Cool NOIR Camera (IP: 10.0.0.66)
- [ ] Warm Visible Camera (IP: 10.0.0.67)
- [ ] Warm NOIR Camera (IP: 10.0.0.68)
- [ ] All cameras enabled via `raspi-config`
- [ ] Camera Module 3 connected to each

### Sensors (Per Tower)
**Cool Tower:**
- [X] Atlas EC Mini (I2C 0x64)
- [X] Gen 3 pH (I2C 0x63)
- [X] DS18B20 water temp (OneWire)
- [X] DHT22 air temp/humidity

**Warm Tower:**
- [X] Atlas EC Mini (I2C 0x64)
- [X] Gen 3 pH (I2C 0x63)
- [X] DS18B20 water temp (OneWire)

### Dosing Pumps (8 total)
**Cool Tower (Pumps 1-4):**
- [ ] Pump 1: Epsom Salt solution (GPIO 12)
- [ ] Pump 2: Calcium Nitrate solution (GPIO 13)
- [ ] Pump 3: pH Down solution (GPIO 14)
- [ ] Pump 4: Potassium Bicarbonate solution (GPIO 15)

**Warm Tower (Pumps 5-8):**
- [ ] Pump 5: Epsom Salt solution (GPIO 16)
- [ ] Pump 6: Calcium Nitrate solution (GPIO 17)
- [ ] Pump 7: pH Down solution (GPIO 18)
- [ ] Pump 8: Potassium Bicarbonate solution (GPIO 19)

### Network
- [ ] All devices on same network (10.0.0.x/24)
- [ ] Internet connectivity for API calls
- [ ] Router port forwarding (if using remote access)
- [ ] Tailscale installed (optional but recommended)

---

## 💻 Software Installation

### Raspberry Pi 5
- [X] Raspberry Pi OS (64-bit) installed
- [X] System updated: `sudo apt update && sudo apt upgrade`
- [X] Mycodo installed (includes Mosquitto MQTT)
- [X] Python 3.10+ installed
- [X] pip3 and virtualenv available
- [ ] Git installed
- [ ] NFS server packages: `sudo apt install nfs-kernel-server`

### Python Dependencies
```bash
cd "/Users/brianaltmaier/Python project"
pip3 install -r requirements.txt
```

**Verify these are installed:**
- [ ] paho-mqtt
- [ ] python-dotenv
- [ ] twilio
- [ ] requests
- [ ] opencv-python
- [ ] numpy
- [ ] Pillow
- [ ] Flask
- [ ] Flask-Ask
- [ ] pandas
- [ ] psutil

### Pi Zero 2W (Each Camera)
- [ ] Raspberry Pi OS Lite installed
- [ ] Camera interface enabled
- [ ] Python 3 and pip3 installed
- [ ] `picamera2` library installed
- [ ] NFS client packages: `sudo apt install nfs-common`
- [ ] Camera scripts copied

### ESP32 Firmware
- [ ] Arduino IDE installed or PlatformIO
- [ ] ESP32 board support added
- [ ] Required libraries installed:
  - [ ] WiFi.h
  - [ ] PubSubClient
  - [ ] Wire (I2C)
  - [ ] OneWire
  - [ ] DallasTemperature
  - [ ] DHT
  - [ ] ArduinoJson

**Firmware uploaded:**
- [ ] `esp32/cool_tower/cool_tower.ino` → Cool Tower ESP32
- [ ] `esp32/warm_tower/warm_tower.ino` → Warm Tower ESP32
- [ ] `esp32/dosing_pumps/dosing_pumps.ino` → Dosing Pump ESP32

---

## 🔐 Configuration

### Environment Variables (.env)
```bash
cd "/Users/brianaltmaier/Python project"
cp .env.template .env
nano .env
```

**Required settings:**
- [ ] `MQTT_BROKER=10.0.0.62`
- [ ] `MQTT_USERNAME=hydro_user`
- [ ] `MQTT_PASSWORD=<your_secure_password>`
- [ ] `WIFI_SSID=12BravoP`
- [ ] `WIFI_PASSWORD=$apper!2B10`
- [ ] `TWILIO_ACCOUNT_SID=<your_sid>`
- [ ] `TWILIO_AUTH_TOKEN=<your_token>`
- [ ] `TWILIO_FROM_PHONE=<your_number>`
- [ ] `TWILIO_TO_PHONE=<your_number>`
- [ ] `XAI_API_KEY=<your_grok_key>`

**Optional but recommended:**
- [ ] `EMAIL_FROM` (for weekly reports)
- [ ] `EMAIL_PASSWORD`
- [ ] `TAILSCALE_HOSTNAME=pydro-ai`
- [ ] `ALEXA_SKILL_ID=<your_skill_id>`

### MQTT Broker Setup
```bash
# Create MQTT user
sudo mosquitto_passwd -c /etc/mosquitto/passwd hydro_user

# Configure mosquitto.conf
sudo nano /etc/mosquitto/mosquitto.conf
```

Add these lines:
```
listener 1883
allow_anonymous false
password_file /etc/mosquitto/passwd
```

Restart:
```bash
sudo systemctl restart mosquitto
```

**Verify:**
- [ ] Mosquitto running: `sudo systemctl status mosquitto`
- [ ] Can connect: `python3 utils/test_mqtt.py`

### NFS File Sharing
```bash
# On RPi5
sudo bash utils/nfs_setup.sh

# On each Pi Zero
sudo bash utils/nfs_setup.sh
```

**Verify:**
- [ ] RPi5 exports visible: `showmount -e 10.0.0.62`
- [ ] Pi Zeros can mount: `df -h | grep nfs`
- [ ] Write test successful on all cameras

### Directory Structure
```bash
# RPi5
mkdir -p ~/hydro_images ~/hydro_logs ~/hydro_data
mkdir -p ~/hydro_images/{cool,warm}/{visible,noir}
mkdir -p ~/hydro_images/{archive,perfect,harvests}
```

**Verify permissions:**
```bash
ls -la ~/hydro_images
# Should show: drwxr-xr-x pi pi
```

---

## ✅ Pre-Flight Testing

### 1. Configuration Validation
```bash
python3 utils/validate_config.py
```

**Should pass:**
- [ ] All environment variables set
- [ ] MQTT connection successful
- [ ] Network hosts reachable
- [ ] Directories created
- [ ] No critical errors

### 2. MQTT Communication Test
```bash
# Terminal 1: Subscribe to all topics
mosquitto_sub -h 10.0.0.62 -u hydro_user -P <password> -t "/#" -v

# Terminal 2: Publish test message
mosquitto_pub -h 10.0.0.62 -u hydro_user -P <password> \
  -t "/test/hello" -m "Pydro online"
```

**Verify:**
- [ ] Message appears in Terminal 1

### 3. Sensor Data Flow
Power on ESP32 controllers and watch MQTT:
```bash
mosquitto_sub -h 10.0.0.62 -u hydro_user -P <password> -t "/cool/#" -v
```

**Should see (within 60 seconds):**
- [ ] `/cool/ph` - pH reading
- [ ] `/cool/ec` - EC reading  
- [ ] `/cool/water_temp` - Water temperature
- [ ] `/cool/air_temp` - Air temperature
- [ ] `/cool/air_humidity` - Humidity
- [ ] `/cool/status` - ESP32 status

Repeat for `/warm/#`

### 4. Camera Test
```bash
# On Cool Visible camera Pi Zero
python3 pi_zero/visible_camera.py --test

# Check RPi5 for image
ls -lh ~/hydro_images/cool/visible/
```

**Verify:**
- [ ] Image captured
- [ ] Saved to NFS mount
- [ ] MQTT metadata published

### 5. VPD Monitor Test
```bash
python3 rpi5/vpd_monitor.py
```

**Watch MQTT:**
```bash
mosquitto_sub -h 10.0.0.62 -u hydro_user -P <password> -t "/+/vpd_status"
```

**Should see:**
- [ ] VPD calculated for both towers
- [ ] Status (low/optimal/high)
- [ ] Recommendations

### 6. Plant Tracker Test
```bash
python3 rpi5/plant_tracker.py
```

**Add test plant via MQTT:**
```bash
mosquitto_pub -h 10.0.0.62 -u hydro_user -P <password> \
  -t "/plants/command" \
  -m '{"command":"plant_seed", "tower":"cool", "section":1, "position":"A", "variety":"lettuce"}'
```

**Verify:**
- [ ] Plant registered with ID C01A
- [ ] Database created: `~/hydro_data/plants.db`
- [ ] MQTT status published to `/plants/C01A`

### 7. Dosing Pump Safety Test
```bash
# Start controller
python3 rpi5/dosing_controller.py
```

**Test pump (2 second burst):**
```bash
mosquitto_pub -h 10.0.0.62 -u hydro_user -P <password> \
  -t "/cool/pump/command" \
  -m '{"pump_id":1, "run_time_seconds":2}'
```

**Verify:**
- [ ] Pump 1 runs for 2 seconds
- [ ] Stops automatically
- [ ] Status published to `/pumps/status`
- [ ] Logged in `~/hydro_data/dosing.db`

### 8. Image Quality Scorer Test
```bash
python3 rpi5/image_quality_scorer.py
```

**Trigger with test image:**
```bash
mosquitto_pub -h 10.0.0.62 -u hydro_user -P <password> \
  -t "/images/new" \
  -m '{"path":"~/hydro_images/cool/visible/test.jpg", "tower":"cool", "camera_type":"visible"}'
```

**Verify:**
- [ ] Image scored (1-10)
- [ ] Metadata in `~/hydro_data/images.db`
- [ ] 10/10 images moved to `/perfect/`

### 9. Home Assistant Discovery
```bash
python3 rpi5/ha_bridge.py
```

**In Home Assistant:**
- [ ] Navigate to Configuration → Integrations
- [ ] MQTT integration shows new devices
- [ ] Sensors visible: `sensor.cool_tower_ph`, etc.
- [ ] Lights visible: `light.cool_tower_led`

### 10. Alexa Integration Test
```bash
python3 rpi5/alexa_integration.py
```

**Test Alexa:**
- [ ] "Alexa, ask Pydro for cool tower status"
- [ ] Alexa responds with sensor readings
- [ ] Echo Show displays visual dashboard (if configured)

---

## 🚀 Production Deployment

### Install as Systemd Services
```bash
sudo bash utils/setup_systemd.sh
```

**Services created:**
- [ ] `hydro-main.service` - Main orchestrator
- [ ] `hydro-vpd.service` - VPD monitor
- [ ] `hydro-plants.service` - Plant tracker
- [ ] `hydro-images.service` - Image quality scorer
- [ ] `hydro-dosing.service` - Dosing controller
- [ ] `hydro-alexa.service` - Alexa integration
- [ ] `hydro-ha.service` - Home Assistant bridge

**Enable and start:**
```bash
sudo systemctl enable hydro-*.service
sudo systemctl start hydro-*.service
```

**Verify all running:**
```bash
sudo systemctl status hydro-*.service
```

### Camera Auto-Start (Pi Zero)
```bash
# Add to crontab
crontab -e

# Add line:
@reboot sleep 30 && python3 /home/pi/visible_camera.py &
```

### Watchdog Setup (Optional)
```bash
sudo apt install watchdog
sudo systemctl enable watchdog
```

Prevents system hang if process crashes.

---

## 📊 Monitoring

### View Logs
```bash
# All services
sudo journalctl -u hydro-* -f

# Specific service
sudo journalctl -u hydro-main.service -f

# Application logs
tail -f ~/hydro_logs/*.log
```

### MQTT Dashboard
```bash
# Real-time sensor stream
mosquitto_sub -h 10.0.0.62 -u hydro_user -P <password> -t "/#" -v
```

### Database Inspection
```bash
# Plant tracking
sqlite3 ~/hydro_data/plants.db "SELECT * FROM plants;"

# Image quality
sqlite3 ~/hydro_data/images.db "SELECT filename, quality_score FROM images ORDER BY quality_score DESC LIMIT 10;"

# Dosing history
sqlite3 ~/hydro_data/dosing.db "SELECT * FROM dose_history WHERE DATE(dose_date) = DATE('now');"
```

---

## 🔐 Security Checklist

- [ ] Changed default MQTT password
- [ ] `.env` file has restricted permissions (600)
- [ ] `.env` added to `.gitignore`
- [ ] Firewall configured (UFW or iptables)
- [ ] SSH key-based authentication
- [ ] Tailscale VPN for remote access (instead of port forwarding)
- [ ] Regular backups of databases
- [ ] Auto-dosing disabled until tested: `ENABLE_AUTO_DOSING=false`

---

## 🆘 Troubleshooting

### MQTT Not Connecting
```bash
# Check broker status
sudo systemctl status mosquitto

# Test connection
mosquitto_sub -h 10.0.0.62 -p 1883 -u hydro_user -P <password> -t "/test"

# Check logs
sudo journalctl -u mosquitto -f
```

### Sensors Not Reporting
```bash
# Check ESP32 serial output
# Connect via USB and open Arduino Serial Monitor

# Verify I2C addresses
i2cdetect -y 1

# Should see 0x63 (pH) and 0x64 (EC)
```

### NFS Mount Failed
```bash
# On RPi5: Check exports
sudo exportfs -v

# On Pi Zero: Test mount manually
sudo mount -t nfs 10.0.0.62:/home/pi/hydro_images /mnt/hydro_images
```

### Python Service Won't Start
```bash
# Check logs
sudo journalctl -u hydro-main.service -n 50

# Test manually
cd "/Users/brianaltmaier/Python project"
python3 rpi5/hydro_ai_main.py
```

### Database Locked
```bash
# Check permissions
ls -la ~/hydro_data/

# Fix if needed
sudo chown -R pi:pi ~/hydro_data
chmod 644 ~/hydro_data/*.db
```

---

## ✅ Final Verification

Once everything is running, verify end-to-end:

1. **Sensors** → MQTT → Database
   - [ ] All sensor readings updating every 60 seconds
   - [ ] VPD calculations correct
   - [ ] Alerts triggering on threshold violations

2. **Cameras** → NFS → Quality Scoring
   - [ ] Images captured every 4 hours
   - [ ] Saved to NFS mount
   - [ ] Quality scored and organized

3. **Plant Tracking**
   - [ ] Can add new plants
   - [ ] Growth stages tracked
   - [ ] Harvest predictions accurate

4. **Dosing System**
   - [ ] Manual doses work
   - [ ] Safety limits enforced
   - [ ] History logged

5. **Alexa Integration**
   - [ ] Voice commands responsive
   - [ ] Echo Show displays correct data

6. **Home Assistant**
   - [ ] All sensors discovered
   - [ ] Arrival notifications working

---

## 🎉 You're Live!

**Your Pydro system is now operational!**

Monitor via:
- 📱 SMS alerts (critical events)
- 🗣️ Alexa voice commands
- 🏠 Home Assistant dashboard
- 📧 Weekly email reports
- 💻 Direct MQTT monitoring

**Recommended first actions:**
1. Plant first batch of lettuce (Cool tower)
2. Plant first batch of basil (Warm tower)
3. Monitor VPD and adjust environment
4. Calibrate dosing pump volumes
5. Review image quality scores
6. Fine-tune alert thresholds

**Next: Phase 2!**
- Web dashboard
- Predictive analytics
- Time-lapse videos
- Mobile app

---

**Happy Growing! 🌱**
