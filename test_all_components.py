#!/usr/bin/env python3
"""
Comprehensive test suite for all CV Review components.
Tests each component individually and saves results to markdown files.
"""

import asyncio
import json
import os
import sys
import shutil
from datetime import datetime
from pathlib import Path

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from adapters.repositories.github import GitHubAdapter
from adapters.analyzers.openrouter import OpenRouterAdapter
from adapters.storage.sqlite import SQLiteAdapter
from adapters.notifications.telegram import TelegramAdapter
from core.models import Role, Submission, SubmissionStatus, AnalysisRequest
from utils.prompts import load_prompt
from utils.validators import validate_github_url


class ComponentTester:
    def __init__(self):
        self.results_dir = Path("test_results")
        self.results_dir.mkdir(exist_ok=True)
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.test_url = "https://github.com/mohammad-hdr/auth-me-test-project"
        self.role = Role.FRONTEND
        
    def save_result(self, filename: str, content: str):
        """Save test result to markdown file."""
        filepath = self.results_dir / f"{self.timestamp}_{filename}"
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  ✓ Saved: {filepath}")
        return filepath
    
    async def test_1_url_validation(self):
        """Test 1: URL Validation"""
        print("\n" + "="*60)
        print("TEST 1: URL VALIDATION")
        print("="*60)
        
        test_urls = [
            ("https://github.com/user/repo", True),
            ("https://github.com/user/repo.git", True),
            ("https://gitlab.com/user/repo", False),
            ("not-a-url", False),
            ("", False),
        ]
        
        result = f"# URL Validation Test Results\n\n"
        result += f"**Timestamp:** {self.timestamp}\n\n"
        result += "## Test Cases\n\n"
        
        for url, expected in test_urls:
            is_valid, error_msg = validate_github_url(url)
            status = "✅" if (is_valid == expected) else "❌"
            result += f"- {status} `{url}`\n"
            result += f"  - Expected: {expected}\n"
            result += f"  - Got: {is_valid}\n"
            if error_msg:
                result += f"  - Error: {error_msg}\n"
            result += "\n"
        
        self.save_result("1_url_validation.md", result)
        print("✓ URL validation test completed")
        
    async def test_2_repository_structure(self):
        """Test 2: Fetch Repository Structure"""
        print("\n" + "="*60)
        print("TEST 2: REPOSITORY STRUCTURE FETCHING")
        print("="*60)
        
        adapter = GitHubAdapter()
        result = f"# Repository Structure Test\n\n"
        result += f"**Repository:** {self.test_url}\n"
        result += f"**Timestamp:** {self.timestamp}\n\n"
        
        try:
            # Clone repository
            import tempfile
            temp_dir = tempfile.mkdtemp(prefix='test_cv_')
            
            print(f"  Cloning to: {temp_dir}")
            from git import Repo
            repo = Repo.clone_from(self.test_url, temp_dir, depth=1)
            
            # Get repository structure
            structure = await adapter._get_repository_structure(temp_dir)
            
            result += "## Repository Statistics\n\n"
            result += f"- **Total Files:** {structure['total_files']}\n"
            result += f"- **Total Size:** {structure['total_size'] / (1024*1024):.2f} MB\n"
            result += f"- **Directories:** {len(structure['directories'])}\n\n"
            
            result += "## File List\n\n"
            result += "```\n"
            for file in sorted(structure['files'])[:50]:
                result += f"{file}\n"
            if len(structure['files']) > 50:
                result += f"\n... and {len(structure['files']) - 50} more files\n"
            result += "```\n\n"
            
            result += "## Directory Structure\n\n"
            result += "```\n"
            for dir_name in sorted(structure['directories'])[:30]:
                result += f"{dir_name}/\n"
            if len(structure['directories']) > 30:
                result += f"\n... and {len(structure['directories']) - 30} more directories\n"
            result += "```\n"
            
            # Clean up
            shutil.rmtree(temp_dir, ignore_errors=True)
            await adapter.cleanup()
            
        except Exception as e:
            result += f"\n## Error\n\n```\n{str(e)}\n```\n"
            import traceback
            result += f"\n## Traceback\n\n```\n{traceback.format_exc()}\n```\n"
        
        self.save_result("2_repository_structure.md", result)
        print("✓ Repository structure test completed")
        
    async def test_3_file_pattern_test(self):
        """Test 3: File Pattern Filtering"""
        print("\n" + "="*60)
        print("TEST 3: FILE PATTERN FILTERING")
        print("="*60)
        
        adapter = GitHubAdapter()
        result = f"# File Pattern Test\n\n"
        result += f"**Repository:** {self.test_url}\n"
        result += f"**Role:** {self.role.value}\n"
        result += f"**Timestamp:** {self.timestamp}\n\n"
        
        try:
            # Get repository structure
            import tempfile
            temp_dir = tempfile.mkdtemp(prefix='test_cv_')
            from git import Repo
            repo = Repo.clone_from(self.test_url, temp_dir, depth=1)
            
            structure = await adapter._get_repository_structure(temp_dir)
            
            result += "## Repository Structure\n\n"
            result += f"- **Total Files:** {structure['total_files']}\n"
            result += f"- **Total Size:** {structure['total_size'] / (1024*1024):.2f} MB\n\n"
            
            # Get file patterns for the role
            patterns = adapter.get_file_patterns(self.role)
            
            result += "## File Patterns Applied\n\n"
            result += f"### Excluded Patterns ({len(patterns.get('exclude', []))}):\n"
            for pattern in patterns.get('exclude', [])[:10]:
                result += f"- `{pattern}`\n"
            
            result += f"\n### Included Patterns:\n"
            result += f"- Critical: {patterns.get('critical', ['**/*'])}\n"
            
            # Extract files using patterns
            files = adapter._extract_files(temp_dir, self.role)
            
            result += f"\n## Files After Filtering\n\n"
            result += f"- **Total Files Selected:** {len(files)}\n"
            result += f"- **Files Excluded:** {structure['total_files'] - len(files)}\n\n"
            
            result += "### Selected Files:\n"
            for i, file in enumerate(files[:20], 1):
                result += f"{i}. `{file.path}` ({file.tokens} tokens)\n"
            
            if len(files) > 20:
                result += f"\n... and {len(files) - 20} more files\n"
            
            # Clean up
            shutil.rmtree(temp_dir, ignore_errors=True)
            await adapter.cleanup()
            
        except Exception as e:
            result += f"\n## Error\n\n```\n{str(e)}\n```\n"
            import traceback
            result += f"\n## Traceback\n\n```\n{traceback.format_exc()}\n```\n"
        
        self.save_result("3_file_pattern_test.md", result)
        print("✓ File pattern test completed")
    
    async def test_4_fetch_files(self):
        """Test 4: Fetch Selected Files"""
        print("\n" + "="*60)
        print("TEST 4: FETCH SELECTED FILES")
        print("="*60)
        
        adapter = GitHubAdapter()
        result = f"# File Fetching Test\n\n"
        result += f"**Repository:** {self.test_url}\n"
        result += f"**Role:** {self.role.value}\n"
        result += f"**Timestamp:** {self.timestamp}\n\n"
        
        try:
            # Fetch repository with all files
            repo_content = await adapter.fetch_repository(self.test_url, self.role)
            
            result += "## Fetch Statistics\n\n"
            result += f"- **Files Fetched:** {len(repo_content.files)}\n"
            result += f"- **Total Tokens:** {repo_content.total_tokens}\n"
            result += f"- **Repository URL:** {repo_content.url}\n\n"
            
            result += "## Files by Priority\n\n"
            critical = [f for f in repo_content.files if f.priority == 'critical']
            important = [f for f in repo_content.files if f.priority == 'important']
            useful = [f for f in repo_content.files if f.priority == 'useful']
            
            result += f"- **Critical:** {len(critical)} files\n"
            result += f"- **Important:** {len(important)} files\n"
            result += f"- **Useful:** {len(useful)} files\n\n"
            
            result += "## Files List\n\n"
            for i, file in enumerate(repo_content.files, 1):
                result += f"{i}. `{file.path}` ({file.priority})\n"
                result += f"   - Language: {file.language or 'unknown'}\n"
                result += f"   - Tokens: {file.tokens}\n"
                result += f"   - Size: {len(file.content)} chars\n\n"
                
                if i <= 3:  # Show first 3 files' content preview
                    result += f"   <details>\n   <summary>Content preview</summary>\n\n   ```{file.language or ''}\n"
                    result += file.content[:500]
                    if len(file.content) > 500:
                        result += f"\n   ... truncated ({len(file.content)} total chars)\n"
                    result += "   ```\n   </details>\n\n"
            
            # Clean up
            await adapter.cleanup()
            
        except Exception as e:
            result += f"\n## Error\n\n```\n{str(e)}\n```\n"
            import traceback
            result += f"\n## Traceback\n\n```\n{traceback.format_exc()}\n```\n"
        
        self.save_result("4_fetch_files.md", result)
        print("✓ File fetching test completed")
    
    async def test_5_analysis_prompt(self):
        """Test 5: Build Analysis Prompt"""
        print("\n" + "="*60)
        print("TEST 5: ANALYSIS PROMPT BUILDING")
        print("="*60)
        
        result = f"# Analysis Prompt Test\n\n"
        result += f"**Repository:** {self.test_url}\n"
        result += f"**Role:** {self.role.value}\n"
        result += f"**Timestamp:** {self.timestamp}\n\n"
        
        try:
            # Fetch repository
            adapter = GitHubAdapter()
            repo_content = await adapter.fetch_repository(self.test_url, self.role)
            
            # Load task requirements
            task_file = f"data/task_requirements/{self.role.value}_task.md"
            with open(task_file, 'r') as f:
                task_requirements = f.read()
            
            result += "## Task Requirements\n\n"
            result += "```markdown\n"
            result += task_requirements[:1500]
            if len(task_requirements) > 1500:
                result += f"\n... truncated ({len(task_requirements)} total chars)\n"
            result += "```\n\n"
            
            # Build the analysis request
            analysis_request = AnalysisRequest(
                repository_content=repo_content,
                role=self.role,
                task_requirements=task_requirements,
                github_url=self.test_url,
                submission_id=1
            )
            
            # Prepare content for analysis
            analyzer = OpenRouterAdapter()
            content_parts = []
            for file in repo_content.files[:20]:  # Limit for testing
                content_parts.append(f"### File: {file.path}\n```{file.language or ''}\n{file.content}\n```\n")
            content = "\n---\n".join(content_parts)
            
            # Build the prompt
            try:
                prompt = load_prompt(
                    "analysis/code_review.md",
                    role=analysis_request.role.value,
                    task_requirements=analysis_request.task_requirements,
                    github_url=analysis_request.github_url,
                    file_count=len(repo_content.files),
                    total_tokens=repo_content.total_tokens,
                    code_content=content[:10000]  # Limit for display
                )
                
                result += "## Analysis Prompt\n\n"
                result += "<details>\n<summary>Click to expand full prompt</summary>\n\n"
                result += "```markdown\n"
                result += prompt[:8000]
                if len(prompt) > 8000:
                    result += f"\n... truncated ({len(prompt)} total chars)\n"
                result += "```\n</details>\n\n"
                
            except Exception as e:
                result += f"## Prompt Building Error\n\n```\n{str(e)}\n```\n"
            
            result += "## Content Statistics\n\n"
            result += f"- **Files Included:** {len(repo_content.files)}\n"
            result += f"- **Total Content Size:** {sum(len(f.content) for f in repo_content.files)} chars\n"
            result += f"- **Estimated Tokens:** {repo_content.total_tokens}\n"
            
            # Clean up
            await adapter.cleanup()
            
        except Exception as e:
            result += f"\n## Error\n\n```\n{str(e)}\n```\n"
            import traceback
            result += f"\n## Traceback\n\n```\n{traceback.format_exc()}\n```\n"
        
        self.save_result("5_analysis_prompt.md", result)
        print("✓ Analysis prompt test completed")
    
    async def test_6_llm_analysis(self):
        """Test 6: LLM Code Analysis"""
        print("\n" + "="*60)
        print("TEST 6: LLM CODE ANALYSIS")
        print("="*60)
        
        result = f"# LLM Analysis Test\n\n"
        result += f"**Repository:** {self.test_url}\n"
        result += f"**Role:** {self.role.value}\n"
        result += f"**Timestamp:** {self.timestamp}\n\n"
        
        try:
            # Fetch repository
            adapter = GitHubAdapter()
            repo_content = await adapter.fetch_repository(self.test_url, self.role)
            
            # Load task requirements
            task_file = f"data/task_requirements/{self.role.value}_task.md"
            with open(task_file, 'r') as f:
                task_requirements = f.read()
            
            # Create analysis request
            analysis_request = AnalysisRequest(
                repository_content=repo_content,
                role=self.role,
                task_requirements=task_requirements,
                github_url=self.test_url,
                submission_id=1
            )
            
            # Perform analysis
            print("  Calling LLM for code analysis...")
            analyzer = OpenRouterAdapter()
            analysis_result = await analyzer.analyze_code(analysis_request)
            
            result += "## Analysis Result\n\n"
            
            if analysis_result:
                result += "### Scores\n\n"
                for metric, score in analysis_result.scores.items():
                    result += f"- **{metric.title()}:** {score}/100\n"
                result += f"- **Overall:** {analysis_result.get_overall_score():.1f}/100\n\n"
                
                result += f"### Recommendation\n\n"
                result += f"**{analysis_result.recommendation.value.upper()}** (Confidence: {analysis_result.confidence:.0%})\n\n"
                
                result += "### Strengths\n\n"
                for strength in analysis_result.strengths[:5]:
                    result += f"- {strength}\n"
                result += "\n"
                
                result += "### Weaknesses\n\n"
                for weakness in analysis_result.weaknesses[:5]:
                    result += f"- {weakness}\n"
                result += "\n"
                
                result += "### Requirements Met\n\n"
                for req, met in list(analysis_result.requirements_met.items())[:10]:
                    status = "✅" if met else "❌"
                    result += f"- {status} {req}\n"
                result += "\n"
                
                result += "### Detailed Feedback\n\n"
                result += analysis_result.detailed_feedback[:2000]
                if len(analysis_result.detailed_feedback) > 2000:
                    result += f"\n\n... truncated ({len(analysis_result.detailed_feedback)} total chars)\n"
                
                # Save raw JSON response
                raw_result = analysis_result.to_dict()
                raw_json = json.dumps(raw_result, indent=2)
                self.save_result("6b_analysis_raw.json", raw_json)
                
            else:
                result += "**Analysis failed - no result returned**\n"
            
            # Clean up
            await adapter.cleanup()
            
        except Exception as e:
            result += f"\n## Error\n\n```\n{str(e)}\n```\n"
            import traceback
            result += f"\n## Traceback\n\n```\n{traceback.format_exc()}\n```\n"
        
        self.save_result("6_llm_analysis.md", result)
        print("✓ LLM analysis test completed")
    
    async def test_7_database_operations(self):
        """Test 7: Database Operations"""
        print("\n" + "="*60)
        print("TEST 7: DATABASE OPERATIONS")
        print("="*60)
        
        result = f"# Database Operations Test\n\n"
        result += f"**Timestamp:** {self.timestamp}\n\n"
        
        try:
            storage = SQLiteAdapter()
            await storage.initialize()
            
            # Create a test submission
            submission = Submission(
                telegram_user_id="test_user_123",
                telegram_username="test_user",
                github_url=self.test_url,
                role=self.role,
                status=SubmissionStatus.PENDING
            )
            
            result += "## Create Submission\n\n"
            created = await storage.create_submission(submission)
            result += f"- **ID:** {created.id}\n"
            result += f"- **Status:** {created.status.value}\n"
            result += f"- **Created At:** {created.created_at}\n\n"
            
            # Update submission
            result += "## Update Submission\n\n"
            updated = await storage.update_submission(
                created.id,
                status=SubmissionStatus.ANALYZING
            )
            result += f"- **Updated:** {updated}\n"
            result += f"- **New Status:** ANALYZING\n\n"
            
            # Get submission
            result += "## Retrieve Submission\n\n"
            retrieved = await storage.get_submission(created.id)
            if retrieved:
                result += f"- **ID:** {retrieved.id}\n"
                result += f"- **URL:** {retrieved.github_url}\n"
                result += f"- **Status:** {retrieved.status.value}\n\n"
            
            # Get statistics
            result += "## Database Statistics\n\n"
            stats = await storage.get_statistics()
            result += "```json\n"
            result += json.dumps(stats, indent=2)
            result += "\n```\n\n"
            
            # Get pending submissions
            result += "## Pending Submissions\n\n"
            pending = await storage.get_pending_submissions()
            result += f"Found {len(pending)} pending submissions\n\n"
            for sub in pending:
                result += f"- ID: {sub.id}, Status: {sub.status.value}, URL: {sub.github_url}\n"
            
        except Exception as e:
            result += f"\n## Error\n\n```\n{str(e)}\n```\n"
            import traceback
            result += f"\n## Traceback\n\n```\n{traceback.format_exc()}\n```\n"
        
        self.save_result("7_database_operations.md", result)
        print("✓ Database operations test completed")
    
    async def run_all_tests(self):
        """Run all component tests."""
        print("\n" + "="*60)
        print("CV REVIEW SYSTEM - COMPREHENSIVE COMPONENT TESTING")
        print("="*60)
        print(f"Timestamp: {self.timestamp}")
        print(f"Results will be saved to: {self.results_dir}/")
        
        # Run tests
        await self.test_1_url_validation()
        await self.test_2_repository_structure()
        await self.test_3_file_pattern_test()
        await self.test_4_fetch_files()
        await self.test_5_analysis_prompt()
        await self.test_6_llm_analysis()
        await self.test_7_database_operations()
        
        # Create summary
        summary = f"# Test Suite Summary\n\n"
        summary += f"**Timestamp:** {self.timestamp}\n"
        summary += f"**Repository Tested:** {self.test_url}\n"
        summary += f"**Role:** {self.role.value}\n\n"
        summary += "## Tests Executed\n\n"
        summary += "1. ✅ URL Validation\n"
        summary += "2. ✅ Repository Structure Fetching\n"
        summary += "3. ✅ File Pattern Filtering\n"
        summary += "4. ✅ File Fetching\n"
        summary += "5. ✅ Analysis Prompt Building\n"
        summary += "6. ✅ LLM Code Analysis\n"
        summary += "7. ✅ Database Operations\n\n"
        summary += "## Results Files\n\n"
        
        for file in sorted(self.results_dir.glob(f"{self.timestamp}_*.md")):
            summary += f"- `{file.name}`\n"
        
        self.save_result("0_summary.md", summary)
        
        print("\n" + "="*60)
        print("ALL TESTS COMPLETED!")
        print(f"Results saved to: {self.results_dir}/")
        print("="*60)


if __name__ == "__main__":
    tester = ComponentTester()
    asyncio.run(tester.run_all_tests())