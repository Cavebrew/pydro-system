#!/usr/bin/env python3
"""
Image Analyzer - Plant Health Detection using TensorFlow Lite
Analyzes visible and NOIR camera images for deficiency detection
Fuses visible and IR images for comprehensive analysis

Part of the Dual Tower Hydroponic AI System
"""

import os
import cv2
import numpy as np
from pathlib import Path
from datetime import datetime
import logging
from typing import Dict, List, Tuple, Optional

# TensorFlow Lite
try:
    import tflite_runtime.interpreter as tflite
except ImportError:
    try:
        import tensorflow.lite as tflite
    except ImportError:
        tflite = None
        logging.warning("TensorFlow Lite not available - running in mock mode")

logger = logging.getLogger('image_analyzer')

# Model path
MODEL_DIR = Path(__file__).parent.parent / 'models'
MODEL_PATH = MODEL_DIR / 'plant_deficiency_model.tflite'

# Deficiency detection classes (example - customize based on your model)
DEFICIENCY_CLASSES = {
    0: 'healthy',
    1: 'nitrogen_deficiency',  # Yellowing
    2: 'calcium_deficiency',   # Tip burn
    3: 'phosphorus_deficiency',  # Purple veins
    4: 'magnesium_deficiency',  # Interveinal chlorosis
    5: 'potassium_deficiency',  # Brown edges
    6: 'ready_for_harvest',
    7: 'bolting_flowering'  # Overripe
}

# Deficiency to nutrient mapping
DEFICIENCY_SOLUTIONS = {
    'nitrogen_deficiency': {
        'cool': 'Add 5g Lettuce Fertilizer 8-15-36',
        'warm': 'Add small scoop MaxiGrow (~5g)'
    },
    'calcium_deficiency': {
        'cool': 'Apply foliar Ca spray (CalMagic diluted). Check air flow and humidity (target 50-70%)',
        'warm': 'Apply foliar Ca spray. Ensure good air circulation'
    },
    'phosphorus_deficiency': {
        'cool': 'Increase Lettuce Fertilizer to 12g (high P content)',
        'warm': 'Boost MaxiGrow dosage'
    },
    'magnesium_deficiency': {
        'cool': 'Add 2-3g Epsom Salt',
        'warm': 'Add 2g Epsom Salt'
    },
    'potassium_deficiency': {
        'cool': 'Check EC - may need fresh reservoir',
        'warm': 'Increase MaxiGrow slightly'
    },
    'ready_for_harvest': {
        'cool': 'Lettuce/dill ready - harvest soon for best quality',
        'warm': 'Basil/oregano ready - harvest before flowering'
    },
    'bolting_flowering': {
        'cool': 'URGENT: About to bolt/flower - harvest immediately',
        'warm': 'URGENT: Flowering detected - harvest now to prevent bitter taste'
    }
}


class ImageAnalyzer:
    def __init__(self):
        self.model = None
        self.input_details = None
        self.output_details = None
        self.model_loaded = False
        
        # Load model if available
        if tflite and MODEL_PATH.exists():
            self._load_model()
        else:
            logger.warning(f"Model not found at {MODEL_PATH}. Using rule-based analysis only.")
    
    def _load_model(self):
        """Load TensorFlow Lite model"""
        try:
            self.model = tflite.Interpreter(model_path=str(MODEL_PATH))
            self.model.allocate_tensors()
            
            self.input_details = self.model.get_input_details()
            self.output_details = self.model.get_output_details()
            
            self.model_loaded = True
            logger.info(f"Loaded TFLite model from {MODEL_PATH}")
            
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            self.model_loaded = False
    
    def analyze_images(self, visible_path: Path, noir_path: Optional[Path], tower: str) -> Dict:
        """
        Analyze visible and NOIR images for plant health
        
        Args:
            visible_path: Path to visible spectrum image
            noir_path: Path to NOIR (IR) image (optional)
            tower: Tower name ('cool' or 'warm')
        
        Returns:
            Dictionary with analysis results
        """
        results = {
            'timestamp': datetime.now().isoformat(),
            'tower': tower,
            'deficiencies': [],
            'health_score': 100,
            'issues': [],
            'suggestions': []
        }
        
        # Load visible image
        visible_img = self._load_image(visible_path)
        if visible_img is None:
            logger.error(f"Failed to load visible image: {visible_path}")
            return results
        
        # Load NOIR image if provided
        noir_img = None
        if noir_path and noir_path.exists():
            noir_img = self._load_image(noir_path)
        
        # ML-based detection (if model available)
        if self.model_loaded:
            ml_results = self._ml_detect_deficiency(visible_img)
            results['deficiencies'].extend(ml_results)
        
        # Rule-based color analysis
        color_results = self._color_analysis(visible_img, tower)
        results['deficiencies'].extend(color_results)
        
        # IR analysis for heat stress (if NOIR image available)
        if noir_img is not None:
            ir_results = self._ir_analysis(noir_img, visible_img)
            results['deficiencies'].extend(ir_results)
        
        # Calculate health score
        results['health_score'] = self._calculate_health_score(results['deficiencies'])
        
        # Generate issues and suggestions
        results['issues'], results['suggestions'] = self._generate_recommendations(
            results['deficiencies'], tower
        )
        
        return results
    
    def _load_image(self, image_path: Path) -> Optional[np.ndarray]:
        """Load and preprocess image"""
        try:
            img = cv2.imread(str(image_path))
            if img is None:
                return None
            return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        except Exception as e:
            logger.error(f"Error loading image {image_path}: {e}")
            return None
    
    def _ml_detect_deficiency(self, image: np.ndarray) -> List[Dict]:
        """Use TFLite model to detect deficiencies"""
        try:
            # Get input shape from model
            input_shape = self.input_details[0]['shape']
            input_height, input_width = input_shape[1], input_shape[2]
            
            # Resize and preprocess
            img_resized = cv2.resize(image, (input_width, input_height))
            img_normalized = img_resized.astype(np.float32) / 255.0
            img_batch = np.expand_dims(img_normalized, axis=0)
            
            # Run inference
            self.model.set_tensor(self.input_details[0]['index'], img_batch)
            self.model.invoke()
            
            # Get predictions
            output_data = self.model.get_tensor(self.output_details[0]['index'])
            predictions = output_data[0]
            
            # Get top predictions (confidence > 0.5)
            deficiencies = []
            for idx, confidence in enumerate(predictions):
                if confidence > 0.5 and idx in DEFICIENCY_CLASSES:
                    class_name = DEFICIENCY_CLASSES[idx]
                    if class_name != 'healthy':
                        deficiencies.append({
                            'type': class_name,
                            'confidence': float(confidence),
                            'method': 'ml_detection'
                        })
            
            return deficiencies
            
        except Exception as e:
            logger.error(f"ML detection error: {e}")
            return []
    
    def _color_analysis(self, image: np.ndarray, tower: str) -> List[Dict]:
        """Rule-based color analysis for deficiencies"""
        deficiencies = []
        
        # Convert to HSV for better color detection
        hsv = cv2.cvtColor(cv2.cvtColor(image, cv2.COLOR_RGB2BGR), cv2.COLOR_BGR2HSV)
        
        # Define color ranges (HSV)
        # Yellow (nitrogen deficiency)
        yellow_lower = np.array([20, 100, 100])
        yellow_upper = np.array([30, 255, 255])
        yellow_mask = cv2.inRange(hsv, yellow_lower, yellow_upper)
        yellow_ratio = np.sum(yellow_mask > 0) / yellow_mask.size
        
        if yellow_ratio > 0.15:  # >15% yellowing
            deficiencies.append({
                'type': 'nitrogen_deficiency',
                'confidence': min(yellow_ratio * 3, 1.0),
                'method': 'color_analysis',
                'detail': f'Yellowing detected: {yellow_ratio*100:.1f}% of leaf area'
            })
        
        # Brown (tip burn - calcium deficiency)
        brown_lower = np.array([10, 50, 50])
        brown_upper = np.array([20, 200, 200])
        brown_mask = cv2.inRange(hsv, brown_lower, brown_upper)
        brown_ratio = np.sum(brown_mask > 0) / brown_mask.size
        
        if brown_ratio > 0.05 and tower == 'cool':  # Tip burn common in lettuce
            deficiencies.append({
                'type': 'calcium_deficiency',
                'confidence': min(brown_ratio * 5, 1.0),
                'method': 'color_analysis',
                'detail': f'Tip burn detected: {brown_ratio*100:.1f}% of leaf area'
            })
        
        # Purple (phosphorus deficiency)
        purple_lower = np.array([130, 50, 50])
        purple_upper = np.array([160, 255, 255])
        purple_mask = cv2.inRange(hsv, purple_lower, purple_upper)
        purple_ratio = np.sum(purple_mask > 0) / purple_mask.size
        
        if purple_ratio > 0.08:  # >8% purple
            deficiencies.append({
                'type': 'phosphorus_deficiency',
                'confidence': min(purple_ratio * 4, 1.0),
                'method': 'color_analysis',
                'detail': f'Purple veining: {purple_ratio*100:.1f}% of leaf area'
            })
        
        return deficiencies
    
    def _ir_analysis(self, noir_img: np.ndarray, visible_img: np.ndarray) -> List[Dict]:
        """Analyze NOIR (IR) image for heat stress"""
        issues = []
        
        try:
            # Convert to grayscale
            noir_gray = cv2.cvtColor(cv2.cvtColor(noir_img, cv2.COLOR_RGB2BGR), 
                                     cv2.COLOR_BGR2GRAY)
            
            # Analyze temperature variance (brighter = warmer in IR)
            mean_temp = np.mean(noir_gray)
            std_temp = np.std(noir_gray)
            
            # High variance suggests uneven heating (stress)
            if std_temp > 40:  # Threshold for variance
                issues.append({
                    'type': 'heat_stress',
                    'confidence': min(std_temp / 60, 1.0),
                    'method': 'ir_analysis',
                    'detail': f'Uneven heat distribution detected (IR variance: {std_temp:.1f})'
                })
            
            # Very high average brightness = overall heat stress
            if mean_temp > 180:  # High IR brightness
                issues.append({
                    'type': 'overall_heat_stress',
                    'confidence': min((mean_temp - 180) / 75, 1.0),
                    'method': 'ir_analysis',
                    'detail': f'High IR brightness: {mean_temp:.1f} - possible heat stress'
                })
        
        except Exception as e:
            logger.error(f"IR analysis error: {e}")
        
        return issues
    
    def _calculate_health_score(self, deficiencies: List[Dict]) -> int:
        """Calculate overall plant health score (0-100)"""
        if not deficiencies:
            return 100
        
        # Deduct points based on deficiency confidence
        score = 100
        for deficiency in deficiencies:
            confidence = deficiency.get('confidence', 0.5)
            
            # Critical issues (harvest, bolting)
            if deficiency['type'] in ['bolting_flowering', 'ready_for_harvest']:
                score -= int(confidence * 5)  # Minor deduction
            else:
                # Deficiencies
                score -= int(confidence * 20)  # Major deduction
        
        return max(score, 0)
    
    def _generate_recommendations(self, deficiencies: List[Dict], tower: str) -> Tuple[List[str], List[str]]:
        """Generate actionable issues and suggestions"""
        issues = []
        suggestions = []
        
        for deficiency in deficiencies:
            deficiency_type = deficiency['type']
            confidence = deficiency.get('confidence', 0.5)
            
            # Only include if confidence is high enough
            if confidence < 0.4:
                continue
            
            # Format issue
            issue_text = deficiency_type.replace('_', ' ').title()
            detail = deficiency.get('detail', '')
            if detail:
                issue_text += f" ({detail})"
            issues.append(issue_text)
            
            # Get solution
            if deficiency_type in DEFICIENCY_SOLUTIONS:
                solution = DEFICIENCY_SOLUTIONS[deficiency_type]
                if isinstance(solution, dict):
                    suggestion = solution.get(tower, solution.get('cool', 'Unknown'))
                else:
                    suggestion = solution
                suggestions.append(suggestion)
        
        return issues, suggestions


# Create placeholder model file if it doesn't exist
def create_placeholder_model():
    """Create a placeholder TFLite model file for development"""
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    readme_path = MODEL_DIR / 'README.md'
    
    if not readme_path.exists():
        with open(readme_path, 'w') as f:
            f.write("""# Plant Deficiency Detection Models

## Model Files

Place your trained TensorFlow Lite model here:
- `plant_deficiency_model.tflite`

## Training Your Own Model

1. Collect dataset of plant images labeled with deficiencies
2. Use PlantVillage dataset or similar as base
3. Fine-tune for basil, lettuce, dill, oregano specifically
4. Export to TensorFlow Lite format
5. Target >95% accuracy for production use

## Pre-trained Models

Consider using:
- PlantVillage dataset models (https://github.com/spMohanty/PlantVillage-Dataset)
- Custom models trained on hydroponic herb/lettuce data
- Transfer learning from ImageNet models

## Model Input

- Input shape: [1, 224, 224, 3] (or model-specific)
- Normalized: 0.0-1.0 (pixel values / 255)
- RGB color space

## Model Output

- Classes: See DEFICIENCY_CLASSES in image_analyzer.py
- Output: Softmax probabilities for each class
""")
        logger.info(f"Created model README at {readme_path}")


if __name__ == '__main__':
    # Test mode
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    create_placeholder_model()
    
    analyzer = ImageAnalyzer()
    print(f"Model loaded: {analyzer.model_loaded}")
    print("Image analyzer ready for testing")
