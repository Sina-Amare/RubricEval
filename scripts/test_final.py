#!/usr/bin/env python
"""Quick test to verify the fixes"""

import asyncio
import sys
sys.path.insert(0, 'src')

from adapters.repositories.github import GitHubAdapter
from adapters.analyzers.openrouter import OpenRouterAdapter
from core.models import AnalysisRequest, Role

async def test_repo():
    """Test a repository to check the fixes"""
    github = GitHubAdapter()
    analyzer = OpenRouterAdapter()
    
    # Test repo1 which has ~50-60 penalty points
    repo_url = "https://github.com/mehransobhani/dekamond"
    
    print(f"Testing: {repo_url}")
    print("=" * 60)
    
    # Fetch repository
    repo_content = await github.fetch_repository(repo_url, Role.FRONTEND)
    print(f"✓ Fetched {len(repo_content.files)} files")
    
    # Load task requirements
    with open('data/task_requirements/frontend_task.md', 'r') as f:
        task_req = f.read()
    
    # Create analysis request
    request = AnalysisRequest(
        repository_content=repo_content,
        task_requirements=task_req,
        role=Role.FRONTEND,
        github_url=repo_url
    )
    
    # Analyze
    result = await analyzer.analyze_code(request)
    
    # Check penalty
    if result.penalty_breakdown:
        total_penalty = result.penalty_breakdown.get('total_penalty', 0)
        print(f"\nTotal Penalty: {total_penalty} points")
        if total_penalty > 60:
            print("  → Should show AUTO-REJECT THRESHOLD")
        else:
            print("  → Should NOT show AUTO-REJECT THRESHOLD")
    
    # Check architecture
    if result.architecture_analysis:
        client_ok = result.architecture_analysis.get('client_components_well_structured', 
                    result.architecture_analysis.get('server_client_boundaries_correct', False))
        print(f"\nClient Components: {'✅ Well-structured' if client_ok else '❌ Needs improvement'}")
    
    print(f"\nDecision: {result.recommendation}")
    print(f"Requirements met: {sum(1 for v in result.requirements_met.values() if v)}/{len(result.requirements_met)}")
    
    # Cleanup
    await github.cleanup()

if __name__ == "__main__":
    asyncio.run(test_repo())