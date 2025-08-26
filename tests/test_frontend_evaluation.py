#!/usr/bin/env python3
"""
Test script for frontend evaluation system
Tests the new Next.js App Router evaluation criteria
"""

import sys
import os
import asyncio
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from adapters.analyzers.openrouter import OpenRouterAnalyzer
from adapters.repositories.github import GitHubAdapter
from config import Config
from utils.logger import setup_logger

# Setup logger
logger = setup_logger('test_frontend', 'logs/test_frontend.log')

async def test_frontend_repo(repo_url: str, expected_decision: str):
    """
    Test a frontend repository
    
    Args:
        repo_url: GitHub repository URL
        expected_decision: Expected hiring decision (HIRE/NO_HIRE)
    """
    print(f"\n{'='*60}")
    print(f"Testing: {repo_url}")
    print(f"Expected: {expected_decision}")
    print(f"{'='*60}")
    
    try:
        # Initialize components
        config = Config()
        analyzer = OpenRouterAnalyzer(config, logger)
        github = GitHubAdapter(config, logger)
        
        # Clone and get files
        print("1. Cloning repository...")
        repo_data = await github.get_repository_content(
            repo_url=repo_url,
            role='frontend'
        )
        
        if not repo_data or not repo_data.get('files'):
            print("❌ Failed to get repository content")
            return False
            
        print(f"   ✓ Found {len(repo_data['files'])} files")
        
        # Check for App Router structure
        files = repo_data['files']
        app_router_files = [f['path'] for f in files if f['path'].startswith('app/')]
        pages_router_files = [f['path'] for f in files if f['path'].startswith('pages/')]
        
        print(f"\n2. Router Detection:")
        print(f"   - App Router files: {len(app_router_files)}")
        print(f"   - Pages Router files: {len(pages_router_files)}")
        
        if app_router_files[:5]:  # Show first 5 app router files
            print("   Sample App Router files:")
            for f in app_router_files[:5]:
                print(f"     • {f}")
        
        # Analyze
        print("\n3. Running LLM analysis...")
        result = await analyzer.analyze_code(
            files=repo_data['files'],
            repository_url=repo_url,
            role='frontend'
        )
        
        if not result:
            print("❌ Analysis failed")
            return False
        
        # Extract key information
        print("\n4. Analysis Results:")
        
        # Requirements check
        if 'requirements_met' in result:
            print("\n   Mandatory Requirements:")
            reqs = result['requirements_met']
            all_met = True
            for req, met in reqs.items():
                status = "✓" if met else "✗"
                print(f"     {status} {req}: {met}")
                if not met:
                    all_met = False
            print(f"   All requirements met: {'YES' if all_met else 'NO'}")
        
        # Architecture analysis
        if 'architecture_analysis' in result:
            arch = result['architecture_analysis']
            print("\n   Architecture Analysis:")
            print(f"     - Uses App Router: {arch.get('uses_app_router', False)}")
            print(f"     - File conventions followed: {arch.get('file_conventions_followed', False)}")
            print(f"     - Server/Client boundaries correct: {arch.get('server_client_boundaries_correct', False)}")
        
        # Penalties
        if 'penalty_breakdown' in result:
            penalties = result['penalty_breakdown']
            print(f"\n   Penalties: {penalties.get('total_penalty', 0)} points")
            if penalties.get('issues_found'):
                print("   Issues found:")
                for issue in penalties['issues_found'][:5]:  # Show first 5 issues
                    print(f"     • [{issue.get('category', 'unknown')}] {issue.get('issue', '')} ({issue.get('penalty', 0)} points)")
        
        # Scores
        if 'scores' in result:
            scores = result['scores']
            print("\n   Quality Scores:")
            print(f"     - Task Completion: {scores.get('task_completion', 0)}%")
            print(f"     - Code Quality: {scores.get('code_quality', 0)}%")
            print(f"     - Seniority: {scores.get('seniority_indicators', 0)}%")
            print(f"     - Next.js Expertise: {scores.get('nextjs_expertise', 0)}%")
            print(f"     - Critical Issues Penalty: {scores.get('critical_issues_penalty', 0)}")
            
            # Calculate average (excluding penalty)
            positive_scores = [
                scores.get('task_completion', 0),
                scores.get('code_quality', 0),
                scores.get('seniority_indicators', 0),
                scores.get('nextjs_expertise', 0)
            ]
            avg_score = sum(positive_scores) / len(positive_scores)
            print(f"     - Average Quality: {avg_score:.1f}%")
        
        # Hiring decision
        if 'hiring_decision' in result:
            decision = result['hiring_decision']
            print(f"\n   📊 Hiring Decision: {decision.get('decision', 'UNKNOWN')}")
            print(f"   Confidence: {decision.get('confidence', 'UNKNOWN')}")
            print(f"   Reason: {decision.get('primary_reason', 'N/A')}")
            
            # Check if matches expected
            actual_decision = decision.get('decision', 'UNKNOWN')
            if actual_decision == expected_decision:
                print(f"\n✅ TEST PASSED: Decision matches expected ({expected_decision})")
                return True
            else:
                print(f"\n❌ TEST FAILED: Expected {expected_decision}, got {actual_decision}")
                return False
        
        print("\n❌ No hiring decision in result")
        return False
        
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        logger.error(f"Test error for {repo_url}: {e}", exc_info=True)
        return False

async def main():
    """Run frontend evaluation tests"""
    
    print("\n" + "="*60)
    print("FRONTEND EVALUATION TEST SUITE")
    print("Testing Next.js App Router evaluation criteria")
    print("="*60)
    
    # Test cases
    test_cases = [
        # You can add test repositories here
        # Format: (repo_url, expected_decision)
        # Example:
        # ("https://github.com/user/nextjs-app-router-auth", "HIRE"),
        # ("https://github.com/user/nextjs-pages-router-auth", "NO_HIRE"),
    ]
    
    if not test_cases:
        print("\nℹ️  No test cases defined. Add repositories to test in the test_cases list.")
        print("\nTo test a specific repository, you can run:")
        print("  python test_frontend_evaluation.py <github_url>")
        
        # Check if URL provided as argument
        if len(sys.argv) > 1:
            repo_url = sys.argv[1]
            print(f"\nTesting provided repository: {repo_url}")
            await test_frontend_repo(repo_url, "UNKNOWN")
        else:
            print("\nExample repositories to test:")
            print("  - App Router (should HIRE if good): Any Next.js 14+ app with /app directory")
            print("  - Pages Router (should NO_HIRE): Any Next.js app with /pages directory")
            print("  - Non-Tailwind (should NO_HIRE): Any app using CSS modules or styled-components")
    else:
        # Run all test cases
        results = []
        for repo_url, expected in test_cases:
            success = await test_frontend_repo(repo_url, expected)
            results.append((repo_url, success))
        
        # Summary
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        passed = sum(1 for _, success in results if success)
        total = len(results)
        print(f"Passed: {passed}/{total}")
        
        for repo_url, success in results:
            status = "✓" if success else "✗"
            print(f"  {status} {repo_url}")

if __name__ == "__main__":
    asyncio.run(main())