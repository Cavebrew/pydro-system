#!/usr/bin/env python3
"""
Alexa & Echo Show 21 Integration
Provides voice interface and visual dashboard for Pydro system

Features:
- Voice commands via Alexa skill
- Visual plant status on Echo Show 21
- Audio alerts and announcements
- Integration with Home Assistant for arrival notifications
- Image carousel of plants
- Real-time sensor dashboards
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_ask import Ask, statement, question
import requests

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

# Flask app for Alexa Skill endpoint
app = Flask(__name__)
ask = Ask(app, "/")

# Global state
system_status = {
    "cool": {
        "ph": None,
        "ec": None,
        "water_temp": None,
        "air_temp": None,
        "air_humidity": None,
        "vpd": None,
        "plant_count": 0,
        "health": "unknown"
    },
    "warm": {
        "ph": None,
        "ec": None,
        "water_temp": None,
        "air_temp": None,
        "air_humidity": None,
        "vpd": None,
        "plant_count": 0,
        "health": "unknown"
    },
    "last_alert": None,
    "harvest_ready": []
}

class AlexaIntegration:
    def __init__(self):
        # MQTT Configuration
        self.broker = os.getenv("MQTT_BROKER", "10.0.0.62")
        self.port = int(os.getenv("MQTT_PORT", 1883))
        self.username = os.getenv("MQTT_USERNAME", "hydro_user")
        self.password = os.getenv("MQTT_PASSWORD", "")
        
        # Home Assistant Configuration
        self.ha_enabled = os.getenv("ENABLE_HOME_ASSISTANT", "true").lower() == "true"
        self.ha_arrival_delay = int(os.getenv("HA_ARRIVAL_DELAY_MINUTES", 5))
        
        # MQTT client
        self.client = mqtt.Client()
        self.client.username_pw_set(self.username, self.password)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        
        # Important announcements queue
        self.announcements = []
        
        logger.info("Alexa Integration initialized")
    
    def on_connect(self, client, userdata, flags, rc):
        """MQTT connection handler"""
        if rc == 0:
            logger.info("Connected to MQTT broker")
            
            # Subscribe to all sensor topics
            client.subscribe("/+/ph")
            client.subscribe("/+/ec")
            client.subscribe("/+/water_temp")
            client.subscribe("/+/air_temp")
            client.subscribe("/+/air_humidity")
            client.subscribe("/+/vpd")
            
            # Subscribe to alerts and events
            client.subscribe("/alerts/#")
            client.subscribe("/events/#")
            
            # Subscribe to Home Assistant topics
            if self.ha_enabled:
                client.subscribe("homeassistant/person/+/state")
        else:
            logger.error(f"MQTT connection failed: {rc}")
    
    def on_message(self, client, userdata, msg):
        """MQTT message handler"""
        global system_status
        
        try:
            topic = msg.topic
            
            # Update sensor readings
            if topic.count('/') == 1:
                parts = topic.strip('/').split('/')
                tower = parts[0]
                sensor = parts[1]
                
                if tower in ["cool", "warm"]:
                    try:
                        value = float(msg.payload.decode())
                        system_status[tower][sensor] = value
                    except:
                        pass
            
            # Handle alerts
            elif topic.startswith("/alerts/"):
                alert_type = topic.split('/')[-1]
                payload = json.loads(msg.payload.decode())
                
                self.handle_alert(alert_type, payload)
            
            # Handle events
            elif topic.startswith("/events/"):
                event_type = topic.split('/')[-1]
                payload = json.loads(msg.payload.decode())
                
                if event_type == "harvest":
                    self.announce_harvest(payload)
            
            # Handle Home Assistant person tracking
            elif "homeassistant/person/" in topic and self.ha_enabled:
                # Check if user just arrived home
                state = msg.payload.decode()
                if state == "home":
                    # Schedule announcement after delay
                    self.schedule_arrival_announcement()
        
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def handle_alert(self, alert_type: str, payload: Dict):
        """Process alerts and queue announcements"""
        global system_status
        
        severity = payload.get("severity", "info")
        tower = payload.get("tower", "system")
        
        system_status["last_alert"] = {
            "type": alert_type,
            "severity": severity,
            "tower": tower,
            "time": datetime.now().isoformat()
        }
        
        # Create announcement for critical alerts
        if severity == "critical":
            announcement = self.create_alert_announcement(alert_type, payload)
            self.announcements.append(announcement)
            
            # Also send push notification via Home Assistant
            if self.ha_enabled:
                self.send_ha_notification(announcement)
    
    def create_alert_announcement(self, alert_type: str, payload: Dict) -> str:
        """Create voice announcement text"""
        tower = payload.get("tower", "")
        
        if alert_type == "ph":
            return f"Critical pH alert in {tower} tower. Current pH is {payload.get('value', 'unknown')}."
        
        elif alert_type == "ec":
            return f"Critical EC alert in {tower} tower. Current EC is {payload.get('value', 'unknown')}."
        
        elif alert_type == "temperature":
            return f"Temperature alert in {tower} tower. Current temperature is {payload.get('value', 'unknown')} degrees."
        
        elif alert_type == "vpd":
            return f"VPD alert in {tower} tower. Current VPD is {payload.get('vpd', 'unknown')} kilopascals."
        
        elif alert_type == "deficiency":
            deficiency = payload.get("deficiency", "nutrient")
            return f"{deficiency} deficiency detected in {tower} tower."
        
        else:
            return f"Alert in {tower} tower: {alert_type}"
    
    def announce_harvest(self, payload: Dict):
        """Announce harvest completion"""
        plant_id = payload.get("plant_id", "unknown")
        weight = payload.get("weight_grams", 0)
        days = payload.get("days_to_harvest", 0)
        
        announcement = (
            f"Harvest complete! Plant {plant_id} yielded {weight} grams "
            f"after {days} days of growth."
        )
        
        self.announcements.append(announcement)
    
    def schedule_arrival_announcement(self):
        """Schedule announcement for when user arrives home"""
        # This would be implemented with a timer
        # For now, just add to queue
        if self.announcements:
            logger.info(f"User arrived home - {len(self.announcements)} announcements pending")
    
    def send_ha_notification(self, message: str):
        """Send notification via Home Assistant"""
        # Publish to Home Assistant MQTT
        self.client.publish(
            "homeassistant/notify/alexa",
            json.dumps({
                "message": message,
                "target": "Echo Show 21",
                "data": {
                    "type": "tts"
                }
            })
        )
    
    def get_status_summary(self, tower: str) -> str:
        """Get voice-friendly status summary"""
        global system_status
        
        status = system_status.get(tower, {})
        
        ph = status.get("ph")
        ec = status.get("ec")
        temp = status.get("water_temp")
        vpd = status.get("vpd")
        
        summary = f"{tower.capitalize()} tower status: "
        
        if ph:
            summary += f"pH is {ph:.1f}, "
        if ec:
            summary += f"EC is {ec:.1f}, "
        if temp:
            summary += f"water temperature is {temp:.0f} degrees, "
        if vpd:
            summary += f"VPD is {vpd:.2f}."
        
        return summary
    
    def run(self):
        """Start MQTT listener"""
        try:
            logger.info("Starting Alexa Integration...")
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
        except Exception as e:
            logger.error(f"Error starting MQTT: {e}")

# Create global instance
alexa_integration = AlexaIntegration()

# Alexa Skill Intent Handlers

@ask.launch
def launch():
    """Alexa skill launch handler"""
    welcome_text = "Welcome to Pydro, your hydroponic monitoring assistant. You can ask about tower status, plant health, or recent alerts."
    return question(welcome_text)

@ask.intent("TowerStatusIntent", mapping={"tower": "Tower"})
def get_tower_status(tower):
    """Handle tower status request"""
    if not tower:
        return question("Which tower would you like to check? Cool or warm?")
    
    tower_name = tower.lower()
    if tower_name not in ["cool", "warm"]:
        return statement("I can only check the cool or warm tower.")
    
    summary = alexa_integration.get_status_summary(tower_name)
    return statement(summary)

@ask.intent("SystemStatusIntent")
def get_system_status():
    """Handle overall system status request"""
    global system_status
    
    cool_summary = alexa_integration.get_status_summary("cool")
    warm_summary = alexa_integration.get_status_summary("warm")
    
    full_summary = f"{cool_summary} {warm_summary}"
    return statement(full_summary)

@ask.intent("AlertStatusIntent")
def get_alert_status():
    """Handle recent alerts request"""
    global system_status
    
    last_alert = system_status.get("last_alert")
    
    if not last_alert:
        return statement("No recent alerts. All systems are normal.")
    
    alert_type = last_alert.get("type", "unknown")
    tower = last_alert.get("tower", "system")
    severity = last_alert.get("severity", "info")
    
    response = f"Last alert was a {severity} {alert_type} alert in the {tower} tower."
    return statement(response)

@ask.intent("PlantCountIntent", mapping={"tower": "Tower"})
def get_plant_count(tower):
    """Handle plant count request"""
    if not tower:
        return question("Which tower? Cool or warm?")
    
    tower_name = tower.lower()
    if tower_name not in ["cool", "warm"]:
        return statement("I can only check the cool or warm tower.")
    
    # This would query the plant tracker
    count = system_status[tower_name].get("plant_count", 0)
    return statement(f"The {tower} tower has {count} active plants.")

@ask.intent("HarvestReadyIntent")
def get_harvest_ready():
    """Handle harvest readiness request"""
    global system_status
    
    ready_plants = system_status.get("harvest_ready", [])
    
    if not ready_plants:
        return statement("No plants are ready for harvest at this time.")
    
    count = len(ready_plants)
    if count == 1:
        return statement(f"One plant is ready for harvest: {ready_plants[0]}")
    else:
        return statement(f"{count} plants are ready for harvest.")

@ask.intent("AMAZON.HelpIntent")
def help():
    """Help intent"""
    help_text = (
        "You can ask about tower status, plant health, recent alerts, "
        "plant counts, or which plants are ready for harvest. "
        "What would you like to know?"
    )
    return question(help_text)

@ask.intent("AMAZON.StopIntent")
def stop():
    """Stop intent"""
    return statement("Goodbye!")

@ask.intent("AMAZON.CancelIntent")
def cancel():
    """Cancel intent"""
    return statement("Cancelled.")

# Visual dashboard endpoint for Echo Show 21
@app.route("/dashboard", methods=["GET"])
def dashboard():
    """Return visual dashboard data for Echo Show 21"""
    global system_status
    
    return jsonify({
        "version": "1.0",
        "status": system_status,
        "timestamp": datetime.now().isoformat(),
        "announcements": alexa_integration.announcements
    })

def main():
    """Main entry point"""
    # Start MQTT integration
    alexa_integration.run()
    
    # Start Flask app for Alexa Skill
    port = int(os.getenv("ALEXA_SKILL_PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

if __name__ == "__main__":
    main()
