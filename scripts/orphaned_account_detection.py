#!/usr/bin/env python3
"""Category 4.2 — Orphaned account detection.

Flags enabled user accounts with no manager assigned — a common JML
(joiner/mover/leaver) hygiene gap and a real risk: an account nobody owns is
an account nobody notices going stale. Uses only Microsoft Graph, free on
any tenant tier.

Auth: device code flow. Needs an app registration with delegated permission
User.Read.All.

Usage:
    export AZURE_TENANT_ID=<your tenant id>
    export AZURE_CLIENT_ID=<your app registration's client id>
    python3 orphaned_account_detection.py
"""
import os

import requests
from azure.identity import DeviceCodeCredential

GRAPH = "https://graph.microsoft.com/v1.0"


def get_token() -> str:
    cred = DeviceCodeCredential(
        tenant_id=os.environ["AZURE_TENANT_ID"],
        client_id=os.environ["AZURE_CLIENT_ID"],
    )
    return cred.get_token("https://graph.microsoft.com/.default").token


def find_orphaned_accounts(token: str) -> list[dict]:
    headers = {"Authorization": f"Bearer {token}"}
    orphaned = []

    url = f"{GRAPH}/users"
    params = {
        "$filter": "accountEnabled eq true",
        "$select": "id,displayName,userPrincipalName",
        "$top": "999",
    }

    while url:
        resp = requests.get(url, headers=headers, params=params).json()
        for user in resp.get("value", []):
            manager = requests.get(f"{GRAPH}/users/{user['id']}/manager", headers=headers)
            if manager.status_code == 404:
                orphaned.append(user)
        url = resp.get("@odata.nextLink")
        params = None  # nextLink already includes query params

    return orphaned


if __name__ == "__main__":
    token = get_token()
    orphaned = find_orphaned_accounts(token)

    print(f"Found {len(orphaned)} enabled account(s) with no manager assigned:\n")
    for user in orphaned:
        print(f"  - {user['userPrincipalName']} ({user.get('displayName', '?')})")

    print(
        "\nNote: 'no manager' isn't proof of orphaning on its own — service "
        "accounts and some external guests legitimately have none. Cross-"
        "reference against your account inventory before treating every "
        "result here as an action item."
    )
