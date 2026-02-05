#!/usr/bin/env python3
"""
Planting Scheduler
AI-powered staggered planting scheduler for continuous harvests

Features:
- Suggests optimal planting dates for continuous harvests
- Tracks available sections in each tower
- Considers growth cycles and harvest windows
- AI recommendations for variety selection
- Maintains target plant population
"""

import os
import json
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

class PlantingScheduler:
    def __init__(self, db_path="/home/pi/hydro_data/plants.db"):
        self.db_path = db_path
        self.max_plants = int(os.getenv("MAX_PLANTS_PER_TOWER", 30))
        
        # Growth cycle data (days to harvest)
        self.growth_cycles = {
            "lettuce": 31,
            "dill": 56,
            "basil": 49,
            "oregano": 70
        }
        
        # Optimal harvest windows (days)
        self.harvest_windows = {
            "lettuce": 7,   # Can harvest within 7-day window
            "dill": 14,
            "basil": 10,
            "oregano": 14
        }
        
        # MQTT Configuration
        self.broker = os.getenv("MQTT_BROKER", "10.0.0.62")
        self.port = int(os.getenv("MQTT_PORT", 1883))
        self.username = os.getenv("MQTT_USERNAME", "hydro_user")
        self.password = os.getenv("MQTT_PASSWORD", "")
        
        # MQTT client
        self.client = mqtt.Client()
        self.client.username_pw_set(self.username, self.password)
        
        logger.info("Planting Scheduler initialized")
    
    def get_available_sections(self, tower: str) -> List[int]:
        """Get available planting sections"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get occupied sections
        cursor.execute('''
            SELECT DISTINCT section FROM plants
            WHERE tower = ? AND harvest_date IS NULL
        ''', (tower,))
        
        occupied = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        # Return unoccupied sections (1-15 available per tower)
        all_sections = list(range(1, 16))
        available = [s for s in all_sections if s not in occupied]
        
        return available
    
    def get_current_plant_count(self, tower: str) -> int:
        """Get current active plant count"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*) FROM plants
            WHERE tower = ? AND harvest_date IS NULL
        ''', (tower,))
        
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    def get_upcoming_harvests(self, tower: str, days_ahead: int = 30) -> List[Dict]:
        """Get upcoming harvest dates"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT plant_id, variety, planted_date
            FROM plants
            WHERE tower = ? AND harvest_date IS NULL
        ''', (tower,))
        
        harvests = []
        now = datetime.now()
        
        for row in cursor.fetchall():
            plant_id, variety, planted_date = row
            planted = datetime.fromisoformat(planted_date)
            
            if variety.lower() in self.growth_cycles:
                harvest_days = self.growth_cycles[variety.lower()]
                est_harvest = planted + timedelta(days=harvest_days)
                days_until = (est_harvest - now).days
                
                if 0 <= days_until <= days_ahead:
                    harvests.append({
                        "plant_id": plant_id,
                        "variety": variety,
                        "harvest_date": est_harvest.isoformat(),
                        "days_until": days_until
                    })
        
        conn.close()
        return sorted(harvests, key=lambda x: x["days_until"])
    
    def calculate_planting_schedule(self, tower: str, target_plants: int = 25) -> List[Dict]:
        """
        Calculate optimal planting schedule for continuous harvests
        
        Args:
            tower: "cool" or "warm"
            target_plants: Target number of active plants (default 25, max 30)
        
        Returns:
            List of recommended planting dates and varieties
        """
        current_count = self.get_current_plant_count(tower)
        upcoming_harvests = self.get_upcoming_harvests(tower, 60)
        
        # Determine varieties for tower
        if tower == "cool":
            varieties = ["lettuce", "dill"]
        else:
            varieties = ["basil", "oregano"]
        
        schedule = []
        
        # Calculate planting needs based on harvest schedule
        for i in range(60):  # Look 60 days ahead
            check_date = datetime.now() + timedelta(days=i)
            
            # Count plants that will still be growing on this date
            active_on_date = current_count
            for harvest in upcoming_harvests:
                harvest_date = datetime.fromisoformat(harvest["harvest_date"])
                if check_date >= harvest_date:
                    active_on_date -= 1
            
            # If below target, schedule a planting
            if active_on_date < target_plants:
                # Choose variety to plant
                # Alternate between varieties for diversity
                variety_idx = len(schedule) % len(varieties)
                variety = varieties[variety_idx]
                
                schedule.append({
                    "date": check_date.isoformat(),
                    "variety": variety,
                    "reason": f"Maintain target population ({active_on_date}/{target_plants})",
                    "growth_days": self.growth_cycles[variety],
                    "estimated_harvest": (check_date + timedelta(days=self.growth_cycles[variety])).isoformat()
                })
                
                # Only schedule one planting per week
                i += 7
        
        return schedule[:10]  # Return next 10 planting suggestions
    
    def get_ai_variety_recommendation(self, tower: str) -> str:
        """Get AI recommendation for which variety to plant next"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get variety distribution in tower
        cursor.execute('''
            SELECT variety, COUNT(*) as count
            FROM plants
            WHERE tower = ? AND harvest_date IS NULL
            GROUP BY variety
        ''', (tower,))
        
        variety_counts = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()
        
        # Recommend variety with lowest count
        if tower == "cool":
            varieties = ["lettuce", "dill"]
        else:
            varieties = ["basil", "oregano"]
        
        # Find variety with lowest count
        min_count = float('inf')
        recommended = varieties[0]
        
        for variety in varieties:
            count = variety_counts.get(variety, 0)
            if count < min_count:
                min_count = count
                recommended = variety
        
        return recommended
    
    def publish_schedule(self, tower: str):
        """Publish planting schedule to MQTT"""
        schedule = self.calculate_planting_schedule(tower)
        recommendation = self.get_ai_variety_recommendation(tower)
        
        data = {
            "tower": tower,
            "recommended_variety": recommendation,
            "schedule": schedule,
            "current_count": self.get_current_plant_count(tower),
            "available_sections": len(self.get_available_sections(tower)),
            "upcoming_harvests": len(self.get_upcoming_harvests(tower)),
            "generated_at": datetime.now().isoformat()
        }
        
        self.client.publish(f"/{tower}/planting_schedule", json.dumps(data), retain=True)
        logger.info(f"Published planting schedule for {tower} tower")
        
        return data
    
    def run(self):
        """Generate and publish schedules"""
        try:
            logger.info("Generating planting schedules...")
            self.client.connect(self.broker, self.port, 60)
            
            # Publish schedules for both towers
            cool_schedule = self.publish_schedule("cool")
            warm_schedule = self.publish_schedule("warm")
            
            logger.info(f"Cool tower: {len(cool_schedule['schedule'])} plantings recommended")
            logger.info(f"Warm tower: {len(warm_schedule['schedule'])} plantings recommended")
            
            self.client.disconnect()
        
        except Exception as e:
            logger.error(f"Error generating schedules: {e}")

def main():
    scheduler = PlantingScheduler()
    scheduler.run()

if __name__ == "__main__":
    main()
