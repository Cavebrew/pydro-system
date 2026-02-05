#!/usr/bin/env python3
"""
Main Hydroponic AI System Orchestrator
Coordinates sensor monitoring, image analysis, nutrient recommendations, and alerts

Raspberry Pi 5 with AI Hat 2
Dual Tower Hydroponic System - Brian Altmaier
"""

import os
import sys
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta
from threading import Thread, Event
import json
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

# Import local modules
from sensor_monitor import SensorMonitor, THRESHOLDS
from image_analyzer import ImageAnalyzer
from sms_alerts import SMSAlertSystem
from nutrient_advisor import NutrientAdvisor

load_dotenv()

# Logging configuration
LOG_PATH = Path(os.getenv('LOG_PATH', '/home/pi/hydro_logs'))
LOG_PATH.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_PATH / 'hydro_ai.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('hydro_ai_main')


class HydroponicAISystem:
    def __init__(self):
        logger.info("=== Initializing Hydroponic AI System ===")
        
        # Configuration
        self.mqtt_broker = os.getenv('MQTT_BROKER', '10.0.0.62')
        self.mqtt_port = int(os.getenv('MQTT_PORT', 1883))
        self.mqtt_username = os.getenv('MQTT_USERNAME', 'hydro_user')
        self.mqtt_password = os.getenv('MQTT_PASSWORD', '')
        
        self.image_storage_path = Path(os.getenv('IMAGE_STORAGE_PATH', '/home/pi/hydro_images'))
        self.image_storage_path.mkdir(parents=True, exist_ok=True)
        
        # Components
        self.sensor_monitor = None
        self.image_analyzer = None
        self.sms_alerts = None
        self.nutrient_advisor = None
        self.mqtt_client = None
        
        # State tracking
        self.pending_images = {
            'cool': {'visible': None, 'noir': None},
            'warm': {'visible': None, 'noir': None}
        }
        self.last_image_analysis = {
            'cool': datetime.now() - timedelta(hours=5),
            'warm': datetime.now() - timedelta(hours=5)
        }
        
        # LED control state
        self.current_led_intensity = {
            'cool': 75,
            'warm': 75
        }
        
        # Control
        self.running = Event()
        self.running.set()
        
        # Initialize components
        self._initialize_components()
    
    def _initialize_components(self):
        """Initialize all system components"""
        logger.info("Initializing system components...")
        
        # Sensor Monitor with alert callback
        self.sensor_monitor = SensorMonitor(alert_callback=self._handle_sensor_alert)
        if not self.sensor_monitor.connect():
            logger.error("Failed to initialize sensor monitor")
        
        # Image Analyzer
        self.image_analyzer = ImageAnalyzer()
        logger.info(f"Image analyzer initialized (ML model: {self.image_analyzer.model_loaded})")
        
        # SMS Alerts
        self.sms_alerts = SMSAlertSystem()
        if self.sms_alerts.enabled:
            logger.info("SMS alerts enabled")
        else:
            logger.warning("SMS alerts disabled - configure Twilio credentials")
        
        # Nutrient Advisor
        self.nutrient_advisor = NutrientAdvisor()
        
        # MQTT for camera image notifications
        self._setup_mqtt_camera_listener()
        
        logger.info("All components initialized successfully")
    
    def _setup_mqtt_camera_listener(self):
        """Setup MQTT listener for camera image notifications"""
        self.mqtt_client = mqtt.Client(client_id="rpi5_ai_main")
        self.mqtt_client.username_pw_set(self.mqtt_username, self.mqtt_password)
        
        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                # Subscribe to camera image topics
                topics = [
                    ('/cool_tower/camera/visible', 0),
                    ('/cool_tower/camera/noir', 0),
                    ('/warm_tower/camera/visible', 0),
                    ('/warm_tower/camera/noir', 0),
                ]
                client.subscribe(topics)
                logger.info("Subscribed to camera image topics")
        
        def on_message(client, userdata, msg):
            self._handle_camera_image(msg.topic, msg.payload)
        
        self.mqtt_client.on_connect = on_connect
        self.mqtt_client.on_message = on_message
        
        try:
            self.mqtt_client.connect(self.mqtt_broker, self.mqtt_port, 60)
            self.mqtt_client.loop_start()
        except Exception as e:
            logger.error(f"Failed to connect MQTT camera listener: {e}")
    
    def _handle_camera_image(self, topic, payload):
        """Handle incoming camera image notification"""
        try:
            metadata = json.loads(payload.decode('utf-8'))
            tower = metadata['tower']
            camera_type = metadata['camera_type']
            filepath = Path(metadata['filepath'])
            
            logger.info(f"Received {camera_type} image from {tower} tower: {filepath.name}")
            
            # Store image path
            self.pending_images[tower][camera_type] = filepath
            
            # Check if we have both visible and NOIR for this tower
            if all(self.pending_images[tower].values()):
                # Both images ready - analyze
                self._analyze_tower_images(tower)
                
        except Exception as e:
            logger.error(f"Error handling camera image: {e}")
    
    def _analyze_tower_images(self, tower: str):
        """Analyze visible and NOIR images for a tower"""
        logger.info(f"Analyzing images for {tower} tower...")
        
        visible_path = self.pending_images[tower]['visible']
        noir_path = self.pending_images[tower]['noir']
        
        # Run image analysis
        results = self.image_analyzer.analyze_images(visible_path, noir_path, tower)
        
        self.last_image_analysis[tower] = datetime.now()
        
        # Log results
        logger.info(f"{tower.capitalize()} Tower Analysis Results:")
        logger.info(f"  Health Score: {results['health_score']}/100")
        logger.info(f"  Deficiencies: {len(results['deficiencies'])}")
        for deficiency in results['deficiencies']:
            logger.info(f"    - {deficiency['type']} (confidence: {deficiency.get('confidence', 0):.2f})")
        
        # Handle detected issues
        if results['deficiencies']:
            self._handle_image_deficiencies(tower, results)
        
        # Clear pending images
        self.pending_images[tower] = {'visible': None, 'noir': None}
    
    def _handle_image_deficiencies(self, tower: str, results: Dict):
        """Handle deficiencies detected in images"""
        for deficiency in results['deficiencies']:
            deficiency_type = deficiency['type']
            confidence = deficiency.get('confidence', 0.5)
            
            # Skip low confidence detections
            if confidence < 0.5:
                continue
            
            # Get current sensor data
            sensor_data = self.sensor_monitor.get_current_data(tower)
            
            # Special handling for harvest/bolting
            if deficiency_type == 'ready_for_harvest':
                plant_type = THRESHOLDS[tower]['plant_type']
                self.sms_alerts.send_harvest_alert(tower, plant_type, urgency='ready')
                logger.info(f"{tower.capitalize()} tower ready for harvest")
                continue
            
            elif deficiency_type == 'bolting_flowering':
                plant_type = THRESHOLDS[tower]['plant_type']
                self.sms_alerts.send_harvest_alert(tower, plant_type, urgency='urgent')
                logger.warning(f"{tower.capitalize()} tower bolting - urgent harvest needed")
                continue
            
            # Heat stress - adjust LEDs
            elif 'heat_stress' in deficiency_type:
                self._adjust_led_intensity(tower, 50, "Heat stress detected via IR")
                continue
            
            # Get nutrient recommendation
            recommendation = self.nutrient_advisor.get_recommendation(
                tower,
                deficiency_type,
                sensor_data['sensor_data'],
                deficiencies=[d['type'] for d in results['deficiencies']]
            )
            
            # Send SMS alert
            suggestion = f"{recommendation['action']} ({recommendation['amount']})"
            self.sms_alerts.send_image_alert(
                tower,
                deficiency_type,
                suggestion,
                confidence,
                sensor_data['sensor_data']
            )
            
            logger.info(f"Sent deficiency alert for {tower} tower: {deficiency_type}")
    
    def _handle_sensor_alert(self, tower: str, issue: Dict, sensor_data: Dict, env_data: Dict):
        """Handle sensor threshold violation (callback from SensorMonitor)"""
        logger.warning(f"{tower.capitalize()} Tower Sensor Alert: {issue['message']}")
        
        # Get nutrient recommendation if EC/pH related
        if any(x in issue['type'] for x in ['ec_', 'ph_', 'nitrogen', 'calcium']):
            recommendation = self.nutrient_advisor.get_recommendation(
                tower,
                issue['type'],
                sensor_data
            )
            
            # Override suggestion with nutrient advisor recommendation
            if recommendation['source'] == 'grok_ai':
                issue['suggestion'] = f"{recommendation['action']} ({recommendation['amount']}) [AI]"
            else:
                issue['suggestion'] = f"{recommendation['action']} - {recommendation['amount']}"
        
        # Handle air temperature issues with LED adjustment
        if 'air_temp_high' in issue['type']:
            current_intensity = self.current_led_intensity[tower]
            if current_intensity > 50:
                self._adjust_led_intensity(tower, 50, "High air temp")
        
        # Send SMS alert
        self.sms_alerts.send_sensor_alert(tower, issue, sensor_data, env_data)
    
    def _adjust_led_intensity(self, tower: str, intensity: int, reason: str):
        """Adjust LED grow light intensity"""
        if intensity == self.current_led_intensity[tower]:
            return  # No change needed
        
        topic = f"/{tower}_tower/led_intensity"
        
        try:
            self.mqtt_client.publish(topic, str(intensity))
            self.current_led_intensity[tower] = intensity
            
            logger.info(f"Adjusted {tower} tower LED to {intensity}% ({reason})")
            
            # Send SMS notification
            self.sms_alerts.send_led_adjustment_alert(tower, intensity, reason)
            
        except Exception as e:
            logger.error(f"Failed to adjust LED intensity: {e}")
    
    def run(self):
        """Main system loop"""
        logger.info("=== Hydroponic AI System Running ===")
        logger.info("Press Ctrl+C to stop")
        
        try:
            while self.running.is_set():
                # Main loop - most work is event-driven via MQTT callbacks
                
                # Periodic health checks every 5 minutes
                time.sleep(300)
                self._periodic_health_check()
                
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        except Exception as e:
            logger.error(f"Fatal error in main loop: {e}", exc_info=True)
        finally:
            self.shutdown()
    
    def _periodic_health_check(self):
        """Periodic system health check"""
        logger.debug("Running periodic health check...")
        
        # Check for stale sensor data (no updates in 10 minutes)
        for tower in ['cool', 'warm']:
            tower_data = self.sensor_monitor.sensor_data[tower]
            if tower_data['last_update']:
                time_since_update = (datetime.now() - tower_data['last_update']).seconds
                if time_since_update > 600:  # 10 minutes
                    logger.warning(f"{tower.capitalize()} tower sensors stale ({time_since_update}s since last update)")
        
        # Check environment sensor
        env_data = self.sensor_monitor.sensor_data['environment']
        if env_data['last_update']:
            time_since_update = (datetime.now() - env_data['last_update']).seconds
            if time_since_update > 600:
                logger.warning(f"Environment sensor stale ({time_since_update}s since last update)")
        
        # Log current status
        for tower in ['cool', 'warm']:
            data = self.sensor_monitor.sensor_data[tower]
            logger.info(f"{tower.capitalize()}: EC={data.get('ec')}, pH={data.get('ph')}, "
                       f"Temp={data.get('water_temp')}°F, LED={self.current_led_intensity[tower]}%")
    
    def shutdown(self):
        """Cleanup and shutdown"""
        logger.info("Shutting down Hydroponic AI System...")
        
        self.running.clear()
        
        if self.sensor_monitor:
            self.sensor_monitor.disconnect()
        
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        
        logger.info("Shutdown complete")


def main():
    """Main entry point"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║   Dual Tower Hydroponic AI System - Raspberry Pi 5          ║
║   Brian Altmaier © 2026                                      ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    # Check environment
    if not os.path.exists('.env'):
        logger.error("Configuration file .env not found!")
        logger.error("Copy .env.template to .env and configure credentials")
        sys.exit(1)
    
    # Create and run system
    system = HydroponicAISystem()
    system.run()


if __name__ == '__main__':
    main()
