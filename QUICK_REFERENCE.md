# Quick Reference Guide

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    HYDROPONIC SYSTEM                        │
│                                                             │
│  ┌──────────────┐              ┌──────────────┐           │
│  │  Cool Tower  │              │  Warm Tower  │           │
│  │              │              │              │           │
│  │  Lettuce/    │              │  Basil/      │           │
│  │  Dill        │              │  Oregano     │           │
│  │              │              │              │           │
│  │  EC: 1.2-1.8 │              │  EC: 1.5-2.0 │           │
│  │  pH: 5.8-6.2 │              │  pH: 5.8-6.2 │           │
│  │  Temp: 60-70°F│             │  Temp: 70-80°F│          │
│  │              │              │              │           │
│  │  [Visible Cam]              │  [Visible Cam]           │
│  │  [NOIR Cam]  │              │  [NOIR Cam]  │           │
│  │  [ESP32-S3]  │              │  [ESP32-S3]  │           │
│  └──────┬───────┘              └──────┬───────┘           │
│         │         [DHT22]             │                   │
│         │            │                │                   │
│         └────────────┴────────────────┘                   │
│                      │                                     │
│              ┌───────▼────────┐                           │
│              │  Raspberry Pi 5 │                          │
│              │  (10.0.0.62)   │                           │
│              │                 │                           │
│              │  • Mycodo       │                           │
│              │  • MQTT Broker  │                           │
│              │  • AI Analysis  │                           │
│              │  • SMS Alerts   │                           │
│              └─────────────────┘                           │
└─────────────────────────────────────────────────────────────┘
```

## Quick Commands

### RPi5 - Main AI System

```bash
# Start AI system
python3 rpi5/hydro_ai_main.py

# Start as service
sudo systemctl start hydro-ai-main

# View logs
sudo journalctl -u hydro-ai-main -f

# Stop service
sudo systemctl stop hydro-ai-main
```

### Testing

```bash
# Validate setup
python3 utils/quick_start.py

# Test MQTT
python3 utils/test_mqtt.py

# Calibrate sensors
python3 utils/calibration.py
```

### MQTT Commands

```bash
# Subscribe to all topics
mosquitto_sub -h 10.0.0.62 -u hydro_user -P PASSWORD -t '#' -v

# Publish test value
mosquitto_pub -h 10.0.0.62 -u hydro_user -P PASSWORD \
  -t '/cool_tower/ec' -m '1.5'

# Control LED intensity
mosquitto_pub -h 10.0.0.62 -u hydro_user -P PASSWORD \
  -t '/warm_tower/led_intensity' -m '50'
```

## Nutrient Recipes (5 Gallons)

### Cool Tower (Lettuce/Dill)
```
1. Buffer: 5ml CalMagic + 10g Calcium Nitrate
2. Base: 10-12g Lettuce Fertilizer 8-15-36
3. Supplements: 5g Epsom Salt, 5ml Armor Si
4. Mix, aerate, pH to 5.8-6.2
5. Wait 60min → Add 10ml Hydroguard
Target: EC 1.2-1.8, pH 5.8-6.2
```

### Warm Tower (Basil/Oregano)
```
1. Buffer: 5ml CalMagic
2. Base: 10g MaxiGrow (1 big + 1 little scoop)
3. Supplements: 5ml Armor Si, 1-2g Epsom Salt
4. Mix, aerate, pH to 5.8-6.2
5. Wait 60min → Add 10ml Hydroguard
Target: EC 1.5-2.0, pH 5.8-6.2
```

## Threshold Values

| Metric | Cool Tower | Warm Tower |
|--------|-----------|-----------|
| EC Min | 1.2 mS/cm | 1.5 mS/cm |
| EC Max | 1.8 mS/cm | 2.0 mS/cm |
| pH Min | 5.8 | 5.8 |
| pH Max | 6.2 | 6.2 |
| Water Temp Max | 75°F | 75°F |
| Air Temp Max | 70°F | 80°F |
| Humidity Min | 50% | 50% |
| Humidity Max | 70% | 60% |

## Common Issues & Solutions

### EC Low
```
Cool: Add 5-8g Lettuce Fertilizer
Warm: Add ~5g MaxiGrow (small scoop)
```

### EC High
```
Dilute with 0.5-1 gal RO water
If >10% over: Fresh reservoir change
```

### pH High (>6.2)
```
Add 0.5ml pH Down
Wait 30min, retest
If unstable >24h: Fresh reservoir
```

### Tip Burn (Calcium Deficiency)
```
Apply foliar Ca spray (5ml CalMagic per liter)
Check air flow and humidity (50-70%)
Increase air circulation
```

### Yellowing (Nitrogen Deficiency)
```
Cool: Add 5g Lettuce Fertilizer
Warm: Add small scoop MaxiGrow
```

### Heat Stress
```
Cool reservoir
Dim LEDs to 50%
Increase air circulation
```

## MQTT Topics

### Sensor Data (Published by ESP32)
```
/cool_tower/ec
/cool_tower/ph
/cool_tower/water_temp
/warm_tower/ec
/warm_tower/ph
/warm_tower/water_temp
/environment/air_temp
/environment/humidity
```

### Camera Images (Published by Pi Zero)
```
/cool_tower/camera/visible
/cool_tower/camera/noir
/warm_tower/camera/visible
/warm_tower/camera/noir
```

### Control Commands (Subscribe by ESP32)
```
/cool_tower/led_intensity   (0-100)
/warm_tower/led_intensity   (0-100)
```

## File Locations

```
RPi5:
  Code:    ~/Python project/
  Images:  ~/hydro_images/
  Logs:    ~/hydro_logs/
  Mycodo:  http://10.0.0.62:8080

Pi Zero:
  Script:  ~/visible_camera.py or ~/noir_camera.py
  Images:  ~/hydro_images/

ESP32:
  Flash:   Arduino IDE → esp32/cool_tower/ or warm_tower/
```

## Maintenance Schedule

### Daily
- [ ] Check SMS alerts
- [ ] Visual plant inspection

### Weekly
- [ ] Top up reservoirs (50% strength)
- [ ] Export Mycodo logs
- [ ] Harvest mature plants

### Bi-Weekly (7-10 days)
- [ ] Full reservoir change
- [ ] Clean system components

### Monthly
- [ ] Calibrate pH & EC sensors
- [ ] Review ML accuracy
- [ ] Deep clean system

## Emergency Contacts

- System Logs: `~/hydro_logs/hydro_ai.log`
- Mycodo Dashboard: http://10.0.0.62:8080
- SMS Alerts: Configured in .env

## Useful Commands

### Check Service Status
```bash
sudo systemctl status hydro-ai-main
sudo systemctl status mosquitto
```

### View Real-time Logs
```bash
# AI System
sudo journalctl -u hydro-ai-main -f

# Mosquitto
sudo journalctl -u mosquitto -f

# All system logs
tail -f ~/hydro_logs/hydro_ai.log
```

### Network Diagnostics
```bash
# Ping devices
ping 10.0.0.62    # RPi5
ping 10.0.0.63    # Cool Tower ESP32
ping 10.0.0.64    # Warm Tower ESP32

# Check WiFi
iwconfig
```

### Backup Data
```bash
# Backup Mycodo database
mycodo-backup create

# Export sensor data to CSV
# Via Mycodo web interface: Data → Export

# Backup images
rsync -avz ~/hydro_images/ /mnt/backup/hydro_images/
```

## System URLs

- **Mycodo Dashboard**: http://10.0.0.62:8080
- **MQTT Broker**: mqtt://10.0.0.62:1883
- **Image Storage**: ~/hydro_images/
- **Log Files**: ~/hydro_logs/

---

**For detailed setup**: See SETUP_GUIDE.md  
**For troubleshooting**: See README.md → Troubleshooting section  
**For code details**: See inline comments in Python/Arduino files
