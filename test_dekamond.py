#!/usr/bin/env python3
"""
Test script to analyze the dekamond repository directly
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from adapters.repositories.github import GitHubAdapter
from adapters.analyzers.openrouter import OpenRouterAdapter
from core.models import AnalysisRequest, Role

async def test_dekamond():
    """Test the dekamond repository analysis"""
    print("=" * 60)
    print("Testing dekamond repository analysis")
    print("=" * 60)
    
    # Initialize adapters
    github = GitHubAdapter()
    analyzer = OpenRouterAdapter()
    
    try:
        # Fetch repository
        print("\n1. Fetching repository...")
        repo_content = await github.fetch_repository(
            "https://github.com/mehransobhani/dekamond",
            role=Role.FRONTEND
        )
        print(f"   - Files: {len(repo_content.files)}")
        print(f"   - Total tokens: {repo_content.total_tokens}")
        
        # Load task requirements
        task_req_path = os.path.join(
            os.path.dirname(__file__), 
            "data/task_requirements/frontend_task.md"
        )
        with open(task_req_path, 'r') as f:
            task_requirements = f.read()
        
        # Create analysis request
        print("\n2. Creating analysis request...")
        request = AnalysisRequest(
            repository_content=repo_content,
            task_requirements=task_requirements,
            role=Role.FRONTEND,
            github_url="https://github.com/mehransobhani/dekamond"
        )
        
        # Analyze
        print("\n3. Analyzing code...")
        result = await analyzer.analyze_code(request)
        
        # Show results
        print("\n" + "=" * 60)
        print("ANALYSIS RESULTS")
        print("=" * 60)
        
        print(f"\n📊 Recommendation: {result.recommendation.value}")
        print(f"🎯 Overall Score: {result.scores.get('overall', result.get_overall_score())}%")
        print(f"🔍 Confidence: {result.confidence:.0%}")
        
        print("\n📋 Requirements Met:")
        for req, met in result.requirements_met.items():
            status = "✅" if met else "❌"
            print(f"  {status} {req}")
        
        print("\n⚠️ Penalties:")
        print(f"  Total Penalty: {result.penalty_breakdown.total_penalty} points")
        if result.penalty_breakdown.issues_found:
            for issue in result.penalty_breakdown.issues_found[:5]:  # Show first 5
                print(f"  - {issue.issue} ({issue.penalty} points)")
        
        print("\n✅ Strengths:")
        for strength in result.strengths[:3]:
            print(f"  • {strength}")
        
        print("\n❌ Weaknesses:")
        for weakness in result.weaknesses[:3]:
            print(f"  • {weakness}")
        
        # Final decision
        print("\n" + "=" * 60)
        if result.recommendation.value in ["yes", "strong_yes"]:
            print("✅ CANDIDATE WOULD BE HIRED")
        else:
            print("❌ CANDIDATE WOULD BE REJECTED")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error during analysis: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        await github.cleanup()

if __name__ == "__main__":
    asyncio.run(test_dekamond())