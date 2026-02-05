#!/usr/bin/env python3
"""
Sensor Calibration Utility
Interactive tool for calibrating Atlas Scientific sensors (EC, pH)
"""

import os
import sys
import time
from datetime import datetime

print("""
╔══════════════════════════════════════════════════════════════╗
║        Atlas Scientific Sensor Calibration Utility           ║
║            For Hydroponic Monitoring System                  ║
╚══════════════════════════════════════════════════════════════╝
""")

print("This utility helps calibrate Atlas Scientific EZO sensors.")
print("You must have the sensors connected via I2C and MQTT.")
print()

# Import MQTT after banner
try:
    import paho.mqtt.client as mqtt
    from dotenv import load_dotenv
except ImportError as e:
    print(f"Error: Missing dependency - {e}")
    print("Install: pip install paho-mqtt python-dotenv")
    sys.exit(1)

load_dotenv()

MQTT_BROKER = os.getenv('MQTT_BROKER', '10.0.0.62')
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))
MQTT_USERNAME = os.getenv('MQTT_USERNAME', 'hydro_user')
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD', '')


def show_menu():
    """Display main menu"""
    print("\n" + "=" * 60)
    print("Sensor Calibration Menu")
    print("=" * 60)
    print("1. pH Sensor Calibration (3-point)")
    print("2. EC Sensor Calibration (2-point)")
    print("3. View Current Readings")
    print("4. Exit")
    print("=" * 60)


def calibrate_ph():
    """pH sensor calibration guide"""
    print("\n" + "=" * 60)
    print("pH Sensor Calibration (Atlas Scientific Gen 3)")
    print("=" * 60)
    print()
    print("Required materials:")
    print("  - pH 4.0 calibration solution")
    print("  - pH 7.0 calibration solution")
    print("  - pH 10.0 calibration solution")
    print("  - Distilled/RO water for rinsing")
    print()
    print("IMPORTANT:")
    print("  - Ensure probe is clean and rinsed")
    print("  - Remove storage cap and rinse with RO water")
    print("  - Shake off excess water (don't wipe)")
    print()
    
    input("Press Enter when ready to start calibration...")
    
    print("\n--- Step 1: Mid-point (pH 7.0) ---")
    print("1. Place probe in pH 7.0 solution")
    print("2. Wait 30 seconds for reading to stabilize")
    print("3. On ESP32 Arduino Serial Monitor, send command:")
    print("   Cal,mid,7.0")
    print("4. Wait for 'Success' response")
    
    input("\nPress Enter when mid-point calibration complete...")
    
    print("\n--- Step 2: Low-point (pH 4.0) ---")
    print("1. Rinse probe with RO water")
    print("2. Place probe in pH 4.0 solution")
    print("3. Wait 30 seconds")
    print("4. Send command: Cal,low,4.0")
    
    input("\nPress Enter when low-point calibration complete...")
    
    print("\n--- Step 3: High-point (pH 10.0) ---")
    print("1. Rinse probe with RO water")
    print("2. Place probe in pH 10.0 solution")
    print("3. Wait 30 seconds")
    print("4. Send command: Cal,high,10.0")
    
    input("\nPress Enter when high-point calibration complete...")
    
    print("\n✓ pH calibration complete!")
    print("  - Rinse probe thoroughly with RO water")
    print("  - Store in storage solution or pH 7.0 buffer")
    print("  - Test with known pH solution to verify")


def calibrate_ec():
    """EC sensor calibration guide"""
    print("\n" + "=" * 60)
    print("EC Sensor Calibration (Atlas Scientific EC Mini)")
    print("=" * 60)
    print()
    print("Required materials:")
    print("  - EC calibration solution (e.g., 1413 μS/cm)")
    print("  - Distilled/RO water (dry calibration)")
    print()
    print("IMPORTANT:")
    print("  - Ensure probe is clean and dry for first step")
    print("  - Temperature compensation should be enabled")
    print()
    
    input("Press Enter when ready to start calibration...")
    
    print("\n--- Step 1: Dry Calibration (0 μS/cm) ---")
    print("1. Ensure probe is completely dry")
    print("2. Keep probe in air (not touching anything)")
    print("3. Send command: Cal,dry")
    print("4. Wait for 'Success' response")
    
    input("\nPress Enter when dry calibration complete...")
    
    print("\n--- Step 2: Single-point Calibration ---")
    print("1. Place probe in calibration solution (e.g., 1413 μS/cm)")
    print("2. Wait 30 seconds for reading to stabilize")
    print("3. Send command: Cal,1413")
    print("   (Replace 1413 with your calibration solution value)")
    print("4. Wait for 'Success' response")
    
    input("\nPress Enter when calibration complete...")
    
    print("\n✓ EC calibration complete!")
    print("  - Rinse probe thoroughly with RO water")
    print("  - Test with known EC solution to verify")
    print("  - Store probe dry or in storage solution")


def view_readings():
    """Display current sensor readings via MQTT"""
    print("\n" + "=" * 60)
    print("Current Sensor Readings")
    print("=" * 60)
    print("Listening to MQTT topics for 10 seconds...")
    print()
    
    readings = {}
    
    def on_message(client, userdata, msg):
        topic = msg.topic
        value = msg.payload.decode('utf-8')
        readings[topic] = value
        print(f"  {topic}: {value}")
    
    client = mqtt.Client(client_id="calibration_reader")
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.on_message = on_message
    
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        
        topics = [
            '/cool_tower/ec',
            '/cool_tower/ph',
            '/warm_tower/ec',
            '/warm_tower/ph',
            '/environment/air_temp',
            '/environment/humidity'
        ]
        
        for topic in topics:
            client.subscribe(topic)
        
        client.loop_start()
        time.sleep(10)
        client.loop_stop()
        client.disconnect()
        
        if not readings:
            print("\n⚠ No readings received")
            print("  - Check MQTT broker is running")
            print("  - Check ESP32 devices are online")
        
    except Exception as e:
        print(f"✗ Error: {e}")


def main():
    """Main program loop"""
    while True:
        show_menu()
        
        choice = input("\nEnter choice (1-4): ").strip()
        
        if choice == '1':
            calibrate_ph()
        elif choice == '2':
            calibrate_ec()
        elif choice == '3':
            view_readings()
        elif choice == '4':
            print("\nExiting calibration utility...")
            break
        else:
            print("\n✗ Invalid choice. Please enter 1-4.")
    
    print("\n✓ Calibration utility closed")
    print("Remember to log calibration dates in your maintenance log!")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(0)
