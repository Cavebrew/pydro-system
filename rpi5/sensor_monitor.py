#!/usr/bin/env python3
"""
Sensor Monitor - MQTT Subscriber for Hydroponic System
Subscribes to all sensor topics and maintains current state
Detects threshold violations and triggers alerts

Part of the Dual Tower Hydroponic AI System
"""

import os
import time
from datetime import datetime, timedelta
import paho.mqtt.client as mqtt
from dotenv import load_dotenv
import json
import logging

load_dotenv()

# Logging
logger = logging.getLogger('sensor_monitor')

# Tower-specific thresholds
THRESHOLDS = {
    'cool': {
        'ec_min': 1.2,
        'ec_max': 1.8,
        'ph_min': 5.8,
        'ph_max': 6.2,
        'water_temp_max': 75.0,
        'air_temp_max': 70.0,
        'air_temp_min': 55.0,  # Night minimum
        'humidity_min': 50.0,
        'humidity_max': 70.0,
        'plant_type': 'lettuce/dill'
    },
    'warm': {
        'ec_min': 1.5,
        'ec_max': 2.0,
        'ph_min': 5.8,
        'ph_max': 6.2,
        'water_temp_max': 75.0,
        'air_temp_max': 80.0,
        'air_temp_min': 70.0,
        'humidity_min': 50.0,
        'humidity_max': 60.0,  # Lower for basil
        'plant_type': 'basil/oregano'
    }
}

# Nutrient recipes (amounts per 5 gallons)
NUTRIENT_RECIPES = {
    'cool': {
        'buffer': '5ml CalMagic + 10g Calcium Nitrate',
        'fertilizer': '10-12g Lettuce Fertilizer 8-15-36',
        'supplements': '5g Epsom Salt, 5ml Armor Si',
        'target_ec': '1.2-1.8 mS/cm',
        'target_ph': '5.8-6.2'
    },
    'warm': {
        'buffer': '5ml CalMagic',
        'fertilizer': '10g MaxiGrow (1 big + 1 little scoop)',
        'supplements': '5ml Armor Si, optional 1-2g Epsom Salt',
        'target_ec': '1.5-2.0 mS/cm',
        'target_ph': '5.8-6.2'
    }
}


class SensorMonitor:
    def __init__(self, alert_callback=None):
        self.mqtt_broker = os.getenv('MQTT_BROKER', '10.0.0.62')
        self.mqtt_port = int(os.getenv('MQTT_PORT', 1883))
        self.mqtt_username = os.getenv('MQTT_USERNAME', 'hydro_user')
        self.mqtt_password = os.getenv('MQTT_PASSWORD', '')
        
        self.alert_callback = alert_callback
        self.client = None
        
        # Current sensor readings
        self.sensor_data = {
            'cool': {'ec': None, 'ph': None, 'water_temp': None, 'last_update': None},
            'warm': {'ec': None, 'ph': None, 'water_temp': None, 'last_update': None},
            'environment': {'air_temp': None, 'humidity': None, 'last_update': None}
        }
        
        # Issue tracking
        self.active_issues = {}
        self.last_reservoir_change = {
            'cool': datetime.now() - timedelta(days=5),  # Assume 5 days ago
            'warm': datetime.now() - timedelta(days=5)
        }
        
        # Alert cooldowns (prevent spam)
        self.alert_cooldowns = {}
        self.cooldown_period = timedelta(hours=2)
    
    def connect(self):
        """Connect to MQTT broker"""
        self.client = mqtt.Client(client_id="rpi5_sensor_monitor")
        self.client.username_pw_set(self.mqtt_username, self.mqtt_password)
        
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        
        try:
            self.client.connect(self.mqtt_broker, self.mqtt_port, 60)
            self.client.loop_start()
            logger.info(f"Connected to MQTT broker at {self.mqtt_broker}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            return False
    
    def _on_connect(self, client, userdata, flags, rc):
        """MQTT connection callback"""
        if rc == 0:
            logger.info("MQTT connection successful")
            # Subscribe to all sensor topics
            topics = [
                ('/cool_tower/ec', 0),
                ('/cool_tower/ph', 0),
                ('/cool_tower/water_temp', 0),
                ('/warm_tower/ec', 0),
                ('/warm_tower/ph', 0),
                ('/warm_tower/water_temp', 0),
                ('/environment/air_temp', 0),
                ('/environment/humidity', 0),
            ]
            client.subscribe(topics)
            logger.info(f"Subscribed to {len(topics)} sensor topics")
        else:
            logger.error(f"MQTT connection failed with code {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """MQTT disconnection callback"""
        if rc != 0:
            logger.warning(f"Unexpected MQTT disconnect: {rc}")
    
    def _on_message(self, client, userdata, msg):
        """Handle incoming MQTT messages"""
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            value = float(payload)
            
            # Update sensor data
            if '/cool_tower/' in topic:
                tower = 'cool'
                sensor = topic.split('/')[-1]
                self.sensor_data['cool'][sensor] = value
                self.sensor_data['cool']['last_update'] = datetime.now()
            elif '/warm_tower/' in topic:
                tower = 'warm'
                sensor = topic.split('/')[-1]
                self.sensor_data['warm'][sensor] = value
                self.sensor_data['warm']['last_update'] = datetime.now()
            elif '/environment/' in topic:
                sensor = topic.split('/')[-1]
                self.sensor_data['environment'][sensor] = value
                self.sensor_data['environment']['last_update'] = datetime.now()
            
            # Check thresholds
            if tower in ['cool', 'warm']:
                self._check_thresholds(tower)
            
        except Exception as e:
            logger.error(f"Error processing message from {msg.topic}: {e}")
    
    def _check_thresholds(self, tower):
        """Check if sensor readings violate thresholds"""
        data = self.sensor_data[tower]
        thresholds = THRESHOLDS[tower]
        env_data = self.sensor_data['environment']
        
        issues = []
        
        # EC checks
        if data['ec'] is not None:
            if data['ec'] < thresholds['ec_min']:
                suggestion = self._get_ec_low_suggestion(tower, data['ec'])
                issues.append({
                    'type': 'ec_low',
                    'severity': 'medium',
                    'message': f"EC low: {data['ec']:.2f} mS/cm (target {thresholds['ec_min']}-{thresholds['ec_max']})",
                    'suggestion': suggestion
                })
            elif data['ec'] > thresholds['ec_max']:
                issues.append({
                    'type': 'ec_high',
                    'severity': 'medium',
                    'message': f"EC high: {data['ec']:.2f} mS/cm (target {thresholds['ec_min']}-{thresholds['ec_max']})",
                    'suggestion': 'Dilute with RO water or consider fresh reservoir change if persistent'
                })
        
        # pH checks
        if data['ph'] is not None:
            if data['ph'] < thresholds['ph_min']:
                issues.append({
                    'type': 'ph_low',
                    'severity': 'high',
                    'message': f"pH low: {data['ph']:.2f} (target {thresholds['ph_min']}-{thresholds['ph_max']})",
                    'suggestion': 'Unusual - check probe calibration. Normally pH drifts up, not down.'
                })
            elif data['ph'] > thresholds['ph_max']:
                issues.append({
                    'type': 'ph_high',
                    'severity': 'high',
                    'message': f"pH high: {data['ph']:.2f} (target {thresholds['ph_min']}-{thresholds['ph_max']})",
                    'suggestion': 'Add pH Down. If unstable >24h, suggest fresh reservoir change'
                })
        
        # Water temperature
        if data['water_temp'] is not None:
            if data['water_temp'] > thresholds['water_temp_max']:
                issues.append({
                    'type': 'water_temp_high',
                    'severity': 'high',
                    'message': f"Water temp high: {data['water_temp']:.1f}°F (max {thresholds['water_temp_max']}°F)",
                    'suggestion': 'Cool reservoir - low oxygen risk. Check air stones. Manual DO test suggested.'
                })
        
        # Air temperature
        if env_data['air_temp'] is not None:
            if env_data['air_temp'] > thresholds['air_temp_max']:
                issues.append({
                    'type': 'air_temp_high',
                    'severity': 'medium',
                    'message': f"Air temp high: {env_data['air_temp']:.1f}°F (max {thresholds['air_temp_max']}°F)",
                    'suggestion': f"Reduce heat. Consider dimming LEDs to 50%. Heat stress risk for {thresholds['plant_type']}."
                })
        
        # Humidity
        if env_data['humidity'] is not None:
            if env_data['humidity'] < thresholds['humidity_min']:
                issues.append({
                    'type': 'humidity_low',
                    'severity': 'low',
                    'message': f"Humidity low: {env_data['humidity']:.1f}% (target {thresholds['humidity_min']}-{thresholds['humidity_max']}%)",
                    'suggestion': 'Increase humidity - tip burn risk (especially for lettuce)'
                })
            elif env_data['humidity'] > thresholds['humidity_max']:
                issues.append({
                    'type': 'humidity_high',
                    'severity': 'medium',
                    'message': f"Humidity high: {env_data['humidity']:.1f}% (target {thresholds['humidity_min']}-{thresholds['humidity_max']}%)",
                    'suggestion': 'Increase air flow - disease/mold risk'
                })
        
        # Check for fresh reservoir change needed
        days_since_change = (datetime.now() - self.last_reservoir_change[tower]).days
        if days_since_change >= 7:
            issues.append({
                'type': 'reservoir_change_due',
                'severity': 'medium',
                'message': f"Reservoir change due ({days_since_change} days since last change)",
                'suggestion': 'Fresh reservoir change suggested - nutrient buildup risk'
            })
        
        # Trigger alerts for new issues
        for issue in issues:
            issue_key = f"{tower}_{issue['type']}"
            
            # Check cooldown
            if issue_key in self.alert_cooldowns:
                if datetime.now() - self.alert_cooldowns[issue_key] < self.cooldown_period:
                    continue  # Skip - still in cooldown
            
            # New issue or cooldown expired
            self.active_issues[issue_key] = {
                'tower': tower,
                'issue': issue,
                'timestamp': datetime.now()
            }
            
            # Trigger alert callback
            if self.alert_callback:
                self.alert_callback(tower, issue, data, env_data)
            
            # Set cooldown
            self.alert_cooldowns[issue_key] = datetime.now()
    
    def _get_ec_low_suggestion(self, tower, current_ec):
        """Generate specific suggestion for low EC"""
        recipe = NUTRIENT_RECIPES[tower]
        
        if tower == 'cool':
            return f"Add 5g Lettuce Fertilizer 8-15-36 to increase EC. Current recipe: {recipe['fertilizer']}"
        else:  # warm
            return f"Add small scoop MaxiGrow (~5g) to increase EC. Current recipe: {recipe['fertilizer']}"
    
    def get_current_data(self, tower):
        """Get current sensor data for a tower"""
        return {
            'sensor_data': self.sensor_data[tower],
            'environment': self.sensor_data['environment'],
            'thresholds': THRESHOLDS[tower],
            'recipe': NUTRIENT_RECIPES[tower]
        }
    
    def mark_reservoir_changed(self, tower):
        """Mark that reservoir was changed"""
        self.last_reservoir_change[tower] = datetime.now()
        logger.info(f"{tower.capitalize()} tower reservoir marked as changed")
        
        # Clear related issues
        for key in list(self.active_issues.keys()):
            if key.startswith(f"{tower}_reservoir"):
                del self.active_issues[key]
    
    def disconnect(self):
        """Disconnect from MQTT"""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            logger.info("Disconnected from MQTT broker")


if __name__ == '__main__':
    # Test mode
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    def test_alert(tower, issue, sensor_data, env_data):
        print(f"\n=== ALERT: {tower.upper()} Tower ===")
        print(f"Issue: {issue['message']}")
        print(f"Suggestion: {issue['suggestion']}")
        print(f"Severity: {issue['severity']}")
        print(f"Sensor Data: EC={sensor_data.get('ec')}, pH={sensor_data.get('ph')}, "
              f"Temp={sensor_data.get('water_temp')}")
        print("=" * 50)
    
    monitor = SensorMonitor(alert_callback=test_alert)
    
    if monitor.connect():
        print("Sensor monitor running. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down...")
            monitor.disconnect()
