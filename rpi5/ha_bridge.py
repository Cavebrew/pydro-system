#!/usr/bin/env python3
"""
Home Assistant MQTT Discovery Bridge
Automatically creates Home Assistant entities for all Pydro sensors and controls

Features:
- Auto-discovery via MQTT
- Sensor entities for pH, EC, temp, VPD
- Binary sensors for alerts
- Number entities for dosing controls
- Camera entities for plant images
- Arrival-based notifications via Alexa
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict
import paho.mqtt.client as mqtt
from dotenv import load_dotenv
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

class HomeAssistantBridge:
    def __init__(self):
        # MQTT Configuration
        self.broker = os.getenv("MQTT_BROKER", "10.0.0.62")
        self.port = int(os.getenv("MQTT_PORT", 1883))
        self.username = os.getenv("MQTT_USERNAME", "hydro_user")
        self.password = os.getenv("MQTT_PASSWORD", "")
        
        # Home Assistant Configuration
        self.discovery_prefix = os.getenv("HA_MQTT_DISCOVERY_PREFIX", "homeassistant")
        self.device_name = "Pydro"
        self.device_id = "pydro_ai_hydro_system"
        
        # MQTT client
        self.client = mqtt.Client()
        self.client.username_pw_set(self.username, self.password)
        self.client.on_connect = self.on_connect
        
        # Track user presence for arrival notifications
        self.user_home = False
        self.pending_announcements = []
        
        logger.info("Home Assistant Bridge initialized")
    
    def create_device_config(self) -> Dict:
        """Create device configuration for HA"""
        return {
            "identifiers": [self.device_id],
            "name": self.device_name,
            "model": "Dual Tower Hydroponic System",
            "manufacturer": "Pydro",
            "sw_version": "1.0.0"
        }
    
    def publish_sensor_discovery(self, tower: str, sensor_type: str, config: Dict):
        """Publish MQTT discovery message for a sensor"""
        # Create unique ID
        object_id = f"{tower}_{sensor_type}"
        unique_id = f"{self.device_id}_{object_id}"
        
        # Discovery topic
        discovery_topic = f"{self.discovery_prefix}/sensor/{self.device_id}/{object_id}/config"
        
        # Base configuration
        discovery_config = {
            "name": f"{tower.capitalize()} Tower {config.get('name', sensor_type)}",
            "unique_id": unique_id,
            "state_topic": f"/{tower}/{sensor_type}",
            "device": self.create_device_config(),
            "object_id": object_id,
        }
        
        # Merge with provided config
        discovery_config.update(config)
        
        # Publish
        self.client.publish(discovery_topic, json.dumps(discovery_config), retain=True)
        logger.info(f"Published discovery for {tower} {sensor_type}")
    
    def setup_all_sensors(self):
        """Setup all sensor discoveries"""
        towers = ["cool", "warm"]
        
        # pH sensors
        for tower in towers:
            self.publish_sensor_discovery(tower, "ph", {
                "name": "pH",
                "unit_of_measurement": "pH",
                "device_class": "ph",
                "state_class": "measurement",
                "icon": "mdi:ph"
            })
        
        # EC sensors
        for tower in towers:
            self.publish_sensor_discovery(tower, "ec", {
                "name": "EC",
                "unit_of_measurement": "mS/cm",
                "state_class": "measurement",
                "icon": "mdi:flash"
            })
        
        # Water temperature
        for tower in towers:
            self.publish_sensor_discovery(tower, "water_temp", {
                "name": "Water Temperature",
                "unit_of_measurement": "°F",
                "device_class": "temperature",
                "state_class": "measurement",
                "icon": "mdi:thermometer-water"
            })
        
        # Air temperature
        for tower in towers:
            self.publish_sensor_discovery(tower, "air_temp", {
                "name": "Air Temperature",
                "unit_of_measurement": "°F",
                "device_class": "temperature",
                "state_class": "measurement",
                "icon": "mdi:thermometer"
            })
        
        # Air humidity
        for tower in towers:
            self.publish_sensor_discovery(tower, "air_humidity", {
                "name": "Air Humidity",
                "unit_of_measurement": "%",
                "device_class": "humidity",
                "state_class": "measurement",
                "icon": "mdi:water-percent"
            })
        
        # VPD
        for tower in towers:
            self.publish_sensor_discovery(tower, "vpd", {
                "name": "VPD",
                "unit_of_measurement": "kPa",
                "state_class": "measurement",
                "icon": "mdi:chart-line"
            })
        
        # LED status
        for tower in towers:
            discovery_topic = f"{self.discovery_prefix}/light/{self.device_id}/{tower}_led/config"
            config = {
                "name": f"{tower.capitalize()} Tower LED",
                "unique_id": f"{self.device_id}_{tower}_led",
                "state_topic": f"/{tower}/led_status",
                "command_topic": f"/{tower}/led_command",
                "device": self.create_device_config(),
                "brightness_scale": 100,
                "brightness_state_topic": f"/{tower}/led_brightness",
                "brightness_command_topic": f"/{tower}/led_brightness/set",
                "schema": "json"
            }
            self.client.publish(discovery_topic, json.dumps(config), retain=True)
        
        logger.info("All sensor discoveries published")
    
    def setup_binary_sensors(self):
        """Setup binary sensors for alerts"""
        towers = ["cool", "warm"]
        
        for tower in towers:
            # System health binary sensor
            discovery_topic = f"{self.discovery_prefix}/binary_sensor/{self.device_id}/{tower}_health/config"
            config = {
                "name": f"{tower.capitalize()} Tower Health",
                "unique_id": f"{self.device_id}_{tower}_health",
                "state_topic": f"/{tower}/health",
                "device": self.create_device_config(),
                "payload_on": "healthy",
                "payload_off": "alert",
                "device_class": "problem",
                "icon": "mdi:leaf"
            }
            self.client.publish(discovery_topic, json.dumps(config), retain=True)
    
    def setup_person_tracking(self):
        """Setup person tracking for arrival notifications"""
        self.client.subscribe("homeassistant/person/+/state")
        logger.info("Person tracking enabled for arrival notifications")
    
    def on_connect(self, client, userdata, flags, rc):
        """MQTT connection handler"""
        if rc == 0:
            logger.info("Connected to MQTT broker")
            
            # Publish all discovery messages
            time.sleep(1)  # Give broker time to settle
            self.setup_all_sensors()
            self.setup_binary_sensors()
            
            # Setup person tracking if enabled
            arrival_delay = int(os.getenv("HA_ARRIVAL_DELAY_MINUTES", 5))
            if arrival_delay > 0:
                self.setup_person_tracking()
            
            # Subscribe to alerts for announcement queue
            client.subscribe("/alerts/#")
            client.subscribe("/events/#")
        else:
            logger.error(f"MQTT connection failed: {rc}")
    
    def run(self):
        """Main run loop"""
        try:
            logger.info("Starting Home Assistant Bridge...")
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_forever()
        except KeyboardInterrupt:
            logger.info("Shutting down Home Assistant Bridge...")
            self.client.disconnect()
        except Exception as e:
            logger.error(f"Fatal error: {e}")
            raise

def main():
    bridge = HomeAssistantBridge()
    bridge.run()

if __name__ == "__main__":
    main()
