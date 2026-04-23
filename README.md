# Resource Registry & Lifecycle Management System

Automated lifecycle management for Anaconda Labs educational resources (demos, tutorials, guides).

---

## Overview

This system provides:
- **Automated intake** - Transfer resources from Anaconda-Sandbox → Anaconda-Labs
- **Quality validation** - Automated checks before resources are accepted
- **Lifecycle monitoring** - Weekly freshness checks with automatic flagging
- **Self-service certification** - Resource owners can update their resource status
- **Status badges** - Visual indicators of resource health

---

## Architecture

### Core Components

1. **registry.yml** - Central manifest tracking all resources
2. **Intake workflows** - Automate resource onboarding
3. **Lifecycle engine** - Monitor resource freshness
4. **Quality checker** - Validate resources meet standards
5. **Status badges** - Visual health indicators

### Repository Structure

```
resource-registry/
├── registry.yml                          # Central resource manifest
├── workflow_diagrams.html                # Visual workflow documentation
├── .github/
│   ├── workflows/
│   │   ├── intake-automation.yml         # Transfer repos on PR merge
│   │   ├── intake-check.yml              # Validate PRs before merge
│   │   └── lifecycle-engine.yml          # Monitor freshness (weekly)
│   ├── scripts/
│   │   ├── intake_automation.py          # Repo transfer & setup logic
│   │   ├── lifecycle_check.py            # Freshness monitoring logic
│   │   └── quality_check.py              # Resource validation logic
│   └── resource-templates/
│       ├── quality-check.yml             # Template: quality validation workflow
│       ├── update-status.yml             # Template: owner certification workflow
│       └── README_BADGE_SNIPPET.md       # Template: status badge for READMEs
```

---

## Complete Workflow

### 1. Developer Creates Resource in Sandbox

**Location:** `Anaconda-Sandbox` organization

**Required files:**
- `README.md` with:
  - Owner GitHub handle (e.g., @username)
  - Target audience
  - Resource type (guide/show/tell)
  - Business metrics (for shows) or learning objectives (for guides)
- `environment.yml` or `pixi.toml`
- `LICENSE` (MIT)

**Optional:** Run local quality check using [criteria_checker](https://github.com/Anaconda-Labs/criteria_checker)

### 2. Submit Intake Request

**Action:** Open PR to `resource-registry` adding entry to `registry.yml`

**Entry format:**
```yaml
- repo: my-resource-name
  org: Anaconda-Labs                  # Target org after transfer
  source_org: Anaconda-Sandbox        # Current location (required for transfer)
  type: show                          # guide | show | tell
  owner_github: your-handle
  last_tested: '2026-04-23'
  status: active
  status_since: '2026-04-23'
  key_dependencies: []
  registered: '2026-04-23'
  reviewed_by: reviewer-handle
  notes: 'Optional notes about the resource'
```

**Important:** The `source_org` field tells the automation where to find the repo for transfer.

### 3. Automated Quality Check (PR)

**Workflow:** `intake-check.yml` runs automatically on PR

**Validates:**
- ✅ registry.yml syntax is valid
- ✅ All required fields present
- ✅ Resource exists in `source_org`
- ✅ README has owner, audience, LICENSE exists
- ✅ environment.yml or pixi.toml present
- ✅ Type-specific criteria met (learning objectives for guides, business metrics for shows)

**Result:** PR is blocked if checks fail

### 4. DevRel Review & Approval

**Manual step:** DevRel team member reviews:
- Quality check results
- Resource content and purpose
- Owner and audience appropriateness

**Action:** Merge PR if approved

### 5. Intake Automation (Post-Merge)

**Workflow:** `intake-automation.yml` triggers on merge

**Automated steps:**
1. **Detect new resources** - Compare registry diff to find additions
2. **Transfer repository** - Move from `source_org` → `org` using GitHub API
3. **Add workflow files:**
   - `.github/workflows/quality-check.yml` - On-demand quality validation
   - `.github/workflows/update-status.yml` - Owner certification
4. **Create status badge** - `.github/badges/status.json`
5. **Update README** - Add status badge with cache-busting
6. **Set repository variables:**
   - `REGISTRY_OWNER`: Anaconda-Labs
   - `REGISTRY_REPO`: resource-registry
7. **Create welcome issue** - Instructions for resource owner
8. **Post PR comment** - Report results back to intake PR

**Time:** ~30 seconds per resource

### 6. Manual Step: Add REGISTRY_TOKEN

**Required:** DevRel must manually add secret to transferred repo

**Location:** `https://github.com/Anaconda-Labs/{repo-name}/settings/secrets/actions`

**Secret details:**
- **Name:** `REGISTRY_TOKEN`
- **Scope:** `repo`, `workflow`
- **Purpose:** Allows update-status workflow to commit to registry.yml

**Time:** ~2 minutes per resource

**Why manual:** GitHub API security restriction prevents automated secret creation

### 7. Owner Certification

**Action:** Resource owner runs "Update Status (Owner Certification)" workflow

**Location:** Resource repo → Actions tab

**Workflow behavior:**
1. Owner confirms they've tested the resource end-to-end
2. Workflow updates `last_tested` date in registry.yml
3. If status was `needs_review`, changes to `active`
4. Status badge updates to green
5. 90-day freshness timer resets

**Frequency:** Owners should certify at least every 90 days

### 8. Lifecycle Monitoring

**Workflow:** `lifecycle-engine.yml` runs every Monday at 9am UTC

**Process:**
1. Check all resources in registry.yml
2. For each resource, calculate days since `last_tested`
3. **If > 90 days:**
   - Change status to `needs_review`
   - Update `status_since` date
   - Open issue in resource repo
   - Badge changes to orange
   - Owner receives notification
4. **If ≤ 90 days:**
   - Status remains `active`
   - Badge stays green

**Owner action:** Re-run certification workflow to reset timer

---

## Configuration

### Required Secrets

**In resource-registry:**
- `INTAKE_TOKEN`
  - **Scopes:** `repo` + `admin:org`
  - **Purpose:** Transfer repos, read/write registry, set up workflows
  - **Important:** Must be authorized for SAML SSO in Anaconda-Labs org

**In each resource repo (manual):**
- `REGISTRY_TOKEN`
  - **Scopes:** `repo` + `workflow`
  - **Purpose:** Update registry.yml from resource repo
  - **Setup:** DevRel adds manually after transfer

### Optional Variables

These have smart defaults and typically don't need to be set:
- `REGISTRY_OWNER` (defaults to `Anaconda-Labs`)
- `REGISTRY_REPO` (defaults to `resource-registry`)

---

## Resource Types

### Guide (Hands-on Tutorial)
**Goal:** Teach skills  
**Criteria:**
- 3-5 measurable learning objectives
- Time estimate
- Checkpoints with verification steps

### Show (Demo)
**Goal:** Inspire and demonstrate value  
**Criteria:**
- Business metrics (time/cost/risk saved)
- Customer-runnable without internal access
- Clear value proposition

### Tell (Explainer)
**Goal:** Build understanding  
**Criteria:**
- Tested code examples
- Progressive complexity
- Next steps for learners

---

## Status Badges

Resources display a status badge in their README:

```markdown
[![Status](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Anaconda-Labs/REPO-NAME/main/.github/badges/status.json&cacheSeconds=300)](https://github.com/Anaconda-Labs/REPO-NAME)
```

**Badge colors:**
- 🟢 **Green (active)** - Tested within 90 days
- 🟠 **Orange (needs_review)** - Stale, needs owner attention
- ⚫ **Gray (archived)** - No longer maintained

---

## Troubleshooting

### Intake Automation Failed

**Check:**
1. Is `INTAKE_TOKEN` configured in resource-registry secrets?
2. Does token have both `repo` and `admin:org` scopes?
3. Is token authorized for SAML SSO in Anaconda-Labs?
4. Does resource exist in `source_org`?
5. Check workflow logs in Actions tab

**Common issues:**
- 403 errors → SAML SSO not authorized
- 404 errors → Repo doesn't exist or wrong org
- No resources detected → Entry already existed before PR

### Owner Certification Failed

**Check:**
1. Is `REGISTRY_TOKEN` secret configured in resource repo?
2. Does token have `repo` and `workflow` scopes?
3. Is resource registered in registry.yml?
4. Check workflow logs in resource repo Actions tab

### Quality Check Failed

**Check criteria_checker guidance:**
- https://github.com/Anaconda-Labs/criteria_checker

**Common issues:**
- Missing owner GitHub handle in README
- No environment.yml or pixi.toml
- Missing LICENSE file
- Type-specific requirements not met (learning objectives, business metrics)

---

## FAQ

### Why the manual REGISTRY_TOKEN step?

GitHub API doesn't allow automated secret creation. This is a security feature. We considered alternatives:
- **GitHub App** - More complex setup, ongoing maintenance
- **Centralized token** - Network dependency, single point of failure  
- **Pre-populate in Sandbox** - Adds manual step earlier in process

Current approach minimizes manual work (~2 min) while maintaining security.

### Can I skip the source_org field?

Only if the resource is already in `Anaconda-Labs`. For transfers from Sandbox, `source_org` is required so the automation knows where to find the repo.

### What happens if I don't certify within 90 days?

- Status changes to `needs_review`
- Badge turns orange
- Issue opened in your repo
- Resource still works, just flagged as potentially stale
- Certify anytime to reset timer

### Can I transfer from a different org?

Yes! Set `source_org` to any org where you have access. The `INTAKE_TOKEN` must have permission to transfer from that org to `Anaconda-Labs`.

### How do I delete/archive a resource?

1. Update `status: archived` in registry.yml
2. Badge will turn gray
3. Lifecycle monitoring stops
4. Resource repo can be archived on GitHub

---

## Development

### Testing Changes

The system includes a test resource (`test-resource-intake`) in `Anaconda-Sandbox` for validating changes.

**Test process:**
1. Remove test resource from registry.yml (if present)
2. Merge removal PR
3. Add test resource back with `source_org: Anaconda-Sandbox`
4. Merge addition PR
5. Intake automation will detect it as new and transfer it
6. Verify all steps completed successfully

### Key Fixes Applied (2026-04-23)

- ✅ Added `source_org` field support for pre-transfer validation
- ✅ Fixed authentication: changed from deprecated `token` prefix to `Bearer`
- ✅ Authorized `INTAKE_TOKEN` for SAML SSO
- ✅ Fixed source_org detection in intake_automation.py
- ✅ Added missing pyyaml dependency in quality check job
- ✅ Added better error logging for API failures

### Viewing Workflow Diagrams

Open `workflow_diagrams.html` in a browser to see visual representations of the lifecycle workflows.

---

## Support

**Issues:** https://github.com/Anaconda-Labs/resource-registry/issues

**Owner:** @dbouquin

**Related Tools:**
- [criteria_checker](https://github.com/Anaconda-Labs/criteria_checker) - Quality validation tools

---

## License

MIT License - See LICENSE file for details.
