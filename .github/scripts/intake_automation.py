#!/usr/bin/env python3
"""
Intake automation script for Anaconda-Labs resource lifecycle system.
Handles repo transfer, workflow setup, and initial configuration when new resources are added to registry.yml.
"""

import os
import sys
import yaml
import requests
import base64
import json
import time
from datetime import datetime, timedelta
from pathlib import Path


# Configuration from environment
INTAKE_TOKEN = os.environ.get('INTAKE_TOKEN')
BASE_SHA = os.environ.get('BASE_SHA')
HEAD_SHA = os.environ.get('HEAD_SHA')
TARGET_ORG = os.environ.get('TARGET_ORG', 'Anaconda-Labs')
REGISTRY_OWNER = os.environ.get('REGISTRY_OWNER', 'Anaconda-Labs')
REGISTRY_REPO = os.environ.get('REGISTRY_REPO', 'resource-registry')

HEADERS = {
    'Authorization': f'token {INTAKE_TOKEN}',
    'Accept': 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28',
}

# Results tracking
results = {
    'success': True,
    'processed': [],
    'error': None
}


def log(message):
    """Print timestamped log message."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")


def get_file_at_sha(sha, path='registry.yml'):
    """Get file content at a specific commit SHA."""
    url = f'https://api.github.com/repos/{REGISTRY_OWNER}/{REGISTRY_REPO}/contents/{path}?ref={sha}'
    r = requests.get(url, headers=HEADERS)
    if r.status_code == 200:
        content = base64.b64decode(r.json()['content']).decode('utf-8')
        return yaml.safe_load(content)
    else:
        log(f"Warning: Could not fetch {path} at {sha}: {r.status_code}")
        return None


def detect_new_resources():
    """Compare base and head versions of registry.yml to find new resources."""
    log("Detecting new resources...")

    base_data = get_file_at_sha(BASE_SHA)
    head_data = get_file_at_sha(HEAD_SHA)

    if not base_data or not head_data:
        return []

    base_repos = {r['repo'] for r in base_data.get('resources', [])}
    head_repos = {r['repo'] for r in head_data.get('resources', [])}

    new_repo_names = head_repos - base_repos

    if not new_repo_names:
        log("No new resources detected")
        return []

    log(f"Found {len(new_repo_names)} new resource(s): {', '.join(new_repo_names)}")

    # Get full resource objects
    new_resources = [r for r in head_data['resources'] if r['repo'] in new_repo_names]
    return new_resources


def transfer_repository(repo_name, source_org='Anaconda-Sandbox'):
    """Transfer repository from source org to target org."""
    log(f"Transferring {source_org}/{repo_name} → {TARGET_ORG}/{repo_name}")

    url = f'https://api.github.com/repos/{source_org}/{repo_name}/transfer'
    response = requests.post(
        url,
        headers=HEADERS,
        json={'new_owner': TARGET_ORG}
    )

    if response.status_code == 202:
        log(f"Transfer initiated successfully (202 Accepted)")
        # Transfer is async - wait for it to complete
        log("Waiting 15 seconds for transfer to complete...")
        time.sleep(15)
        return True
    else:
        log(f"Transfer failed: {response.status_code} - {response.text}")
        return False


def load_template(template_name):
    """Load a workflow template file."""
    template_path = Path('.github/resource-templates') / template_name
    if template_path.exists():
        return template_path.read_text()
    else:
        log(f"Warning: Template {template_name} not found")
        return None


def create_file_in_repo(org, repo, path, content, message):
    """Create or update a file in the repository."""
    url = f'https://api.github.com/repos/{org}/{repo}/contents/{path}'

    # Check if file exists (need SHA to update)
    check_response = requests.get(url, headers=HEADERS)

    encoded_content = base64.b64encode(content.encode()).decode()

    data = {
        'message': message,
        'content': encoded_content,
    }

    if check_response.status_code == 200:
        # File exists, need SHA to update
        data['sha'] = check_response.json()['sha']

    response = requests.put(url, headers=HEADERS, json=data)

    if response.status_code in (200, 201):
        log(f"Created/updated {path}")
        return True
    else:
        log(f"Failed to create {path}: {response.status_code} - {response.text}")
        return False


def setup_workflows(org, repo, resource_type):
    """Create workflow files in the transferred repository."""
    log(f"Setting up workflows for {org}/{repo}")

    success = True

    # Load and customize quality-check.yml
    quality_template = load_template('quality-check.yml')
    if quality_template:
        # Customize resource type
        quality_content = quality_template.replace('resource_type: show', f'resource_type: {resource_type}')
        success &= create_file_in_repo(
            org, repo,
            '.github/workflows/quality-check.yml',
            quality_content,
            'chore: add quality check workflow from intake automation'
        )
    else:
        success = False

    # Load update-status.yml (no customization needed)
    status_template = load_template('update-status.yml')
    if status_template:
        success &= create_file_in_repo(
            org, repo,
            '.github/workflows/update-status.yml',
            status_template,
            'chore: add owner certification workflow from intake automation'
        )
    else:
        success = False

    # Create badge JSON
    badge_template = load_template('status.json')
    if badge_template:
        success &= create_file_in_repo(
            org, repo,
            '.github/badges/status.json',
            badge_template,
            'chore: add lifecycle status badge'
        )
    else:
        success = False

    return success


def add_badge_to_readme(org, repo):
    """Prepend lifecycle badge to README.md."""
    log(f"Adding badge to README in {org}/{repo}")

    url = f'https://api.github.com/repos/{org}/{repo}/contents/README.md'

    # Fetch current README
    response = requests.get(url, headers=HEADERS)

    if response.status_code != 200:
        log(f"Warning: Could not fetch README.md: {response.status_code}")
        return False

    file_info = response.json()
    readme_content = base64.b64decode(file_info['content']).decode('utf-8')
    sha = file_info['sha']

    # Check if badge already exists
    if 'status.json' in readme_content:
        log("Badge already exists in README, skipping")
        return True

    # Create badge markdown
    badge = f"[![Status](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/{org}/{repo}/main/.github/badges/status.json?0&cacheSeconds=300)](https://github.com/{org}/{repo})"

    # Insert badge after first heading
    lines = readme_content.split('\n')

    # Find first heading
    insert_index = 0
    for i, line in enumerate(lines):
        if line.strip().startswith('#'):
            insert_index = i + 1
            break

    # Insert badge with blank lines
    lines.insert(insert_index, '')
    lines.insert(insert_index, badge)
    lines.insert(insert_index, '')

    new_readme = '\n'.join(lines)

    # Commit updated README
    response = requests.put(
        url,
        headers=HEADERS,
        json={
            'message': 'chore: add lifecycle status badge',
            'content': base64.b64encode(new_readme.encode()).decode(),
            'sha': sha,
        }
    )

    if response.status_code in (200, 201):
        log("Badge added to README successfully")
        return True
    else:
        log(f"Failed to update README: {response.status_code}")
        return False


def set_repository_variable(org, repo, var_name, var_value):
    """Set a repository variable."""
    url = f'https://api.github.com/repos/{org}/{repo}/actions/variables'

    # Try to create variable
    response = requests.post(
        url,
        headers=HEADERS,
        json={
            'name': var_name,
            'value': var_value,
        }
    )

    if response.status_code == 201:
        log(f"Set variable {var_name} = {var_value}")
        return True
    elif response.status_code == 409:
        # Variable exists, update it
        update_url = f'{url}/{var_name}'
        response = requests.patch(
            update_url,
            headers=HEADERS,
            json={'value': var_value}
        )
        if response.status_code == 204:
            log(f"Updated variable {var_name} = {var_value}")
            return True
        else:
            log(f"Failed to update variable {var_name}: {response.status_code}")
            return False
    else:
        log(f"Failed to create variable {var_name}: {response.status_code}")
        return False


def setup_repository_variables(org, repo):
    """Set required repository variables."""
    log(f"Setting repository variables for {org}/{repo}")

    success = True
    success &= set_repository_variable(org, repo, 'REGISTRY_OWNER', REGISTRY_OWNER)
    success &= set_repository_variable(org, repo, 'REGISTRY_REPO', REGISTRY_REPO)

    return success


def create_welcome_issue(org, repo, owner):
    """Create a welcome issue in the newly transferred repository."""
    log(f"Creating welcome issue in {org}/{repo}")

    today = datetime.today().strftime('%Y-%m-%d')
    due_date = (datetime.today() + timedelta(days=90)).strftime('%Y-%m-%d')

    body = f"""## 🎉 Welcome to {TARGET_ORG}!

Your resource **{repo}** has been successfully onboarded to the lifecycle management system.

### ✅ What Was Set Up

- ✅ Transferred from Anaconda-Sandbox to {TARGET_ORG}
- ✅ Quality check workflow added (`.github/workflows/quality-check.yml`)
- ✅ Owner certification workflow added (`.github/workflows/update-status.yml`)
- ✅ Lifecycle status badge added to README
- ✅ Registry entry created in `{REGISTRY_OWNER}/{REGISTRY_REPO}`
- ✅ Repository variables configured

### 🔐 Required: Add REGISTRY_TOKEN Secret

**Action needed by DevRel:** This repo needs the `REGISTRY_TOKEN` secret to update the registry.

1. Go to [Settings → Secrets and variables → Actions](https://github.com/{org}/{repo}/settings/secrets/actions)
2. Add a new repository secret:
   - **Name:** `REGISTRY_TOKEN`
   - **Value:** (use the shared REGISTRY_TOKEN value)

Without this secret, the owner certification workflow will fail.

### 📋 Next Steps for Resource Owner (@{owner})

1. **Verify quality checks work:**
   - Make a small change to README.md and push
   - Check that the quality check workflow runs successfully

2. **Certify your resource:**
   - Go to [Actions → Update Status (Owner Certification)](https://github.com/{org}/{repo}/actions)
   - Click "Run workflow"
   - Check the confirmation box
   - Click "Run workflow" button
   - This updates your `last_tested` date and keeps the badge green

3. **Understand the lifecycle:**
   - Your resource must be certified every **90 days**
   - If not certified, it will automatically be flagged for review
   - You'll receive an issue notification when flagging occurs

### 📚 Documentation

- [Getting Started Guide](https://github.com/Anaconda-Labs/criteria_checker/blob/main/GETTING_STARTED.md)
- [Quick Reference](https://github.com/Anaconda-Labs/criteria_checker/blob/main/QUICK_REFERENCE.md)
- [Quality Criteria](https://github.com/Anaconda-Labs/criteria_checker/blob/main/README.md)

### ⏰ Important Dates

- **Registered:** {today}
- **Next certification due:** {due_date}

If you don't certify within 90 days, the lifecycle engine will automatically flag this resource for review.

### 🔍 Badge Status

Your README now includes a lifecycle status badge that shows:
- 🟢 **active** - Resource tested within last 90 days
- 🟠 **needs review** - Flagged by lifecycle engine (stale or owner change)
- ⚪ **archived** - No longer maintained

---

**Questions?** Comment on this issue or reach out to DevRel.

**Note:** The badge may take up to 5 minutes to update after certification due to caching. Use hard refresh (Cmd+Shift+R / Ctrl+Shift+R) if needed.
"""

    url = f'https://api.github.com/repos/{org}/{repo}/issues'
    response = requests.post(
        url,
        headers=HEADERS,
        json={
            'title': f'[Intake] Welcome to {TARGET_ORG} Lifecycle System',
            'body': body,
            'labels': ['onboarding'],
        }
    )

    if response.status_code == 201:
        issue_url = response.json()['html_url']
        log(f"Created welcome issue: {issue_url}")
        return issue_url
    else:
        log(f"Failed to create welcome issue: {response.status_code}")
        return None


def process_resource(resource):
    """Process a single new resource through the intake pipeline."""
    repo_name = resource['repo']
    resource_type = resource.get('type', 'show')
    owner = resource.get('owner_github', 'unknown')
    source_org = resource.get('org', 'Anaconda-Sandbox')

    log(f"\n{'='*60}")
    log(f"Processing resource: {repo_name}")
    log(f"Type: {resource_type}, Owner: @{owner}")
    log(f"{'='*60}\n")

    resource_result = {
        'name': repo_name,
        'transferred': False,
        'workflows_added': False,
        'badge_added': False,
        'variables_set': False,
        'welcome_issue': None,
    }

    # Step 1: Transfer repository
    if source_org != TARGET_ORG:
        resource_result['transferred'] = transfer_repository(repo_name, source_org)
        if not resource_result['transferred']:
            log(f"❌ Failed to transfer {repo_name}, skipping remaining steps")
            return resource_result
    else:
        log(f"Repository already in {TARGET_ORG}, skipping transfer")
        resource_result['transferred'] = True

    # Step 2: Set up workflows
    resource_result['workflows_added'] = setup_workflows(TARGET_ORG, repo_name, resource_type)

    # Step 3: Add badge to README
    resource_result['badge_added'] = add_badge_to_readme(TARGET_ORG, repo_name)

    # Step 4: Set repository variables
    resource_result['variables_set'] = setup_repository_variables(TARGET_ORG, repo_name)

    # Step 5: Create welcome issue
    resource_result['welcome_issue'] = create_welcome_issue(TARGET_ORG, repo_name, owner)

    log(f"\n✅ Completed processing {repo_name}")
    return resource_result


def main():
    """Main intake automation logic."""
    log("Starting intake automation")

    # Validate environment
    if not INTAKE_TOKEN:
        log("ERROR: INTAKE_TOKEN not set")
        results['success'] = False
        results['error'] = 'INTAKE_TOKEN secret is not configured'
        sys.exit(1)

    if not BASE_SHA or not HEAD_SHA:
        log("ERROR: BASE_SHA or HEAD_SHA not set")
        results['success'] = False
        results['error'] = 'Could not determine PR diff (missing BASE_SHA or HEAD_SHA)'
        sys.exit(1)

    # Detect new resources
    new_resources = detect_new_resources()

    if not new_resources:
        log("No new resources to process")
        results['success'] = True
        results['processed'] = []
    else:
        # Process each new resource
        for resource in new_resources:
            try:
                resource_result = process_resource(resource)
                results['processed'].append(resource_result)
            except Exception as e:
                log(f"ERROR processing {resource['repo']}: {e}")
                results['success'] = False
                results['error'] = f"Exception during processing: {str(e)}"

    # Write results to file for PR comment
    with open('/tmp/intake_results.json', 'w') as f:
        json.dump(results, f, indent=2)

    log("\n" + "="*60)
    log("Intake automation complete")
    log(f"Processed {len(results['processed'])} resource(s)")
    log("="*60)

    if results['success']:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
