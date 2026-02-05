# Project Directory Structure

```
Python project/
│
├── .env.template              # Configuration template (copy to .env)
├── .gitignore                 # Git ignore patterns
├── requirements.txt           # Python dependencies
│
├── README.md                  # Main project documentation
├── SETUP_GUIDE.md            # Step-by-step setup instructions
├── QUICK_REFERENCE.md        # Command cheat sheet
├── PROJECT_SUMMARY.md        # Complete project overview
│
├── esp32/                     # ESP32-S3 Arduino code
│   ├── cool_tower/
│   │   └── cool_tower.ino    # Cool tower sensors + DHT22 + LED control
│   └── warm_tower/
│       └── warm_tower.ino    # Warm tower sensors + LED control
│
├── pi_zero/                   # Raspberry Pi Zero 2W camera scripts
│   ├── visible_camera.py     # Visible spectrum image capture
│   └── noir_camera.py        # Near-infrared image capture
│
├── rpi5/                      # Raspberry Pi 5 AI system
│   ├── hydro_ai_main.py      # Main orchestrator (entry point)
│   ├── sensor_monitor.py     # MQTT sensor monitoring & thresholds
│   ├── image_analyzer.py     # TensorFlow Lite ML inference
│   ├── sms_alerts.py         # Twilio SMS notifications
│   └── nutrient_advisor.py   # xAI Grok API integration
│
├── utils/                     # Utility scripts
│   ├── test_mqtt.py          # MQTT connectivity test
│   ├── calibration.py        # Sensor calibration guide
│   ├── setup_systemd.sh      # Auto-start service installer
│   └── quick_start.py        # System validation script
│
└── models/                    # Machine learning models
    └── README.md             # ML model training guide
```

## File Count Summary

- **Total Files**: 20
- **Python Scripts**: 9
- **Arduino Sketches**: 2
- **Documentation**: 5
- **Configuration**: 3
- **Shell Scripts**: 1

## Code Statistics

### Python Code (RPi5 AI System)
- **hydro_ai_main.py**: Main orchestrator (~250 lines)
- **sensor_monitor.py**: MQTT monitoring (~350 lines)
- **image_analyzer.py**: ML inference (~400 lines)
- **sms_alerts.py**: SMS alerts (~250 lines)
- **nutrient_advisor.py**: AI recommendations (~350 lines)

### Python Code (Pi Zero Cameras)
- **visible_camera.py**: Visible capture (~250 lines)
- **noir_camera.py**: IR capture (~250 lines)

### Python Code (Utilities)
- **test_mqtt.py**: MQTT test (~150 lines)
- **calibration.py**: Sensor calibration (~200 lines)
- **quick_start.py**: Validation (~200 lines)

### Arduino Code (ESP32)
- **cool_tower.ino**: Sensors + DHT22 (~350 lines)
- **warm_tower.ino**: Sensors only (~280 lines)

### Documentation
- **README.md**: Main docs (~400 lines)
- **SETUP_GUIDE.md**: Setup guide (~600 lines)
- **QUICK_REFERENCE.md**: Quick ref (~350 lines)
- **PROJECT_SUMMARY.md**: Summary (~300 lines)
- **models/README.md**: ML guide (~300 lines)

**Total Lines of Code**: ~5,200 lines

## Component Breakdown

### Hardware Components
```
Raspberry Pi 5 (16GB)
├── AI Hat 2 (for ML inference)
├── Ethernet (10.0.0.62)
└── WiFi (12BravoP)

4x Raspberry Pi Zero 2W
├── 2x Camera Module 3 (visible)
└── 2x Camera Module 3 NOIR (near-IR)

2x ESP32-S3
├── Atlas EC Mini (I2C 0x64)
├── Gen 3 pH (I2C 0x63)
├── DS18B20 (OneWire)
├── DHT22 (Cool tower only)
└── MOSFET LED controller
```

### Software Stack
```
Operating System
├── Raspberry Pi OS Trixie (64-bit)
└── libcamera + picamera2 support

Core Services
├── Mycodo (data logging + MQTT broker)
├── Mosquitto MQTT (communication)
└── InfluxDB (time-series storage)

Python Dependencies
├── paho-mqtt (MQTT client)
├── opencv-python (image processing)
├── tflite-runtime (ML inference)
├── twilio (SMS alerts)
└── requests (xAI Grok API)

Arduino Libraries
├── PubSubClient (MQTT)
├── ArduinoJson
├── OneWire
├── DallasTemperature
└── DHT sensor library
```

## Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                      Data Flow Diagram                      │
└─────────────────────────────────────────────────────────────┘

ESP32-S3 (Cool Tower)                    ESP32-S3 (Warm Tower)
├── EC Sensor ────┐                      ├── EC Sensor ────┐
├── pH Sensor ────┤                      ├── pH Sensor ────┤
├── Water Temp ───┤ MQTT publish         ├── Water Temp ───┤ MQTT publish
└── DHT22 ────────┘ every 60s            └─────────────────┘ every 60s
        │                                         │
        └──────────────┬──────────────────────────┘
                       │
                       ▼
            ┌──────────────────────┐
            │  Mosquitto MQTT      │
            │  (on RPi5)           │
            └──────────────────────┘
                       │
                       ▼
            ┌──────────────────────┐
            │  sensor_monitor.py   │
            │  - Threshold checks  │
            │  - Alert triggers    │
            └──────────────────────┘
                       │
                       ▼
            ┌──────────────────────┐
            │  hydro_ai_main.py    │
            │  - Orchestration     │
            │  - Decision making   │
            └──────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
        ▼              ▼              ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│ Image       │ │ Nutrient    │ │ SMS Alerts  │
│ Analyzer    │ │ Advisor     │ │             │
│ (ML/CV)     │ │ (xAI Grok)  │ │ (Twilio)    │
└─────────────┘ └─────────────┘ └─────────────┘
        │              │              │
        └──────────────┴──────────────┘
                       │
                       ▼
            Brian receives SMS alert
```

## Deployment Targets

| Device | IP Address | Software | Purpose |
|--------|-----------|----------|---------|
| RPi5 | 10.0.0.62 | hydro_ai_main.py | Master AI controller |
| Cool ESP32 | 10.0.0.63 | cool_tower.ino | Cool tower sensors |
| Warm ESP32 | 10.0.0.64 | warm_tower.ino | Warm tower sensors |
| Cool Visible Cam | 10.0.0.65 | visible_camera.py | Cool tower RGB |
| Cool NOIR Cam | 10.0.0.66 | noir_camera.py | Cool tower IR |
| Warm Visible Cam | 10.0.0.67 | visible_camera.py | Warm tower RGB |
| Warm NOIR Cam | 10.0.0.68 | noir_camera.py | Warm tower IR |

---

**Project Status**: ✅ Complete and ready for deployment

All 20 files created successfully. Follow SETUP_GUIDE.md for deployment.
