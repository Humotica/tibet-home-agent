#!/usr/bin/env python3
"""One-shot setup for the home agent.

Creates the registry entry for the home agent's sub-`.aint`, adds the
parental-controls supervisor relation, and issues a session token —
all in one server-side call. Prints the export lines you can paste
into your shell to run the daemon.

This is a *bootstrap* helper for getting the demo up. The user-facing
flow (in the K/IT app + a small claim shell) lands later.

Run on the brain server (this script imports brain modules directly):

    python3 scripts/provision_home_agent.py home.vandemeent vandemeent

Args:
    sub_domain   — full sub-`.aint` name without `.aint` suffix
                   (e.g. `home.vandemeent`)
    parent       — supervising parent .aint (e.g. `vandemeent`)
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Make brain_api importable regardless of where this script is run from.
sys.path.insert(0, "/srv/jtel-stack/brain_api")


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    sub_full = sys.argv[1].strip().lower().removesuffix(".aint")
    parent = sys.argv[2].strip().lower().removesuffix(".aint")
    if "." not in sub_full:
        print(f"sub_domain must contain a dot (e.g. home.{parent}), got: {sub_full}", file=sys.stderr)
        return 2

    domain_key = f"{sub_full}.aint"
    parent_key = f"{parent}.aint"

    # 1. Registry entry
    reg_path = Path("/srv/jtel-stack/brain_api/ains_registry.json")
    with reg_path.open("r") as f:
        registry = json.load(f)
    domains = registry.setdefault("domains", {})
    if parent_key not in domains:
        print(f"parent {parent_key} not in registry — claim it first", file=sys.stderr)
        return 1

    if domain_key in domains:
        print(f"[provision] {domain_key} already exists — updating + reissuing session")
        existing = domains[domain_key]
    else:
        print(f"[provision] creating {domain_key} as supervised sub-`.aint` of {parent_key}")
        # Hardware-hash will be set when daemon first connects (via the same
        # ParentAttest device_rebind flow as Storm). For now we use a
        # placeholder so claim-by-hardware lookups don't accidentally match.
        # The daemon's *first* /api/ainternet/claim call (with provider
        # branch we just shipped) will succeed because the daemon supplies
        # both the hardware_hash *and* a public_key, and the hash will
        # then be bound at claim time via the rebind path.
        domains[domain_key] = {
            "agent": sub_full,
            "owner": domains[parent_key].get("owner", parent),
            "tier": "free",
            "is_founder": False,
            "is_clean": True,
            "trust_score": 0.5,
            "status": "active",
            "entity_type": "agent",
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "endpoint": "https://api.ainternet.org",
            "capabilities": ["chat", "ipoll"],
            "description": f"Home agent sub-`.aint` for {parent_key}",
            "parent_domain": parent_key,
            # No hardware_hash yet — daemon will bind it on first claim.
        }
        existing = domains[domain_key]

    # 2. Parental-controls supervisor relation
    pc_path = Path("/srv/jtel-stack/brain_api/data/parental_controls.json")
    with pc_path.open("r") as f:
        pc = json.load(f)
    sup = pc.setdefault("supervised", {})
    if sub_full not in sup:
        sup[sub_full] = {
            "parent": parent,
            "filter_level": "L1",
            "added_at": datetime.now(timezone.utc).isoformat(),
        }

    # 3. I-Poll registry — pull endpoint requires the agent to be approved
    #    here AND owns a pull_token. Keys in this registry are bare names
    #    (no `.aint`). The token is a per-agent secret used as
    #    X-IPoll-Token header by callers reading the agent's inbox.
    import secrets as _secrets
    ipoll_reg_path = Path("/srv/jtel-stack/brain_api/ipoll_registry.json")
    with ipoll_reg_path.open("r") as f:
        ipoll_reg = json.load(f)
    ipoll_agents = ipoll_reg.setdefault("agents", {})
    pull_token: str
    if sub_full in ipoll_agents and ipoll_agents[sub_full].get("pull_token"):
        pull_token = ipoll_agents[sub_full]["pull_token"]
        print(f"[provision] {sub_full} already in ipoll_registry — reusing pull_token")
    else:
        pull_token = _secrets.token_urlsafe(32)
        ipoll_agents[sub_full] = {
            "status": "approved",
            "tier": "verified",   # not sandbox — can message non-echo agents
            "trust_score": 0.5,
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "description": f"Home agent for {parent_key}",
            "capabilities": ["chat", "ipoll"],
            "pull_token": pull_token,
        }

    # Atomic writes
    for path, data in (
        (reg_path, registry),
        (pc_path, pc),
        (ipoll_reg_path, ipoll_reg),
    ):
        tmp = path.with_suffix(".tmp")
        with tmp.open("w") as f:
            json.dump(data, f, indent=2, sort_keys=True)
        tmp.replace(path)

    # 3. Issue a session token via the existing helper. We don't have a
    #    real Request object here, so we pass a minimal stub; _create_session
    #    only reads `request.client.host` from it for logging.
    class _Stub:
        class _Client: host = "127.0.0.1"
        client = _Client()
    from ainternet_auth import _create_session
    # Use a sentinel pubkey — when the daemon does a real claim later it
    # will overwrite this. Length must satisfy the model min (16 chars).
    sentinel_pubkey = "DAEMON_BOOTSTRAP_KEY_PLACEHOLDER"
    session = _create_session(sub_full, sentinel_pubkey, _Stub())
    token = session.get("token", "")
    expires = session.get("expires_at", "")

    print()
    print("─── home agent provisioned ────────────────────────────────────")
    print(f"  domain      {domain_key}")
    print(f"  parent      {parent_key}")
    print(f"  expires     {expires}")
    print()
    print("Export these to run the daemon:")
    print()
    print(f"  export HOME_AGENT_AINT='{sub_full}'")
    print(f"  export HOME_AGENT_TOKEN='{token}'")
    print(f"  export HOME_AGENT_IPOLL_TOKEN='{pull_token}'")
    print(f"  export HOME_AGENT_PROVIDER='echo'   # or gemini/anthropic/openai")
    print(f"  export BRAIN_URL='http://localhost:8000'")
    print()
    print("Then:  ainternet-home-agent")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
