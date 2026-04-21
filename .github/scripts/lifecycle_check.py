#!/usr/bin/env python3
"""
Lifecycle engine for Anaconda-Labs educational resources.
Checks every resource in registry.yml and applies lifecycle rules:
  - Active: last_tested within 90 days, owner is current org member
  - Needs Review: flag condition exists; opens a GitHub issue
  - Archived: Needs Review unresolved for 30+ days
"""

import yaml
import os
import sys
import requests
from datetime import datetime, timedelta


GH_TOKEN = os.environ.get('REGISTRY_TOKEN') or os.environ.get('GITHUB_TOKEN')
HEADERS = {
    'Authorization': f'token {GH_TOKEN}',
    'Accept': 'application/vnd.github.v3+json',
    'X-GitHub-Api-Version': '2022-11-28',
}
STALENESS_DAYS = 90
REVIEW_DEADLINE_DAYS = 30


def check_org_membership(username: str, org: str) -> bool:
    """Returns True if username is a member of the org."""
    url = f'https://api.github.com/orgs/{org}/members/{username}'
    r = requests.get(url, headers=HEADERS)
    return r.status_code == 204


def get_open_lifecycle_issues(org: str, repo: str) -> list:
    """Return open issues tagged with [Lifecycle] in the repo."""
    url = f'https://api.github.com/repos/{org}/{repo}/issues'
    r = requests.get(url, headers=HEADERS, params={'state': 'open', 'labels': 'lifecycle'})
    if r.status_code != 200:
        return []
    return [i for i in r.json() if '[Lifecycle]' in i.get('title', '')]


def create_issue(org: str, repo: str, title: str, body: str) -> dict:
    """Create an issue in the specified repo."""
    url = f'https://api.github.com/repos/{org}/{repo}/issues'
    r = requests.post(url, headers=HEADERS, json={
        'title': title,
        'body': body,
        'labels': ['lifecycle']
    })
    if r.status_code == 201:
        print(f"  Opened issue: {r.json()['html_url']}")
        return r.json()
    else:
        print(f"  Warning: Could not create issue ({r.status_code}): {r.text}")
        return {}


def main():
    with open('registry.yml', 'r') as f:
        data = yaml.safe_load(f)

    today = datetime.today().date()
    changed = False

    print(f"\nLifecycle check — {today}\n{'='*50}")

    for resource in data['resources']:
        repo = resource['repo']
        org = resource.get('org', 'Anaconda-Labs')
        owner = resource['owner_github']
        status = resource['status']

        print(f"\n{org}/{repo} [{status}]")

        if status == 'archived':
            print("  Skipped (already archived)")
            continue

        flags = []

        # Check 1: Staleness
        last_tested = datetime.strptime(str(resource['last_tested']), '%Y-%m-%d').date()
        days_since = (today - last_tested).days
        if days_since > STALENESS_DAYS:
            flags.append(
                f'Last tested **{days_since} days ago** (threshold: {STALENESS_DAYS} days). '
                f'Owner should run end-to-end test and update registry.'
            )
        else:
            print(f"  Last tested: {last_tested} ({days_since} days ago) ✓")

        # Check 2: Owner membership
        if not check_org_membership(owner, org):
            flags.append(
                f'Owner **@{owner}** is not a current member of `{org}`. '
                f'A new owner should volunteer or the resource should be archived.'
            )
        else:
            print(f"  Owner @{owner}: active org member ✓")

        # Apply flags
        if flags and status == 'active':
            resource['status'] = 'needs_review'
            resource['status_since'] = str(today)
            changed = True

            flag_list = '\n'.join(f'- {f}' for f in flags)
            body = f"""## ⚠️ Lifecycle Review Required

This resource has been automatically flagged and moved to **Needs Review** status.

**Flags raised on {today}:**
{flag_list}

**What to do:**
1. Resolve the flag(s) above
2. If staleness: run the resource end-to-end, then trigger the [Update Status workflow]({f'https://github.com/{org}/{repo}/actions'}) in this repo
3. If owner change: comment on this issue to volunteer as new owner, then update `registry.yml`
4. Once resolved, close this issue

**Deadline:** If this issue is not resolved within {REVIEW_DEADLINE_DAYS} days of opening, this resource will be automatically moved to **Archived** status.

cc @{owner}
"""
            create_issue(org, repo, f'[Lifecycle] {repo} — Needs Review', body)
            print(f"  → Flagged as needs_review")

        elif status == 'needs_review':
            status_since_str = resource.get('status_since')
            if status_since_str:
                status_since = datetime.strptime(str(status_since_str), '%Y-%m-%d').date()
                days_in_review = (today - status_since).days
                print(f"  In needs_review for {days_in_review} days")

                if days_in_review > REVIEW_DEADLINE_DAYS:
                    resource['status'] = 'archived'
                    resource['status_since'] = str(today)
                    changed = True

                    body = f"""## 📦 Resource Archived

This resource has been in **Needs Review** status for **{days_in_review} days** without resolution and has been automatically moved to **Archived** status.

**Required action:**
Please update the README to include the following notice at the very top of the file:

```
> ⚠️ ARCHIVED — This resource is no longer maintained and may not work
> with current versions of the tools referenced.
```

A new owner may volunteer to restore this resource to Active status after:
1. Running end-to-end testing
2. Resolving all open issues
3. Updating `registry.yml` with a new `last_tested` date and `status: active`

cc @{owner}
"""
                    create_issue(org, repo, f'[Lifecycle] {repo} — Archived', body)
                    print(f"  → Moved to archived after {days_in_review} days")
            else:
                print(f"  In needs_review (no status_since date recorded)")
        else:
            print(f"  Status: {status} — no action needed ✓")

    if changed:
        with open('registry.yml', 'w') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        print(f"\nRegistry updated and saved.")
    else:
        print(f"\nNo status changes needed.")


if __name__ == '__main__':
    main()
