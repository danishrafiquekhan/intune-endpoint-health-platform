**Intune Endpoint Health & Application Remediation Platform**

This is my existing project, not something new — I built it doing endpoint/device support work and it's genuinely the strongest thing I have to show, so it needs to actually live here instead of sitting on a work laptop somewhere. Still need to go move the real scripts and docs in — what's below is the IAM tooling I added on top while getting this repo set up, plus a placeholder for the actual migration.

**What it does (once I move it in)**
Proactive remediation for Intune-managed endpoints — catching things like a required app silently failing to install, a compliance policy drifting out of sync, or a device health check that would otherwise just sit there until someone notices during an audit. The idea was to stop finding these problems reactively when a user complains and start finding them before that happens.

**Why I built it in the first place**
Manually checking device compliance and app deployment status across a fleet doesn't scale past a small number of machines, and by the time someone notices a pattern of failures it's usually already caused a support ticket. Wanted something that flags the drift automatically instead of waiting for it to become someone's problem.

**What's in here**
- `scripts/` — the actual remediation/detection scripts once migrated, plus the IAM and asset reconciliation scripts below
- `docs/` — design notes, usage, and case studies (`docs/asset-reconciliation.md`, `docs/case-study-policy-bypass.md`)

**IAM scripts (added separately, for the IAM side of the study plan)**
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

**Asset reconciliation**
`scripts/asset_reconciliation.py` — based on a real cleanup reconciling several
hundred duplicate device records between LegacyCMDB and Intune (same serial
number under a different asset ID, or the same device name with case/
formatting drift). Takes a CSV of device records, groups likely duplicates
using exact serial match, normalized-name match, and difflib fuzzy-name
matching (three confidence tiers: high/medium/low), and writes a
reconciliation report with match reasoning and a suggested canonical record
per group. Stdlib difflib for the matching, pandas for the CSV/report
handling — didn't want a new fuzzy-matching dependency for something
difflib already handles at this data size.

`scripts/sample_device_records.csv` is a 41-row synthetic sample (entirely
made-up serials/names, no real hostnames) with 8 duplicate groups seeded in
plus unique negative examples; `scripts/sample_reconciliation_report.csv` is
the report the script produces against it, checked in so you can see the
output without running anything. Full writeup, including the false-positive
merge risk and why this is a triage aid and not an auto-merge tool, is in
[`docs/asset-reconciliation.md`](docs/asset-reconciliation.md). I've run this
against the synthetic sample only — not against a real LegacyCMDB/Intune
export, since that data doesn't leave the machine it came from.

**Case studies**
[`docs/case-study-policy-bypass.md`](docs/case-study-policy-bypass.md) — a
genericized writeup of a real investigation where a Chrome PWA install kept
getting blocked despite Intune policy looking correctly applied. Root cause
was profile-scoped, not device-scoped: the user was in a personal (non-
managed) Chrome profile, which doesn't inherit Intune-enforced Chrome policy
the way a managed profile does. Includes a detection-concept sketch for
"policy-managed app running under an unmanaged profile" — and is honest that
it stays conceptual, since Intune doesn't natively expose Chrome
profile-level telemetry to build a real rule against.

**The rest of the IAM catalog**
| Test case | What it needs | Status |
|---|---|---|
| Access review | Graph, no premium license | done, above |
| Orphaned accounts | Graph, no premium license | done, above |
| Asset reconciliation | pandas, stdlib difflib | done, above — synthetic data only |
| Policy bypass case study | write-up only, no live system | done, above — conceptual detection sketch, no working rule |
| Conditional Access test matrix | Entra ID P1 | needs a real tenant — free via M365 Developer Program's E5 trial |
| PIM walkthrough | Entra ID P2 | same E5 trial covers this |
| RBAC audit | Azure subscription | the free-tier one I already use for Terraform would work, just haven't done it |

The last three aren't blocked by cost, they're just not done — there's no honest way to demo a Conditional Access test matrix or a PIM walkthrough against an empty tenant with nothing configured in it. Signing up for the M365 dev sandbox is the actual next step, not something I'm waiting on money for.

No real device names, usernames, tenant IDs, or org data in this repo — sanitised before anything gets committed, screenshots included.

**One-time setup after cloning**
```bash
git config core.hooksPath .githooks
```
