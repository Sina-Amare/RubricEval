#!/usr/bin/env python3
"""Test script to verify the hiring decision override fix."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import asyncio
import json
import sqlite3
from pathlib import Path
from adapters.analyzers.openrouter import OpenRouterAdapter as OpenRouterAnalyzer
from adapters.repositories.github import GitHubAdapter
from adapters.storage.sqlite import SQLiteAdapter  
from adapters.notifications.telegram import TelegramAdapter
from core.models import Submission, SubmissionStatus, Role as CandidateRole
import config
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_majidbl_aaa():
    """Test the majidbl/aaa repository analysis."""
    
    # Initialize adapters
    db_url = f"sqlite:///{config.DATABASE_PATH}"
    storage = SQLiteAdapter(db_url)
    await storage.initialize()
    
    repo_adapter = GitHubAdapter(config.MAX_TOKENS)
    analyzer = OpenRouterAnalyzer()
    
    # Create a test submission
    submission = Submission(
        telegram_user_id="test_user",
        telegram_username="test_username",
        candidate_name="Majid BL",
        github_url="https://github.com/majidbl/aaa",
        role=CandidateRole.BACKEND,
        status=SubmissionStatus.PENDING
    )
    
    # Save submission
    saved_submission = await storage.create_submission(submission)
    logger.info(f"Created submission ID: {saved_submission.id}")
    
    try:
        # Clone and extract files
        logger.info("Cloning repository...")
        files = await repo_adapter.extract_repository_files(submission.github_url)
        logger.info(f"Extracted {len(files)} files")
        
        # Analyze
        logger.info("Analyzing repository...")
        result = await analyzer.analyze_code(files, submission.role)
        
        # Log the key metrics
        logger.info("\n=== ANALYSIS RESULTS ===")
        logger.info(f"Scores: {result.scores}")
        
        # Calculate average from positive metrics only
        positive_scores = []
        for key, value in result.scores.items():
            if 'penalty' not in key.lower() and 'critical' not in key.lower():
                positive_scores.append(value)
        avg_score = sum(positive_scores) / len(positive_scores) if positive_scores else 0
        logger.info(f"Average (positive only): {avg_score:.1f}%")
        
        penalty = result.scores.get('critical_issues_penalty', 0)
        logger.info(f"Penalty: {penalty}")
        
        if result.hiring_decision:
            logger.info(f"Hiring Decision: {result.hiring_decision.get('decision')}")
            logger.info(f"Primary Reason: {result.hiring_decision.get('primary_reason')}")
        
        # Check if the decision matches our expectation
        expected_hire = penalty < 50 and avg_score >= 70
        actual_hire = result.hiring_decision and result.hiring_decision.get('decision') == 'HIRE'
        
        if expected_hire == actual_hire:
            logger.info("✅ PASS: Hiring decision matches expected logic!")
        else:
            logger.error(f"❌ FAIL: Expected {'HIRE' if expected_hire else 'NO_HIRE'} but got {'HIRE' if actual_hire else 'NO_HIRE'}")
        
        # Save the report
        from core.models import Report
        report = Report(
            submission_id=saved_submission.id,
            analysis_result=result,
            model_used="google/gemini-2.5-flash",
            tokens_used=0,
            analysis_duration=0
        )
        
        saved_report = await storage.create_report(report)
        logger.info(f"Created report ID: {saved_report.id}")
        
        # Now test the Telegram formatting
        logger.info("\n=== TESTING TELEGRAM REPORT FORMATTING ===")
        
        # Get report from DB to simulate real flow
        db_report = await storage.get_report(saved_report.id)
        
        # Check if hiring_decision is in the stored JSON
        conn = sqlite3.connect(config.DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT analysis_result FROM reports WHERE id = ?", (saved_report.id,))
        row = cursor.fetchone()
        if row:
            analysis_json = json.loads(row[0])
            logger.info(f"Hiring decision in DB: {analysis_json.get('hiring_decision')}")
        conn.close()
        
        # Initialize Telegram adapter and test formatting
        telegram = TelegramAdapter(config.BOT_TOKEN)
        
        # This will test if the report displays correctly
        report_text = telegram._format_analysis_report(saved_submission, db_report)
        
        # Check if the report contains HIRE or NO HIRE
        if "✅ HIRE" in report_text:
            logger.info("✅ Report shows HIRE decision")
        elif "❌ NO HIRE" in report_text:
            logger.info("❌ Report shows NO HIRE decision")
        else:
            logger.warning("⚠️ Report doesn't show clear hiring decision")
        
        # Log the decision section
        lines = report_text.split('\n')
        for i, line in enumerate(lines):
            if 'HIRING RECOMMENDATION' in line:
                logger.info(f"\nHiring section from report:\n{chr(10).join(lines[i:min(i+5, len(lines))])}")
                break
        
        return expected_hire == actual_hire and ("✅ HIRE" in report_text if expected_hire else "❌ NO HIRE" in report_text)
        
    except Exception as e:
        logger.error(f"Test failed with error: {e}", exc_info=True)
        return False
    finally:
        # Cleanup
        await storage.close()

if __name__ == "__main__":
    success = asyncio.run(test_majidbl_aaa())
    if success:
        print("\n✅ All tests passed! The fix is working correctly.")
    else:
        print("\n❌ Tests failed. The issue is not fully resolved.")