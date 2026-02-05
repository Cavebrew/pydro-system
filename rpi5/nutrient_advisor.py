#!/usr/bin/env python3
"""
Nutrient Advisor with xAI Grok API Integration
Provides advanced nutrient recommendations using AI

Part of the Dual Tower Hydroponic AI System
"""

import os
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger('nutrient_advisor')


class NutrientAdvisor:
    def __init__(self):
        self.xai_api_key = os.getenv('XAI_API_KEY')
        self.xai_api_url = os.getenv('XAI_API_URL', 'https://api.x.ai/v1/chat/completions')
        self.xai_enabled = bool(self.xai_api_key)
        
        if self.xai_enabled:
            logger.info("xAI Grok API enabled for advanced recommendations")
        else:
            logger.warning("xAI Grok API not configured - using rule-based recommendations only")
        
        # Local nutrient knowledge base
        self.nutrient_database = {
            'cool': {
                'base': 'Lettuce Fertilizer 8-15-36',
                'buffer': 'CalMagic + Calcium Nitrate',
                'supplements': ['Epsom Salt', 'Armor Si', 'Hydroguard'],
                'ec_range': (1.2, 1.8),
                'ph_range': (5.8, 6.2),
                'plant_type': 'lettuce/dill'
            },
            'warm': {
                'base': 'MaxiGrow 10-5-14',
                'buffer': 'CalMagic',
                'supplements': ['Armor Si', 'Epsom Salt', 'Hydroguard'],
                'ec_range': (1.5, 2.0),
                'ph_range': (5.8, 6.2),
                'plant_type': 'basil/oregano'
            }
        }
    
    def get_recommendation(self, tower: str, issue_type: str, 
                          sensor_data: Dict, deficiencies: List[str] = None) -> Dict:
        """
        Get nutrient recommendation for an issue
        
        Returns:
            {
                'action': str,
                'amount': str,
                'reason': str,
                'priority': str,
                'source': str  # 'local' or 'grok_ai'
            }
        """
        # Try Grok AI first for advanced analysis
        if self.xai_enabled and deficiencies:
            grok_result = self._query_grok(tower, issue_type, sensor_data, deficiencies)
            if grok_result:
                return grok_result
        
        # Fallback to local rule-based recommendations
        return self._local_recommendation(tower, issue_type, sensor_data)
    
    def _query_grok(self, tower: str, issue_type: str, 
                    sensor_data: Dict, deficiencies: List[str]) -> Optional[Dict]:
        """Query xAI Grok API for advanced recommendation"""
        try:
            # Build context
            tower_info = self.nutrient_database[tower]
            
            prompt = f"""You are an expert hydroponic nutrient advisor. Analyze this situation and provide a specific, actionable recommendation.

Tower: {tower.capitalize()} ({tower_info['plant_type']})
Issue: {issue_type}
Deficiencies detected: {', '.join(deficiencies)}

Current Sensor Data:
- EC: {sensor_data.get('ec', 'N/A')} mS/cm (target: {tower_info['ec_range'][0]}-{tower_info['ec_range'][1]})
- pH: {sensor_data.get('ph', 'N/A')} (target: {tower_info['ph_range'][0]}-{tower_info['ph_range'][1]})
- Water Temp: {sensor_data.get('water_temp', 'N/A')}°F
- Air Temp: {sensor_data.get('air_temp', 'N/A')}°F
- Humidity: {sensor_data.get('humidity', 'N/A')}%

Available Nutrients:
- Base: {tower_info['base']}
- Buffer: {tower_info['buffer']}
- Supplements: {', '.join(tower_info['supplements'])}
- pH Down, CalMagic, Epsom Salt, Calcium Nitrate

Provide recommendation in JSON format:
{{
    "action": "specific nutrient to add",
    "amount": "precise amount in grams or ml",
    "reason": "explanation based on data",
    "priority": "low/medium/high",
    "additional_notes": "any other relevant advice"
}}

Be specific with amounts. Consider nutrient interactions and lockouts."""

            headers = {
                'Authorization': f'Bearer {self.xai_api_key}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'model': 'grok-beta',
                'messages': [
                    {
                        'role': 'system',
                        'content': 'You are an expert in hydroponic nutrient management with deep knowledge of plant deficiencies and nutrient chemistry.'
                    },
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                'temperature': 0.3,  # Lower for more consistent recommendations
                'max_tokens': 500
            }
            
            response = requests.post(
                self.xai_api_url,
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                
                # Try to parse JSON from response
                try:
                    # Extract JSON from markdown code blocks if present
                    if '```json' in content:
                        content = content.split('```json')[1].split('```')[0].strip()
                    elif '```' in content:
                        content = content.split('```')[1].split('```')[0].strip()
                    
                    recommendation = json.loads(content)
                    recommendation['source'] = 'grok_ai'
                    
                    logger.info(f"Grok AI recommendation: {recommendation['action']}")
                    return recommendation
                    
                except json.JSONDecodeError:
                    # If JSON parsing fails, extract key info from text
                    logger.warning("Failed to parse Grok JSON response, using text extraction")
                    return {
                        'action': 'See full response',
                        'amount': 'Variable',
                        'reason': content[:200],
                        'priority': 'medium',
                        'source': 'grok_ai_text'
                    }
            else:
                logger.error(f"Grok API error: {response.status_code} - {response.text}")
                
        except requests.Timeout:
            logger.error("Grok API timeout")
        except Exception as e:
            logger.error(f"Grok API error: {e}")
        
        return None
    
    def _local_recommendation(self, tower: str, issue_type: str, sensor_data: Dict) -> Dict:
        """Local rule-based nutrient recommendations"""
        tower_info = self.nutrient_database[tower]
        ec = sensor_data.get('ec', 0)
        ph = sensor_data.get('ph', 0)
        
        # EC adjustments
        if 'ec_low' in issue_type:
            if tower == 'cool':
                return {
                    'action': 'Add Lettuce Fertilizer 8-15-36',
                    'amount': '5-8g',
                    'reason': f'EC below target ({ec:.2f} < {tower_info["ec_range"][0]})',
                    'priority': 'medium',
                    'source': 'local'
                }
            else:  # warm
                return {
                    'action': 'Add MaxiGrow (small scoop)',
                    'amount': '~5g',
                    'reason': f'EC below target ({ec:.2f} < {tower_info["ec_range"][0]})',
                    'priority': 'medium',
                    'source': 'local'
                }
        
        elif 'ec_high' in issue_type:
            return {
                'action': 'Dilute with RO water or fresh reservoir change',
                'amount': '0.5-1 gallon RO water if <10% over target',
                'reason': f'EC above target ({ec:.2f} > {tower_info["ec_range"][1]})',
                'priority': 'high' if ec > tower_info["ec_range"][1] * 1.2 else 'medium',
                'source': 'local'
            }
        
        # pH adjustments
        elif 'ph_high' in issue_type:
            return {
                'action': 'Add pH Down',
                'amount': '0.5ml, wait 30min, retest',
                'reason': f'pH above target ({ph:.2f} > {tower_info["ph_range"][1]})',
                'priority': 'high',
                'source': 'local'
            }
        
        elif 'ph_low' in issue_type:
            return {
                'action': 'Check calibration - pH rarely drifts low',
                'amount': 'N/A',
                'reason': f'Unusual low pH ({ph:.2f}). Verify probe accuracy.',
                'priority': 'high',
                'source': 'local'
            }
        
        # Calcium deficiency (tip burn)
        elif 'calcium' in issue_type or 'tip_burn' in issue_type:
            return {
                'action': 'Foliar Ca spray + check air flow',
                'amount': '5ml CalMagic per liter water, spray leaves',
                'reason': 'Tip burn indicates Ca transport issue. Increase air circulation.',
                'priority': 'high',
                'source': 'local'
            }
        
        # Nitrogen deficiency
        elif 'nitrogen' in issue_type or 'yellowing' in issue_type:
            if tower == 'cool':
                return {
                    'action': 'Add Lettuce Fertilizer',
                    'amount': '5g',
                    'reason': 'Yellowing indicates nitrogen deficiency',
                    'priority': 'medium',
                    'source': 'local'
                }
            else:
                return {
                    'action': 'Add MaxiGrow',
                    'amount': 'Small scoop (~5g)',
                    'reason': 'Yellowing indicates nitrogen deficiency',
                    'priority': 'medium',
                    'source': 'local'
                }
        
        # Magnesium deficiency
        elif 'magnesium' in issue_type:
            return {
                'action': 'Add Epsom Salt',
                'amount': '2-3g',
                'reason': 'Interveinal chlorosis suggests Mg deficiency',
                'priority': 'medium',
                'source': 'local'
            }
        
        # Default
        else:
            return {
                'action': 'Monitor and verify issue',
                'amount': 'N/A',
                'reason': f'Unknown issue type: {issue_type}',
                'priority': 'low',
                'source': 'local'
            }
    
    def get_fresh_reservoir_recipe(self, tower: str) -> str:
        """Get full recipe for fresh reservoir mix"""
        if tower == 'cool':
            return """Cool Tower Fresh Reservoir (5 gallons):
1. Buffer: 5ml CalMagic + 10g Calcium Nitrate
2. Fertilizer: 10-12g Lettuce Fertilizer 8-15-36
3. Supplements: 5g Epsom Salt, 5ml Armor Si
4. Mix order: Add buffers first, stir, then fertilizer/Epsom
5. Aerate with air stones, adjust pH to 5.8-6.2
6. Target EC: 1.2-1.8 mS/cm
7. Wait 60min, then add 10ml Hydroguard"""
        else:  # warm
            return """Warm Tower Fresh Reservoir (5 gallons):
1. Buffer: 5ml CalMagic
2. Fertilizer: 10g MaxiGrow (1 big + 1 little scoop)
3. Supplements: 5ml Armor Si, optional 1-2g Epsom Salt
4. Stir gently, aerate with air stones
5. Adjust pH to 5.8-6.2
6. Target EC: 1.5-2.0 mS/cm
7. Wait 60min, then add 10ml Hydroguard"""


if __name__ == '__main__':
    # Test mode
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    advisor = NutrientAdvisor()
    
    # Test local recommendations
    print("=== Local Recommendation Test ===")
    rec = advisor.get_recommendation(
        'cool',
        'ec_low',
        {'ec': 1.0, 'ph': 6.0, 'water_temp': 68.0}
    )
    print(json.dumps(rec, indent=2))
    
    # Test Grok API if enabled
    if advisor.xai_enabled:
        print("\n=== Grok AI Recommendation Test ===")
        rec = advisor.get_recommendation(
            'warm',
            'deficiency_detected',
            {'ec': 1.7, 'ph': 6.1, 'water_temp': 72.0, 'air_temp': 76.0, 'humidity': 55.0},
            deficiencies=['tip_burn', 'slight_yellowing']
        )
        print(json.dumps(rec, indent=2))
    
    # Print recipes
    print("\n=== Fresh Reservoir Recipes ===")
    print(advisor.get_fresh_reservoir_recipe('cool'))
    print("\n")
    print(advisor.get_fresh_reservoir_recipe('warm'))
