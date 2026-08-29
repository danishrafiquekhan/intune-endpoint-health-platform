# Intune Endpoint Health & Application Remediation Platform

**Status: migrate existing work here** — this repo is the home for an already-built Intune endpoint health and application remediation project. Move/import the real project files here (scripts, docs, config) rather than starting over.

## What this is
_(fill in: what the platform monitors/remediates)_

## Why I built it
_(fill in: the operational problem it solves)_

## How it works
- `scripts/` — remediation/detection scripts, plus two IAM hygiene scripts (see below)
- `docs/` — design notes and usage

## IAM hygiene scripts (added for the IAM test-case catalog)
Two Microsoft Graph scripts that need **no premium license** — Graph API access is free on any tenant tier, including the free [Microsoft 365 Developer Program](https://developer.microsoft.com/microsoft-365/dev-program) sandbox:
- `scripts/privileged_role_access_review.py` — lists members of a given directory role, flags anyone with 30+ days of sign-in inactivity
- `scripts/orphaned_account_detection.py` — flags enabled accounts with no manager assigned

```bash
cd scripts
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
export AZURE_TENANT_ID=<your tenant id>
export AZURE_CLIENT_ID=<your app registration client id>   # delegated perms: RoleManagement.Read.Directory, AuditLog.Read.All, User.Read.All
python3 privileged_role_access_review.py "Global Administrator"
python3 orphaned_account_detection.py
```

Both use device-code auth (no client secret to manage or leak) and were syntax-verified but not run end-to-end against a live tenant in this session — see the tool-comparison table below for what's needed to finish that.

## Ideal tool vs. what's used, for the full IAM catalog
| Test case | Ideal (catalog spec) | Free path used / available |
|---|---|---|
| 4.1 Access review | Entra ID + PowerShell/Graph | Graph API script above — no premium license needed |
| 4.2 Orphaned accounts | Entra ID + PowerShell/Graph | Graph API script above — no premium license needed |
| 4.3 Conditional Access test matrix | Entra ID P1 (Conditional Access) | Needs a real tenant with CA enabled — the free M365 Developer Program sandbox includes an E5 trial (P1+P2) for 90 days; not yet built |
| 4.4 PIM activation walkthrough | Entra ID P2 (PIM) | Same M365 Developer Program E5 trial covers PIM; not yet built |
| 4.5 Least-privilege RBAC audit | Azure RBAC | Azure free-tier subscription (already set up for `terraform-labs`) is enough; not yet built |

**Why 4.3–4.5 aren't built yet:** they need an actual configured tenant/subscription with real state to review (policies, role assignments) — there's no meaningful way to demo them against synthetic/empty data. The free M365 Developer Program signup is the concrete next step, not a cost or licensing blocker.

## What I learned / trade-offs
_(fill in)_

## Security note
No real device names, usernames, tenant IDs, or organisational data — sanitise before committing, including in any screenshots.

## One-time setup after cloning
```bash
git config core.hooksPath .githooks   # enables the gitleaks secret-scan on commit
```
