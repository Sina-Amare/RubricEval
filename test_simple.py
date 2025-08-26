#!/usr/bin/env python3
"""
Simple test to verify dekamond repository gets accepted
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from adapters.repositories.github import GitHubAdapter
from adapters.analyzers.openrouter import OpenRouterAdapter
from core.models import AnalysisRequest, Role

async def test():
    # Initialize adapters
    github = GitHubAdapter()
    analyzer = OpenRouterAdapter()
    
    # Fetch repository
    repo_content = await github.fetch_repository(
        "https://github.com/mehransobhani/dekamond",
        role=Role.FRONTEND
    )
    print(f"✅ Repository fetched: {len(repo_content.files)} files")
    
    # Load task requirements
    with open("data/task_requirements/frontend_task.md", 'r') as f:
        task_requirements = f.read()
    
    # Create analysis request
    request = AnalysisRequest(
        repository_content=repo_content,
        task_requirements=task_requirements,
        role=Role.FRONTEND,
        github_url="https://github.com/mehransobhani/dekamond"
    )
    
    # Analyze
    result = await analyzer.analyze_code(request)
    
    # Show results
    print("\n" + "=" * 60)
    print("🎉 FINAL RESULT FOR mehransobhani/dekamond")
    print("=" * 60)
    print(f"📊 Decision: {result.recommendation.value.upper()}")
    print(f"🔍 Confidence: {result.confidence:.0%}")
    print(f"✅ All 11 requirements met: {all(result.requirements_met.values())}")
    
    # Show penalty info if available
    try:
        if hasattr(result, 'penalty_breakdown'):
            penalty = result.penalty_breakdown.get('total_penalty', 0)
            print(f"⚠️ Total penalty: {penalty} points (threshold: 60)")
    except:
        pass
    
    if result.recommendation.value in ["accept", "strong_accept", "yes", "strong_yes"]:
        print("\n✅ CANDIDATE HIRED! 🎉")
    else:
        print("\n❌ CANDIDATE REJECTED")
    print("=" * 60)
    
    await github.cleanup()

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.ERROR)  # Suppress info logs
    asyncio.run(test())