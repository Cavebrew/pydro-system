#!/usr/bin/env python3
"""
MQTT Test Utility
Test MQTT broker connection and publish/subscribe functionality
"""

import os
import sys
import time
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv()

MQTT_BROKER = os.getenv('MQTT_BROKER', '10.0.0.62')
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))
MQTT_USERNAME = os.getenv('MQTT_USERNAME', 'hydro_user')
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD', '')

received_messages = []


def on_connect(client, userdata, flags, rc):
    """Connection callback"""
    if rc == 0:
        print(f"✓ Connected to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
        print(f"  Client ID: {client._client_id.decode()}")
        
        # Subscribe to test topics
        test_topics = [
            '/cool_tower/#',
            '/warm_tower/#',
            '/environment/#'
        ]
        for topic in test_topics:
            client.subscribe(topic)
            print(f"  Subscribed to: {topic}")
    else:
        print(f"✗ Connection failed with code {rc}")
        print(f"  0: Success")
        print(f"  1: Incorrect protocol version")
        print(f"  2: Invalid client identifier")
        print(f"  3: Server unavailable")
        print(f"  4: Bad username or password")
        print(f"  5: Not authorized")


def on_disconnect(client, userdata, rc):
    """Disconnection callback"""
    if rc != 0:
        print(f"✗ Unexpected disconnection (code {rc})")
    else:
        print("✓ Disconnected cleanly")


def on_message(client, userdata, msg):
    """Message received callback"""
    topic = msg.topic
    payload = msg.payload.decode('utf-8')
    
    print(f"\n📥 Message received:")
    print(f"   Topic: {topic}")
    print(f"   Payload: {payload}")
    
    received_messages.append((topic, payload))


def main():
    """Main test function"""
    print("=" * 60)
    print("MQTT Broker Test Utility")
    print("=" * 60)
    print()
    
    # Check credentials
    if not MQTT_PASSWORD:
        print("⚠ Warning: MQTT_PASSWORD not set in .env")
        print("  Connection may fail if broker requires authentication")
        print()
    
    # Create client
    client = mqtt.Client(client_id="mqtt_test_utility")
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    
    # Attempt connection
    print(f"Connecting to {MQTT_BROKER}:{MQTT_PORT}...")
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
        
        time.sleep(2)  # Wait for connection
        
        # Publish test messages
        print("\n" + "=" * 60)
        print("Publishing test messages...")
        print("=" * 60)
        
        test_messages = [
            ('/cool_tower/ec', '1.5'),
            ('/cool_tower/ph', '6.0'),
            ('/warm_tower/ec', '1.8'),
            ('/environment/air_temp', '68.0'),
        ]
        
        for topic, payload in test_messages:
            result = client.publish(topic, payload)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                print(f"✓ Published to {topic}: {payload}")
            else:
                print(f"✗ Failed to publish to {topic}")
            time.sleep(0.5)
        
        # Listen for messages
        print("\n" + "=" * 60)
        print("Listening for messages (10 seconds)...")
        print("=" * 60)
        
        time.sleep(10)
        
        # Summary
        print("\n" + "=" * 60)
        print("Test Summary")
        print("=" * 60)
        print(f"Messages received: {len(received_messages)}")
        
        if received_messages:
            print("\nReceived messages:")
            for topic, payload in received_messages:
                print(f"  {topic}: {payload}")
        else:
            print("\n⚠ No messages received")
            print("  Possible issues:")
            print("  - MQTT broker not running")
            print("  - No devices publishing to topics")
            print("  - Firewall blocking connection")
        
        # Disconnect
        client.loop_stop()
        client.disconnect()
        
        print("\n✓ Test complete")
        
    except ConnectionRefusedError:
        print(f"\n✗ Connection refused by {MQTT_BROKER}:{MQTT_PORT}")
        print("  Check that Mosquitto MQTT broker is running:")
        print("    sudo systemctl status mosquitto")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
