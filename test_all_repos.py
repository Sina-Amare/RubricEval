#!/usr/bin/env python3
"""
Test all three repositories with detailed analysis
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from adapters.repositories.github import GitHubAdapter
from adapters.analyzers.openrouter import OpenRouterAdapter
from core.models import AnalysisRequest, Role

async def analyze_repo(url, name):
    """Analyze a single repository"""
    print(f"\n{'='*60}")
    print(f"🔍 ANALYZING: {name}")
    print(f"URL: {url}")
    print(f"{'='*60}")
    
    # Initialize adapters
    github = GitHubAdapter()
    analyzer = OpenRouterAdapter()
    
    try:
        # Fetch repository
        print(f"📦 Fetching repository...")
        repo_content = await github.fetch_repository(url, role=Role.FRONTEND)
        print(f"✅ Files: {len(repo_content.files)}")
        print(f"✅ Tokens: {repo_content.total_tokens}")
        
        # Load task requirements
        with open("data/task_requirements/frontend_task.md", 'r') as f:
            task_requirements = f.read()
        
        # Create and execute analysis
        request = AnalysisRequest(
            repository_content=repo_content,
            task_requirements=task_requirements,
            role=Role.FRONTEND,
            github_url=url
        )
        
        print(f"🤖 Running LLM analysis...")
        result = await analyzer.analyze_code(request)
        
        # Display results
        print(f"\n📊 RESULTS:")
        print(f"  Decision: {result.recommendation.value.upper()}")
        print(f"  Confidence: {result.confidence:.0%}")
        
        # Check all requirements
        all_met = all(result.requirements_met.values())
        print(f"  All Requirements Met: {'✅ YES' if all_met else '❌ NO'}")
        
        # Show which requirements failed
        if not all_met:
            print(f"\n  Failed Requirements:")
            for req, met in result.requirements_met.items():
                if not met:
                    print(f"    ❌ {req}")
        
        # Penalty info
        penalty = 0
        if hasattr(result, 'penalty_breakdown'):
            if isinstance(result.penalty_breakdown, dict):
                penalty = result.penalty_breakdown.get('total_penalty', 0)
            else:
                penalty = getattr(result.penalty_breakdown, 'total_penalty', 0)
        print(f"  Penalty Points: {penalty}/60")
        
        # Final verdict
        print(f"\n  🎯 FINAL: ", end="")
        if result.recommendation.value in ["accept", "strong_accept", "yes", "strong_yes"]:
            print("✅ HIRE")
        else:
            print("❌ REJECT")
            
        # Show top issues if any
        if penalty > 0 and hasattr(result, 'penalty_breakdown'):
            pb = result.penalty_breakdown
            if isinstance(pb, dict) and 'issues_found' in pb:
                issues = pb['issues_found'][:3]  # Top 3 issues
                if issues:
                    print(f"\n  Top Issues:")
                    for issue in issues:
                        if isinstance(issue, dict):
                            print(f"    • {issue.get('issue', 'Unknown')} ({issue.get('penalty', 0)} pts)")
        
        return {
            'url': url,
            'name': name,
            'decision': result.recommendation.value,
            'confidence': result.confidence,
            'all_requirements_met': all_met,
            'penalty': penalty,
            'hired': result.recommendation.value in ["accept", "strong_accept", "yes", "strong_yes"]
        }
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return {
            'url': url,
            'name': name,
            'error': str(e)
        }
    finally:
        await github.cleanup()

async def main():
    """Test all three repositories"""
    repos = [
        ("https://github.com/mehransobhani/dekamond", "mehransobhani/dekamond"),
        ("https://github.com/behnamhsn/dekamond-auth-demo", "behnamhsn/dekamond-auth-demo"),
        ("https://github.com/Talkhestani/digitaldekamond", "Talkhestani/digitaldekamond")
    ]
    
    results = []
    for url, name in repos:
        result = await analyze_repo(url, name)
        results.append(result)
        print("\n" + "="*60)
    
    # Summary
    print("\n" + "="*60)
    print("📈 SUMMARY OF ALL REPOSITORIES")
    print("="*60)
    
    for r in results:
        if 'error' in r:
            print(f"\n{r['name']}: ❌ ERROR - {r['error']}")
        else:
            status = "✅ HIRED" if r['hired'] else "❌ REJECTED"
            print(f"\n{r['name']}:")
            print(f"  Status: {status}")
            print(f"  Requirements: {'✅ All Met' if r['all_requirements_met'] else '❌ Some Missing'}")
            print(f"  Penalty: {r['penalty']}/60")
            print(f"  Confidence: {r['confidence']:.0%}")
    
    print("\n" + "="*60)
    print("✅ ANALYSIS COMPLETE")
    print("="*60)

if __name__ == "__main__":
    import logging
    # Only show warnings and errors
    logging.basicConfig(level=logging.WARNING, format='%(message)s')
    asyncio.run(main())