#!/usr/bin/env python3
"""
Quick Start Test Script
Validates all system components are configured correctly
"""

import os
import sys
from pathlib import Path

print("""
╔══════════════════════════════════════════════════════════════╗
║     Hydroponic AI System - Quick Start Validation           ║
╚══════════════════════════════════════════════════════════════╝
""")

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'rpi5'))

checks_passed = 0
checks_failed = 0


def check(name, test_func):
    """Run a check and track results"""
    global checks_passed, checks_failed
    
    print(f"\n{'='*60}")
    print(f"Checking: {name}")
    print('='*60)
    
    try:
        result = test_func()
        if result:
            print(f"✓ {name}: PASS")
            checks_passed += 1
        else:
            print(f"✗ {name}: FAIL")
            checks_failed += 1
    except Exception as e:
        print(f"✗ {name}: ERROR - {e}")
        checks_failed += 1


def check_env_file():
    """Check if .env file exists"""
    env_path = Path('.env')
    if not env_path.exists():
        print("✗ .env file not found")
        print("  Copy .env.template to .env and configure")
        return False
    
    print("✓ .env file exists")
    
    # Check for critical variables
    from dotenv import load_dotenv
    load_dotenv()
    
    critical_vars = ['MQTT_BROKER', 'TWILIO_ACCOUNT_SID', 'XAI_API_KEY']
    missing = []
    
    for var in critical_vars:
        value = os.getenv(var)
        if not value or 'your_' in value.lower():
            missing.append(var)
            print(f"  ⚠ {var} not configured")
        else:
            print(f"  ✓ {var} configured")
    
    if missing:
        print(f"\n  Configure these in .env: {', '.join(missing)}")
        return False
    
    return True


def check_dependencies():
    """Check Python dependencies"""
    required = [
        'paho.mqtt',
        'cv2',
        'numpy',
        'PIL',
        'twilio',
        'requests',
        'dotenv'
    ]
    
    missing = []
    
    for module_name in required:
        module_import = module_name.replace('.', '_')
        try:
            __import__(module_name)
            print(f"  ✓ {module_name}")
        except ImportError:
            missing.append(module_name)
            print(f"  ✗ {module_name} - not installed")
    
    if missing:
        print(f"\n  Install missing: pip install {' '.join(missing)}")
        return False
    
    return True


def check_mqtt_broker():
    """Check MQTT broker connectivity"""
    try:
        import paho.mqtt.client as mqtt
        from dotenv import load_dotenv
        load_dotenv()
        
        broker = os.getenv('MQTT_BROKER', '10.0.0.62')
        port = int(os.getenv('MQTT_PORT', 1883))
        
        print(f"  Connecting to {broker}:{port}...")
        
        connected = [False]
        
        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                connected[0] = True
        
        client = mqtt.Client(client_id="quick_start_test")
        client.on_connect = on_connect
        
        username = os.getenv('MQTT_USERNAME')
        password = os.getenv('MQTT_PASSWORD')
        if username and password:
            client.username_pw_set(username, password)
        
        client.connect(broker, port, 10)
        client.loop_start()
        
        import time
        time.sleep(2)
        
        client.loop_stop()
        client.disconnect()
        
        if connected[0]:
            print(f"  ✓ Connected to MQTT broker at {broker}")
            return True
        else:
            print(f"  ✗ Failed to connect to MQTT broker")
            return False
            
    except Exception as e:
        print(f"  ✗ MQTT test error: {e}")
        return False


def check_directories():
    """Check required directories exist"""
    required_dirs = [
        'rpi5',
        'esp32',
        'pi_zero',
        'utils',
        'models'
    ]
    
    all_exist = True
    
    for dirname in required_dirs:
        dirpath = Path(dirname)
        if dirpath.exists():
            print(f"  ✓ {dirname}/")
        else:
            print(f"  ✗ {dirname}/ - missing")
            all_exist = False
    
    return all_exist


def check_ai_modules():
    """Check AI system modules can be imported"""
    try:
        from sensor_monitor import SensorMonitor
        print("  ✓ sensor_monitor")
        
        from image_analyzer import ImageAnalyzer
        print("  ✓ image_analyzer")
        
        from sms_alerts import SMSAlertSystem
        print("  ✓ sms_alerts")
        
        from nutrient_advisor import NutrientAdvisor
        print("  ✓ nutrient_advisor")
        
        return True
        
    except ImportError as e:
        print(f"  ✗ Module import error: {e}")
        return False


def main():
    """Run all checks"""
    global checks_passed, checks_failed
    
    # Run checks
    check("Environment Configuration", check_env_file)
    check("Python Dependencies", check_dependencies)
    check("Directory Structure", check_directories)
    check("AI System Modules", check_ai_modules)
    check("MQTT Broker Connection", check_mqtt_broker)
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print('='*60)
    print(f"Checks Passed: {checks_passed}")
    print(f"Checks Failed: {checks_failed}")
    print()
    
    if checks_failed == 0:
        print("✓ All checks passed! System ready to run.")
        print()
        print("Start the system with:")
        print("  python3 rpi5/hydro_ai_main.py")
        print()
        print("Or install as systemd service:")
        print("  sudo bash utils/setup_systemd.sh")
        return 0
    else:
        print("✗ Some checks failed. Review errors above.")
        print()
        print("Common fixes:")
        print("  1. Install dependencies: pip install -r requirements.txt")
        print("  2. Configure .env from .env.template")
        print("  3. Start Mosquitto: sudo systemctl start mosquitto")
        return 1


if __name__ == '__main__':
    sys.exit(main())
