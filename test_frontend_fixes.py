#!/usr/bin/env python3
"""
Test script to verify frontend analysis fixes.
"""

import asyncio
import json
from pathlib import Path

# Add src to path
import sys
sys.path.insert(0, 'src')

from adapters.storage.sqlite import SQLiteAdapter
from core.models import (
    Report, AnalysisResult, RecommendationLevel,
    Submission, SubmissionStatus, Role
)
from datetime import datetime, timezone


async def test_architecture_retrieval():
    """Test that architecture analysis is properly retrieved from database."""
    
    print("🧪 Testing Frontend Analysis Fixes")
    print("=" * 50)
    
    # Initialize storage adapter
    storage = SQLiteAdapter("sqlite:///data/reviews.db")
    
    try:
        # Test 1: Check recent frontend reports
        print("\n📊 Checking recent frontend reports...")
        reports = await storage.get_reports_by_role(Role.FRONTEND, limit=2)
        
        if not reports:
            print("⚠️  No frontend reports found in database")
            return
        
        for i, report in enumerate(reports, 1):
            print(f"\n📝 Report #{i} (ID: {report.id}):")
            
            # Check if analysis_result has architecture_analysis
            if hasattr(report.analysis_result, 'architecture_analysis'):
                arch = report.analysis_result.architecture_analysis
                if arch:
                    print(f"  ✅ Architecture analysis present")
                    print(f"     - App Router: {arch.get('uses_app_router', 'N/A')}")
                    print(f"     - File conventions: {arch.get('file_conventions_followed', 'N/A')}")
                    
                    # Check folder structure
                    folder = arch.get('folder_structure_analysis', {})
                    if folder:
                        print(f"     - Components dir: {folder.get('has_components_directory', 'N/A')}")
                        print(f"     - Lib dir: {folder.get('has_lib_directory', 'N/A')}")
                        print(f"     - Overall quality: {folder.get('overall_structure_quality', 'N/A')}")
                else:
                    print(f"  ❌ Architecture analysis is None")
            else:
                print(f"  ❌ No architecture_analysis attribute")
            
            # Check penalty breakdown
            if hasattr(report.analysis_result, 'penalty_breakdown'):
                penalty = report.analysis_result.penalty_breakdown
                if penalty:
                    total = penalty.get('total_penalty', 0) if isinstance(penalty, dict) else 0
                    print(f"  📊 Penalty breakdown present (total: {total} points)")
                else:
                    print(f"  ⚠️  Penalty breakdown is None")
            
            # Check hiring decision
            if hasattr(report.analysis_result, 'hiring_decision'):
                hiring = report.analysis_result.hiring_decision
                if hiring:
                    decision = hiring.get('decision', 'N/A') if isinstance(hiring, dict) else 'N/A'
                    print(f"  🎯 Hiring decision: {decision}")
            
            # Check for specific evidence in feedback
            feedback = report.analysis_result.detailed_feedback
            if feedback:
                # Look for file:line patterns
                import re
                evidence_patterns = re.findall(r'\w+\.\w+:\d+', feedback)
                if evidence_patterns:
                    print(f"  ✅ Contains specific evidence: {len(evidence_patterns)} references")
                    print(f"     Examples: {evidence_patterns[:3]}")
                else:
                    print(f"  ⚠️  No specific file:line evidence found")
                
                # Check for vague language
                vague_phrases = ['could benefit', 'might improve', 'consider adding']
                has_vague = any(phrase in feedback.lower() for phrase in vague_phrases)
                if has_vague:
                    print(f"  ⚠️  Contains vague language")
                else:
                    print(f"  ✅ No vague language detected")
        
        print("\n" + "=" * 50)
        print("✅ Test completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await storage.close()


if __name__ == "__main__":
    asyncio.run(test_architecture_retrieval())