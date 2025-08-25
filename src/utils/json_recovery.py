"""
JSON recovery utilities for handling malformed LLM responses.

This module provides robust JSON extraction and recovery mechanisms
to prevent losing expensive LLM responses due to minor formatting issues.
"""

import json
import re
from typing import Dict, Any, Optional, Tuple
from utils.logger import setup_logger

logger = setup_logger(__name__)


class JSONRecovery:
    """
    Robust JSON extraction and recovery from LLM responses.
    
    Handles various common issues:
    - Missing commas
    - Trailing commas
    - Unescaped quotes
    - Mixed quotes
    - Incomplete JSON
    - JSON within markdown
    - Multiple JSON objects
    """
    
    @staticmethod
    def extract_json(response_text: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Extract JSON from response with multiple fallback strategies.
        
        Returns:
            Tuple of (parsed_json, raw_json_text) or (None, error_message)
        """
        if not response_text or not response_text.strip():
            return None, "Empty response"
        
        # Store original for recovery attempts
        original = response_text
        
        # Strategy 1: Direct JSON parsing
        result = JSONRecovery._try_direct_parse(response_text)
        if result[0]:
            return result
        
        # Strategy 2: Extract from markdown code blocks
        result = JSONRecovery._extract_from_markdown(response_text)
        if result[0]:
            return result
        
        # Strategy 3: Find JSON boundaries
        result = JSONRecovery._extract_json_boundaries(response_text)
        if result[0]:
            return result
        
        # Strategy 4: Fix common JSON errors
        result = JSONRecovery._fix_and_parse(response_text)
        if result[0]:
            return result
        
        # Strategy 5: Partial recovery - extract what we can
        result = JSONRecovery._partial_recovery(response_text)
        if result[0]:
            logger.warning("Using partial recovery - some data may be missing")
            return result
        
        # Strategy 6: Save raw response for manual recovery
        JSONRecovery._save_failed_response(original)
        
        return None, "All recovery strategies failed"
    
    @staticmethod
    def _try_direct_parse(text: str) -> Tuple[Optional[Dict], Optional[str]]:
        """Try direct JSON parsing."""
        try:
            text = text.strip()
            if text.startswith('{') and text.endswith('}'):
                return json.loads(text), text
        except json.JSONDecodeError:
            pass
        return None, None
    
    @staticmethod
    def _extract_from_markdown(text: str) -> Tuple[Optional[Dict], Optional[str]]:
        """Extract JSON from markdown code blocks."""
        patterns = [
            r'```json\s*(.*?)```',
            r'```\s*(.*?)```',
            r'`([^`]+)`'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                match = match.strip()
                if match.startswith('{'):
                    try:
                        return json.loads(match), match
                    except json.JSONDecodeError:
                        # Try fixing common issues
                        fixed = JSONRecovery._fix_json_string(match)
                        try:
                            return json.loads(fixed), fixed
                        except json.JSONDecodeError:
                            continue
        
        return None, None
    
    @staticmethod
    def _extract_json_boundaries(text: str) -> Tuple[Optional[Dict], Optional[str]]:
        """Find JSON object boundaries in text."""
        # Find all potential JSON start/end positions
        starts = [m.start() for m in re.finditer(r'\{', text)]
        ends = [m.end() for m in re.finditer(r'\}', text)]
        
        # Try different combinations
        for start in starts:
            for end in reversed(ends):
                if end > start:
                    potential_json = text[start:end]
                    try:
                        return json.loads(potential_json), potential_json
                    except json.JSONDecodeError:
                        # Try with fixes
                        fixed = JSONRecovery._fix_json_string(potential_json)
                        try:
                            return json.loads(fixed), fixed
                        except json.JSONDecodeError:
                            continue
        
        return None, None
    
    @staticmethod
    def _fix_json_string(json_str: str) -> str:
        """Fix common JSON formatting issues."""
        # Remove trailing commas
        json_str = re.sub(r',\s*}', '}', json_str)
        json_str = re.sub(r',\s*]', ']', json_str)
        
        # Fix missing commas between elements
        json_str = re.sub(r'}\s*"', '},"', json_str)
        json_str = re.sub(r']\s*"', '],"', json_str)
        json_str = re.sub(r'(\d)\s*"', r'\1,"', json_str)
        json_str = re.sub(r'"\s*"', '","', json_str)
        
        # Fix unescaped quotes inside strings
        # This is tricky - we'll try to identify string boundaries
        lines = json_str.split('\n')
        fixed_lines = []
        for line in lines:
            # If line has a key-value pair with unescaped quotes
            if '": "' in line:
                parts = line.split('": "', 1)
                if len(parts) == 2 and parts[1].count('"') > 1:
                    # Likely has unescaped quotes
                    value_part = parts[1].rstrip(',').rstrip('"')
                    if value_part:
                        value_part = value_part.replace('"', '\\"')
                        line = parts[0] + '": "' + value_part + '"'
                        if parts[1].rstrip().endswith(','):
                            line += ','
            fixed_lines.append(line)
        json_str = '\n'.join(fixed_lines)
        
        # Remove any BOM or special characters at the start
        json_str = json_str.lstrip('\ufeff')
        
        # Ensure proper escaping of backslashes
        json_str = json_str.replace('\\\\', '\\')
        
        return json_str
    
    @staticmethod
    def _fix_and_parse(text: str) -> Tuple[Optional[Dict], Optional[str]]:
        """Apply various fixes and try parsing."""
        # Find potential JSON content
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if not json_match:
            return None, None
        
        json_str = json_match.group()
        
        # Apply fixes
        fixed = JSONRecovery._fix_json_string(json_str)
        
        try:
            return json.loads(fixed), fixed
        except json.JSONDecodeError as e:
            # Try more aggressive fixes
            logger.debug(f"JSON decode error after fixes: {e}")
            
            # Remove problematic unicode characters
            fixed = fixed.encode('ascii', 'ignore').decode('ascii')
            
            # Try to fix specific error position
            if hasattr(e, 'pos'):
                # Try to fix around the error position
                before = fixed[:e.pos]
                after = fixed[e.pos:]
                
                # Common fix: add missing comma
                if after and after[0] == '"' and before and before[-1] not in ',{[':
                    fixed = before + ',' + after
                    try:
                        return json.loads(fixed), fixed
                    except json.JSONDecodeError:
                        pass
            
        return None, None
    
    @staticmethod
    def _partial_recovery(text: str) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Attempt to recover partial data from malformed JSON.
        Extract what fields we can even if the full structure is broken.
        """
        result = {
            "requirements_met": {},
            "scores": {},
            "strengths": [],
            "weaknesses": [],
            "recommendation": "review_required",
            "confidence": 50,
            "detailed_feedback": "Partial recovery from malformed response",
            "suggestions": [],
            "partial_recovery": True
        }
        
        # Try to extract specific fields using regex
        patterns = {
            'recommendation': r'"recommendation"\s*:\s*"([^"]+)"',
            'confidence': r'"confidence"\s*:\s*(\d+)',
            'detailed_feedback': r'"detailed_feedback"\s*:\s*"([^"]+)"',
        }
        
        for field, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = match.group(1)
                if field == 'confidence':
                    result[field] = int(value)
                else:
                    result[field] = value
        
        # Extract scores if possible
        score_pattern = r'"scores"\s*:\s*\{([^}]+)\}'
        score_match = re.search(score_pattern, text, re.DOTALL)
        if score_match:
            scores_text = score_match.group(1)
            score_items = re.findall(r'"([^"]+)"\s*:\s*(\d+)', scores_text)
            for key, value in score_items:
                result['scores'][key] = int(value)
        
        # Extract arrays (strengths, weaknesses)
        for field in ['strengths', 'weaknesses', 'suggestions']:
            pattern = rf'"{field}"\s*:\s*\[(.*?)\]'
            match = re.search(pattern, text, re.DOTALL)
            if match:
                items_text = match.group(1)
                items = re.findall(r'"([^"]+)"', items_text)
                result[field] = items
        
        # Extract requirements_met
        req_pattern = r'"requirements_met"\s*:\s*\{([^}]+)\}'
        req_match = re.search(req_pattern, text, re.DOTALL)
        if req_match:
            req_text = req_match.group(1)
            req_items = re.findall(r'"([^"]+)"\s*:\s*(true|false)', req_text, re.IGNORECASE)
            for key, value in req_items:
                result['requirements_met'][key] = value.lower() == 'true'
        
        # Only return if we got at least some meaningful data
        if (result['scores'] or result['strengths'] or result['weaknesses'] or 
            result['recommendation'] != 'review_required'):
            logger.info(f"Partial recovery successful - recovered {len(result)} fields")
            return result, json.dumps(result)
        
        return None, None
    
    @staticmethod
    def _save_failed_response(response_text: str):
        """Save failed response for manual recovery or debugging."""
        import os
        from datetime import datetime
        
        # Create directory for failed responses
        failed_dir = "./data/failed_responses"
        os.makedirs(failed_dir, exist_ok=True)
        
        # Save with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(failed_dir, f"failed_response_{timestamp}.txt")
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(response_text)
            logger.info(f"Saved failed response to {filepath} for manual recovery")
        except Exception as e:
            logger.error(f"Failed to save response: {e}")
    
    @staticmethod
    def validate_recovered_json(data: Dict[str, Any]) -> bool:
        """
        Validate that recovered JSON has minimum required fields.
        
        Returns:
            True if JSON has minimum viable structure
        """
        required_fields = ['recommendation', 'scores']
        
        for field in required_fields:
            if field not in data:
                return False
        
        # Check scores has at least some values
        if not isinstance(data.get('scores'), dict) or not data['scores']:
            return False
        
        return True