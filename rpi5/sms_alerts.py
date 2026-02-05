#!/usr/bin/env python3
"""
SMS Alert System using Twilio
Sends formatted SMS alerts to user for hydroponic system issues

Part of the Dual Tower Hydroponic AI System
"""

import os
from datetime import datetime
from dotenv import load_dotenv
import logging
from typing import Dict, List, Optional

try:
    from twilio.rest import Client
    from twilio.base.exceptions import TwilioRestException
except ImportError:
    Client = None
    TwilioRestException = Exception
    logging.warning("Twilio not installed - SMS alerts disabled")

load_dotenv()

logger = logging.getLogger('sms_alerts')


class SMSAlertSystem:
    def __init__(self):
        self.account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        self.auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        self.from_phone = os.getenv('TWILIO_FROM_PHONE')
        self.to_phone = os.getenv('TWILIO_TO_PHONE')
        
        self.client = None
        self.enabled = False
        
        if Client and all([self.account_sid, self.auth_token, self.from_phone, self.to_phone]):
            try:
                self.client = Client(self.account_sid, self.auth_token)
                self.enabled = True
                logger.info("Twilio SMS client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Twilio client: {e}")
        else:
            logger.warning("Twilio credentials not configured - SMS alerts disabled")
    
    def send_alert(self, tower: str, issue: str, suggestion: str, 
                   sensor_data: Optional[Dict] = None, image_data: Optional[Dict] = None) -> bool:
        """
        Send formatted SMS alert
        
        Format: "Brian, [Tower]: [Issue] | Suggestion: [Action] | Data: [Values] | Time: [Timestamp]"
        Max 160 characters for standard SMS
        """
        if not self.enabled:
            logger.warning("SMS alerts disabled - cannot send message")
            return False
        
        try:
            # Format message
            message = self._format_message(tower, issue, suggestion, sensor_data, image_data)
            
            # Send via Twilio
            result = self.client.messages.create(
                body=message,
                from_=self.from_phone,
                to=self.to_phone
            )
            
            logger.info(f"SMS sent successfully: SID {result.sid}")
            logger.debug(f"Message: {message}")
            return True
            
        except TwilioRestException as e:
            logger.error(f"Twilio error: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to send SMS: {e}")
            return False
    
    def _format_message(self, tower: str, issue: str, suggestion: str,
                       sensor_data: Optional[Dict], image_data: Optional[Dict]) -> str:
        """
        Format SMS message with 160 character limit consideration
        Priority: Issue > Suggestion > Data > Time
        """
        # Base message
        tower_name = tower.capitalize()
        timestamp = datetime.now().strftime('%m/%d %H:%M')
        
        # Truncate long texts
        issue = self._truncate(issue, 40)
        suggestion = self._truncate(suggestion, 50)
        
        # Build data string
        data_str = ""
        if sensor_data:
            data_parts = []
            if 'ec' in sensor_data and sensor_data['ec'] is not None:
                data_parts.append(f"EC:{sensor_data['ec']:.1f}")
            if 'ph' in sensor_data and sensor_data['ph'] is not None:
                data_parts.append(f"pH:{sensor_data['ph']:.1f}")
            if 'water_temp' in sensor_data and sensor_data['water_temp'] is not None:
                data_parts.append(f"Temp:{sensor_data['water_temp']:.0f}F")
            
            if data_parts:
                data_str = " | " + " ".join(data_parts)
        
        # Assemble message
        message = f"Brian, {tower_name} Tower: {issue} | {suggestion}{data_str} | {timestamp}"
        
        # If over 160, progressively trim
        if len(message) > 160:
            # Try without data
            message = f"Brian, {tower_name} Tower: {issue} | {suggestion} | {timestamp}"
        
        if len(message) > 160:
            # Trim suggestion further
            suggestion = self._truncate(suggestion, 30)
            message = f"Brian, {tower_name} Tower: {issue} | {suggestion} | {timestamp}"
        
        if len(message) > 160:
            # Last resort - very short format
            message = f"{tower_name}: {self._truncate(issue, 50)} | {self._truncate(suggestion, 40)}"
        
        return message[:160]  # Hard limit
    
    def _truncate(self, text: str, max_len: int) -> str:
        """Truncate text to max length"""
        if len(text) <= max_len:
            return text
        return text[:max_len-3] + "..."
    
    def send_sensor_alert(self, tower: str, issue_data: Dict, 
                         sensor_data: Dict, env_data: Dict) -> bool:
        """Send alert for sensor threshold violation"""
        issue = issue_data['message']
        suggestion = issue_data['suggestion']
        
        # Combine sensor and environment data
        combined_data = {**sensor_data}
        if env_data:
            if 'air_temp' in env_data:
                combined_data['air_temp'] = env_data['air_temp']
            if 'humidity' in env_data:
                combined_data['humidity'] = env_data['humidity']
        
        return self.send_alert(tower, issue, suggestion, combined_data)
    
    def send_image_alert(self, tower: str, deficiency: str, suggestion: str,
                        confidence: float, sensor_data: Optional[Dict] = None) -> bool:
        """Send alert for image-detected deficiency"""
        issue = f"{deficiency.replace('_', ' ').title()} ({int(confidence*100)}% conf.)"
        return self.send_alert(tower, issue, suggestion, sensor_data)
    
    def send_reservoir_alert(self, tower: str, days_since_change: int,
                            reason: str = "scheduled") -> bool:
        """Send alert for reservoir change needed"""
        issue = f"Reservoir change due ({days_since_change}d)"
        suggestion = f"Fresh change suggested - {reason}"
        return self.send_alert(tower, issue, suggestion)
    
    def send_harvest_alert(self, tower: str, plant_type: str, urgency: str = "ready") -> bool:
        """Send alert for harvest readiness"""
        if urgency == "urgent":
            issue = f"{plant_type} flowering/bolting"
            suggestion = "HARVEST NOW - quality declining"
        else:
            issue = f"{plant_type} ready for harvest"
            suggestion = "Harvest soon for best flavor"
        
        return self.send_alert(tower, issue, suggestion)
    
    def send_led_adjustment_alert(self, tower: str, new_intensity: int, reason: str) -> bool:
        """Send alert for LED intensity adjustment"""
        issue = f"LED dimmed to {new_intensity}%"
        suggestion = reason
        return self.send_alert(tower, issue, suggestion)
    
    def send_manual_check_alert(self, tower: str, check_type: str, reason: str) -> bool:
        """Send alert requesting manual intervention"""
        issue = f"Manual {check_type} test needed"
        suggestion = reason
        return self.send_alert(tower, issue, suggestion)
    
    def send_calibration_alert(self, tower: str, sensor: str, discrepancy: str) -> bool:
        """Send alert for sensor calibration needed"""
        issue = f"{sensor} calibration needed"
        suggestion = f"Discrepancy: {discrepancy}"
        return self.send_alert(tower, issue, suggestion)
    
    def test_connection(self) -> bool:
        """Test SMS connection with simple message"""
        if not self.enabled:
            logger.error("Cannot test - SMS not enabled")
            return False
        
        try:
            message = f"Hydro System Test - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            result = self.client.messages.create(
                body=message,
                from_=self.from_phone,
                to=self.to_phone
            )
            logger.info(f"Test SMS sent: {result.sid}")
            return True
        except Exception as e:
            logger.error(f"Test SMS failed: {e}")
            return False


if __name__ == '__main__':
    # Test mode
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    sms = SMSAlertSystem()
    
    if sms.enabled:
        print("SMS Alert System initialized")
        
        # Test message
        test = input("Send test SMS? (y/n): ")
        if test.lower() == 'y':
            if sms.test_connection():
                print("Test SMS sent successfully!")
            else:
                print("Test SMS failed - check logs")
        
        # Example alerts
        print("\nExample alert formats:")
        
        # Sensor alert
        sms.send_sensor_alert(
            'cool',
            {'message': 'pH high: 6.5', 'suggestion': 'Add pH Down'},
            {'ec': 1.4, 'ph': 6.5, 'water_temp': 68.0},
            {'air_temp': 65.0, 'humidity': 60.0}
        )
        
        # Image alert
        sms.send_image_alert(
            'warm',
            'tip_burn',
            'Apply foliar Ca spray',
            0.85,
            {'ec': 1.8, 'ph': 6.1}
        )
        
    else:
        print("SMS Alert System not configured")
        print("Set TWILIO credentials in .env file to enable")
