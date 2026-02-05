# Pydro: Dual Tower Hydroponic System with AI

**Phase 1 Complete!** 🎉 Comprehensive AI-powered monitoring, plant tracking, automated dosing, VPD monitoring, Alexa integration, and Home Assistant connectivity.

> *Smarter hydroponic growing through artificial intelligence*

## 🌟 Key Features

### Core Monitoring
- ✅ Real-time sensor monitoring (EC, pH, water temp, air temp, humidity)
- ✅ Dual camera system (visible + NOIR) per tower
- ✅ TensorFlow Lite AI deficiency detection
- ✅ SMS alerts via Twilio
- ✅ xAI Grok API nutrient recommendations

### Phase 1 Enhancements
- 🆕 **VPD Monitoring** - Optimal plant transpiration tracking
- 🆕 **Individual Plant Tracking** - Seed-to-harvest lifecycle (C01A format)
- 🆕 **Image Quality Scoring** - AI rates all photos, keeps 10/10 forever
- 🆕 **Automated Dosing** - 8 peristaltic pumps with AI-calculated doses
- 🆕 **Planting Scheduler** - Staggered plantings for continuous harvests
- 🆕 **Alexa Integration** - Voice control + Echo Show 21 dashboard
- 🆕 **Home Assistant** - MQTT Discovery with arrival notifications
- 🆕 **NFS File Sharing** - Centralized image storage

## 📦 Quick Links

- **[PHASE_1_SUMMARY.md](PHASE_1_SUMMARY.md)** - Complete Phase 1 feature guide
- **[SETUP_GUIDE.md](SETUP_GUIDE.md)** - Detailed installation instructions
- **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** - Command cheat sheet
- **[PROJECT_SUMMARY.md](PROJECT_SUMMARY.md)** - Original project overview

## System Architecture

### Hardware Components
- **Master Controller**: Raspberry Pi 5 (16GB, IP: 10.0.0.62) with AI Hat 2
- **Sensor Controllers**: 
  - 2x ESP32-S3 (one per tower for sensors + LEDs)
  - 1x ESP32 (dosing pump controller - 8 pumps)
- **Cameras**: 4x Pi Zero 2W with Raspberry Pi Camera Module 3 (2 visible + 2 NOIR)
- **Towers**: 
  - **Cool Tower**: Lettuce/Dill (EC 1.2-1.8, Temp 60-70°F, up to 30 plants)
  - **Warm Tower**: Basil/Oregano (EC 1.5-2.0, Temp 70-80°F, up to 30 plants)
- **Dosing Pumps**: 8x peristaltic (Epsom salt, Ca-Nitrate, pH Down, K-Bicarbonate × 2)

### Sensors (Per Tower)
- Atlas EC Mini (I2C 0x64)
- Gen 3 pH (I2C 0x63)
- DS18B20 (water temperature, OneWire)
- DHT22 (air temp/humidity - Cool Tower only, shared)

### Communication
- **Protocol**: MQTT via Mosquitto broker on RPi5
- **Topics** (short format):
  - `/cool/ec`, `/cool/ph`, `/cool/water_temp`, `/cool/air_temp`, `/cool/air_humidity`
  - `/cool/vpd`, `/cool/led`, `/cool/pump/command`, `/cool/planting_schedule`
  - `/warm/ec`, `/warm/ph`, `/warm/water_temp`, `/warm/vpd`, `/warm/led`
  - `/plants/{plant_id}`, `/events/harvest`, `/alerts/*`, `/pumps/status`

## Directory Structure

```
Pydro/
├── .env.template              # Configuration template (Phase 1 enhanced)
├── .gitignore
├── requirements.txt           # Python dependencies (updated)
├── README.md                  # This file
├── PHASE_1_SUMMARY.md         # Phase 1 complete feature guide
├── SETUP_GUIDE.md
├── QUICK_REFERENCE.md
├── PROJECT_SUMMARY.md
├── DEPLOYMENT_CHECKLIST.md
│
├── esp32/                     # ESP32 firmware
│   ├── cool_tower/cool_tower.ino       # Cool sensors + DHT22
│   ├── warm_tower/warm_tower.ino       # Warm sensors
│   └── dosing_pumps/dosing_pumps.ino   # 8-pump controller (NEW)
│
├── pi_zero/                   # Camera scripts
│   ├── visible_camera.py
│   └── noir_camera.py
│
├── rpi5/                      # AI & Control scripts
│   ├── hydro_ai_main.py       # Main orchestrator
│   ├── sensor_monitor.py      # MQTT sensor monitoring
│   ├── image_analyzer.py      # ML deficiency detection
│   ├── sms_alerts.py          # Twilio SMS
│   ├── nutrient_advisor.py    # xAI Grok integration
│   ├── vpd_monitor.py         # VPD calculation (NEW)
│   ├── plant_tracker.py       # Plant lifecycle (NEW)
│   ├── image_quality_scorer.py # AI image rating (NEW)
│   ├── dosing_controller.py   # Automated dosing (NEW)
│   ├── planting_scheduler.py  # Planting calendar (NEW)
│   ├── alexa_integration.py   # Alexa + Echo Show (NEW)
│   └── ha_bridge.py           # Home Assistant (NEW)
│
├── utils/                     # Utility scripts
│   ├── test_mqtt.py
│   ├── calibration.py
│   ├── setup_systemd.sh       # Auto-start services
│   ├── quick_start.py
│   ├── nfs_setup.sh           # NFS automation (NEW)
│   └── validate_config.py     # Config validation (NEW)
│
└── data/                      # Auto-created databases
    ├── plants.db              # Plant tracking
    ├── images.db              # Image metadata
    └── dosing.db              # Dosing history
```

## 🚀 Quick Start

### 1. Configuration

```bash
# Navigate to project
cd "/Users/brianaltmaier/Python project"

# Copy environment template
cp .env.template .env

# Edit configuration (add your credentials)
nano .env
```

**Required settings in `.env`**:
- `MQTT_BROKER`, `MQTT_USERNAME`, `MQTT_PASSWORD`
- `WIFI_SSID`, `WIFI_PASSWORD`
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` (for SMS)
- `XAI_API_KEY` (for Grok AI recommendations)

### 2. Validate Configuration

```bash
# Run pre-flight checks
python3 utils/validate_config.py
```

This checks:
- ✓ All environment variables set
- ✓ MQTT broker reachable
- ✓ Network hosts available
- ✓ Directories created
- ✓ API credentials valid

### 3. Setup NFS File Sharing

```bash
# On RPi5 (run first)
sudo bash utils/nfs_setup.sh

# On each Pi Zero 2W camera (after RPi5)
sudo bash utils/nfs_setup.sh
```

### 4. Deploy System

```bash
# Install Python dependencies
pip3 install -r requirements.txt

# Install as systemd services (auto-start on boot)
sudo bash utils/setup_systemd.sh

# Or run manually for testing
python3 rpi5/hydro_ai_main.py
python3 rpi5/vpd_monitor.py
python3 rpi5/plant_tracker.py
python3 rpi5/dosing_controller.py
python3 rpi5/alexa_integration.py
python3 rpi5/ha_bridge.py
```

### 5. Flash ESP32 Firmware

Upload Arduino sketches to each ESP32:
- **Cool Tower**: `esp32/cool_tower/cool_tower.ino`
- **Warm Tower**: `esp32/warm_tower/warm_tower.ino`
- **Dosing Pumps**: `esp32/dosing_pumps/dosing_pumps.ino`

### 6. Setup Cameras (Pi Zero 2W)

```bash
# On each Pi Zero
python3 pi_zero/visible_camera.py  # For visible cameras
python3 pi_zero/noir_camera.py     # For NOIR cameras
```

## 🎮 Usage Examples

### Voice Control (Alexa)

```
"Alexa, ask Pydro for cool tower status"
"Alexa, ask Pydro which plants are ready for harvest"
"Alexa, ask Pydro about recent alerts"
```

### Plant Management

```bash
# Register a new plant
mosquitto_pub -h 10.0.0.62 -u hydro_user -P password \
  -t "/plants/C01A/command" \
  -m '{"command":"plant_seed", "variety":"lettuce", "section":1}'

# Check planting schedule
mosquitto_sub -h 10.0.0.62 -u hydro_user -P password \
  -t "/cool/planting_schedule"
```

### Manual Dosing

```bash
# Dose 10 mL of Epsom salt to cool tower
mosquitto_pub -h 10.0.0.62 -u hydro_user -P password \
  -t "/cool/pump/command" \
  -m '{"solution":"epsom_salt", "volume_ml":10, "reason":"Mg supplement"}'
```

### Monitor Sensors

```bash
# Subscribe to all cool tower sensors
mosquitto_sub -h 10.0.0.62 -u hydro_user -P password -t "/cool/#"

# Watch VPD
mosquitto_sub -h 10.0.0.62 -u hydro_user -P password -t "/cool/vpd_status"
```

## Setup Instructions (Detailed)

### 1. Raspberry Pi 5 Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Mycodo (includes Mosquitto MQTT broker)
curl -L https://kizniche.github.io/Mycodo/install | bash

# Install dependencies
cd "/Users/brianaltmaier/Python project"
pip3 install -r requirements.txt

# Create directories
mkdir -p ~/hydro_images ~/hydro_logs ~/hydro_data

# Set up systemd services
sudo bash utils/setup_systemd.sh
```

### 2. Pi Zero 2W Setup (Repeat for all 4 cameras)

```bash
# Enable camera
sudo raspi-config  # Interface Options -> Camera -> Enable

# Install dependencies
sudo apt install -y python3-picamera2 python3-pip
pip3 install paho-mqtt python-dotenv

# Copy camera script
scp pi_zero/visible_camera.py pi@<PI_ZERO_IP>:~/
# OR for NOIR cameras:
scp pi_zero/noir_camera.py pi@<PI_ZERO_IP>:~/

# Set up auto-start (on Pi Zero)
sudo nano /etc/systemd/system/hydro_camera.service
sudo systemctl enable hydro_camera.service
sudo systemctl start hydro_camera.service
```

### 3. ESP32-S3 Setup

1. Install Arduino IDE with ESP32 board support
2. Install libraries:
   - PubSubClient (MQTT)
   - ArduinoJson
   - OneWire
   - DallasTemperature
   - DHT sensor library (for Cool Tower only)
3. Open appropriate `.ino` file from `esp32/` folder
4. Update WiFi and MQTT credentials (or use .env values)
5. Flash to each ESP32-S3

### 4. Mycodo Configuration

1. Access Mycodo web interface: `http://10.0.0.62:8080`
2. Add MQTT Inputs:
   - Topic: `/cool_tower/ec`, Unit: mS/cm
   - Topic: `/cool_tower/ph`, Unit: pH
   - Topic: `/cool_tower/water_temp`, Unit: °F
   - (Repeat for warm tower and environment)
3. Enable InfluxDB for data logging
4. Configure PID controllers for regulation (optional)

## Initial Nutrient Recipes

### Warm Tower (Basil/Oregano - 5 Gallons)
1. Add 5ml CalMagic (buffer)
2. Add 1 big scoop + 1 little scoop MaxiGrow (~10g)
3. Add 5ml Armor Si
4. Optional: 1-2g Epsom Salt
5. Stir, aerate, adjust pH to 5.8-6.2
6. Target EC: 1.5-2.0 mS/cm
7. Wait 60min, then add 10ml Hydroguard

### Cool Tower (Lettuce/Dill - 5 Gallons)
1. Add 5ml CalMagic + 10g Calcium Nitrate (buffer)
2. Add 10-12g Lettuce Fertilizer 8-15-36
3. Add 5g Epsom Salt
4. Add 5ml Armor Si
5. Stir, aerate, adjust pH to 5.8-6.2
6. Target EC: 1.2-1.8 mS/cm
7. Wait 60min, then add 10ml Hydroguard

## Monitoring Thresholds

### Automated AI Alerts
- **EC Low**: <1.2 (Cool) / <1.5 (Warm) → Add fertilizer
- **EC High**: >1.8 (Cool) / >2.0 (Warm) → Dilute or fresh change
- **pH Off**: <5.8 or >6.2 → Add pH Down or suggest fresh change
- **Water Temp High**: >75°F → Cool reservoir
- **Air Temp**: >70°F (Cool) / >80°F (Warm) → Reduce heat, dim LEDs
- **Humidity**: <50% or >70% → Adjust air flow/humidifier

### Camera Deficiency Detection
- **Tip Burn**: Brown edges → Foliar Ca + air flow
- **Yellowing**: N deficiency → Add base fertilizer
- **Purple Veins**: P deficiency → Boost fertilizer
- **Harvest Ready**: Full leaves/head formation → Alert
- **Bolting**: Elongated stems/buds → "Harvest soon"

## SMS Alert Format

```
Brian, [Tower]: [Issue] | Suggestion: [Action] | Data: [Values] | Time: [Timestamp]

Example:
Brian, Cool Tower: Tip burn detected | Suggestion: Apply foliar Ca, check air flow | Data: pH 6.4, Humidity 72%, EC 1.3 | Time: 2026-02-04 14:30
```

## Maintenance Schedule

### Daily
- Review AI SMS alerts
- Visual plant inspection

### Weekly
- Top up reservoirs (50% strength mix based on EC drop)
- Export Mycodo CSV logs for analysis
- Harvest mature plants/trim

### Bi-Weekly (7-10 Days)
- Full reservoir change (AI will alert)
- Deep clean system components

### Monthly
- Calibrate sensors (pH, EC)
- Review ML model performance
- System deep clean

## Troubleshooting

### MQTT Connection Issues
```bash
# Test MQTT broker
python3 utils/test_mqtt.py

# Check Mosquitto status
sudo systemctl status mosquitto

# View logs
tail -f /var/log/mosquitto/mosquitto.log
```

### Sensor Calibration
```bash
# Run calibration utility
python3 utils/calibration.py
```

### Camera Issues
```bash
# Test camera on Pi Zero
libcamera-hello --list-cameras
libcamera-jpeg -o test.jpg
```

### Check AI Script Logs
```bash
tail -f ~/hydro_logs/hydro_ai.log
```

## Future Expansions

- [ ] Dosage pumps on third ESP32-S3 (automated nutrient dosing)
- [ ] M.2 NVMe storage expansion
- [ ] Manual DO probe integration ($80 Amazon probe)
- [ ] Time-lapse growth tracking
- [ ] Fine-tuned ML models (95%+ accuracy)
- [ ] Advanced Grok API forecasting

## Safety Notes

- Always wear gloves when handling nutrients
- Ensure electrical components are waterproof/isolated
- Monitor for water leaks regularly
- Keep pH Down away from children/pets
- Backup Mycodo data to M.2 drive regularly

## License

Personal project - Brian Altmaier © 2026
