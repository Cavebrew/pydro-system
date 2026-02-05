#!/usr/bin/env python3
"""
Configuration Validator
Validates all environment variables and system settings before startup

Features:
- Validates .env file completeness
- Tests MQTT connection
- Checks API credentials (Twilio, xAI)
- Verifies file paths exist
- Tests network connectivity
- Validates sensor thresholds
"""

import os
import sys
import logging
from typing import Dict, List, Tuple
from dotenv import load_dotenv
import paho.mqtt.client as mqtt
import socket
import requests

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ConfigValidator:
    def __init__(self):
        load_dotenv()
        self.errors = []
        self.warnings = []
        self.passed = []
    
    def validate_required_env(self, key: str, description: str) -> bool:
        """Check if required environment variable exists"""
        value = os.getenv(key)
        if not value or value.startswith("your_"):
            self.errors.append(f"Missing {description}: {key}")
            return False
        else:
            self.passed.append(f"✓ {description}: {key}")
            return True
    
    def validate_optional_env(self, key: str, description: str, default: str = None) -> bool:
        """Check optional environment variable"""
        value = os.getenv(key, default)
        if not value or value.startswith("your_"):
            self.warnings.append(f"Optional {description} not set: {key}")
            return False
        else:
            self.passed.append(f"✓ {description}: {key}")
            return True
    
    def validate_mqtt(self) -> bool:
        """Test MQTT broker connection"""
        try:
            broker = os.getenv("MQTT_BROKER", "10.0.0.62")
            port = int(os.getenv("MQTT_PORT", 1883))
            username = os.getenv("MQTT_USERNAME")
            password = os.getenv("MQTT_PASSWORD")
            
            client = mqtt.Client()
            if username and password:
                client.username_pw_set(username, password)
            
            client.connect(broker, port, 5)
            client.disconnect()
            
            self.passed.append(f"✓ MQTT connection: {broker}:{port}")
            return True
        
        except Exception as e:
            self.errors.append(f"MQTT connection failed: {e}")
            return False
    
    def validate_network_host(self, host: str, description: str) -> bool:
        """Test if network host is reachable"""
        try:
            socket.create_connection((host, 22), timeout=2)
            self.passed.append(f"✓ Network host reachable: {description} ({host})")
            return True
        except:
            self.warnings.append(f"Network host unreachable: {description} ({host})")
            return False
    
    def validate_directory(self, path: str, description: str, create: bool = False) -> bool:
        """Check if directory exists or create it"""
        if os.path.exists(path):
            self.passed.append(f"✓ Directory exists: {description} ({path})")
            return True
        elif create:
            try:
                os.makedirs(path, exist_ok=True)
                self.passed.append(f"✓ Directory created: {description} ({path})")
                return True
            except Exception as e:
                self.errors.append(f"Cannot create directory {path}: {e}")
                return False
        else:
            self.warnings.append(f"Directory missing: {description} ({path})")
            return False
    
    def validate_xai_api(self) -> bool:
        """Test xAI API connection"""
        try:
            api_key = os.getenv("XAI_API_KEY")
            if not api_key or api_key.startswith("your_"):
                self.warnings.append("xAI API key not configured")
                return False
            
            # Simple API validation (just check if key format is valid)
            if len(api_key) > 10:
                self.passed.append("✓ xAI API key configured")
                return True
            else:
                self.warnings.append("xAI API key looks invalid")
                return False
        
        except Exception as e:
            self.warnings.append(f"xAI API validation error: {e}")
            return False
    
    def validate_twilio(self) -> bool:
        """Validate Twilio credentials"""
        try:
            from twilio.rest import Client
            
            account_sid = os.getenv("TWILIO_ACCOUNT_SID")
            auth_token = os.getenv("TWILIO_AUTH_TOKEN")
            
            if not account_sid or account_sid.startswith("your_"):
                self.warnings.append("Twilio not configured - SMS alerts disabled")
                return False
            
            # Try to create client (doesn't actually call API)
            client = Client(account_sid, auth_token)
            self.passed.append("✓ Twilio credentials configured")
            return True
        
        except Exception as e:
            self.warnings.append(f"Twilio validation failed: {e}")
            return False
    
    def run_full_validation(self) -> bool:
        """Run complete validation suite"""
        logger.info("=" * 60)
        logger.info("Pydro Configuration Validation")
        logger.info("=" * 60)
        
        # Core MQTT settings
        logger.info("\n[1] MQTT Configuration")
        self.validate_required_env("MQTT_BROKER", "MQTT Broker IP")
        self.validate_required_env("MQTT_USERNAME", "MQTT Username")
        self.validate_required_env("MQTT_PASSWORD", "MQTT Password")
        self.validate_mqtt()
        
        # WiFi (for ESP32)
        logger.info("\n[2] WiFi Configuration")
        self.validate_required_env("WIFI_SSID", "WiFi SSID")
        self.validate_required_env("WIFI_PASSWORD", "WiFi Password")
        
        # Twilio SMS
        logger.info("\n[3] Twilio SMS")
        self.validate_twilio()
        
        # xAI API
        logger.info("\n[4] xAI Grok API")
        self.validate_xai_api()
        
        # Email (optional)
        logger.info("\n[5] Email Configuration")
        self.validate_optional_env("EMAIL_FROM", "Email sender")
        
        # Network hosts
        logger.info("\n[6] Network Devices")
        self.validate_network_host(
            os.getenv("MQTT_BROKER", "10.0.0.62"), 
            "RPi5"
        )
        self.validate_network_host(
            os.getenv("COOL_TOWER_ESP32_IP", "10.0.0.63"),
            "Cool Tower ESP32"
        )
        self.validate_network_host(
            os.getenv("WARM_TOWER_ESP32_IP", "10.0.0.64"),
            "Warm Tower ESP32"
        )
        
        # Directories
        logger.info("\n[7] Directory Structure")
        self.validate_directory(
            os.getenv("IMAGE_STORAGE_PATH", "/home/pi/hydro_images"),
            "Image Storage",
            create=True
        )
        self.validate_directory(
            "/home/pi/hydro_data",
            "Database Storage",
            create=True
        )
        self.validate_directory(
            os.getenv("LOG_PATH", "/home/pi/hydro_logs"),
            "Log Storage",
            create=True
        )
        
        # Plant tracking config
        logger.info("\n[8] Plant Tracking Configuration")
        max_plants = int(os.getenv("MAX_PLANTS_PER_TOWER", 30))
        if max_plants <= 30:
            self.passed.append(f"✓ Max plants per tower: {max_plants}")
        else:
            self.warnings.append(f"Max plants ({max_plants}) exceeds recommended 30")
        
        # VPD configuration
        logger.info("\n[9] VPD Monitoring")
        vpd_low = float(os.getenv("VPD_ALERT_THRESHOLD_LOW", 0.4))
        vpd_high = float(os.getenv("VPD_ALERT_THRESHOLD_HIGH", 1.5))
        if 0.2 <= vpd_low <= vpd_high <= 2.0:
            self.passed.append(f"✓ VPD thresholds: {vpd_low}-{vpd_high} kPa")
        else:
            self.errors.append(f"Invalid VPD thresholds: {vpd_low}-{vpd_high}")
        
        # Dosing configuration
        logger.info("\n[10] Dosing System")
        reservoir_gallons = float(os.getenv("RESERVOIR_VOLUME_GALLONS", 5))
        if reservoir_gallons == 5:
            self.passed.append(f"✓ Reservoir volume: {reservoir_gallons} gallons")
        else:
            self.warnings.append(f"Non-standard reservoir size: {reservoir_gallons} gallons")
        
        auto_dosing = os.getenv("ENABLE_AUTO_DOSING", "false").lower() == "true"
        if auto_dosing:
            self.warnings.append("⚠ Auto-dosing ENABLED - monitor carefully!")
        else:
            self.passed.append("✓ Auto-dosing disabled (safe mode)")
        
        # Home Assistant
        logger.info("\n[11] Home Assistant Integration")
        ha_enabled = os.getenv("ENABLE_HOME_ASSISTANT", "true").lower() == "true"
        if ha_enabled:
            self.passed.append("✓ Home Assistant MQTT Discovery enabled")
        
        # Alexa
        logger.info("\n[12] Alexa Integration")
        alexa_enabled = os.getenv("ENABLE_ALEXA", "true").lower() == "true"
        if alexa_enabled:
            self.passed.append("✓ Alexa integration enabled")
        
        # Print results
        logger.info("\n" + "=" * 60)
        logger.info("VALIDATION RESULTS")
        logger.info("=" * 60)
        
        if self.passed:
            logger.info(f"\n✓ PASSED ({len(self.passed)}):")
            for msg in self.passed[:10]:  # Show first 10
                logger.info(f"  {msg}")
            if len(self.passed) > 10:
                logger.info(f"  ... and {len(self.passed) - 10} more")
        
        if self.warnings:
            logger.info(f"\n⚠ WARNINGS ({len(self.warnings)}):")
            for msg in self.warnings:
                logger.warning(f"  {msg}")
        
        if self.errors:
            logger.info(f"\n✗ ERRORS ({len(self.errors)}):")
            for msg in self.errors:
                logger.error(f"  {msg}")
        
        logger.info("\n" + "=" * 60)
        
        if self.errors:
            logger.error("VALIDATION FAILED - Fix errors before starting system")
            return False
        elif self.warnings:
            logger.warning("VALIDATION PASSED with warnings - Some features may be limited")
            return True
        else:
            logger.info("VALIDATION PASSED - All systems configured correctly")
            return True

def main():
    validator = ConfigValidator()
    success = validator.run_full_validation()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
