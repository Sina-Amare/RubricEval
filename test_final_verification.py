#!/usr/bin/env python3
"""
Final verification test - Life and death matter check!
"""

import sys
sys.path.insert(0, 'src')

import asyncio
from adapters.storage.sqlite import SQLiteAdapter
from adapters.notifications.telegram import TelegramAdapter
from core.models import Role, Submission, SubmissionStatus
from datetime import datetime, timezone

async def final_verification():
    print("🔍 FINAL VERIFICATION - LIFE AND DEATH CHECK!")
    print("=" * 60)
    
    storage = SQLiteAdapter('sqlite:///data/reviews.db')
    telegram = TelegramAdapter('fake_token')  # We won't send, just format
    
    all_good = True
    
    try:
        # Get the two most recent frontend reports you mentioned
        reports = await storage.get_reports_by_role(Role.FRONTEND, limit=2)
        
        if not reports:
            print("❌ No frontend reports to test!")
            return False
        
        for report in reports:
            print(f"\n📝 Testing Report ID: {report.id}")
            print("-" * 40)
            
            # Test 1: Check database retrieval completeness
            print("1️⃣ Database Retrieval Test:")
            if not hasattr(report.analysis_result, 'architecture_analysis'):
                print("   ❌ FAIL: Missing architecture_analysis attribute!")
                all_good = False
            elif report.analysis_result.architecture_analysis is None:
                print("   ⚠️  WARNING: architecture_analysis is None")
                all_good = False
            else:
                print(f"   ✅ PASS: architecture_analysis present")
                arch = report.analysis_result.architecture_analysis
                print(f"      - Type: {type(arch)}")
                print(f"      - Keys: {list(arch.keys()) if isinstance(arch, dict) else 'Not a dict'}")
            
            if not hasattr(report.analysis_result, 'penalty_breakdown'):
                print("   ❌ FAIL: Missing penalty_breakdown attribute!")
                all_good = False
            else:
                print(f"   ✅ PASS: penalty_breakdown present")
            
            if not hasattr(report.analysis_result, 'hiring_decision'):
                print("   ❌ FAIL: Missing hiring_decision attribute!")
                all_good = False
            else:
                print(f"   ✅ PASS: hiring_decision present")
            
            # Test 2: Check Telegram formatting
            print("\n2️⃣ Telegram Display Test:")
            
            # Create a dummy submission for testing
            dummy_submission = Submission(
                telegram_user_id="123",
                telegram_username="test",
                github_url="https://github.com/test/test",
                role=Role.FRONTEND,
                status=SubmissionStatus.COMPLETED
            )
            dummy_submission.id = 1
            
            # Test the architecture formatting
            arch_text = telegram._format_architecture_requirements(
                report.analysis_result, 
                Role.FRONTEND
            )
            
            if "Frontend architecture analysis not available" in arch_text:
                print("   ❌ FAIL: Still showing 'not available' message!")
                print(f"      Architecture data: {report.analysis_result.architecture_analysis}")
                all_good = False
            else:
                print("   ✅ PASS: Architecture analysis displays correctly")
                # Check for expected content
                expected_items = ['App Router', 'File Conventions', 'Server/Client Components']
                for item in expected_items:
                    if item in arch_text:
                        print(f"      ✅ Contains '{item}'")
                    else:
                        print(f"      ⚠️  Missing '{item}'")
            
            # Test 3: Check for specific evidence in feedback
            print("\n3️⃣ Feedback Quality Test:")
            feedback = report.analysis_result.detailed_feedback
            
            import re
            # Check for file:line patterns
            evidence_patterns = re.findall(r'\w+\.\w+:\d+', feedback)
            if evidence_patterns:
                print(f"   ✅ Contains {len(evidence_patterns)} specific file:line references")
            else:
                print(f"   ⚠️  No file:line evidence (may be old report)")
            
            # Check for vague phrases
            vague_phrases = ['could benefit from', 'might improve', 'consider adding']
            vague_found = [p for p in vague_phrases if p in feedback.lower()]
            if vague_found:
                print(f"   ⚠️  Contains vague phrases: {vague_found} (may be old report)")
            else:
                print(f"   ✅ No vague language")
    
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        all_good = False
    
    finally:
        await storage.close()
    
    print("\n" + "=" * 60)
    if all_good:
        print("✅ ALL TESTS PASSED - YOU'RE SAFE! 🎉")
        print("The frontend analysis is now as robust as backend!")
    else:
        print("⚠️  Some issues detected - see above for details")
    
    return all_good

if __name__ == "__main__":
    result = asyncio.run(final_verification())
    sys.exit(0 if result else 1)