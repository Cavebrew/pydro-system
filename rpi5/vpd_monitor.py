#!/usr/bin/env python3
"""
VPD (Vapor Pressure Deficit) Monitor
Calculates and monitors VPD for optimal plant transpiration
VPD = VPsat - VPair where VP is vapor pressure in kPa

Optimal VPD Ranges:
- Lettuce/Dill (Cool): 0.4-0.8 kPa
- Basil/Oregano (Warm): 0.8-1.2 kPa
"""

import json
import math
import time
import logging
from datetime import datetime
from typing import Dict, Optional, Tuple
import paho.mqtt.client as mqtt
from dotenv import load_dotenv
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

class VPDMonitor:
    def __init__(self):
        # MQTT Configuration
        self.broker = os.getenv("MQTT_BROKER", "10.0.0.62")
        self.port = int(os.getenv("MQTT_PORT", 1883))
        self.username = os.getenv("MQTT_USERNAME", "hydro_user")
        self.password = os.getenv("MQTT_PASSWORD", "")
        
        # VPD thresholds
        self.vpd_low = float(os.getenv("VPD_ALERT_THRESHOLD_LOW", 0.4))
        self.vpd_high = float(os.getenv("VPD_ALERT_THRESHOLD_HIGH", 1.5))
        self.check_interval = int(os.getenv("VPD_CHECK_INTERVAL_MINUTES", 15)) * 60
        
        # Tower-specific data
        self.tower_data = {
            "cool": {
                "air_temp": None,
                "air_humidity": None,
                "vpd": None,
                "ideal_range": (0.4, 0.8),  # kPa for lettuce/dill
                "last_alert": 0
            },
            "warm": {
                "air_temp": None,
                "air_humidity": None,
                "vpd": None,
                "ideal_range": (0.8, 1.2),  # kPa for basil/oregano
                "last_alert": 0
            }
        }
        
        # MQTT client setup
        self.client = mqtt.Client()
        self.client.username_pw_set(self.username, self.password)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        
        logger.info("VPD Monitor initialized")
    
    def calculate_vpd(self, temp_c: float, humidity_percent: float) -> float:
        """
        Calculate VPD using temperature and relative humidity
        
        Args:
            temp_c: Air temperature in Celsius
            humidity_percent: Relative humidity (0-100)
        
        Returns:
            VPD in kPa
        """
        # Saturation vapor pressure (kPa) using Magnus formula
        vpd_sat = 0.61078 * math.exp((17.27 * temp_c) / (temp_c + 237.3))
        
        # Actual vapor pressure
        vpd_air = vpd_sat * (humidity_percent / 100.0)
        
        # VPD
        vpd = vpd_sat - vpd_air
        
        return round(vpd, 3)
    
    def get_vpd_status(self, vpd: float, tower: str) -> str:
        """
        Get VPD status relative to ideal range
        
        Returns:
            "low", "optimal", or "high"
        """
        ideal_min, ideal_max = self.tower_data[tower]["ideal_range"]
        
        if vpd < ideal_min:
            return "low"
        elif vpd > ideal_max:
            return "high"
        else:
            return "optimal"
    
    def get_recommendation(self, vpd: float, tower: str) -> str:
        """Generate recommendation based on VPD status"""
        status = self.get_vpd_status(vpd, tower)
        
        if status == "low":
            return "Increase air circulation or reduce humidity to promote transpiration"
        elif status == "high":
            return "Increase humidity or reduce temperature to prevent plant stress"
        else:
            return "VPD is optimal - plants can transpire efficiently"
    
    def on_connect(self, client, userdata, flags, rc):
        """Handle MQTT connection"""
        if rc == 0:
            logger.info(f"Connected to MQTT broker at {self.broker}")
            # Subscribe to air temp and humidity topics
            client.subscribe("/cool/air_temp")
            client.subscribe("/cool/air_humidity")
            client.subscribe("/warm/air_temp")
            client.subscribe("/warm/air_humidity")
            logger.info("Subscribed to temperature and humidity topics")
        else:
            logger.error(f"Failed to connect to MQTT broker, return code: {rc}")
    
    def on_message(self, client, userdata, msg):
        """Process incoming MQTT messages"""
        try:
            topic = msg.topic
            value = float(msg.payload.decode())
            
            # Parse topic to determine tower and sensor type
            parts = topic.strip('/').split('/')
            if len(parts) != 2:
                return
            
            tower = parts[0]  # "cool" or "warm"
            sensor = parts[1]  # "air_temp" or "air_humidity"
            
            if tower not in self.tower_data:
                return
            
            # Update tower data
            if sensor == "air_temp":
                # Convert Fahrenheit to Celsius
                temp_c = (value - 32) * 5/9
                self.tower_data[tower]["air_temp"] = temp_c
            elif sensor == "air_humidity":
                self.tower_data[tower]["air_humidity"] = value
            
            # Calculate VPD if we have both values
            if (self.tower_data[tower]["air_temp"] is not None and 
                self.tower_data[tower]["air_humidity"] is not None):
                
                vpd = self.calculate_vpd(
                    self.tower_data[tower]["air_temp"],
                    self.tower_data[tower]["air_humidity"]
                )
                
                old_vpd = self.tower_data[tower]["vpd"]
                self.tower_data[tower]["vpd"] = vpd
                
                # Publish VPD value
                vpd_topic = f"/{tower}/vpd"
                client.publish(vpd_topic, vpd, retain=True)
                
                # Publish detailed VPD status
                status = self.get_vpd_status(vpd, tower)
                status_data = {
                    "vpd_kpa": vpd,
                    "status": status,
                    "ideal_min": self.tower_data[tower]["ideal_range"][0],
                    "ideal_max": self.tower_data[tower]["ideal_range"][1],
                    "temp_c": round(self.tower_data[tower]["air_temp"], 2),
                    "temp_f": round((self.tower_data[tower]["air_temp"] * 9/5) + 32, 2),
                    "humidity_pct": self.tower_data[tower]["air_humidity"],
                    "recommendation": self.get_recommendation(vpd, tower),
                    "timestamp": datetime.now().isoformat()
                }
                
                status_topic = f"/{tower}/vpd_status"
                client.publish(status_topic, json.dumps(status_data), retain=True)
                
                # Check for alerts
                if status != "optimal":
                    now = time.time()
                    last_alert = self.tower_data[tower]["last_alert"]
                    
                    # Alert if VPD changed from optimal or cooldown expired
                    if (old_vpd is None or 
                        self.get_vpd_status(old_vpd, tower) == "optimal" or
                        now - last_alert > self.check_interval):
                        
                        alert_data = {
                            "tower": tower,
                            "vpd": vpd,
                            "status": status,
                            "recommendation": self.get_recommendation(vpd, tower),
                            "severity": "warning" if abs(vpd - sum(self.tower_data[tower]["ideal_range"])/2) < 0.5 else "critical"
                        }
                        
                        client.publish("/alerts/vpd", json.dumps(alert_data))
                        self.tower_data[tower]["last_alert"] = now
                        
                        logger.warning(
                            f"{tower.upper()} tower VPD {status}: {vpd} kPa "
                            f"(ideal: {self.tower_data[tower]['ideal_range']})"
                        )
                
                logger.info(
                    f"{tower.upper()}: VPD={vpd} kPa, Status={status}, "
                    f"Temp={self.tower_data[tower]['air_temp']:.1f}°C, "
                    f"RH={self.tower_data[tower]['air_humidity']:.1f}%"
                )
        
        except Exception as e:
            logger.error(f"Error processing message from {msg.topic}: {e}")
    
    def run(self):
        """Main run loop"""
        try:
            logger.info("Starting VPD Monitor...")
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_forever()
        except KeyboardInterrupt:
            logger.info("Shutting down VPD Monitor...")
            self.client.disconnect()
        except Exception as e:
            logger.error(f"Fatal error: {e}")
            raise

def main():
    monitor = VPDMonitor()
    monitor.run()

if __name__ == "__main__":
    main()
