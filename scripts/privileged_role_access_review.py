#!/usr/bin/env python3
"""Category 4.1 — Access review automation.

Lists every member of a given Entra ID directory role and flags anyone who
hasn't signed in for 30+ days. Uses only Microsoft Graph, which is available
on ANY tenant tier (including the free Microsoft 365 Developer Program
sandbox) — no P1/P2 license needed for this one specifically.

Auth: device code flow (no client secret to manage/leak). Needs an app
registration with delegated permissions: RoleManagement.Read.Directory,
AuditLog.Read.All, User.Read.All.

Usage:
    export AZURE_TENANT_ID=<your tenant id>
    export AZURE_CLIENT_ID=<your app registration's client id>
    python3 privileged_role_access_review.py "Global Administrator"
"""
import datetime
import os
import sys

import requests
from azure.identity import DeviceCodeCredential

GRAPH = "https://graph.microsoft.com/v1.0"
STALE_DAYS = 30


def get_token() -> str:
    cred = DeviceCodeCredential(
        tenant_id=os.environ["AZURE_TENANT_ID"],
        client_id=os.environ["AZURE_CLIENT_ID"],
    )
    return cred.get_token("https://graph.microsoft.com/.default").token


def get_role_members(token: str, role_display_name: str) -> list[dict]:
    headers = {"Authorization": f"Bearer {token}"}

    roles = requests.get(
        f"{GRAPH}/directoryRoles",
        headers=headers,
        params={"$filter": f"displayName eq '{role_display_name}'"},
    ).json()
    if not roles.get("value"):
        raise SystemExit(f"Role '{role_display_name}' not found or not activated in this tenant.")
    role_id = roles["value"][0]["id"]

    members = requests.get(f"{GRAPH}/directoryRoles/{role_id}/members", headers=headers).json()
    return members.get("value", [])


def flag_stale_signins(token: str, members: list[dict]) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=STALE_DAYS)

    print(f"{'User':40} {'Last sign-in':25} {'Status'}")
    print("-" * 80)
    for member in members:
        user = requests.get(
            f"{GRAPH}/users/{member['id']}",
            headers=headers,
            params={"$select": "displayName,userPrincipalName,signInActivity"},
        ).json()
        last_signin = (user.get("signInActivity") or {}).get("lastSignInDateTime")
        upn = user.get("userPrincipalName", "?")

        if not last_signin:
            print(f"{upn:40} {'never recorded':25} FLAG - no sign-in activity on record")
            continue

        last_dt = datetime.datetime.fromisoformat(last_signin.replace("Z", "+00:00"))
        status = "FLAG - stale" if last_dt < cutoff else "ok"
        print(f"{upn:40} {last_signin:25} {status}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} '<role display name>'", file=sys.stderr)
        sys.exit(1)

    token = get_token()
    members = get_role_members(token, sys.argv[1])
    print(f"Found {len(members)} member(s) of '{sys.argv[1]}'\n")
    flag_stale_signins(token, members)
