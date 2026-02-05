#!/usr/bin/env python3
"""
NOIR (Near-Infrared) Camera Capture for Pi Zero 2W
Captures near-IR/thermal images using Raspberry Pi Camera Module 3 NOIR
Sends images to RPi5 for AI analysis via MQTT or network share

Deploy to: Cool Tower NOIR, Warm Tower NOIR
"""

import os
import sys
import time
from datetime import datetime
from pathlib import Path
import paho.mqtt.client as mqtt
from dotenv import load_dotenv
import json
import socket

# Import picamera2 (only available on Raspberry Pi)
try:
    from picamera2 import Picamera2
    from libcamera import controls
except ImportError:
    print("Warning: picamera2 not available. Running in mock mode.")
    Picamera2 = None

# Load environment variables
load_dotenv()

# Configuration
MQTT_BROKER = os.getenv('MQTT_BROKER', '10.0.0.62')
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))
MQTT_USERNAME = os.getenv('MQTT_USERNAME', 'hydro_user')
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD', '')

# Determine tower from hostname or config
HOSTNAME = socket.gethostname()
if 'cool' in HOSTNAME.lower() or 'COOL_TOWER' in os.environ:
    TOWER_NAME = 'cool'
elif 'warm' in HOSTNAME.lower() or 'WARM_TOWER' in os.environ:
    TOWER_NAME = 'warm'
else:
    TOWER_NAME = os.getenv('TOWER_NAME', 'unknown')

CAMERA_TYPE = 'noir'
MQTT_TOPIC_IMAGE = f"/{TOWER_NAME}_tower/camera/{CAMERA_TYPE}"
MQTT_TOPIC_STATUS = f"/{TOWER_NAME}_tower/camera/{CAMERA_TYPE}/status"

# Image settings
IMAGE_DIR = Path('/home/pi/hydro_images')
IMAGE_DIR.mkdir(parents=True, exist_ok=True)
IMAGE_WIDTH = 2304
IMAGE_HEIGHT = 1296
IMAGE_QUALITY = 85

# Capture interval - every 4 hours during lights-on (6am-10pm)
CAPTURE_INTERVAL_HOURS = 4
LIGHTS_ON_HOUR = 6
LIGHTS_OFF_HOUR = 22

# MQTT Client
mqtt_client = None
camera = None


def setup_mqtt():
    """Initialize MQTT connection"""
    global mqtt_client
    
    mqtt_client = mqtt.Client(client_id=f"{TOWER_NAME}_noir_cam")
    mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print(f"Connected to MQTT broker at {MQTT_BROKER}")
            # Publish online status
            status = {
                'status': 'online',
                'tower': TOWER_NAME,
                'camera': CAMERA_TYPE,
                'ip': get_ip_address()
            }
            client.publish(MQTT_TOPIC_STATUS, json.dumps(status), retain=True)
        else:
            print(f"Failed to connect to MQTT broker, code: {rc}")
    
    def on_disconnect(client, userdata, rc):
        print(f"Disconnected from MQTT broker, code: {rc}")
        if rc != 0:
            print("Unexpected disconnection. Attempting to reconnect...")
    
    mqtt_client.on_connect = on_connect
    mqtt_client.on_disconnect = on_disconnect
    
    # Set last will
    last_will = {
        'status': 'offline',
        'tower': TOWER_NAME,
        'camera': CAMERA_TYPE
    }
    mqtt_client.will_set(MQTT_TOPIC_STATUS, json.dumps(last_will), retain=True)
    
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.loop_start()
        return True
    except Exception as e:
        print(f"Error connecting to MQTT: {e}")
        return False


def setup_camera():
    """Initialize Raspberry Pi NOIR Camera"""
    global camera
    
    if Picamera2 is None:
        print("Camera not available (running in mock mode)")
        return False
    
    try:
        camera = Picamera2()
        
        # Configure camera for NOIR (near-infrared)
        # Disable AWB for IR imaging, use manual controls
        config = camera.create_still_configuration(
            main={"size": (IMAGE_WIDTH, IMAGE_HEIGHT)},
            controls={
                "AfMode": controls.AfModeEnum.Continuous,
                "AeEnable": True,
                "AwbEnable": False,  # Disable auto white balance for IR
                "AwbMode": controls.AwbModeEnum.Tungsten,  # Better for IR
                "ExposureTime": 10000,  # Microseconds - adjust as needed
                "AnalogueGain": 2.0  # Increase sensitivity for IR
            }
        )
        camera.configure(config)
        camera.start()
        
        # Allow camera to warm up
        time.sleep(2)
        
        print("NOIR camera initialized successfully")
        return True
        
    except Exception as e:
        print(f"Error initializing NOIR camera: {e}")
        return False


def capture_image():
    """Capture IR image from NOIR camera"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{TOWER_NAME}_{CAMERA_TYPE}_{timestamp}.jpg"
    filepath = IMAGE_DIR / filename
    
    try:
        if camera:
            # Capture image
            camera.capture_file(str(filepath))
            print(f"Captured IR image: {filepath}")
            
            # Get file size
            file_size = filepath.stat().st_size
            
            return filepath, file_size
        else:
            # Mock mode - create placeholder
            print(f"Mock capture: {filepath}")
            with open(filepath, 'w') as f:
                f.write("Mock IR image data")
            return filepath, 100
            
    except Exception as e:
        print(f"Error capturing IR image: {e}")
        return None, 0


def send_image_mqtt(filepath, file_size):
    """Send IR image metadata to RPi5 via MQTT"""
    try:
        metadata = {
            'tower': TOWER_NAME,
            'camera_type': CAMERA_TYPE,
            'filename': filepath.name,
            'filepath': str(filepath),
            'file_size': file_size,
            'timestamp': datetime.now().isoformat(),
            'width': IMAGE_WIDTH,
            'height': IMAGE_HEIGHT,
            'spectrum': 'near_infrared'
        }
        
        # Publish metadata
        mqtt_client.publish(MQTT_TOPIC_IMAGE, json.dumps(metadata), qos=1)
        print(f"Sent IR image metadata via MQTT: {filepath.name}")
        
        # Note: Actual image file should be accessed via network share
        # or transferred via separate mechanism (rsync, sftp, etc.)
        
        return True
        
    except Exception as e:
        print(f"Error sending IR image metadata: {e}")
        return False


def is_lights_on():
    """Check if grow lights should be on based on schedule"""
    current_hour = datetime.now().hour
    return LIGHTS_ON_HOUR <= current_hour < LIGHTS_OFF_HOUR


def get_ip_address():
    """Get local IP address"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "unknown"


def cleanup():
    """Cleanup resources"""
    global camera, mqtt_client
    
    print("\nShutting down...")
    
    if camera and Picamera2:
        camera.stop()
        camera.close()
    
    if mqtt_client:
        status = {
            'status': 'offline',
            'tower': TOWER_NAME,
            'camera': CAMERA_TYPE
        }
        mqtt_client.publish(MQTT_TOPIC_STATUS, json.dumps(status), retain=True)
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
    
    print("Cleanup complete")


def main():
    """Main capture loop"""
    print(f"=== NOIR Camera Starting ===")
    print(f"Tower: {TOWER_NAME}")
    print(f"Camera Type: {CAMERA_TYPE} (Near-Infrared)")
    print(f"Image Directory: {IMAGE_DIR}")
    print(f"Capture Interval: {CAPTURE_INTERVAL_HOURS} hours")
    print(f"Lights Schedule: {LIGHTS_ON_HOUR}:00 - {LIGHTS_OFF_HOUR}:00")
    print("=" * 40)
    
    # Setup
    if not setup_mqtt():
        print("Failed to setup MQTT. Exiting.")
        return
    
    if not setup_camera():
        print("Warning: NOIR camera setup failed. Running in mock mode.")
    
    try:
        last_capture_time = 0
        capture_interval_seconds = CAPTURE_INTERVAL_HOURS * 3600
        
        while True:
            current_time = time.time()
            
            # Check if it's time to capture
            if current_time - last_capture_time >= capture_interval_seconds:
                
                # Only capture during lights-on hours
                if is_lights_on():
                    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]")
                    print("Capturing IR image...")
                    
                    filepath, file_size = capture_image()
                    
                    if filepath and file_size > 0:
                        send_image_mqtt(filepath, file_size)
                        last_capture_time = current_time
                    else:
                        print("IR image capture failed")
                else:
                    print(f"Lights off (current hour: {datetime.now().hour}). Skipping capture.")
                    # Still update last capture time to avoid immediate retry
                    last_capture_time = current_time
            
            # MQTT keepalive
            time.sleep(60)  # Check every minute
            
    except KeyboardInterrupt:
        print("\nReceived interrupt signal")
    except Exception as e:
        print(f"Error in main loop: {e}")
    finally:
        cleanup()


if __name__ == '__main__':
    main()
