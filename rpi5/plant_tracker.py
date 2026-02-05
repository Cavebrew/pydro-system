#!/usr/bin/env python3
"""
Plant Tracker - Individual Plant Lifecycle Management
Tracks each plant from seed to harvest with AI-powered identification

Plant ID Format: C01A (Cool tower, section 1, plant A)
Max capacity: 30 plants per tower

Features:
- Seed-to-harvest tracking
- AI visual plant identification
- Growth stage monitoring
- Harvest predictions
- Plant passport (digital record)
"""

import json
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

class PlantTracker:
    def __init__(self, db_path="/home/pi/hydro_data/plants.db"):
        self.db_path = db_path
        self.max_plants_per_tower = int(os.getenv("MAX_PLANTS_PER_TOWER", 30))
        
        # MQTT Configuration
        self.broker = os.getenv("MQTT_BROKER", "10.0.0.62")
        self.port = int(os.getenv("MQTT_PORT", 1883))
        self.username = os.getenv("MQTT_USERNAME", "hydro_user")
        self.password = os.getenv("MQTT_PASSWORD", "")
        
        # Growth stage duration estimates (days)
        self.growth_stages = {
            "lettuce": {
                "germination": 3,
                "seedling": 7,
                "vegetative": 14,
                "mature": 7,
                "harvest": 31  # Total days
            },
            "dill": {
                "germination": 7,
                "seedling": 14,
                "vegetative": 21,
                "mature": 14,
                "harvest": 56
            },
            "basil": {
                "germination": 5,
                "seedling": 10,
                "vegetative": 20,
                "mature": 14,
                "harvest": 49
            },
            "oregano": {
                "germination": 7,
                "seedling": 14,
                "vegetative": 28,
                "mature": 21,
                "harvest": 70
            }
        }
        
        # Initialize database
        self._init_database()
        
        # MQTT client
        self.client = mqtt.Client()
        self.client.username_pw_set(self.username, self.password)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        
        logger.info("Plant Tracker initialized")
    
    def _init_database(self):
        """Initialize SQLite database for plant tracking"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Plants table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS plants (
                plant_id TEXT PRIMARY KEY,
                tower TEXT NOT NULL,
                section INTEGER NOT NULL,
                position TEXT NOT NULL,
                variety TEXT NOT NULL,
                planted_date TEXT NOT NULL,
                germination_date TEXT,
                harvest_date TEXT,
                current_stage TEXT DEFAULT 'germination',
                health_status TEXT DEFAULT 'healthy',
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Growth observations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plant_id TEXT NOT NULL,
                observation_date TEXT NOT NULL,
                stage TEXT NOT NULL,
                height_cm REAL,
                leaf_count INTEGER,
                health_score INTEGER,
                deficiencies TEXT,
                image_path TEXT,
                notes TEXT,
                ai_confidence REAL,
                FOREIGN KEY (plant_id) REFERENCES plants(plant_id)
            )
        ''')
        
        # Harvest records
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS harvests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plant_id TEXT NOT NULL,
                harvest_date TEXT NOT NULL,
                weight_grams REAL,
                quality_score INTEGER,
                days_to_harvest INTEGER,
                image_path TEXT,
                notes TEXT,
                FOREIGN KEY (plant_id) REFERENCES plants(plant_id)
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info(f"Database initialized at {self.db_path}")
    
    def generate_plant_id(self, tower: str, section: int, position: str) -> str:
        """
        Generate plant ID in format C01A
        
        Args:
            tower: "cool" or "warm" -> "C" or "W"
            section: 1-15 (section number)
            position: "A", "B", etc.
        """
        tower_prefix = tower[0].upper()
        return f"{tower_prefix}{section:02d}{position.upper()}"
    
    def plant_seed(self, tower: str, section: int, position: str, variety: str, notes: str = "") -> Dict:
        """Register a new plant"""
        plant_id = self.generate_plant_id(tower, section, position)
        
        # Check tower capacity
        current_count = self.get_active_plant_count(tower)
        if current_count >= self.max_plants_per_tower:
            raise ValueError(f"{tower.upper()} tower at capacity ({self.max_plants_per_tower} plants)")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO plants (plant_id, tower, section, position, variety, planted_date, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (plant_id, tower, section, position, variety, datetime.now().isoformat(), notes))
            
            conn.commit()
            
            # Publish to MQTT
            self.publish_plant_status(plant_id)
            
            logger.info(f"New plant registered: {plant_id} ({variety})")
            
            return {
                "plant_id": plant_id,
                "variety": variety,
                "planted_date": datetime.now().isoformat(),
                "estimated_harvest": self.estimate_harvest_date(variety, datetime.now())
            }
        
        except sqlite3.IntegrityError:
            logger.error(f"Plant ID {plant_id} already exists")
            raise ValueError(f"Plant ID {plant_id} already exists")
        finally:
            conn.close()
    
    def get_active_plant_count(self, tower: str) -> int:
        """Get count of active (not harvested) plants in tower"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*) FROM plants 
            WHERE tower = ? AND harvest_date IS NULL
        ''', (tower,))
        
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    def estimate_harvest_date(self, variety: str, planted_date: datetime) -> str:
        """Estimate harvest date based on variety"""
        if variety.lower() not in self.growth_stages:
            return "Unknown"
        
        days_to_harvest = self.growth_stages[variety.lower()]["harvest"]
        harvest_date = planted_date + timedelta(days=days_to_harvest)
        return harvest_date.isoformat()
    
    def update_stage(self, plant_id: str, new_stage: str, notes: str = ""):
        """Update plant growth stage"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if new_stage == "germinated":
            cursor.execute('''
                UPDATE plants 
                SET current_stage = 'seedling', germination_date = ?, notes = ?, updated_at = ?
                WHERE plant_id = ?
            ''', (datetime.now().isoformat(), notes, datetime.now().isoformat(), plant_id))
        else:
            cursor.execute('''
                UPDATE plants 
                SET current_stage = ?, notes = ?, updated_at = ?
                WHERE plant_id = ?
            ''', (new_stage, notes, datetime.now().isoformat(), plant_id))
        
        conn.commit()
        conn.close()
        
        self.publish_plant_status(plant_id)
        logger.info(f"{plant_id} stage updated to {new_stage}")
    
    def add_observation(self, plant_id: str, height_cm: Optional[float] = None,
                       leaf_count: Optional[int] = None, health_score: Optional[int] = None,
                       deficiencies: str = "", image_path: str = "", notes: str = "",
                       ai_confidence: float = 0.0):
        """Add growth observation"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get current stage
        cursor.execute('SELECT current_stage FROM plants WHERE plant_id = ?', (plant_id,))
        result = cursor.fetchone()
        if not result:
            logger.error(f"Plant {plant_id} not found")
            return
        
        stage = result[0]
        
        cursor.execute('''
            INSERT INTO observations 
            (plant_id, observation_date, stage, height_cm, leaf_count, health_score, 
             deficiencies, image_path, notes, ai_confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (plant_id, datetime.now().isoformat(), stage, height_cm, leaf_count,
              health_score, deficiencies, image_path, notes, ai_confidence))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Observation added for {plant_id}")
    
    def record_harvest(self, plant_id: str, weight_grams: float, quality_score: int,
                      image_path: str = "", notes: str = ""):
        """Record plant harvest"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get planted date
        cursor.execute('SELECT planted_date FROM plants WHERE plant_id = ?', (plant_id,))
        result = cursor.fetchone()
        if not result:
            logger.error(f"Plant {plant_id} not found")
            return
        
        planted_date = datetime.fromisoformat(result[0])
        harvest_date = datetime.now()
        days_to_harvest = (harvest_date - planted_date).days
        
        # Update plant record
        cursor.execute('''
            UPDATE plants 
            SET harvest_date = ?, current_stage = 'harvested', updated_at = ?
            WHERE plant_id = ?
        ''', (harvest_date.isoformat(), harvest_date.isoformat(), plant_id))
        
        # Insert harvest record
        cursor.execute('''
            INSERT INTO harvests 
            (plant_id, harvest_date, weight_grams, quality_score, days_to_harvest, image_path, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (plant_id, harvest_date.isoformat(), weight_grams, quality_score,
              days_to_harvest, image_path, notes))
        
        conn.commit()
        conn.close()
        
        # Publish harvest event
        harvest_data = {
            "plant_id": plant_id,
            "harvest_date": harvest_date.isoformat(),
            "weight_grams": weight_grams,
            "quality_score": quality_score,
            "days_to_harvest": days_to_harvest
        }
        
        self.client.publish("/events/harvest", json.dumps(harvest_data))
        
        logger.info(f"Harvest recorded for {plant_id}: {weight_grams}g in {days_to_harvest} days")
    
    def publish_plant_status(self, plant_id: str):
        """Publish plant status to MQTT"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM plants WHERE plant_id = ?', (plant_id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return
        
        status = {
            "plant_id": result[0],
            "tower": result[1],
            "variety": result[4],
            "planted_date": result[5],
            "current_stage": result[8],
            "health_status": result[9],
            "days_since_planting": (datetime.now() - datetime.fromisoformat(result[5])).days
        }
        
        self.client.publish(f"/plants/{plant_id}", json.dumps(status), retain=True)
    
    def get_harvest_calendar(self, days_ahead: int = 14) -> List[Dict]:
        """Get upcoming harvests"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT plant_id, variety, planted_date, current_stage
            FROM plants
            WHERE harvest_date IS NULL
        ''')
        
        upcoming = []
        now = datetime.now()
        
        for row in cursor.fetchall():
            plant_id, variety, planted_date, stage = row
            planted = datetime.fromisoformat(planted_date)
            
            if variety.lower() in self.growth_stages:
                est_harvest = planted + timedelta(days=self.growth_stages[variety.lower()]["harvest"])
                days_until = (est_harvest - now).days
                
                if 0 <= days_until <= days_ahead:
                    upcoming.append({
                        "plant_id": plant_id,
                        "variety": variety,
                        "estimated_harvest": est_harvest.isoformat(),
                        "days_until": days_until,
                        "current_stage": stage
                    })
        
        conn.close()
        return sorted(upcoming, key=lambda x: x["days_until"])
    
    def on_connect(self, client, userdata, flags, rc):
        """MQTT connection handler"""
        if rc == 0:
            logger.info(f"Connected to MQTT broker")
            client.subscribe("/plants/+/command")
            client.subscribe("/ai/plant_identified")
        else:
            logger.error(f"MQTT connection failed: {rc}")
    
    def on_message(self, client, userdata, msg):
        """MQTT message handler"""
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())
            
            if "/command" in topic:
                plant_id = topic.split('/')[2]
                command = payload.get("command")
                
                if command == "update_stage":
                    self.update_stage(plant_id, payload.get("stage"), payload.get("notes", ""))
                elif command == "add_observation":
                    self.add_observation(plant_id, **payload.get("data", {}))
                elif command == "harvest":
                    self.record_harvest(plant_id, **payload.get("data", {}))
            
            elif topic == "/ai/plant_identified":
                # AI has identified a plant from image
                plant_id = payload.get("plant_id")
                confidence = payload.get("confidence", 0.0)
                deficiencies = payload.get("deficiencies", "")
                
                self.add_observation(
                    plant_id,
                    deficiencies=deficiencies,
                    image_path=payload.get("image_path", ""),
                    ai_confidence=confidence
                )
        
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def run(self):
        """Main run loop"""
        try:
            logger.info("Starting Plant Tracker...")
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_forever()
        except KeyboardInterrupt:
            logger.info("Shutting down Plant Tracker...")
            self.client.disconnect()
        except Exception as e:
            logger.error(f"Fatal error: {e}")
            raise

def main():
    tracker = PlantTracker()
    tracker.run()

if __name__ == "__main__":
    main()
