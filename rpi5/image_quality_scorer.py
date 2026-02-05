#!/usr/bin/env python3
"""
Image Quality Scorer
AI-powered image quality assessment for plant photos

Features:
- Auto-tags images with quality scores (1-10)
- Preserves all 10/10 rated images permanently
- Keeps all harvest photos for 5 years
- Compresses and archives lower-quality images
- ML-based blur detection, lighting analysis, plant coverage
"""

import os
import json
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional
from pathlib import Path
import paho.mqtt.client as mqtt
from dotenv import load_dotenv
import cv2
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

class ImageQualityScorer:
    def __init__(self, db_path="/home/pi/hydro_data/images.db"):
        self.db_path = db_path
        self.image_storage = os.getenv("IMAGE_STORAGE_PATH", "/home/pi/hydro_images")
        self.quality_threshold = int(os.getenv("IMAGE_QUALITY_THRESHOLD", 10))
        self.harvest_retention_years = int(os.getenv("HARVEST_PHOTO_RETENTION_YEARS", 5))
        
        # Storage structure
        self.archive_path = f"{self.image_storage}/archive"
        self.perfect_path = f"{self.image_storage}/perfect"
        self.harvest_path = f"{self.image_storage}/harvests"
        
        # Create directories
        for path in [self.archive_path, self.perfect_path, self.harvest_path]:
            os.makedirs(path, exist_ok=True)
        
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
        
        logger.info("Image Quality Scorer initialized")
    
    def _init_database(self):
        """Initialize image metadata database"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT UNIQUE NOT NULL,
                filepath TEXT NOT NULL,
                tower TEXT NOT NULL,
                camera_type TEXT NOT NULL,
                capture_date TEXT NOT NULL,
                quality_score INTEGER,
                blur_score REAL,
                brightness_score REAL,
                contrast_score REAL,
                plant_coverage REAL,
                is_harvest_photo BOOLEAN DEFAULT 0,
                is_perfect BOOLEAN DEFAULT 0,
                archived BOOLEAN DEFAULT 0,
                deleted BOOLEAN DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info(f"Image database initialized at {self.db_path}")
    
    def calculate_blur_score(self, image_path: str) -> float:
        """
        Calculate blur score using Laplacian variance
        Higher score = sharper image
        """
        try:
            img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
            if img is None:
                return 0.0
            
            # Calculate Laplacian variance
            laplacian_var = cv2.Laplacian(img, cv2.CV_64F).var()
            
            # Normalize to 0-100 scale (typical sharp images: 100-500+)
            normalized = min(100, (laplacian_var / 5.0))
            return round(normalized, 2)
        
        except Exception as e:
            logger.error(f"Error calculating blur: {e}")
            return 0.0
    
    def calculate_brightness_score(self, image_path: str) -> float:
        """
        Calculate brightness score
        Optimal range: 40-60% (returns score 80-100)
        """
        try:
            img = cv2.imread(image_path)
            if img is None:
                return 0.0
            
            # Convert to HSV and get V channel
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            v_channel = hsv[:, :, 2]
            mean_brightness = np.mean(v_channel) / 255.0 * 100  # 0-100
            
            # Score based on optimal range (40-60%)
            if 40 <= mean_brightness <= 60:
                score = 100
            elif 30 <= mean_brightness < 40 or 60 < mean_brightness <= 70:
                score = 80
            elif 20 <= mean_brightness < 30 or 70 < mean_brightness <= 80:
                score = 60
            else:
                score = 40
            
            return round(score, 2)
        
        except Exception as e:
            logger.error(f"Error calculating brightness: {e}")
            return 0.0
    
    def calculate_contrast_score(self, image_path: str) -> float:
        """
        Calculate contrast score using standard deviation
        Higher std dev = better contrast
        """
        try:
            img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
            if img is None:
                return 0.0
            
            std_dev = np.std(img)
            
            # Normalize (typical good contrast: 40-80 std dev)
            normalized = min(100, (std_dev / 0.8))
            return round(normalized, 2)
        
        except Exception as e:
            logger.error(f"Error calculating contrast: {e}")
            return 0.0
    
    def calculate_plant_coverage(self, image_path: str) -> float:
        """
        Estimate plant coverage using green pixel detection
        Returns percentage of image containing plant matter
        """
        try:
            img = cv2.imread(image_path)
            if img is None:
                return 0.0
            
            # Convert to HSV
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            
            # Green color range (adjust for grow lights)
            lower_green = np.array([30, 40, 40])
            upper_green = np.array([90, 255, 255])
            
            # Create mask
            mask = cv2.inRange(hsv, lower_green, upper_green)
            
            # Calculate coverage
            green_pixels = np.sum(mask > 0)
            total_pixels = mask.shape[0] * mask.shape[1]
            coverage = (green_pixels / total_pixels) * 100
            
            return round(coverage, 2)
        
        except Exception as e:
            logger.error(f"Error calculating plant coverage: {e}")
            return 0.0
    
    def calculate_overall_score(self, blur: float, brightness: float, 
                               contrast: float, coverage: float) -> int:
        """
        Calculate overall quality score (1-10)
        
        Weights:
        - Blur: 40% (most important)
        - Coverage: 30% (shows plant well)
        - Brightness: 20%
        - Contrast: 10%
        """
        # Normalize all to 0-100 range first
        weighted_score = (
            (blur * 0.40) +
            (coverage * 0.30) +
            (brightness * 0.20) +
            (contrast * 0.10)
        )
        
        # Convert to 1-10 scale
        final_score = max(1, min(10, round(weighted_score / 10)))
        return final_score
    
    def score_image(self, image_path: str, tower: str, camera_type: str, 
                   is_harvest: bool = False) -> Dict:
        """
        Score an image and store metadata
        
        Returns:
            Dict with all scores and final rating
        """
        filename = os.path.basename(image_path)
        
        # Calculate individual scores
        blur_score = self.calculate_blur_score(image_path)
        brightness_score = self.calculate_brightness_score(image_path)
        contrast_score = self.calculate_contrast_score(image_path)
        plant_coverage = self.calculate_plant_coverage(image_path)
        
        # Overall score
        quality_score = self.calculate_overall_score(
            blur_score, brightness_score, contrast_score, plant_coverage
        )
        
        # Perfect image (10/10)
        is_perfect = quality_score >= self.quality_threshold
        
        # Store in database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO images 
                (filename, filepath, tower, camera_type, capture_date, quality_score,
                 blur_score, brightness_score, contrast_score, plant_coverage,
                 is_harvest_photo, is_perfect)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (filename, image_path, tower, camera_type, datetime.now().isoformat(),
                  quality_score, blur_score, brightness_score, contrast_score,
                  plant_coverage, is_harvest, is_perfect))
            
            conn.commit()
        except sqlite3.IntegrityError:
            logger.warning(f"Image {filename} already scored")
        finally:
            conn.close()
        
        # Move perfect images to special directory
        if is_perfect and not is_harvest:
            new_path = os.path.join(self.perfect_path, filename)
            if image_path != new_path:
                os.rename(image_path, new_path)
                logger.info(f"Moved perfect image to {new_path}")
        
        # Move harvest photos to harvest directory
        if is_harvest:
            new_path = os.path.join(self.harvest_path, filename)
            if image_path != new_path:
                os.rename(image_path, new_path)
                logger.info(f"Moved harvest photo to {new_path}")
        
        result = {
            "filename": filename,
            "quality_score": quality_score,
            "blur_score": blur_score,
            "brightness_score": brightness_score,
            "contrast_score": contrast_score,
            "plant_coverage": plant_coverage,
            "is_perfect": is_perfect,
            "is_harvest": is_harvest,
            "rating": self.get_rating_description(quality_score)
        }
        
        # Publish to MQTT
        self.client.publish(
            f"/{tower}/image_quality",
            json.dumps(result)
        )
        
        logger.info(
            f"Image scored: {filename} = {quality_score}/10 "
            f"(blur:{blur_score:.1f}, brightness:{brightness_score:.1f}, "
            f"contrast:{contrast_score:.1f}, coverage:{plant_coverage:.1f}%)"
        )
        
        return result
    
    def get_rating_description(self, score: int) -> str:
        """Get text description of quality score"""
        ratings = {
            10: "Perfect",
            9: "Excellent",
            8: "Very Good",
            7: "Good",
            6: "Above Average",
            5: "Average",
            4: "Below Average",
            3: "Poor",
            2: "Very Poor",
            1: "Unusable"
        }
        return ratings.get(score, "Unknown")
    
    def cleanup_old_images(self):
        """
        Archive or delete old images based on retention policy
        - Keep all 10/10 images forever
        - Keep harvest photos for 5 years
        - Compress and archive other images after 30 days
        - Delete archived images after 1 year
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get images older than 30 days that aren't perfect or harvest
        cutoff_date = (datetime.now() - timedelta(days=30)).isoformat()
        
        cursor.execute('''
            SELECT id, filename, filepath, quality_score, is_harvest_photo, is_perfect
            FROM images
            WHERE capture_date < ? 
            AND is_perfect = 0 
            AND is_harvest_photo = 0
            AND archived = 0
            AND deleted = 0
        ''', (cutoff_date,))
        
        for row in cursor.fetchall():
            img_id, filename, filepath, score, is_harvest, is_perfect = row
            
            if os.path.exists(filepath):
                # Compress and move to archive
                archive_path = os.path.join(self.archive_path, filename)
                
                # Simple compression using JPEG quality
                img = cv2.imread(filepath)
                if img is not None:
                    cv2.imwrite(archive_path, img, [cv2.IMWRITE_JPEG_QUALITY, 75])
                    os.remove(filepath)
                    
                    # Update database
                    cursor.execute('''
                        UPDATE images 
                        SET archived = 1, filepath = ?
                        WHERE id = ?
                    ''', (archive_path, img_id))
                    
                    logger.info(f"Archived image: {filename}")
        
        # Delete old harvest photos (after 5 years)
        harvest_cutoff = (datetime.now() - timedelta(days=365 * self.harvest_retention_years)).isoformat()
        
        cursor.execute('''
            SELECT id, filepath
            FROM images
            WHERE is_harvest_photo = 1
            AND capture_date < ?
            AND deleted = 0
        ''', (harvest_cutoff,))
        
        for row in cursor.fetchall():
            img_id, filepath = row
            if os.path.exists(filepath):
                os.remove(filepath)
                cursor.execute('UPDATE images SET deleted = 1 WHERE id = ?', (img_id,))
                logger.info(f"Deleted old harvest photo: {filepath}")
        
        conn.commit()
        conn.close()
    
    def on_connect(self, client, userdata, flags, rc):
        """MQTT connection handler"""
        if rc == 0:
            logger.info("Connected to MQTT broker")
            client.subscribe("/images/new")
        else:
            logger.error(f"MQTT connection failed: {rc}")
    
    def on_message(self, client, userdata, msg):
        """MQTT message handler"""
        try:
            payload = json.loads(msg.payload.decode())
            
            image_path = payload.get("path")
            tower = payload.get("tower")
            camera_type = payload.get("camera_type")
            is_harvest = payload.get("is_harvest", False)
            
            if image_path and os.path.exists(image_path):
                self.score_image(image_path, tower, camera_type, is_harvest)
        
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def run(self):
        """Main run loop"""
        try:
            logger.info("Starting Image Quality Scorer...")
            self.client.connect(self.broker, self.port, 60)
            
            # Run cleanup on startup
            self.cleanup_old_images()
            
            self.client.loop_forever()
        except KeyboardInterrupt:
            logger.info("Shutting down Image Quality Scorer...")
            self.client.disconnect()
        except Exception as e:
            logger.error(f"Fatal error: {e}")
            raise

def main():
    scorer = ImageQualityScorer()
    scorer.run()

if __name__ == "__main__":
    main()
