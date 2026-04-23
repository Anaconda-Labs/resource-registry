#!/usr/bin/env python3
"""
Quality check script for Anaconda educational resources.
Checks README fields, environment files, and license against
the criteria defined in criteria_checker.
"""

import os
import sys
import re
from pathlib import Path


def check_readme(content: str, resource_type: str) -> list[str]:
    """Check README content against universal and type-specific criteria."""
    issues = []

    # Universal checks
    if not re.search(r'@[\w-]+', content):
        issues.append("No GitHub handle (@username) found for owner")

    if not re.search(
        r'(audience|who this is for|who should use|prerequisites|target)',
        content, re.IGNORECASE
    ):
        issues.append("No target audience section found")

    # Type-specific checks
    if resource_type == 'guide':
        if not re.search(
            r'(learning objectives?|you will (be able to|learn)|by the end)',
            content, re.IGNORECASE
        ):
            issues.append("Guide: No learning objectives found")
        if not re.search(r'\d+\s*(minute|hour|min)', content, re.IGNORECASE):
            issues.append("Guide: No time estimate found")
        if not re.search(r'(checkpoint|verify|confirm|expected output)', content, re.IGNORECASE):
            issues.append("Guide: No checkpoints or verification steps found")

    elif resource_type == 'show':
        if not re.search(
            r'(time|cost|risk|minute|hour|percent|%|faster|reduce|save)',
            content, re.IGNORECASE
        ):
            issues.append("Show: No business metrics (time/cost/risk) found")

    elif resource_type == 'tell':
        if not re.search(r'(next steps?|learn more|further reading)', content, re.IGNORECASE):
            issues.append("Tell: No 'next steps' or 'further reading' section found")

    return issues


def main():
    repo_path = Path(os.environ.get('REPO_PATH', '.'))
    resource_type = os.environ.get('RESOURCE_TYPE', 'show').lower().strip()

    print(f"\nRunning quality check (type: {resource_type})\n{'='*50}")
    all_issues = []

    # Check README exists and has content
    readme = repo_path / 'README.md'
    if not readme.exists():
        print("FAIL: README.md not found")
        sys.exit(1)

    readme_content = readme.read_text()
    if len(readme_content.strip()) < 200:
        print("FAIL: README.md appears to be nearly empty (< 200 characters)")
        sys.exit(1)

    readme_issues = check_readme(readme_content, resource_type)
    all_issues.extend(readme_issues)

    # Check environment file (accepts any *environment.yml pattern or pixi.toml)
    env_files = list(repo_path.glob('*environment.yml'))
    has_env = len(env_files) > 0 or (repo_path / 'pixi.toml').exists()
    if not has_env:
        all_issues.append("No *environment.yml or pixi.toml found")

    # Check LICENSE
    license_files = list(repo_path.glob('LICENSE*'))
    if not license_files:
        all_issues.append("No LICENSE file found")
    else:
        license_content = license_files[0].read_text()
        if 'MIT' not in license_content:
            all_issues.append("LICENSE does not appear to be MIT")

    # Report
    if all_issues:
        print(f"Quality check FAILED — {len(all_issues)} issue(s) found:\n")
        for issue in all_issues:
            print(f"  ✗ {issue}")
        print("\nRefer to https://github.com/Anaconda-Labs/criteria_checker for guidance.")
        sys.exit(1)
    else:
        print("All quality checks passed ✓")
        sys.exit(0)


if __name__ == '__main__':
    main()
