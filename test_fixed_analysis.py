#!/usr/bin/env python3
"""
Test the fixed analysis system to ensure unique, accurate evaluations
"""

import asyncio
import sys
sys.path.insert(0, 'src')

from adapters.repositories.github import GitHubAdapter
from adapters.analyzers.openrouter import OpenRouterAdapter
from core.models import AnalysisRequest, Role
import os
from dotenv import load_dotenv

load_dotenv()

async def test_repository_analysis(repo_url: str):
    """Test analysis of a specific repository"""
    print(f"\n{'='*60}")
    print(f"Testing: {repo_url}")
    print('='*60)
    
    # Initialize adapters
    github_adapter = GitHubAdapter()
    analyzer = OpenRouterAdapter()  # Uses OPENROUTER_KEY from env
    
    try:
        # Fetch repository
        print("Fetching repository...")
        repo_content = await github_adapter.fetch_repository(repo_url, Role.FRONTEND)
        print(f"✓ Fetched {len(repo_content.files)} files")
        
        # Show actual files in repo
        print("\nActual files in repository:")
        for i, file in enumerate(repo_content.files[:5]):
            print(f"  - {file.path}")
        if len(repo_content.files) > 5:
            print(f"  ... and {len(repo_content.files) - 5} more files")
        
        # Read task requirements
        with open('data/task_requirements/frontend_task.md', 'r') as f:
            task_requirements = f.read()
        
        # Create analysis request
        request = AnalysisRequest(
            repository_content=repo_content,
            task_requirements=task_requirements,
            role=Role.FRONTEND,
            github_url=repo_url
        )
        
        # Analyze
        print("\nAnalyzing code...")
        result = await analyzer.analyze_code(request)
        
        if result:
            print("\n✓ Analysis completed successfully!")
            
            # Show requirements check
            print("\nRequirements Check:")
            for req, met in result.requirements_met.items():
                status = "✓" if met else "✗"
                print(f"  {status} {req}: {met}")
            
            # Show evidence validation
            if hasattr(result, 'penalty_breakdown') and result.penalty_breakdown:
                print("\nPenalties Found:")
                issues = result.penalty_breakdown.get('issues_found', [])
                for issue in issues[:3]:  # Show first 3
                    print(f"  - {issue.get('issue', 'Unknown')}")
                    print(f"    Evidence: {issue.get('evidence', 'None')}")
                if len(issues) > 3:
                    print(f"  ... and {len(issues) - 3} more issues")
                print(f"\nTotal Penalty: {result.penalty_breakdown.get('total_penalty', 0)} points")
            
            # Show decision
            print(f"\n📊 Final Decision: {result.recommendation}")
            print(f"Confidence: {result.confidence}")
            
            # Check for invalid references
            print("\n⚠️ Check logs for evidence validation warnings above")
            
        else:
            print("\n✗ Analysis failed - check logs above for details")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        await github_adapter.cleanup()

async def main():
    """Test multiple repositories to ensure unique analysis"""
    
    # Test repositories
    test_repos = [
        "https://github.com/mehransobhani/dekamond",        # repo1
        "https://github.com/behnamhsn/dekamond-auth-demo",  # repo2 - uses CSS modules, should be rejected
        "https://github.com/hoseingp/login-register",       # repo3
    ]
    
    for repo in test_repos:
        await test_repository_analysis(repo)
    
    print("\n" + "="*60)
    print("Testing complete! Check the analysis above:")
    print("1. Requirements should reflect ACTUAL code analysis")
    print("2. Evidence should reference ACTUAL files from the repo")
    print("3. No generic examples like 'file.ts:42' should appear")
    print("4. Check logs for evidence validation warnings")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())