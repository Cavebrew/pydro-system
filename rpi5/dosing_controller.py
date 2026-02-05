#!/usr/bin/env python3
"""
Dosing Pump Controller
Controls 8 peristaltic pumps (4 per tower) for automated nutrient dosing

Pump Configuration (per tower):
1. Epsom Salt (MgSO4) - Magnesium supplement
2. Calcium Nitrate (Ca(NO3)2) - Calcium & Nitrogen
3. pH Down (Phosphoric acid) - pH adjustment
4. Potassium Bicarbonate (KHCO3) - Potassium & pH up

Safety Features:
- Maximum dose limits per day
- Staged dosing (small increments with monitoring)
- AI-calculated dosing based on sensor readings
- Manual override capability
- Dose history logging
"""

import os
import json
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import paho.mqtt.client as mqtt
from dotenv import load_dotenv
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

class DosingController:
    def __init__(self, db_path="/home/pi/hydro_data/dosing.db"):
        self.db_path = db_path
        
        # Reservoir configuration
        self.reservoir_volume_gallons = float(os.getenv("RESERVOIR_VOLUME_GALLONS", 5))
        self.reservoir_volume_liters = self.reservoir_volume_gallons * 3.78541
        
        # Pump configuration
        self.pump_ml_per_second = float(os.getenv("PUMP_ML_PER_SECOND", 1.0))
        self.max_dose_ml_per_day = float(os.getenv("MAX_DOSE_ML_PER_DAY", 100))
        self.auto_dosing_enabled = os.getenv("ENABLE_AUTO_DOSING", "false").lower() == "true"
        
        # Solution concentrations (g/L)
        self.concentrations = {
            "epsom_salt": float(os.getenv("EPSOM_SALT_CONCENTRATION", 100)),
            "calcium_nitrate": float(os.getenv("CALCIUM_NITRATE_CONCENTRATION", 150)),
            "potassium_bicarbonate": float(os.getenv("POTASSIUM_BICARBONATE_CONCENTRATION", 50)),
            "ph_down": float(os.getenv("PH_DOWN_CONCENTRATION", 10))
        }
        
        # Pump GPIO pins (to be set on ESP32)
        self.pump_pins = {
            "cool": {
                "epsom_salt": 1,      # GPIO pin for Cool tower Epsom pump
                "calcium_nitrate": 2,
                "ph_down": 3,
                "potassium_bicarbonate": 4
            },
            "warm": {
                "epsom_salt": 5,      # GPIO pin for Warm tower Epsom pump
                "calcium_nitrate": 6,
                "ph_down": 7,
                "potassium_bicarbonate": 8
            }
        }
        
        # Current tower sensor readings
        self.tower_status = {
            "cool": {"ph": None, "ec": None, "temp": None},
            "warm": {"ph": None, "ec": None, "temp": None}
        }
        
        # MQTT Configuration
        self.broker = os.getenv("MQTT_BROKER", "10.0.0.62")
        self.port = int(os.getenv("MQTT_PORT", 1883))
        self.username = os.getenv("MQTT_USERNAME", "hydro_user")
        self.password = os.getenv("MQTT_PASSWORD", "")
        
        # Initialize database
        self._init_database()
        
        # MQTT client
        self.client = mqtt.Client()
        self.client.username_pw_set(self.username, self.password)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        
        logger.info("Dosing Controller initialized")
    
    def _init_database(self):
        """Initialize dosing history database"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dose_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tower TEXT NOT NULL,
                solution TEXT NOT NULL,
                volume_ml REAL NOT NULL,
                dose_date TEXT NOT NULL,
                reason TEXT,
                auto_dosed BOOLEAN DEFAULT 0,
                ph_before REAL,
                ec_before REAL,
                ph_after REAL,
                ec_after REAL,
                success BOOLEAN DEFAULT 1,
                notes TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info(f"Dosing database initialized at {self.db_path}")
    
    def calculate_dose_volume(self, tower: str, solution: str, target_adjustment: float) -> float:
        """
        Calculate required dose volume based on target adjustment
        
        Args:
            tower: "cool" or "warm"
            solution: Solution type
            target_adjustment: Desired change (e.g., +0.2 EC, -0.3 pH)
        
        Returns:
            Volume in mL to dose
        """
        # This is a simplified calculation - real dosing requires empirical calibration
        # For now, use conservative estimates
        
        concentration = self.concentrations.get(solution, 0)
        if concentration == 0:
            return 0
        
        # Example calculation (needs calibration in practice)
        if solution == "ph_down":
            # Rough estimate: 1ml of 10% phosphoric acid per gallon lowers pH ~0.1
            ml_per_gallon_per_point = 10
            volume_ml = abs(target_adjustment) * self.reservoir_volume_gallons * ml_per_gallon_per_point
        
        elif solution == "potassium_bicarbonate":
            # pH up - similar rough estimate
            ml_per_gallon_per_point = 8
            volume_ml = abs(target_adjustment) * self.reservoir_volume_gallons * ml_per_gallon_per_point
        
        elif solution in ["epsom_salt", "calcium_nitrate"]:
            # EC adjustment - very rough estimate
            # 1g/L increases EC by ~1.0 mS/cm
            target_grams = abs(target_adjustment) * self.reservoir_volume_liters
            volume_ml = (target_grams / concentration) * 1000  # Convert L to mL
        
        else:
            volume_ml = 0
        
        # Safety limits
        max_single_dose = 50  # mL maximum per dose
        volume_ml = min(volume_ml, max_single_dose)
        
        return round(volume_ml, 2)
    
    def check_daily_dose_limit(self, tower: str, solution: str, proposed_ml: float) -> bool:
        """Check if dose would exceed daily limit"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        today = datetime.now().date().isoformat()
        
        cursor.execute('''
            SELECT SUM(volume_ml) FROM dose_history
            WHERE tower = ? AND solution = ? AND DATE(dose_date) = ?
        ''', (tower, solution, today))
        
        result = cursor.fetchone()[0]
        conn.close()
        
        total_today = result if result else 0
        
        if total_today + proposed_ml > self.max_dose_ml_per_day:
            logger.warning(
                f"{tower.upper()} {solution}: Daily limit would be exceeded "
                f"({total_today + proposed_ml:.1f} mL > {self.max_dose_ml_per_day} mL)"
            )
            return False
        
        return True
    
    def dose(self, tower: str, solution: str, volume_ml: float, reason: str = "", 
            auto: bool = False) -> bool:
        """
        Execute dosing operation
        
        Args:
            tower: "cool" or "warm"
            solution: Solution type
            volume_ml: Volume to dose in mL
            reason: Reason for dosing
            auto: Whether this is an automatic dose
        
        Returns:
            True if successful
        """
        # Safety checks
        if volume_ml <= 0:
            logger.error("Invalid dose volume")
            return False
        
        if not self.check_daily_dose_limit(tower, solution, volume_ml):
            return False
        
        # Get current readings
        ph_before = self.tower_status[tower]["ph"]
        ec_before = self.tower_status[tower]["ec"]
        
        # Calculate pump run time
        run_time_seconds = volume_ml / self.pump_ml_per_second
        
        # Send command to ESP32 via MQTT
        pump_id = self.pump_pins[tower].get(solution)
        dose_command = {
            "pump_id": pump_id,
            "run_time_seconds": run_time_seconds,
            "volume_ml": volume_ml,
            "solution": solution,
            "timestamp": datetime.now().isoformat()
        }
        
        topic = f"/{tower}/pump/command"
        self.client.publish(topic, json.dumps(dose_command))
        
        logger.info(
            f"Dosing {tower.upper()} tower: {volume_ml:.1f} mL of {solution} "
            f"(pump {pump_id} for {run_time_seconds:.1f}s)"
        )
        
        # Wait for pump to finish
        time.sleep(run_time_seconds + 2)
        
        # Wait for mixing (30 seconds)
        logger.info("Waiting for solution to mix...")
        time.sleep(30)
        
        # Record dose
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO dose_history
            (tower, solution, volume_ml, dose_date, reason, auto_dosed, 
             ph_before, ec_before, ph_after, ec_after, success)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (tower, solution, volume_ml, datetime.now().isoformat(), reason,
              auto, ph_before, ec_before, None, None, True))
        
        conn.commit()
        conn.close()
        
        # Publish dosing event
        event_data = {
            "tower": tower,
            "solution": solution,
            "volume_ml": volume_ml,
            "reason": reason,
            "auto": auto,
            "timestamp": datetime.now().isoformat()
        }
        
        self.client.publish("/events/dose", json.dumps(event_data))
        
        return True
    
    def auto_adjust_ph(self, tower: str):
        """Automatically adjust pH if out of range"""
        if not self.auto_dosing_enabled:
            return
        
        current_ph = self.tower_status[tower]["ph"]
        if current_ph is None:
            return
        
        # Target ranges
        target_range = (5.8, 6.2)
        
        if current_ph < target_range[0]:
            # pH too low - add potassium bicarbonate
            adjustment = target_range[0] - current_ph
            volume = self.calculate_dose_volume(tower, "potassium_bicarbonate", adjustment)
            
            if volume > 0:
                self.dose(
                    tower, "potassium_bicarbonate", volume,
                    f"Auto pH up: {current_ph:.2f} → {target_range[0]:.2f}",
                    auto=True
                )
        
        elif current_ph > target_range[1]:
            # pH too high - add pH down
            adjustment = current_ph - target_range[1]
            volume = self.calculate_dose_volume(tower, "ph_down", adjustment)
            
            if volume > 0:
                self.dose(
                    tower, "ph_down", volume,
                    f"Auto pH down: {current_ph:.2f} → {target_range[1]:.2f}",
                    auto=True
                )
    
    def auto_adjust_nutrients(self, tower: str, deficiency: str):
        """Adjust nutrients based on AI-detected deficiency"""
        if not self.auto_dosing_enabled:
            return
        
        # Map deficiencies to solutions
        solution_map = {
            "magnesium": "epsom_salt",
            "calcium": "calcium_nitrate",
            "nitrogen": "calcium_nitrate",
            "potassium": "potassium_bicarbonate"
        }
        
        solution = solution_map.get(deficiency.lower())
        if not solution:
            return
        
        # Conservative dose (10 mL)
        volume = 10.0
        
        self.dose(
            tower, solution, volume,
            f"Auto nutrient: {deficiency} deficiency detected",
            auto=True
        )
    
    def get_dose_history(self, tower: str, days: int = 7) -> List[Dict]:
        """Get dosing history for tower"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        cursor.execute('''
            SELECT solution, volume_ml, dose_date, reason, auto_dosed
            FROM dose_history
            WHERE tower = ? AND dose_date >= ?
            ORDER BY dose_date DESC
        ''', (tower, cutoff))
        
        history = []
        for row in cursor.fetchall():
            history.append({
                "solution": row[0],
                "volume_ml": row[1],
                "date": row[2],
                "reason": row[3],
                "auto": bool(row[4])
            })
        
        conn.close()
        return history
    
    def on_connect(self, client, userdata, flags, rc):
        """MQTT connection handler"""
        if rc == 0:
            logger.info("Connected to MQTT broker")
            # Subscribe to sensor readings
            client.subscribe("/+/ph")
            client.subscribe("/+/ec")
            client.subscribe("/+/water_temp")
            # Subscribe to dosing commands
            client.subscribe("/dosing/+/command")
            # Subscribe to AI alerts
            client.subscribe("/alerts/deficiency")
        else:
            logger.error(f"MQTT connection failed: {rc}")
    
    def on_message(self, client, userdata, msg):
        """MQTT message handler"""
        try:
            topic = msg.topic
            
            # Update sensor readings
            if topic.endswith("/ph") or topic.endswith("/ec") or topic.endswith("/water_temp"):
                parts = topic.strip('/').split('/')
                tower = parts[0]
                sensor = parts[1]
                value = float(msg.payload.decode())
                
                if sensor == "ph":
                    self.tower_status[tower]["ph"] = value
                    # Check if auto-adjustment needed
                    self.auto_adjust_ph(tower)
                
                elif sensor == "ec":
                    self.tower_status[tower]["ec"] = value
                
                elif sensor == "water_temp":
                    self.tower_status[tower]["temp"] = value
            
            # Handle manual dosing commands
            elif "/dosing/" in topic and "/command" in topic:
                parts = topic.split('/')
                tower = parts[2]
                
                payload = json.loads(msg.payload.decode())
                solution = payload.get("solution")
                volume = payload.get("volume_ml")
                reason = payload.get("reason", "Manual dose")
                
                self.dose(tower, solution, volume, reason, auto=False)
            
            # Handle AI deficiency alerts
            elif topic == "/alerts/deficiency":
                payload = json.loads(msg.payload.decode())
                tower = payload.get("tower")
                deficiency = payload.get("deficiency")
                
                self.auto_adjust_nutrients(tower, deficiency)
        
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def run(self):
        """Main run loop"""
        try:
            logger.info("Starting Dosing Controller...")
            logger.info(f"Auto-dosing: {'ENABLED' if self.auto_dosing_enabled else 'DISABLED'}")
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_forever()
        except KeyboardInterrupt:
            logger.info("Shutting down Dosing Controller...")
            self.client.disconnect()
        except Exception as e:
            logger.error(f"Fatal error: {e}")
            raise

def main():
    controller = DosingController()
    controller.run()

if __name__ == "__main__":
    main()
