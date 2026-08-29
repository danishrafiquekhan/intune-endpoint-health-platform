# Intune Endpoint Health & Application Remediation Platform

This is my existing project, not something new — I built it doing endpoint/device support work and it's genuinely the strongest thing I have to show, so it needs to actually live here instead of sitting on a work laptop somewhere. Still need to go move the real scripts and docs in — what's below is the IAM tooling I added on top while getting this repo set up, plus a placeholder for the actual migration.

## What it does (once I move it in)
Proactive remediation for Intune-managed endpoints — catching things like a required app silently failing to install, a compliance policy drifting out of sync, or a device health check that would otherwise just sit there until someone notices during an audit. The idea was to stop finding these problems reactively when a user complains and start finding them before that happens.

## Why I built it in the first place
Manually checking device compliance and app deployment status across a fleet doesn't scale past a small number of machines, and by the time someone notices a pattern of failures it's usually already caused a support ticket. Wanted something that flags the drift automatically instead of waiting for it to become someone's problem.

## What's in here
- `scripts/` — the actual remediation/detection scripts once migrated, plus the two IAM scripts below
- `docs/` — design notes and usage

## IAM scripts (added separately, for the IAM side of the study plan)
Two Graph API scripts that don't need any premium Entra ID license — Graph access is free on any tenant, including the free Microsoft 365 Developer Program sandbox:
- `scripts/privileged_role_access_review.py` — lists everyone in a given directory role, flags anyone who hasn't signed in for 30+ days
- `scripts/orphaned_account_detection.py` — flags enabled accounts with no manager assigned

```bash
cd scripts
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
export AZURE_TENANT_ID=<your tenant id>
export AZURE_CLIENT_ID=<your app registration client id>
python3 privileged_role_access_review.py "Global Administrator"
python3 orphaned_account_detection.py
```
Both use device-code auth so there's no client secret sitting around to leak. I've checked they parse and import cleanly but haven't run them against a live tenant yet — I don't have one set up.

## The rest of the IAM catalog
| Test case | What it needs | Status |
|---|---|---|
| Access review | Graph, no premium license | done, above |
| Orphaned accounts | Graph, no premium license | done, above |
| Conditional Access test matrix | Entra ID P1 | needs a real tenant — free via M365 Developer Program's E5 trial |
| PIM walkthrough | Entra ID P2 | same E5 trial covers this |
| RBAC audit | Azure subscription | the free-tier one I already use for Terraform would work, just haven't done it |

The last three aren't blocked by cost, they're just not done — there's no honest way to demo a Conditional Access test matrix or a PIM walkthrough against an empty tenant with nothing configured in it. Signing up for the M365 dev sandbox is the actual next step, not something I'm waiting on money for.

No real device names, usernames, tenant IDs, or org data in this repo — sanitised before anything gets committed, screenshots included.

## One-time setup after cloning
```bash
git config core.hooksPath .githooks
```
