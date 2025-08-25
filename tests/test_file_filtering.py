#!/usr/bin/env python3
"""Test file filtering for backend repository."""

import asyncio
import sys
import os
import json
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from adapters.repositories.github import GitHubAdapter
from core.models import Role
import shutil

async def test_repo_filtering():
    """Test the repository filtering process."""
    
    repo_url = "https://github.com/mobinadavid/go-auth-otp-service"
    role = Role.BACKEND
    
    print(f"Testing repository: {repo_url}")
    print(f"Role: {role.value}")
    print("=" * 60)
    
    # Initialize the adapter
    adapter = GitHubAdapter()
    
    try:
        # Clone the repository
        print("\n1. Cloning repository...")
        import tempfile
        temp_dir = tempfile.mkdtemp(prefix="cv_review_test_")
        repo = await adapter._clone_repository(repo_url, temp_dir)
        clone_dir = repo.working_dir  # Get the actual directory path
        print(f"   Repository cloned to: {clone_dir}")
        
        # Get ALL files in the repository
        print("\n2. Getting all files in repository...")
        all_files = []
        for root, dirs, files in os.walk(clone_dir):
            # Skip .git directory
            dirs[:] = [d for d in dirs if d != '.git']
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, clone_dir)
                # Get file size
                file_size = os.path.getsize(file_path)
                all_files.append({
                    'path': rel_path,
                    'size': file_size,
                    'extension': Path(file).suffix
                })
        
        print(f"   Total files found: {len(all_files)}")
        
        # Now run the filtering process
        print("\n3. Running file filtering process...")
        result = await adapter.fetch_repository(repo_url, role)
        
        # Get filtered files
        filtered_files = []
        for file_obj in result.files:
            # Determine priority
            if hasattr(file_obj, 'priority'):
                if hasattr(file_obj.priority, 'value'):
                    priority = file_obj.priority.value
                else:
                    priority = str(file_obj.priority)
            else:
                priority = 'unknown'
            
            filtered_files.append({
                'path': file_obj.path,
                'size': len(file_obj.content.encode('utf-8')) if file_obj.content else 0,
                'priority': priority
            })
        
        print(f"   Filtered files: {len(filtered_files)}")
        print(f"   Total tokens: {result.total_tokens}")
        
        # Save full list to file
        print("\n4. Saving full file list...")
        with open('backend_repo_all_files.json', 'w') as f:
            json.dump({
                'repository': repo_url,
                'role': role.value,
                'total_files': len(all_files),
                'files': sorted(all_files, key=lambda x: x['path'])
            }, f, indent=2)
        print("   Saved to: backend_repo_all_files.json")
        
        # Save filtered list to file
        print("\n5. Saving filtered file list...")
        with open('backend_repo_filtered_files.json', 'w') as f:
            json.dump({
                'repository': repo_url,
                'role': role.value,
                'total_files': len(filtered_files),
                'total_tokens': result.total_tokens,
                'files': sorted(filtered_files, key=lambda x: x['path'])
            }, f, indent=2)
        print("   Saved to: backend_repo_filtered_files.json")
        
        # Analyze what was filtered out
        print("\n6. Analysis:")
        print("=" * 60)
        
        filtered_paths = {f['path'] for f in filtered_files}
        excluded_files = [f for f in all_files if f['path'] not in filtered_paths]
        
        print(f"Total files in repo: {len(all_files)}")
        print(f"Files after filtering: {len(filtered_files)}")
        print(f"Files excluded: {len(excluded_files)}")
        print(f"Retention rate: {len(filtered_files)/len(all_files)*100:.1f}%")
        
        # Group excluded files by extension
        excluded_by_ext = {}
        for f in excluded_files:
            ext = f['extension'] or 'no_extension'
            if ext not in excluded_by_ext:
                excluded_by_ext[ext] = []
            excluded_by_ext[ext].append(f['path'])
        
        print("\nExcluded files by extension:")
        for ext, paths in sorted(excluded_by_ext.items()):
            print(f"  {ext}: {len(paths)} files")
            if len(paths) <= 5:
                for p in paths:
                    print(f"    - {p}")
            else:
                for p in paths[:3]:
                    print(f"    - {p}")
                print(f"    ... and {len(paths)-3} more")
        
        # Group included files by priority
        included_by_priority = {}
        for f in filtered_files:
            priority = f.get('priority', 'unknown')
            if priority not in included_by_priority:
                included_by_priority[priority] = []
            included_by_priority[priority].append(f['path'])
        
        print("\nIncluded files by priority:")
        for priority, paths in sorted(included_by_priority.items()):
            print(f"  {priority}: {len(paths)} files")
            if len(paths) <= 5:
                for p in paths:
                    print(f"    - {p}")
            else:
                for p in paths[:3]:
                    print(f"    - {p}")
                print(f"    ... and {len(paths)-3} more")
        
        # Check for important Go files
        print("\nChecking for important Go backend files:")
        important_patterns = [
            'main.go',
            'go.mod',
            'go.sum',
            'Dockerfile',
            'docker-compose',
            '.env',
            'Makefile',
            'README',
            'handler',
            'controller',
            'service',
            'repository',
            'model',
            'middleware',
            'auth',
            'config',
            'database',
            'migration'
        ]
        
        for pattern in important_patterns:
            matching_all = [f['path'] for f in all_files if pattern.lower() in f['path'].lower()]
            matching_filtered = [f['path'] for f in filtered_files if pattern.lower() in f['path'].lower()]
            
            if matching_all:
                status = "✅" if matching_filtered else "❌"
                print(f"  {status} {pattern}: {len(matching_filtered)}/{len(matching_all)} included")
                if matching_all and not matching_filtered:
                    print(f"     Missing: {', '.join(matching_all[:3])}")
        
        print("\n" + "=" * 60)
        print("Test complete! Check the generated JSON files:")
        print("  - backend_repo_all_files.json (all files)")
        print("  - backend_repo_filtered_files.json (filtered files)")
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        await adapter.cleanup()

if __name__ == "__main__":
    asyncio.run(test_repo_filtering())