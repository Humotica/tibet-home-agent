"""Standalone tests for the M110 kill-guard.

Run as:
    cd /srv/jtel-stack/packages/tibet-home-agent
    python3 -m tests.test_kill_guard

The tests synthesize an Ed25519 keypair on the fly so they don't depend on
any production key. They cover the accept path and the major refusal paths.
"""
from __future__ import annotations

import base64
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Make sure `src/` is importable when this test is run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)
from tibet_home_agent.kill_guard import (
    PINNED_KEY_ID,
    verify_kill_authority,
)


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def _make_kill_request(
    *,
    privkey: Ed25519PrivateKey,
    issued_at: datetime,
    ttl_sec: int = 60,
    key_id: str = PINNED_KEY_ID,
    algo: str = "ed25519",
    scope: str = "fleet",
    tamper: bool = False,
) -> dict:
    """Build a signed kill-request. Set tamper=True to mutate the payload
    after signing, to produce an invalid signature."""
    payload = {
        "type": "kill-request",
        "thread_id": "deadbeef" * 4,
        "issued_at": issued_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ttl_sec": ttl_sec,
        "scope": scope,
        "reason": "unit-test",
        "tibet": {"key_id": key_id, "algo": algo},
    }
    canon = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sig = privkey.sign(canon)
    payload["tibet"]["signature"] = _b64(sig)
    if tamper:
        payload["reason"] = "tampered-after-sign"
    return payload


def main() -> int:
    privkey = Ed25519PrivateKey.generate()
    pinned_pub_b64 = _b64(privkey.public_key().public_bytes_raw())
    now = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)

    cases = []

    # ── Accept path ────────────────────────────────────────────────────────
    valid = _make_kill_request(privkey=privkey, issued_at=now)
    cases.append(("valid signed kill",        valid, pinned_pub_b64, now, True))

    # ── Refusal paths ──────────────────────────────────────────────────────
    expired = _make_kill_request(privkey=privkey, issued_at=now - timedelta(minutes=5), ttl_sec=60)
    cases.append(("expired (TTL passed)",     expired, pinned_pub_b64, now, False))

    future = _make_kill_request(privkey=privkey, issued_at=now + timedelta(minutes=5))
    cases.append(("issued in the future",     future, pinned_pub_b64, now, False))

    bad_key_id = _make_kill_request(privkey=privkey, issued_at=now, key_id="root_idd.v2")
    cases.append(("wrong key_id",             bad_key_id, pinned_pub_b64, now, False))

    bad_algo = _make_kill_request(privkey=privkey, issued_at=now, algo="rsa")
    cases.append(("non-ed25519 algo",         bad_algo, pinned_pub_b64, now, False))

    tampered = _make_kill_request(privkey=privkey, issued_at=now, tamper=True)
    cases.append(("tampered after signing",   tampered, pinned_pub_b64, now, False))

    other_priv = Ed25519PrivateKey.generate()
    wrong_signer = _make_kill_request(privkey=other_priv, issued_at=now)
    cases.append(("signed by another key",    wrong_signer, pinned_pub_b64, now, False))

    no_pin = _make_kill_request(privkey=privkey, issued_at=now)
    cases.append(("no pinned pubkey",         no_pin, "", now, False))

    too_long_ttl = _make_kill_request(privkey=privkey, issued_at=now, ttl_sec=9999)
    cases.append(("ttl_sec exceeds cap",      too_long_ttl, pinned_pub_b64, now, False))

    # ── Run ────────────────────────────────────────────────────────────────
    print(f"M110 kill_guard tests — pinned pubkey {pinned_pub_b64[:16]}…")
    fail = 0
    for label, payload, pin, when, expect in cases:
        ok, reason = verify_kill_authority(payload, pin, now_utc=when)
        verdict = "✓" if ok == expect else "✗"
        if ok != expect:
            fail += 1
        print(f"  {verdict}  expect={'accept' if expect else 'refuse':<6}  got={'accept' if ok else 'refuse':<6}  {label}  ({reason})")

    print()
    if fail == 0:
        print(f"  {len(cases)}/{len(cases)} cases pass")
        return 0
    print(f"  {fail}/{len(cases)} cases FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
