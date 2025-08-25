"""
Test JSON recovery functionality with various malformed responses.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.json_recovery import JSONRecovery


def test_json_recovery():
    """Test various JSON recovery scenarios."""
    
    test_cases = [
        # Case 1: Valid JSON
        {
            "name": "Valid JSON",
            "input": '{"recommendation": "accept", "scores": {"quality": 80}}',
            "should_pass": True
        },
        
        # Case 2: JSON with markdown
        {
            "name": "JSON in markdown",
            "input": '''Here's my analysis:
```json
{
    "recommendation": "accept",
    "scores": {"quality": 80, "testing": 70},
    "strengths": ["Good code", "Clean architecture"]
}
```
That's the result.''',
            "should_pass": True
        },
        
        # Case 3: Missing comma (your error case)
        {
            "name": "Missing comma",
            "input": '''{
    "recommendation": "reject",
    "scores": {
        "quality": 50,
        "testing": 30
    }
    "strengths": ["Some good parts"]
}''',
            "should_pass": True
        },
        
        # Case 4: Trailing comma
        {
            "name": "Trailing comma",
            "input": '''{
    "recommendation": "accept",
    "scores": {"quality": 90,},
    "strengths": ["Excellent",],
}''',
            "should_pass": True
        },
        
        # Case 5: Unescaped quotes
        {
            "name": "Unescaped quotes",
            "input": '''{
    "recommendation": "accept",
    "detailed_feedback": "The code has "good" quality and shows "excellent" patterns",
    "scores": {"quality": 85}
}''',
            "should_pass": True
        },
        
        # Case 6: Incomplete JSON
        {
            "name": "Incomplete JSON",
            "input": '''{
    "recommendation": "review_required",
    "scores": {"quality": 60, "testing": 50},
    "strengths": ["Decent structure"''',
            "should_pass": True  # Partial recovery
        },
        
        # Case 7: Mixed content
        {
            "name": "Mixed content",
            "input": '''Analysis complete. Here are the results:

The candidate shows promise.

{
    "recommendation": "accept",
    "confidence": 75,
    "scores": {
        "quality": 80,
        "architecture": 85
    }
}

Additional notes: Good overall.''',
            "should_pass": True
        },
        
        # Case 8: Extra backticks (common LLM issue)
        {
            "name": "Extra backticks",
            "input": '''```json
{
    "recommendation": "strongly_accept",
    "scores": {"quality": 95}
}
```
```''',
            "should_pass": True
        }
    ]
    
    print("Testing JSON Recovery System")
    print("=" * 50)
    
    passed = 0
    failed = 0
    
    for test in test_cases:
        print(f"\nTest: {test['name']}")
        print("-" * 30)
        
        result, raw = JSONRecovery.extract_json(test['input'])
        
        if result:
            print(f"✓ Recovery successful")
            print(f"  Recommendation: {result.get('recommendation', 'N/A')}")
            print(f"  Scores: {result.get('scores', {})}")
            if result.get('partial_recovery'):
                print(f"  ⚠ Partial recovery used")
            passed += 1
        else:
            print(f"✗ Recovery failed: {raw}")
            if test['should_pass']:
                failed += 1
                print(f"  ERROR: This should have passed!")
        
    print("\n" + "=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 50)
    
    # Test validation
    print("\nTesting validation...")
    valid_data = {"recommendation": "accept", "scores": {"quality": 80}}
    invalid_data = {"recommendation": "accept"}  # Missing scores
    
    print(f"Valid data validation: {JSONRecovery.validate_recovered_json(valid_data)}")
    print(f"Invalid data validation: {JSONRecovery.validate_recovered_json(invalid_data)}")


if __name__ == "__main__":
    test_json_recovery()